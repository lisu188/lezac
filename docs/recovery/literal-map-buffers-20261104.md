# Literal Map Buffer Transport

`tools/literal_map_buffers.py` provides a bounded, lossless gzip/JSON container
for tile bytes, little-endian map-word bytes and the raw six-bit VGA DAC shadow.
It does not launch, attach to, stop, read or write a guest. The caller supplies
already observed buffers from one stopped-child instant.

## Why This Exists

Current natural-window projection fields named `tiles_hex` and `words_hex` hold
SHA-256 receipts, not literal original map bytes. Complete RGB comparisons and
matching map receipts do not independently establish literal map-plane equality.
Existing DS snapshots cannot reconstruct heap planes outside DS.

This helper prepares retention of those separately read buffers without changing
gameplay, replacing old evidence, synthesizing original expectations from C++, or
publishing private snapshots. Campaign-capture integration is separate work.
Adding this transport does not upgrade historical claims.

## Contract

The packer receives `state['tiles']`, `state['words']`, `state['frame']`,
`state['rng']`, a complete 65,536-byte DS snapshot and the 768-byte DAC shadow as
hex. These are the raw inputs already available to the natural observer before
its projected map receipts are computed.

Dimensions and far pointers follow the existing observer layout:

- Width: DS:C204; height: `word(DS:2096) // 8 + 21`.
- Tile pointer: DS:C1E0; word pointer: DS:6612, each offset then segment.
- Native frame: DS:78C2; RNG: DS:1AFE; level byte: DS:79B7.
- Both heap spans must fit their 64 KiB far span and conventional-memory bound.

The container carries literal bytes as canonical lowercase hex, their complete
lengths/hashes, DS digest, pointer descriptors, dimensions, native frame, RNG,
route tick, phase and the caller's observation role. No DS bytes or other guest
memory are included. All fidelity and full-guest-RAM claims remain false.

Readers require the original DS snapshot, expected tick/phase/role, the external
container digest and all three external plane digests. Those receipts must come
from the separately authenticated observation journal, not from the container
being checked. A caller-provided `original_runtime` role is not an attestation
that the caller actually observed the original game.

Readers reject changed extents, pointers, DS bytes, hashes, roles, instants,
metadata, unsupported phases, noncanonical JSON/hex, duplicate JSON keys, DAC
values above63, corrupted gzip, trailing bytes and concatenated gzip members.
Compressed and decoded documents are both bounded to256KiB before parsing.
Packing uses a fixed gzip header with no filename or timestamp. Repeat packing
is deterministic in a given runtime; cross-zlib compressed-byte identity is not
required for reading a receipt-checked existing container.

## Validation And Limits

`literal_map_buffers_fixture` runs synthetic controls without game assets,
Pillow, optional executors or guest execution. It covers all four previously
observed campaign dimensions, the full64KiB word span, complete byte roundtrips,
external receipt binding, coherent data/metadata mutations, bounded decoding and
an isolated source-checkout roundtrip. The Python compatibility matrix includes
this suite on Python3.12/3.15 and Linux/Windows.

Local validation passes19synthetic tests on Windows Python3.12.14 and WSL
Python3.12.3, plus five focused CTests including existing capture regressions.
A private bounded original Level1probe also passed:17samples,34boundaries and
228072complete literal buffer bytes read back. No C++ expectations constructed
those observations. Hooks, the trampoline function and protected inputs were
restored. The codec used in that probe has SHA-256
`2b1ace49dca24d499b147e3b7a57f35ce808977114151e6d7eac17379dc31f08`.
Its producer has SHA-256
`edb5ce4af38e511ec43983340959b7abcd7bd19888372a3a6a0d73b1987f38e7`.
Private payloads and screenshots are not committed. An earlier probe's premature
stopped-window screenshot assertion failed; its diagnostics are retained, not
counted as a successful run. The corrected probe uses the established
presentation screenshot path and leaves the codec unchanged.

This is a transport contract, not a new Level4capture, a C++ map comparison,
a complete palette-model verification, a raw-memory normalization policy, or
whole-frame equivalence. Original/runtime evidence must be obtained and audited
before making any of those claims. Raw captures remain private.
