"""Capture the original pre-terrain movement boundary from authenticated full paths."""
import argparse
import gzip
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

import check_actor_motion_fixture as parent
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
INPUT=struct.Struct('<38s7h4B4B3HHIB512s')
RESULT=struct.Struct('<38s4h3HIBBHI')
MAGIC=b'LZNPM001'


def require(value,message):
    if not value:
        raise ValueError(message)


def cases(raw,image):
    at=0;domains=[0]*6;outcomes=[0]*5;excluded=0
    def take(size):
        nonlocal at
        require(size>=0 and at+size<=len(raw),'Truncated parent movement projection')
        value=raw[at:at+size];at+=size;return value
    def number(size):
        return int.from_bytes(take(size),'little')
    require(take(8)==b'LZMOTION' and number(4)==78927,'Parent movement domain differs')
    for index in range(78927):
        require(number(4)==index,'Parent movement case index differs')
        outcome,domain=number(4),number(4)
        require(outcome<5 and domain<6,'Parent movement case scope differs')
        outcomes[outcome]+=1;domains[domain]+=1
        entry=struct.unpack('<13HI',take(30));endpoint=struct.unpack('<13HI',take(30))
        selected=domain in (0,4,5);initial=None
        if selected:
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
        seeds=number(4);require(seeds<4096,'Parent movement seed reserve differs')
        for unused in range(seeds):
            address,size=number(4),number(4)
            require(size<=65536 and address+size<=1048576,'Parent movement seed exceeds memory')
            data=take(size)
            if selected:
                initial[address:address+size]=data
        if domain==0 and (entry[6]!=0x3fdc or struct.unpack_from('<H',initial,DATA+0x1afa)[0]!=0x200):
            selected=False;excluded+=1;initial=None
        states=number(4);require(1<states<3000000,'Parent movement trace reserve differs')
        previous=[0]*14;start=stop=None
        for row in range(states):
            mask=number(2);require(mask<0x4000 and (row!=0 or mask==0x3fff),'Parent movement delta mask differs')
            if selected:
                for column in range(14):
                    if mask&(1<<column):
                        previous[column]=number(4 if column==13 else 2)
                if row==0:
                    require(tuple(previous)==entry,'Parent movement entry checkpoint differs')
                if previous[7]==0x1000 and previous[12]==0x7018 and start is None:
                    start=tuple(previous)
                if previous[7]==0x1000 and previous[12]==0x732c and stop is None:
                    stop=tuple(previous)
            else:
                take(mask.bit_count()*2+(2 if mask&0x2000 else 0))
        if selected:
            require(tuple(previous)==endpoint and start is not None,'Parent movement trace extent differs')
        writes=number(4);require(writes<300000,'Parent movement write reserve differs')
        take(writes*7)
        if selected:
            if stop is None:
                require(outcome==3 and endpoint[7]==0x1000 and endpoint[12]==0x70dc,
                    'Normalized movement case has no declared prefix boundary')
                stop=endpoint
            yield index,domain,entry,initial,start,stop
    require(at==len(raw) and domains==[6475,376,6416,65552,54,54] and
        outcomes==[6437,72316,36,30,108] and excluded==14,'Parent movement extraction coverage differs')


def packet(memory,r):
    ss,bp,ds=r[10],r[6],r[8]
    def local(offset):
        return ss*16+((bp+offset)&65535)
    def word(address):
        return struct.unpack_from('<H',memory,address)[0]
    actor=word(local(6))*16+word(local(4))
    require(actor+38<=1048576,'Prefix actor reference exceeds memory')
    signed=lambda value:value-65536 if value>=32768 else value
    values=(bytes(memory[actor:actor+38]),
        *(signed(word(local(n))) for n in (-48,-44,-46,-4,-6,-12,-14)),
        *(memory[local(n)] for n in (-34,-33,-35,-36)),
        *memory[ds*16+0x2054:ds*16+0x2058],
        *(word(ds*16+n) for n in (0xc1e8,0x2072,0x2074)),
        word(ds*16+0x78c2),struct.unpack_from('<I',memory,ds*16+0x1afe)[0],
        memory[local(-32)],bytes(memory[ds*16+0x58:ds*16+0x258]))
    return values


def generate(root,out):
    out=out.resolve()
    require(out.is_relative_to(Path('/dev/shm')) and not out.exists(),'Use a new RAM-only prefix capture directory')
    require(unicorn.__version__=='2.1.4' and not any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')),
        'Unsupported prefix oracle runtime')
    library=Path(uclib._name).resolve(strict=True)
    def mapped():
        return sha(library.read_bytes())==LIB_SHA and any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines())
    require(mapped(),'Actual prefix library mapping differs')
    names=tuple(dict.fromkeys((*parent.INPUTS[1:],'tools/check_actor_motion_fixture.py','tools/nonplayer_motion_oracle.py')))
    sources={name:sha((root/name).read_bytes()) for name in names}
    require((root/'tools/nonplayer_motion_oracle.py').read_bytes()==Path(__file__).read_bytes(),'Prefix producer source differs')
    raw=parent.read_fixture(root,root/'tests/fixtures/actor_motion')
    exe=(root/'LEZAC.EXE').read_bytes();require(sha(exe)==EXE_SHA,'Canonical prefix executable differs')
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out.mkdir();rows=[];counts=[0,0,0];outcomes=[0,0,0];initial=final=None;index=-1
    try:
        for index,domain,entry,initial,expected_start,expected_stop in cases(raw,image):
            endpoints=[];input_values=None;instructions=0;writes=[];fault=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,entry):
                    engine.reg_write(register,value)
                def code(uc,address,size,user):
                    nonlocal input_values,instructions
                    if address==0x17018:
                        r=tuple(uc.reg_read(register) for register in REGS)
                        require(input_values is None and r==expected_start,'Original prefix-entry checkpoint differs')
                        input_values=packet(uc.mem_read(0,1048576),r)
                    if input_values is not None:
                        instructions+=1
                def write(uc,access,address,size,value,user):
                    require(size in (1,2) and DATA<=address and address+size<=0xb0001,'Prefix write left declared owners')
                    writes.append((address,size,value&((1<<(size*8))-1)))
                def intr(uc,number,user):
                    nonlocal fault
                    address=uc.reg_read(REGS[7])*16+uc.reg_read(REGS[12])
                    require(number==0 and address==0x170dc,'Unexpected original prefix interrupt')
                    fault=address;uc.emu_stop()
                def io(*unused):
                    raise ValueError('Original prefix attempted hardware I/O')
                engine.hook_add(unicorn.UC_HOOK_INTR,intr)
                engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,io,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(entry[7]*16+entry[12],0x1732c,count=3000000)
                r=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                require(r==expected_stop and final[0x10000:DATA]==image[:0xaa20],'Original prefix endpoint/code differs')
                endpoints.append((r,final,fault));del engine
            require(endpoints[0]==endpoints[1] and input_values is not None,'Prefix observer changed complete memory/registers')
            reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            require(reconstructed==final,'Prefix ordered writes do not reconstruct complete memory')
            output_values=packet(final,r);outcome=2 if fault is not None else 0
            expected=RESULT.pack(output_values[0],*output_values[2:4],*output_values[6:8],
                *output_values[16:19],output_values[20],output_values[21],outcome,r[12],instructions)
            rows.append(struct.pack('<IB',index,domain)+INPUT.pack(*input_values)+expected)
            counts[(0,4,5).index(domain)]+=1;outcomes[outcome]+=1
            if len(rows)%512==0:
                print(json.dumps(dict(status='running',cases=len(rows),original_case=index)),flush=True)
        require(counts==[6461,54,54] and outcomes==[6539,0,30],'Prefix case scope differs')
        require(mapped() and sha((root/'LEZAC.EXE').read_bytes())==EXE_SHA and all(
            sha((root/name).read_bytes())==digest for name,digest in sources.items()),'Prefix producer inputs changed')
        output=MAGIC+struct.pack('<I',len(rows))+bytes.fromhex(sha(raw))+b''.join(rows)
        packed=gzip.compress(output,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-nonplayer-motion-prefix-v1',cases=len(rows),domains=counts,outcomes=outcomes,
            parent_projection_sha256=sha(raw),parent_manifest_sha256=parent.MANIFEST_SHA,
            source_sha256=sources,asset_sha256={'LEZAC.EXE':EXE_SHA},unicorn_version=unicorn.__version__,
            unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,original_code_bytes_verified=43552,
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,
            frozen_parent_entry_and_endpoint_checkpoints_verified=True,instruction_patches=0,calls_stubbed=0,
            later_state_injected=False,interrupts_delivered=0,hardware_io=0,controlled_initial_memory=True,
            normalized_private_stack=True,excluded_private_stack_profiles=14,continuous_actor_cases=54,real_caller_cases=54,
            input_bytes=INPUT.size,result_bytes=RESULT.size,projection_bytes=len(output),projection_sha256=sha(output),
            compressed_bytes=len(packed),compressed_sha256=sha(packed),production_app_comparison=False,
            natural_capture=False,full_frame_claim=False,whole_game_parity=False,raw_memory_published=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),domains=counts,outcomes=outcomes,
            bytes=len(output),compressed=len(packed),sha256=sha(output))),flush=True)
    except BaseException as error:
        (out/'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        (out/'failed.json').write_text(json.dumps(dict(case=index,error=repr(error),sources=sources))+'\n')
        if initial is not None:
            (out/'failed-initial.bin').write_bytes(initial)
        if final is not None:
            (out/'failed-final.bin').write_bytes(final)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
