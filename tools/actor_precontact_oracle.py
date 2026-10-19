"""Unchanged prefix/caller/prologue through actor precontact, without stage injection."""
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
from frame_actor_entry_oracle import cases as entry_cases
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
STOPS={0x1654e:0,0x1804e:1,0x177dc:2,0x11b14:3,0x192e2:4}


def direct_profiles():
    rows=[]
    def add(**changes):
        row=dict(kind=0,behavior=2,hotspot=0,x=100,y=100,dx=20,dy=20,
            dx2=-30,dy2=-30,states=(1,1),held=(0,0),velocity=(0,0),serials=(1,2,3),
            linkmode=255,output=(100,100),segment=0x5000,offset=0x1bd4,
            visual=2,floor=0x200,bp=0x3fdc,seed=0x12345678)
        row.update(changes);rows.append(row)
    for value in range(256):
        add(behavior=value)
        add(hotspot=value)
        add(kind=value,dx=0,dy=0,dx2=0,dy2=0)
        add(kind=19,dx=0,dy=0,dx2=0,dy2=0,seed=(value*0x01010101)&0xffffffff)
        add(kind=31,serials=(value,129,255),linkmode=value,velocity=(value*257,65535-value*257))
    deltas=(-32768,-32767,-10,-9,0,9,10,32767)
    for dx,dy,kind in itertools.product(deltas,deltas,(1,8,19,29,30,31,255)):
        add(kind=kind,dx=dx,dy=dy,dx2=dy,dy2=dx,linkmode=3)
    for states,held,kind in itertools.product(itertools.product((0,1,2),repeat=2),
            ((0,0),(0,1),(1,0),(255,255)),(1,19,29,31)):
        add(kind=kind,states=states,held=held,dx=0,dy=0,dx2=0,dy2=0)
    for serials,mode,velocity in itertools.product(((0,2,3),(1,0,3),(1,2,0),(128,129,255),(129,128,1)),
            (0,1,3,127,128,254,255),((-32768,32767),(-2,2),(0,0),(32767,-32768))):
        add(kind=31,serials=serials,linkmode=mode,velocity=velocity,output=(32767,-32768))
    for segment,offset,visual in itertools.product((0x1aa2,0x5000),
            (0,0x1b88,0x1bae,0x1bd4,0xffe7,0xfff0,0xfff3,0xffff),(0,1,31,32,127,255)):
        add(segment=segment,offset=offset,visual=visual,kind=19,dx=0,dy=0,dx2=0,dy2=0)
    for floor,bp,kind in itertools.product((0x200,0x4000,0x3d72,0x3d73),(0x3fdc,0x40),(19,31)):
        add(floor=floor,bp=bp,kind=kind,dx=0,dy=0,dx2=0,dy2=0,linkmode=3)
    return rows


def direct_case(index,row):
    patches=[]
    def put(address,raw):
        patches.append((address,raw))
    def data(offset,raw):
        put(DATA+offset,raw)
    def word(offset,value):
        data(offset,struct.pack('<H',value&65535))
    bp=row['bp'];sp=(bp+2)&65535
    for i in range(-160,18):
        put(0x70000+((bp+i)&65535),bytes(((index*7+i*29+11)&255,)))
    word(0x1afa,row['floor']);data(0x1afe,struct.pack('<I',row['seed']))
    data(0x1b78,bytes((index*7+i*13)&255 for i in range(15)))
    data(0x62,bytes((index*19+i*29)&255 for i in range(8)))
    data(0x79ae,bytes(row['held']));data(0x79e6,bytes(row['states'])+bytes((index&255,(index+1)&255)))
    data(0x1b89,bytes((0,)));data(0x1baf,bytes((1,)))
    table=bytearray()
    for sprite in range(256):
        table.extend(struct.pack('<BBH',(sprite*7+index)&255,(sprite*13+index)&255,(sprite*197+index*23)&65535))
    data(0xc322,table)
    for number in range(13):
        data(0x42+number*2,bytes(((index+number*17)&255,)))
    for number in range(129):
        raw=bytearray((index*7+number*11+i*13)&255 for i in range(16))
        raw[3]=row['linkmode'];struct.pack_into('<2H',raw,11,*[v&65535 for v in row['output']])
        data(0x79ea+number*16,raw)
    for visual,x,y in ((0,row['x']+row['dx'],row['y']+row['dy']),
            (1,row['x']+row['dx2'],row['y']+row['dy2']),
            (row['visual'],row['x'],row['y']+row['hotspot']-(256 if row['hotspot']>=128 else 0))):
        data(0xc21e+visual*8,struct.pack('<4H',x&65535,y&65535,0xa55a,0x5aa5))
    actor=bytearray((index*7+i*11+19)&255 for i in range(38))
    actor[0]=row['kind'];actor[1]=row['visual'];actor[20]=row['hotspot'];actor[21]=row['behavior']
    actor[14:17]=bytes(row['serials']);actor[22]=6
    struct.pack_into('<2H',actor,6,*[v&65535 for v in row['velocity']])
    for i,value in enumerate(actor):
        put(row['segment']*16+((row['offset']+i)&65535),bytes((value,)))
    for offset,value in ((4,row['offset']),(6,row['segment'])):
        put(0x70000+((bp+offset)&65535),struct.pack('<H',value))
    put(0x70000+((bp-19)&65535),bytes((row['visual'],)))
    values=(0xa55a,0x1234,0x5678,0xabcd,0x1357,0x2468,0x3ffe,
        0x1000,0x1aa2,0x40,0x7000,sp,0x6053,0x602 if index%2 else 0x202)
    return values,patches


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported actor precontact oracle profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual precontact oracle mapping differs')
    names=('actor_precontact_oracle.py','frame_actor_entry_oracle.py','boss_links_oracle.py',
        'frame_camera_oracle.py','frame_spawner_oracle.py','frame_waiting_oracle.py','ammo_hud_oracle.py')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in names}
    pins=dict(ASSET_SHA,**{'LEZAC.EXE':EXE_SHA});assets={name:(root/name).read_bytes() for name in pins}
    if any(sha(assets[name])!=digest for name,digest in pins.items()):
        raise ValueError('Canonical precontact asset differs')
    exe=assets['LEZAC.EXE'];mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only precontact output')
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
        output=bytearray(b'LZPREP01'+struct.pack('<I',len(cases)))
        coverage=set();states=write_count=0;outcomes=[0]*5;domains=[0]*3
        for index,(domain,values,patches) in enumerate(cases):
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                initial[address:address+len(raw)]=raw
            trace,writes,endpoints=[],[],[];stop=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Precontact crossed an interrupt or hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    row=tuple(uc.reg_read(register) for register in REGS)
                    if not (row[7]==0x1000 and row[12]<0x83f0 or row[7]==0x1920 and row[12]<0x1820 or
                            row[7]==0x18ac and 0x517<=row[12]<0x594):
                        raise ValueError('Precontact left declared original code: '+str((row[7],row[12],address,size)))
                    trace.append(row);coverage.add((row[7],row[12]))
                def write(uc,access,address,size,value,user):
                    actor_owned=False
                    if domain==2:
                        actor_offset=int.from_bytes(initial[0x70000+((values[11]+2)&65535):0x70000+((values[11]+2)&65535)+2],'little')
                        actor_segment=int.from_bytes(initial[0x70000+((values[11]+4)&65535):0x70000+((values[11]+4)&65535)+2],'little')
                        actor_owned=address in {actor_segment*16+((actor_offset+i)&65535) for i in (0,2,20,21,*range(22,29))} and size==1
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x70000<=address and address+size<=0x80001 or
                            0xa0000<=address and address+size<=0xb0001 or actor_owned):
                        raise ValueError('Precontact write left data/stack/VGA/far-actor owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(values[7]*16+values[12],0 if observed else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Precontact endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Precontact observer changed complete memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Precontact writes do not reconstruct complete final memory')
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
        if any(sha((root/name).read_bytes())!=digest for name,digest in pins.items()) or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()) or sha(library.read_bytes())!=LIB_SHA:
            raise ValueError('Precontact producer changed during generation')
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-actor-precontact-v1',cases=len(cases),domains=domains,
            continuous_prefix_cases=prefix_count,asset_sha256=pins,source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            original_code_bytes_verified=43552,sine_initializer=sine_proof,register_states=states,ordered_writes=write_count,
            outcomes=outcomes,executed_instructions=[list(row) for row in sorted(coverage)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,later_state_injected=False,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,actor_precontact_executed=True,
            behavior_after_654e_executed=False,production_app_comparison=False,
            trace_arithmetic_flags_compared=False,endpoint_all_flags_compared=True,trace_storage='register-columns-v1',
            raw_memory_published=False,active_prefix_executed=False,full_frame_claim=False,whole_game_parity=False)
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps(dict(status='passed',cases=len(cases),states=states,writes=write_count,outcomes=outcomes,
            domains=domains,bytes=len(raw),compressed=len(compressed),sha256=sha(raw))),flush=True)
    except BaseException as error:
        (out/'failed.json').write_text(json.dumps(dict(status='failed',case=index,error=repr(error)))+'\n');raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',required=True,type=Path);parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args();generate(args.repo.resolve(),args.out)
