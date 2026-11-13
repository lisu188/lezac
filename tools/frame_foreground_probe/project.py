"""Project original whole foreground CPU, palette, pixels and independently replayed clocks."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

from .trace import rows,inspect_trace

sha=lambda raw:hashlib.sha256(raw).hexdigest()
REGS='ax bx cx dx si di bp cs ds es ss sp ip'.split()


def projections(path,recipe):
    checked=inspect_trace(path)
    for name in ('trace_end_marker','trace_uncompressed_bytes','trace_uncompressed_sha256','keyboard_windows','validated_target_completed'):
        assert checked[name]==recipe[name]
    output=bytearray(b'LZFFGD01'+struct.pack('<I',len(checked['keyboard_windows'])))
    entry=previous=None;packed=bytearray();events=[];deliveries=[];cases=[];count=0
    for row in rows(path,{}):
        kind=row['kind']
        if kind=='identified':
            continue
        if kind=='keyboard_enter':
            entry=row;previous=None;packed=bytearray();events=[];deliveries=[];count=0
            assert int(entry['cs'])==recipe['code_segment'] and int(entry['ip'])==0x7903 and int(entry['ds'])==recipe['data_segment']
            assert int(entry['keyboard_cs'])==0xf000 and bytes.fromhex(entry['keyboard_stub'])[0:3]==b'\xfb\xfe8'
            continue
        assert entry and row['stack_ss']==entry['ss'] and row['stack_base']==entry['stack_base']
        assert int(row['defined_flags'])==0x700
        if previous:
            op=bytes.fromhex(previous['opcode'])
            if op[0] in (0xe4,0xe6):
                events.append((op[0]==0xe6,op[1],int(previous['ax'])&255 if op[0]==0xe6 else int(row['ax'])&255))
        if (int(row['cs']),int(row['ip']))==(0xf000,0xfea5):
            deliveries.append(count)
        packed.extend(struct.pack('<13H3I',*[int(row[key]) for key in REGS],int(row['flags']),int(row['defined_flags']),len(events)))
        for key in ('stack','crt_globals','bios_keyboard','globals','drain_key','hud_globals','hud_pixels','psp_bytes','frame_globals','display_globals','pacing_globals'):
            packed.extend(bytes.fromhex(row[key]))
        count+=1
        if kind=='keyboard_return':
            assert int(row['sp'])==int(entry['sp']) and int(row['ip'])==0x7a13 and 1<count<=150001
            bank=bytes.fromhex(entry['bank']);offset,segment=struct.unpack_from('<HH',bytes.fromhex(entry['globals']),5)
            assert int(entry['vector_cs'])==0xf000
            output.extend(struct.pack('<10H3I',recipe['code_segment'],int(entry['keyboard_base']),int(entry['ss']),
                int(entry['stack_base']),int(entry['keyboard_entry']),segment,offset,len(bank),int(entry['vector_ip']),int(entry['psp']),count,len(events),len(deliveries)))
            for value in deliveries:
                output.extend(struct.pack('<I',value))
            output.extend(bank+bytes.fromhex(entry['hud_font'])+packed)
            for event in events:
                output.extend(struct.pack('<BHB',*event))
            cases.append(dict(category=int(entry['keyboard_class']),entry_ip=int(entry['keyboard_entry']),states=count,irq_boundaries=deliveries))
            entry=None
        previous=row
    assert entry is None
    return bytes(output),cases


def project(capture,out,executable):
    capture=capture.resolve(strict=True);out=out.resolve();assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
    recipe=json.loads((capture/'report.json').read_bytes());trace=capture/'guest-keyboard.csv.gz';raw=trace.read_bytes()
    assert recipe['status']=='observed' and recipe['passed'] is True and recipe['target_completed'] is True and recipe['validated_target_completed'] is True
    assert recipe['child_exit_code']==0 and recipe['canonical_assets_unchanged'] is True
    assert recipe['bios_keyboard_service_profile']=='DOSBox 0.74-3 INT16 AH=00/01 with CB_INT16 and original BIOS queue translation'
    assert recipe['host_build']['guest_instruction_patches']==0 and recipe['host_build']['cpu_source_unchanged'] is True
    assert recipe['host_build']['rebuild_producer_sha256']==sha(Path(__file__).with_name('rebuild.py').read_bytes())
    assert recipe['trace_sha256']==sha(raw) and recipe['trace_bytes']==len(raw)
    for field,name in [('producer_sha256','producer.py'),('input_route_sha256','input-route.py'),('capture_contract_sha256','capture-contract.py')]:
        assert recipe[field]==sha((capture/name).read_bytes())
    assert recipe['trace_parser_sha256']==sha(Path(__file__).with_name('trace.py').read_bytes())
    assert recipe['process_memory_writes']==recipe['injected_instructions']==recipe['process_pauses']==0
    assert recipe['gameplay_state_seeded'] is False and recipe['clock_or_irq_state_seeded'] is False
    for field,name in [('probe_sha256','lezac_work_probe.h'),('patch_sha256','dos_time_hook.patch'),
        ('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h')]:
        assert recipe['host_build'][field]==sha(Path(__file__).with_name(name).read_bytes())
    assert all(digest==sha(Path(__file__).with_name(name).read_bytes()) for name,digest in recipe['host_build']['device_fragment_hashes'].items())
    exe=executable.read_bytes();assert sha(exe)==recipe['executable_sha256']=='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    mz=struct.unpack_from('<14H',exe);expected=bytearray(exe[0x770:])
    for index in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+index*4);at=segment*16+offset
        struct.pack_into('<H',expected,at,(struct.unpack_from('<H',expected,at)[0]+recipe['code_segment'])&65535)
    proofs=[]
    for sample in recipe['samples']:
        assert Path(sample['name']).name==sample['name']
        compressed=(capture/(sample['name']+'.ram.gz')).read_bytes()
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            ram=stream.read(1048577)
        assert len(ram)==1048576 and sha(ram)==sample['ram_sha256'] and sha(compressed)==sample['ram_gzip_sha256']
        start=recipe['code_segment']*16;assert ram[start:start+43552]==expected[:43552]
        png=(capture/(sample['name']+'.png')).read_bytes();assert sha(png)==sample['png_sha256']
        proofs.append(dict(name=sample['name'],ram_sha256=sha(ram),png_sha256=sha(png),code_bytes_verified=43552))
    cpu,cases=projections(trace,recipe);clock=clock_projection(trace,cases);out.mkdir();(out/'cpu.bin').write_bytes(cpu)
    (out/'clock.bin').write_bytes(clock)
    record=dict(cases=cases,states=sum(item['states'] for item in cases),cpu_sha256=sha(cpu),clock_sha256=sha(clock),trace_sha256=sha(raw),raw_samples_verified=proofs,
        irq_eligibility_claim=False,later_cpu_memory_injected=False,whole_game_parity=False)
    (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)


def clock_projection(path,cases):
    output=bytearray(b'LZFGCL01'+struct.pack('<I',len(cases)));current=-1;palette=None
    for row in rows(path,{}):
        if row['kind']=='identified':
            continue
        if row['kind']=='keyboard_enter':
            current+=1;palette=None
            output.extend(struct.pack('<I',cases[current]['states']))
            native=row['native_palette'];output.extend(struct.pack('<256I',*[int(native[i:i+8],16) for i in range(0,2048,8)]));continue
        op=bytes.fromhex(row['opcode']);kind=1 if op[0]==0xe4 else 2 if op[0]==0xe6 else 0
        output.extend(struct.pack('<3qQI2H',int(row['cpu_cycles']),int(row['cpu_left']),int(row['io_delay_removed']),
            int(row['pic_ticks']),int(row['flags']),int(row['cs']),int(row['ip'])))
        output.extend(struct.pack('<BHB2B',kind,op[1] if kind else 0,int(row['ax'])&255,op[0],op[1]))
        output.extend(struct.pack('<4H4B',*[int(row[key]) for key in
            ('active_lines','masked_lines','inservice_lines','pic_pending','pic_active','irq0_vector','pic_special','pic_auto_eoi')]))
        queue=[item.split(':') for item in row['queue'].split(';') if item]
        assert len(queue)<=64 and all(int(item[1]) in (1,3,4,5,6,7) for item in queue)
        output.extend(struct.pack('<IQIBBH',int(row['pit0_delay_bits']),int(row['pit0_start_bits']),int(row['pit0_count']),
            int(row['pit0_mode']),int(row['pit0_update']),len(queue)))
        for index,kind,value in queue:
            output.extend(struct.pack('<IBQ',int(index,16),int(kind),int(value)))
        devices=[int(value) for value in row['devices'].split(';')];tickers=[int(value) for value in row['tickers'].split(';') if value]
        assert len(devices)==31 and tickers==[11,10] and row['ticker_overflow']=='0'
        output.extend(struct.pack('<31QB',*devices,len(tickers))+bytes(tickers))
        changed=row['render_palette']!=palette
        output.extend(struct.pack('<B',changed))
        if changed:
            palette=row['render_palette'];parts=palette.split(';')
            output.extend(struct.pack('<4I',*[int(value) for value in parts[:4]]))
            for token in parts[4:6]:
                output.extend(struct.pack('<256I',*[int(token[i:i+8],16) for i in range(0,2048,8)]))
            output.extend(bytes.fromhex(parts[6]))
        output.extend(struct.pack('<18I',*[int(value) for value in row['gfx_format'].split(';')]))
    return bytes(output)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--exe',type=Path,required=True)
    args=parser.parse_args();project(args.capture,args.out,args.exe)
