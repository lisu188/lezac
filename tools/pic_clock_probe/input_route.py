"""Ordinary prompt input, restricted to independently inspected original screens."""

MAIN_PIXELS = 'a6e2f9867be3fac329c8862529e751aedffd76f84d846c1c70700eb42bb3a914'
LEVEL_ONE_INTRO_PIXELS = frozenset({
    '7ad34a4ee880a433d291baf7c8192834f4d7c838b03634f777c0b14e66057bcb',
    'f33a2f71546ff046a10e88e5de95d14669391aaa7476b5eac69d6a9f03ff9916',
})


def prompt_key(pixels_sha256, unchanged_seconds, attempts):
    if unchanged_seconds < 5 or attempts >= 12:
        return None
    if pixels_sha256 == MAIN_PIXELS:
        return '1'
    if pixels_sha256 in LEVEL_ONE_INTRO_PIXELS:
        return 'Return'
    return None
