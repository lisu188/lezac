# Physical Actor Storage Core

This is a staged recovery of the original physical tables, not production
application integration or complete actor/campaign fidelity. `ActorStorage`
is compiled into a standalone regression probe; `App` still owns its existing
typed collections. No completion or broad fidelity flag changes.

## Original Rules

The pinned `LEZAC.EXE` SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Original constructor `1000:2F9F` appends up to 30 nonplayer actors. It writes
only bytes `0,1,2,6..13,20,21` of a reused 38-byte record; all other bytes are
preserved. Rejection changes only the success WORD. Velocity clamping includes
the original `-32768` exception and is shared with the existing recovered helper.

Retirement `1000:3358` stably copies complete actor and visual records. It does
not clear their inactive tails. Surviving actor visual references, including
player 2, and active boss-link reference bytes decrement only when greater than
the removed visual index. Actor slot 0 belongs to player 2; retiring that slot
is outside the nonplayer API and explicitly rejected, not claimed equivalent
to arbitrary original invalid inputs.

The storage portion of reset slices `2BA4..2BDC`, `2D5A..2D91`, and
`2D91..2E0B` resets counts, player descriptors and specified player-2 fields.
It preserves all 30 inactive nonplayer records. This is not emulation of the
complete level initializer or its DOS, rendering, and file operations.

Tables at DS `1BAE` (31 x 38 actors), `C21E` (visual rows), and `79EA`
(8 x 16 boss links), plus their counts and success WORD, form each 1,575-byte
snapshot. Visual guard row 32 is included, not removed from comparison. Its
last four bytes overlap original descriptor 0 at `C322..C325`; active operations
do not write that guard row. The separate descriptor bank is immutable input.

## Compiled Comparison

The four gzip fixtures under `tests/fixtures/actor_storage/` contain binary
requests and actual unpatched original-machine-code output, not Python-model
predictions. The constructor/retirement stream covers 5,340 operations:
1,395 retirements, 12 continuous retirement/appends, 93 out-of-range retirements,
and 3,840 constructions including 960 capacity rejections. The reset/reuse
stream covers 16 reset sequences, 480 successive allocations and 16 capacity
rejections: 512 operations without reseeding between a reset and its appends.

`actor_storage_core_original` compares all 9,216,900 table/scalar bytes after
5,852 operations. Compressed and decompressed fixture SHA-256 identities are
pinned in `tools/check_actor_storage_core.py`; decompression is bounded. The
checker records a unique report and retains requests, expected/actual output,
stderr, and the first differing operation/byte on failure or timeout.
`actor_storage_checker_contract` verifies all 1,575 byte offsets, corrupt or
oversized fixtures, output extents, process failure, timeout, and diagnostic
retention. The Windows probe explicitly selects binary stdin/stdout.
`actor_storage_api_contract` additionally checks seven rejected accesses or
restores, preservation after rejection, mutable writeback, and a retained tail.

The source-bound original CPU helper used for capture is SHA-256
`fd3066a8b28edc5872221692a88f24d4758c8e7961cb7b91a03d9b94c16fe41c`.
Retained capture scripts are SHA-256
`bdbb069b3d5c4fbe6a5d6aace5f487f9215325dea56104a4e4b7c3226e7d1dbd`
(constructor/retirement) and
`6d2dc70ab7787bb7f261a1ea56f07563c07d9de5d6b6cb0dcd8b5eda00c09364`
(reset/reuse), with wire serializer
`7cf2eca5f0821279f4cce614be0e866fb328578b00ec698988f464a991633a2b`.
These task-local capture sources are retained evidence, not an advertised
fresh-checkout capture command. The committed regression needs only Python's
standard library and the compiled probe, not Unicorn or an unmerged PR.

Local compiled negative controls reject construction-slot clearing, actor-tail
clearing, visual-tail clearing, reversed actor-reference adjustment, reversed
boss-reference adjustment, and clearing nonplayer records on level reset.
The unmodified standalone Linux probe passes; this does not claim a local full
game build, Windows compilation, or a fresh native original capture.

## Remaining Integration

Production integration must write typed state back before retiring a physical
slot, preserve in-place corpse/reward/fade conversions, and handle same-pass
appends without duplicate allocations. Ordinary level reset must not become
zero-filled diagnostic initialization. Full raw fields must come from storage,
not fixture-supplied projection. Natural stale-slot reachability, all actor
consumers, Windows execution, complete campaigns, VGA/HUD and sound parity
remain separate open requirements. All agent-launched commands use dummy audio.
