#!/usr/bin/env python3
"""Keep exported level denominators aligned with the recovered word domain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import export_resources_to_json as exporter


ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_SHA256 = 'd8b553871014108515d6af05b0853de8ccc22e4d3e44d63533ba1167fdc8c7b2'
SHIPPED_COUNTS = [66, 393, 739, 435, 988, 2724, 330]


def exported_levels(data=None):
    captured = []
    with patch.object(exporter, 'write_json', side_effect=lambda name, value: captured.append((name, value))):
        if data is None:
            exporter.export_levels()
        else:
            with patch.object(exporter, 'read', return_value=data) as reader:
                exporter.export_levels()
            reader.assert_called_once_with('LIVELS.SCH')
    if len(captured) != 1 or captured[0][0] != 'LIVELS.SCH.json':
        raise AssertionError('unexpected level export output')
    return captured[0][1]


class LevelExporterTests(unittest.TestCase):
    def test_shipped_counts_match_original_headers(self):
        self.assertEqual(hashlib.sha256((ROOT / 'LIVELS.SCH').read_bytes()).hexdigest(), ORIGINAL_SHA256)
        bank = exported_levels()
        self.assertEqual(bank['level_count'], 7)
        self.assertEqual([level['fieldB'] for level in bank['levels']], SHIPPED_COUNTS)
        self.assertEqual([level['startingDestructibleTiles'] for level in bank['levels']], SHIPPED_COUNTS)

    def test_committed_bank_matches_export(self):
        committed = json.loads((ROOT / 'src/LIVELS.SCH.json').read_text(encoding='utf-8'))
        self.assertEqual(exported_levels(), committed)

    def test_word_boundaries_are_independent_of_glyphs(self):
        # Two eligible words: one has an empty glyph, one the objective glyph.
        tiles = bytes([0, 0, 0x6c, 0x12, 0x31, 0x75, 0x76, 0xff])
        words = struct.pack('<8H', 0, 1, 0x3fff, 0x4000, 0x7fff, 0x8000, 0x8001, 0xffff)
        tile_encoded = b''.join(bytes([0, a, b]) for a, b in zip(tiles[::2], tiles[1::2]))
        word_encoded = b''.join(bytes([0, a, b]) for a, b in zip(words[::2], words[1::2]))
        data = (struct.pack('<HHBHB', 8, 1, 0x6c, 1, 20) + struct.pack('<H', len(tile_encoded)) + tile_encoded +
                struct.pack('<H', len(word_encoded)) + word_encoded + struct.pack('<HH', 0, 2) + b'\0\0\0')
        level = exported_levels(data)['levels'][0]
        self.assertEqual(level['startingDestructibleTiles'], 2)
        self.assertEqual(level['startingDestructibleTiles'], level['fieldB'])
        self.assertEqual(level['startingObjectiveTiles'], 1)
        self.assertEqual(level['tiles_rows_hex'], [exporter.bytes_to_hex_rows(tiles, 8)[0]])
        self.assertEqual(level['word_rows_hex'], ['0000 0001 3fff 4000 7fff 8000 8001 ffff'])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LevelExporterTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)
    print('level_exporter_counts=ok shipped_levels=7 boundary_words=8 committed_bank=1 glyph_independent=1')
