"""Unchanged prefix/caller/actor execution through boss contact or tile-cache handoff."""
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
from ammo_hud_oracle import ASSET_SHA, sprites
from boss_links_oracle import sine_table
from frame_actor_entry_oracle import cases as entry_cases
from frame_camera_oracle import EXE_SHA, LIB_SHA, REGS, sha

DATA=0x1aa20
STOPS={0x165a2:0,0x173e5:1,0x1804e:2,0x177dc:3,0x11b14:4,0x192e2:5}


def contact_profiles():
    rows=[]
    def add(family,**changes):
        row=dict(family=family,kind=30,behavior=6,hotspot=0,x=64,y=80,dx=20,dy=20,
            dx2=-30,dy2=-30,states=(1,1),held=(0,0),velocity=(0,0),serials=(1,2,3),
            linkmode=255,output=(64,80),segment=0x5000,offset=0x1bd4,visual=2,
            floor=0x200,bp=0x3fdc,seed=0x12345678,width=3,height=2,owner=1,
            life=1,hp=255,tick=1,edges=0,edge_tile=1,flames=0,flame_shift=0,
            mass=1,bombs=2,bomb_match='both',prior_owner=7,group=4,
            triggers=3,cells=8,mapping='distinct',map_offset=0,
            sound_active=0,sound_priority=0)
        row.update(changes);rows.append(row)
    for value in range(256):
        add('width',width=value,height=1)
        add('height',width=1,height=value)
        add('sound_priority',sound_active=1,sound_priority=value,life=255)
    for flames,hp,life,mass in itertools.product((0,1,127,128,255,256),(0,1,127,255),(0,1,255),(1,2)):
        add('damage',width=16,height=32,flames=flames,hp=hp,life=life,mass=mass)
    for tick,dx,bottom,seed in itertools.product((0,1,28,29,30,58,65535),(-1,0,1),(False,True),range(8)):
        add('periodic',tick=tick,dx=dx,dx2=100,dy2=100,edges=2 if bottom else 0,seed=seed)
    for velocity,edges,tile in itertools.product(((-32768,-32768),(-1,-1),(0,0),(1,1),
            (32767,32767),(32767,-32768)),range(16),(1,76,77,82,83,255)):
        add('reflection',velocity=velocity,edges=edges,edge_tile=tile)
    for triggers,cells,owner,group in itertools.product(range(4),(0,1,8,256),(0,1,255,256),(0,4,30,255)):
        add('trigger_group',life=255,triggers=triggers,cells=cells,owner=owner,group=group,
            mapping=('distinct','chain','zero','duplicate')[triggers])
    for segment,offset,visual,map_offset in itertools.product((0x1aa2,0x5000),
            (0,0x1b88,0x1bae,0x1bd4,0xffe7,0xfff0,0xfff3,0xffff),(0,1,32,255),(0,0xfffe)):
        add('far_alias',segment=segment,offset=offset,visual=visual,map_offset=map_offset,
            life=255,flames=1)
    for bombs,match,mass,prior in itertools.product((0,1,2,200),('first','last','both','none'),(0,1,2,255),(0,7,65535)):
        add('attribution',bombs=bombs,bomb_match=match,mass=mass,prior_owner=prior,flames=1)
    for shift in (0,1):
        add('sample_columns',width=16,height=4,flames=16,flame_shift=shift)
    for flames in (1,2):
        add('maximum_box',width=255,height=255,flames=flames)
    for floor,bp in itertools.product((0x200,0x4000,0x3d72,0x3d73),(0x3fdc,0x40)):
        add('stack_probe',floor=floor,bp=bp,life=255)
    return rows


def contact_case(index,row):
    values,patches=direct_case(index,row)
    def put(address,raw):
        patches.append((address,raw))
    def data(offset,raw):
        put(DATA+offset,raw)
    def word(offset,value):
        data(offset,struct.pack('<H',value&65535))
    def actor_byte(offset,value):
        put(row['segment']*16+((row['offset']+offset)&65535),bytes((value&255,)))
    def actor_word(offset,value):
        for i,value in enumerate(struct.pack('<H',value&65535)):
            actor_byte(offset+i,value)

    # Physical records are seeded first; later explicit globals retain alias order.
    for slot in range(1,row['group']+1):
        raw=bytearray(38);raw[0]=31 if slot%4!=0 else 10
        raw[37]=(row['owner']+(1 if slot%4==3 else 0))&255
        raw[21]=6;raw[27]=3
        data(0x1bae+slot*38,raw)
    actor_byte(0,row['kind']);actor_byte(1,row['visual']);actor_byte(2,row['life'])
    actor_word(14,row['width']|(row['height']<<8));actor_word(18,row['owner'])
    actor_byte(20,row['hotspot']);actor_byte(21,row['behavior']);actor_byte(22,6)
    actor_byte(27,0);actor_byte(36,row['hp'])
    for offset,value in ((0xc1e0,row['map_offset']),(0xc1e2,0x4000),(0xc1fe,0x4000),
            (0xc204,64),(0x206e,0x6000),(0x78ba,row['cells']),(0x78c2,row['tick']),
            (0x2074,row['prior_owner']),(0x2076,row['bombs']),(0x78c0,0x2222)):
        word(offset,value)
    for offset,value in ((0x208d,row['group']),(0x79a7,row['triggers']),
            (0x79c4,row['sound_active']),(0x799e,row['sound_priority']),(0x799f,0)):
        data(offset,bytes((value,)))

    tiles=bytearray(65536)
    base=((row['y']&65535)>>3)*64+((row['x']&65535)>>3)
    def tile(cell,value):
        tiles[(row['map_offset']+cell)&65535]=value
    width,height=row['width'],row['height']
    for mask,start,step,count in ((1,base-64,1,width),(2,base+height*64,1,width),
            (4,base-1,64,height),(8,base+width,64,height)):
        if row['edges']&mask and count:
            tile(start+(count-1)*step,row['edge_tile'])
    flame_cells=[(base+y*64+x+row['flame_shift'])&65535
        for y in range(height) for x in range(0,width,2)][:row['flames']]
    for cell in flame_cells:
        tile(cell,117)
    last=flame_cells[-1] if flame_cells else 0xffff
    for slot in range(row['bombs']):
        match=row['bomb_match']=='both' or row['bomb_match']=='first' and slot==0 or row['bomb_match']=='last' and slot==row['bombs']-1
        word(0x209e+slot*11,last if match else last^0x5555)
    for owner in (row['prior_owner'],1,row['bombs']):
        data((owner+0x78d5)&65535,bytes((row['mass'],)))

    for bank in range(1,row['triggers']+1):
        mappings={'distinct':(11,12,13,14),'chain':(2,3,4,5),
            'zero':(11,12,13,14),'duplicate':(2,2,2,2)}
        sources=(0,2,3,4) if row['mapping']=='zero' else (1,2,3,4)
        if row['mapping']=='duplicate':
            sources=(1,1,2,2)
        replacements=mappings[row['mapping']]
        if row['mapping']=='distinct' and bank==2:
            replacements=(31,32,33,34)
        key=1000 if bank<=2 else 999
        data(0x77c0+bank*14,struct.pack('<3H8B',100,200,key,*sources,*replacements))
    word_plane=bytearray((row['cells']+1)*2)
    for cell in range(1,row['cells']+1):
        value=(99,100,200,201,0x8064,0x80c8,199,200)[(cell-1)%8]
        struct.pack_into('<H',word_plane,cell*2,value)
        tiles[cell]=(cell-1)%4+1
    put(0x40000,tiles);put(0x60000,word_plane)
    return values,patches


def generate(root,out):
    if unicorn.__version__!='2.1.4' or any(k in os.environ for k in ('LD_PRELOAD','LIBUNICORN_PATH')):
        raise ValueError('Unsupported actor contact oracle profile')
    library=Path(uclib._name).resolve(strict=True)
    if sha(library.read_bytes())!=LIB_SHA or not any(line.endswith(str(library))
            for line in Path('/proc/self/maps').read_text().splitlines()):
        raise ValueError('Actual contact oracle mapping differs')
    names=('actor_contact_oracle.py','actor_precontact_oracle.py','frame_actor_entry_oracle.py',
        'boss_links_oracle.py','frame_camera_oracle.py','frame_spawner_oracle.py',
        'frame_waiting_oracle.py','ammo_hud_oracle.py')
    sources={name:sha((root/'tools'/name).read_bytes()) for name in names}
    pins=dict(ASSET_SHA,**{'LEZAC.EXE':EXE_SHA});assets={name:(root/name).read_bytes() for name in pins}
    if any(sha(assets[name])!=digest for name,digest in pins.items()):
        raise ValueError('Canonical contact asset differs')
    exe=assets['LEZAC.EXE'];mz=struct.unpack_from('<14H',exe);image=bytearray(exe[mz[4]*16:])
    for i in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+i*4);at=segment*16+offset
        struct.pack_into('<H',image,at,(struct.unpack_from('<H',image,at)[0]+0x1000)&65535)
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only contact output')
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
        output=bytearray(b'LZCONT01'+struct.pack('<I',len(cases)))
        coverage=set();states=write_count=0;outcomes=[0]*6;domains=[0]*4
        for index,(domain,values,patches) in enumerate(cases):
            initial=bytearray(1048576);initial[0x10000:0x10000+len(image)]=image
            for address,raw in patches:
                if not 0<=address<=address+len(raw)<=1048576:
                    raise ValueError('Contact initial patch exceeds real-mode memory')
                initial[address:address+len(raw)]=raw
            actor_bytes=set()
            if domain>=2:
                offset=struct.unpack_from('<H',initial,0x70000+((values[11]+2)&65535))[0]
                segment=struct.unpack_from('<H',initial,0x70000+((values[11]+4)&65535))[0]
                actor_bytes={segment*16+((offset+i)&65535) for i in (0,2,20,21,*range(22,29),36)}
            trace,writes,endpoints=[],[],[];stop=None
            for observed in (True,False):
                engine=unicorn.Uc(unicorn.UC_ARCH_X86,unicorn.UC_MODE_16)
                engine.mem_map(0,1048576);engine.mem_write(0,bytes(initial))
                for register,value in zip(REGS,values):
                    engine.reg_write(register,value)
                def external(*unused):
                    raise ValueError('Contact crossed an interrupt or hardware I/O')
                def code(uc,address,size,user):
                    nonlocal stop
                    if address in STOPS:
                        stop=address;uc.emu_stop();return
                    row=tuple(uc.reg_read(register) for register in REGS)
                    if not (row[7]==0x1000 and row[12]<0x83f0 or row[7]==0x1920 and row[12]<0x1820 or
                            row[7]==0x18ac and 0x517<=row[12]<0x594):
                        raise ValueError('Contact left declared original code: '+str((row[7],row[12],address,size)))
                    trace.append(row);coverage.add((row[7],row[12]))
                def write(uc,access,address,size,value,user):
                    if size not in (1,2) or not (DATA<=address and address+size<=DATA+65536 or
                            0x70000<=address and address+size<=0x80001 or
                            0xa0000<=address and address+size<=0xb0001 or
                            domain==3 and 0x40000<=address and address+size<=0x50000 or
                            size==1 and address in actor_bytes):
                        raise ValueError('Contact write left declared owners: '+str((address,size)))
                    writes.append((address,size,value&((1<<(size*8))-1)))
                engine.hook_add(unicorn.UC_HOOK_INTR,external)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_IN)
                engine.hook_add(unicorn.UC_HOOK_INSN,external,None,1,0,UC_X86_INS_OUT)
                if observed:
                    engine.hook_add(unicorn.UC_HOOK_CODE,code);engine.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
                engine.emu_start(values[7]*16+values[12],0 if observed else stop,count=3000000)
                registers=tuple(engine.reg_read(register) for register in REGS);final=bytes(engine.mem_read(0,1048576))
                if stop not in STOPS or registers[7]*16+registers[12]!=stop or final[0x10000:DATA]!=image[:0xaa20]:
                    raise ValueError('Contact endpoint or unchanged code differs')
                endpoints.append((registers,final))
            if endpoints[0]!=endpoints[1]:
                raise ValueError('Contact observer changed complete memory/registers')
            registers,final=endpoints[0];reconstructed=bytearray(initial)
            for address,size,value in writes:
                reconstructed[address:address+size]=value.to_bytes(size,'little')
            if reconstructed!=final:
                raise ValueError('Contact writes do not reconstruct complete final memory')
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
            if len(output)>1024*1024*1024:
                raise ValueError('Contact projection exceeds declared RAM reserve')
            if index%512==0:
                print(json.dumps(dict(status='running',case=index,cases=len(cases),states=states)),flush=True)
        if any(sha((root/name).read_bytes())!=digest for name,digest in pins.items()) or any(
                sha((root/'tools'/name).read_bytes())!=digest for name,digest in sources.items()) or sha(library.read_bytes())!=LIB_SHA:
            raise ValueError('Contact producer changed during generation')
        raw=bytes(output);compressed=gzip.compress(raw,mtime=0)
        (out/'oracle.bin.gz').write_bytes(compressed)
        manifest=dict(schema='lezac-controlled-actor-contact-v1',cases=len(cases),domains=domains,
            foundation_cases=foundation_count,target_profile_families=dict(Counter(row['family'] for row in profiles)),
            continuous_prefix_cases=prefix_count,asset_sha256=pins,source_sha256=sources,
            unicorn_version=unicorn.__version__,unicorn_library_sha256=LIB_SHA,actual_library_mapping_verified=True,
            original_code_bytes_verified=43552,sine_initializer=sine_proof,register_states=states,ordered_writes=write_count,
            outcomes=outcomes,executed_instructions=[list(row) for row in sorted(coverage)],
            projection_bytes=len(raw),projection_sha256=sha(raw),compressed_bytes=len(compressed),compressed_sha256=sha(compressed),
            complete_memory_observer_control=True,ordered_writes_reconstruct_memory=True,later_state_injected=False,
            instruction_patches=0,calls_stubbed=0,interrupts_delivered=0,hardware_io=0,
            controlled_initial_memory=True,natural_capture=False,actor_contact_executed=True,
            tile_behavior_after_65a2_executed=False,motion_integration_73e5_executed=False,
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
