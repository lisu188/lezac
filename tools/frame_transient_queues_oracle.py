"""Observe original 804E queue selection and coupled calls without publishing RAM."""
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
from capture_original_collapse_update import collapse,LEVELS_SHA
from capture_original_debris_update import debris
from transient_update_oracle import profiles as transient_profiles
from collapse_update_oracle import profiles as collapse_profiles,make_case as collapse_case,native_check
from frame_camera_oracle import EXE_SHA,LIB_SHA,REGS,sha

DATA=0x1aa20
SOURCES=('frame_transient_queues_oracle.py','collapse_update_oracle.py','capture_original_collapse_update.py','capture_original_debris_update.py',
         'scan_livels_debris_sites.py','transient_update_oracle.py','frame_camera_oracle.py')
ASSETS=('LEZAC.EXE','LIVELS.SCH','tests/fixtures/collapse_steps_original.txt','tests/fixtures/fracture_actor_original.txt')

def profiles(root):
    rows=[dict(row,family='transient_'+row['family']) for row in transient_profiles()]
    collapse_rows=collapse_profiles(root)
    rows.extend(dict(row,family='collapse_'+row['family']) for row in collapse_rows)
    bases=[next(row for row in collapse_rows if row['family']==family) for family in
        ('horizontal_airborne','vertical_supported','diagonal_airborne','vertical_collapse_contact')]
    for base,motion,velocity,life in itertools.product(bases,(-128,-1,1,127),(-128,0,31,127),(0,1,2,255)):
        tiles=bytearray(base['tiles']);words=base['words'][:]
        for cell in (52,53):tiles[cell],words[cell]=0x75,0
        tiles[84],words[84]=0x76,0xc0aa
        sparks=[debris(52,0,vx=motion,sx=127 if motion>0 else -128,rest=life,glyph=0x75),
            debris(53,0,vy=velocity,sy=127,rest=2,glyph=0x75)]
        fragment=debris(84,0xc0aa,vx=velocity,vy=31,sx=127,sy=127,rest=2,glyph=0x76)
        rows.append(dict(base,family='mixed_'+base['family'],tiles=tiles,words=words,
            sparks=sparks,weights=[1,2],fragments=list(base['fragments'])+[fragment],native=None))
    retiring=next(row for row in transient_profiles() if row['family']=='shatter_retire' and
        int.from_bytes(row['fragments'][0][2:4],'little')==0xffbc and row['fragments'][0][9]==0x78)
    for velocity,rest,phase,with_collapse in itertools.product((-128,0,127),(0,99),(0,127),(False,True)):
        tiles=bytearray(retiring['tiles']);words=retiring['words'][:]
        tiles[84],words[84]=0x60,0xc0aa
        records=[]
        if with_collapse:
            for cell in (164,165):tiles[cell],words[cell]=0x60,0x8001
            tiles[180]=tiles[181]=1;records=[collapse(164,165)]
        rows.append(dict(retiring,family='retire_compaction_mixed' if with_collapse else 'retire_compaction_debris',
            tiles=tiles,words=words,fragments=list(retiring['fragments'])+[
                debris(84,0xc0aa,vx=velocity,sx=phase,rest=rest,glyph=0x60)],collapses=records))
    return rows

def make_case(root,index,row,descriptors):
    values,patches=collapse_case(root,index,row,descriptors)
    values=list(values);values[12]=0x804e
    return tuple(values),patches

def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported frame queue oracle loader')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library)) for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual frame queue oracle mapping differs')
    assets={name:sha((root/name).read_bytes()) for name in ASSETS}
    if assets['LEZAC.EXE']!=EXE_SHA or assets['LIVELS.SCH']!=LEVELS_SHA:raise ValueError('Canonical frame queue assets differ')
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
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():raise ValueError('Use fresh RAM-only frame queue output')
    out.mkdir();rows=profiles(root)
    if len(rows)!=3973:raise ValueError('Frame queue profile catalog differs')
    output=bytearray(b'LZTRQP01'+struct.pack('<II',len(rows),len(exe))+exe)
    coverage=set();states=write_count=dense_cases=0;outcomes=[0,0,0,0];visits=Counter();index=-1;patterns=[0,0,0,0];native_checks=0
    try:
        for index,row in enumerate(rows):
            values,patches=make_case(root,index,row,descriptors);initial=bytearray(1048576)
            initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:initial[address:address+len(raw)]=raw
            trace=[];writes=[];results=[];stop=None;fault=False;case_states=0;case_calls=0
            dense=index%128==0 or row['family'].startswith('retire_compaction_')
            for observed in (True,False):
                cpu=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16);cpu.mem_map(0,1048576);cpu.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):cpu.reg_write(register,value)
                def interrupt(uc,number,user):
                    nonlocal stop,fault
                    if number!=0:raise ValueError('Unexpected frame queue interrupt')
                    fault=True;stop=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12]);uc.emu_stop()
                def io(*unused):raise ValueError('Unexpected frame queue hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop,case_states,case_calls
                    if address in (0x1806a,0x192e2,0x192e9):stop=address;uc.emu_stop();return
                    if not (0x10000<=address<0x183f0 or 0x18ac0<=address<0x19200 or 0x19200<=address<0x1aa20):
                        raise ValueError('Frame queue left declared code: '+hex(address))
                    if address in (0x145fa,0x15102):
                        bit=1 if address==0x145fa else 2
                        if case_calls&bit:raise ValueError('Repeated original queue call')
                        case_calls|=bit
                    case_states+=1;coverage.add(address);visits[address]+=1
                    if dense and len(trace)<4000:trace.append(tuple(uc.reg_read(register) for register in REGS))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65537 or
                            0x40000<=address and address+size<=0x60001 or 0x80000<=address and address+size<=0x90001):
                        raise ValueError('Frame queue write left declared memory: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                cpu.hook_add(unicorn.UC_HOOK_INTR,interrupt)
                cpu.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
                cpu.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
                if observed:
                    cpu.hook_add(unicorn.UC_HOOK_CODE,code);cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                cpu.emu_start(0x1804e,0 if observed else stop,count=1000000)
                regs=tuple(cpu.reg_read(register) for register in REGS);final=bytes(cpu.mem_read(0,1048576))
                if stop is None or regs[7]*16+regs[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Frame queue endpoint/code preservation differs')
                results.append((regs,final))
            if results[0]!=results[1]:raise ValueError('Frame queue observer changed complete memory/registers')
            regs,final=results[0];reconstructed=bytearray(initial)
            for address,size,value in writes:reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:raise ValueError('Frame queue writes do not reconstruct complete memory')
            if row.get('native') and not case_calls&1:
                native_check(row,final);native_checks+=1
            patterns[case_calls]+=1
            outcome=2 if fault else 3 if stop==0x192e9 else int(stop==0x192e2);outcomes[outcome]+=1
            if not dense or case_states>4000:trace=[values]
            else:dense_cases+=1
            trace.append(regs)
            output.extend(struct.pack('<III13HI13HI',index,case_calls,outcome,*values,*regs));output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(r[column] for r in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for write in writes:output.extend(struct.pack('<IBH',*write))
            if len(output)>32*1024**2:raise ValueError('Compact frame queue corpus exceeds reserve')
            states+=case_states;write_count+=len(writes)
            if index%128==0:print(json.dumps(dict(status='running',case=index,cases=len(rows),bytes=len(output))),flush=True)
        if any(sha((root/name).read_bytes())!=v for name,v in assets.items()) or \
            any(sha((root/'tools'/name).read_bytes())!=v for name,v in sources.items()):raise ValueError('Frame queue producer inputs changed')
        caller_addresses={0x1804e,0x18053,0x18055,0x1805b,0x1805d,0x18060,0x18065,0x18067}
        if not caller_addresses.issubset(coverage) or not all(patterns) or \
            visits[0x145fa]!=patterns[1]+patterns[3] or visits[0x15102]!=patterns[2]+patterns[3]:
            raise ValueError('Frame queue caller/call coverage differs')
        raw=bytes(output);packed=gzip.compress(raw,compresslevel=9,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-frame-transient-queues-v1',cases=len(rows),dense_cases=dense_cases,
            profile_families=dict(Counter(r['family'] for r in rows)),asset_sha256=assets,source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,native_input_cases=27,native_endpoint_crosschecks=native_checks,call_patterns=patterns,
            original_instructions=states,ordered_writes=write_count,outcomes=outcomes,executed_addresses=sorted(coverage),
            caller_instructions_covered=True,
            helper_visits={hex(a):visits[a] for a in (0x1804e,0x145fa,0x15102,0x1456b,0x145ce,0x150be,
                0x1508b,0x1370e,0x13bb2,0x13d46,0x12f9f,0x106ab,0x19b45)},
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(packed),compressed_sha256=sha(packed),
            instruction_patches=0,calls_stubbed=0,hardware_io=0,interrupts_delivered=0,later_state_injected=False,
            controlled_initial_memory=True,natural_capture=False,raw_memory_published=False,actual_app_integration=False,full_frame_claim=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),dense_cases=dense_cases,states=states,writes=write_count,
            outcomes=outcomes,call_patterns=patterns,native_endpoint_crosschecks=native_checks,raw_bytes=len(raw),compressed_bytes=len(packed))),flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,family=rows[index]['family'] if index>=0 else None,error=repr(error)))+'\n');raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
