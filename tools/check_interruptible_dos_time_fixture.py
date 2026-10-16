"""Project exact frozen DOS/timer observations, never arbitrary capture recipes."""
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import struct

import check_dos_time_fixture as dos

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/dos_timer'
MANIFEST_SHA = '1e2f46b00e1edde6d9133f98728ccf9dafb2ce11e9fef11959527c3f243d9a63'
REGISTERS = 'ax bx cx dx si di bp cs ds es ss sp ip'.split()
HEX = {'opcode', 'stack', 'vector_stub', 'globals', 'bank'}
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse(raw, recipe, legacy=False):
    require(0 < len(raw) < 8 * 1024**2 and raw.endswith(b'\nend\n'), 'Trace terminal or cap differs')
    rows = []
    for item in csv.DictReader(raw[:-4].decode('ascii').splitlines()):
        require(None not in item and all(type(v) is str for v in item.values()), 'Malformed row')
        row = {key: value if key == 'kind' else bytes.fromhex(value) if key in HEX else int(value)
               for key, value in item.items()}
        require(row['kind'] in ('identified', 'callback_enter', 'instruction', 'service_before', 'service_after', 'returned'),
                'Diagnostic or unknown row')
        require(all(0 <= row[key] <= 65535 for key in REGISTERS) and 0 <= row['flags'] <= 0xffffffff,
                'Register range differs')
        require(row['cycle_max'] == 6000 and row['id_toggle'] == 0x200000 and
                row['vector_stub'] == dos.STUB and len(row['stack']) == (64 if legacy else 128), 'Profile differs')
        rows.append(row)
    require(rows and rows[0]['kind'] == 'identified', 'Startup identity absent')
    cases = []
    for call in sorted({row['call'] for row in rows if row['kind'] == 'callback_enter'}):
        if legacy and call != 2:
            continue
        group = [row for row in rows if row['call'] == call]
        entry = group[0]
        require(entry['kind'] == 'callback_enter' and group[-1]['kind'] == 'returned', 'Window order differs')
        states = [dict(row) for row in group if row['kind'] in ('instruction', 'returned')]
        require(states[0]['dispatch'] == entry['dispatch'] and
                all(b['dispatch'] == a['dispatch'] + 1 for a, b in zip(states, states[1:])), 'Dispatch gap')
        require(entry['ax'] >> 8 == 0x2c and entry['ip'] == entry['vector_ip'] + 1, 'DOS entry differs')
        require(sum(row['cs'] == entry['vector_cs'] and entry['vector_ip'] <= row['ip'] < entry['vector_ip'] + 15
                    for row in states[:-1]) == 325, 'DOS dispatch domain differs')
        require((states[-1]['cs'], states[-1]['ip'], states[-1]['sp']) ==
                (entry['return_cs'], entry['return_ip'], (entry['sp'] + 6) & 65535), 'DOS return differs')
        deliveries = [index for index, row in enumerate(states) if row['cs'] == 0xf000 and row['ip'] == 0xfea5]
        io = []
        for index, row in enumerate(states):
            row['io_count'] = len(io)
            require(row['defined_flags'] == (0x207fd7 if row['kind'] == 'returned' else 0x700), 'Flag scope differs')
            if legacy:
                row.update(motor=0, drive=0, globals=bytes(10))
            else:
                require(row['stack_base'] == entry['stack_base'] and row['stack_ss'] == entry['ss'] and
                        len(row['globals']) == 10, 'Fixed observed memory scope differs')
            if row['kind'] == 'returned':
                continue
            op = row['opcode']
            if op[0] in (0xe4, 0xe6):
                require(op[1] in ((0x61,) if op[0] == 0xe4 else (0x20, 0x61, 0x42, 0x43)), 'Unknown port')
                io.append((op[0] == 0xe6, op[1], row['ax'] & 255 if op[0] == 0xe6 else states[index + 1]['ax'] & 255))
        require(not legacy or (len(states) == 362 and deliveries == [118]), 'Legacy IRQ domain differs')
        require(legacy or (len(entry['bank']) == 780 and entry['psp'] == recipe['code_segment'] - 16),
                'Initial bank or PSP differs')
        if legacy:
            bank_segment = bank_offset = 0
        else:
            bank_offset, bank_segment = struct.unpack_from('<HH', entry['globals'], 5)
        cases.append(dict(game=recipe['code_segment'], base=entry['vector_ip'], psp=entry['psp'],
            ss=entry['ss'], sp=entry['sp'], stack_base=entry['sp'] if legacy else entry['stack_base'],
            stack_length=64 if legacy else 128, bank_segment=bank_segment, bank_offset=bank_offset,
            bank=b'' if legacy else entry['bank'], vector_ip=0xfbe if legacy else entry['int1c_ip'],
            vector_cs=recipe['code_segment'] if legacy else entry['int1c_cs'], legacy=legacy,
            states=states, deliveries=deliveries, io=io))
    require(len(cases) == (1 if legacy else 10), 'Capture call domain differs')
    return cases


def projection(cases):
    output = bytearray(b'LZDTIR01' + struct.pack('<I', len(cases)))
    for case in cases:
        output.extend(struct.pack('<12HB3I', *[case[key] for key in
            ('game', 'base', 'psp', 'ss', 'sp', 'stack_base', 'stack_length', 'bank_segment', 'bank_offset')],
            len(case['bank']), case['vector_ip'], case['vector_cs'], case['legacy'],
            len(case['states']), len(case['io']), len(case['deliveries'])))
        for index in case['deliveries']:
            output.extend(struct.pack('<I', index))
        output.extend(case['bank'])
        for row in case['states']:
            output.extend(struct.pack('<13H4I2BI', *[row[key] for key in REGISTERS], row['flags'],
                row['defined_flags'], row['bios_ticks'], row['psp_stack'], row['motor'], row['drive'], row['io_count']))
            output.extend(row['stack']); output.extend(row['globals'])
        for event in case['io']:
            output.extend(struct.pack('<BHB', *event))
    return bytes(output)


def read_fixture():
    raw = (FIXTURE / 'manifest.json').read_bytes()
    require(sha(raw) == MANIFEST_SHA, 'Frozen manifest differs')
    manifest = json.loads(raw)
    for item in manifest['files']:
        raw = (FIXTURE / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen observation differs')
    dos.check_fixture()
    legacy = ROOT / 'tests/fixtures/dos_time'
    cases = parse(gzip.decompress((legacy / 'r2-trace.csv.gz').read_bytes()),
                  json.loads((legacy / 'r2-recipe.json').read_text()), legacy=True)
    for run in ('r1', 'r2'):
        recipe = json.loads((FIXTURE / (run + '-recipe.json')).read_text())
        raw = gzip.decompress((FIXTURE / (run + '-trace.csv.gz')).read_bytes())
        require(recipe['passed'] is True and recipe['canonical_assets_unchanged'] is True and
                recipe['child_exit_code'] == 0 and recipe['trace_sha256'] == sha(raw) and
                recipe['trace_bytes'] == len(raw), 'Failed or unbound capture')
        require(recipe['producer_sha256'] == sha((ROOT / 'tools/dos_timer_probe/capture.py').read_bytes()) and
                recipe['host_build']['probe_sha256'] == sha((ROOT / 'tools/dos_timer_probe/lezac_work_probe.h').read_bytes()) and
                recipe['host_build']['patch_sha256'] == sha((ROOT / 'tools/dos_timer_probe/dos_time_hook.patch').read_bytes()) and
                recipe['capture_contract_sha256'] == sha((ROOT / 'tools/original_capture_contract.py').read_bytes()),
                'Published producer or observer differs')
        cases.extend(parse(raw, recipe))
    require(len(cases) == 21 and sum(len(case['states']) for case in cases) == 6882, 'Coverage differs')
    print('interruptible_dos_time_fixture=ok cases=21 states=6882 legacy_partial_irq_windows=1 fresh_full_memory_windows=20')
    return cases


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', type=Path)
    args = parser.parse_args()
    cases = read_fixture()
    if args.projection:
        args.projection.write_bytes(projection(cases))
