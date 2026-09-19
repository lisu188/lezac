#!/usr/bin/env python3
"""Mutation tests for the modular source ownership and recovery guardrails."""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import check_gran_usage_guardrail as gran
import check_port_completion_status as completion
import check_sound_compatibility_hooks as sound
import check_unevidenced_constants as uncertainty
from source_guardrails import (
    check_inventory, diagnostic_source_text, diagnostic_text, function_ranges, ownership,
    source_files, source_text, unqualify_definitions,
)


ROOT = Path(__file__).resolve().parent.parent


class SourceGuardrailTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="lezac-source-guards-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def manifest(self, owners):
        self.write("tools/source_ownership.json", json.dumps({
            "version": 1, "owners": owners,
        }))

    def split_gran(self):
        gran.write_contract_files(self.root)
        gran.write_source(self.root)
        path = self.root / "src/app/app.cpp"
        lines = path.read_text().splitlines(keepends=True)
        ranges = function_ranges("".join(lines), gran.DEBUG_FUNCTIONS + gran.LIVE_FUNCTIONS)
        debug = []
        live = []
        removed = set()
        for name, (start, end) in ranges.items():
            block = "".join(lines[start - 1:end])
            owner = "BossSystem" if name in gran.LIVE_FUNCTIONS else "Diagnostics"
            block = block.replace(f"void {name}(", f"void {owner}::{name}(")
            (live if name in gran.LIVE_FUNCTIONS else debug).append(block)
            removed.update(range(start - 1, end))
        path.write_text("".join(line for index, line in enumerate(lines) if index not in removed))
        self.write("src/gameplay/boss.cpp", "\n".join(live))
        self.write("src/diagnostics/gran.cpp", "\n".join(debug))
        self.manifest({
            "app": {"runtime": ["src/app/app.cpp"]},
            "gameplay": {"runtime": ["src/gameplay/boss.cpp"]},
            "diagnostics": {"diagnostics": ["src/diagnostics/gran.cpp"]},
        })

    def test_qualified_definition_and_brace_literals(self):
        text = ('// void Fake::consumer() {\n'
                'void lezac::BossSystem::consumer(\n int value) const {\n'
                '  const char* s = "}"; /* } */\n'
                '  auto raw = R"tag({}})tag";\n'
                '  if (value) { call(); }\n}\n')
        self.assertEqual(function_ranges(text, ("consumer",)), {"consumer": (2, 7)})
        normalized = unqualify_definitions(text)
        self.assertIn("void consumer(\n", normalized)
        self.assertIn("// void Fake::consumer() {", normalized)
        self.assertIn('auto raw = R"tag({}})tag";', normalized)
        with self.assertRaisesRegex(RuntimeError, "duplicate function"):
            function_ranges(text + "void Other::consumer() {}\n", ("consumer",))
        with self.assertRaisesRegex(RuntimeError, "unterminated function"):
            function_ranges("void Owner::consumer() {\n", ("consumer",))

    def test_inventory_and_manifest_fail_closed(self):
        self.write("src/app/app.cpp", "")
        with self.assertRaises(FileNotFoundError):
            ownership(self.root)
        self.manifest({"app": {"runtime": ["src/app/app.cpp"]}})
        self.assertEqual(check_inventory(self.root), 1)
        self.write("src/app/app-LIS.cpp", "historical copy")
        self.assertEqual(check_inventory(self.root), 1)
        self.write("src/gameplay/hidden.cpp", "void unexpected() {}")
        with self.assertRaisesRegex(RuntimeError, "unmapped production source"):
            check_inventory(self.root)
        self.manifest({"app": {"runtime": ["../outside.cpp"]}})
        with self.assertRaisesRegex(RuntimeError, "invalid source path"):
            ownership(self.root)
        self.manifest({"app": {"runtime": ["src/app/app.cpp", "src/app/app.cpp"]}})
        with self.assertRaisesRegex(RuntimeError, "duplicate source"):
            ownership(self.root)

    def test_roles_and_legacy_override(self):
        self.write("src/gameplay/boss.cpp", "void Boss::spawn() { live(); }")
        self.write("src/diagnostics/boss.cpp", "void Debug::spawn() { copied(); }")
        self.write("src/app/commands.cpp", '"--debug-boss"')
        self.manifest({
            "gameplay": {"runtime": ["src/gameplay/boss.cpp"]},
            "diagnostics": {"diagnostics": ["src/diagnostics/boss.cpp"]},
            "app": {"dispatch": ["src/app/commands.cpp"]},
        })
        self.assertNotIn("copied", source_text(self.root, "gameplay"))
        diagnostic = diagnostic_source_text(self.root / "src/app/app.cpp")
        self.assertIn("copied", diagnostic)
        self.assertIn("--debug-boss", diagnostic)
        self.assertNotIn("live();", diagnostic)
        standalone = self.write("standalone.cpp", "void Debug::only() {}")
        self.assertEqual(diagnostic_source_text(standalone), "void only() {}")

    def test_gran_valid_relocation(self):
        self.split_gran()
        self.assertEqual(gran.check_source(self.root), (13, 2, 9, 1, 1))
        self.assertEqual(check_inventory(self.root), 3)

    def test_gran_deleted_live_consumer(self):
        self.split_gran()
        self.write("src/gameplay/boss.cpp", "")
        with self.assertRaisesRegex(RuntimeError, "missing live consumer"):
            gran.check_source(self.root)

    def test_gran_diagnostic_copy_cannot_replace_runtime(self):
        self.split_gran()
        live = (self.root / "src/gameplay/boss.cpp").read_text()
        diagnostics = self.root / "src/diagnostics/gran.cpp"
        diagnostics.write_text(diagnostics.read_text() + live)
        self.write("src/gameplay/boss.cpp", "")
        with self.assertRaisesRegex(RuntimeError, "missing live consumer"):
            gran.check_source(self.root)

    def test_gran_new_unauthorized_consumer(self):
        self.split_gran()
        path = self.root / "src/gameplay/boss.cpp"
        path.write_text(path.read_text() + "\nvoid Boss::surprise() { use(gran_); }\n")
        with self.assertRaisesRegex(RuntimeError, r"unexpected live GRAN references: src/gameplay/boss.cpp:"):
            gran.check_source(self.root)

    def test_gran_diagnostic_copy_does_not_hide_extra_consumer(self):
        self.split_gran()
        path = self.root / "src/diagnostics/gran.cpp"
        path.write_text(path.read_text() + "\nvoid Debug::surprise() { use(gran_); }\n")
        with self.assertRaisesRegex(RuntimeError, "unexpected live GRAN references"):
            gran.check_source(self.root)

    def test_completion_relocation_and_claim_mutation(self):
        subsystems = [("resources", "--validate")]
        items = ["pending_original_evidence"]
        completion.write_synthetic_tree(self.root, subsystems, items)
        source = completion.synthetic_source(subsystems, items).replace(
            "void debugPortCompletionStatus()", "void Diagnostics::debugPortCompletionStatus()")
        self.write("src/diagnostics/status.cpp", source)
        self.write("src/app/app.cpp", "")
        self.manifest({
            "diagnostics": {"diagnostics": ["src/diagnostics/status.cpp"]},
            "app": {"dispatch": ["src/app/app.cpp"]},
        })
        self.assertEqual(completion.parse_source(self.root), (subsystems, items))
        self.write("src/diagnostics/status.cpp", source.replace("original_fidelity_claim=0", "original_fidelity_claim=1"))
        with self.assertRaisesRegex(RuntimeError, "source:fidelity_claim"):
            completion.parse_source(self.root)

    def prepare_uncertainty(self):
        self.write("src/app/app.cpp", "")
        self.write("src/gameplay/actor.cpp", "// UNRECOVERED @unevidenced:actor_time\n")
        self.write("docs/inventory.md", "- `actor_time` -- Pending original evidence.\n")
        self.manifest({
            "app": {"runtime": ["src/app/app.cpp"]},
            "gameplay": {"runtime": ["src/gameplay/actor.cpp"]},
        })

    def run_uncertainty(self):
        with patch("sys.argv", ["checker", "--source", str(self.root / "src/app/app.cpp"),
                                "--doc", str(self.root / "docs/inventory.md")]):
            with contextlib.redirect_stdout(io.StringIO()):
                return uncertainty.main()

    def test_uncertainty_moved_marker(self):
        self.prepare_uncertainty()
        self.assertEqual(self.run_uncertainty(), 0)

    def test_uncertainty_duplicate_marker_across_files(self):
        self.prepare_uncertainty()
        self.write("src/app/app.cpp", "// INFERRED @unevidenced:actor_time\n")
        with self.assertRaisesRegex(SystemExit, "duplicate @unevidenced tag"):
            self.run_uncertainty()

    def test_uncertainty_removed_and_untagged_markers(self):
        self.prepare_uncertainty()
        self.write("src/gameplay/actor.cpp", "")
        with self.assertRaisesRegex(SystemExit, "entries with no marked site"):
            self.run_uncertainty()
        self.write("src/gameplay/actor.cpp", "// UNRECOVERED timing\n")
        with self.assertRaisesRegex(SystemExit, "no @unevidenced"):
            self.run_uncertainty()

    def test_sound_diagnostic_copy_cannot_replace_runtime(self):
        source = source_text(ROOT, ("sound", "gameplay", "ui"))
        self.write("src/sound/sound.cpp", source)
        # A copied runtime snippet in diagnostics must not satisfy a live check.
        self.write("src/diagnostics/sound.cpp", diagnostic_text(ROOT) + "\n" + source)
        self.manifest({
            owner: {"runtime": ["src/sound/sound.cpp"]}
            for owner in ("sound", "gameplay", "ui")
        } | {
            "diagnostics": {"diagnostics": ["src/diagnostics/sound.cpp"]},
            "app": {"dispatch": ["src/diagnostics/sound.cpp"]},
        })
        sound.check_source(self.root)
        self.write("src/sound/sound.cpp", source.replace(
            "return requestSoundCursor(hook.capturedCursor, hook.capturedPriority);", "return false;"))
        with self.assertRaisesRegex(RuntimeError, "missing snippet"):
            sound.check_source(self.root)


def main() -> int:
    mapped = check_inventory(ROOT)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SourceGuardrailTests)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
    if not result.wasSuccessful():
        print(output.getvalue(), end="")
        return 1
    print(f"source_guardrails_selftest=ok cases={result.testsRun} mapped_sources={mapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
