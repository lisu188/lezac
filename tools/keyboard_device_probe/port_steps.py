"""Project observed port-60 scheduling boundaries; later CPU states are comparison targets only."""
import csv
import gzip
import io
import struct


def state(row):
    buffer = bytes.fromhex(row['hardware_buffer'])
    fields = [int(value) for value in row['hardware'].split(';')]
    assert len(buffer) == 32 and len(fields) == 13
    return buffer + struct.pack('<13Q', *fields)


def clock(row):
    return struct.pack('<3q', *[int(row[name]) for name in ('cpu_cycles', 'cpu_left', 'io_delay_removed')])


def pic(row):
    return struct.pack('<5H', *[int(row[name]) for name in
        ('pic_active', 'pic_pending', 'active_lines', 'inservice_lines', 'masked_lines')])


def projection(traces):
    records, reslices = [], 0
    for path in traces:
        raw = gzip.decompress(path.read_bytes())
        assert raw.endswith(b'\nend\n')
        rows = list(csv.DictReader(io.StringIO(raw[:-4].decode('ascii'))))
        for before, after in zip(rows, rows[1:]):
            fields = [int(value) for value in before['hardware'].split(';')]
            if not before['opcode'].startswith('e460') or not fields[0] or fields[11]: continue
            assert before['window'] == after['window'] and int(after['dispatch']) == int(before['dispatch']) + 1
            assert int(after['ip']) == int(before['ip']) + 2 and before['pic_ticks'] == after['pic_ticks']
            assert int(before['cpu_cycles']) > 0 and not (int(before['flags']) & 0x300)
            assert bytes.fromhex(before['hardware_buffer']) == bytes.fromhex(after['hardware_buffer'])
            records.append(struct.pack('<I', int(before['flags'])) + clock(before) +
                struct.pack('<Q', int(before['pic_ticks'])) + pic(before) + state(before) +
                clock(after) + struct.pack('<Q', int(after['pic_ticks'])) + pic(after) + state(after))
            reslices += before['cpu_left'] != after['cpu_left']
    assert len(records) == 20 and reslices == 14
    return b'LZKPORT1' + struct.pack('<I', len(records)) + b''.join(records)
