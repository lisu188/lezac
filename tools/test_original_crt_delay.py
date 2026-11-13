"""Frozen CRT oracle contract; CI needs only the Python standard library."""
import copy
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/crt_delay'
SHA = lambda raw: hashlib.sha256(raw).hexdigest()
EXE_SHA = '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
FLAGS = dict(original_calls_stubbed=False, inputs_seeded=True,
    calibration_and_com1_reads_scripted=True, data_input_writes_declared=True,
    natural_clock_claim=False, cycle_clock_claim=False, full_game_parity=False,
    undefined_logic_auxiliary_flag_unclaimed=True)
REGISTERS = {'ax', 'bx', 'cx', 'dx', 'di', 'bp', 'cs', 'ds', 'es', 'ss', 'sp', 'ip', 'flags'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def exact(value, expected, message):
    require(type(value) is type(expected) and value == expected, message)


def validate_observation(doc, provider, producer_sha):
    for key, value in FLAGS.items():
        exact(doc.get(key), value, 'Contradictory CRT scope: ' + key)
    for key, value in dict(entry_cs=0x184a, entry_ip=0x29c, original_caller_entry_ip=0x79df,
        original_caller_return_ip=0x79e8, original_caller_instructions_executed=2,
        original_code_bytes_verified=43552, original_instruction_patches=0,
        hardware_interrupts_injected=0, stack_window_address=0x8fdfe, stack_window_bytes=8).items():
        exact(doc.get(key), value, 'CRT profile differs: ' + key)
    exact(doc.get('unicorn'), '2.1.4', 'Unicorn version differs')
    exact(doc.get('original_executable_sha256'), EXE_SHA, 'Original executable differs')
    exact(doc.get('producer_sha256'), producer_sha, 'Producer differs')
    exact(doc.get('routine_sha256'), '5b41023c828ecea8d4fc62bad88b831733dd83443d69cfc4c7f57bcb49baadd9', 'CRT code differs')
    exact(doc.get('input_provider'), provider, 'Input provider differs')
    exact(doc.get('read_hook_ranges'), [[0x400, 0x400], [0x22988, 0x22988]] if provider == 'memory' else [],
          'Read hooks include unexpected memory')
    cases = doc['cases']
    require(type(cases) is list and len(cases) == 17 and len({case['name'] for case in cases}) == 17, 'Case domain differs')
    total_snapshots = 0
    for case in cases:
        require(type(case['argument']) is int and 0 <= case['argument'] <= 65535, 'Argument differs')
        for key, maximum in [('calibration_inputs', 65535), ('com1_inputs', 255)]:
            values = case[key]
            require(type(values) is list and values and all(type(item.get('value')) is int and
                    0 <= item['value'] <= maximum for item in values), 'Input script differs')
        snapshots = case['snapshots']
        require(type(snapshots) is list and snapshots and snapshots[0]['dispatch'] == 0, 'Entry snapshot differs')
        prior = -1
        for snapshot in snapshots:
            for key in ('dispatch', 'calibration_reads', 'com1_reads'):
                require(type(snapshot[key]) is int and snapshot[key] >= 0, 'Snapshot counter differs')
            require(snapshot['dispatch'] > prior, 'Snapshot order differs')
            prior = snapshot['dispatch']
            registers = snapshot['registers']
            require(set(registers) == REGISTERS and all(type(value) is int and
                    0 <= value <= (0xffffffff if key == 'flags' else 65535) for key, value in registers.items()),
                    'Register range differs')
            require(type(snapshot['defined_flags_hex']) is str and
                    snapshot['defined_flags_hex'] in ('ffffffff', 'ffffffef'), 'Undefined flag scope differs')
            require(type(snapshot['stack_window']) is str and len(bytes.fromhex(snapshot['stack_window'])) == 8,
                    'Stack window differs')
        require((snapshots[0]['registers']['cs'], snapshots[0]['registers']['ip'], snapshots[0]['registers']['sp']) ==
                (0x184a, 0x29c, 0xfe00), 'CRT entry tuple differs')
        last = snapshots[-1]
        require((last['registers']['cs'], last['registers']['ip'], last['registers']['sp']) ==
                (0x1000, 0x79e8, 0xfe06), 'Original return tuple differs')
        for key, snapshot_key in [('dispatches', 'dispatch'), ('calibration_reads', 'calibration_reads'), ('com1_reads', 'com1_reads')]:
            exact(case.get(key), last[snapshot_key], 'Terminal work differs')
        total_snapshots += len(snapshots)
    require(total_snapshots == 758 and sum(case['dispatches'] for case in cases) == 13273201, 'Original work coverage differs')


def validate_pair(first, second, producer_sha):
    validate_observation(first, 'memory', producer_sha)
    validate_observation(second, 'instruction', producer_sha)
    require(first['cases'] == second['cases'], 'Independent input providers disagree')


def check_fixture():
    raw = (FIXTURE / 'manifest.json').read_bytes()
    exact(SHA(raw), '9ca083fbda39629af14f48fb0b3aa5fe12b2caca25f467caef674d7390cd41b6', 'Frozen manifest differs')
    manifest = json.loads(raw)
    for key, value in dict(schema=1, cases=17, snapshots=758, original_dispatches=13273201,
                          identical_input_provider_results=True, natural_clock_claim=False,
                          cycle_clock_claim=False, full_game_parity=False).items():
        exact(manifest.get(key), value, 'Fixture scope differs: ' + key)
    exact(SHA((ROOT / 'LEZAC.EXE').read_bytes()), EXE_SHA, 'Installed original differs')
    producer_sha = SHA((ROOT / 'tools/capture_original_crt_delay.py').read_bytes())
    exact(manifest.get('original_executable_sha256'), EXE_SHA, 'Manifest original differs')
    exact(manifest.get('producer_sha256'), producer_sha, 'Manifest producer differs')
    exact([item['name'] for item in manifest['files']], ['instruction-provider.json', 'memory-provider.json'], 'Fixture file domain differs')
    for item in manifest['files']:
        contents = (FIXTURE / item['name']).read_bytes()
        exact(len(contents), item['bytes'], 'Fixture size differs')
        exact(SHA(contents), item['sha256'], 'Fixture bytes differ')
    first = json.loads((FIXTURE / 'memory-provider.json').read_text())
    second = json.loads((FIXTURE / 'instruction-provider.json').read_text())
    validate_pair(first, second, producer_sha)
    print('crt_delay_fixture_contract=ok cases=17 snapshots=758 providers=2 original_dispatches=13273201 natural_clock=0 cycle_clock=0')


class OriginalCrtDelayTests(unittest.TestCase):
    def setUp(self):
        self.first = json.loads((FIXTURE / 'memory-provider.json').read_text())
        self.second = json.loads((FIXTURE / 'instruction-provider.json').read_text())
        self.sha = SHA((ROOT / 'tools/capture_original_crt_delay.py').read_bytes())

    def test_frozen_contract(self):
        check_fixture()

    def test_contradictory_typed_scope_rejected(self):
        for key, expected in FLAGS.items():
            for value in [not expected, 0, 1, None]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_observation(dict(self.first, **{key: value}), 'memory', self.sha)
            missing = dict(self.first)
            del missing[key]
            with self.subTest(missing=key), self.assertRaises(ValueError):
                validate_observation(missing, 'memory', self.sha)

    def test_profile_and_read_hook_rejections(self):
        for key, value in [('original_instruction_patches', False), ('hardware_interrupts_injected', 1),
                           ('original_code_bytes_verified', 0), ('original_caller_instructions_executed', True),
                           ('input_provider', 'instruction'), ('read_hook_ranges', [[1, 0xfffff]]),
                           ('producer_sha256', '0' * 64), ('routine_sha256', '0' * 64)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_observation(dict(self.first, **{key: value}), 'memory', self.sha)

    def test_snapshot_rejections(self):
        controls = [('dispatch', 1), ('calibration_reads', False), ('defined_flags_hex', '00000000'),
                    ('stack_window', '00')]
        for key, value in controls:
            changed = copy.deepcopy(self.first)
            changed['cases'][0]['snapshots'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_observation(changed, 'memory', self.sha)
        changed = copy.deepcopy(self.first)
        changed['cases'][0]['snapshots'][-1]['registers']['ip'] = 0x2ba
        with self.assertRaises(ValueError):
            validate_observation(changed, 'memory', self.sha)

    def test_provider_disagreement_rejected(self):
        changed = copy.deepcopy(self.second)
        changed['cases'][0]['snapshots'][0]['registers']['ax'] ^= 1
        with self.assertRaisesRegex(ValueError, 'disagree'):
            validate_pair(self.first, changed, self.sha)


if __name__ == '__main__':
    unittest.main()
