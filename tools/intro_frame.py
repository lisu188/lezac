"""Recognize the Italian Level 1 intro used by the physical keyboard tests.

This is scene recognition, not a whole-frame original/C++ parity comparison.
"""

from functools import lru_cache
from itertools import product


WHITE = b"\xff\xff\xff"
SHADOW = b"\x00\x00\xaa"

# White rows y=94..101 from the ungated original intro waiting capture:
# RGB SHA-256 33993e7ce0a873860eee4db36245a60014a2bcfec473e9f7d0f80f165ea7b431.
CAPTION_ROWS = (
    0x180000f0018031fe30c1e00300000c1e00007e3fc1f8000783fc1e03f0780fc7f83f07e0000,
    0x1c0001980180300630c0c00300000c0c0000c600c31800030060330630cc18c018630c60000,
    0x1800030c0180300630c0c00300000c0c00018600c61800030060618c318630c018c31860000,
    0x1800030c0180301e30c0c00300000c0c00018603c61800030060618c318630c078c31860000,
    0x1800030c018030061980c00300000c0c0000fe00c3f8000300607f87f1fe1fc0187f0fe0000,
    0x1800030c018030060f00c00300000c0c00003600c018000300606181b18600c0181b0060000,
    0x18000198018030060f00c00300000c0c0000e600c018000300606187318600c018730060000,
    0x3c0000f07f8ff1fe0601e0ff0003fc1e0001863fc01800078060618c318600c7f8c30060000,
)
CAPTION_WHITE = frozenset(y * 320 + x for y, row in enumerate(CAPTION_ROWS, 94)
                          for x in range(320) if row & (1 << x))
CAPTION_PREFIXES = {}
for count in range(1, 27):
    visible = frozenset(i for i in CAPTION_WHITE if i % 320 < 17 + count * 11)
    CAPTION_PREFIXES[visible] = frozenset(i - 321 for i in visible) - visible


@lru_cache(maxsize=128)
def legal_palette(colors):
    """Existence check for seven entries, including duplicate RGB values."""
    if not 1 <= len(colors) <= 7:
        return False
    vga = {(i << 2) | (i >> 4): i for i in range(44)}
    channels = []
    for channel in range(3):
        observed = {color[channel] for color in colors}
        start = vga.get(min(observed))
        if start is None or start > 19:
            return False
        candidates = []
        for delta in range(30):
            sequence = tuple((value << 2) | (value >> 4)
                             for i in range(7) for value in (start + delta * i // 7,))
            if set(sequence) == observed:
                candidates.append(sequence)
        if not candidates:
            return False
        channels.append(candidates)
    return any(frozenset(bytes(color) for color in zip(*channels_rgb)) == colors
               for channels_rgb in product(*channels))


def is_level1_intro(pixels):
    if len(pixels) != 320 * 200 * 3:
        return False
    colors = frozenset(pixels[i:i + 3] for i in range(0, 320 * 80 * 3, 3))
    if not legal_palette(colors):
        return False
    white = frozenset(i // 3 for i in range(0, len(pixels), 3) if pixels[i:i + 3] == WHITE)
    shadow = CAPTION_PREFIXES.get(white)
    if shadow is None:
        return False
    if any(pixels[i * 3:i * 3 + 3] != SHADOW for i in shadow):
        return False
    # Outside the exact glyph overlays, the entire frame must be background.
    return all(pixels[i:i + 3] in colors for i in range(0, len(pixels), 3)
               if i // 3 not in white and i // 3 not in shadow)


def intro(image):
    return image.mode == "RGB" and image.size == (320, 200) and is_level1_intro(image.tobytes())
