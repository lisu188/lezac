# Walker Gravity Word Arithmetic

Two independent silent DOSBox captures confirm 32 seeded kind-1, behavior-3
gravity/landing boundaries each. They exercise the ordinary signed `0x07FF`
limit, supported/upward motion, zero-speed support, ten landing snaps, and two
signed-word wrap boundaries. This is bounded original runtime evidence, not a
natural high-speed fall or a complete actor/campaign comparison.

## Recovered Order

The shipped `LEZAC.EXE` SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its MZ header places the image at file offset `0x0770`.
The unrelocated instruction window is `1000:716E..71A4`, file
`0x78DE..7914`, exclusive end:

```text
807edf007406837ef2007d128346f240817ef2ff077e05c746f2ff07eb18
837ef2007e1231c08946f28b46d225f8ff8946d2c646e001
```

- Clear bottom flag or negative VY takes the gravity branch.
- `717A` adds `0x40` to the 16-bit VY local, wrapping before the comparison.
- `717E..7185` uses a signed compare and clamps only results above `0x07FF`.
- Otherwise positive supported VY becomes zero, Y is masked by `0xFFF8`,
  and the facing-reselect flag is set. Supported zero VY holds without a snap.

Airborne `1983`, `1984`, and `2047` all produce `2047`; `32704` produces
`-32768`, and `32767` produces `-32705`. The previous C++ wide addition
incorrectly produced `2047` in those last two cases. These overflow inputs
were explicitly seeded, not observed during ordinary level traversal.

## Capture And Fixture

The native producer installs three reviewed hooks: main pre-pass `7EC5`,
gravity entry `716E`, and gravity exit `71A4`. The latter two are restricted to
kind 1 / behavior 3. Trampolines preserve stale stack words as well as CPU
registers/flags and retain the displaced instructions. Runtime CS is derived
from the relocated support call, and all code/data segment relationships and
instruction windows are checked before installation. The original boots into
two-player level 1 through its physical menu key and completes one unseeded
tick before the cases.

Each case explicitly seeds one actor, terrain, shared clock/RNG, and player
state at a case boundary. Grounded cases use two `0x52` bottom tiles, not
assumed edge flags. Each original pre/post observation includes raw stack
locals and registers from the same frame and actor call. Independent replay of
the unchanged original instructions agrees with all 64 native transitions.
Every undeclared local byte remains unchanged. Both runs restored all three
hooks and their scratch bytes, and their owned DOSBox children were terminated.
The repository original assets were hash-checked and never launched in place.

Retained RAM-only captures:

- `/dev/shm/lezac-walker-gravity-original-20261003-v38-a/capture.json`, SHA256
  `0bdb5d90948f3c47933409d1c8e07956f3830f007182ddea6317ef2f37e5c6a1`.
- `/dev/shm/lezac-walker-gravity-original-20261003-v38-b/capture.json`, SHA256
  `a344fdfd89a0b66a70bdaf93ca39a197eef0f5a2777e5a9c5cc065f619e601bb`.
- Native producer SHA256
  `12765724af49e5c6b67b468622146b14759d2f0c046cd43b2e024bbb920de5c3`.
- Extraction receipt SHA256
  `635d39b8cbf5ab289331e81c89066abd9e9698263da8d06cc9f4a1508a58676a`.

The checked-in recapture helper differs from that producer only in deriving
the repository root portably. Both captures derive the same 486-byte fixture:
[`walker_gravity_word_original.bin`](../../tests/fixtures/walker_gravity_word_original.bin),
SHA256 `17c7c33a7ef9c94fc69332e220ead2d0337fc765b2f6383650dd516188803df5`,
FNV1a64 `e000b1d9dfe2e9c5`. The header records the executable digest and exact
instruction window. Thirty-two ordered 12-byte records retain bottom flag,
input/output VY, input/output Y, and input/output facing flag.

## Production And Checks

`updateMonsters()` now calls `applyGroundMonsterGravity()` at the same point
before motion/ledge handling. The helper narrows the sum to a signed word
before applying the signed terminal-speed comparison. Landing/facing behavior
and the boss/flyer paths are unchanged.

`walker_gravity_word_original` checks every phase field against the fixture,
then separately exercises all 32 cases through production `updateMonsters()`
and checks VY, bottom contact and unchanged RNG. The final full-update actor
positions/animation are not compared to the pre-integration original window.
The fixture guard pins all bytes and the shipped instruction window; its
self-test rejects every byte mutation, truncation, trailing data, and a changed
original executable. The production replay guard requires a positive replay
and rejection of 18 malformed fixtures. A capture self-check runs without
starting a game.

The path-scoped original-probe workflow stages a private copy under the same
128 MiB output and 512 MiB process allowances used by the earlier native
probe, with strict 10-percent disk/memory floors. It recaptures all cases on
the PR head, checks the complete fixture byte-for-byte, and preserves the raw
capture and any failures. Full Linux/Windows suites and both extracted-package
checks remain required before merge.

The local isolated GCC check compiles the verbatim production phase against
all original cases and rejects restored wide addition, unconditional gravity,
and removed landing snap. It is not a substitute for the full-executable CTest
or exact-head CI. The first local mutation run accidentally retained the
narrowing cast in its old-behavior mutant; that failed run is preserved
separately and was not relabelled as passing.

```sh
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy \
  ./build/lezac_cpp --debug-walker-gravity-word-evidence \
  tests/fixtures/walker_gravity_word_original.bin
ctest --test-dir build -R '^walker_gravity_' --output-on-failure
```

For a recapture, prepare a new temporary copy of all eleven original shipped
assets, then use fresh output paths:

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_walker_gravity.py \
  --run-dir /dev/shm/lezac-gravity-original-copy \
  --out-dir /dev/shm/lezac-gravity-fresh-capture \
  --approve-procmem --approve-runtime-instrumentation
```

## Remaining Scope

The ordinary walker gravity limit is no longer merely inferred. The historical
level-2 fixture still truthfully records `gravity_clamp_exercised=0`; it was
not modified. Other kinds/behaviors, natural terminal-speed falls, complete
contact/sprite behavior, physical-input parity, sampled VGA/HUD parity and
whole-game fidelity remain unproven. The bootstrap screenshot was inspected
and shown; it predates actor seeding and is not a synchronized C++ comparison.
`actor_update_original_contact_semantics` remains open, as do the other three
original-fidelity items. No full replay reserve was lowered or route shortened.
`port_functionally_complete=0` and `original_fidelity_claim=0` remain unchanged.
