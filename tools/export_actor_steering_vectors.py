"""Extract typed vector inputs/outputs from the authenticated original capture."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import check_actor_steering_fixture as original

ROOT=Path(__file__).resolve().parents[1]
VECTORS_SHA='ee4722d4876bfd19dcb9aa7f314a24c6ae5d1f500c39dd8d3f907ecaa2c9236c'
MAGIC=b'LZSTV001'


def require(value,message):
    if not value:
        raise ValueError(message)


def derive(raw):
    at=0
    def take(size):
        nonlocal at
        require(size>=0 and at+size<=len(raw),'Truncated original steering projection')
        value=raw[at:at+size];at+=size;return value
    def number(size):
        return int.from_bytes(take(size),'little')
    def registers():
        return struct.unpack('<13HI',take(30))
    require(take(8)==b'LZSTEER1' and number(4)==3736,'Original steering domain differs')
    rows=[];domains=[0,0,0];outcomes=[0,0];excluded=dict(square_root=0,runtime_error=0,alias=0)
    for index in range(3736):
        require(number(4)==index,'Original steering case index differs')
        outcome,domain=number(4),number(4)
        require(outcome<2 and domain<3,'Original steering outcome/domain differs')
        outcomes[outcome]+=1;domains[domain]+=1;entry,endpoint=registers(),registers()
        memory={};seeds=number(4);require(seeds<64,'Original steering seed reserve differs')
        for unused in range(seeds):
            address,size=number(4),number(4)
            require(size<=65536 and address+size<=1048576,'Original steering seed exceeds memory')
            memory.update((address+i,value) for i,value in enumerate(take(size)))
        states=number(4);require(1<states<3000000,'Original steering trace reserve differs')
        for row in range(states):
            require(at+2<=len(raw),'Truncated original steering delta')
            mask=struct.unpack_from('<H',raw,at)[0];at+=2
            require(mask<0x4000 and (row!=0 or mask==0x3fff),'Original steering delta mask differs')
            size=mask.bit_count()*2+(2 if mask&0x2000 else 0)
            require(at+size<=len(raw),'Truncated original steering register row')
            if row==0:
                require(struct.unpack_from('<13HI',raw,at)==entry,'Original steering entry row differs')
            at+=size
        final=dict(memory);written=set();writes=number(4);require(writes<300000,'Original steering write reserve differs')
        for unused in range(writes):
            address,size,value=struct.unpack('<IBH',take(7))
            require(size in (1,2) and address+size<=1048576,'Original steering write exceeds memory')
            for offset in range(size):
                final[address+offset]=(value>>(offset*8))&255;written.add(address+offset)
        if domain==2:
            excluded['square_root']+=1;continue
        if outcome==1:
            excluded['runtime_error']+=1;continue
        def word(values,address):
            require(address in values and address+1 in values,'Vector extraction read an unseeded/unwritten word')
            return values[address]|(values[address+1]<<8)
        segment,bp,sp=entry[10],entry[6],entry[11]
        if domain==0:
            require(entry[7]==0x1000 and entry[12]==0x346b and endpoint[12]==0x7f00,'Vector helper endpoint differs')
            refs=[]
            for slot in range(5):
                address=segment*16+((sp+2+slot*4)&65535)
                refs.append(word(memory,address+2)*16+word(memory,address))
            if len({a+n for a in refs for n in (0,1)})!=10:
                excluded['alias']+=1;continue
            out_y,out_x,speed,y,x=refs
        else:
            require(entry[7]==0x1000 and entry[12]==0x710d and endpoint[12]==0x714f,'Vector caller endpoint differs')
            out_y=segment*16+((bp-14)&65535);out_x=segment*16+((bp-12)&65535)
            x=segment*16+((bp-4)&65535);y=segment*16+((bp-6)&65535);speed=entry[8]*16+0x2074
        require(all(a+n in written for a in (out_x,out_y) for n in (0,1)),'Original did not write both vector outputs')
        signed=lambda value:value-65536 if value>=32768 else value
        dx,dy=signed(word(memory,x)),signed(word(memory,y))
        rows.append((index,dx,dy,word(memory,speed),signed(word(final,out_x)),signed(word(final,out_y)),domain,
                     int(abs(dx)+abs(dy)<65535)))
    require(at==len(raw) and domains==[2136,64,1536] and outcomes==[2961,775],
        'Original steering extraction coverage differs')
    require(len(rows)==2136 and excluded==dict(square_root=1536,runtime_error=10,alias=54),
        'Typed vector extraction scope differs')
    output=MAGIC+struct.pack('<I',len(rows))+hashlib.sha256(raw).digest()+b''.join(struct.pack('<IhhHhhBB',*r) for r in rows)
    info=dict(cases=len(rows),live_caller_cases=sum(r[6]==1 for r in rows),
        app_homing_cases=sum(r[7] for r in rows),app_gate_excluded=sum(not r[7] for r in rows),excluded=excluded,
        parent_projection_sha256=hashlib.sha256(raw).hexdigest(),bytes=len(output),sha256=hashlib.sha256(output).hexdigest())
    return output,info


def run(root,out,report=None):
    fixture=root/'tests/fixtures/actor_steering'
    protected=[root/name for name in original.INPUTS]+[fixture/'manifest.json',fixture/'oracle.bin.gz',
        root/'tools/export_actor_steering_vectors.py']
    for candidate in (out,report):
        if candidate:
            require(all(candidate.resolve()!=p.resolve() and not
                (candidate.exists() and p.exists() and candidate.samefile(p)) for p in protected),
                'Vector export/report must not replace authenticated inputs')
    if report:
        require(out.resolve()!=report.resolve() and not
            (out.exists() and report.exists() and out.samefile(report)),'Vector report/export overlap')
    result=dict(status='failed',production_app_comparison=False,whole_game_parity=False)
    try:
        require((root/'tools/export_actor_steering_vectors.py').read_bytes()==Path(__file__).read_bytes(),
            'Vector exporter source differs from executing source')
        output,info=derive(original.read_fixture(root,fixture))
        require(info['sha256']==VECTORS_SHA,'Frozen derived steering vectors differ')
        if out.exists():
            require(out.read_bytes()==output,'Existing vector export differs; preserved')
        else:
            out.write_bytes(output)
        result.update(info,status='passed')
    except Exception as error:
        result['error']=str(error);raise
    finally:
        if report:
            report.write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--report',type=Path);args=parser.parse_args();print(json.dumps(run(ROOT,args.out,args.report),sort_keys=True))
