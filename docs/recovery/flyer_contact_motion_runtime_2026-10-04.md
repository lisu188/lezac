# Original Behavior-4 Terrain and Motion

Two independent silent original captures agree on all 176 seeded motion cases.
The production replay initially disagreed at exactly eight signed-word NEG
boundaries. Narrowing the negation before division fixes those cases; all 176
positions, velocities, fractional bytes and RNG results now match.

## Native Observation

The portable producer is `tools/capture_original_flyer_contacts.py`. It starts
the shipped executable in a private asset copy, uses physical menu input to
enter two-player level 1 and finishes one unseeded update before any case seed.
The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.

Three guarded hooks observe the actor-pass boundary at `1000:7EC5`, the
behavior-4 floor response at `1000:7062` and the end of common Y/X integration
at `1000:741E`. The latter is before generic actor damage and final writeback.
Both motion hooks check the actual actor parameter `SS:[BP+4] = DS:1BD4`
and behavior local 4, excluding unrelated actors. The producer preserves the
registers, flags and stale hook-stack bytes, checks the two far-call relocation
words separately, then restores every hook and scratch byte before closing its
owned child. Native motion changes registers; only segment, stack and actor
identity are required to remain equal across the observation pair.

The scratch extent is the existing verified `F400..F8B6` window. Cases are
seeded only at the actor-pass boundary. There are no result-local writes or
per-instruction changes inside the observed motion path. The 58 raw local
bytes, six registers, actor pointer, input actor bytes and terrain hash accompany
every native result. Target deltas are checked against those raw locals.

Producer SHA-256:
`f4028c623b9303892d94fa4848e462475a9f3a1395aab29fe58548a705d7fc81`.
Complete native JSON hashes:

- Run A: `feba3e13a0186e1167fa7385bd15b1bddc93bbe24db7014ebf7d6d743207ca88`
- Run B: `ad056ab436c09418788a27a81118f1561e6f3069263eb3f0192fb7a2527d041c`

Both complete captures and negative/positive diagnostics are preserved in the
[byte-checked archive](evidence/flyer_contact_20261004/README.md). The pinned
fixture is `tests/fixtures/flyer_contact_motion_original.bin`, 6,400 bytes,
SHA-256 `e82e0f352fd2e83fefbccfe297e3504254a0289d90952d3e6f75e7c98ea0b367`,
FNV-1a64 `5c0909e8081f8026`. Its 64-byte header pins the executable and floor/common
instruction windows; each of the 176 36-byte rows carries input fields, original
edge flags and complete observed X/Y, VX/VY, fractional-byte and RNG outputs.

## Coverage and Recovered Behavior

- 64 off-gate cases: eight actor kinds with no edge, each individual edge,
  both sides, floor/ceiling squeeze and all four edges.
- 48 tile-class boundaries: `00,01,4C,4D,52,53,75,FF` at six edge combinations.
- 32 signed VX boundaries: `-32768,-32767,-1,32767` for each of kinds 1..8.
- 32 steering/contact cases: all 16 edge combinations at a shared-clock gate,
  separately exercising far RNG steering and negative diagonal near homing.

The case actors intentionally use a common zero hotspot and descriptor range
40..42. This exercises kind-dependent dispatch with bounded explicit actor
inputs; it does not recover every kind's shipped constructor or sprite profile.
The camera, start level, player inputs, terrain and actor state are deliberate
seeds, not natural spawn or route evidence.

The native results confirm strong floor reflection only for tiles `1..4C`,
floor/ceiling squeeze before steering, ceiling clamp and side response after
steering, both-side zeroing, the sign-based one-pixel side push, and persistent
fractional carries through Y-before-X integration. Bottom-only `4D..52` cells
set the wider bottom flag but do not cause behavior-4 floor reflection. Far
steering consumes the two RNG draws even if common contact then replaces VX.

At `1000:73CC`, `NEG AX` operates on a word before `CWD/IDIV 2`.
For VX `-32768`, negation remains `-32768`; division produces `-16384`, the
side push is leftward, and the captured final X is 271. The previous wide C++
negation produced positive 16384 and the opposite push. The fix changes only
this common monster reflection expression, leaving gravity, floor response,
steering, push order, integration, animation and damage code unchanged.

The preserved pre-fix source commit is
`c8f674c550a6eb0ac18942738c1c984f324159e8`. Its diagnostic failed at exactly
`112,116,120,124,128,132,136,140`; the other 168 cases matched. The changed
production expression makes every case pass. This is an original-backed
signed-word boundary, not evidence that a natural flyer reaches that velocity.

## Validation

`--debug-flyer-contact-motion-evidence` drives production `updateMonsters()`
for every fixture row and checks both integer axes, both velocities, both
fraction bytes and RNG, with independently checked terrain scan flags.
The fixture guard rejects all 6,400 single-byte mutations, truncation, trailing
bytes and a changed original executable. The executable replay rejects 18
malformed inputs. The retained-archive test checks all 24 members and reproduces
the fixture independently from both complete native captures.

Local Release build and 73 focused CTests passed, including all six new gates,
the existing behavior-4 replays/target tests, actor contacts, walker ledges,
four gravity families and boss combat replays. A separate exact-head workflow
recaptures all 176 original cases on Linux; full Linux/Windows and isolated
package checks remain required before merge. The archive-checking helper's
initial unsupported `safe_file` argument was corrected to a bounded structured
path check; the subsequent archive test passes without weakening its checksum,
member-count or byte guards. This tooling error was not a game mismatch.

## Frame Inspection and Limits

The original bootstrap and fresh C++ level-3 flyer spawn frames are nonblank
320x200 game surfaces. The C++ PNG is a lossless encoding of the captured PPM;
its manifest has player `(376,32)`, flyer `(353,47)`, VX/VY `(288,-192)`, kind 2,
behavior 4, HP 5 and sprite 39. These screenshots use different scenes and are
not synchronized native/C++ checkpoints:

- [Original unseeded bootstrap](evidence/flyer_contact_20261004/original-bootstrap.png)
- [Fresh C++ flyer checkpoint](evidence/flyer_contact_20261004/cpp-level3-spawned.png)

This narrows `behavior4_motion_runtime_fixture` and the broader actor-contact
item without closing either. Natural constructors/trajectories, all level
geometry, spawn parameter generation, animation and damage parity, two-player
interaction, coordinate overflow/out-of-map behavior and full actor writeback
remain outside these probes. Other reflection helpers are not changed by this
batch. All four OPEN items remain; `visual_claim=0`,
`original_fidelity_claim=0` and `port_functionally_complete=0` are unchanged.
