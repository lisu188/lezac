"""Observe unchanged original collapse calls without publishing complete RAM."""
import argparse
from collections import Counter
import itertools
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN,UC_X86_INS_OUT
from capture_original_collapse_update import collapse,matrix,LEVELS_SHA
from capture_original_debris_update import debris,room
from scan_livels_debris_sites import load_levels
from transient_update_oracle import make_case as transient_case
from frame_camera_oracle import EXE_SHA,LIB_SHA,REGS,sha

DATA=0x1aa20
SOURCES=('collapse_update_oracle.py','capture_original_collapse_update.py','capture_original_debris_update.py',
         'scan_livels_debris_sites.py','transient_update_oracle.py','frame_camera_oracle.py')
ASSETS=('LEZAC.EXE','LIVELS.SCH','tests/fixtures/collapse_steps_original.txt','tests/fixtures/fracture_actor_original.txt')

def profiles(root):
    rows=[]
    def add(family,tiles,words,fragments=(),collapses=(),**extra):
        rows.append(dict(family=family,tiles=tiles,words=words,fragments=list(fragments),
            collapses=list(collapses),sparks=[],weights=[],**extra))
    tiles,words=room();add('empty_termination',tiles,words)
    level=load_levels(root/'LIVELS.SCH')[0]
    for line in (root/'tests/fixtures/collapse_steps_original.txt').read_text().splitlines():
        if not line.startswith('case='):continue
        fields=dict(token.split('=',1) for token in line.split());tiles=bytearray(level['tiles']);words=level['words'][:]
        for cell in fields['cells'].split(','):
            at,tile,word=cell.split(':');tiles[int(at)],words[int(at)]=int(tile,16),int(word,16)
        records=lambda value:[] if value=='none' else [bytes.fromhex(part) for part in value.split(',')]
        add('native_crosscheck',tiles,words,records(fields['debris']),records(fields['collapse']),
            native=fields,width=60,tick=int(fields['tick']),rng=0x12345678)
    if len(rows)!=28:raise ValueError('Native collapse case count differs')
    for family,tiles,words,fragments,collapses in matrix():add(family,tiles,words,fragments,collapses)
    for direction,own,other,mass in itertools.product((-1,1),(1,50,127),(-128,-1,0,1,127),(None,0,2,18,128)):
        tiles,words=room();target=120 if direction<0 else 152
        for cell in (136,137):tiles[cell],words[cell]=0x60,0x8001
        word=0xc002 if mass is None else 0x8002
        for cell in (target,) if mass is None else (target,target+1):tiles[cell],words[cell]=0x60,word
        source=collapse(136,137,vy=own*direction,sy=127 if direction>0 else -128)
        fragments=[debris(target,word,vy=other)] if mass is None else []
        targets=[] if mass is None else [collapse(target,target+1,word,vy=other,mass=mass)]
        add('vertical_debris_contact' if mass is None else 'vertical_collapse_contact',tiles,words,fragments,targets+[source])
    source=next(r for r in rows if r['family']=='horizontal_airborne')
    rows.append(dict(source,family='zero_width_divide',width=0))
    source=next(r for r in rows if r['family']=='vertical_collapse_contact' and r['collapses'][0][-1]==0)
    rows.append(dict(source,family='zero_mass_vertical',collapses=[v[:-1]+b'\0' for v in source['collapses']]))
    for source,floor in ((rows[1],65535),
            (next(r for r in rows if r['family']=='collapse_contact'),0xfcd0),
            (next(r for r in rows if r['family']=='debris_contact'),0xfcd0)):
        rows.append(dict(source,family='stack_error',floor=floor,native=None))
    return rows

def make_case(root,index,row,descriptors):
    values,patches=transient_case(index,row)
    patches.extend(((DATA+0x207a,struct.pack('<H',0x6620)),(DATA+0x206e,struct.pack('<H',0x5000)),
        (DATA+0x1bae,bytes(31*38)),(DATA+0xc21e,bytes(32*8)),(DATA+0xc322,descriptors),
        (DATA+0x208d,b'\0'),(DATA+0xc204,struct.pack('<H',row.get('width',16))),
        (DATA+0x78c2,struct.pack('<4H',row.get('tick',index&65535),0x4000,0,0)),
        (DATA+0x1afe,struct.pack('<I',row.get('rng',(0x12345678^(index*0x9e3779b9))&0xffffffff))),
        (0x8ff00,struct.pack('<H',0x806a))))
    values=list(values);values[12]=0x5102
    return tuple(values),patches

def native_check(row,final):
    fields=row.get('native')
    if not fields:return
    state=final[DATA:DATA+65536]
    records=lambda value:[] if value=='none' else [bytes.fromhex(part) for part in value.split(',')]
    debris,collapse=records(fields['after_debris']),records(fields['after_collapse'])
    if struct.unpack_from('<HH',state,0x207e)!=(199+len(debris),len(collapse)) or state[0x1afe:0x1b02].hex()!=fields['rng'] or \
        struct.unpack_from('<H',state,0x78c8)[0]!=int(fields['destroyed']) or \
        struct.unpack_from('<H',state,0x78c4)[0]!=int(fields['next_word'],16) or \
        state[0x292b:0x292b+len(debris)*11]!=b''.join(debris) or state[0x6620:0x6620+len(collapse)*15]!=b''.join(collapse):
        raise ValueError('Native collapse endpoint records differ')
    for cell in fields['after_cells'].split(','):
        at,tile,word=cell.split(':');at=int(at)
        if final[0x40000+at]!=int(tile,16) or struct.unpack_from('<H',final,0x50000+at*2)[0]!=int(word,16):
            raise ValueError('Native collapse endpoint map differs')

def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported collapse oracle loader')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual collapse oracle mapping differs')
    assets={name:sha((root/name).read_bytes()) for name in ASSETS}
    if assets['LEZAC.EXE']!=EXE_SHA or assets['LIVELS.SCH']!=LEVELS_SHA:raise ValueError('Canonical collapse assets differ')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in SOURCES}
    descriptor_row=next(line for line in (root/'tests/fixtures/fracture_actor_original.txt').read_text().splitlines()
        if line.startswith('sprites descriptors='))
    descriptors=bytes.fromhex(descriptor_row.split('=',1)[1])
    if len(descriptors)!=92*4:raise ValueError('Actor descriptors differ')
    exe=(root/'LEZAC.EXE').read_bytes();mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+4*i);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():raise ValueError('Use fresh RAM-only collapse output')
    out.mkdir();rows=profiles(root);output=bytearray(b'LZCLUP01'+struct.pack('<II',len(rows),len(exe))+exe)
    coverage=set();states=write_count=dense_cases=0;outcomes=[0,0,0,0];visits=Counter();index=-1
    try:
        for index,row in enumerate(rows):
            values,patches=make_case(root,index,row,descriptors);initial=bytearray(1048576)
            initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:initial[address:address+len(raw)]=raw
            trace=[];writes=[];results=[];stop=None;fault=False;case_states=0;dense=index%128==0
            for observed in (True,False):
                cpu=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16);cpu.mem_map(0,1048576);cpu.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):cpu.reg_write(register,value)
                def interrupt(uc,number,user):
                    nonlocal stop,fault
                    if number!=0:raise ValueError('Unexpected collapse interrupt')
                    fault=True;stop=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12]);uc.emu_stop()
                def io(*unused):raise ValueError('Unexpected collapse hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop,case_states
                    if address in (0x1806a,0x192e2,0x192e9):stop=address;uc.emu_stop();return
                    if not (0x10000<=address<0x183f0 or 0x18ac0<=address<0x19200 or 0x19200<=address<0x1aa20):
                        raise ValueError('Collapse left declared code: '+hex(address))
                    case_states+=1;coverage.add(address);visits[address]+=1
                    if dense and len(trace)<4000:trace.append(tuple(uc.reg_read(register) for register in REGS))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65537 or
                            0x40000<=address and address+size<=0x60001 or 0x80000<=address and address+size<=0x90001):
                        raise ValueError('Collapse write left declared memory: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                cpu.hook_add(unicorn.UC_HOOK_INTR,interrupt)
                cpu.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
                cpu.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
                if observed:
                    cpu.hook_add(unicorn.UC_HOOK_CODE,code);cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                cpu.emu_start(0x15102,0 if observed else stop,count=1000000)
                regs=tuple(cpu.reg_read(register) for register in REGS);final=bytes(cpu.mem_read(0,1048576))
                if stop is None or regs[7]*16+regs[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Collapse endpoint/code preservation differs')
                results.append((regs,final))
            if results[0]!=results[1]:raise ValueError('Collapse observer changed complete memory/registers')
            regs,final=results[0];reconstructed=bytearray(initial)
            for address,size,value in writes:reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:raise ValueError('Collapse writes do not reconstruct complete memory')
            native_check(row,final)
            outcome=2 if fault else 3 if stop==0x192e9 else int(stop==0x192e2);outcomes[outcome]+=1
            if not dense or case_states>4000:trace=[values]
            else:dense_cases+=1
            trace.append(regs)
            output.extend(struct.pack('<III13HI13HI',index,0,outcome,*values,*regs));output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(r[column] for r in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for write in writes:output.extend(struct.pack('<IBH',*write))
            if len(output)>32*1024**2:raise ValueError('Compact collapse corpus exceeds reserve')
            states+=case_states;write_count+=len(writes)
            if index%128==0:print(json.dumps(dict(status='running',case=index,cases=len(rows),bytes=len(output))),flush=True)
        if any(sha((root/name).read_bytes())!=v for name,v in assets.items()) or \
            any(sha((root/'tools'/name).read_bytes())!=v for name,v in sources.items()):raise ValueError('Collapse producer inputs changed')
        raw=bytes(output);packed=gzip.compress(raw,compresslevel=9,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-collapse-update-v1',cases=len(rows),dense_cases=dense_cases,
            profile_families=dict(Counter(r['family'] for r in rows)),asset_sha256=assets,source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,native_crosschecks=27,
            original_instructions=states,ordered_writes=write_count,outcomes=outcomes,executed_addresses=sorted(coverage),
            helper_visits={hex(a):visits[a] for a in (0x15102,0x1508b,0x1370e,0x13bb2,0x13d46,0x12f9f,0x106ab,0x19b45)},
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(packed),compressed_sha256=sha(packed),
            instruction_patches=0,calls_stubbed=0,hardware_io=0,interrupts_delivered=0,later_state_injected=False,
            controlled_initial_memory=True,natural_capture=False,raw_memory_published=False,actual_app_integration=False,full_frame_claim=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),dense_cases=dense_cases,states=states,writes=write_count,
            outcomes=outcomes,raw_bytes=len(raw),compressed_bytes=len(packed))),flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,family=rows[index]['family'] if index>=0 else None,error=repr(error)))+'\n');raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
