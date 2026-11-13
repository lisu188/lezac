"""Execute complete original 45FA calls, including sparks, debris and real callees."""
import argparse
from collections import Counter
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT
from capture_original_debris_update import matrix, room, debris
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
SOURCES=('transient_update_oracle.py','capture_original_debris_update.py',
         'scan_livels_debris_sites.py','frame_camera_oracle.py')
LIMIT=16*1024**2

def profiles():
    rows=[]
    def add(family,tiles,words,fragments=(),collapses=(),sparks=(),weights=None):
        rows.append(dict(family=family,tiles=tiles,words=words,fragments=list(fragments),
            collapses=list(collapses),sparks=list(sparks),weights=list(weights or [1]*len(sparks))))
    tiles,words=room();add('empty',tiles,words)
    for family,tiles,words,fragments,collapses in matrix():
        add(family,tiles,words,fragments,collapses)
    motions=((0,0,0,0),(127,0,127,0),(-128,0,-128,0),(0,127,0,127),(0,-128,0,-128),(127,127,127,127))
    for motion,target,life in itertools.product(motions,(0,0x75,1,0x66,0x60),(0,1,2)):
        vx,vy,fx,fy=motion;tiles,words=room();tiles[136]=0x75
        dx=1 if vx>0 else -1 if vx<0 else 0;dy=1 if vy>0 else -1 if vy<0 else 0
        cell=136+dx+dy*16
        if cell!=136:
            tiles[cell]=target
        fragments=[]
        if target==0x60 and cell!=136:
            words[cell]=0xc001;fragments=[debris(cell,0xc001,vx=-13,vy=31)]
        add('spark_motion_contact',tiles,words,fragments,sparks=[debris(136,0,vx,vy,fx,fy,life,0x75,2)])
    for weights in ((1,2),(0,0)):
        tiles,words=room();tiles[136]=tiles[137]=0x75
        add('spark_compaction',tiles,words,sparks=[debris(136,0,rest=1,glyph=0x75),
            debris(137,0,rest=2,glyph=0x75)],weights=weights)
    tiles,words=room();tiles[136]=0x75;tiles[137]=0x60;words[137]=0x8001
    collapse=struct.pack('<HHHBBBBHBBB',274,274,0x8001,0,0,0,0,255,0,0,0)
    add('spark_zero_mass_fault',tiles,words,collapses=[collapse],
        sparks=[debris(136,0,vx=127,sx=127,rest=2,glyph=0x75)],weights=[0])
    for value in (0x8001,0xc00d):
        tiles,words=room();tiles[136]=0x75;tiles[137]=0x60;words[137]=value
        add('spark_missing_identity',tiles,words,sparks=[debris(136,0,vx=127,sx=127,rest=2,glyph=0x75)])
    for source,floor in ((rows[0],65535),
            (next(r for r in rows if r['family']=='debris_contact'),0xfcd0),
            (next(r for r in rows if r['family']=='spark_motion_contact' and r['tiles'][137]==0x66),0xfcd0)):
        rows.append(dict(source,family='stack_error',floor=floor))
    return rows

def make_case(index,row):
    patches=[]
    def put(address,raw):
        patches.append((address,raw))
    put(DATA+0x1afa,struct.pack('<H',row.get('floor',0)));put(DATA+0x1afe,struct.pack('<I',(0x12345678^(index*0x9e3779b9))&0xffffffff))
    put(DATA+0x2076,struct.pack('<6H',len(row['sparks']),0,0,0x209e,199+len(row['fragments']),len(row['collapses'])))
    if row['sparks']:
        put(DATA+0x209e,b''.join(row['sparks']));put(DATA+0x78d6,bytes(row['weights']))
    if row['fragments']:
        put(DATA+0x2093+2200,b''.join(row['fragments']))
    if row['collapses']:
        put(DATA+0x6620,b''.join(row['collapses']))
    for offset,raw in ((0x6612,struct.pack('<HH',0,0x5000)),(0xc1e0,struct.pack('<HH',0,0x4000)),
                       (0xc1fe,struct.pack('<H',0x4000)),(0xc204,struct.pack('<H',16)),
                       (0x78c2,struct.pack('<H',index&65535)),(0x661e,b'\x5a')):
        put(DATA+offset,raw)
    put(0x40000,bytes(row['tiles']));put(0x50000,struct.pack('<'+'H'*len(row['words']),*row['words']))
    put(0x8ff00,struct.pack('<H',0x8060))
    values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3fee,0x1000,0x1aa2,0x40,0x8000,0xff00,0x45fa,0x202)
    return values,patches

def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported updater oracle loader')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual updater oracle mapping differs')
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Canonical updater MZ differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in SOURCES}
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+4*i);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a fresh RAM-only updater output')
    out.mkdir();rows=profiles();output=bytearray(b'LZTRUP01'+struct.pack('<II',len(rows),len(exe))+exe)
    coverage=set();states=write_count=dense_cases=0;outcomes=[0,0,0];visits=Counter();index=-1
    try:
        for index,row in enumerate(rows):
            values,patches=make_case(index,row);initial=bytearray(1048576)
            initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                initial[address:address+len(raw)]=raw
            trace=[];writes=[];results=[];stop=None;fault=False;case_states=0;dense=index%64==0
            for observed in (True,False):
                cpu=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                cpu.mem_map(0,1048576);cpu.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    cpu.reg_write(register,value)
                def interrupt(uc,number,user):
                    nonlocal stop,fault
                    if number!=0:
                        raise ValueError('Unexpected updater interrupt')
                    fault=True;stop=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12]);uc.emu_stop()
                def io(*unused):
                    raise ValueError('Unexpected updater hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop,case_states
                    if address in (0x18060,0x192e2):
                        stop=address;uc.emu_stop();return
                    if not (0x10000<=address<0x183f0 or 0x19200<=address<0x1aa20):
                        raise ValueError('Updater left declared code: '+hex(address))
                    case_states+=1;coverage.add(address);visits[address]+=1
                    if dense and len(trace)<4000:
                        trace.append(tuple(uc.reg_read(register) for register in REGS))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65537 or
                            0x40000<=address and address+size<=0x60001 or 0x80000<=address and address+size<=0x90001):
                        raise ValueError('Updater write left declared memory: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                cpu.hook_add(unicorn.UC_HOOK_INTR,interrupt)
                cpu.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
                cpu.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
                if observed:
                    cpu.hook_add(unicorn.UC_HOOK_CODE,code);cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                cpu.emu_start(0x145fa,0 if observed else stop,count=1000000)
                regs=tuple(cpu.reg_read(register) for register in REGS);final=bytes(cpu.mem_read(0,1048576))
                if stop is None or regs[7]*16+regs[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Updater endpoint/code preservation differs')
                results.append((regs,final))
            if results[0]!=results[1]:
                raise ValueError('Updater observer changed complete memory/registers')
            regs,final=results[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Updater writes do not reconstruct complete final memory')
            outcome=2 if fault else int(stop==0x192e2);outcomes[outcome]+=1
            if not dense or case_states>4000:
                trace=[values]
            else:
                dense_cases+=1
            trace.append(regs)
            output.extend(struct.pack('<III13HI13HI',index,int(bool(row['sparks'])),outcome,*values,*regs))
            output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:
                output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(r[column] for r in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for entry in writes:
                output.extend(struct.pack('<IBH',*entry))
            if len(output)>LIMIT:
                raise ValueError('Updater compact corpus exceeds 16 MiB')
            states+=case_states;write_count+=len(writes)
            if index%64==0:
                print(json.dumps(dict(status='running',case=index,cases=len(rows),bytes=len(output))),flush=True)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or any(sha((root/'tools'/n).read_bytes())!=v for n,v in sources.items()):
            raise ValueError('Updater producer inputs changed')
        raw=bytes(output);packed=gzip.compress(raw,compresslevel=9,mtime=0)
        (out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-transient-update-v1',cases=len(rows),dense_cases=dense_cases,
            profile_families=dict(Counter(r['family'] for r in rows)),asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,original_instructions=states,
            ordered_writes=write_count,outcomes=outcomes,executed_addresses=sorted(coverage),
            helper_visits={hex(a):visits[a] for a in (0x13eda,0x1452a,0x1458d,0x19b45,
                0x13a7e,0x13b18,0x13bb2,0x13d46,0x1370e,0x1414a,0x13fa6)},
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(packed),compressed_sha256=sha(packed),
            instruction_patches=0,calls_stubbed=0,hardware_io=0,interrupts_delivered=0,later_state_injected=False,
            controlled_initial_memory=True,natural_capture=False,raw_memory_published=False,actual_app_integration=False,full_frame_claim=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),dense_cases=dense_cases,states=states,writes=write_count,
            outcomes=outcomes,raw_bytes=len(raw),compressed_bytes=len(packed))),flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,family=rows[index]['family'] if index>=0 else None,error=repr(error)))+'\n')
        raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
