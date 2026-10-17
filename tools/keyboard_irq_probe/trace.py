"""Validate complete, contiguous original IRQ1 windows without promoting partial runs."""
import csv
import gzip
import hashlib
import io
from pathlib import Path

REQUIRED_SCANS = {0x2c, 0x2d, 0x32, 0x31, 0x2e, 0x4b, 0x4d, 0x52, 0x48, 0x50,
                  0xac, 0xad, 0xb2, 0xb1, 0xae, 0xcb, 0xcd, 0xd2, 0xc8, 0xd0, 0xe0, 0x12, 0x13, 0x1e}


def inspect_trace(path):
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(32 * 1024**2 + 1)
    assert len(raw) <= 32 * 1024**2 and raw.endswith(b'\nend\n')
    rows = list(csv.DictReader(io.StringIO(raw[:-4].decode('ascii'))))
    windows, active, previous = [], None, None
    for row in rows:
        assert None not in row and all(value is not None for value in row.values())
        kind = row['kind']
        if kind == 'irq_enter':
            assert active is None and int(row['window']) == len(windows) + 1
            assert int(row['cs']) == int(row['game']) and int(row['ip']) == 0x1091
            assert int(row['data']) == int(row['game']) + 0xaa2
            assert int(row['chain_cs']) == int(row['bios15_cs']) == 0xf000
            assert row['chain_stub'] == '50e460b44ff9cd157304fe381000fab020e62058cf'
            assert row['bios15_stub'] == 'fe380e00cf'
            active = dict(window=int(row['window']), scan=int(row['scan']), states=0,
                          entry_dispatch=int(row['dispatch']), frame=int(row['frame']), level=int(row['level']))
            previous = None
        assert active is not None and int(row['window']) == active['window']
        dispatch = int(row['dispatch'])
        assert previous is None or dispatch == previous + 1
        previous = dispatch
        assert len(bytes.fromhex(row['stack'])) == 128 and len(bytes.fromhex(row['bios'])) == 152
        assert len(bytes.fromhex(row['held'])) == 10 and len(bytes.fromhex(row['opcode'])) == 8
        assert len(bytes.fromhex(row['hardware_buffer'])) == 32 and len(row['hardware'].split(';')) == 13
        active['states'] += 1
        if kind == 'irq_return':
            assert int(row['cs']) == int(row['return_cs']) and int(row['ip']) == int(row['return_ip'])
            assert int(row['sp']) == (int(row['initial_sp']) + 6) & 65535
            active['return_dispatch'] = dispatch
            windows.append(active)
            active = None
        else:
            assert kind in ('irq_enter', 'instruction')
    assert active is None and windows
    scans = {item['scan'] for item in windows}
    complete = REQUIRED_SCANS <= scans and sum(item['scan'] == 0x2c for item in windows) >= 2
    return dict(trace_end_marker=True, trace_uncompressed_bytes=len(raw),
                trace_uncompressed_sha256=hashlib.sha256(raw).hexdigest(), irq_windows=windows,
                states=sum(item['states'] for item in windows), observed_scans=sorted(scans),
                validated_target_completed=complete)
