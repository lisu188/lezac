# Level Decoder Output Tails

The original decoder at `082D:0000` (file `0x8a40`, 273 bytes) writes each
run inclusively. Its run length is a nibble plus one; it writes both the start
and end positions, then advances the output cursor by the run length. When
that cursor reaches the requested output length, the last run has already
written between one and sixteen bytes beyond the logical plane.

`decodeLevelRle3WithTail` retains that exact written suffix separately from
the logical payload. The existing `decodeLevelRle3` payload-only interface is
unchanged. `PresentationState` still overwrites only the compressed prefix of
the retained 60,000-byte input/background buffer. `App` applies the object
decoder tail before decoding words, and applies the word tail afterwards.
`MapPlaneMemory` preserves the suffix in the same backing used for wrapped
and overlapping map reads. A small allocation can alias an object tail with
the later word allocation, so this write order is significant.

## Original Evidence

The checksummed fixture `tests/fixtures/level_rle_tail_original.json.gz` was
produced by `tools/capture_level_rle_tail.py` using Unicorn 2.1.4 and the
unmodified, relocated original executable. Fourteen cases decode both planes
of all seven shipped levels in ascending order using a retained input buffer.
Eight synthetic cases cover run boundaries, first-run termination, second-run
termination, and both maximum sixteen-byte tails.

Each original call is executed with a write observer and without that observer.
The complete 1 MiB RAM image and all fourteen recorded registers must agree.
There are no memory-read hooks, patched instructions, or interrupt/I/O stubs.
The original code region must remain unchanged and the far return must preserve
the caller's BP and pop the original arguments. These are seeded routine calls,
not natural campaign or level-reload observations.

To regenerate into a new path with Unicorn 2.1.4 available:

```sh
python3 -B tools/capture_level_rle_tail.py --root . --out /tmp/level-rle-tail-original.json.gz
sha256sum /tmp/level-rle-tail-original.json.gz
```

The fixture SHA-256 is
`8a49090e26f0b3d8d55db6dfc2341b34cab29085e9241be4acd626214898f5cb`.
It is byte-pinned with `-text` for cross-platform checkout stability.

## Verification

`level_rle_tail_original` compares the compiled production resource and
presentation decoders with all 22 cases: 143,247 logical payload bytes and
106 tail bytes, with no masks. The test also checks that both payload-only
interfaces retain their previous output contract. `level_rle_tail_unit` covers
exact written extent, empty/truncated input compatibility, alias write order,
and tail persistence across a subsequent allocation. `level_rle_tail_checker`
rejects nine corrupted fixture/output controls.

Focused local GCC and MSVC builds passed these checks and the existing
map-memory unit test passed with the updated header. A separate bounded
production-composition probe used the observed all-zero menu input buffer,
decoded Level 1, and read both complete 64 KiB map windows. Both compiler
outputs matched three unchanged-original startup RAM captures byte-for-byte:
393,216 compared bytes, zero differences, no masks. The previous production
probe differed at eight physical bytes, visible in both overlapping windows.
The original instruction trace and captured startup RAM both identify these
as eight `0x33` bytes written by the final word-plane run.

The startup RAM captures are retained in the task evidence bundle from
`natural-startup-heap-observation-t147`; the corrected compiler probes and
source pins are retained in `rle-tail-native-t149`. The probe uses observed
menu memory as exogenous input. It is not a complete C++ startup replay or a
full App memory-state comparison. The production App integration was checked
locally with `-fsyntax-only`; full build/runtime validation is delegated to CI
while the host disk guard is active.

This fix does not establish arbitrary Pascal heap-fragmentation parity,
natural reload/campaign history, a gameplay consequence of the extra bytes,
frame/pixel parity, sound-runtime parity, or whole-game completion. The broad
completion flags in `port_completion_status.md` remain unchanged.
