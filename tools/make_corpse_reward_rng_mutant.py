"""Generate equal-draw-count mutations in the actual production reward path."""
import argparse
import hashlib
import json
from pathlib import Path

SOUND = '''        const uint16_t rewardSound =
            static_cast<uint16_t>(0xea74 + randomRangeValue(0, 20));
        requestSoundCursor(rewardSound, 4);
'''
PARTICLES = '        spawnExpiryParticles(monster.x, monster.y + monster.hotspotY);\n'
HELPER = '''#include <cstdlib>
#include <string>
namespace {
bool rewardRngMutation(const char* name) {
    const char* selected = std::getenv("LEZAC_REWARD_RNG_MUTANT");
    return selected && std::string(selected) == name;
}
}
'''


def function(source, name):
    start = source.index('    void ' + name + '(')
    end = source.index('\n    void ', start + 1)
    return start, end, source[start:end]


def once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('unexpected production reward layout: ' + old[:60])
    return source.replace(old, new, 1)


def generate(source):
    if 'bool rewardRngMutation(' in source:
        raise ValueError('source is already mutated')
    start, end, body = function(source, 'finishMonsterDeathReward')
    body = once(body, SOUND, '        if (!rewardRngMutation("sound_after_particles")) {\n' + SOUND + '        }\n')
    body = once(body, PARTICLES, PARTICLES + '        if (rewardRngMutation("sound_after_particles")) {\n' + SOUND + '        }\n')
    source = source[:start] + body + source[end:]
    start, end, body = function(source, 'spawnExpiryParticles')
    first_line = body.index('\n') + 1
    body = body[:first_line] + '        const size_t firstParticle = transientActors_.size();\n' + body[first_line:]
    body = once(body, 'static_cast<int16_t>(vy8), 13,',
                'static_cast<int16_t>(rewardRngMutation("swap_axes") ? vx8 : vy8), 13,')
    body = once(body, 'actor->vx8 = static_cast<int16_t>(vx8);',
                'actor->vx8 = static_cast<int16_t>(rewardRngMutation("swap_axes") ? vy8 : vx8);')
    body = once(body, '\n    }\n', '''
        if (rewardRngMutation("reverse_particles"))
            std::reverse(transientActors_.begin() + static_cast<std::ptrdiff_t>(firstParticle), transientActors_.end());
    }
''')
    return HELPER + source[:start] + body + source[end:]


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
        mutant_sha256=hashlib.sha256(mutant).hexdigest(), controls=3, unchanged_diagnostic=True,
        unchanged_draw_count=True), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
