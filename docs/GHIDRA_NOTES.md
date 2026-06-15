# Ghidra Notes for LEZAC.EXE

Ghidra 12.0.4 imports `LEZAC.EXE` as:

- Loader: `Old-style DOS Executable (MZ)`
- Language: `x86:LE:16:Real Mode`
- Entry: `1000:7783`
- Header size: `0x770`

`--debug-shipped-file-manifest` pins the oracle file set used by these notes:
14 shipped files, aggregate size `193537`, `LEZAC.EXE` size `52384`, MZ header
paragraphs `119`, image base `0x0770`, and image size `50480`. This keeps
Ghidra offset-to-file-offset assumptions tied to the exact binary currently in
the repository.

The executable is a Borland/Turbo Pascal DOS program. The original on-disk far
segment references are relocated by the MZ loader. For example, the on-disk call
bytes targeting `082d:0000` are relocated by Ghidra into memory at
`182d:0000`.

## Confirmed Routines

| Address | Name | Notes |
| --- | --- | --- |
| `1000:06ab` | animation state initializer | Writes the seven-byte animation cursor used at `actor + 0x16`: current/start/end/counter/delay/mode/step. |
| `1000:0c33` | level loader | Opens/seeks in `LIVELS.SCH`, reads the level header, allocates level buffers, reads compressed layers and entity blocks. |
| `1000:0630` | load PROEFS.SON | Opens `PROEFS.SON`, reads step count `0x0082`, allocates and reads `0x82 * 6` payload bytes. |
| `1000:0faa` | level loader wrapper | Sets up stack frame and calls `1000:0c33`. |
| `1000:0fbe` | sound tick / INT 1Ch playback | Uses `DS:79c4`, `DS:78c0`, `DS:79a0..79a2`, and the `DS:79c0` sound-bank far pointer to drive PC speaker output. |
| `1000:165a` | queue sound if priority allows | Latches pending sound cursor/priority from `DS:2074`/`DS:799f` into `DS:78c0`/`DS:799e` when no sound is active or the new priority can preempt. |
| `182d:0000` | `rle3_decode` | Decodes the two `LIVELS.SCH` compressed layers from 3-byte run commands. |
| `1000:2efd` | new game state | Opens `LIVELS.SCH`, initializes player state, lives/energy flags, and level globals. |
| `1000:3358` | remove actor slot | Compacts 0x26-byte actor records and adjusts ordering in other active lists. |
| `1000:3587` | update camera | Computes tile-aligned scroll offsets from player coordinates and level dimensions. |
| `1000:370e` | tile fragmentation/collapse | Marks damaged tiles and queues 0x0b-byte falling/debris records. |
| `1000:1091` | keyboard IRQ handler | Reads port `0x60` and tracks scancodes for both players. |
| `1000:26e8` | startup/input setup | Sends keyboard typematic commands, saves `INT 09h`/`INT 1Ch`, installs handlers, and allocates runtime buffers. |
| `1000:6053` | entity update candidate | Updates object animation, positions, controls, and collision/object behavior. |
| `18ac:00f4` | transparent blit/object draw | Copies sprite pixels with zero treated as transparent. Palette index `0xff` is visible. |

`--debug-sprite-blit-contract` exercises that blit rule through the C++ renderer:
source index `0` preserves the destination framebuffer, while every nonzero
source index is copied through the active palette, including visible `0xff`.

Ghidra decompilation is not very useful for the Pascal code because of 16-bit
segmented pointers and runtime helper calls, but disassembly was useful enough
to confirm the file and RLE formats used by this port.

## Level RLE

The routine at `182d:0000` takes source and destination far pointers plus a
target output length. It does not use the compressed byte count directly; the
record length is used by the caller to advance in the level file.

Each command is:

```text
u8 command
u8 first_value
u8 second_value
```

The high nibble of `command`, plus one, is the first run length. The low nibble,
plus one, is the second run length. The Pascal routine writes each run with an
inclusive loop and then advances by the nominal run length, so adjacent runs
overwrite one byte at the boundary. The C++ port preserves this compatibility
quirk.

## Confirmed Data Files

- `BOMPAL.PAL` is exactly 768 bytes: 256 VGA RGB values using 6-bit channels.
- `SFONLEF.ZBG` starts with a 768-byte palette and then PCX-style RLE bytes
  for a 321x388 indexed background.
- `CARO.CAR` starts with a big-endian 16-bit tile count, followed by raw 8x8
  indexed tiles.
  `--debug-core-resource-raw-roundtrip` verifies all three raw files against
  the converted JSON resources: `BOMPAL.PAL` size `768`, `SFONLEF.ZBG` size
  `34292`, decoded background pixels `124548`, `CARO.CAR` size `8450`, tile
  count `132`, tile payload `8448`, and checksum-style sums/XORs pinned in
  CTest.
- `FONTS.SPR`, `PROVA.SPR`, and `BOMOMIMK.SPR` start with an 8-bit sprite
  count. Each sprite then has 8-bit width, 8-bit height, and raw indexed pixels.
  `FONTS.SPR` stores large `A-Z`, compact `A-Z`, compact `0-9`, then period,
  colon, semicolon, comma, exclamation, and apostrophe/accent glyphs.
  `--debug-sprite-raw-roundtrip` verifies the converted JSON for all three
  sprite banks matches the shipped raw layout byte-for-byte: 250 sprites,
  46,843 raw bytes, 46,340 pixel bytes, 21,396 zero pixels, 24,944 nonzero
  pixels, and 369 visible `0xff` pixels.
- `RECS.DAT` starts with an 8-bit record count. Each record is a little-endian
  32-bit score, an 8-bit reached level, and an 8-byte name padded with `:`.
  `--debug-records-raw-roundtrip` verifies the shipped 92-byte file against
  `src/RECS.DAT.json`: seven 13-byte records, all level `8`, all encoded names
  `aga:::::`, score sum `3508890`, top `541200`, cutoff `474930`, byte sum
  `6047`, weighted byte sum `278918`, and XOR `0xdd`.
- `PROEFS.SON` starts with little-endian word `0x0082`. Disassembly of
  `1000:0630..06aa` treats this as a count of 130 six-byte sound steps and
  reads `0x82 * 6 = 780` payload bytes into the sound bank. The converted JSON
  still preserves the same payload as six 130-byte chunks for compatibility
  with the earlier approximate renderer; `--debug-son-raw-roundtrip` verifies
  that no payload bytes are lost.
- `GRAN.MST` has no observed header in the shipped file. It is seven fixed-size
  57-byte records, likely aligned with the seven shipped levels, but the field
  semantics are still unresolved. Runtime JSON loading now rejects any converted
  shape other than `7 * 57` bytes, and `--debug-gran-raw-roundtrip` verifies
  the converted JSON bytes exactly match the shipped 399-byte file. The
  roundtrip also pins an opaque byte profile for comparison work only:
  aggregate `byte_sum=12560`, `weighted_sum=337318`, `nonzero_bytes=249`,
  `zero_bytes=150`, `xor=0x0c`, and record sums
  `631,2230,1389,1242,1780,2720,2568`.
  `tools/check_gran_usage_guardrail.py` confirms the current C++ port only
  loads, stores, validates, and debug-prints those opaque records; no live
  gameplay or rendering path may consume `GRAN.MST` without first adding
  evidence.
- The C++ loader now defaults to the shipped files themselves, while
  `LEZAC_LOAD_JSON_ASSETS=1` keeps the converted JSON path available for
  diagnostics. `--debug-original-asset-load` verifies that the original-asset
  path produces the same runtime palettes, background, tiles, sprites, records,
  sound payload, GRAN bytes, and level structures as the JSON path.

## Level Entity Blocks

After the two compressed `LIVELS.SCH` layers and two extra words, the level
loader reads three counted fixed-size blocks:

- 30-byte records are monster spawners. The runtime loop around
  `1000:7a6b-7c2c` checks enabled/budget/live-count/cooldown fields and creates
  active 0x26-byte actor records. Observed monster kinds are `1`, `2`, `3`, `4`,
  `6`, and `9`. Spawned actors retain a source-spawner id so actor removal can
  return the live slot to the spawner. The fatal damage branch at
  `1000:74a6..7513` sets state `2`, kind `0x0c`, timer `0x19`, and, when
  `actor+0x25 > 0`, immediately returns the source live slot around
  `1000:74e6..74f9`; the later death-timer removal must not return it a second
  time.
  The last two bytes are split in runtime use: byte `0x1c` reloads the spawner
  cooldown and byte `0x1d` is passed to the actor animation initializer as a
  delay value.
- In the shipped level records, the normal monster kinds observed are `1`, `2`,
  `3`, and `4`. The executable uses lookup tables rather than the monster kind
  as a direct sprite index. The currently confirmed zero-based `BOMOMIMK.SPR`
  normal animation ranges are: player 1 `0..18`, player 2 `19..37`, kind 1
  left `43..44`, kind 1 right `45..46`, kind 2 `39..41`, kind 3 `49..51`, and
  kind 4 `53..55`. The adjacent frames `42`, `47`, `48`, `52`, and `56` are
  impact/extra frames from related tables, not ordinary looping frames.
- `LIVELS.SCH` contains 15 enabled monster spawner records across levels 1..6;
  level 7 has none. Their shipped monster-kind counts are kind 1: seven, kind
  2: two, kind 3: three, and kind 4: three. Behavior values are behavior 3:
  nine records and behavior 4: six records.
- Monster reward sprites follow `BOMOMIMK.SPR` indices `61..67`, matching the
  score table sequence found near executable file offset `0xb1c6`:
  present `61`/2000, first aid `62`/1000, hot dog `63`/1500, jolly cloud
  `64`/2000, yellow bomb box `65`/3000, green bomb box `66`/1000, and big
  diamond `67`/5000.

## Actor Movement Behaviors

The shipped spawners use actor behavior values `3` and `4`.

- Behavior `3` is a ground walker. The C++ reconstruction uses randomized actor
  parameter `ai0` as an 8.8 fixed-point horizontal speed magnitude, applies
  gravity, and flips direction/profile on wall or ledge collision.
- Behavior `4` is timed retarget/random movement. The reconstruction uses `ai0`
  as the retarget tick period, `ai1` as 8.8 fixed-point movement magnitude, and
  `ai2` as the Manhattan-distance threshold for chasing the player before
  falling back to random signed velocities. Each active actor carries its own
  countdown so actors spawned at different times do not retarget in lockstep.

These mappings follow the Ghidra analysis around `1000:70bc..7148` and
`1000:728c..731b`.

Active monsters now use the original-style signed 8.8 velocity fields and
fractional accumulator bytes. The integration helper mirrors the byte-carry
logic at `1000:73e5..741b`: add the low velocity byte to the fractional byte,
then add the signed high velocity byte plus carry to the integer position. This
preserves the original floor-style behavior for negative fractional velocities.
`--debug-monster-motion-model` now locks that 8.8 carry behavior and the current
behavior `3`/`4` branch hypotheses in a synthetic fixture, including kind-1
directional frame selection and behavior-4 countdown retargeting. This is a
regression oracle for the current reconstruction model, not proof that the
remaining AI/collision rules are exact.
`--debug-behavior4-runtime-oracle` is the normalized evidence parser for future
DOSBox-debug behavior-4 captures. It requires runtime `CS`/`DS`, semantic
spawner and actor before/after records, target/player-dead state, and
breakpoints covering the spawner loop `1000:7a6b..7c2c`, behavior-4 branch
`1000:728c..731b`, and 8.8 integration `1000:73e5..741b`; optional `DS:` dumps
are segment-checked and byte-counted. Current checked-in fixtures are synthetic
or malformed parser coverage only and carry `visual_claim=0`.
`tools/check_behavior4_runtime_oracle_fixtures.py` keeps that fixed synthetic
baseline while allowing future `behavior4_runtime_oracle_original*.txt`
fixtures only when they parse as valid runtime evidence and have matching CTest
coverage.
`tools/check_optional_original_oracle_fixtures.py` keeps the behavior-4,
actor-update, and contact-scanner optional-original fixture gates aligned.
`tools/check_visual_claim_guardrail.py` requires every checked-in DOSBox oracle
fixture to carry an explicit `visual_claim=0` or `visual_claim=1` line; claims
remain `0` unless original frame/presentation evidence has been promoted.
Promoted fixture entries must be recorded in
`docs/recovery/visual_claim_promotions.md` with original, C++, comparison frame
artifacts, and a checked-in frame-compare bundle whose summary reports
`promotion_ready=1`. The CTest self-test for
`tools/check_visual_claim_guardrail.py` exercises a synthetic promoted fixture
and rejects missing checked-in artifacts or unready bundles.
Original-runtime fixtures that came from DOSBox/debugger captures are tracked
separately in `docs/recovery/runtime_evidence_ledger.md`.
`tools/check_runtime_evidence_guardrail.py` requires every checked-in original
runtime fixture to remain `temp_copy=1`, include runtime `CS`/`DS`, and keep
`visual_claim=0` until there is separate rendered-frame evidence. The fixture
ledger points to `docs/recovery/original_runtime_fixture_notes.md`, and the
checker requires that supporting note to name each fixture it backs.

The C++ collision/passability model currently treats destruction-progress tiles
as solid except passable object cells. A cell is passable when its tile is the
portal tile `0x45`, a bomb-object tile `0x67..0x72`, or when its decoded
word-layer value is a nonzero low physical-object word (`word < 0x4000` and not
flagged damaged). The low-word rule is a gameplay-model fix for level 1 object
columns and panels that visually belong to pass-through object groups; high
word-layer floor/link markers remain solid unless their tile id is already a
known passable object. Player collision samples a 12x16 footprint; monster
collision samples a 14x16 footprint. `--debug-passable-objects` verifies the
decoded levels contain portal, bomb-object, low-word object, high-word solid,
and solid examples, then checks full actor footprints, consumed bomb-object
tiles, and a level 1 start-route movement probe against the passability helper.
The 2026-04-24 live collision pass keeps those cells pass-through while allowing
bomb-object and low-word object cells to act as jump support when sampled under
the player's feet. `--debug-object-collision-jump-live` locks that behavior on
a level-1 object cell and verifies the level-1 bomb route still passes through
the object columns.
`--debug-autoplayer level1_bomb_route` drives that route through the update
helpers and frame-inspects the route, bomb, and explosion checkpoints.
`--debug-collision-pushout` locks the current model by forcing horizontal and
vertical player/monster collisions into a synthetic solid tile, then asserting
the actors finish clear. It covers behavior-3 full horizontal reversal/vertical
stop and behavior-4 half reversal with retarget timer reset. Exact original
clearance rules inside
`1000:6053..777f` still need more disassembly or DOSBox-debug runtime evidence.
`--debug-actor-update-runtime-oracle <fixture> [--expect-error]` is now the
normalization target for that evidence. Its checked-in fixtures are synthetic
parser coverage for runtime `CS`/`DS`, contact scanner anchors
`1000:5cb0..604f`, actor-update anchors `1000:6053..777f`, actor before/after
state, contact flags, tile probes, and raw `DS:` dump rows; they do not claim
exact original collision geometry. `tools/capture_original_actor_update_debug.sh`
records the matching debugger command plan and labels current captures
`debugger_seeded` until full gameplay-route evidence is available. Its
`candidate_fixture.txt` is a fill-in normalization skeleton, not evidence until
runtime fields and dump rows are captured. Short WSL/Xvfb live launch probes now
reach the DOSBox-debug prompt and let the helper preserve runtime `CS`/`DS`
metadata plus a runtime-translated `debugger_commands_runtime.txt`, but semantic
breakpoint submission is still pending.
`--debug-contact-scanner-runtime-oracle <fixture> [--expect-error]` narrows that
contract to the scanner window only: subject/other actor boxes, overlap size,
contact flags, pending damage, runtime `CS`/`DS`, and breakpoints at
`1000:5cb0` and `1000:604f`. `tools/capture_original_contact_scanner_debug.sh`
records the scanner-only debugger command plan and keeps those captures labeled
`debugger_seeded` until a full gameplay route proves the same state naturally.
Its `candidate_fixture.txt` is a skeleton for transcript normalization, not
evidence until runtime fields and dump rows are filled; live launch attempts
also preserve prompt `runtime_cs`/`runtime_ds` metadata and a concrete runtime
command plan for later address translation.
The actor/contact fixture expectation checkers deliberately keep the
synthetic/malformed parser fixtures fixed while permitting future
`actor_update_runtime_oracle_original*.txt` and
`contact_scanner_runtime_oracle_original*.txt` fixtures only when they parse as
valid runtime evidence and have matching CTest coverage. Any checked-in
original fixture still remains `visual_claim=0` until the separate visual
promotion ledger is satisfied.
Because command submission to this DOSBox-debug prompt remains unreliable, the
guarded `tools/capture_original_actor_contact_procmem.sh` wrapper can prove
reachability by writing a temporary `EB FE` freeze loop into the child
DOSBox-debug process after the known route starts. A 2026-05-11 probe froze
`1000:6053` at runtime `01ED:6053` with original bytes `55 89` and runtime
`DS=0C8F`; this is instrumentation evidence only, not a promoted semantic
actor/contact fixture. A first `1000:5CB0` contact-scanner-start probe loaded
the same `EB FE` runtime patch at `01ED:5CB0` but did not freeze on the default
level-1 route, so the scanner path still needs a tuned contact/collision route.
The process-memory route dumps now preserve `DS:7900`, `DS:79E0`, and `DS:7A00`
for actor/contact candidate scaffolds. A longer `x:5.0,m:0.5,x:2.0` scanner
route reached active level-1 state but still did not freeze `1000:5CB0`; the
matching pre-route patch run also did not freeze, so the next scanner probe
should use a different live contact route or revalidate the entry anchor. The
actor/contact route sweep added after that result also missed `1000:5CB0` on
`x:8.00` and `x:5.00,m:0.50,x:4.00`; a `1000:604F` probe on the latter route
loaded runtime bytes `c9 c2` and did not freeze, consistent with a return-tail
anchor rather than a useful entry breakpoint. Static near-call scanning of the
loaded code image found the scanner entry's only direct call at `1000:6555`
inside actor update (`e8 58 f7` -> `1000:5CB0`), so
`contact_scanner_callsite` is now a probe target. The first live callsite probe
on `x:5.00,m:0.50,x:4.00` loaded `01ED:6555` but also did not freeze,
indicating that route still does not reach the scanner callsite.
`tools/check_actor_contact_callsite_context.py` further pins the local branch:
`1000:654E` compares `[bp-31h]` with `06`, `1000:6552` skips to `1000:655B`
when the value differs, the matching path executes `push bp; call 1000:5CB0`,
and `1000:6558` jumps into the shared `1000:73E5` integration path. The next
runtime probe should therefore target a route or seeded state that makes the
`06` case live before spending more effort on entry-only breakpoints.
The same static checker now also locks the neighboring `05` gate at
`1000:65A2`: its integration path enters through `1000:65D7`, while the
alternate end path jumps to `1000:777F`. Within `1000:6053..777F`, the only
direct near jumps to the shared integration entry are now checked as
`1000:6558` and `1000:65D7`. These are exposed as
`capture_original_actor_contact_procmem.sh` targets `actor_update_gate5`,
`actor_update_gate5_integration`, and `actor_update_gate6` for the next live
route sweep. `tools/check_actor_update_dispatch_gates.py` additionally scans
the actor-update window for every `cmp [bp-31h], imm` gate and currently locks
`1000:654E = 06`, `1000:65A2 = 05`, and the later `1000:7595 = 05` exit gate
to `1000:777F`; that late gate is exposed as `actor_update_gate5_exit`.
`tools/sweep_original_actor_dispatch_gates.py` plans or runs the mapped gate
set as one matrix so the next DOSBox pass can test all gate reachability with
the same route and timing inputs. `--debug-actor-update-runtime-oracle` now
reports optional `dispatch_gates=` names from these breakpoints when they are
present in a normalized fixture. `tools/summarize_actor_dispatch_gate_sweep.py`
follows a completed dispatch-sweep manifest and reports capture counts, observed
freeze targets, missing targets, candidate readiness counts, and candidate
fixtures ready for oracle normalization; each freeze line also labels candidate
readiness, the expected runtime oracle flag, and an `oracle_command=` using the
configured C++ binary path. Placeholder detection scans the whole candidate
file, including commented skeleton hints, while required-record checks only use
active fixture lines. `--require-ready` turns the summary into a promotion gate
by returning nonzero whenever an observed freeze has a missing, incomplete, or
absent candidate fixture. `--write-ready-manifest` writes a small follow-up
manifest containing only ready fixtures and their oracle commands.
`tools/run_actor_dispatch_ready_manifest.py` can then dry-run or execute that
handoff without copying shell lines out of the summary output; it rejects
missing fixture paths and mismatched oracle/flag pairs before execution, and
can write a result manifest for the planned or executed oracle commands. Result
manifests and logs are expected to stay outside the repository by default.
`tools/summarize_actor_dispatch_ready_results.py` summarizes that result
manifest and can gate promotion on successful executed oracle runs.
The generic behavior-4/actor-update/contact-scanner debug-capture handoff now
has the same final review step:
`tools/summarize_debug_capture_ready_results.py` summarizes result manifests
from `tools/run_debug_capture_ready_manifest.py` and can require successful
executed candidates with verified per-candidate environment preflights before
promotion. `tools/check_debug_capture_ready_pipeline.py` covers the full
synthetic handoff so future capture tooling changes cannot break the promotion
path silently.

## Bomb Inventory

The original tracks four bomb counts rather than a single radius. New-game setup
initializes the single-player inventory to `200, 20, 6, 0`; the fourth, strongest
bomb type starts unavailable. Left+right together cycles to the next nonempty
weapon. Fire consumes one count from the selected weapon and then places a bomb
actor. Yellow bomb boxes replenish the normal set, while green bomb boxes
replenish/unlock the super set.

The reconstruction now models that inventory and switching. Bomb placement uses
the actor kind mapping `0x0d..0x10` and fuse values `20, 30, 40, 200` from
`1000:6bdf..6c59`; those values are countdown ticks, not blast radius.
Expiration processes the original-style 2x2 tile footprint:
`(x,y)`, `(x+1,y)`, `(x+1,y+1)`, `(x,y+1)`.

Only object tiles `0x67..0x72` are consumed directly by the bomb helper at
`1000:5afd`. When that helper enables physical damage, the reconstruction now
routes the tile above the footprint cell through a `1000:370e`-style word-layer
path: bit `0x8000` means already damaged, words `>0x3fff` enqueue one deferred
debris record, and lower words flood-fill a matching connected group and enqueue
a collapse record. The high-word 11-byte debris payload is represented with its
known fields; the lower-word collapse payload remains provisional until its
playback routines are fully mapped.

Bomb actor expiration at `1000:75f1..75fb` calls the dispatcher at `1000:414a`
with a selector derived from the actor kind. The selector branches are `1..4`;
the dispatcher then sets state/sound selectors `4..7` and record offsets
`0xea74`, `0xea7e`, `0xea88`, and `0xeace`. The visible parameter packs
reference sprite/effect ids `0x84..0x89` and seed per-variant bytes
`8/5`, `9/5`, `9/3`, and `0x3a/0x0a` alongside a fixed detail byte `0x75`.
The C++ reconstruction carries these selector/state/offset fields in a typed
explosion effect and renders a simplified local effect until the exact playback
routines are fully mapped.

The live C++ update pass now resolves expired bombs before monster movement for
the current frame. This preserves the original-style blast overlap expectation
for actors that are already inside the footprint when the fuse expires, while
leaving exact explosion sprite playback blocked on `1000:3a56..4d3b`.
`--debug-monster-bomb-kill-live` locks same-frame blast damage, fatal monster
state entry, reward presence, and death actor removal.

Static disassembly of `1000:370e` with the MZ image base at file offset `0x770`
confirms it is a tile damage queue helper, not a late renderer. It reads the
word layer through the far pointer at `DS:6612`, skips words already carrying
bit `0x8000`, and splits the remaining work at threshold `0x4000`.

The high-word debris branch in `1000:370e` increments `DS:207e` before writing
an 11-byte record at `0x2093 + 0x0b * DS:207e`, so the first original-written
record is `DS:209e`: word tile index, word `word | 0x8000`, byte argument pair,
three zero bytes, one lookup byte from the far-pointer source stored at
`DS:c1e0`, and a final zero byte. Any reconstruction-only lifetime is separate
from that payload.

The low-word collapse branch increments `DS:2080` before writing a 15-byte
record at `0x6611 + 0x0f * DS:2080`, so the first original-written record is
`DS:6620`. The payload is start byte offset, end byte offset, stored flagged
word, lane/input bytes at `+6/+7`, a word `abs(arg0) + abs(arg1)` at `+0a`,
and affected-byte count at `+0e`. A fresh original level-1 route capture
matched the C++ bomb object route for the first collapse rectangle
(`0x0a06..0x0a08`, word `0x0009`, flagged `0x8009`, affected bytes `4`);
broader low-word grouping remains a model until more original rectangles are
compared.

The playback helpers at `1000:3a7e` and `1000:3b18` are forward/reverse lookup
passes. They split damaged words on bit `0x8000` and threshold `0x4000`, then
load the forward byte from collapse/debris record offsets `+6`/`+4` and the
reverse byte from offsets `+7`/`+5`. The collapse passes at `1000:3bb2` and
`1000:3d46` write those lanes back through `0x6617`/`0x2097` and
`0x6618`/`0x2098`, using `0x4e20` as the high-half spill marker. Static
disassembly now ties that lane model to the live effect/debris consumer:
`1000:45fa..4d3b` iterates the 11-byte queue records, calls the forward pass at
`1000:4c96` with `DS:78d2`, then calls the reverse pass at `1000:4ca9` with
`DS:78d4` after ORing the current word with `0x8000`. The same routine removes
expired queue slots through `1000:452a`/`1000:458d`, so the queue lane bytes are
confirmed as mutable playback state rather than write-only creation metadata.
`--debug-damage-queues` now locks these original consumer offsets, the
one-based collapse/debris slot tags, the first-slot lane write addresses
(`DS:6626`/`DS:6627` and `DS:20a2`/`DS:20a3`), and the collapse span weight
from record offset `+0e`.

Static disassembly of `1000:3bb2` and `1000:3d46` shows both lane blenders
take a far pointer at `[BP+4]` and a byte weight at `[BP+8]`, loop over the
one-based staging count in `DS:2078`, read staging words from `DS:655c + 2*i`
and target offsets from `DS:6598 + 2*i`, and record selected output tags in
`DS:65d4 + 2*i`. Tags below `0x4e20` select collapse records; tags at or above
`0x4e20` select debris records after subtracting the marker. The forward helper
calls lookup routine `1000:3a7e` and writes the blended byte to
`DS:6617 + 0x0f*slot` or `DS:2097 + 0x0b*slot`; the reverse helper calls
`1000:3b18` and writes to `DS:6618 + 0x0f*slot` or
`DS:2098 + 0x0b*slot`. Both helpers also write the result back through the
input far pointer. They call far routine `0920:0945` after accumulating signed
input/weight terms. That far routine is a signed 32-bit division helper:
callers pass the accumulated numerator in `DX:AX`, pass the positive weight
sum in `BX:CX`, and consume quotient byte `AL` as the blended lane result.
The quotient rounds toward zero and the remainder keeps the dividend sign; a
zero divisor branches through `0920:09ac` with `AX=0x00c8` before entering the
runtime error path. The lookup helpers store the neighbor lane byte in
`DS:661e`, and the lane blenders multiply that signed byte by the unsigned
record weight before adding it to the numerator. `--debug-lane-helper-model`
locks the data flow and `--debug-lane-blend-arithmetic` locks the division
contract before any live playback behavior is changed.

A 2026-04-28 original runtime-child-memory capture now freezes the forward
lane blender at `1000:3cd4`, just before it loads the far division helper
registers. The promoted
`explosion_playback_oracle_original_3cd4_lane_div_scratch_runtime.txt` fixture
records scratch `CS:3d24` with would-be `DX:AX=0xffff:0xfff8`,
`BX:CX=0x0000:0x0005`, active staging count/index `1`, and the matching
locals `[BP-8]=0x0005`, `[BP-4]=0xfff8`, `[BP-2]=0xffff`. It also captures live
lane globals `DS:2074=1`, `DS:655e=0x8009`, and `DS:659a=0x0a7a` in the same
held playback frame. This is still instrumented evidence with `visual_claim=0`,
but it directly ties the static signed-divide model to one original
mid-helper execution. Temp-copy lane-div instrumentation is intentionally
blocked because the larger scratch body can overlap DOS relocation words near
the far-call operand; use runtime child-memory patching for these stops.
A follow-up 2026-04-29 runtime capture freezes the actual forward divide call
at `1000:3ce3`. The promoted
`explosion_playback_oracle_original_3ce3_lane_div_scratch_runtime.txt` fixture
records the already-loaded registers `DX:AX=0x0000:0x001c` and
`BX:CX=0x0000:0x0010`, with matching numerator/weight locals. Immediate
runtime probes at reverse setup/call sites `1000:3e68` and `1000:3e77` loaded
their patches but did not freeze on the same route, so no reverse-helper
scratch fixture is promoted yet.
A later 2026-04-29 runtime capture freezes the forward collapse writeback at
`1000:3d1b`, before the original `mov [di+0x6617],al` executes. The promoted
`explosion_playback_oracle_original_3d1b_lane_write_scratch_runtime.txt`
fixture records output byte `0x01`, selected tag `0x0003`, loop index/count
`1/1`, and `DI=0x002d`, matching `tag * 0x0f`. This directly proves one
original helper lane byte about to be written to collapse offset
`DS:6617 + 0x002d = DS:6644`.
A same-day safer lane-write probe replaces only the target instruction with a
three-byte near jump and parks the runtime scratch/freezing body at `CS:f000`
with scratch at `CS:f080`. That removes the earlier risk of overwriting the
shared writeback loop join. The promoted trampoline fixtures show a forward
collapse stop at `1000:3d1b` with output `0x04`, tag `0x0004`, and
`DI=0x003c`, plus a reverse collapse stop at `1000:3eaf` with output `0x00`,
the same tag, and the same `DI`. The tag relation remains `tag * 0x0f`, so the
route now proves both collapse writeback bases:
`DS:6617 + 0x003c` and `DS:6618 + 0x003c`. Safe trampoline probes at
`1000:3d2d` and `1000:3ec1` loaded but did not freeze on this route; debris
writeback still needs a different route or debugger-seeded setup.
Labeled runtime-seeded fixtures then patch the original `4c96`/`4ca9` helper
call sites to seed `DS:655e=0xc004` before calling the original helper bodies.
Those fixtures are not full gameplay-route evidence, but they prove the debris
writeback branch arithmetic: both forward `1000:3d2d` and reverse `1000:3ec1`
resolve selected tag `0x4ee8` to `DI=0x0898`, matching
`(0x4ee8 - 0x4e20) * 0x0b`. The forward seeded result byte is `0x35`; the
reverse seeded result byte is `0x00`.
`tools/capture_original_lane_write_runtime.py` and
`tools/sweep_original_lane_write_routes.py` now provide the guarded natural-route
capture path for those debris-side writeback offsets. Their safe preflight pins
the shipped target bytes (`1000:3d2d` = `88 95 97`, `1000:3ec1` = `88 95 98`),
scratch block `CS:f080`, scratch length 12, and trampoline body length 45
before any DOSBox/process-memory capture is attempted.
`tools/summarize_lane_write_route_sweep.py` classifies completed manifests as
ready/no-freeze/incomplete/missing and intentionally rejects runtime-seeded
fixtures as natural-route promotion candidates. The matching
`tools/run_lane_write_ready_manifest.py` and
`tools/summarize_lane_write_ready_results.py` wrappers share the lane-result
ready-candidate runner while preserving lane-write manifest labels.
The capture helper and explosion playback oracle now also support
`lane-result-cs-scratch` for the final helper far-pointer result writes at
`1000:3d3f` and `1000:3ed3` (`mov es:[di],al`). The runtime scratch body is
parked at `CS:f200`, stores fields at `CS:f280`, and captures the result byte,
`ES:DI`, `[BP+4]`/`[BP+6]`, `[BP-0d]`, active count/index, and the destination
byte before the write. The oracle validates that `ES:DI` equals the passed far
pointer, the stored result byte equals `[BP-0d]`, and the loop count/index are
in bounds. The process-memory helper also refuses to install this trampoline
unless the target bytes are exactly `26 88 05` (`mov es:[di],al`).
`--describe-freeze-patch` can preflight these bytes without launching DOSBox:
`explosion_playback_oracle_lane_result_scratch_synthetic.txt` for forward
`3d3f`, `explosion_playback_oracle_lane_result_reverse_scratch_synthetic.txt`
for reverse `3ed3`, plus malformed coverage for missing fields, wrong observed
kind, bad far pointers, bad output/local values, bad target-byte width, bad
loop bounds, and fields emitted without a scratch-present flag. The oracle also
checks that fixture `freeze_old_bytes` begin with `freeze_expected_old_bytes`,
with malformed coverage for mismatched or missing old-byte evidence. The
original-runtime fixture
`explosion_playback_oracle_original_3ed3_lane_result_runtime.txt` now promotes
one reverse result-write capture: runtime `CS:IP=01ed:3ed3`, `DS=0c8f`,
scratch `01ed:f280`, result byte `0x00ef`, far destination
`18b3:3fe6`, caller far pointer `18b3:3fe6`, result local `0x00ef`, active
count/index `1/1`, and target-before byte `0xde`. The labeled runtime-seeded
fixture `explosion_playback_oracle_original_3d3f_lane_result_runtime_seeded.txt`
promotes one forward result-write capture: runtime `CS:IP=01ed:3d3f`,
`DS=0c8f`, seed call site `01ed:4c96`, helper body `01ed:3bb2`, scratch
`01ed:f280`, result byte `0x00fa`, far destination `0c44:78d2`, caller far
pointer `0c44:78d2`, result local `0x00fa`, active count/index `1/1`, and
target-before byte `0xf3`. The natural route-step fixture
`explosion_playback_oracle_original_3d3f_lane_result_route_step_no_freeze.txt`
records route `x:2.00,c:0.50` loading the forward `3d3f` patch without a
freeze or scratch record; its chosen sample still has
`lane_update_flag=0x05`, `lane_word=0x0004`, `lane_target_offset=0x072c`, and
reverse input `0xfb`. The default/timing-variant/route-step 2026-05-06 routes
loaded the forward `3d3f` patch but did not hit the freeze. A 2026-06-15 WSL
route sweep then promoted
`explosion_playback_oracle_original_3d3f_lane_result_runtime_natural.txt`:
natural route `x:2.00`, runtime `CS:IP=01ed:3d3f`, `DS=0c8f`, scratch
`01ed:f280`, result byte `0x0002`, far destination `0c44:78d2`, active
count/index `1/1`, target-before byte `0x21`, and `runtime_seeded=0`. The same
pass promoted
`explosion_playback_oracle_original_3ec1_lane_write_runtime_natural.txt`:
natural route `x:2.00,m:0.35`, runtime `CS:IP=01ed:3ec1`, `DS=0c8f`, reverse
debris lane-write output `0x00fb`, `DI=0x0898`, tag `0x4ee8`, active
count/index `5/2`, and `runtime_seeded=0`. Natural forward debris writeback at
`1000:3d2d` remains pending. `tools/summarize_lane_result_route_sweep.py`
now classifies completed route-sweep candidates as `ready`, `no_freeze`,
`incomplete`, or `missing`; `tools/run_lane_result_ready_manifest.py` and
`tools/summarize_lane_result_ready_results.py` then execute and gate only
promotable `--debug-explosion-playback-oracle` fixtures. The matching
lane-write handoff uses `tools/run_lane_write_ready_manifest.py` and
`tools/summarize_lane_write_ready_results.py`, preserving the recovered
lane-write kind/target metadata while applying the same runtime segment,
fixture provenance, run/dry-run status, and oracle-log gates.
`tools/check_explosion_evidence_map.py` keeps this explosion/playback handoff
traceable across these address notes, lane-result capture helpers, fixture
coverage, source output fields, and CTest wiring.

The effect constructor at `1000:3fa6` writes 11-byte effect records at
`0x2093 + 0x0b * DS:2076` and stores the effect type byte in
`0x78d5 + DS:2076`. `1000:414a` is the dispatcher profile selector: types
`1..4` call `1000:3fa6` with different argument triples, latch sound cursors
`0xea74`, `0xea7e`, `0xea88`, and `0xeace`, and write sound selectors
`DS:799f=4..7` before calling the sound helper at `1000:165a`. This confirms
the C++ explosion profile diagnostics as static metadata only; exact rendered
sprite timing still needs runtime/frame evidence.

Diagnostic coverage now asserts metadata only for this area: dispatcher states
`4..7`, direct-sweep offsets `0xea74`/`0xea7e`/`0xea88`/`0xeace`, debris stride
`0x0b`, collapse stride `0x0f`, damaged bit `0x8000`, threshold `0x4000`,
forward/reverse phase lookup sources and consumers, and real-asset bomb-object
explosion cases that leave consumed object tiles passable while routing the tile
above the footprint into collapse or debris queues. The live C++ path reads the
recovered sound values through `kExplosionDirectSweepSoundOffsets` and
`kExplosionSoundSelectors`, keeping the `1000:414a` mapping centralized. This is
not evidence for
exact rendered sprites or original frame timing; keep those claims blocked on a
full mapping or runtime capture of `1000:3a56..4d3b`.

### Explosion Runtime Capture Target

Use `dosbox-debug` from a temporary copy when runtime bytes are needed for
explosion/debris/collapse playback. Start with:

```text
dosbox-debug -c "mount c /tmp/lezac-dosbox-explosion" -c "c:" -c "DEBUG LEZAC.EXE"
```

The `DEBUG LEZAC.EXE` wrapper stops at program entry; a current capture attempt
recorded `CS=01ed`, `DS=01dd`, `IP=7783` there. In this environment the
debugger's curses input accepted printable characters through raw PTY, piped
stdin, tmux, and an Xvfb `zutty` terminal captured with `script`, but Enter,
keypad Enter, CR, LF, Ctrl-J, and Ctrl-M were not delivered as debugger command
submissions. The xterm F5 sequence (`\x1b[15~`) did continue into the game. No
explosion breakpoint was reached automatically; treat this as an environment
limitation, not original-game evidence.

When a controllable debugger session is available, translate Ghidra anchors by
keeping the offset and using the runtime `CS`. Useful breakpoints are
`1000:75f1`, `1000:414a`, `1000:370e`, `1000:3a7e`, `1000:3b18`,
`1000:3bb2`, `1000:3d46`, `1000:3fa6`, and `1000:432a`. For the immediate
level-1 collapse route, start a one-player game, move to bomb tile `(24,22)`,
and place a player-1 bomb with `N`; the target tile above is `(24,21)` with
word `0x0009`, expected to flag as `0x8009` and enqueue a two-cell collapse
group.

Record `R`, `U CS:IP`, `D SS:SP`, `D DS:2070`, `D DS:7990`, `D DS:2090`,
`D DS:6610`, `D DS:c1e0`, `D DS:c21e`, and `D DS:c320` after relevant stops.
Normalize the transcript into
`tests/fixtures/dosbox/explosion_playback_oracle_original.txt` only after live
bytes are captured. The checked-in `--debug-explosion-playback-oracle` fixtures
are synthetic parser coverage and keep `visual_claim=0`; they must not be used
as evidence for exact sprite playback. The oracle now decodes the first raw
debris, collapse, and effect records into named fields such as
`debris0_tile_index`, `debris0_flagged`, `collapse0_start`,
`collapse0_word`, `collapse0_flagged`, `effect0_xy`, `effect0_sprite`,
`effect0_timer`, and `effect0_variant`, while still printing the raw byte
lists. `explosion_playback_oracle_missing_effect_byte` verifies incomplete
effect-entry dumps fail instead of producing partial visual claims.
Fixtures may optionally include `selected_debris_base`,
`selected_collapse_base`, or `selected_effect_base` when original runtime
queues contain useful data in a later slot. When `DS:207e` or `DS:2080` are
present, the parser first derives the current debris/collapse bases from the
original one-based counter formulas. Without counters or explicit keys, it
keeps the slot-zero parser defaults `DS:2093`, `DS:6611`, and `DS:c21e`.
`explosion_playback_oracle_sparse_count` verifies that sparse dumps can cover a
high counter-derived debris slot such as `DS:292b` without requiring every
intermediate zero row in the fixture.

An approved process-memory attempt on 2026-04-24 proved a fallback way to find
the LEZAC image/data bytes in a child DOSBox process (`CS=01ED`, gameplay
`DS=0C8F`, data string at `DS:008B`) and added
`tools/capture_original_explosion_procmem.py`. Later route hardening made the
helper reach level 1, place a visible bomb, and capture visible explosion/smoke
playback with selected queue-slot bytes, but that still did not promote an
original fixture because process-memory sampling has not proven a stop inside
`1000:3a56..4d3b`. The helper can now patch only the temporary executable copy
with an `EB FE` freeze loop at a requested Ghidra offset. Instrumented attempts
showed `1000:3fa6` is reached before visible explosion playback and `1000:3a7e`
may be route/timing sensitive, while `1000:3bb2` and `1000:432a` were not
reached by the current level-1 timed route. It also emits
`route_state_samples.tsv` and `route_state_dumps.txt` with timestamped raw
bytes for known route/control ranges (`DS:1b70`, `DS:78c0`, `DS:7990`,
`DS:79e0`) plus explosion/effect ranges (`DS:2090`, `DS:6610`, `DS:c1e0`,
`DS:c21e`, `DS:c320`), so later debugger/freeze attempts can be aligned to
runtime state rather than fixed sleeps alone. The `DS:2090` dump is widened to
the `DS:6610` boundary so high debris counters can be selected from original
bytes instead of score-picked early slots. A follow-up child-memory
instrumentation mode can defer the `EB FE` write until after a route-state
condition; gated probes applied runtime patches at `1000:3a7e` and
`1000:3fa6` after bomb input. `3a7e` did not freeze in that window, while
`3fa6` froze before visible explosion playback. Stronger queue-growth gates
later patched `1000:432a` after selected collapse base `DS:6620` became active;
the patch loaded but did not freeze while visible playback continued. The same
late-collapse gate, with a route-tuned effect threshold, also patched
`1000:3bb2` and `1000:3d46`; both loaded successfully and neither froze while
visible playback continued. Tail-confirmed early-gated probes then froze at
`1000:75f1` and `1000:414a` on armed-bomb frames, while `1000:370e` froze on a
visible explosion frame. A later process-memory run patched `1000:4c96` after
queue growth and confirmed the bytes loaded, but the route continued; patching
the enclosing `1000:45fa` entry with the tuned late-collapse gate froze on a
visible explosion/playback frame with selected bases `DS:209e`, `DS:6620`, and
`DS:c22e`. Patching `1000:492f` also froze on a visible playback frame; that
candidate had `DS:207e=0x00c7`, and static code immediately exits the
high-debris interior unless `DS:207e >= 0x00c8`, explaining why `4c96` and
nearby interior branch probes did not freeze on the current route. This is
still instrumentation evidence with `visual_claim=0`, not a promoted pristine
fixture. See
`docs/recovery/dosbox_explosion_process_memory_attempt_2026-04-24.md`.

Replaying the earlier high-counter route timing with
`--runtime-freeze-require-debris-base 0x292b` let the helper patch
`1000:4c96` while the selected debris slot was counter-derived:
`DS:207e=0x00c8`, selected debris base `DS:292b`, and record bytes
`41 05 04 c0 26 00 1c 00 00 67 80`. The patch loaded at runtime but visible
playback advanced through the tail screenshots, so this run proves the
high-counter queue state and loaded `4c96` patch, not execution of the
lane-call instruction after the patch point.
The next static fork is `1000:4b3f`: after `1000:4b35` confirms nonzero
`DS:2090`, `4b3f..4b5e` samples the target byte that chooses `4b6a`
(zero-target branch) or `4c20` (nonzero-target branch), and `4c75` later gates
the `4c96`/`4ca9` calls on a positive word-layer value. A route-tuned
temp-copy patch at `1000:4b3f` froze on the visible explosion frame with
`DS:207e=0x00c8` and selected debris base `DS:292b`, proving the high-debris
interior reaches the target-byte sample before the unresolved lane-call branch.
The helper now decodes the target fields directly: `DS:2090` delta, target
offset, lookup segment at `DS:c1fe`, word-layer pointer at `DS:6612`,
`DS:c204`, target byte, and target word. A follow-up `1000:4b61` freeze stopped
at the byte gate with target offset `0x0541`, target byte `0x00`, word-layer
value `0x0000`, and `DS:c204=0x003c`; by the static `cmpb $0x0,-0x11(%bp)` /
`je 4b6a` pair, that frozen state chooses the zero-target branch at `4b6a`.
The capture helper can now gate runtime child-memory patching on that decoded
target byte, but two `1000:4b6a` runtime-patch attempts selected the same
counter-derived debris slot later in the route with target byte `0x33`, so no
patch was applied. That makes the target-byte sample a time-sensitive playback
state. A faster process-memory run using `--sample-interval 0.005` and
`--route-state-interval 0` caught the zero-target window and patched
`1000:4b6a` at runtime after `1.436s`: `DS:207e=0x00c8`, selected debris base
`DS:292b`, target byte `0x00`, and word-layer value `0x0000`. The frozen tail
screenshots matched the visible blast frame, so the zero-target branch is now
runtime-observed, though still as instrumentation evidence with
`visual_claim=0`.
Static code at `1000:4c64..4ca9` loads a word through the `DS:6612` far pointer
into `[bp-4]`, checks it at `1000:4c75`, skips to `4cae` when the word is
zero-or-negative, and otherwise calls the forward lane helper from `4c96` and
the reverse lane helper from `4ca9` after OR-ing the word with `0x8000`.
The `damage_queues` diagnostic now locks the surrounding static anchors as
named metadata: the `4b3f` target sample, `4b61` byte gate, `4b6a`/`4c20`
branch targets, `4c64` word load, `4c75` word gate, `4cae` skip target, and
the `DS:659a`/`DS:655e`/`DS:2078` staging globals used before the lane calls.
See `docs/recovery/high_debris_lane_branch_model_2026-04-25.md` for the exact
local byte dump and static interpretation.
Follow-up fast gated probes now freeze `1000:4c75`, `1000:4c96`, and
`1000:4ca9` in the captured high-debris route. A strict `4c96` rerun that also
required collapse base `DS:6611` missed the arming window; relaxing it to the
durable selected-debris base `DS:292b` plus target byte `0x00` froze the
forward lane-call site at `01ED:4c96`. The promoted fixture summaries still
show sampled target bytes and word-layer values from queue state, not the live
`[bp-4]` local at the frozen instruction; by static control flow, the `4c96`
and `4ca9` freezes mean some live iteration took the positive side of the
`4c75` gate. The oracle/capture helper now also names the post-call return
anchors `1000:4c99` and `1000:4cac`. Runtime child-memory attempts at `4c99`
were sensitive to the route window, but temp-copy instrumentation froze both
post-call returns in the high-counter state with selected debris base
`DS:292b`, selected collapse base `DS:663e`, target byte `0x00`, first selected
debris bytes `41 05 04 c0 26 00 1c 00 00 67 80`, and first selected collapse
bytes `06 0a 08 0a 09 80 00 04 00 00 04 00 00 01 04`. These fixtures prove
helper-return reachability and preserve helper-written lane bytes for that
sampled state. A refreshed capture also dumps `DS:78c0`: both return stops show
`DS:78d2=0xf7` and `DS:78d4=0xfc`. The sampled staging globals are zero at the
freezes (`DS:2078=0x00`, `DS:655e=0x0000`, `DS:659a=0x0000`), so the exact
lifetime of the static pre-call staging fields and the live `[bp-4]` local
cannot be inferred from the post-call fixtures alone. A narrower runtime-child
instrumentation mode now patches `1000:4c75` to copy `[bp-4]` into
`CS:4c7e` before freezing. The promoted `4c75` scratch fixture records
`instrumented_bp4_local_value=0x0003` while the sampled selected word-layer
summary is still `0x0000`, proving a positive gate local directly and marking
the queue-summary fields as sampled context rather than the exact loop-local
source.
The later `3cd4` lane-div scratch fixture goes one step deeper into the helper:
it freezes the forward lane blender while `DS:2078=1`, `DS:655e=0x8009`, and
`DS:659a=0x0a7a`, and records the pre-division numerator/weight registers as
`DX:AX=0xffff:0xfff8` over divisor `BX:CX=0x0000:0x0005`. This confirms one
live helper iteration where signed weighted lane accumulation is about to be
divided by the positive weight sum.
The `3ce3` call-site fixture confirms the same register contract after setup
has completed for a later forward-helper iteration: `DX:AX=0x0000:0x001c` and
`BX:CX=0x0000:0x0010` at the far divide call.
The `3d1b` writeback fixture then catches a later forward-helper writeback
iteration: `AL=0x01`, selected tag `0x0003`, `DI=0x002d`, and result local
`[BP-0d]=0x01`, proving the original is about to write the quotient byte to
the collapse lane table via `DS:6617 + DI`.

## Sound Playback Evidence

The original sound loader at `1000:0630..06aa` opens `PROEFS.SON`, reads first
word `0x0082`, multiplies it by six, and reads 780 payload bytes into the
sound-bank far pointer at `DS:79c0`. This means the shipped file is better
understood as 130 six-byte entries than as six original records; the current
JSON chunking is a compatibility container for those bytes.

The tick routine at `1000:0fbe..1088` uses:

- `DS:79c4`: active/request-present flag.
- `DS:78c0`: current sound cursor or direct sweep value.
- `DS:79a0`: tick accumulator.
- `DS:79a1`: gate/off tick.
- `DS:79a2`: step period.
- `DS:79c0`: far pointer to the loaded `PROEFS.SON` payload.

When `DS:78c0 > 0xea60`, the tick routine follows a direct speaker-sweep branch:
it calls the speaker helper with `DS:78c0 - 0xea42`, subtracts four from
`DS:78c0`, and stops when the cursor falls to `<= 0xea60`. The bomb explosion
values `0xea74`, `0xea7e`, `0xea88`, and `0xeace` are therefore direct sweep
cursors, not offsets into `PROEFS.SON`.

The priority latch at `1000:165a..167d` implements:

```text
if DS:79c4 != 0 and (DS:799e - 1) >= DS:799f:
    return
DS:799e = DS:799f
DS:78c0 = DS:2074
DS:79c4 = 1
```

So an inactive latch accepts every request. While active, same-or-higher numeric
priority refreshes/replaces the latched cursor, but one-below-or-lower priority
is rejected. The C++ port maps this to `latchSoundRequest`, `requestSoundOffset`,
and `pumpSoundLatch`; explosion sounds now enter through this path.

Further disassembly of `1000:0fbe..1088` confirms the non-direct `PROEFS.SON`
step shape. On each step advance the routine increments `DS:78c0`, computes
`sound_bank + (DS:78c0 * 6) - 6`, and reads a six-byte entry:

- bytes `+0..+1`: speaker period word. `0x7530` is the stop sentinel; when
  seen, the routine silences the speaker, clears `DS:79c4`, resets `DS:79a0`,
  and sets `DS:79a2 = 1`.
- byte `+2`: copied to `DS:79a1`, the tick value that calls the silence helper
  while the current step is active.
- byte `+3`: copied to `DS:79a2`, the tick value that advances to the next
  six-byte step.
- bytes `+4..+5`: not referenced in this recovered tick window; they are
  preserved as unknown fields.

The current stop-cursor map from the shipped `PROEFS.SON` payload is:
`0x0005, 0x0008, 0x0012, 0x001a, 0x0021, 0x0024, 0x0027, 0x002d,
0x0031, 0x0035, 0x003d, 0x0056, 0x0069, 0x0078, 0x0082`.
`--debug-sound-cursor-segments` validates these boundaries and renders the
known non-direct cursor starts through `synthesizeSoundCursor`.
`--debug-son-step-fields` is a field-only diagnostic for the same raw bank:
it keeps the JSON schema byte-preserving and prints each sampled six-byte step
as `step_index`, `period_word`, `gate_tick`, `period_ticks`, `unknown4`, and
`unknown5`. In the shipped bank, the first step is cursor `0x0001` with
`period_word=0x00f7`, `gate_tick=1`, `period_ticks=1`, `unknown4=0x01`, and
`unknown5=0x02`; the first stop sentinel is cursor `0x0005`, and the final
stop sentinel is cursor `0x0082`. 118 of 130 steps have a nonzero
`unknown4`/`unknown5` pair, but the tick routine window above still does not
interpret those bytes. `--debug-son-tail-field-mutation` mutates bytes `+4..+5`
for every shipped step and confirms the recovered C++ synthesizer renders the
same samples for all known non-direct cursor starts, keeping those tail bytes
preserved but behaviorally unused until original evidence proves otherwise.

Six non-explosion gameplay cues are now mapped to original queued requests:

`tools/check_sound_callsite_map.py` verifies this handoff stays consistent
across these address notes, the C++ request sites, and the CTest scenario names.

- The bomb-object destruction scan around `1000:6cb3..6e3f` clears the
  `DS:2074` score accumulator and `DS:79ab` high-object marker, walks the four
  bomb footprint offsets, sets `DS:79ab = 1` when a consumed object tile id is
  above `0x6c`, and after the scan queues priority `3`. The default request
  leaves `DS:2074 = 0x0000`; high object tiles write `DS:2074 = 0x0012`
  before the `1000:165a` call. The C++ `explode` path mirrors this with
  `requestBombObjectScoreSound`.
- The portal record helper at `1000:5999..5a72` scans the 7-byte portal records
  at `0x7717 + 7 * n` for a matching word-layer key, copies the destination
  coordinates into the actor frame, writes `DS:2074 = 0x001a`,
  `DS:799f = 4`, and calls `1000:165a`. The C++ tile `0x45` transfer path
  mirrors successful portal lookup with `requestPortalTeleportSound`.
- The tile-trigger rewrite helper at `1000:5740..586e` masks its trigger-key
  argument with `0x7fff`, saves the previous `DS:2074`, writes
  `DS:2074 = 0x0027`, `DS:799f = 6`, calls `1000:165a`, restores `DS:2074`,
  and then scans the 14-byte trigger rewrite records. The C++ tile `0x72`
  path mirrors successful trigger activation with `requestTileTriggerSound`.
- The pickup/effect branch around `1000:6e4b..6f8d` applies reward effects and
  then writes `DS:2074 = 0x0008`, `DS:799f = 5`, and calls `1000:165a`.
  The C++ `collectBonusDrop` path mirrors that with
  `requestSoundCursor(kBonusPickupSoundCursor, kBonusPickupSoundPriority)`.
- The per-player damage pass around `1000:7f34..804e` calls the actor update
  routine at `1000:6053`, subtracts accumulated damage from the live player
  energy byte, and when the damage counter is nonzero writes
  `DS:2074 = 0x002d`, `DS:799f = 4`, then calls `1000:165a`
  (`1000:7f84..7f8f`, file offset `0x86f4`). The C++ live path queues damage
  through per-player counters and drains them with `drainPlayerDamageCounters`,
  while direct debug helpers use the same byte-subtraction routine.
- The following life-loss helper at `1000:30a3` is separate from the hurt cue:
  it writes `DS:2074 = 0x0056`, `DS:799f = 5`, calls `1000:165a`, then moves
  the actor into the death/reentry state. The mapped field writes are
  actor byte `+0x15 = 2`, word `+0x10 = 0x003c`, and energy byte
  `+0x24 = 0x64` at `1000:3123..3134`. The C++ `beginPlayerDeath` path now
  mirrors the sound request and energy reset, so fatal damage first queues the
  priority-`4` hurt cue and then replaces it with the priority-`5`
  death/life-loss cue through the original latch rule. The `+0x10` countdown
  remains a visual/state-timing mapping target rather than being treated as the
  C++ reentry timer.

`--debug-sound-callsite-oracle <fixture> [--expect-error]` is the normalized
runtime-evidence gate for these callsites. Fixtures record runtime `CS`/`DS`,
the original request callsite, the `1000:165a` latch breakpoint, the pending
cursor/priority pair (`DS:2074`, `DS:799f`), the latched current cursor/priority
(`DS:78c0`, `DS:799e`), and `DS:79c4` active state. The synthetic fixture covers
the player hurt request and remains `visual_claim=0`; original fixtures should
only be promoted after a real DOSBox-debug stop supplies those bytes.
`tools/capture_original_sound_callsite_debug.sh <out_dir> [asset_dir]
<scenario>` stages that original debugger pass for `bomb_object_sound`,
`portal_teleport_sound`, `tile_trigger_sound`, `bonus_pickup_sound`,
`player_damage_sound`, and `player_death_sound`, writing a manifest, raw dump,
debugger command plan, runtime command plan, and fill-in `sound_callsite`
candidate fixture.

Other non-explosion cues are still being mapped; direct `playSound(index)`
callers remain compatibility hooks until their original cursor/priority writes
are confirmed.

Player damage counter evidence: `1000:7f68..7f75` subtracts the full accumulated
per-player damage byte (`DS:79e8` for player 1, `DS:79e9` for player 2) before
the `0x002d` hurt request. `1000:63f0` and `1000:6491` increment those counters
on harmful actor overlap, and the clear sites at `1000:7a57..7a5c` reset them
once per outer actor pass. `--debug-original-damage-counters` preserves this
byte-subtraction model and also verifies the live C++ path. Monster contact,
active debris/collapse hazard areas, and bomb blasts now increment the
per-player pending bytes; the update pass drains those bytes once, requests the
priority-`4` hurt cue once when nonzero, skips energy subtraction for state-2
players while preserving the hurt request, and dispatches death when unsigned
byte subtraction wraps above `0x00c8`.
`--debug-player-damage-death-live` exercises that live path with a rendered
hazard fixture, verifies a visible HP decrement, advances into state 2 with the
life count still unchanged, waits through the 60-tick countdown until the
pending life is consumed, and then reenters.
`--debug-monster-contact-damage-live` extends the same model through active
monster overlap: multiple same-pass contacts accumulate in pending bytes before
drain, the hurt cue is latched once, state-2 players preserve energy while still
requesting the hurt cue, and fatal contact underflow is promoted to the
life-loss helper. This is a damage-counter cadence regression, not proof of the
exact original collision-clearance geometry inside `1000:6053..777f`.

State-2 life/reentry evidence: `1000:30a3` only queues the death/life-loss cue
and writes the actor death/reentry fields (`+0x15 = 2`, `+0x10 = 0x003c`,
`+0x24 = 0x64`). The later state-2 handler around `1000:7c89..7db5` owns the
next transition. It decrements actor word `+0x10` at `1000:7c93`, waits for
zero, decrements the Pascal-style life/reentry counter at `DS:79e9 + player`
(`DS:79ea` for player 1, `DS:79eb` for player 2), marks
`DS:79e5 + player = 0` on wrap to `0xff`, and decrements active-player count
`DS:79b8`. When lives remain it later sets `DS:79e5 + player = 2`, initializes
a visual/effect entry, and the normal return-to-active path at `1000:7ddf..7ea7`
requires the reentry gate before restoring player state `1` and energy `0x64`.
The C++ port now mirrors the recovered `+0x10` countdown as a separate
`deathStateTimer` field. Live manual reentry and unwinnable-level restart are
now blocked until that countdown reaches zero, matching the proven state-2
delay while keeping the longer C++ compatibility reentry timeout separate.

Return-to-active evidence: `1000:7db5..7dc7` copies the current player's action
gate into `DS:79a3` from `DS:1b7b` for player 1 or `DS:1b80` for player 2.
Manual byte inspection maps those source bytes to keyboard IRQ state:
`DS:1b7b` is set/cleared by scan codes `0x31`/`0xb1`, and `DS:1b80` by
`0x52`/`0xd2`. `1000:7ddf` only processes players whose `DS:79e5 + player`
state byte is `2`. The path reads an 8-byte effect entry at
`DS:c21e + 8 * actor[+0x01]`, computes map occupancy from effect words `+0` and
`+2`, and may decrement effect `+2` while placement descends. `1000:7e74`
requires `DS:79a3 == 1`; on success, `1000:7e85..7e8c` restores actor state
`+0x15` to `0` for player 1 or `1` for player 2, `1000:7e97` writes
`DS:79e5 + player = 1`, `1000:7e9d..7ea2` clears both gate bytes, and
`1000:7ea7` restores actor energy `+0x24 = 0x64`. The C++ port mirrors the
countdown/action-gate ordering by rejecting manual reentry while
`deathStateTimer > 0`; effect-entry descent and exact actor-state byte mapping
remain documented model behavior until the renderer-facing state is recovered.
The fallback block at `1000:7ef8..7f2a` is now represented in
`--debug-original-state2-return-model`: it only runs when `DS:79b8` reports no
active players, increments `DS:79b9`, and promotes any player status byte
`DS:79e5 + player == 2` to `1` at `0xe6` without performing the normal actor
state or energy restore. The live C++ respawn path does not use this as a
normal return-to-active shortcut.

State-2 animation/effect evidence: `1000:06ab` / file `0x0e1b` initializes a
seven-byte animation cursor at the far pointer passed by callers. Manual
inspection of the writes gives this layout:

```text
anim+0 = arg_0a   current frame
anim+1 = arg_0a   first/min frame
anim+2 = arg_08   last/max frame
anim+3 = arg_06   tick counter
anim+4 = arg_06   tick threshold / frame delay
anim+5 = arg_04   playback mode
anim+6 = 1        signed frame step
```

The player death/life-loss helper at `1000:3108..311d` passes `actor + 0x16`
to that initializer with `DS:006c`, `DS:006d`, delay `3`, and mode `1`, after
which the helper writes actor state `+0x15 = 2`, countdown `+0x10 = 0x003c`,
and energy `+0x24 = 0x64`. The actor update routine around
`1000:6053..6156` consumes `actor + 0x16` as this cursor: when mode is nonzero
it increments the counter, advances the current frame by signed step when the
incremented counter is greater than the delay byte, wraps to the minimum after
the maximum for non-ping-pong modes, negates the step at either bound for mode
`2`, and copies the wrapped cursor into the secondary animation slot for mode
`3`. It then uses the current frame to select sprite metadata from
`DS:c322..c324` before writing the visual/effect entry at
`DS:c21e`/`DS:c224`. The C++ debug commands
`--debug-original-state2-animation-init` and
`--debug-original-state2-animation-advance` lock the initializer byte order and
cursor advancement rules.

The `DS:c21e + 8 * n` entry is renderer/effect state rather than the animation
cursor. The mapped state-2 return path at `1000:7df9..7e70` reads entry words
`+0` and `+2`, computes `x_tile = word0 >> 3` and
`y_tile = ((word2 + 7) >> 3) + 1`, and blocks placement when either the base
tile or the right tile is `0x01` or `0x4c`. If placement is not blocked and
entry word `+2 > 0x18`, the routine decrements word `+2` before the
`DS:79a3` action-gate check. The C++ debug command
`--debug-original-state2-effect-placement` locks that placement/descent model.
One real `dosbox-debug` capture now stops the original game at runtime
`01ED:7C89` after a one-player bomb death. At that stop `DS=0C8F`,
`DS:006a = 0x45`, `DS:006c = 0x4a`, `DS:006d = 0x4f`, and the first effect
entry at `DS:c21e` is `x = 0x0068`, `y = 0x00a8`. The current oracle formula
`DS:c322 + 4 * frame` yields `first_entry_addr = 0xc44a`, six rows, first row
`10,10,7d,43`, last row `10,10,7d,48`, row-byte-0 sequence
`10,10,10,10,10,10`, row-byte-1 sequence `10,10,10,10,10,10`,
row-byte-2 sequence `7d,7d,7d,7d,7d,7d`, and row-byte-3 sequence
`43,44,45,46,47,48`. This is original runtime evidence for the countdown
state, but the live renderer still needs the remaining frame-table field
interpretation and visual consumption path confirmed before it can claim
faithful death/reentry art.

Current C++ mapping: `State2VisualCursor` in `src/main.cpp` mirrors the
recovered initializer and mode-1 advancement with start frame `0x4a`, end frame
`0x4f`, delay `3`, initial counter `3`, and step `+1`. `beginPlayerDeath`
seeds that cursor, the update loop advances it while a player is in state 2,
and `drawState2PlayerVisual` renders a provisional visible state-2 frame so
autoplayer/UI tests can inspect live death playback. This remains a
`visual_claim=0` implementation until the `DS:c322` row fields and final
renderer consumption path are fully mapped. The debug command
`--debug-original-state2-visual-row-model` mirrors the original row range as a
C++ model with rows `4a:10,10,7d,43` through `4f:10,10,7d,48`,
row-byte-3 sprite candidates `67..72`, draw-offset candidate `16,16`, and
`visual_claim=0`. `--debug-original-state2-visual-row-assets` then confirms
those row-byte-3 candidates are in-bounds `BOMOMIMK` sprites, all `16x16`, and
contrasts them with the current provisional cursor-index sequence `74..79`.
`--capture-state2-visual-row-preview <out_dir>` renders both sequences as
isolated C++ PPM artifacts with a manifest for later original-frame comparison.
`--capture-state2-visual-row-game-preview <out_dir>` uses the same row-byte-3
candidate renderer only inside that debug capture, producing full gameplay
frames beside the current provisional renderer frames.
`tools/compare_state2_visual_row_game_previews.py` converts those paired C++
previews and an original-frame directory into a standard frame-compare bundle
with labels such as `state2_current_4a` and `state2_row3_4a`.
Live rendering is not switched to that model until the remaining field names
and frame comparison are proven.

The C++ debug command `--debug-state2-runtime-frame-oracle <dump.txt>` parses a
normalized saved DOSBox debugger transcript. It expects runtime `CS`/`DS`,
translated breakpoints, a `D DS:0060` dump for `DS:006a`, `DS:006c`, and
`DS:006d`, frame-table bytes at `DS:c322 + 4 * frame`, and `DS:c21e` effect
entry bytes. The synthetic fixture proves parser mechanics, address math,
complete raw row reporting, and malformed-input rejection. The original fixture
captures a temp-copy `dosbox-debug` stop at `01ED:7C89` with runtime `CS=01ED`
and `DS=0C8F`; it keeps `visual_claim=0`.

`--debug-visual-table-oracle <fixture> [--expect-error]` is the follow-up
normalizer for renderer-facing visual evidence. It requires runtime `CS`/`DS`,
translated breakpoints for the selected scenario, actor animation cursor state,
an explicit frame-table row at `DS:c322 + 4 * frame`, sprite bank/index
candidates, draw offsets, and effect-entry before/after bytes. Fixtures include
synthetic/malformed parser coverage plus
`visual_table_oracle_original_state2_runtime.txt`, which normalizes the
existing original state-2 stop for actor frame `0x4a`, row address `DS:c44a`,
row bytes `10,10,7d,43`, runtime `CS=01ED` / `DS=0C8F`, row byte 3 as the
`BOMOMIMK` sprite-index candidate `0x43`, and effect placement
`0x0068,0x00a8`. The oracle now validates `sprite_source=row_byte3` for this
fixture, while row bytes 0..2 still need final field names. Fixtures
intentionally keep `visual_claim=0` and do not promote the provisional
dead-player renderer.
`tools/capture_original_visual_table_debug.sh <out_dir> [asset_dir]
state2_death_table_consumption` now stages the matching DOSBox-debug capture
plan, including the `1000:3108`, `1000:6053`, `1000:6148`, `1000:7C89`, and
`1000:7DDF` breakpoints, broad `DS:c322`/`DS:c21e` dumps, an
`environment_preflight=` manifest entry, and a `debugger_seeded` candidate
fixture for later normalization with `--debug-visual-table-oracle`.
`tools/capture_original_state2_visual_frames.sh <out_dir> [asset_dir]
state2_death_table_consumption` stages the companion original-frame capture
contract for `tools/compare_state2_visual_row_game_previews.py`: six planned
`state2_game_4a..4f` screenshots, a manifest, a frame plan, route
`debugger_seeded`, and `visual_claim=0` until the DOSBox/debugger-seeded frames
exist.
Promoted original visual-table fixtures should be named
`visual_table_oracle_original*.txt`; the fixture expectation checker treats
that prefix as optional original evidence while keeping `visual_claim=0` until
separate frame comparison promotes presentation.

State-2 fallback caveat: the `1000:7ef8..7f2a` model above is static
disassembly behavior only. Runtime circumstances that reach it, active-player
count edge cases, and any visible result still need DOSBox/debugger evidence.

## Level Embedded Records

- The two words immediately after the decoded tile and word layers are preserved
  as unresolved `fieldA`/`fieldB` values. In the shipped levels their pairs are:
  level 1 `0x4005`/`0x0042`, level 2 `0x401e`/`0x0189`, level 3
  `0x4036`/`0x02e3`, level 4 `0x403c`/`0x01b3`, level 5 `0x4066`/`0x03dc`,
  level 6 `0x409f`/`0x0aa4`, and level 7 `0x4041`/`0x014a`.
  The second word exactly matches the count of nonzero low word-layer cells
  (`word < 0x4000`) in each shipped level, so the C++ port now treats it as the
  original physical-damage progress denominator. Destruction completion advances
  when low-word collapse groups are damaged, not when visible tile ids or
  trigger rewrites change. The low 14 bits of the first word are
  close to, but do not always equal, the high-word cell count; its exact meaning
  remains unresolved. It also does not match high-word unique counts or
  connected-component counts in the shipped levels.
  `--debug-level-raw-roundtrip` pins these raw words and their low-14-bit
  payloads against the shipped `LIVELS.SCH`, while `--debug-word-layer`
  summarizes the negative candidates: across all seven levels, `fieldB` matches
  the low physical-word count seven times, but `fieldA & 0x3fff` matches the
  high-word/high-unique/high-same-word-component counts only once and the
  high-component count zero times.
- 7-byte records are start and teleport destinations: `u16 key`, `u16 x`,
  `u16 y`, `u8 marker`. Key `0` records with marker `1` and `2` are player
  starts. Tile `0x45` uses the word-layer key to select a nonzero destination.
- 14-byte records are tile-trigger rewrite rules: `u16 range_first`,
  `u16 range_last`, `u16 trigger_key`, four source tile ids, and four
  replacement tile ids. Tile `0x72` passes its word-layer key to the trigger
  matcher. The scan masks level word-layer values with `0x7fff` before applying
  the word range.

## Raw Level Roundtrip

`--debug-level-raw-roundtrip` parses original `LIVELS.SCH` directly and compares
the result with `src/LIVELS.SCH.json`. This locks the current file-format
understanding to the shipped binary asset: seven levels, 47,700 decoded cells,
15 spawners, 21 portals, and three trigger rules. Confirmed level file offsets
are `0`, `1242`, `4923`, `10984`, `15225`, `21546`, and `36128`.

## Record Entry Evidence

Manual byte/disassembly inspection of `1000:1845..1ad4` shows the high-score
name-entry path accepts `A..Z` plus space, stores typed letters by applying
`or 0x20`, handles Backspace as `0x08`, commits on Enter `0x0d`, and stores the
eight-byte name with colon padding. The C++ port follows those input rules while
retaining `Esc` as a reconstruction-only cancel path so failed or accidental
entries can be abandoned from the SDL menu. `--debug-record-name-entry` now
locks cancel, ignored non-letter keys, Backspace, lowercase storage,
eight-character truncation, space-to-colon encoding, and short-name colon
padding against a temporary binary `RECS.DAT`-format file.
`--debug-record-update` writes both temporary `.dat` and `.json` tables: the
default `.dat` path is pinned to the original 92-byte binary layout, while the
`.json` path remains a diagnostics-only compatibility serializer.

## Game Over and Completed-Game Evidence

Manual byte/disassembly inspection of `1000:1b14..1d42` maps the post-game
dispatcher. MZ header math confirms its file window as `0x2284..0x24b2` using
`file_offset = 0x770 + CS_offset`.

- `1000:1b63` reads a byte mode parameter. Mode `1` draws the Pascal string at
  `CS:1ae1`, `game over`.
- Mode `2` draws `CS:1aeb`, `eccellente>>>`, and `CS:1af9`,
  `hai completato il gioco`, then sets `DS:208c = 1`, likely the completed-game
  flag.
- `1000:1bf8` starts a loop over player indices `1..2`. Player 1 uses score
  pointer `DS:785a` and display marker `'1'`; player 2 uses `DS:7888` and
  display marker `'2'`.
- `1000:1c4b..1c5e` skips a player display if that player's score dword is
  zero.
- `1000:1cf8` waits for one key through the keyboard helper before checking
  records.
- `1000:1d18..1d24` compares each player score against the current seventh
  record score at `DS:1af7 + 7 * 0x0d`.
- `1000:1d38` calls `1000:1845` with the score dword and player index for each
  qualifying player. Because the record threshold is read again after a prompt,
  player 2 is re-evaluated against the table that may already include player 1.

The C++ port maps this to `beginEndRun`, `startNextPendingRecord`, and
`finalizePendingRecord`. It keeps the original player-check order and re-checks
queued player scores against the current record table immediately before
opening name entry. `--debug-end-flow-records` now includes a threshold case
where player 2 would qualify against the old seventh record but is skipped after
player 1 is inserted and the table cutoff rises. It also locks the strict
cutoff comparison: a score equal to the current seventh record does not open
name entry.
`--debug-record-save-failure` verifies that a failed write leaves the pending
entry on the name-entry page and that retrying with a writable record path
commits the same pending score/name instead of discarding it.
`tools/check_record_flow_evidence_map.py` guards this handoff by checking the
`RECS.DAT` converted resource shape, record/name/end-flow debug commands, CTest
output contracts, and the `1000:1845..1ad4` / `1000:1b14..1d42` docs anchors.

## Code Mapping

- Level JSON loading: `loadLevels`; raw binary validation: `loadRawLevels`.
- Pascal-compatible level RLE: `decodeLevelRle3`.
- Actor 8.8 integration: `integrateAxis8_8`.
- Bomb expiration and physical damage: `explode`, `queueTileDamage`,
  `damageMonstersInExplosion`.
- Player damage counters: `queuePlayerDamage` mirrors the `DS:79e8`/`DS:79e9`
  increment sites; `drainPlayerDamageCounters` maps the `1000:7f68..7f8f`
  byte-subtract and hurt-request pass.
- Sound bank loading and latch: `loadSon` maps `1000:0630..06aa`;
  `latchSoundRequest`, `requestSoundCursor`, `requestSoundOffset`, and
  `pumpSoundLatch` map `1000:165a..167d`; `synthesizeDirectSweep` maps the
  `DS:78c0 > 0xea60` branch; `synthesizeSoundCursor` maps the non-direct
  six-byte step advance at `1000:0fbe..1088`.
- High-score load/save/name entry: `loadRecords`, `saveRecords`,
  `handleNameEntryKey`, `finalizePendingRecord`.
- End-of-run dispatch and per-player record queue:
  `updateLevelCompletion`, `beginEndRun`, `startNextPendingRecord`,
  `cancelPendingRecord`.
- Debug surface: command dispatch in `main`.
