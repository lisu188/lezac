"""Check original snapshot coherence without normalizing any differing bytes."""
import gzip
import hashlib
import json
from pathlib import Path
import sys

SOURCE = Path('/dev/shm/lezac-level3-results-regression-20261006-t1')
OUT = Path('/dev/shm/lezac-results-handoff-original-20261006-t1')
CONTROL = Path(__file__).parent
sys.path.insert(0, str(SOURCE / 'tools'))
import level1_fidelity as fidelity
import level1_handoff as handoff

reels = handoff.load(OUT / 'level3-results.jsonl.gz')
entry = handoff.load(OUT / 'level4-handoff.jsonl.gz')
states = [reels[0]['baseline']] + [row['state'] for row in reels[1:-1]]
states += [entry[0]['baseline'], entry[0]['intro']]
states += [row[field] for row in entry[1:-1] for field in ('pre', 'rendered', 'post')]
journal = fidelity.strict_json((OUT / 'results-handoff-ds-journal.json').read_text())
assert len(states) == len(journal['records']) == 148
differences = []
with gzip.open(OUT / 'results-handoff-ds.bin.gz', 'rb') as stream:
    for index, (state, record) in enumerate(zip(states, journal['records'])):
        raw = stream.read(65536)
        assert len(raw) == 65536 and hashlib.sha256(raw).hexdigest() == record['sha256']
        fields = [('globals', 0x79a0, bytes.fromhex(state['globals']))]
        for player_index, player in enumerate(state['players'], 1):
            offset = 0x1b62 + player_index * 38
            fields.append((f'player{player_index}_raw', offset, bytes.fromhex(player['raw'])))
            visual = 0xc21e + raw[offset + 1] * 8
            fields.append((f'player{player_index}_visual', visual, bytes.fromhex(player['visual'])))
        for name, offset, expected in fields:
            actual = raw[offset:offset + len(expected)]
            for relative, (a, b) in enumerate(zip(actual, expected)):
                if a != b:
                    differences.append(dict(record=index, role=record['role'], field=name,
                                            ds_offset=offset + relative, raw=a, projected_native=b))
    assert not stream.read(1)
report = dict(status='native_snapshot_coherence_audited', boundaries=148,
              globals_bytes_per_boundary=90, differing_byte_observations=len(differences),
              differences=differences, normalized_bytes=0, cpp_full_state_parity_claim=False,
              source_sha256=fidelity.sha256(Path(__file__)), raw_sha256=fidelity.sha256(OUT / 'results-handoff-ds.bin.gz'))
target = CONTROL / 'native-coherence-audit.json'
assert not target.exists()
target.write_text(json.dumps(report, sort_keys=True) + '\n', encoding='ascii')
print(json.dumps({k: v for k, v in report.items() if k != 'differences'}), flush=True)
