"""Check the exact frozen natural IRQ corpus, not arbitrary capture recipes."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import struct

from original_capture_contract import ASSET_PINS

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/timer_irq/natural'
MANIFEST_SHA='a705bbfe749811fbfe0e9703e27a308b7368d6c3f00fc27018460e3b42c92eb2'
REGISTERS='ax bx cx dx si di bp cs ds es ss sp ip'.split()
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def require(condition,message):
    if not condition:
        raise ValueError(message)


def parse_cases(raw,recipe):
    """Parse already-bound frozen data; this does not establish capture provenance."""
    require(0<len(raw)<8*1024**2 and raw.endswith(b'\nend\n'),'Natural trace terminal or cap differs')
    rows=list(csv.DictReader(raw[:-4].decode('ascii').splitlines()))
    require(rows and rows[0]['kind']=='identified' and int(rows[0]['ip'])==0x7783,'Startup identity differs')
    require(all(row['kind'] in ('identified','enter','instruction','returned') and None not in row for row in rows),
            'Incomplete or malformed IRQ window')
    cases=[]
    for call in range(1,max(int(row['call']) for row in rows)+1):
        group=[row for row in rows if int(row['call'])==call]
        require(group[0]['kind']=='enter' and group[-1]['kind']=='returned','IRQ window order differs')
        entry=group[0]
        states=[dict(row) for row in group if row['kind'] in ('instruction','returned')]
        require(len(states)==len(group)-1 and len(states)>1 and
            all(int(b['dispatch'])==int(a['dispatch'])+1 for a,b in zip(states,states[1:])),'IRQ dispatch continuity differs')
        require(int(entry['cs'])==0xf000 and int(entry['ip'])==0xfea5 and entry['id_toggle']=='2097152','BIOS entry differs')
        require(all(int(row['int1c_cs'])==recipe['code_segment'] and int(row['int1c_ip'])==0xfbe and
                    row['stack_ss']==entry['stack_ss'] and row['stack_base']==entry['stack_base'] and
                    len(bytes.fromhex(row['stack']))==128 and len(bytes.fromhex(row['globals']))==10 and
                    int(row['defined_flags'])==(0x207fd7 if row['kind']=='returned' else 0x700) for row in states),
                'IRQ memory/vector/flag scope differs')
        frame=bytes.fromhex(entry['stack'])
        at=(int(entry['sp'])-int(entry['stack_base']))&65535
        require(at+6<=128,'Return frame outside observed stack')
        ip,cs,flags=struct.unpack_from('<HHH',frame,at)
        last=states[-1]
        require((int(last['ip']),int(last['cs']),int(last['sp']))==(ip,cs,(int(entry['sp'])+6)&65535) and
                int(last['bios_ticks'])==(int(entry['bios_ticks'])+1)&0xffffffff,'IRQ return or BIOS increment differs')
        data=bytes.fromhex(entry['globals'])
        bank=bytes.fromhex(entry['bank'])
        require(len(bank)==780 and (data[-1]==0 or bank==(ROOT/'PROEFS.SON').read_bytes()[2:]),'Active bank input differs')
        bank_offset,bank_segment=struct.unpack_from('<HH',data,5)
        io=[]
        for index,state in enumerate(states):
            state['io_count']=len(io)
            if state['kind']=='returned':continue
            op=bytes.fromhex(state['opcode'])
            require(len(op)==8,'Instruction window differs')
            if op[0] in (0xe4,0xe6):
                require(op[1] in ((0x61,) if op[0]==0xe4 else (0x61,0x42,0x43,0x20)),'Unexpected port')
                io.append((op[0]==0xe6,op[1],int(state['ax'])&255 if op[0]==0xe6 else int(states[index+1]['ax'])&255))
        cases.append((recipe['code_segment'],entry,states,io,bank_offset,bank_segment))
    return cases


def projection(cases):
    output=bytearray(b'LZTIMN01'+struct.pack('<I',len(cases)))
    for game,entry,states,io,bank_offset,bank_segment in cases:
        output.extend(struct.pack('<5H3I',game,int(entry['stack_ss']),int(entry['stack_base']),bank_segment,bank_offset,
            int(entry['id_toggle']),len(states),len(io)))
        output.extend(bytes.fromhex(entry['bank']))
        for state in states:
            output.extend(struct.pack('<13H3I2BI',*[int(state[key]) for key in REGISTERS],int(state['flags']),
                int(state['defined_flags']),int(state['bios_ticks']),int(state['motor']),int(state['drive']),state['io_count']))
            output.extend(bytes.fromhex(state['stack']));output.extend(bytes.fromhex(state['globals']))
        for out,port,value in io:output.extend(struct.pack('<BHB',out,port,value))
    return bytes(output)


def read_fixture():
    raw=(FIXTURE/'manifest.json').read_bytes()
    require(sha(raw)==MANIFEST_SHA,'Frozen natural manifest differs')
    manifest=json.loads(raw)
    for item in manifest['files']:
        raw=(FIXTURE/item['name']).read_bytes()
        require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen natural evidence differs')
    for name,(size,pin) in ASSET_PINS.items():
        raw=(ROOT/name).read_bytes()
        require(len(raw)==size and sha(raw)==pin,'Installed original differs: '+name)
    cases=[]
    for run in ('r4','r5'):
        raw=gzip.decompress((FIXTURE/(run+'.csv.gz')).read_bytes())
        recipe=json.loads((FIXTURE/(run+'-recipe.json')).read_text())
        require(recipe['passed'] is True and recipe['status']=='observed' and recipe['child_exit_code']==0 and
                recipe['trace_sha256']==sha(raw) and recipe['trace_bytes']==len(raw),'Natural recipe binding differs')
        require(recipe['producer_sha256']==sha((ROOT/'tools/timer_irq_probe/capture.py').read_bytes()) and
                recipe['host_build']['probe_sha256']==sha((ROOT/'tools/timer_irq_probe/lezac_work_probe.h').read_bytes()) and
                recipe['capture_contract_sha256']==sha((ROOT/'tools/original_capture_contract.py').read_bytes()),
                'Natural producer or observer differs')
        cases.extend(parse_cases(raw,recipe))
    require(len(cases)==24 and sum(len(case[2]) for case in cases)==1434,'Natural coverage differs')
    print('timer_irq_natural_fixture=ok calls=24 states=1434 seeded_gameplay=0 device_inputs_observed=1 scheduler_claim=0')
    return cases


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection',type=Path)
    args=parser.parse_args()
    cases=read_fixture()
    if args.projection:args.projection.write_bytes(projection(cases))
