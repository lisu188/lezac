"""Stream and validate bounded compressed full-pacing observations."""
import csv
import gzip
import hashlib

MAX_RAW = 384 * 1024**2


def rows(path, metadata):
    digest = hashlib.sha256()
    length = 0
    with gzip.open(path, 'rb') as stream:
        def lines():
            nonlocal length
            for raw in stream:
                length += len(raw)
                if length > MAX_RAW:
                    raise ValueError('Pacing trace expanded beyond its reserve')
                digest.update(raw)
                yield raw.decode('ascii')
        reader = csv.reader(lines())
        header = next(reader)
        if len(header) != len(set(header)) or header[-6:] != ['frame_globals', 'display_globals', 'pacing_globals',
                'devices', 'ticker_overflow', 'tickers']:
            raise ValueError('Pacing trace header differs')
        ended = False
        for values in reader:
            if values == ['end']:
                ended = True
                if next(reader, None) is not None:
                    raise ValueError('Pacing trace continues after its terminal marker')
                break
            if len(values) != len(header):
                raise ValueError('Pacing trace is truncated or capped')
            row = dict(zip(header, values))
            if row['kind'] not in ('identified', 'pacing_enter', 'instruction', 'pacing_return'):
                raise ValueError('Unexpected pacing trace boundary')
            if (int(row['cycle_max']), int(row['id_toggle']), int(row['queue_overflow'])) != (6000, 0x200000, 0):
                raise ValueError('Pacing trace host profile differs')
            if any(len(bytes.fromhex(row[name])) != size for name, size in
                [('stack', 128), ('globals', 10), ('frame_globals', 11), ('display_globals', 5), ('pacing_globals', 9)]):
                raise ValueError('Pacing trace memory scope differs')
            if row['ticker_overflow'] != '0' or len(row['devices'].split(';')) != 31:
                raise ValueError('Device or ticker observation scope differs')
            if any(not value.isdecimal() for value in row['devices'].split(';')):
                raise ValueError('Device observation encoding differs')
            yield row
        if not ended:
            raise ValueError('Missing pacing trace terminal marker')
    metadata.update(trace_end_marker=True, trace_uncompressed_bytes=length,
        trace_uncompressed_sha256=digest.hexdigest())


def inspect_trace(path):
    metadata = {}
    windows = []
    current = None
    identified = False
    for row in rows(path, metadata):
        kind = row['kind']
        if kind == 'identified':
            if identified or current:
                raise ValueError('Pacing identification order differs')
            identified = True
            continue
        if not identified:
            raise ValueError('Pacing trace has no original identification')
        if kind == 'pacing_enter':
            if current or len(windows) >= 2 or int(row['ip']) != 0x7903 or int(row['cs']) != int(row['return_cs']):
                raise ValueError('Pacing window entry differs')
            if len(bytes.fromhex(row['bank'])) != 780:
                raise ValueError('Pacing entry bank differs')
            current = dict(window=int(row['call']), states=0, irq_entries=0, dispatch=int(row['dispatch']) - 1)
            continue
        if current is None or int(row['call']) != current['window'] or int(row['dispatch']) != current['dispatch'] + 1:
            raise ValueError('Pacing window is missing an instruction boundary')
        current['dispatch'] = int(row['dispatch'])
        current['states'] += 1
        current['irq_entries'] += (int(row['cs']), int(row['ip'])) == (0xf000, 0xfea5)
        if kind == 'pacing_return':
            if int(row['ip']) != 0x79e8 or int(row['cs']) != int(row['return_cs']):
                raise ValueError('Pacing window return differs')
            current['target_completed'] = row['target_completed'] == '1'
            if current['target_completed'] != (current['irq_entries'] > 0):
                raise ValueError('Pacing target does not bind an observed timer entry')
            windows.append(current)
            current = None
    if current is not None or not identified:
        raise ValueError('Incomplete pacing observation')
    metadata['pacing_windows'] = windows
    metadata['validated_target_completed'] = any(window['target_completed'] for window in windows)
    return metadata
