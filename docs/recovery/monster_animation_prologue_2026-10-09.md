# Living-Monster Animation Prologue

## Original Evidence

The fixture runs the unmodified original `LEZAC.EXE` at `CS:6078..615A`,
stopping before actor behavior, motion or facing reselection. It is a controlled
CPU experiment, not naturally reached gameplay. No instructions are patched,
calls stubbed, or hardware I/O/interrupts permitted.

- Original executable SHA-256:
  `7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
- LF-normalized fixture SHA-256:
  `5cb198b666f4cca3c0167ef595e4472b908bc7a1cfbdb58d5c63eb363309ddf1`.
- LF-normalized fixture FNV-1a64: `0a33b9389958728e`; 56,244 bytes.
- 53 cases, each carrying its state through 12 updates: 636 updates total.
- Modes 0, 1, 2, 3, 4 and 255, signed/zero steps, endpoint and overshoot cases,
  counter wrap, maximum delay, cursor byte wrap, and five backup step patterns.
- 413 descriptor-word writes and ten mode-3 backup restorations.

A read-only visual-write observer is checked against a second unobserved CPU:
all 1 MiB of memory and 14 registers match at every return. Actor bytes outside
22..28, including backup bytes 29..35, remain unchanged. Each CPU has its own
continuously advanced state; expected bytes are not reinjected between updates.

The observer detects the original visual descriptor word write, not a full
descriptor rewrite. The prologue does not update visual width/height bytes.
The recorded visible index is the zero-based index used for that word lookup.
This fixture does not prove complete visual-row or rendered-frame fidelity.

## Production Change

The living-monster path now uses the existing `ActorAnimation::advance` routine
through an explicit conversion between the monster's zero-based cursor/range
and the original one-based bytes. This preserves the original rules:

- Mode zero leaves the counter and visible index unchanged.
- The byte counter advances only when it exceeds the delay; 255 wraps to zero.
- Cursor addition wraps as a byte. There is no runtime range repair or clamp.
- Mode two reverses the signed step at either endpoint without undoing overshoot.
- Other modes wrap only when the unsigned current byte exceeds the last byte.
- Mode three restores all seven active bytes from the backup after that wrap.
- The visible index changes only at an actual advance boundary.

`ActiveMonster` now retains a backup block. The Level 7 loader copies it from
the corresponding GRAN actor bytes 29..35, independently of selector reseeding.
One old synthetic collision diagnostic now explicitly initializes its cursor
instead of depending on the removed runtime repair.

## Reproduction

Install Unicorn 2.1.4 in an isolated analysis environment, then run from a clean
checkout with a new output directory:

```sh
env SDL_AUDIODRIVER=dummy python3 -B tools/capture_original_monster_animation.py \
  --out /tmp/lezac-original-animation-new
```

`--unicorn-path` optionally selects the analysis dependency directory. The
runner compiles and executes its single-read, hashed `original_bomb_cpu.py`
source buffer, not cached bytecode or an identically named imported helper.
It pins the normalized helper source and the original inputs. Fresh reports
record source/dependency identities and retain failure diagnostics; existing
output directories are never overwritten. The produced fixture must match
the committed normalized digest above. CRLF checkout conversion is accepted
by the compiled fixture reader without allowing other input changes.

Build normally and run these registered tests:

```sh
env SDL_AUDIODRIVER=dummy ctest --test-dir build --output-on-failure \
  -R '^monster_animation_(original_helper|original_app|fixture_contract)$'
```

`monster_animation_original_helper` checks the compiled helper's seven active
bytes, seven retained backup bytes, visible index and advance flag at all 636
boundaries. The contract test accepts LF/CRLF inputs and rejects seven missing,
corrupt, truncated, trailing or oversized inputs.

`monster_animation_original_app` invokes the actual `App::updateMonsters`
function and observes the production animation boundary. Its diagnostic-only
observer stops the call before behavior/motion/facing changes, matching the
original CPU boundary. State is seeded once per case and then carried forward.
It additionally invokes the production boss loader to check all seven shipped
backup blocks and seven distinct seeded blocks. These 14 loader checks are
preservation contracts, not original-CPU or natural-route comparisons.

## Validation Boundary

Bounded local validation passed all 636 compiled-helper comparisons, the seven
input rejections, 19 source guard cases, App syntax checking and CTest
registration. Seven compiled negative controls were rejected: late endpoint
reversal, omitted backup restoration, early delay comparison, invented cursor
repair, premature visible writes, default backup substitution, and the exact
previous production animation block. These are compiled helper/control tests,
not mutated full-App runs.

Full App compilation and the actual App regression are delegated to hosted CI;
local configure/syntax checks are not reported as runtime validation. Local
source and check directories each stay below 8 MiB. No full game build or new
native frame capture is permitted while the host disk reserve is closed.

Physical slot reuse and inherited backup tails remain open. Other actor types,
corpse animation, complete 38-byte actor fidelity, descriptor dimensions,
natural campaign routes, sound timing and whole-game acceptance are not proved
by this batch. Existing completion/fidelity claim gates remain unchanged.
