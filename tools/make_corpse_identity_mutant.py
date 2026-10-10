"""Generate the single deliberately broken App used by the identity regression."""
import argparse
import hashlib
import json
from pathlib import Path

ANCHOR = b"            // Reuse the corpse's identity; this conversion is not an allocation.\n            BonusDrop reward;\n"


def generate(source, output):
    if source.resolve() == output.resolve() or (output.exists() and source.samefile(output)):
        raise ValueError('mutation output must not replace the production source')
    raw = source.read_bytes()
    normalized = raw.replace(b'\r\n', b'\n')
    if normalized.count(ANCHOR) != 1:
        raise ValueError('expected exactly one corpse conversion anchor')
    mutated = normalized.replace(ANCHOR, ANCHOR + b'            (void)claimActorOrder();\n', 1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(mutated)
    manifest = dict(source=str(source.resolve()), source_sha256=hashlib.sha256(raw).hexdigest(),
                    mutated_source_sha256=hashlib.sha256(mutated).hexdigest(),
                    mutation='one unused claimActorOrder in corpse-to-reward conversion',
                    replacements=1, production_source_modified=False)
    output.with_suffix(output.suffix + '.manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.source.resolve() == args.out.resolve():
        parser.error('mutation output must not replace the production source')
    print(json.dumps(generate(args.source, args.out)), flush=True)


if __name__ == '__main__':
    main()
