"""Project atomic active-window inputs and independently observed CPU/clock boundaries."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from frame_active_live_probe.trace import rows,inspect_trace
from original_capture_contract import read_canonical_assets

ROOT=Path(__file__).resolve().parents[2]
OWN=Path(__file__).resolve().parent
sha=lambda raw:hashlib.sha256(raw).hexdigest()


def _project(capture,out,repo):
    capture=capture.resolve(strict=True);out=out.resolve();repo=repo.resolve(strict=True)
    if not out.is_relative_to(Path('/dev/shm')) or not out.is_dir():
        raise ValueError('Projection directory was not prepared')
    recipe=json.loads((capture/'report.json').read_bytes());host=recipe['host_build']
    assert recipe['schema']=='lezac-instrumented-active-live-v1' and recipe['status']=='observed' and recipe['passed'] is True
    assert recipe['validated_target_completed'] is True and recipe['child_exit_code']==0
    assert recipe['canonical_assets_unchanged'] is True and recipe['atomic_active_endpoints'] is True
    assert recipe['actual_environment_verified'] is True and recipe['actual_sdl_sha256']==host['sdl_runtime_sha256']
    assert host['schema']=='lezac-active-observer-build-v1' and host['status']=='built'
    assert host['host_sha256']==recipe['dosbox_sha256']
    assert host['guest_instruction_patches']==recipe['process_memory_writes']==recipe['injected_instructions']==recipe['process_pauses']==0
    assert host['cpu_source_unchanged'] is True and recipe['gameplay_state_seeded'] is False and recipe['clock_or_irq_state_seeded'] is False
    for field,name in [('producer_sha256','capture.py'),('trace_parser_sha256','trace.py')]:
        assert recipe[field]==sha((OWN/name).read_bytes())
    for field,name in [('active_rebuilder_sha256','rebuild.py'),('probe_sha256','lezac_work_probe.h'),
            ('active_vga_fragment_sha256','vga_frame_observation.inc')]:
        assert host[field]==sha((OWN/name).read_bytes())
    assets=read_canonical_assets(repo)
    assert set(assets)==set(recipe['assets']) and all(sha(raw)==recipe['assets'][name]['sha256']
        and len(raw)==recipe['assets'][name]['bytes'] for name,raw in assets.items())
    exe=assets['LEZAC.EXE'];assert sha(exe)=='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    expected=bytearray(exe[0x770:]);mz=struct.unpack_from('<14H',exe);game=recipe['code_segment']
    for index in range(mz[3]):
        offset,segment=struct.unpack_from('<HH',exe,mz[12]+index*4);at=segment*16+offset
        struct.pack_into('<H',expected,at,(struct.unpack_from('<H',expected,at)[0]+game)&65535)
    trace=capture/'guest-keyboard.csv.gz'
    assert sha(trace.read_bytes())==recipe['trace_sha256']
    details=inspect_trace(trace)
    assert details['validated_target_completed'] is True and details['active_live_windows']==recipe['active_live_windows']
    windows=details['active_live_windows'];cases=[];cpu=bytearray(b'LZACTV01'+struct.pack('<I',len(windows)));current=None
    for row in rows(trace,{}):
        if row['kind']=='identified':
            continue
        if row['kind']=='keyboard_enter':
            window=windows[len(cases)];identity=int(row['call']);assert identity==window['window']
            memories=[]
            for phase in ('initial','final'):
                path=capture/('atomic-%d-%s.ram.gz'%(identity,phase));compressed=path.read_bytes()
                with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
                    memory=stream.read(1048577)
                assert len(memory)==1048576 and memory[game*16:game*16+43552]==expected[:43552]
                memories.append(memory)
            cpu.extend(struct.pack('<4H2I',game,int(row['vector_ip']),int(row['keyboard_base']),int(row['psp']),
                int(row['id_toggle']),window['states']))
            cpu.extend(memories[0]);cpu.extend(memories[1])
            current=dict(window=identity,states=0,initial_sha256=sha(memories[0]),final_sha256=sha(memories[1]),
                irq_entries=window['irq_entries'],render_irq_entries=window['render_irq_entries'])
            continue
        assert current is not None and int(row['call'])==current['window']
        r=[int(row[name]) for name in ('ax','bx','cx','dx','si','di','bp','cs','ds','es','ss','sp','ip')]
        cpu.extend(struct.pack('<13H2I',*r,int(row['flags']),int(row['defined_flags'])))
        opcode=bytes.fromhex(row['opcode']);assert len(opcode)==8;cpu.extend(opcode);current['states']+=1
        if row['kind']=='keyboard_return':
            assert current['states']==windows[len(cases)]['states'];cases.append(current);current=None
    assert current is None and len(cases)==len(windows)
    clock=clock_projection(trace,cases)
    (out/'cpu.bin').write_bytes(cpu);(out/'clock.bin').write_bytes(clock)
    result=dict(cases=cases,cpu_sha256=sha(cpu),clock_sha256=sha(clock),recipe_sha256=sha((capture/'report.json').read_bytes()),
        trace_sha256=recipe['trace_sha256'],initial_memory_only_as_input=True,later_cpu_memory_injected=False,
        whole_game_parity=False,actual_app_integration=False)
    return result


def project(capture,out,repo=ROOT):
    out=out.resolve()
    if not out.is_relative_to(Path('/dev/shm')) or out.exists():
        raise ValueError('Use a new RAM-only projection directory')
    out.mkdir();result=dict(status='failed',later_cpu_memory_injected=False,whole_game_parity=False)
    try:
        result=_project(capture,out,repo)
        result['status']='projected'
        result['projector_sha256']=sha(Path(__file__).read_bytes())
    except BaseException as error:
        result['error']=repr(error)
        raise
    finally:
        (out/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    return result


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
    for name in ('capture','out','repo'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();project(args.capture,args.out,args.repo)
