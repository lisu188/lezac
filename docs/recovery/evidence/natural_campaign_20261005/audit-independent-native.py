"""Compare two retained original Level 2 executions without accepting C++ input."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path('/mnt/c/Users/andrz/git/LEZAC')
WORK = Path('/dev/shm/lezac-campaign-regression-20261005')
sys.path.insert(0, str(ROOT / 'tools'))
import level1_fidelity as fidelity
import level1_handoff as handoff
import natural_campaign as campaign

paths = [ROOT / 'build-codex-tmp/level2-natural-outcome-evidence-20261001-v18/lezac-natural-level2-outcome-original-20261001-v18',
         ROOT / 'build-codex-tmp/level3-failed-handoff-evidence-20261001-v20/lezac-natural-level3-handoff-original-20261001-v20']
digests = ['509d03f02d561c85874b2322fc295b6bfb53f9ee0b12756573a14c8a52ff3f88',
           '64829a917bcbd36b297c0da158d9984852c220550e617fc27a61fa4e5f0462e9']
captures = []
for path, digest in zip(paths, digests):
    manifest = fidelity.strict_json((path / 'outcome-manifest.json').read_text())
    fidelity.require(manifest['status'] == 'captured' and manifest['patches_restored'] is True and
                     manifest['gameplay_frames'] == 2352 and manifest['gate_cpp_tick'] == 3094,
                     'native capture incomplete')
    for name, expected in manifest['files'].items():
        fidelity.require(fidelity.sha256(path / name) == expected, 'native captured bytes changed')
    fidelity.require(fidelity.sha256(path / 'gameplay.jsonl.gz') == digest, 'native stream pin differs')
    for name in ('outcome-observer.py', 'extension-observer.py', 'observer.py', 'results-observer.py'):
        fidelity.require(fidelity.sha256(path / name) == campaign.CAPTURE_PINS[name], 'native producer differs')
    captures.append(handoff.load(path / 'gameplay.jsonl.gz'))
fidelity.require((paths[0] / 'extension-route.txt').read_bytes() == (paths[1] / 'extension-route.txt').read_bytes(),
                 'different original routes')
projected = hashlib.sha256()
for index, (left, right) in enumerate(zip(captures[0][1:-1], captures[1][1:-1])):
    fidelity.require(left['sample'] == right['sample'] == index and left['cpp_tick'] == right['cpp_tick'] == 743 + index and
                     left['events'] == right['events'] and left['gate_eligible'] == right['gate_eligible'] == (index == 2351) and
                     left['rgb_sha256'] == right['rgb_sha256'], 'native frame/input/gate differs')
    for field, pi in (('pre', 0), ('rendered', 1), ('post', 2)):
        a = campaign.native_boundary(left[field], left['dac'][pi], captures[0][0]['atlas'])
        b = campaign.native_boundary(right[field], right['dac'][pi], captures[1][0]['atlas'])
        fidelity.require(a == b, 'independent original projected boundary differs')
        projected.update(campaign.original.json_bytes(a))
report = {'status': 'match', 'frames': 2352, 'projected_boundaries': 7056, 'pixels': 150528000,
          'gameplay_streams_sha256': digests, 'projected_body_sha256': projected.hexdigest(),
          'scope': 'pre/rendered/post mapped state, full map planes, 217 DAC entries and whole RGB frame hashes',
          'original_captures_are_historical': True, 'raw_all_byte_equivalence_claim': False,
          'all_actor_fields_compared': False, 'whole_game_parity': False}
(WORK / 'independent-native-comparison.json').write_bytes(campaign.original.json_bytes(report))
print(json.dumps(report), flush=True)
