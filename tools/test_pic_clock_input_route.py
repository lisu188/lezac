import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent / 'pic_clock_probe'))
from input_route import LEVEL_ONE_INTRO_PIXELS, MAIN_PIXELS, prompt_key


class NaturalPromptInputTest(unittest.TestCase):
    def test_main_menu(self):
        self.assertEqual(prompt_key(MAIN_PIXELS, 5, 0), '1')

    def test_inspected_level_one_intros(self):
        for pixels in LEVEL_ONE_INTRO_PIXELS:
            with self.subTest(pixels=pixels):
                self.assertEqual(prompt_key(pixels, 5, 0), 'Return')

    def test_stall_is_not_a_prompt_identity(self):
        for pixels in ('', '0' * 64, MAIN_PIXELS[:-1] + '0'):
            with self.subTest(pixels=pixels):
                self.assertIsNone(prompt_key(pixels, 1800, 0))

    def test_moving_counter_never_acknowledges(self):
        for pixels in (MAIN_PIXELS, *LEVEL_ONE_INTRO_PIXELS):
            for seconds in (0, 1, 4.999):
                with self.subTest(pixels=pixels, seconds=seconds):
                    self.assertIsNone(prompt_key(pixels, seconds, 0))

    def test_input_bound(self):
        self.assertEqual(prompt_key(MAIN_PIXELS, 5, 11), '1')
        for pixels in (MAIN_PIXELS, *LEVEL_ONE_INTRO_PIXELS):
            for attempts in (12, 13, 100):
                with self.subTest(pixels=pixels, attempts=attempts):
                    self.assertIsNone(prompt_key(pixels, 1800, attempts))


if __name__ == '__main__':
    unittest.main()
