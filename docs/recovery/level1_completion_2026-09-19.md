# Natural C++ Level 1 completion and the original results gate

## Scope

This batch extends the event replay from PR #237 with complete, input-only
single-player and two-player C++ Level 1 routes. Both begin at the menu,
collect the objective, place two large bombs, let destruction and collapse
finish, wait through the results, acknowledge Level 2's introduction, and
continue in active Level 2. Neither route changes positions, health, inventory,
map cells, progress, enemy state or timers. The existing replay initializes
one RNG seed and advances its documented presentation clock.

These are native C++ playability and regression results. They are not a
successful original-versus-port natural route or full-frame fidelity proof.
The original gate and blocking call are independently identifiable in the
executable. The new original capture helper observes seeded gate boundaries
and a result sequence, not a natural victory.

## Production corrections

The ordinary route exposed two real divergences from the original control flow:

1. The port entered results as soon as the bonus/destruction threshold was
   reached, without waiting for the collapse queue to empty.
2. While results were displayed, the port continued actor, player, terrain,
   palette and gameplay-clock updates. The player could continue taking damage
   and the map could change behind the banner.

`updateLevelCompletion` now also requires an empty collapse queue. The
fallback completion caption uses the same gate. Once results are active,
`updateWithControls` advances only the result presentation and sound latch.
The test-only timed transition follows the same suspension. Input continues
through the existing result handler; acknowledgements and score count-up
remain live. No asset decoder, movement, bomb, collapse or enemy rule is changed.

The older seeded `level_transition` autoplayer now explicitly allows terrain
to settle before measuring its existing 101-tick compatibility transition.
It rejects early advancement while collapse is still pending. It is still a
seeded subsystem test, not evidence of natural gameplay completion.

## Original instruction evidence

Original `LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Main code file offsets equal the listed Ghidra offsets plus `0x770`.

| Ghidra anchor | Meaning |
| --- | --- |
| `1000:8283` | Test bonus-complete byte `DS:79C5`; skip results if zero. |
| `1000:828A` | Test destruction-complete byte `DS:79C6`; skip if zero. |
| `1000:8291` | Test collapse-count word `DS:2080`; skip if nonzero. |
| `1000:8298` | Call blocking results routine `1000:1D61`. |
| `1000:829B` | Inspect the level after the results routine returns. |
| `1000:82A2` | Jump to level initialization at `1000:77DC`. |
| `1000:82AF` | Skipped-results path, followed by the main-loop return. |

The regression pins the original executable and complete gate bytes. This
static evidence must not be described as an uninstrumented runtime capture.
The existing `seed_original_level.py` also identifies this gate and result
routine when advancing the original through seeded level transitions.

`capture_original_level1_completion.py` adds a focused live observation:
four guarded hooks preserve registers/flags and replay displaced instructions.
Nine cases must skip results; the final `(bonus=1, destruction=1, collapse=0)`
case must enter the real result routine. Collapse counts include 1, 256 and
65535. Rejected probes restore the two flag bytes and collapse word before
resuming the next real game update. The accepted case runs the original
result routine, samples gameplay state nine times, and acknowledges its return
to level 2. No player coordinates or map cells are seeded.

The helper requires a private copied game directory, an owned DOSBox child,
private Xvfb, both instrumentation approval flags, fresh output paths, and
silent audio. It retains the raw actor/life state, map digests, register values,
case outcomes, a result screenshot and a completion marker. An incomplete
attempt writes a separately labeled partial report and cannot become evidence.
Hooks are restored in a `finally` block. Interrupts continue while hooks wait;
this probe does not establish IRQ timing, natural keyboard equivalence,
result-animation frame timing or full-screen original pixel parity.

## C++ route observations

| Checkpoint | Single player | Two players |
| --- | ---: | ---: |
| Objective first collected | 84 | 84 |
| First/second large bomb constructed | 137 / 351 | 137 / 351 |
| Threshold first reached with pending collapse | 434 | 434 |
| Collapse empty; results start | 755 | 755 |
| Result sequence reaches key wait | 927 | 989 |
| Result acknowledgement; Level 2 introduction | 1181 | 1481 |
| Level 2 first active update | 1201 | 1501 |
| Captured frames, including initial menu | 1261 | 1601 |
| P1 score entering Level 2 | 6050 | 6050 |
| P2 score entering Level 2 | Not active | 5750 |

These are one-based replay update ticks, not claimed original frame numbers.
The routes deliberately wait at the result prompt so duplicate awards and
unacknowledged transitions are observable. All full 320x200 frames include
HUD, overlays and introductions.

The runtime progress denominator is 66 physical word-layer cells. At the
result gate 50 have been destroyed, giving integer destruction percentage 75
and a 750-point destruction award. P1 has 20 medium and 4 large bombs left,
worth 4000 points, added to the existing 1300 score exactly once. The legacy
JSON summary's `startingDestructibleTiles=573` is not this progress denominator.
The production loader recomputes it from the word layer.

P1 loses no life on either route. P2 moves through its own input mapping, then
enters a dying state before results in the two-player case; that state is
suspended along with the rest of gameplay. Both players are active after the
Level 2 introduction. This is one natural two-player interaction case, not
complete death/reentry or simultaneous-input qualification.

A negative single-player control removes only the second fire press/release.
After 800 updates it has collected the objective but destroyed only 29/66
physical cells. It remains in Level 1 without results. A large final score or
an arbitrary next-level flag alone cannot satisfy the successful route test.

## Reproduction

```sh
python3 tools/test_level1_completion.py --exe build/lezac_cpp --mode single --out /tmp/lezac-completion-single
python3 tools/test_level1_completion.py --exe build/lezac_cpp --mode two --out /tmp/lezac-completion-two
ctest --test-dir build -R '^level1_completion_' --output-on-failure
python3 tools/capture_original_level1_completion.py --self-check
```

The two integration cases each run six assertions through the production
executable. Checks cover the original static gate and corrupted-byte rejection,
ordinary input and Level 2 reachability, delayed completion while collapse is
pending, frozen gameplay during results, one-time awards, preserved score,
explicit acknowledgement, actual full-frame integrity and unchanged source
assets. The single-player case also records the one-bomb negative control.
The existing 13-case replay/parser/mutation suite remains unchanged.

Both `original_fidelity_claim` and `port_functionally_complete` remain false.
The next cross-runtime task is a phase-mapped original capture of the same
successful input stream, with matched initialization and no gameplay-state
seeding, followed by first-divergence recovery. Exact result timing, frame
presentation order, natural death/reentry/restart and audio parity remain open.
