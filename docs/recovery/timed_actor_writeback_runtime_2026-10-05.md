# Complete Timed Actor Writeback

## Original Observation

Four independent silent original captures agree on 1,184 seeded behavior-2
updates each: two discovery runs and two runs with the production observer.
Entry is `1000:701C`; exit is the actual `1000:777F` return. Raw 58-byte
stack locals, 38-byte actors, eight-byte visual records, terrain hashes,
loaded instruction windows, unseeded bootstrap images and restoration proof
are retained. The selected actor-pointer and behavior guards exclude other
actors. CS, DS, SS, SP and BP remain stable; ES legitimately changes from
the map segment to DS during the native visual writeback.

Kinds 12 (corpse) and 13 (small bomb) cover eight tile glyphs, all 16 edge
subsets, signed velocity extrema and eight coordinate-wrap profiles. Fractions
start at 165/90. The initial timer byte is 11, both frame parities occur,
and animation is explicitly disabled. Hotspot 6 and the shared animation
profiles are exogenous seeds, not claims about shipped constructors. In
particular, a natural small bomb's sprite height gives a different hotspot.

The observer also guards the complete shared friction function at `5B86`,
the common response/integration window `738F..741E`, and coordinate/actor
writeback at `7530`. All three affected far-call relocation words are checked
against the owned child's loaded image before hooks are installed.

## Production Correction

The real C++ diagnostic initially failed 180 helper cases, 145 caller cases
(150 failed checks because five cases fail two caller checks), and 136
visual-coordinate cases; all timer cases already matched. The
negative checkpoint is commit `0f592b4`. Preserved source hashes bind both
the actual failing and passing executables to their capture-time sources.

- Shared floor friction uses a signed WORD absolute value. `-32768` remains
  negative and is cleared by the signed `<43` test, rather than becoming
  widened positive 32768.
- Side reflection narrows native NEG to a WORD before signed division by two.
  Reflecting `-32768` therefore yields `-16384`, not `+16384`.
- Timed X/Y integration retains signed WORD coordinate writes. Small-bomb
  collision-space subtraction and visual-space addition also wrap separately.
- Monster rendering uses the same signed visual-Y projection, including
  hotspot addition. The diagnostic calls that production projection; it does
  not normalize a wrong renderer result inside its comparison.

After these corrections all 1,184 helper updates and all 1,184 actual
`updateMonsters()` / `updateBombs()` calls match position, velocity, fractions,
timer parity, RNG and visual descriptor. The existing wide integrator is
unchanged; narrowing is at the original actor word boundaries.

Because friction is shared with players, a separate compiled diagnostic scans
all 65,536 signed WORD inputs through the helper and grounded/airborne idle
player call paths. Its oracle emulates the guarded native CWD/XOR/SUB and
signed comparison, not newly captured live original inputs. Widened-absolute,
threshold and friction-step variants are discriminated. Existing original
player walking, death, bomb, corpse and boss replays remain regression gates.

## Fixture and Evidence

`tests/fixtures/timed_actor_writeback_original.bin` has a 64-byte header and
1,184 80-byte records: 20 seed bytes, 14 motion/RNG bytes, 38 actor bytes and
eight visual bytes. Size is 94,784; SHA256 is
`a92403df344368bb2975fd570d25dbb37dd4bc9d7ae755905cb9a8ae4b8bccb2`;
the real CLI's FNV guard is `8f14c29f203ed0ca`.

`evidence/timed_writeback_20261005/native-captures.tar.gz` retains all four
complete captures, executed discovery and production sources, capture logs,
negative/positive source snapshots and replay receipts. It has 60 files,
16,728,115 uncompressed bytes and 1,288,451 compressed bytes. SHA256 is
`2b249ee5799ccdc1984ac729201d7785b285be5da9eee8d16fbb03f8918b21f8`.
The checker validates every member and re-extracts all four fixture copies.
Source reconstruction is explicit and accepted only when it matches the
capture-time source hash exactly. Executables and extra failed discovery/QA
material are retained separately as supplementary evidence.

Seven CTests cover real callers, fixture structure, every single-byte fixture
mutation, 18 malformed real CLI inputs, raw retained evidence, observer
self-check and exhaustive compiled friction. Fresh original CI re-extracts
the fixture. The shared observer keeps behavior-4 defaults unchanged; its
176/256/768/1,312-case original fixtures remain independent regression gates.

The fresh Linux boss checkpoint renders the existing controlled level-7
3,200-update replay: all 15 crops match, totaling 711,360 pixels with zero
differences. `cpp_boss_1599.png` is a nearest-neighbor preview of the byte-exact
312x152 gameplay crop. Its original reference is the retained October 1
capture, not a newly played natural campaign.

## Remaining Scope

This is seeded, animation-disabled timed motion and writeback evidence. It
does not establish natural constructors, timer expiration/removal, complete
animation playback, simultaneous actors, other behaviors, full campaign
completion or whole-game visual parity. All broad OPEN items stay OPEN:
`natural_forward_debris_writeback_3d2d`, `exact_explosion_sprite_playback`,
`actor_update_original_contact_semantics`, and `behavior4_motion_runtime_fixture`.
`port_functionally_complete=0`, `original_fidelity_claim=0` and `visual_claim=0`.
