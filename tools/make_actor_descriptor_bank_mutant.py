"""Restore the reviewed wrong-bank lookup in the actual production App."""
import argparse
import hashlib
import json
from pathlib import Path

SELECTION = '        const auto& bank = levelIndex_ == 6 ? altSprites_ : sprites_;\n'


def function(source):
    start = source.index('    lezac::gameplay::ActorSlots::Descriptor actorSpriteDescriptor(')
    end = source.index('\n    void adoptUnorderedActors(', start)
    return start, end, source[start:end]


def generate(source):
    start, end, body = function(source)
    if body.count(SELECTION) != 1:
        raise ValueError('unexpected production descriptor bank layout')
    body = body.replace(SELECTION, '        const auto& bank = sprites_;\n', 1)
    return source[:start] + body + source[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    mutant = generate(raw.decode('utf-8').replace('\r\n', '\n')).encode('utf-8')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(mutant)
    args.out.with_suffix('.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(raw).hexdigest(),
        mutant_sha256=hashlib.sha256(mutant).hexdigest(), old_normal_bank=True,
        unchanged_diagnostic=True), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
