"""Pack the retained eleven-image natural Escape/new-game observation."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

REPORT_SHA = '7ae99141afa9e21b4312e102cee8dc41785412b961395345f59807434b60dbd5'
PRODUCER_SHA = '0184c012ff9fa5003ee7777e3faffea7ec252e795bb24d82b757065827b4039f'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report_raw = (args.capture / 'report.json').read_bytes()
    report = json.loads(report_raw)
    if sha(report_raw) != REPORT_SHA or sha((args.capture / 'producer.py').read_bytes()) != PRODUCER_SHA:
        raise RuntimeError('original observation identity changed')
    if not report['passed'] or len(report['samples']) != 11:
        raise RuntimeError('original capture incomplete')
    raw = bytearray(b'LZAM0001' + struct.pack('<I', 11))
    for sample in report['samples']:
        packed = (args.capture / sample['ram_file']).read_bytes()
        ram = gzip.decompress(packed)
        if sha(packed) != sample['compressed_ram_sha256'] or len(ram) != 1048576 or sha(ram) != sample['raw_ram_sha256']:
            raise RuntimeError('original RAM checksum mismatch')
        raw.extend(ram)
    output = io.BytesIO()
    with gzip.GzipFile(filename='', fileobj=output, mode='wb', compresslevel=9, mtime=0) as stream:
        stream.write(raw)
    packed = output.getvalue()
    metadata = dict(format='lezac-abort-map-observation-v1', original_report_sha256=REPORT_SHA,
        producer_sha256=PRODUCER_SHA, binary_sha256=sha(packed),
        levels_sha256=sha((args.capture / 'run/LIVELS.SCH').read_bytes()),
        capture=report, frame_aligned=False, whole_game_complete=False)
    target = args.out.with_suffix('').with_suffix('.json')
    if args.out.exists() or target.exists():
        raise RuntimeError('fixture output already exists')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(packed)
    target.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(bytes=len(packed), binary_sha256=sha(packed), metadata_sha256=sha(target.read_bytes()))))


if __name__ == '__main__':
    main()
