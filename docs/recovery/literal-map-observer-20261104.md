# Literal Map Observation Binding

`tools/literal_map_observer.py` connects the lossless literal-buffer transport to
the natural original-game observer's boundary journal. It does not launch or
access a guest, choose inputs, change gameplay, or synthesize original data.

## Integration Contract

The caller reads the complete DS snapshot, raw tile/word planes and DAC shadow
at one stopped-child instant, then constructs its usual projected boundary.
Before publishing that boundary, it retains the original raw buffers:

```python
row['literal_buffers'] = retain_literal_buffers(
    row, raw_state, ds_bytes, dac_hex, private_write_and_read)
```

`private_write_and_read(name, payload)` must perform the observer's actual private
write, flush and complete readback, and return the read bytes. The adapter checks
every returned encoded byte before returning a receipt. The callback owns the
storage policy, atomic publication and durability; returning an input buffer
without reading storage does not establish any of those properties.

The adapter binds the container receipt to route tick, present/post-update phase,
observation sequence, native level, complete DS digest, native frame, RNG and the
already computed projected tile/word SHA-256 receipts. Literal planes must match
those receipts. DAC extent/range and the transport's complete layout and framing
checks still apply. If storage fails, readback differs, or the callback changes
the boundary's bound identity, no receipt is returned. Input boundaries are not
modified by the adapter, and an existing attachment cannot be replaced silently.

Readers use the separately authenticated boundary:

```python
metadata, buffers = read_literal_buffers(row, original_ds_bytes, encoded_payload)
```

This verifies the external receipt, exact container name and extent, boundary
context, all three plane hashes and complete unchanged literals. External
authentication must cover the boundary journal itself, including its attachment;
the adapter cannot distinguish a genuine journal from a coherently fabricated
one. An `original_observation` assertion or `original_runtime` role is not source
attestation. Other projected fields are outside this adapter's selected context
and require the journal's own complete-boundary authentication and validation.

## Validation

Fifteen synthetic controls pass on Windows Python 3.12.14, WSL Python 3.12.3 and
the existing Windows Python 3.15.2 embedded runtime. They cover complete
roundtrips at both phases, failed/incorrect callback readbacks, callback identity
mutation, stale DS/projections, changed sequence/tick/phase, malformed receipts,
claim flags and a frozen source-only subprocess without game assets or optional
modules. `literal_map_observer_fixture` is registered alongside the existing
transport fixture and is included in the Python 3.12/3.15 compatibility matrix.

A new private Level 4 observer uses this adapter before each boundary is
published. It reuses the established stopped-child state/heap reads and natural
campaign handoffs, adds no guest mutation, and retains compressed DS, literal
containers and screenshots privately. Its full ordinary startup and three
natural handoffs completed successfully, followed by every frame from route
tick 18100 through 18800. Hooks were restored and protected inputs were unchanged.

The independent original-only audit completely reads back 4,926 private/RAM
members, including 1,408 retained boundaries and 25,596,744 literal buffer bytes.
It re-decodes DS with the previously authenticated frozen decoder, combines it
with the retained original heap/DAC literals, and reproduces every declared
projection without differences. Six mutations of actual original-boundary data
are rejected. No C++ expectations construct this reference.

Both pinned native C++ builds match all 701 complete RGB frames and 1,402
present/post-update boundaries in the new Level 4 window. On each platform the
comparison checks every one of 24,394,800 literal tile/word bytes and 134,592,000
RGB bytes, in addition to the declared state and nine bomb fields across 118
bomb-present boundaries. Fourteen real native-record mutations are rejected per
platform. Each complete four-phase trace also passes its 2,804-row protocol,
input, time and asset checks. The Windows process and its loaded SDL DLL were
observed with their expected hashes. The unchanged C++ source tree is
`8d059cdd61dce9a9af207cb7e07c879d6f843a84`.

All nine compatibility steps pass locally on Windows/WSL Python 3.12: 99 tests
per platform. Six focused CTests pass. The additional Windows Python 3.15 lane
runs all 15 adapter tests, including the isolated source-checkout subprocess.
This does not assert that every hosted CI/scanner job has completed.

Private capture producer SHA-256:
`b2be61cd1142d81e7fe01c13438333fdc017af1a1fdfca96d5d4541dbd0d7283`.
Original-only audit SHA-256:
`8cf570e33c1b2b40fba39a1440593713360c10a0087b575642e785333558b79b`.
Original-only reference SHA-256:
`8181986d6946d705e202d7721c3fc021acf23c0079acaa3feff6dd4800ea960a`.
The adapter used by that capture has SHA-256
`daf4b1f903993bb6c01c9af2d7f834ec2502c8254f5732930f89ea3239697993`.

## Scope

All fidelity/full-frame/full-RAM flags in the attachment remain false. Literal
retention does not itself establish C++ equality, a complete palette model,
full actor-record equivalence, timing equivalence, manual-input acceptance or
whole-game recovery. Historical hash-only map observations are not retroactively
upgraded. No original snapshots, literal payloads or screenshots are published
with this adapter.

The tested Medium route earns no new destruction credit and consumes the last
Medium bomb. It is an independently qualified branch probe, not an improved
campaign resource frontier. The best resource-preserving checkpoint remains
tick 18100, Level 4 at 286/305 credits with one Medium bomb available.
