"""Execute original behavior-5 expiry and complete physical/visual compaction."""
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
STOPS={0x173e5:0,0x17ee4:1,0x192e2:2}
SOURCES=('actor_expiry_oracle.py','actor_contact_oracle.py','actor_precontact_oracle.py',
    'frame_actor_entry_oracle.py','boss_links_oracle.py','frame_camera_oracle.py',
    'frame_spawner_oracle.py','frame_waiting_oracle.py','ammo_hud_oracle.py')


def profiles():
    rows=[]
    def add(family,**changes):
        row=dict(family=family,kind=10,life=0,tick=0,physical=4,index=1,graphics=8,
            visual=2,references=4,reference_byte=None,pointer=0xc21e,bp=0x3fdc,
            floor=0x200,flags=0x202,continuous=False,physical_actor=False,caller=False)
        row.update(changes);rows.append(row)
    for life,tick in itertools.product(range(256),(0,1)):
        add('life_byte',life=life,tick=tick)
    for tick,life in itertools.product((0,1,2,3,255,256,257,32767,32768,65535),(0,1,2)):
        add('tick_word',tick=tick,life=life)
    for value in range(256):
        add('kind_byte',kind=value)
        add('physical_count',physical=value)
        add('index_byte',index=value)
        add('graphics_count',physical=1,graphics=value)
        add('visual_byte',visual=value)
        add('reference_count',physical=1,references=value)
    for visual,value in itertools.product((0,1,127,255),range(256)):
        add('reference_bytes',visual=visual,reference_byte=value)
    for physical,index in itertools.product((0,1,4),(-2,-1,256,32767)):
        add('signed_index',physical=physical,index=index)
    for pointer,flags,index,kind in itertools.product((0,0xc21e,0xfff0),(0x202,0x602),(0,1,4),(1,10)):
        add('visual_alias_direction',pointer=pointer,flags=flags,index=index,kind=kind)
    for bp,floor in itertools.product((0x3fdc,0x700),(0x200,0x3d72,0x3d73,0x3d7e,0x3d7f,0x4000)):
        add('stack_probe',bp=bp,floor=floor)
    for kind,life,tick in itertools.product((1,10,13),(0,1,2,255),(0,1)):
        add('continuous_actor',kind=kind,life=life,tick=tick,continuous=True)
    for kind,life,tick,index in itertools.product((1,10,13),(0,1,2,255),(0,1),(1,4)):
        add('physical_actor_alias',kind=kind,life=life,tick=tick,index=index,
            continuous=True,physical_actor=True)
    for kind,life,tick in itertools.product((1,10,13),(0,1,2,255),(0,1)):
        add('live_caller',kind=kind,life=life,tick=tick,references=0,
            continuous=True,physical_actor=True,caller=True)
    return rows


def make_case(index,row):
    patches=[];bp=row['bp'];actor_offset=0x1bd4;actor_segment=0x5000
    if row['continuous']:
        parent=dict(contact_profiles()[0],kind=row['kind'],behavior=5,life=row['life'],
            tick=row['tick'],width=1,height=1,bombs=0,triggers=0,cells=0,group=4,flames=0,velocity=(0,0))
        values,patches=contact_case(index,parent)
        # These parent banks are zero outside the executable image and have no
        # preceding writes; omitting their all-zero seeds preserves every byte.
        patches=[(address,raw) for address,raw in patches if not
            (address in (0x40000,0x60000) and not any(raw))]
    else:
        values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,bp,
            0x1000,0x1aa2,0x40,0x7000,(bp-58)&65535,0x65a8,row['flags'])
    def put(address,raw):
        patches.append((address,raw))
    def word(offset,value):
        put(DATA+offset,struct.pack('<H',value&65535))
    actor=None
    if row['physical_actor']:
        initial=bytearray(1048576)
        for address,raw in patches:
            initial[address:address+len(raw)]=raw
        actor=bytes(initial[actor_segment*16+actor_offset:actor_segment*16+actor_offset+38])
    physical=bytearray((i*29+index*7+11)&255 for i in range(256*38))
    for slot in range(256):
        physical[slot*38+1]=(slot*17+3)&255
    if 0<=row['index']<256:
        physical[row['index']*38+1]=row['visual']
    put(DATA+0x1bae,physical)
    visual=bytes((i*19+index*13+7)&255 for i in range(256*8))
    first=min(len(visual),65536-row['pointer'])
    put(DATA+row['pointer'],visual[:first])
    if first<len(visual):
        put(DATA,visual[first:])
    references=bytearray((i*13+index*11+5)&255 for i in range(256*16))
    for slot in range(256):
        references[slot*16]=(slot*17)&255 if row['reference_byte'] is None else row['reference_byte']
        references[slot*16+1]=(255-slot*7)&255 if row['reference_byte'] is None else row['reference_byte']
    put(DATA+0x79ea,references)
    for offset,value in ((0x1afa,row['floor']),(0x2082,row['index']),
            (0x78c2,row['tick']),(0xc1fc,row['pointer'])):
        word(offset,value)
    for offset,value in ((0x208d,row['physical']),(0x208e,0),(0xc496,row['graphics']),(0x79f9,row['references'])):
        put(DATA+offset,bytes((value,)))
    put(actor_segment*16+actor_offset,bytes((row['kind'],row['visual'],row['life'])))
    if actor is not None:
        actor_segment=0x1aa2;actor_offset=(0x1bae+row['index']*38)&65535
        put(DATA+actor_offset,actor)
        put(DATA+actor_offset,bytes((row['kind'],row['visual'],row['life'])))
        put(0x70000+((bp+4)&65535),struct.pack('<HH',actor_offset,actor_segment))
    if row['caller']:
        values=(*values[:11],0x3fe4,0x7ebb,values[13])
    if row['continuous']:
        if not row['caller']:
            put(0x70000+values[11],struct.pack('<H',0x7ee4))
    else:
        for offset,value in ((0,0x3ffe),(2,0x7ee4),(4,actor_offset),(6,actor_segment)):
            put(0x70000+((bp+offset)&65535),struct.pack('<H',value))
        put(0x70000+((bp-15)&65535),bytes((row['kind'],)))
        put(0x70000+((bp-49)&65535),bytes((5,)))
    return values,patches


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported expiry oracle profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual expiry oracle mapping differs')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in SOURCES}
    exe=(root/'LEZAC.EXE').read_bytes()
    if sha(exe)!=EXE_SHA:
        raise ValueError('Canonical expiry executable differs')
    mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only expiry output')
    out.mkdir();index=-1
    try:
        rows=profiles();output=bytearray(b'LZEXPI01'+struct.pack('<I',len(rows)))
        coverage=set();states=write_count=0;outcomes=[0]*3;domains=[0]*2
        for index,row in enumerate(rows):
            values,patches=make_case(index,row);domain=int(row['continuous'])
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                if not 0<=address<=address+len(raw)<=1048576:
                    raise ValueError('Expiry seed exceeds memory')
                initial[address:address+len(raw)]=raw
            trace,writes,endpoints=[],[],[];stop=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Expiry crossed an interrupt or hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    registers=tuple(uc.reg_read(register) for register in REGS)
                    if not (registers[7]==0x1000 and registers[12]<0x83f0 or
                            registers[7]==0x1920 and registers[12]<0x1820 or
                            registers[7]==0x18ac and 0x517<=registers[12]<0x5dc):
                        raise ValueError('Expiry left declared code: '+str((registers[7],registers[12],address,size)))
                    trace.append(registers);coverage.add((registers[7],registers[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x70000<=address and address+size<=0x80001 or
                            domain==1 and 0xa0000<=address and address+size<=0xb0001 or
                            0x50000<=address and address+size<=0x60000):
                        raise ValueError('Expiry write left declared owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(values[7]*16+values[12],0 if observed else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Expiry endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Expiry observer changed complete memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Expiry writes do not reconstruct final memory')
            trace.append(registers);outcome=STOPS[stop];outcomes[outcome]+=1;domains[domain]+=1
            output.extend(struct.pack('<III13HI13HI',index,outcome,domain,*values,*registers))
            output.extend(struct.pack('<I',len(patches)))
            for address,raw in patches:
                output.extend(struct.pack('<II',address,len(raw))+raw)
            output.extend(struct.pack('<I',len(trace)))
            for column in range(14):
                output.extend(struct.pack('<'+('I' if column==13 else 'H')*len(trace),*(r[column] for r in trace)))
            output.extend(struct.pack('<I',len(writes)))
            for entry in writes:
                output.extend(struct.pack('<IBH',*entry))
            states+=len(trace);write_count+=len(writes)
            if len(output)>192*1024*1024:
                raise ValueError('Expiry projection exceeds RAM reserve')
            if index%256==0:
                print(json.dumps(dict(status='running',case=index,cases=len(rows),states=states,bytes=len(output))),flush=True)
        if sha((root/'LEZAC.EXE').read_bytes())!=EXE_SHA or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()) or sha(library.read_bytes())!=LIB_SHA:
            raise ValueError('Expiry producer changed during generation')
        raw=bytes(output);packed=gzip.compress(raw,mtime=0);(out/'oracle.bin.gz').write_bytes(packed)
        manifest=dict(schema='lezac-controlled-actor-expiry-v1',cases=len(rows),domains=domains,
            profile_families=dict(Counter(r['family'] for r in rows)),asset_sha256={'LEZAC.EXE':EXE_SHA},source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            original_code_bytes_verified=43552,register_states=states,ordered_writes=write_count,outcomes=outcomes,
            executed_instructions=[list(r) for r in sorted(coverage)],projection_bytes=len(raw),projection_sha256=sha(raw),
            compressed_bytes=len(packed),compressed_sha256=sha(packed),complete_memory_observer_control=True,
            ordered_writes_reconstruct_memory=True,later_state_injected=False,instruction_patches=0,calls_stubbed=0,
            interrupts_delivered=0,hardware_io=0,controlled_initial_memory=True,natural_capture=False,
            continuous_actor_cases=domains[1],physical_actor_alias_cases=sum(r['physical_actor'] for r in rows),
            real_caller_cases=sum(r['caller'] for r in rows),physical_compaction_executed=True,visual_compaction_executed=True,
            motion_after_73e5_executed=False,actor_near_return_executed=True,production_app_comparison=False,
            trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True,trace_storage='register-columns-v1',
            raw_memory_published=False,full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(rows),states=states,writes=write_count,outcomes=outcomes,
            domains=domains,bytes=len(raw),compressed=len(packed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'producer-at-failure.py').write_bytes(Path(__file__).read_bytes())
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error),sources=sources))+'\n')
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
