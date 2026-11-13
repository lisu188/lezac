"""Regression tests for original-backed Italian Level 1 scene recognition."""

import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import unittest

from check_main_menu_fixture import HEADER, ROOT, load_fixture
from intro_frame import CAPTION_PREFIXES, CAPTION_WHITE, SHADOW, WHITE, intro, is_level1_intro, legal_palette
from test_bios_menu_input_xdotool import intro as bios_intro
from test_buffered_menu_repeat_xdotool import intro as buffered_intro


FIXTURE = ROOT / "tests/fixtures/intro_recognition"
MANIFEST_SHA = "f2e1227e356e34c92fd4451ac31f71c7fb30ff26d524ed79b3cfeaab5e1e1adb"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def captures():
    raw = (FIXTURE / "manifest.json").read_bytes()
    assert sha(raw) == MANIFEST_SHA, "intro recognition manifest changed"
    manifest = json.loads(raw)
    assert manifest["schema"] == 1 and manifest["whole_game_parity"] is False
    assert sha((ROOT / "LEZAC.EXE").read_bytes()) == manifest["original_exe_sha256"]
    record = (ROOT / manifest["original_record"]).read_bytes()
    assert sha(record) == manifest["original_record_sha256"]
    assert sha(gzip.decompress((ROOT / manifest["original_observer"]).read_bytes())) == manifest["original_observer_sha256"]
    assert sha(gzip.decompress((FIXTURE / "producer.py.gz").read_bytes())) == manifest["producer_sha256"]
    frames = {}
    for name, row in manifest["frames"].items():
        assert Path(row["file"]).name == row["file"]
        compressed = (FIXTURE / row["file"]).read_bytes()
        assert sha(compressed) == row["gzip_sha256"]
        ppm = gzip.decompress(compressed)
        assert ppm.startswith(HEADER) and len(ppm) == len(HEADER) + 64000 * 3
        assert sha(ppm) == row["ppm_sha256"] and sha(ppm[len(HEADER):]) == row["rgb_sha256"]
        if name != "ci-failure-intro":
            assert sha((ROOT / row["source_png"]).read_bytes()) == row["source_png_sha256"]
        frames[name] = ppm[len(HEADER):]
    assert set(frames) == {"original-intro", "ci-failure-intro", "original-gameplay-one", "original-gameplay-two"}
    assert {p.name for p in FIXTURE.iterdir()} == {"manifest.json", "producer.py.gz"} | {
        row["file"] for row in manifest["frames"].values()}
    assert json.loads(record)["captures"][3]["pixel_sha256"] == sha(frames["original-intro"])
    return frames


def palette(starts=(5, 15, 1), deltas=(0, 3, 4)):
    return tuple(bytes((value << 2) | (value >> 4)
                       for start, delta in zip(starts, deltas) for value in (start + delta * i // 7,))
                 for i in range(7))


def synthetic_frame(colors, count=26):
    # Synthetic recognition probes, not native captures or parity expectations.
    image = bytearray().join(colors[(x // 8 + y // 3) % 7] for y in range(200) for x in range(320))
    visible = frozenset(i for i in CAPTION_WHITE if i % 320 < 17 + count * 11)
    shadow = frozenset(i - 321 for i in visible) - visible
    for positions, color in ((shadow, SHADOW), (visible, WHITE)):
        for i in positions:
            image[i * 3:i * 3 + 3] = color
    return bytes(image)


def recolor(pixels, index, color):
    changed = bytearray(pixels)
    changed[index * 3:index * 3 + 3] = color
    return bytes(changed)


class IntroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.captured = captures()

    def test_original_complete_caption(self):
        image = self.captured["original-intro"]
        self.assertTrue(is_level1_intro(image))
        white = frozenset(i for i in range(64000) if image[i * 3:i * 3 + 3] == WHITE)
        self.assertEqual(white, CAPTION_WHITE)
        self.assertEqual(len(white), 620)
        self.assertEqual(len(CAPTION_PREFIXES[white]), 360)
        self.assertEqual(len(next(iter(CAPTION_PREFIXES))), 31)

    def test_actual_failed_ci_frame_has_legal_duplicate_colors(self):
        image = self.captured["ci-failure-intro"]
        colors = frozenset(image[i:i + 3] for i in range(0, 320 * 80 * 3, 3))
        self.assertEqual(len(colors), 6)
        self.assertEqual(colors, frozenset(palette()))
        self.assertTrue(is_level1_intro(image))

    def test_all_typing_prefixes_with_one_to_seven_distinct_colors(self):
        for distinct in range(1, 8):
            colors = palette(deltas=(0, 0, 0 if distinct == 1 else distinct))
            self.assertEqual(len(set(colors)), distinct)
            for count in range(1, 27):
                with self.subTest(distinct=distinct, count=count):
                    self.assertTrue(is_level1_intro(synthetic_frame(colors, count)))

    def test_monochrome_palette_extremes(self):
        for start in (0, 19):
            self.assertTrue(is_level1_intro(synthetic_frame(palette((start,) * 3, (0, 0, 0)))))

    def test_shadow_color_can_also_be_legal_background(self):
        colors = palette((0, 0, 18), (0, 0, 29))
        self.assertIn(SHADOW, colors)
        self.assertTrue(is_level1_intro(synthetic_frame(colors)))

    def test_legal_palette_parameter_domain(self):
        for start in range(20):
            for delta in range(30):
                self.assertTrue(legal_palette(frozenset(palette((start,) * 3, (delta,) * 3))))
        rng = random.Random(0x2C72)
        for _ in range(100):
            self.assertTrue(legal_palette(frozenset(palette(tuple(rng.randrange(20) for _ in range(3)),
                tuple(rng.randrange(30) for _ in range(3))))))

    def test_invalid_palette_parameters(self):
        for colors in ((), (b"\x01\x02\x03",), palette((20, 20, 20), (0, 0, 0)),
                       palette((0, 0, 0), (30, 30, 30)), tuple(bytes((i * 4, 0, 0)) for i in range(8))):
            with self.subTest(colors=colors):
                self.assertFalse(legal_palette(frozenset(colors)))

    def test_legal_channels_with_illegal_rgb_pairings(self):
        colors = list(palette((5, 15, 1), (14, 14, 14)))
        colors[0], colors[1] = colors[0][:2] + colors[1][2:], colors[1][:2] + colors[0][2:]
        self.assertFalse(legal_palette(frozenset(colors)))
        self.assertFalse(is_level1_intro(synthetic_frame(colors)))

    def test_real_menu_frames_are_not_intro(self):
        _, frames = load_fixture()
        for name, data in frames.items():
            with self.subTest(name=name):
                self.assertFalse(is_level1_intro(data[len(HEADER):]))

    def test_actual_single_and_two_player_gameplay_are_not_intro(self):
        for name in ("original-gameplay-one", "original-gameplay-two"):
            self.assertFalse(is_level1_intro(self.captured[name]))

    def test_blank_and_captionless_stripes_are_not_intro(self):
        self.assertFalse(is_level1_intro(bytes(64000 * 3)))
        self.assertFalse(is_level1_intro(synthetic_frame(palette(), count=0)))

    def test_corrupt_white_glyph_and_wrong_caption_position(self):
        original = self.captured["original-intro"]
        index = min(CAPTION_WHITE)
        removed = recolor(original, index, b"\x1c\x04\x28")
        self.assertFalse(is_level1_intro(removed))
        self.assertFalse(is_level1_intro(recolor(removed, index + 320, WHITE)))
        self.assertFalse(is_level1_intro(recolor(original, 63999, WHITE)))

    def test_corrupt_or_extra_shadow(self):
        original = self.captured["original-intro"]
        index = min(CAPTION_PREFIXES[CAPTION_WHITE])
        self.assertFalse(is_level1_intro(recolor(original, index, b"\x1c\x04\x28")))
        self.assertFalse(is_level1_intro(recolor(original, 63999, SHADOW)))

    def test_nonbackground_pixels_below_the_observed_palette_band(self):
        self.assertFalse(is_level1_intro(recolor(self.captured["original-intro"], 63999, b"\x00\xff\x00")))

    def test_wrong_frame_length(self):
        image = self.captured["original-intro"]
        for data in (b"", image[:-1], image + b"\0", image[:320 * 80 * 3]):
            self.assertFalse(is_level1_intro(data))

    def test_both_live_helpers_use_the_same_recognizer(self):
        self.assertIs(bios_intro, intro)
        self.assertIs(buffered_intro, intro)

    def test_image_mode_and_dimensions(self):
        class Image:
            mode = "RGB"
            size = (320, 200)

            def tobytes(image):
                return self.captured["original-intro"]

        image = Image()
        self.assertTrue(intro(image))
        image.mode = "RGBA"
        self.assertFalse(intro(image))
        image.mode = "RGB"
        for size in ((960, 600), (200, 320), (640, 100)):
            image.size = size
            self.assertFalse(intro(image))


if __name__ == "__main__":
    result = unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    if not result.wasSuccessful():
        raise SystemExit(1)
    print("intro_frame_contract=ok cases=17 original_caption=1 failed_ci_frame=1 palette_sizes=7"
          " typing_prefixes=26 real_menu_frames=16 real_gameplay_frames=2 synthetic_parity_claim=0 whole_game_parity=0")
