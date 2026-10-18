from __future__ import annotations

import argparse
import hashlib
import json
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / 'src/LIVELS.SCH.json'
CHECKPOINT = ROOT / 'tests/fixtures/natural_level4_support_column/guard-input.json'
MANIFEST = ROOT / 'docs/recovery/evidence/natural_level4_support_column_20261008/manifest.json'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def physical_damage_word(word: int) -> bool:
    return 0 < word < 0x4000


def source_words(level: dict) -> list[int]:
    width, height = level['width'], level['height']
    rows = level['word_rows_hex']
    require(width > 0 and height > 0 and len(rows) == height, 'invalid shipped map dimensions')
    words = []
    for row in rows:
        values = row.split()
        require(len(values) == width, 'invalid shipped word row')
        decoded = [int(value, 16) for value in values]
        require(all(0 <= value <= 0xffff for value in decoded), 'invalid shipped word value')
        words.extend(decoded)
    return words


def snapshot_words(checkpoint: dict, count: int) -> list[int]:
    raw = bytes.fromhex(checkpoint['words_hex'])
    require(len(raw) == count * 2, 'invalid checkpoint word-plane extent')
    return list(struct.unpack(f'<{count}H', raw))


def connected_groups(words: list[int], width: int, height: int) -> list[dict]:
    require(len(words) == width * height, 'invalid physical map dimensions')
    remaining = {index for index, word in enumerate(words) if physical_damage_word(word)}
    groups = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        pending = [start]
        cells = []
        while pending:
            index = pending.pop()
            x, y = index % width, index // width
            cells.append((x, y))
            neighbors = []
            if x:
                neighbors.append(index - 1)
            if x + 1 < width:
                neighbors.append(index + 1)
            if y:
                neighbors.append(index - width)
            if y + 1 < height:
                neighbors.append(index + width)
            for neighbor in neighbors:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    pending.append(neighbor)
        xs, ys = zip(*cells)
        groups.append(dict(cells=len(cells), bounds=dict(min_x=min(xs), max_x=max(xs),
                                                      min_y=min(ys), max_y=max(ys))))
    groups.sort(key=lambda group: (-group['cells'], group['bounds']['min_y'], group['bounds']['min_x']))
    return groups


def analyze(bank: dict, checkpoint: dict) -> dict:
    require(bank['level_count'] == len(bank['levels']), 'invalid shipped level count')
    level_number = checkpoint['level']
    require(isinstance(level_number, int) and 1 <= level_number <= len(bank['levels']),
            'invalid checkpoint level')
    level = bank['levels'][level_number - 1]
    width, height = level['width'], level['height']
    original = source_words(level)
    current = snapshot_words(checkpoint, width * height)
    denominator = sum(map(physical_damage_word, original))
    require(denominator == level['fieldB'] == level['startingDestructibleTiles'],
            'shipped physical destruction denominator mismatch')
    objectives, destroyed = checkpoint['progress']
    require(isinstance(objectives, int) and isinstance(destroyed, int) and
            0 <= objectives <= 0xffff and 0 <= destroyed <= denominator,
            'invalid checkpoint progress')
    remaining = sum(map(physical_damage_word, current))
    require(denominator - remaining == destroyed,
            'checkpoint destruction differs from physical map words')
    percent = level['requiredDestruction']
    require(isinstance(percent, int) and 0 <= percent <= 100, 'invalid destruction threshold')
    required = (denominator * percent + 99) // 100
    groups = connected_groups(current, width, height)
    require(sum(group['cells'] for group in groups) == remaining, 'frontier coverage differs')
    return dict(level=level_number, source='cpp_guard_fixture_not_original_capture',
                checkpoint_logic_tick=checkpoint.get('logic_tick'),
                dimensions=[width, height], required_objectives=level['requiredBonus'],
                collected_objectives=objectives, initial_destructible=denominator,
                destroyed=destroyed, still_destructible=remaining,
                required_destroyed=required, additional_destroyed_needed=max(0, required - destroyed),
                objective_gate_met=objectives >= level['requiredBonus'],
                destruction_gate_met=destroyed >= required,
                level_completion_proven=False, groups=groups)


def read_current() -> tuple[dict, dict]:
    fixture_bytes = CHECKPOINT.read_bytes()
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    require(hashlib.sha256(fixture_bytes).hexdigest() == manifest['fixture_pins']['guard-input.json'],
            'untrusted committed checkpoint')
    scope = manifest['guard_input_source']
    require(scope['kind'] == 'cpp_typed_mutation_stimulus_only' and
            scope['phase'] == 'post_update' and scope['tick'] == 11740 and
            manifest['level4_complete'] is False and
            manifest['reference_header']['level4_completion_claim'] is False,
            'checkpoint evidence scope differs')
    return json.loads(BANK.read_text(encoding='utf-8')), json.loads(fixture_bytes)


class FrontierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bank, self.checkpoint = read_current()

    def test_committed_frontier(self) -> None:
        result = analyze(self.bank, self.checkpoint)
        self.assertEqual((result['level'], result['initial_destructible'], result['destroyed'],
                          result['still_destructible'], result['required_destroyed'],
                          result['additional_destroyed_needed']), (4, 435, 244, 191, 305, 61))
        self.assertEqual([item['cells'] for item in result['groups']], [76, 65, 9, 9, 6, 6, 6, 6, 4, 4])
        self.assertTrue(result['objective_gate_met'])
        self.assertFalse(result['destruction_gate_met'])
        self.assertFalse(result['level_completion_proven'])

    def test_progress_mutation_rejected(self) -> None:
        changed = {**self.checkpoint, 'progress': [3, 245]}
        with self.assertRaisesRegex(ValueError, 'checkpoint destruction differs'):
            analyze(self.bank, changed)

    def test_word_plane_mutation_rejected(self) -> None:
        changed = {**self.checkpoint, 'words_hex': self.checkpoint['words_hex'][:-4]}
        with self.assertRaisesRegex(ValueError, 'word-plane extent'):
            analyze(self.bank, changed)

    def test_denominator_mutation_rejected(self) -> None:
        bank = {**self.bank, 'levels': list(self.bank['levels'])}
        bank['levels'][3] = {**bank['levels'][3], 'fieldB': 436}
        with self.assertRaisesRegex(ValueError, 'physical destruction denominator'):
            analyze(bank, self.checkpoint)

    def test_word_boundary_domain(self) -> None:
        self.assertEqual([physical_damage_word(word) for word in (0, 1, 0x3fff, 0x4000, 0xffff)],
                         [False, True, True, False, False])

    def test_no_horizontal_row_wrap(self) -> None:
        groups = connected_groups([0, 0, 1, 1, 0, 0], 3, 2)
        self.assertEqual([group['cells'] for group in groups], [1, 1])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--bank', type=Path, default=BANK)
    parser.add_argument('--checkpoint', type=Path, default=CHECKPOINT)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        result = unittest.TextTestRunner(verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(FrontierTests))
        if not result.wasSuccessful():
            raise SystemExit(1)
        print('campaign_destruction_frontier=ok level=4 remaining=191 additional=61 clusters=10 mutants_rejected=5')
        return
    if args.checkpoint == CHECKPOINT and args.bank == BANK:
        bank, checkpoint = read_current()
    else:
        bank = json.loads(args.bank.read_text(encoding='utf-8'))
        checkpoint = json.loads(args.checkpoint.read_text(encoding='utf-8'))
    print(json.dumps(analyze(bank, checkpoint), sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
