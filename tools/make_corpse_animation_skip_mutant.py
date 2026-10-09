"""Generate the old production prologue layout, retaining the new App diagnostic."""
import argparse
import hashlib
import json
from pathlib import Path

PROLOGUE = '''            // 1000:6078..615A precedes behavior dispatch, including corpses.
            const bool animationAdvanced = lezac::gameplay::advanceMonsterAnimation(monster);
            if (debugMonsterAnimationObserver_) debugMonsterAnimationObserver_(monster, animationAdvanced);
'''
ANCHOR = '            const int damageRow = monster.y >> 3;\n'


def generate(source):
    start = source.index('    void updateMonsters(')
    end = source.index('\n    void ', start + 1)
    body = source[start:end]
    if body.count(PROLOGUE) != 1 or body.count(ANCHOR) != 1:
        raise ValueError('unexpected production prologue layout')
    if not body.index(PROLOGUE) < body.index('if (monster.behavior == 2)') < body.index(ANCHOR):
        raise ValueError('source does not contain the repaired ordering')
    old = body.replace(PROLOGUE, '').replace(ANCHOR, ANCHOR + PROLOGUE)
    return source[:start] + old + source[end:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raw = args.source.read_bytes()
    text = raw.decode('utf-8').replace('\r\n', '\n')
    mutant = generate(text).encode('utf-8')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(mutant)
    args.out.with_suffix('.json').write_text(json.dumps(dict(
        source_sha256=hashlib.sha256(raw).hexdigest(),
        mutant_sha256=hashlib.sha256(mutant).hexdigest(),
        production_change='move shared animation after corpse early return',
        diagnostic_unchanged=True), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
