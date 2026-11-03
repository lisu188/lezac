# Controlled Live-Frame Debris Clock Phase

This regression checks the production App's frame-counter-before-debris order.
It does not change normal gameplay, close `debris_shatter_dice_phase`, or claim
a continuous original frame, original real-time cadence, or whole-game fidelity.

## Original Observations

Fresh REA 6.7.0 / Ghidra 12.1.4 observations on WSL byte-check nineteen
instructions: the new-game reset at `77D2/77D4`, the counter gate at
`7903..7916`, and the shatter predicate at `4AFA..4B0B`. New game writes zero
to `DS:78C2`. The counter gate increments that WORD, reads the new value, and
chooses the DOS-time path at multiples of thirty, including zero after wrap.
Landing shatter subsequently reads `DS:78C2`, adds the physical debris slot
with WORD rollover, and tests the remainder after unsigned division by six.

The optional `capture_original_debris_phase.py` executes the counter block
from `7903`, stopping at the declared `7919` or `79DF` boundary before the
remaining pacing work. Its computed counter output is an input to a separate
complete original `45FA` updater call. This is controlled functional
composition, not continuous original execution across those routines.
The intervening DOS/CRT, rendering, actor and IRQ work is not executed here.

Thirty explicitly seeded prior-counter values and twelve physical slots give
360 cases. They include first-increment, ordinary modulo phases, the
thirty-frame gate and WORD rollover. Both counter-block exits occur. The
executor first reproduces eighteen frozen native updater cross-checks.
All 43,552 relocated code bytes remain unchanged after the counter block and
every updater case, and the updater's actual CS/IP/SP return is checked.
No original calls are stubbed or instructions patched. No full RAM is exported.
Sound state and natural gameplay are outside the comparison.

## Production Consumer

The existing diagnostic accepts a distinct `LZDP0001` input format. These
controlled cases use a 16-by-16 map, no collapse records, an inactive player,
and no spawners. The diagnostic loads the prior counter, then calls the real
`updateWithControls`, not a debug-only clock/debris simulation. That routine
increments `logicTick_` before the ordinary actor and `updateFlashes` work;
`updateFlashes` invokes the production debris updater. The output includes
the actual low counter WORD and all map planes, live records, counts and RNG.
Expected state is never passed to the App.

The frozen 14,564-byte fixture compares every output byte across all 360
cases. Using the prior counter for the dice changes the captured shatter
decision in 127 cases. A source-order contract also checks the real frame
dispatcher, and fixture tests reject changed metadata, payloads, missing
inputs, altered source wiring and changed output extents. Failures retain a
JSON report and available inputs/outputs in a fresh diagnostic directory.

## Validation

The complete App builds with GCC 13.3 in C++23 mode and
`-Wall -Wextra -Werror -pedantic`. All 360 compiled cases match the complete
1,253,580-byte original output. Two independently generated captures are
byte-identical, including their metadata. Deterministic gzip headers are
checked on Linux and native Windows Python.

Two separately compiled App mutants provide runtime negative controls.
Removing the real dispatcher increment changes all 360 cases. Moving it after
`updateFlashes` preserves every final counter WORD but changes 127 cases;
the full-output comparator rejects both. Neither mutant changes the retained
repository source or is shipped as production code.

All 32 focused CTests pass, including the six unchanged original full-frame
routes (1,674 frames total). Seven Python fixture/contract methods pass on
Linux and native Windows. The changed App translation unit also compiles with
native MSVC 14.44 under the project's `/W3 /permissive-` policy. This is an
owner-object compile, not a linked Windows App runtime claim.

A separate fresh controlled DOSBox capture and fresh production C++ replay
match across 41 full frames, 82 mapped state observations and 2,624,000 pixels,
with zero differences. Both frame-41 PNGs are 6,080 bytes and have SHA-256
`77c32e10e1bec868783ef05a92999cc819acd308e2281f0f1bbac01bd089b893`.
That short walk uses the existing declared RNG, resident-hook and normalized
input controls; unlike the unpatched Unicorn routine calls above, it is an
instrumented native capture. It does not establish physical-input, audio,
real-time cadence, owner acceptance or whole-game fidelity.

## Reproduction And Limits

```sh
ctest --test-dir build -R '^original_debris_phase(_fixture)?$' --output-on-failure
python3 -S -B tools/capture_original_debris_phase.py \
  --unicorn-path /path/to/unicorn-2.1.4 \
  --out /dev/shm/new-phase.bin.gz --metadata /dev/shm/new-phase.json
```

Build/runtime scratch should remain in RAM for local work. All App launches
use dummy audio. Existing direct updater, WORD-sum wrap and natural full-frame
fixtures are retained unchanged. Natural startup/restart/pause clock alignment,
adaptive host cadence, the complete original frame and actual recovered-frame
integration remain separate obligations. The intermittent actor-pass hold and
global fidelity/completion flags are unchanged.
