"""Verify the SDL image reported by dladdr in the actual oracle process."""
import hashlib
from pathlib import Path

MARKER='lezac_sdl_library='

def loaded_library(stderr,expected,expected_sha256):
    entries=[line[len(MARKER):] for line in stderr.decode('utf-8').splitlines() if line.startswith(MARKER)]
    if len(entries)!=1 or not entries[0]:raise ValueError('Oracle SDL runtime identity is missing or ambiguous')
    actual=Path(entries[0]).resolve(strict=True);expected=expected.resolve(strict=True)
    digest=hashlib.sha256(actual.read_bytes()).hexdigest()
    if actual!=expected or digest!=expected_sha256 or hashlib.sha256(expected.read_bytes()).hexdigest()!=expected_sha256:
        raise ValueError('Oracle loaded a different SDL image')
    return dict(path=str(actual),sha256=digest,verified=True)
