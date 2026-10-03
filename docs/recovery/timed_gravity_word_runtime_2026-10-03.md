# Timed-Actor Gravity Word Arithmetic

Two independent silent original-game captures each record 64 seeded behavior-2
gravity/landing boundaries: kind `0x0C` timed actors and kind `0x0D` small bombs,
with bottom contact clear/set and sixteen signed velocities per combination.
All 128 observations agree with independent execution of the unchanged original
instruction window. This establishes the bounded gravity arithmetic, not full
timed-actor motion, natural high-speed falls, corpse lifecycle or bomb spawning.

## Original Order

The shipped executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Its MZ image begins at file `0x0770`. The behavior-2 gate is
`1000:7018 3c 02 75 3f`. Gravity/landing occupies `1000:701C..704E`, exclusive
end, before floor friction and common response/integration:

```text
807edf007406837ef2007d128346f240817ef2ff077e05c746f2ff07eb14
837ef2007e0e31c08946f28b46d225f8ff8946d2
```

- Clear bottom contact or negative VY takes the gravity branch.
- `7028` adds `0x40` to a word, wrapping before the signed `0x07FF` comparison.
- Supported positive VY becomes zero and Y is masked by `0xFFF8`.
- Supported zero VY holds; negative VY still receives gravity.
- Unlike the ordinary walker window, this phase does not set a facing flag.

For both kinds, airborne input `32704` produces `-32768`, and `32767` produces
`-32705`. The old C++ wide addition returned `2047` instead. Other cases cover
signed minimum, upward-to-zero boundaries, ordinary acceleration, terminal speed,
supported zero speed and twenty landing snaps. These velocities and terrain
were explicitly seeded, not reached through natural gameplay.

## Capture Provenance

The producer reuses the existing owned-child, private-Xvfb environment and
stack-preserving trampolines. Hooks are main pre-pass `7EC5`, gravity entry
`701C` and gravity exit `704E`. The latter two accept only kinds `0x0C..0x0D`
with behavior 2. Original instruction bytes, relocations, runtime segment
relationships and the previously verified scratch extent are checked first.

The original enters two-player level 1 through physical menu input and completes
one unseeded tick. Each case then seeds an actor, empty/`0x52` bottom terrain,
clock/RNG and distant active players. Kind 12 uses the usual two-cell edge scan;
kind 13 reaches its original single-cell scan. The actor hotspot is explicitly
6, timer byte 11, X 336 and collision Y 99 for both kinds. This is not a claim
that a naturally spawned small bomb uses hotspot 6 or those animation bytes.

Each pre/post pair is from the same actor call/frame and retains 58 raw stack
bytes plus six registers. Only the declared VY/Y word bytes change; facing and
every other local remain byte-identical. All three hooks and scratch bytes were
restored and the owned children terminated. Eleven original assets were copied
privately and hash-verified; no original was launched in the checkout.

Retained RAM-only inputs:

- `/dev/shm/lezac-timed-gravity-original-20261003-v39-a/capture.json`, SHA256
  `f9f4c0c4d3314b3eb9fe47bd275cb7d095cf89c4064f10fc65b1427aec75acd1`.
- `/dev/shm/lezac-timed-gravity-original-20261003-v39-b/capture.json`, SHA256
  `bb8783eb71437e7690eb0e8dccf54e7ff72e84d646502a268560d6eb54bd0286`.
- Native producer SHA256
  `b9d8d496fa3c9c3deae942476146fbaf553d6e5f91859ea665a6aeef21301891`.
- Extraction proof SHA256
  `84d3fb6ec2766bbf2011d8f0e6a3a6a0060b7b6752b586a9b182d2f0982034fb`.

The portable recapture helper differs only in deriving the repository root.
Both captures derive the identical 866-byte
[`timed_gravity_word_original.bin`](../../tests/fixtures/timed_gravity_word_original.bin),
SHA256 `8e4b8478424ad987b27341a19e7c0ac2844ef2672ea043b4564dd237b5f82c56`,
FNV1a64 `ef718e96b15caf9d`. Its header pins the original executable and all
50 instruction bytes; 64 ordered records retain bottom contact, input/output
VY, input/output Y, kind and behavior.

## Production Validation

`updateTimedActorMotion()` now narrows the addition to a signed word before the
terminal-speed comparison. Landing, floor friction, top/side response and 8.8
integration remain in their original C++ order. The rest of the method is
byte-identical to its base after substituting this gravity block. Ordinary
walker, flyer and boss motion paths are not changed by this patch.

The verbatim gravity prefix is compiled independently as C++17 and compared
against all 64 original VY/Y outputs. Restoring wide addition, applying gravity
unconditionally and omitting the landing snap are each rejected. This isolated
check stubs storage/edges and is not a full-executable acceptance substitute.

`timed_gravity_word_original` exercises all 64 cases through the complete
production helper, then through the kind-12 `updateMonsters()` or small-bomb
`updateBombs()` caller. It checks VY, unchanged RNG and the twenty supported
landing Y values. For nonzero output VY, the helper integrates after the native
observation point, so final Y/fractions are deliberately not compared to the
pre-integration fixture. Caller timers are non-expiring test inputs, not a
comparison of the original timer byte or animation/expiry lifecycle.

The fixture guard rejects all 866 single-byte mutations, truncation, trailing
bytes and a changed executable. The production guard requires a positive replay
and rejects eighteen malformed fixtures. The capture self-check launches no game.
The path-scoped native CI job stages fresh assets under unchanged 128 MiB output
and 512 MiB process allowances with strict 10-percent filesystem/memory floors,
recaptures all 64 cases and compares the complete pinned fixture. Both full
platform suites, both extracted-package checks and this exact-head native probe
remain merge gates.

```sh
env SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  ./build/lezac_cpp --debug-timed-gravity-word-evidence \
  tests/fixtures/timed_gravity_word_original.bin
ctest --test-dir build -R '^timed_gravity_' --output-on-failure
```

For recapture, create a fresh temporary copy of all eleven assets, then use
fresh output paths:

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_timed_gravity.py \
  --run-dir /dev/shm/lezac-timed-gravity-copy \
  --out-dir /dev/shm/lezac-timed-gravity-capture \
  --approve-procmem --approve-runtime-instrumentation
```

## Remaining Scope

This narrows the behavior-2 gravity gap, not the broader actor-contact item.
Other timed kinds, natural corpse/bomb trajectories, floor friction, side/top
response, integration, animation/expiry and full campaign fidelity remain
outside these observations. The original bootstrap screenshot was inspected
and shown; it predates actor seeding and is not a paired C++ comparison.
All four original-fidelity items remain open, as do full replay acceptance and
VGA/HUD/input/audio parity. No full replay scope or reserve was weakened;
`port_functionally_complete=0` and `original_fidelity_claim=0` remain unchanged.
