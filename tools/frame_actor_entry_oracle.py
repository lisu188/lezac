"""Unchanged post-render prefix through links and the first actor-body handoff."""
import argparse
import gzip
import itertools
import json
import os
from pathlib import Path
import struct

import unicorn
from unicorn.unicorn_py3.unicorn import uclib
from unicorn.x86_const import UC_X86_INS_IN, UC_X86_INS_OUT

from ammo_hud_oracle import ASSET_SHA, sprites
from boss_links_oracle import sine_table
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha
from frame_spawner_oracle import inputs as spawner_inputs, profiles as spawner_profiles
from frame_waiting_oracle import profiles as waiting_profiles, seeds as waiting_seeds

DATA=0x1aa20
STOPS={0x1615a:0,0x1804e:1,0x177dc:2,0x11b14:3,0x192e2:4}


def direct_profiles():
    rows=[]
    def add(**changes):
        row=dict(states=(0,0),actors=0,links=0,counter=0,mode=0,floor=0x200,sp=0x3fe4)
        row.update(changes);rows.append(row)
    for first,second,actors,links,counter in itertools.product((0,1,2,255),(0,1,2,255),
            (0,1,30,255),(0,1,6),(0,229,230,255)):
        add(states=(first,second),actors=actors,links=links,counter=counter)
    for kind,mode in itertools.product(range(3),(0,1,2,3,255)):
        add(states=(1,1) if kind==1 else (0,1) if kind==2 else (0,0),
            actors=1 if kind==0 else 0,links=6,mode=mode)
    add(actors=1,links=255)
    for links,floor,sp in itertools.product((0,1),(0x4000,0x3dc0,0x200),(0x3fe4,0x210)):
        add(actors=1,links=links,floor=floor,sp=sp,mode=3)
    return rows


def tail_seeds(index,row,sines,prefix=False):
    patches=[]
    def data(offset,raw):
        patches.append((DATA+offset,raw))
    def word(offset,value):
        data(offset,struct.pack('<H',value))
    count=row['links']
    data(0x7bda,sines)
    word(0x1afa,row['floor'])
    if not prefix:
        patches.append((0x70000+row['sp']-1024,bytes((i*29+index*7+11)&255 for i in range(1040))))
        data(0x208d,bytes((row['actors'],)))
        data(0x79e6,bytes(row['states']))
    for slot in range(-1,31):
        at=0x1bae+slot*38
        if not prefix:
            data(at,bytes((i*17+index*7+slot)&255 for i in range(38)))
        data(at+1,bytes(((slot+1)&255,)))
        data(at+22,bytes((6,3,6,0,0,row['mode'],1,9,8,12,1,2,1,255)))
    for visual in range(33 if prefix else 0,256):
        data(0xc21e+visual*8,struct.pack('<4H',(visual*977+index*13+0x7fff)&65535,
            (visual*1013+index*17+0x8000)&65535,0xa55a,0x5aa5))
    for frame in range(16):
        word(0xc324+frame*4,(frame*197+index*23+0x5a)&65535)
    for link in range(1,count+1):
        raw=bytearray((i*11+index*7+link*19)&255 for i in range(16))
        raw[:7]=bytes((2,3,3,0 if count==255 or link%2==0 else 255,100,48,(index+link)&255))
        struct.pack_into('<2H',raw,7,0xffff,0x8000)
        raw[15]=0x80
        data(0x79ea+link*16,raw)
    data(0x79f9,bytes((count,)))
    data(0x79b9,bytes((row['counter'],)))
    return patches


def cases(tiles,atlas,sines):
    waiting,spawners=waiting_profiles(),spawner_profiles()
    result=[]
    for index,row in enumerate(waiting):
        profile=spawners[index%len(spawners)]
        row=dict(row);row['floor']=max(row['floor'],profile[4])
        tail=dict(links=(0,1,6)[index%3],counter=(0,229,230,255)[index%4],mode=(0,1,2,3,255)[index%5],floor=row['floor'])
        patches=spawner_inputs(index,profile)+waiting_seeds(index,row,tiles,atlas)+tail_seeds(index,tail,sines,True)
        result.append((0x7a57,0x3fe4,row['flags'],patches))
    for row in direct_profiles():
        index=len(result)
        result.append((0x7ebb,row['sp'],0x602 if index%2 else 0x202,tail_seeds(index,row,sines)))
    return result,len(waiting)


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(key in os.environ for key in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported frame actor oracle profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual frame actor oracle mapping differs')
    names=('frame_actor_entry_oracle.py','boss_links_oracle.py','frame_camera_oracle.py',
        'frame_spawner_oracle.py','frame_waiting_oracle.py','ammo_hud_oracle.py')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in names}
    pins=dict(ASSET_SHA,**{'LEZAC.EXE':EXE_SHA})
    assets={name:(root/name).read_bytes() for name in pins}
    if any(sha(assets[name])!=digest for name,digest in pins.items()):
        raise ValueError('Canonical frame actor asset differs')
    exe=assets['LEZAC.EXE'];mz=struct.unpack_from('<14H',exe)
    image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only frame actor output')
    out.mkdir();index=-1
    try:
        sines,sine_proof=sine_table(image)
        profiles,prefix_count=cases(assets['CARO.CAR'][2:],sprites(assets['BOMOMIMK.SPR']),sines)
        output=bytearray(b'LZACTR01'+struct.pack('<I',len(profiles)))
        coverage=set();states=write_count=0;outcomes=[0]*5;kinds=[0]*4
        for index,(entry,sp,flags,patches) in enumerate(profiles):
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                initial[address:address+len(raw)]=raw
            values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
                0x1000,0x1aa2,0x40,0x7000,sp,entry,flags)
            trace,writes,endpoints=[],[],[]
            stop=None;kind=0
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Frame actor work crossed an interrupt or hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop,kind
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    row=tuple(uc.reg_read(register) for register in REGS)
                    if not (row[7]==0x1000 and row[12]<0x83f0 or row[7]==0x1920 and row[12]<0x1820 or
                            row[7]==0x18ac and 0x517<=row[12]<0x594):
                        raise ValueError('Frame actor work left declared original code: '+str((row[7],row[12],address,size)))
                    if row[7]==0x1000 and row[12]==0x7ee1:
                        kind=1
                    if row[7]==0x1000 and row[12]==0x7f59:
                        kind=1+int.from_bytes(uc.mem_read(DATA+0x2082,2),'little')
                    trace.append(row);coverage.add((row[7],row[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x70000<=address and address+size<=0x74010 or
                            0xa0000<=address and address+size<=0xb0001):
                        raise ValueError('Frame actor write left data/stack/VGA owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code)
                    engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(0x10000+entry,0 if observed else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS)
                final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Frame actor endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Frame actor observer changed complete memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Frame actor writes do not reconstruct complete final memory')
            trace.append(registers);outcome=STOPS[stop];outcomes[outcome]+=1;kinds[kind]+=1
            output.extend(struct.pack('<III13HI13HI',index,outcome,kind,*values,*registers))
            output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:
                output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(row[column] for row in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for write_row in writes:
                output.extend(struct.pack('<IBH',*write_row))
            states+=len(trace);write_count+=len(writes)
        if any(sha((root/name).read_bytes())!=digest for name,digest in pins.items()) or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()) or sha(library.read_bytes())!=LIB_SHA:
            raise ValueError('Frame actor producer changed during generation')
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-frame-actor-entry-v1',cases=len(profiles),continuous_prefix_cases=prefix_count,
            direct_actor_entry_cases=len(profiles)-prefix_count,asset_sha256=pins,source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            original_code_bytes_verified=43552,sine_initializer=sine_proof,register_states=states,ordered_writes=write_count,
            outcomes=outcomes,actor_kinds=kinds,executed_instructions=[list(row) for row in sorted(coverage)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,later_state_injected=False,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,actor_body_executed=False,production_app_comparison=False,
            trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True,trace_storage='register-columns-v1',
            raw_memory_published=False,active_prefix_executed=False,full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(profiles),states=states,writes=write_count,outcomes=outcomes,kinds=kinds,
            bytes=len(raw),compressed=len(compressed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error)))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
