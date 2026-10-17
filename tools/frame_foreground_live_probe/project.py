"""Authenticate live foreground captures before using the shared frozen codecs."""
import argparse,gzip,hashlib,io,json,struct
from pathlib import Path

from frame_foreground_probe.project import projections,clock_projection
from frame_foreground_live_probe.trace import inspect_trace
from original_capture_contract import read_canonical_assets

COMMON=Path(__file__).resolve().parents[1]/'frame_foreground_probe'
sha=lambda raw:hashlib.sha256(raw).hexdigest()

def project(capture,out,repo):
 capture=capture.resolve(strict=True);out=out.resolve();repo=repo.resolve(strict=True)
 assert out.is_relative_to(Path('/dev/shm')) and not out.exists()
 recipe=json.loads((capture/'report.json').read_bytes());host=recipe['host_build'];trace=capture/'guest-keyboard.csv.gz'
 assert recipe['schema']=='lezac-instrumented-foreground-live-v1' and recipe['status']=='observed' and recipe['passed'] is True
 assert recipe['target_completed'] is True and recipe['validated_target_completed'] is True and recipe['child_exit_code']==0
 assert recipe['canonical_assets_unchanged'] is True and host['host_sha256']==recipe['dosbox_sha256']
 assert host['guest_instruction_patches']==0 and host['cpu_source_unchanged'] is True
 assert recipe['process_memory_writes']==recipe['injected_instructions']==recipe['process_pauses']==0
 assert recipe['gameplay_state_seeded'] is False and recipe['clock_or_irq_state_seeded'] is False
 for field,name in [('producer_sha256','capture.py'),('trace_parser_sha256','trace.py')]:
  assert recipe[field]==sha(Path(__file__).with_name(name).read_bytes())
 for field,name in [('probe_sha256','lezac_work_probe.h'),('rebuild_producer_sha256','rebuild.py'),('repair_producer_sha256','rebuild.py')]:
  assert host[field]==sha(Path(__file__).with_name(name).read_bytes())
 for field,name in [('patch_sha256','dos_time_hook.patch'),('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h')]:
  assert host[field]==sha((COMMON/name).read_bytes())
 assert all(digest==sha((COMMON/name).read_bytes()) for name,digest in host['device_fragment_hashes'].items())
 for field,name in [('input_route_sha256','input_route.py'),('common_trace_parser_sha256','trace.py'),('common_projection_sha256','project.py')]:
  assert recipe[field]==sha((COMMON/name).read_bytes())
 assert recipe['capture_contract_sha256']==sha((COMMON.parent/'original_capture_contract.py').read_bytes())
 for field,name in [('producer_sha256','producer.py'),('input_route_sha256','input-route.py'),('capture_contract_sha256','capture-contract.py')]:
  assert recipe[field]==sha((capture/name).read_bytes())
 raw=trace.read_bytes();assert recipe['trace_sha256']==sha(raw) and recipe['trace_bytes']==len(raw)
 details=inspect_trace(trace)
 for field in ('trace_end_marker','trace_uncompressed_bytes','trace_uncompressed_sha256','keyboard_windows','validated_target_completed','foreground_live_windows'):
  assert recipe[field]==details[field]
 assets=read_canonical_assets(repo)
 assert set(assets)==set(recipe['assets']) and all(sha(raw)==recipe['assets'][name]['sha256'] and len(raw)==recipe['assets'][name]['bytes'] for name,raw in assets.items())
 exe=assets['LEZAC.EXE'];assert sha(exe)==recipe['executable_sha256']=='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
 mz=struct.unpack_from('<14H',exe);expected=bytearray(exe[0x770:])
 for index in range(mz[3]):
  offset,segment=struct.unpack_from('<HH',exe,mz[12]+index*4);at=segment*16+offset
  struct.pack_into('<H',expected,at,(struct.unpack_from('<H',expected,at)[0]+recipe['code_segment'])&65535)
 proofs=[]
 for sample in recipe['samples']:
  assert Path(sample['name']).name==sample['name']
  compressed=(capture/(sample['name']+'.ram.gz')).read_bytes()
  with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:ram=stream.read(1048577)
  assert len(ram)==1048576 and sha(ram)==sample['ram_sha256'] and sha(compressed)==sample['ram_gzip_sha256']
  start=recipe['code_segment']*16;assert ram[start:start+43552]==expected[:43552]
  png=(capture/(sample['name']+'.png')).read_bytes();assert sha(png)==sample['png_sha256']
  proofs.append(dict(name=sample['name'],ram_sha256=sha(ram),png_sha256=sha(png),code_bytes_verified=43552))
 cpu,cases=projections(trace,recipe);clock=clock_projection(trace,cases);out.mkdir()
 (out/'cpu.bin').write_bytes(cpu);(out/'clock.bin').write_bytes(clock)
 record=dict(cases=cases,states=sum(c['states'] for c in cases),live_windows=details['foreground_live_windows'],
  cpu_sha256=sha(cpu),clock_sha256=sha(clock),trace_sha256=sha(raw),raw_samples_verified=proofs,
  later_cpu_memory_injected=False,whole_game_parity=False,actual_app_integration=False)
 (out/'manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 for name in ('capture','out','repo'):parser.add_argument('--'+name,type=Path,required=True)
 args=parser.parse_args();project(args.capture,args.out,args.repo)
