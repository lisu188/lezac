"""Check the pinned original corpus; this is not an arbitrary-capture acceptance tool."""
import argparse
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

from original_capture_contract import ASSET_PINS

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/dos_time'
MANIFEST_SHA = '95295f7bcedbee8244ddd742206a6a903e5d4755f4f4bd276dca9631cbd6c8a2'
REGISTERS = 'ax bx cx dx si di bp cs ds es ss sp ip'.split()
HEX_FIELDS = {'opcode': 8, 'stack': 64, 'vector_stub': 15}
FIELDS = ('kind dispatch clock call windowed pic_ticks cs ip ds es ss sp ax bx cx dx si di bp '
          'flags defined_flags bios_ticks psp psp_stack return_ip return_cs vector_cs vector_ip '
          'cycle_max id_toggle opcode stack vector_stub').split()
STUB = bytes.fromhex('fbfe382500cfcb51b94001e2fe59cf')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_trace(raw, recipe):
    require(0 < len(raw) < 2 * 1024**2 and raw.endswith(b'\nend\n'), 'Trace cap or terminal marker differs')
    reader = csv.DictReader(io.StringIO(raw[:-4].decode('ascii')))
    require(reader.fieldnames == FIELDS, 'Trace fields differ')
    rows = []
    for item in reader:
        require(set(item) == set(FIELDS) and all(type(value) is str for value in item.values()), 'Malformed row')
        row = dict(kind=item['kind'])
        for key in FIELDS[1:]:
            if key in HEX_FIELDS:
                row[key] = bytes.fromhex(item[key])
                require(row[key].hex() == item[key] and len(row[key]) == HEX_FIELDS[key], 'Hex field differs')
            else:
                row[key] = int(item[key])
                require(str(row[key]) == item[key] and 0 <= row[key] <= (2**64 - 1), 'Counter range differs')
        require(row['kind'] in {'identified', 'callback_enter', 'instruction', 'service_before',
                               'service_after', 'returned'}, 'Diagnostic or unknown row')
        require(all(row[key] <= 65535 for key in REGISTERS + ['psp', 'return_ip', 'return_cs', 'vector_cs', 'vector_ip']),
                'Register range differs')
        require(all(row[key] <= 0xffffffff for key in ('flags', 'defined_flags', 'bios_ticks', 'psp_stack')),
                'Dword range differs')
        require(row['cycle_max'] == 6000 and row['id_toggle'] == 0x200000 and row['vector_stub'] == STUB,
                'Callback profile differs')
        require(row['defined_flags'] == (0x207fd7 if row['kind'] == 'returned' else 0x700), 'Flag claim differs')
        if rows:
            require(row['dispatch'] >= rows[-1]['dispatch'] and row['clock'] >= rows[-1]['clock'], 'Trace order differs')
        rows.append(row)
    require(rows and rows[0]['kind'] == 'identified' and rows[0]['call'] == 0, 'Missing entry identity')
    initial = rows[0]
    require(initial['cs'] == recipe['code_segment'] and recipe['data_segment'] == initial['cs'] + 0xaa2,
            'Original relocation differs')
    startup = recipe['run'] in ('r3', 'r4')
    require(initial['ip'] == (0x7783 if startup else 0x1fc), 'Entry scope differs')
    if startup:
        require(initial['ds'] == initial['cs'] - 16 and initial['ss'] == initial['cs'] + 0x1711 and
                initial['sp'] == 0x4000, 'Startup tuple differs')
    else:
        require(initial['ds'] == recipe['data_segment'], 'Late identity differs')
    calls = []
    cursor = 1
    while cursor < len(rows):
        entry = rows[cursor]
        require(entry['kind'] == 'callback_enter' and entry['call'] == len(calls) + 1, 'Call order differs')
        end = cursor + 1
        while end < len(rows) and rows[end]['call'] == entry['call']:
            end += 1
        group = rows[cursor:end]
        before = [row for row in group if row['kind'] == 'service_before']
        after = [row for row in group if row['kind'] == 'service_after']
        returned = [row for row in group if row['kind'] == 'returned']
        require(len(before) == len(after) == len(returned) == 1, 'Incomplete service')
        before, after, returned = before[0], after[0], returned[0]
        require(group[-1] is returned and before['ip'] == entry['vector_ip'] + 5 and
                after['ip'] == entry['vector_ip'] + 7 and entry['ip'] == entry['vector_ip'] + 1 and
                entry['cs'] == before['cs'] == after['cs'] == entry['vector_cs'], 'Callback boundary differs')
        require(entry['windowed'] == int(entry['call'] <= 8) and entry['ax'] >> 8 == 0x2c, 'Service entry differs')
        require(before['psp'] == initial['cs'] - 16 and
                after['psp_stack'] == ((before['ss'] << 16) | ((before['sp'] - 18) & 65535)), 'PSP save differs')
        for key in REGISTERS + ['flags', 'bios_ticks', 'stack']:
            if key != 'ip':
                require(entry[key] == before[key], 'Callback prelude differs: ' + key)
            if key not in ('ip', 'cx', 'dx'):
                require(before[key] == after[key], 'Atomic service changed unexpected state: ' + key)
        ticks = (5 * before['bios_ticks']) & 0xffffffff
        ticks = ((ticks // 59659) << 16) + (((ticks % 59659) << 16) // 59659)
        seconds = ticks // 100
        require(after['cx'] == (((seconds // 3600) & 255) << 8) | ((seconds % 3600) // 60) and
                after['dx'] == ((seconds % 60) << 8) | (ticks % 100), 'Observed time fields differ')
        require((returned['cs'], returned['ip'], returned['sp']) ==
                (entry['return_cs'], entry['return_ip'], (entry['sp'] + 6) & 65535), 'Return tuple differs')
        instructions = [row for row in group if row['kind'] == 'instruction']
        component = [row for row in instructions if row['cs'] == entry['vector_cs'] and
                     entry['vector_ip'] <= row['ip'] < entry['vector_ip'] + 15]
        external = [row for row in instructions if row not in component]
        require(len(instructions) == (325 + len(external) if entry['windowed'] else 0), 'Instruction window differs')
        if entry['windowed']:
            require([row['ip'] - entry['vector_ip'] for row in component] == [1, 7, 8] + [11] * 320 + [13, 14],
                    'DOS return work differs')
            require(component[0] == dict(entry, kind='instruction'), 'Entry instruction differs')
            require(all(second['dispatch'] == first['dispatch'] + 1 for first, second in
                        zip(instructions, instructions[1:])), 'Dispatch gap inside window')
            require(returned['dispatch'] - entry['dispatch'] == len(instructions), 'Return work differs')
        require(len(external) in (0, 36), 'Unclassified external instructions')
        require((len(external) == 36) == (recipe['run'] == 'r2' and entry['call'] == 2), 'IRQ case domain differs')
        if external:
            require(returned['bios_ticks'] == before['bios_ticks'] + 1 and
                    any(row['cs'] == initial['cs'] for row in external), 'Timer interruption evidence differs')
        calls.append(dict(entry=entry, before=before, after=after, returned=returned,
                          component=component, external=external))
        cursor = end
    require(len(calls) == (9 if startup else 4), 'Observed call domain differs')
    return calls


def projection(corpora):
    cases = [(run, case) for run, calls in corpora for case in calls if case['component']]
    result = bytearray(b'LZDOST01' + struct.pack('<I', len(cases)))
    for run, case in cases:
        entry, before = case['entry'], case['before']
        states = case['component'] + [case['returned']]
        result.extend(struct.pack('<6H3I2H', int(run[1:]), entry['call'], entry['vector_ip'], before['psp'],
            entry['ss'], entry['sp'], entry['id_toggle'], before['bios_ticks'], before['psp_stack'],
            len(states), len(case['external'])))
        result.extend(entry['stack'])
        for index, row in enumerate(states):
            offset = row['sp'] - entry['sp']
            require(offset in (-2, 0, 6), 'Stack projection scope differs')
            length = min(64, 64 - offset)
            result.extend(struct.pack('<13H4IB', *[row[key] for key in REGISTERS], row['flags'],
                row['defined_flags'], row['bios_ticks'], before['psp_stack'] if index == 0 else row['psp_stack'], length))
            result.extend(row['stack'][:length])
    return bytes(result)


def check_fixture():
    manifest_raw = (FIXTURE / 'manifest.json').read_bytes()
    require(sha(manifest_raw) == MANIFEST_SHA, 'Frozen manifest differs')
    manifest = json.loads(manifest_raw)
    for item in manifest['files']:
        raw = (FIXTURE / item['name']).read_bytes()
        require(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'Frozen evidence differs: ' + item['name'])
    corpora = []
    for name, (size, pin) in ASSET_PINS.items():
        raw = (ROOT / name).read_bytes()
        require(len(raw) == size and sha(raw) == pin, 'Installed original asset differs: ' + name)
    for run in ('r2', 'r3', 'r4'):
        raw = gzip.decompress((FIXTURE / (run + '-trace.csv.gz')).read_bytes())
        recipe = json.loads((FIXTURE / (run + '-recipe.json')).read_text())
        require(recipe['trace_bytes'] == len(raw) and recipe['trace_sha256'] == sha(raw), 'Trace binding differs')
        require(recipe['passed'] is True and recipe['child_exit_code'] == 0 and recipe['canonical_assets_unchanged'] is True,
                'Failed capture')
        require(recipe['assets'] == {name: dict(bytes=size, sha256=pin) for name, (size, pin) in ASSET_PINS.items()},
                'Frozen original assets differ')
        if run != 'r2':
            require(recipe['producer_sha256'] == sha((ROOT / 'tools/dos_time_probe/capture.py').read_bytes()) and
                    recipe['host_build']['probe_sha256'] == sha((ROOT / 'tools/dos_time_probe/lezac_work_probe.h').read_bytes()) and
                    recipe['host_build']['patch_sha256'] == sha((ROOT / 'tools/dos_time_probe/dos_time_hook.patch').read_bytes()) and
                    recipe['capture_contract_sha256'] == sha((ROOT / 'tools/original_capture_contract.py').read_bytes()),
                    'Frozen producer or probe differs')
        corpora.append((run, parse_trace(raw, recipe)))
    require(sum(len(case['component']) for _, calls in corpora for case in calls) == 6500, 'Component coverage differs')
    require(sum(len(case['external']) for _, calls in corpora for case in calls) == 36, 'External coverage differs')
    print('dos_time_fixture=ok calls=22 windows=20 component_states=6520 external_irq_instructions=36 irq_replayed=0 app_integrated=0')
    return corpora


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', type=Path)
    args = parser.parse_args()
    corpus = check_fixture()
    if args.projection:
        args.projection.write_bytes(projection(corpus))
