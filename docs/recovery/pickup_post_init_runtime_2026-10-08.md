# Pickup Post-Allocation Animation Initialization

## Original Behavior

The pickup caller at `1000:6D81..6E01` gates on fewer than fourteen pickup
actors. It consumes one RNG draw and calls the complete actor constructor
at `1000:2F9F`, even when the shared thirty-slot pool is already full.
The subsequent `1000:6DDD..6DF3` code reads the current `DS:208D` tail index
and calls `1000:06AB` with four zero arguments. That helper writes the seven
animation bytes as `00 00 00 00 00 00 01`.

Crucially, the animation initialization is not conditional on constructor
success. At a full pool, the old last actor receives those bytes, while
its remaining thirty-one bytes stay unchanged. The pickup count increments
only when construction succeeds. At the fourteen-pickup cap, RNG,
construction and animation initialization are all skipped.

The C++ pickup path previously initialized only successfully created
transients. It now initializes the shared tail after every attempted
pickup construction, including refusal. Effects, markers and rewards
carry the original animation tuple directly. Monsters translate the
stopped one-based cursor/range into their zero-based `0xff` representation.
The visible marker/monster frame stays latched, matching the original's
write footprint. Bombs currently have an implicit static stopped cursor.

## Executed Original Evidence

`tools/capture_original_pickup_post_init.py` executes the unpatched original
caller, complete RNG, constructor and animation helper using Unicorn 2.1.4.
No original calls are stubbed. Interrupts and hardware I/O are rejected.
The capture verifies helper entry order, exit CS/IP/SP/BP, allocation/count
boundaries, skipped RNG and all pre-existing actor bytes outside the
permitted tail-animation write on full-pool refusal.

The 480 ordered cases combine:

- Actor/pickup counts `(0,0)`, `(1,0)`, `(29,0)`, `(29,13)`, `(29,14)`,
  `(30,0)`, `(30,13)` and `(30,14)`.
- Effect, marker, monster, reward and static-bomb tail categories.
- Two animated tuples and the stopped tuple; static bombs use stopped only.
- RNG seeds `0x12345678` and `0xffffffff`, and pickup sprites 80 and 90.

There are 240 admissions, 120 full-pool attempts and 120 pickup-cap skips.
Each output record contains actor count, pickup count, RNG and the seven
animation bytes for every live actor in physical/shared order. The combined
79,320-byte original vector has SHA-256
`a6e62f1397c08c90a4b1f88d45a66add2e883f5b8bc6ce8856c73cc5a55e09d1`.
The metadata pins the original executable, native sprite-descriptor fixture,
capture generator, executed caller bytes, case order and compressed vector.
The entire original executable is pinned, including all executed helpers.

Reproduce into a new directory using the pinned executor:

```sh
env SDL_AUDIODRIVER=dummy python3 -B tools/capture_original_pickup_post_init.py \
  --out /tmp/lezac-pickup-post-init-original
```

The generator refuses to overwrite either evidence file.

## Compiled Comparison And Diagnostics

`--debug-original-pickup-post-init OUTPUT` seeds the same controls and calls
the production `collectObjectiveTiles` path. It writes actual live actor
animation/count/RNG state; it does not read the expected original vector.
`tools/check_pickup_post_init.py --exe EXE --out DIRECTORY` independently
checks all emitted bytes against the pinned executed-original fixture.
Each invocation retains expected/actual bytes, stdout, stderr and either
`result.json` or `failure.json` in a unique directory. A mismatch identifies
the ordered case, controls and byte offset.

CTest registers the compiled comparison, a source/provenance/comparator
contract and mocked failure-retention tests. Focused CI runs them with
the existing actor-limit regression before the full suite on Windows and
Linux. Always-run uploads retain focused and final diagnostics separately,
including final CTest logs. The mock tests cover success, nonzero exit,
missing/truncated/extended/corrupted output, wrong coverage banner, timeout,
directory-instead-of-output, launch failure and repeated-run preservation.
Mocks and static contracts do not establish compiled execution.

## Scope

These are controlled original machine-code cases, not natural DOSBox
gameplay. Natural full-pool pickup reachability remains unproved. The
compiled comparison covers animation/count/RNG bytes, not all actor fields
or subsequent actor updates. The original capture additionally checks
preservation of pre-existing actor bytes during the caller window.
Arbitrary inherited animated bomb records are not represented by the
current C++ bomb model and are not covered by the static-bomb cases.
No rendered, physical-timing, sound, natural campaign or whole-game parity
claim follows. Global completion/fidelity flags remain unchanged.
