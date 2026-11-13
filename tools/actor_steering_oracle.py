"""Capture original vector normalization, live caller and Real48 square root."""
import argparse
from collections import Counter
import gzip
import hashlib
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn import x86_const as x86

EXE_SHA='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
LIB_SHA='ddb196ec82b52e502c18e4a34478bf7b9f61c83c2ebaa95c74d8ded45a95da9c'
REGS=[getattr(x86,'UC_X86_REG_'+name) for name in
      ('AX','BX','CX','DX','SI','DI','BP','CS','DS','ES','SS','SP','IP','EFLAGS')]
sha=lambda raw:hashlib.sha256(raw).hexdigest()
STOPS={0x17f00:0,0x1714f:0,0x192e2:1}


def profiles():
    rows=[]
    def add(family,**changes):
        row=dict(family=family,mode=0,dx=40,dy=20,speed=494,alias=0,bp=0x3fdc,
                 floor=0x200,flags=0x202,real=(0x81,0,0))
        row.update(changes);rows.append(row)
    values=(-32768,-257,-256,-1,0,1,127,128,255,256,257,32767)
    for dx,dy,speed in itertools.product(values,values,(0,1,43,214,494,1024,32767,32768,65535)):
        add('signed_vector_grid',dx=dx,dy=dy,speed=speed)
    for speed,(dx,dy) in itertools.product(range(256),((40,20),(9,12),(1,1))):
        add('speed_byte',dx=dx,dy=dy,speed=speed)
    for dx,dy,speed in itertools.product((-32768,0,1,32767),(-32768,0,1,32767),(0,494,32768,65535)):
        add('live_caller',mode=1,dx=dx,dy=dy,speed=speed)
    for alias,(dx,dy),speed in itertools.product(range(1,7),((0,0),(40,20),(-257,256)),(0,494,65535)):
        add('far_reference_alias',alias=alias,dx=dx,dy=dy,speed=speed)
    for bp,floor,flags in itertools.product((0x3fdc,0x700,0x30),(0x200,0x3f00,0xffff),(0x202,0x602)):
        add('stack_and_direction',bp=bp,floor=floor,flags=flags)
    for exponent,mantissa,negative in itertools.product(range(256),(0,1,(1<<39)-1),(False,True)):
        ax=exponent|((mantissa&255)<<8);bx=(mantissa>>8)&65535
        dx=(mantissa>>24)|(0x8000 if negative else 0)
        add('sqrt_bits',mode=2,real=(ax,bx,dx))
    return rows


def make_case(index,row):
    bp=row['bp'];mode=row['mode'];patches=[]
    values=[0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,bp,
            0x1920 if mode==2 else 0x1000,0x1aa2,0x40,0x7000,
            (bp-80)&65535,0xfc2 if mode==2 else 0x710d if mode==1 else 0x346b,row['flags']]
    def put(address,raw):
        patches.append((address,bytes(raw)))
    def word(address,value):
        put(address,struct.pack('<H',value&65535))
    word(0x1aa20+0x1afa,row['floor'])
    # Only initial stack/data are controlled; no instruction or later-state patch.
    if mode==2:
        values[0],values[1],values[3]=row['real']
        put(0x70000+values[11],struct.pack('<HH',0x7f00,0x1000))
    elif mode==1:
        for offset,value in ((-4,row['dx']),(-6,row['dy']),(-12,0x5aa5),(-14,0xa55a)):
            word(0x70000+((bp+offset)&65535),value)
        word(0x1aa20+0x2074,row['speed'])
    else:
        refs=[(0x120+i*2,0x5000) for i in range(5)]
        for pointer,value in zip(refs,(0xa55a,0x5aa5,row['speed'],row['dy'],row['dx'])):
            word(pointer[1]*16+pointer[0],value)
        alias=row['alias']
        if alias==1:
            refs[1]=refs[0]
        elif alias in (2,3,4):
            refs[1]=refs[alias]
        elif alias==5:
            refs[0]=refs[4]
        elif alias==6:
            refs[1]=(refs[0][0]+16,0x4fff)
        put(0x70000+values[11],struct.pack('<H10H',0x7f00,*(v for pair in refs for v in pair)))
    return tuple(values),patches


def encode_trace(output,trace):
    output.extend(struct.pack('<I',len(trace)))
    previous=None
    for row in trace:
        mask=sum(1<<column for column in range(14) if previous is None or row[column]!=previous[column])
        output.extend(struct.pack('<H',mask))
        for column in range(14):
            if mask&(1<<column):
                output.extend(struct.pack('<I' if column==13 else '<H',row[column]))
        previous=row


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported steering producer runtime')
    library=Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes())==LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    if not mapped():
        raise ValueError('Actual steering library mapping differs')
    source=(root/'tools/actor_steering_oracle.py').read_bytes();exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Canonical steering executable differs')
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only steering output')
    out.mkdir();index=-1
    try:
        rows=profiles();output=bytearray(b'LZSTEER1'+struct.pack('<I',len(rows)))
        coverage=set();states=write_count=0;outcomes=[0,0];domains=[0,0,0];max_states=0
        counterexamples=[]
        for index,row in enumerate(rows):
            values,patches=make_case(index,row);initial=bytearray(1048576)
            initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                if not 0<=address<=address+len(raw)<=1048576 or address<0x1aa20:
                    raise ValueError('Steering seed exceeds data/stack ownership')
                initial[address:address+len(raw)]=raw
            trace,writes,endpoints=[],[],[];stop=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Steering crossed interrupt/hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    registers=tuple(uc.reg_read(register) for register in REGS)
                    if not (registers[7]==0x1000 and (0x346b<=registers[12]<0x3587 or 0x710d<=registers[12]<0x712c) or
                            registers[7]==0x1920 and registers[12]<0x1820):
                        raise ValueError('Steering left declared code: '+str((registers[7],registers[12],address,size)))
                    trace.append(registers);coverage.add((registers[7],registers[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (0x50000<=address and address+size<=0x60000 or
                            0x70000<=address and address+size<=0x80001 or
                            0x1aa20<=address and address+size<=0x2aa20):
                        raise ValueError('Steering write left declared owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,x86.UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,x86.UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(values[7]*16+values[12],0 if observed else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:0x1aa20]!=image[:0xaa20]:
                    raise ValueError('Steering endpoint or original code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Steering observer changed full memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Steering writes do not reconstruct complete memory')
            trace.append(registers);outcome=STOPS[stop];outcomes[outcome]+=1;domains[row['mode']]+=1
            output.extend(struct.pack('<III13HI13HI',index,outcome,row['mode'],*values,*registers))
            output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:
                output.extend(struct.pack('<II',address,len(raw))+raw)
            encode_trace(output,trace);output.extend(struct.pack('<I',len(writes)))
            for entry in writes:
                output.extend(struct.pack('<IBH',*entry))
            if row['mode']==0 and row['alias']==0 and row['dx']==1 and row['dy']==0 and row['speed']>=32768:
                counterexamples.append(dict(case=index,dx=1,dy=0,speed=row['speed'],
                    original_vx_word=struct.unpack_from('<H',final,0x50122)[0]))
            states+=len(trace);write_count+=len(writes);max_states=max(max_states,len(trace))
            if len(output)>192*1024*1024:
                raise ValueError('Steering projection exceeds RAM reserve')
            if index%256==0:
                print(json.dumps(dict(status='running',case=index,cases=len(rows),states=states,bytes=len(output))),flush=True)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or (root/'tools/actor_steering_oracle.py').read_bytes()!=source or not mapped():
            raise ValueError('Steering producer inputs changed during capture')
        raw=bytes(output);packed=gzip.compress(raw,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-actor-steering-v1',cases=len(rows),domains=domains,
            profile_families=dict(Counter(r['family'] for r in rows)),asset_sha256={'LEZAC.EXE':EXE_SHA},
            source_sha256={'actor_steering_oracle.py':sha(source)},unicorn_version=unicorn.__version__,
            unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,original_code_bytes_verified=43552,
            register_states=states,maximum_case_states=max_states,ordered_writes=write_count,outcomes=outcomes,
            executed_instructions=[list(r) for r in sorted(coverage)],projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(packed),compressed_sha256=sha(packed),trace_storage='register-delta-v1',
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,later_state_injected=False,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,controlled_initial_memory=True,
            natural_capture=False,live_caller_cases=domains[1],square_root_cases=domains[2],
            real_near_return_executed=True,real_far_return_executed=True,counterexamples_to_speed_clamp=counterexamples,
            production_app_comparison=False,trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True,
            raw_memory_published=False,full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),states=states,writes=write_count,outcomes=outcomes,
            domains=domains,bytes=len(raw),compressed=len(packed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'producer-at-failure.py').write_bytes(source)
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error),source_sha256=sha(source)))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
