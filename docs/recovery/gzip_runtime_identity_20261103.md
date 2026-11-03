# Frozen Gzip Evidence and Runtime Recompression

The Python 3.15 Windows job `125949043346` in compatibility run
`41645328662` failed after PR #484 was merged. The explicit-level-9
recompression test added by #481 still assumed that every runtime would emit
the same DEFLATE bytes as the historical capture. Its gzip metadata was not
the problem: the compressed stream differed despite requesting level 9.
The exact compressor-level cause is not established by that job's log.

The test now distinguishes immutable evidence identity from recompression:

- The frozen gzip SHA-256 remains
  `a490bfeb50d553dc6f5a75208bedf3349f3bc1c3091ad40014170b4154ed93ac`.
- Its decoded length remains 2,511,492 bytes, with SHA-256
  `5939f17b028ed31243c3a0ceb689927faeaef8deae196b5c911f44b41e6d4395`.
- A fresh level-9 encoding must repeat byte-for-byte within the current
  runtime, preserve the complete fixed gzip header and CRC/length trailer,
  and decode to the complete original payload byte-for-byte.
- A valid lossless reencoding is explicitly rejected by the fixture reader.
  Truncated, extended and changed decoded payloads are rejected even after
  authenticating their replacement container in the negative control.
- The level-6 control still detects the changed compression-level header.

No fixture, metadata pin, capture producer, production checker, C++ source or
workflow test command is changed. The 360 original-derived cases and 127
late-clock-phase counterexamples remain the same bounded evidence; this is
not a new original capture or whole-game fidelity proof.

This supersedes the cross-runtime reproduction assumption in
`ci_compression_budget_20261103.md`, not its recorded local Python 3.12 result.
Python documents gzip as backed by zlib and gives controls for metadata and
compression level; CPython delegates the DEFLATE stream to `zlib.compressobj`.

## Local Validation

All five compatibility suites pass, totaling 43 tests per runtime:

| Runtime | Compression backend | Old assertion | Fixed suites |
| --- | --- | --- | --- |
| Linux Python 3.12.3 | zlib 1.3 | passes | 43 pass |
| Native Windows Python 3.12.14 | zlib 1.3.2 | passes | 43 pass |
| Native Windows Python 3.15.2 | zlib-ng 1.3.1 | fails | 43 pass |

The actual Windows 3.15.2 runtime was the official x64 embeddable package,
authenticated against Python.org's SHA-256
`d012f3aa29cf07436dae8aea1fec0fd195c2612a0b059b1f915ae0afb9ad1f62`.
Its level-9 output is 14,672 bytes, SHA-256
`f76d39e215fd887934a0bd808e77171a3e1f8a3a503e33eb5ff148a52fe2b77a`;
the first difference from the frozen container is at byte 12. Both containers
decode to the complete authenticated payload above. This is an actual runtime
reproduction, not an emulation of Python's changed compression default.

The unchanged compiled C++ App passes all 360 original debris-phase cases,
including the 127 late-phase counterexamples. This lane does not execute a new
full original-game frame. All generated validation scratch and the downloaded
runtime remain RAM-backed; only compact reports are retained durably.

References:

- https://docs.python.org/3.15/library/gzip.html
- https://docs.python.org/3.15/library/zlib.html
- https://github.com/python/cpython/blob/v3.15.2/Lib/gzip.py
- https://www.python.org/downloads/release/python-3152/
- https://github.com/lisu188/lezac/actions/runs/41645328662/job/125949043346
