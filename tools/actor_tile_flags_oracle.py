"""Observe original tile classification, without executing its later continuations."""
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

from actor_contact_oracle import contact_case, contact_profiles
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
TILES=(0x2055,0x2056,0x204c,0x2050,0x204f,0x2053,0x2049,0x204a,0x2052,0x204d)
STOPS={0x165a8:0,0x16737:1,0x17018:2}
SOURCES=('actor_tile_flags_oracle.py','actor_contact_oracle.py','actor_precontact_oracle.py',
    'frame_actor_entry_oracle.py','boss_links_oracle.py','frame_camera_oracle.py',
    'frame_spawner_oracle.py','frame_waiting_oracle.py','ammo_hud_oracle.py')


def cases():
    rows=[]
    def direct(family,kind=1,behavior=0,tiles=None,bp=0x3fdc,flags=0x202):
        index=len(rows)
        values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,bp,
            0x1000,0x1aa2,0x40,0x7000,0x3000,0x65a2,flags)
        patches=[(0x70000+((bp+offset)&65535),bytes(((index*7+offset*29)&255,)))
            for offset in range(-55,9)]
        patches.extend(((0x70000+((bp-49)&65535),bytes((behavior,))),
            (0x70000+((bp-15)&65535),bytes((kind,)))))
        patches.extend((DATA+offset,bytes((value,))) for offset,value in
            zip(TILES,tiles if tiles is not None else [0]*len(TILES)))
        rows.append((0,family,values,patches))
    for kind,at,value in itertools.product((1,13),range(len(TILES)),range(256)):
        tiles=[0]*len(TILES);tiles[at]=value
        direct('cached_byte',kind=kind,tiles=tiles)
    for bits in range(256):
        direct('paired_cells',tiles=[1 if bits&(1<<i) else 255 for i in range(8)]+[0,0])
    for bits in range(16):
        tiles=[0]*len(TILES)
        for i,at in enumerate((0,3,8,9)):
            tiles[at]=1 if bits&(1<<i) else 255
        direct('kind13_cells',kind=13,tiles=tiles)
    for kind in range(256):
        direct('kind_byte',kind=kind,tiles=[82,83,77,76,0,1,255,76,76,76])
    for behavior in range(256):
        direct('behavior_byte',behavior=behavior,tiles=[1]*len(TILES))
    for bp,flags in itertools.product((0,1,31,32,37,38,65535),(2,0x202,0x602,0xad7)):
        direct('stack_wrap_flags',bp=bp,flags=flags,kind=13 if bp&1 else 1,tiles=[255,1]*5)
    base=contact_profiles()[0]
    for kind,behavior,pattern in itertools.product((1,13),(0,1,3,4,5),range(4)):
        row=dict(base,kind=kind,behavior=behavior,width=1,height=1,life=255,bombs=0,
            triggers=0,cells=0,group=0,flames=0,velocity=(0,0))
        values,patches=contact_case(len(rows),row)
        start=((row['y']>>3)-1)*64+((row['x']+4)>>3)-1
        for y,x in itertools.product(range(4),range(4)):
            value=(0,1,76,83)[(pattern+x+y)%4]
            patches.append((0x40000+((start+y*64+x)&65535),bytes((value,))))
        rows.append((1,'continuous_actor',values,patches))
    return rows


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported tile flags oracle profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual tile flags oracle mapping differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in SOURCES}
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Canonical tile flags executable differs')
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only tile flags output')
    out.mkdir();index=-1
    try:
        profiles=cases();output=bytearray(b'LZTILE01'+struct.pack('<I',len(profiles)))
        coverage=set();states=write_count=0;outcomes=[0]*3;domains=[0]*2
        for index,(domain,family,values,patches) in enumerate(profiles):
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                if not 0<=address<=address+len(raw)<=1048576:
                    raise ValueError('Tile flags seed exceeds memory')
                initial[address:address+len(raw)]=raw
            trace,writes,endpoints=[],[],[];stop=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Tile flags crossed an interrupt or hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    row=tuple(uc.reg_read(register) for register in REGS)
                    if not (row[7]==0x1000 and row[12]<0x83f0 or row[7]==0x1920 and row[12]<0x1820 or
                            row[7]==0x18ac and 0x517<=row[12]<0x594):
                        raise ValueError('Tile flags left declared code: '+str((row[7],row[12],address,size)))
                    trace.append(row);coverage.add((row[7],row[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x70000<=address and address+size<=0x80001 or
                            domain==1 and 0xa0000<=address and address+size<=0xb0001 or
                            domain==1 and 0x50000<=address and address+size<=0x60000):
                        raise ValueError('Tile flags write left declared owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(values[7]*16+values[12],0 if observed else stop,count=100000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Tile flags endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Tile flags observer changed complete memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Tile flags writes do not reconstruct final memory')
            trace.append(registers);outcome=STOPS[stop];outcomes[outcome]+=1;domains[domain]+=1
            output.extend(struct.pack('<III13HI13HI',index,outcome,domain,*values,*registers))
            output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:
                output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(row[column] for row in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for row in writes:
                output.extend(struct.pack('<IBH',*row))
            states+=len(trace);write_count+=len(writes)
            if len(output)>128*1024*1024:
                raise ValueError('Tile flags projection exceeds RAM reserve')
            if index%1024==0:
                print(json.dumps(dict(status='running',case=index,cases=len(profiles),states=states)),flush=True)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()) or sha(library.read_bytes())!=LIB_SHA:
            raise ValueError('Tile flags producer changed during generation')
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-actor-tile-flags-v1',cases=len(profiles),domains=domains,
            profile_families=dict(Counter(row[1] for row in profiles)),asset_sha256={'LEZAC.EXE':EXE_SHA},
            source_sha256=sources,unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,
            actual_library_mapping_verified=True,original_code_bytes_verified=43552,register_states=states,
            ordered_writes=write_count,outcomes=outcomes,executed_instructions=[list(row) for row in sorted(coverage)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,later_state_injected=False,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,continuous_actor_cases=domains[1],
            expiry_after_65a8_executed=False,motion_after_6737_executed=False,behavior_after_7018_executed=False,
            production_app_comparison=False,classification_all_flags_compared=True,prefix_arithmetic_flags_compared=False,
            trace_storage='register-columns-v1',raw_memory_published=False,full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(profiles),states=states,writes=write_count,
            outcomes=outcomes,domains=domains,bytes=len(raw),compressed=len(compressed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error),sources=sources))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
