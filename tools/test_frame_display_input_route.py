import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'frame_display_probe'))
from input_route import GAME_OVER_TEXT_MASK, LEVEL_ONE_TEXT_MASK, MAIN_PIXELS, prompt_key


class FrameDisplayPromptInputTest(unittest.TestCase):
    def test_inspected_text_mask_with_variable_background(self):
        self.assertEqual(prompt_key('unknown background', 5, 0, LEVEL_ONE_TEXT_MASK), 'Return')

    def test_unknown_text_is_not_a_prompt(self):
        for mask in (None, '', '0' * 64, LEVEL_ONE_TEXT_MASK[:-1] + '0'):
            self.assertIsNone(prompt_key('unknown background', 1800, 0, mask))

    def test_text_mask_does_not_bypass_stall_or_input_bound(self):
        for seconds in (0, 4.99):
            self.assertIsNone(prompt_key('unknown background', seconds, 0, LEVEL_ONE_TEXT_MASK))
        for attempts in (12, 13):
            self.assertIsNone(prompt_key('unknown background', 1800, attempts, LEVEL_ONE_TEXT_MASK))

    def test_main_menu_and_old_route_compatibility(self):
        self.assertEqual(prompt_key(MAIN_PIXELS, 5, 0), '1')
        self.assertIsNone(prompt_key(MAIN_PIXELS, 0, 0))

    def test_inspected_game_over_mask(self):
        self.assertEqual(prompt_key('unknown background', 5, 0, None, GAME_OVER_TEXT_MASK), 'Return')
        self.assertIsNone(prompt_key('unknown background', 4.99, 0, None, GAME_OVER_TEXT_MASK))
        self.assertIsNone(prompt_key('unknown background', 1800, 12, None, GAME_OVER_TEXT_MASK))
        self.assertIsNone(prompt_key('unknown background', 1800, 0, None, '0' * 64))


if __name__ == '__main__':
    unittest.main()
