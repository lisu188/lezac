import tempfile
import unittest
import json
from pathlib import Path

import check_gran_usage_guardrail as guard
from gameplay_source import gameplay_source_text
from source_guardrails import function_ranges


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'src/gameplay/game_session.hpp',
    'src/gameplay/gameplay_operations.hpp',
    'src/diagnostics/gameplay/gameplay_replay.hpp',
)


class GameplayOwnershipTests(unittest.TestCase):
    def test_real_owner_and_detached_replay_contract(self):
        guard.check_session_ownership(ROOT)

    def test_forged_ownership_and_alias_lifetimes_are_rejected(self):
        cases = (
            (FILES[0], 'class GameSession final', 'class GameSession'),
            (FILES[0], 'private detail::GameplayOperations', 'public detail::GameplayOperations'),
            (FILES[2], 'private gameplay::detail::GameplayOperations', 'public gameplay::detail::GameplayOperations'),
            (FILES[0], 'private:\n', 'private:\n    friend class GameplayReplay;\n'),
            (FILES[1], 'protected:\n', 'public:\n'),
            (FILES[1], '    GameplayOperations(const GameplayOperations&) = delete;\n', ''),
            (FILES[1], '    GameplayOperations& operator=(const GameplayOperations&) = delete;\n', ''),
            (FILES[1], '    GameplayOperations(GameplayOperations&&) = delete;\n', ''),
            (FILES[1], '    GameplayOperations& operator=(GameplayOperations&&) = delete;\n', ''),
            (FILES[0], 'public:\n', 'public:\n    GameplayFixture& fixture() { return fixture_; }\n'),
        )
        for relative, before, after in cases:
            with self.subTest(path=relative, mutation=before), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for source in FILES:
                    destination = root / source
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    text = (ROOT / source).read_text()
                    if source == relative:
                        self.assertIn(before, text)
                        text = text.replace(before, after, 1)
                    destination.write_text(text)
                with self.assertRaises(RuntimeError):
                    guard.check_session_ownership(root)


class GameplaySourceTests(unittest.TestCase):
    APP = """class App {
    void tick(int frame, std::array<int, 2> range = {1, 2}) { return withGameplay([&](auto& game) -> decltype(auto) { return game.tick(frame, range); }); }
    void debugProbe() { diagnosticOnly(); }
};
"""
    OPERATIONS = "void GameplayOperations::tick(int frame, std::array<int, 2> range) { actualRuntime(frame); }\n"

    def fixture(self, root, app=None, operations=None, mapped=True):
        for path, text in (("src/app/app.cpp", self.APP if app is None else app),
                           ("src/gameplay/gameplay_operations.hpp", "void tick(int frame);\n"),
                           ("src/gameplay/gameplay_operations.cpp", self.OPERATIONS if operations is None else operations)):
            destination = root / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text)
        manifest = root / "tools/source_ownership.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({"version": 1, "owners": {
            "app": {"runtime": ["src/app/app.cpp"]},
            "gameplay": {"runtime": ["src/gameplay/gameplay_operations.hpp", "src/gameplay/gameplay_operations.cpp"] if mapped else ["src/app/app.cpp"]}}}))

    def test_actual_owner_and_diagnostic_bodies_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            source = gameplay_source_text(root, headers=True)
            first, last = function_ranges(source, ["tick"])["tick"]
            body = "".join(source.splitlines(keepends=True)[first - 1:last])
            self.assertIn("actualRuntime(frame)", body)
            self.assertLess(source.index("actualRuntime(frame)"), source.index("void tick(int frame);"))
            self.assertNotIn("withGameplay", source)
            self.assertIn("diagnosticOnly()", source)
            self.fixture(root, operations=self.OPERATIONS.replace("actualRuntime", "mutatedRuntime"))
            self.assertIn("mutatedRuntime(frame)", gameplay_source_text(root))

    def test_forged_missing_duplicate_or_unowned_boundaries_reject(self):
        cases = (
            (self.APP.replace("void tick(", "void forged("), self.OPERATIONS, True),
            (self.APP.replace("game.tick(frame, range)", "game.forged(frame, range)"), self.OPERATIONS, True),
            (self.APP.replace("return game.tick(frame, range);", "actualRuntime(frame); return game.tick(frame, range);"), self.OPERATIONS, True),
            (self.APP.replace("    void tick", "    // void tick"), self.OPERATIONS, True),
            (self.APP + self.APP, self.OPERATIONS, True),
            (self.APP, self.OPERATIONS + self.OPERATIONS, True),
            (self.APP, self.OPERATIONS.replace("::tick", "::forged"), True),
            (self.APP, self.OPERATIONS, False),
            (self.APP.replace("game.tick(frame, range)", "game.tick(range, frame)"), self.OPERATIONS, True),
            (self.APP.replace("game.tick(frame, range)", "game.tick(0, range)"), self.OPERATIONS, True),
            (self.APP.replace("game.tick(frame, range)", "game.tick(frame)"), self.OPERATIONS, True),
        )
        for app, operations, mapped in cases:
            with self.subTest(app=app, operations=operations, mapped=mapped), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root, app, operations, mapped)
                with self.assertRaises(RuntimeError):
                    gameplay_source_text(root)


if __name__ == '__main__':
    unittest.main()
