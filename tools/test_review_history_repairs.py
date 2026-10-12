#!/usr/bin/env python3
"""Source-contract regressions for historical-review repairs."""
from __future__ import annotations

import ast
from pathlib import Path
import re
import unittest

import check_behavior4_runtime_oracle_fixtures as behavior4
import check_sound_callsite_map as sound_map
from source_guardrails import source_text

ROOT = Path(__file__).resolve().parents[1]
PROBES = {
    'walker-gravity-probe.yml': 'capture_original_walker_gravity.py',
    'behavior4-target-probe.yml': 'capture_original_behavior4_targets.py',
    'shipped-monster-profiles.yml': 'capture_original_shipped_monster_profiles.py',
}


def local_dependencies(entry: str) -> set[str]:
    pending = [entry]
    seen: set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        tree = ast.parse((ROOT / 'tools' / name).read_text(encoding='utf-8'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            else:
                continue
            for module in modules:
                filename = module.split('.')[0] + '.py'
                if (ROOT / 'tools' / filename).is_file() and filename not in seen:
                    pending.append(filename)
    return {'tools/' + name for name in seen}


def probe_paths(text: str) -> set[str]:
    # These workflows intentionally use a literal, indented paths list.
    match = re.search(r'^  pull_request:\n    paths:\n((?:      - [^\n]+\n)+)', text, re.MULTILINE)
    if not match:
        raise ValueError('literal pull_request paths block missing')
    return {line.removeprefix('      - ').strip() for line in match.group(1).splitlines()}


class ReviewHistoryRepairs(unittest.TestCase):
    def test_rendering_exports_sdl_search_directories(self) -> None:
        text = (ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
        self.assertRegex(text, r'(?m)^target_link_directories\(lezac_rendering PUBLIC \$\{SDL2_LIBRARY_DIRS\}\)$')

    def test_support_column_timeout_has_headroom(self) -> None:
        text = (ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
        match = re.search(r'set_tests_properties\(natural_level4_support_column_guard PROPERTIES\s+WORKING_DIRECTORY [^\n]+\s+TIMEOUT (\d+)', text)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 120)

    def test_workflows_cover_local_capture_imports(self) -> None:
        for workflow, entry in PROBES.items():
            with self.subTest(workflow=workflow):
                text = (ROOT / '.github' / 'workflows' / workflow).read_text(encoding='utf-8')
                required = local_dependencies(entry)
                actual = probe_paths(text)
                self.assertFalse(required - actual)
                for dependency in required:
                    with self.subTest(missing_dependency=dependency):
                        mutated = text.replace('      - ' + dependency + '\n', '')
                        self.assertEqual(required - probe_paths(mutated), {dependency})

    def test_duplicate_evidence_records_are_rejected(self) -> None:
        fixture = ROOT / 'tests' / 'fixtures' / 'dosbox' / 'behavior4_runtime_oracle_synthetic.txt'
        self.assertEqual(behavior4.check_parser_rejection_guards(fixture), 45)

    def test_review_gate_is_explicit(self) -> None:
        text = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        for phrase in ('### Code review gate', 'immediately before merging the current head',
                       'Green CI is not a code', 'an empty review history is not approval'):
            self.assertIn(phrase, text)


class DeathSoundOwnership(unittest.TestCase):
    def setUp(self) -> None:
        self.notes = (ROOT / 'docs' / 'GHIDRA_NOTES.md').read_text(encoding='utf-8')
        self.source = ('void enterMonsterDeath() { /* requestMonsterDeathSound(); */ }\n'
                       'void bossDeathChain() { requestMonsterDeathSound(); }\n')

    def test_live_source_and_canonical_notes(self) -> None:
        sound_map.require_death_sound_ownership(source_text(ROOT, ('sound', 'gameplay')), self.notes)

    def test_comments_do_not_request_sound(self) -> None:
        sound_map.require_death_sound_ownership(self.source, self.notes)

    def test_old_callsite_owner_is_rejected(self) -> None:
        notes = self.notes.replace('boss-death chain starting at', 'monster death/reward helper at', 1)
        with self.assertRaisesRegex(RuntimeError, 'boss_death docs owner'):
            sound_map.require_death_sound_ownership(self.source, notes)

    def test_missing_generic_silence_is_rejected(self) -> None:
        notes = self.notes.replace('`1000:74bb..7517` is silent.', '`1000:74bb..7517` requests sound.', 1)
        with self.assertRaisesRegex(RuntimeError, 'generic_corpse docs'):
            sound_map.require_death_sound_ownership(self.source, notes)

    def test_generic_sound_request_is_rejected(self) -> None:
        source = self.source.replace('/* requestMonsterDeathSound(); */', 'requestMonsterDeathSound();')
        with self.assertRaisesRegex(RuntimeError, 'conversion must not request sound'):
            sound_map.require_death_sound_ownership(source, self.notes)

    def test_missing_boss_request_is_rejected(self) -> None:
        source = self.source.replace('void bossDeathChain() { requestMonsterDeathSound(); }',
                                     'void bossDeathChain() { }')
        with self.assertRaisesRegex(RuntimeError, 'boss_death source'):
            sound_map.require_death_sound_ownership(source, self.notes)


if __name__ == '__main__':
    unittest.main()
