"""Regress function-scoped sound-clock mutations and fail-closed target checks."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from check_clocked_sound_routing import replace_in_function, require_changed_mutation


APP = """class App {
public:
    void debugLevel1Replay() {
        startClockedSound();
    }
    void runInteractive() {
        startClockedSound();
        // Original startup leaves map pointers empty until play is selected.
        resetLevel(0, false);
    }
};
"""


class RoutingMutationTest(unittest.TestCase):
    def test_targets_each_live_path_independently(self):
        for name in ("debugLevel1Replay", "runInteractive"):
            with self.subTest(function=name):
                changed = replace_in_function(APP, name, "startClockedSound();", ";")
                self.assertNotEqual(changed, APP)
                self.assertEqual(changed.count("startClockedSound();"), 1)
                self.assertIn("void " + name + "() {\n        ;", changed)

    def test_adjacent_menu_initialization_is_preserved(self):
        changed = replace_in_function(APP, "runInteractive", "startClockedSound();", ";")
        self.assertIn("// Original startup leaves map pointers empty until play is selected.\n"
                      "        resetLevel(0, false);", changed)
        self.assertIn("void debugLevel1Replay() {\n        startClockedSound();", changed)

    def test_missing_function_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "missing mutation function"):
            replace_in_function(APP, "notPresent", "startClockedSound();", ";")

    def test_missing_call_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "must occur once"):
            replace_in_function(APP, "runInteractive", "oldStartupCall();", ";")

    def test_ambiguous_call_is_rejected(self):
        duplicate = APP.replace("startClockedSound();", "startClockedSound();\n        startClockedSound();")
        with self.assertRaisesRegex(RuntimeError, "must occur once"):
            replace_in_function(duplicate, "runInteractive", "startClockedSound();", ";")

    def test_unchanged_replacement_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "must occur once"):
            replace_in_function(APP, "runInteractive", "startClockedSound();", "startClockedSound();")

    def test_unchanged_mutation_tuple_is_rejected(self):
        original = (APP, "engine", "audio")
        with self.assertRaisesRegex(RuntimeError, "mutation 1 is a no-op"):
            require_changed_mutation(original, original, 1)
        require_changed_mutation(original, (APP + "\n", "engine", "audio"), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
