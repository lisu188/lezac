"""Frozen complete INT1C instruction corpus, with standard-library-only CI projection."""
import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/timer_irq'
MANIFEST_SHA = 'dce9735cf75b7229e3afb70e957adba30e9920d65c585eb0ee24854de3ffba16'
REGISTERS = 'ax bx cx dx si di bp cs ds es ss sp ip'.split()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(doc, provider='restricted'):
    for key, value in dict(schema='lezac-original-timer-instructions-v1', unicorn='2.1.4',
        original_executable_sha256='7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec',
        routine_sha256='8505700f9f878bc49cb2ae0a62d2bd2c5ae9ca2849b8581bcc7cf95f6e06aecc',
        original_calls_stubbed=False, original_instruction_patches=0, original_code_bytes_verified=43552,
        inputs_seeded=True, io_ports_scripted=True, bios_wrapper_executed=False,
        memory_read_provider=provider, stack_reads_hooked=False,
        natural_timing=False, whole_game_parity=False).items():
        require(type(doc.get(key)) is type(value) and doc[key] == value, 'Timer scope differs: ' + key)
    require(doc['producer_sha256'] == sha((ROOT / 'tools/capture_original_timer_irq.py').read_bytes()), 'Producer differs')
    cases = doc['cases']
    require(type(cases) is list and len(cases) == 164 and len({case['name'] for case in cases}) == 164, 'Case domain differs')
    instructions = set()
    for case in cases:
        snapshots = case['snapshots']
        require(len(snapshots) == case['dispatches'] + 1 and snapshots[0]['dispatch'] == 0, 'Dispatch count differs')
        for index, state in enumerate(snapshots):
            require(state['dispatch'] == index and type(state['defined']) is int and 0 <= state['defined'] <= 0x7fd7,
                    'State order or flag claim differs')
            require(set(state['registers']) == set(REGISTERS + ['flags']), 'Register domain differs')
            require(all(type(value) is int and 0 <= value <= (0xffffffff if key == 'flags' else 65535)
                        for key, value in state['registers'].items()), 'Register value differs')
            require(len(bytes.fromhex(state['stack'])) == 112 and len(bytes.fromhex(state['globals'])) == 10, 'Memory span differs')
            if index < len(snapshots) - 1:
                instructions.add((state['registers']['cs'], state['registers']['ip']))
        last = snapshots[-1]
        require((last['registers']['cs'], last['registers']['ip'], last['registers']['sp']) == (0x9000, 0x100, 0xfe06),
                'Original IRET return differs')
        require(last['io_count'] == len(case['io']) and last['write_count'] == sum(event['size'] for event in case['writes']) and
                last['read_count'] == sum(event['size'] for event in case['reads']), 'Event coverage differs')
    require(sum(len(case['snapshots']) for case in cases) == 10545 and len(instructions) == 98, 'Instruction coverage differs')


def projection(doc):
    validate(doc)
    output = bytearray(b'LZTIMR01' + struct.pack('<I', len(doc['cases'])))
    for case in doc['cases']:
        states = case['snapshots']
        output.extend(struct.pack('<IIII', len(states), len(case['io']),
            sum(event['size'] for event in case['writes']), sum(event['size'] for event in case['reads'])))
        output.extend(struct.pack('<B', case['port61']))
        for state in states:
            output.extend(struct.pack('<13H5I', *[state['registers'][key] for key in REGISTERS],
                state['registers']['flags'], state['defined'], state['io_count'], state['write_count'], state['read_count']))
            output.extend(bytes.fromhex(state['stack']))
            output.extend(bytes.fromhex(state['globals']))
        for event in case['io']:
            output.extend(struct.pack('<BHB I', event['direction'] == 'out', event['port'], event['value'], event['dispatch']))
        for kind in ('writes', 'reads'):
            for event in case[kind]:
                for index in range(event['size']):
                    output.extend(struct.pack('<IBI', event['address'] + index,
                        (event['value'] >> (index * 8)) & 255, event['dispatch']))
    return bytes(output)


def read_fixture():
    manifest_raw = (FIXTURE / 'manifest.json').read_bytes()
    require(sha(manifest_raw) == MANIFEST_SHA, 'Frozen manifest differs')
    manifest = json.loads(manifest_raw)
    for item in manifest['files']:
        raw = (FIXTURE / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen original differs')
    raw = (FIXTURE / 'original.json.gz').read_bytes()
    doc = json.loads(gzip.decompress(raw))
    validate(doc)
    require(sha((ROOT / 'LEZAC.EXE').read_bytes()) == doc['original_executable_sha256'], 'Installed original differs')
    bank = (ROOT / 'PROEFS.SON').read_bytes()
    require(sha(bank) == 'b5bc702a27ac85554cc76a62fced07567921b07d5c16f2027a62fbc956df701d' and
            sha(bank[2:]) == doc['bank_sha256'], 'Installed sound bank differs')
    control = json.loads(gzip.decompress((FIXTURE / 'no-read-hooks.json.gz').read_bytes()))
    validate(control, 'none')
    def without_reads(cases):
        result = copy.deepcopy(cases)
        for case in result:
            del case['reads']
            for state in case['snapshots']:
                del state['read_count']
        return result
    require(without_reads(doc['cases']) == without_reads(control['cases']), 'Read-hook and no-hook CPU results differ')
    print('timer_irq_fixture=ok cases=164 snapshots=10545 instructions=98 original_calls_stubbed=0 natural_timing=0')
    return doc


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', type=Path)
    args = parser.parse_args()
    doc = read_fixture()
    if args.projection:
        args.projection.write_bytes(projection(doc))
