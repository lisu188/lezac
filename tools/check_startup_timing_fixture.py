"""Check the frozen original startup oracle without requiring Unicorn in CI."""
import hashlib
import json
from pathlib import Path
import struct


def check(root):
    fixture = root / 'tests/fixtures/startup_timing'
    sha = lambda data: hashlib.sha256(data).hexdigest()
    manifest_raw = (fixture / 'manifest.json').read_bytes()
    assert sha(manifest_raw) == '6ba6bdbc8dcb514cd6d1541237aea893129304207fa91175186c70a5ee76d0d2'
    manifest = json.loads(manifest_raw)
    gate = (fixture / 'gate-bits.bin').read_bytes()
    words = (fixture / 'accepted-words.bin').read_bytes()
    assert manifest['schema'] == 1
    assert manifest['original_executable_sha256'] == sha((root / 'LEZAC.EXE').read_bytes())
    assert manifest['original_executable_sha256'] == '7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec'
    assert manifest['producer_sha256'] == sha((root / 'tools/capture_original_startup_timing.py').read_bytes())
    assert manifest['gate_bits_sha256'] == sha(gate) == 'f8f08bb4e30fac392aef7858ea9acac15b0c3d36b46c40bec73466414907ea2b'
    assert manifest['accepted_words_sha256'] == sha(words) == '5b0219a2f7787988fb313178312e41b4e65a81dd9296a5e2c9889ac5ec229f2e'
    assert manifest['full_records_sha256'] == '6d0377dff5751bfee4284270b1d69771282a955437bbdabdc4b8d5d4db6a8bc1'
    assert manifest['code_bytes_verified'] == 43552
    assert [manifest[k] for k in ('entry_ip', 'arithmetic_entry_ip', 'retry_ip', 'function_end_exclusive')] == [0x247f, 0x24f8, 0x2495, 0x2585]
    assert manifest['complete_function_executed'] is True
    assert manifest['scripted_dos_time_service'] is True
    assert manifest['original_calls_stubbed'] is False
    assert manifest['instruction_patches'] == 0
    assert manifest['crt_calibration_word_seeded'] == 544
    assert manifest['com1_base_byte_seeded'] == 248
    assert manifest['unicorn'] == '2.1.4'
    for key in ('natural_startup_claim', 'frame_timing_claim', 'whole_game_parity'):
        assert manifest[key] is False
    assert manifest['elapsed_inputs'] == 65536 and manifest['accepted_inputs'] == 299
    assert len(gate) == 8192 and len(words) == 299 * 6
    assert [raw for raw in range(65536) if gate[raw // 8] & (1 << (raw % 8))] == list(range(1, 300))
    table = [struct.unpack_from('<3H', words, index * 6) for index in range(299)]
    assert table[97] == (82, 16, 2) and table[98] == (81, 16, 2)
    assert table[127] == (63, 13, 2)
    cases = manifest['cases']
    assert len(cases) == 10 and len({case['name'] for case in cases}) == 10
    assert sum(len(case['events']) for case in cases) == 55
    for case in cases:
        samples = iter(case['samples'])
        expected = [dict(kind='crt_delay', argument=500)]
        for first, second in zip(samples, samples):
            expected.extend([dict(kind='dos_time', **first), dict(kind='crt_delay', argument=1000),
                             dict(kind='dos_time', **second)])
        assert case['events'] == expected, case['name']
        first, second = case['samples'][-2:]
        elapsed = ((second['minute'] - first['minute']) * 6000 +
                   (second['second'] - first['second']) * 100 +
                   second['hundredth'] - first['hundredth']) & 65535
        assert 1 <= elapsed < 300
        assert tuple(case[key] for key in ('character_delay', 'auxiliary_delay', 'minimum_word')) == table[elapsed - 1]
    print('startup_timing_fixture_contract=ok inputs=65536 accepted=299 functions=10 original_calls_stubbed=0 natural_startup=0')


if __name__ == '__main__':
    check(Path(__file__).resolve().parents[1])
