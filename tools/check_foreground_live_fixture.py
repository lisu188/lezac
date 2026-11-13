"""Authenticate changed-HUD and natural-timer foreground observations."""
import argparse,hashlib,json
from pathlib import Path
from frame_foreground_probe.project import projections,clock_projection
from frame_foreground_live_probe.trace import inspect_trace

ROOT=Path(__file__).resolve().parents[1];FIXTURE=ROOT/'tests/fixtures/foreground_live';MANIFEST_SHA='dc3c9625e33cf53c8a18504a3ee465f37b525191af94cd952e9034967fbf2794'
sha=lambda raw:hashlib.sha256(raw).hexdigest()
def require(value,message):
 if not value:raise ValueError(message)

def read_fixture(root=FIXTURE):
 raw=(root/'manifest.json').read_bytes();require(sha(raw)==MANIFEST_SHA,'Frozen live foreground manifest differs');manifest=json.loads(raw)
 for name,digest in manifest['sources'].items():require(sha((ROOT/name).read_bytes())==digest,'Frozen live foreground source differs: '+name)
 require({p['name'] for p in manifest['files']}=={'natural.csv.gz','natural-recipe.json'},'Frozen live foreground file domain differs')
 files={}
 for item in manifest['files']:
  raw=(root/item['name']).read_bytes();require(len(raw)==item['bytes'] and sha(raw)==item['sha256'],'Frozen live foreground observation differs');files[item['name']]=raw
 recipe=json.loads(files['natural-recipe.json']);host=recipe['host_build'];own='tools/frame_foreground_live_probe/';common='tools/frame_foreground_probe/'
 require(recipe['schema']=='lezac-instrumented-foreground-live-v1' and recipe['status']=='observed' and recipe['passed'] is True and
  recipe['validated_target_completed'] is True and recipe['target_completed'] is True and recipe['child_exit_code']==0 and
  recipe['canonical_assets_unchanged'] is True,'Live foreground completion differs')
 require(recipe['dosbox_sha256']==host['host_sha256']=='264fc86db615ea5485936d1636a122fa08d89718f0238be9e926155cf34ae38a','Live foreground host differs')
 for field,name in [('producer_sha256','capture.py'),('trace_parser_sha256','trace.py')]:require(recipe[field]==manifest['sources'][own+name],'Live foreground producer binding differs')
 for field,name in [('probe_sha256','lezac_work_probe.h'),('rebuild_producer_sha256','rebuild.py'),('repair_producer_sha256','rebuild.py')]:
  require(host[field]==manifest['sources'][own+name],'Live foreground observer/rebuild binding differs')
 for field,name in [('patch_sha256','dos_time_hook.patch'),('clock_patch_sha256','clock_hook.patch'),('clock_api_sha256','lezac_clock_observation.h')]:
  require(host[field]==manifest['sources'][common+name],'Live foreground shared observer binding differs')
 require(set(host['device_fragment_hashes'])=={'vga_clock_observation.inc','render_clock_observation.inc','gfx_clock_observation.inc',
  'keyboard_clock_observation.inc','mixer_clock_observation.inc','pic_tickers_observation.inc'},'Live foreground getter domain differs')
 for name,digest in host['device_fragment_hashes'].items():require(digest==manifest['sources'][common+name],'Live foreground getter binding differs')
 for field,name in [('input_route_sha256','input_route.py'),('common_trace_parser_sha256','trace.py'),('common_projection_sha256','project.py')]:
  require(recipe[field]==manifest['sources'][common+name],'Live foreground common codec/route binding differs')
 require(recipe['capture_contract_sha256']==manifest['sources']['tools/original_capture_contract.py'],'Live foreground asset contract differs')
 require(host['guest_instruction_patches']==0 and host['cpu_source_unchanged'] is True and recipe['process_memory_writes']==recipe['process_pauses']==
  recipe['injected_instructions']==0 and recipe['gameplay_state_seeded'] is False and recipe['clock_or_irq_state_seeded'] is False,'Live foreground mutation profile differs')
 require(recipe['trace_sha256']==sha(files['natural.csv.gz']) and recipe['trace_bytes']==len(files['natural.csv.gz']),'Live foreground trace binding differs')
 details=inspect_trace(root/'natural.csv.gz');require(details['foreground_live_windows']==recipe['foreground_live_windows']==manifest['live_windows'],
  'Live foreground coverage proof differs')
 cpu,cases=projections(root/'natural.csv.gz',recipe);clock=clock_projection(root/'natural.csv.gz',cases)
 require(cases==manifest['cases'] and sum(c['states'] for c in cases)==144505 and len(cases)==2 and
  sum(len(c['irq_boundaries']) for c in cases)==1 and sha(cpu)==manifest['cpu_sha256'] and sha(clock)==manifest['clock_sha256'],'Live foreground projections differ')
 require(manifest['raw_memory_published'] is False and manifest['raw_memory_available_to_frozen_checker'] is False and
  manifest['whole_game_parity'] is False and manifest['actual_app_integration'] is False,'Live foreground evidence scope differs')
 print('foreground_live_fixture=ok cases=2 states=144505 natural_irqs=1 changed_hud_windows=1 raw_ram_files_verified=0')
 return cpu,clock

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--cpu',type=Path);parser.add_argument('--clock',type=Path)
 args=parser.parse_args();outputs=read_fixture()
 for path,raw in zip((args.cpu,args.clock),outputs):
  if path and (not path.exists() or sha(path.read_bytes())!=sha(raw)):path.write_bytes(raw)
