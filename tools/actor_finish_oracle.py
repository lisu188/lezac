"""Unchanged actor execution through the common tail and real near return."""
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

from actor_precontact_oracle import direct_case, direct_profiles
from actor_contact_oracle import contact_case, contact_profiles
from ammo_hud_oracle import ASSET_SHA, sprites
from boss_links_oracle import sine_table
from frame_actor_entry_oracle import cases as entry_cases
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
STOPS={0x165a2:0,0x17ee4:1,0x17f5c:1,0x1804e:2,0x177dc:3,0x11b14:4,0x192e2:5}


def finish_profiles():
    rows=[]
    base=contact_profiles()[0]
    def add(family,**changes):
        row=dict(base,width=1,height=1,life=2,bombs=0,triggers=0,cells=0,group=0,
            fraction=(0,0),burst=0,packets=0,packet_match=False,pickup_threshold=255,graphics=2)
        row.update(changes);row["family"]=family;rows.append(row)
    for kind in range(256):
        add("kind_byte",kind=kind)
    for velocity,fraction in itertools.product(((-32768,-32768),(-257,-1),(-256,256),(-1,1),
            (0,0),(1,-1),(255,257),(32767,32767)),((0,0),(1,255),(255,1),(128,128))):
        add("fractional_motion",velocity=velocity,fraction=fraction)
    for kind,life,tick in itertools.product((12,13,18,19,29),(0,1,2,255),(0,1)):
        add("expiry_parity",kind=kind,life=life,tick=tick)
    for burst,bombs in itertools.product((0,1,2,3,4,5,255),(0,197,198,199)):
        add("burst_capacity",kind=13,life=1,burst=burst,bombs=bombs)
    for packets,match in itertools.product((0,1,2,3,255),(False,True)):
        add("owner_packets",kind=13,life=1,burst=4,packets=packets,packet_match=match,bombs=198)
    for kind,group,graphics in itertools.product((12,13,18),(0,29,30,255),(0,32,33,255)):
        add("debris_capacity",kind=kind,life=1,group=group,graphics=graphics,bombs=198)
    for seed,threshold in itertools.product(range(32),(0,50,100,255)):
        add("pickup_choice",kind=12,life=1,seed=seed,pickup_threshold=threshold,group=30)
    for kind,hp,flames,solid in itertools.product((1,8),(0,1,255),(0,1),(False,True)):
        add("ordinary_damage",kind=kind,hp=hp,flames=flames,solid=solid,
            velocity=(1 if hp==255 else -1,0))
    return rows


def finish_case(index,row):
    seed=dict(row,flames=0) if row["family"]=="ordinary_damage" else row
    values,patches=contact_case(index,seed)
    def data(offset,raw):
        patches.append((DATA+offset,raw))
    def actor_word(offset,value):
        raw=struct.pack("<H",value&65535)
        patches.append((row["segment"]*16+((row["offset"]+offset)&65535),raw))
    actor_word(10,row["fraction"][0]);actor_word(12,row["fraction"][1])
    data(0x31+((row["kind"]-12)&255),bytes((row["burst"],)))
    data(0x52,bytes((row["pickup_threshold"],)))
    data(0x53,bytes((10,20,30,40,50,60,70,80,90,100,255)))
    data(0x79cb,bytes((row["packets"],)))
    data(0x79cd,bytes((0 if row["packet_match"] else 1,))*256)
    # The key range deliberately also seeds the overlapping packet output buffers.
    data(0x1ab6,b"ABC");data(0x1aba,b"xyz")
    data(0xc496,bytes((row["graphics"],)))
    if row["family"]=="ordinary_damage":
        cell=((row["y"]>>3)*64+(row["x"]>>3)+65)&65535
        for offset,value in ((0,117 if row["flames"] else 1 if row["solid"] else 0),
                (1,76 if row["solid"] else 0),(65,117 if row["flames"] else 0),(64,0)):
            patches.append((0x40000+((cell+offset)&65535),bytes((value,))))
    return values,patches


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported actor finish oracle profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual finish oracle mapping differs')
    names=('actor_finish_oracle.py','actor_contact_oracle.py','actor_precontact_oracle.py','frame_actor_entry_oracle.py',
        'boss_links_oracle.py','frame_camera_oracle.py','frame_spawner_oracle.py',
        'frame_waiting_oracle.py','ammo_hud_oracle.py')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in names}
    pins=dict(ASSET_SHA,**{'LEZAC.EXE':EXE_SHA});assets={name:(root/name).read_bytes() for name in pins}
    if any(sha(assets[name])!=digest for name,digest in pins.items()):
        raise ValueError('Canonical finish asset differs')
    exe=assets['LEZAC.EXE'];mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only finish output')
    out.mkdir();index=-1
    try:
        sines,sine_proof=sine_table(image)
        entries,prefix_count=entry_cases(assets['CARO.CAR'][2:],sprites(assets['BOMOMIMK.SPR']),sines)
        cases=[]
        for entry,sp,flags,patches in entries:
            values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
                0x1000,0x1aa2,0x40,0x7000,sp,entry,flags)
            cases.append((0 if entry==0x7a57 else 1,values,patches))
        for row in direct_profiles():
            values,patches=direct_case(len(cases),row);cases.append((2,values,patches))
        foundation_count=len(cases);profiles=contact_profiles()
        for row in profiles:
            values,patches=contact_case(len(cases),row);cases.append((3,values,patches))
        contact_count=len(cases);finish_rows=finish_profiles()
        for row in finish_rows:
            values,patches=finish_case(len(cases),row);cases.append((4,values,patches))
        for domain,values,patches in cases:
            if domain>=2:
                patches.append((0x70000+values[11],struct.pack('<H',0x7ee4)))
        output=bytearray(b'LZFINI01'+struct.pack('<I',len(cases)))
        coverage=set();states=write_count=0;outcomes=[0]*6;domains=[0]*5
        for index,(domain,values,patches) in enumerate(cases):
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                if not 0<=address<=address+len(raw)<=1048576:
                    raise ValueError('Finish initial patch exceeds real-mode memory')
                initial[address:address+len(raw)]=raw
            actor_bytes=set()
            if domain>=2:
                offset=struct.unpack_from('<H',initial,0x70000+((values[11]+2)&65535))[0]
                segment=struct.unpack_from('<H',initial,0x70000+((values[11]+4)&65535))[0]
                actor_bytes={segment*16+((offset+i)&65535) for i in range(38)}
            trace,writes,endpoints=[],[],[];stop=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Finish crossed an interrupt or hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    row=tuple(uc.reg_read(register) for register in REGS)
                    if not (row[7]==0x1000 and row[12]<0x83f0 or row[7]==0x1920 and row[12]<0x1820 or
                            row[7]==0x18ac and 0x517<=row[12]<0x594):
                        raise ValueError('Finish left declared original code: '+str((row[7],row[12],address,size)))
                    trace.append(row);coverage.add((row[7],row[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x70000<=address and address+size<=0x80001 or
                            0xa0000<=address and address+size<=0xb0001 or
                            domain>=3 and 0x40000<=address and address+size<=0x50000 or
                            address in actor_bytes):
                        raise ValueError('Finish write left declared owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(values[7]*16+values[12],0 if observed else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Finish endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Finish observer changed complete memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Finish writes do not reconstruct complete final memory')
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
            if len(output)>2*1024*1024*1024:
                raise ValueError('Finish projection exceeds declared RAM reserve')
            if index%512==0:
                print(json.dumps(dict(status='running',case=index,cases=len(cases),states=states)),flush=True)
        if any(sha((root/name).read_bytes())!=digest for name,digest in pins.items()) or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()) or sha(library.read_bytes())!=LIB_SHA:
            raise ValueError('Finish producer changed during generation')
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-actor-finish-v1',cases=len(cases),domains=domains,
            foundation_cases=foundation_count,contact_cases=contact_count,
            target_profile_families=dict(Counter(row['family'] for row in finish_rows)),
            continuous_prefix_cases=prefix_count,asset_sha256=pins,source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            original_code_bytes_verified=43552,sine_initializer=sine_proof,register_states=states,ordered_writes=write_count,
            outcomes=outcomes,executed_instructions=[list(row) for row in sorted(coverage)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,later_state_injected=False,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,actor_contact_executed=True,
            tile_behavior_after_65a2_executed=False,motion_integration_73e5_executed=True,actor_near_return_executed=True,
            production_app_comparison=False,trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True,
            trace_storage='register-columns-v1',raw_memory_published=False,active_prefix_executed=False,
            full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),states=states,writes=write_count,outcomes=outcomes,
            domains=domains,bytes=len(raw),compressed=len(compressed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error),sources=sources))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
