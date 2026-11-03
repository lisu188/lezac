# Wrapped Collapse Magnitude

The original fracture gate performs a word subtraction, takes the signed
absolute value of that wrapped word, and compares the resulting **unsigned**
word with 63 (`1000:5565..5576`). The App previously subtracted in an unrestricted
`int`. That incorrectly fractured a two-cell structure for previous magnitudes
`0xFFC1`, `0xFFFE` and `0xFFFF` when the current magnitude was zero.

For example, `0xFFFF - 0` is signed `-1` after the original word operation, so
the original delta is 1 and the structure survives. The old App used 65535 and
incorrectly added two destruction credits. The new `collapseMagnitudeDelta`
helper returns the original word result for both the shared result and the
fracture decision. It also preserves the unsigned `0x8000` absolute-value case.

## Evidence

`tests/fixtures/collapse_magnitude_wrap_original.json.gz` contains 17 original-
only controlled updater cases, frozen producer sources, asset fingerprints and
the REA/Ghidra observations. Expected outputs never come from C++ traces.
The old packaged App differs in three cases; the fixed App matches all 13,585
expected bytes, covering live map planes, records, RNG and progression counters.
Actor and sound-bank bytes are not part of this compact App comparison.

Unicorn 2.1.4 executes the unchanged original initializer and complete collapse
updater, including its original calls, to the real return boundary. An observer
control compares all 1,048,576 internal memory bytes and 14 registers with a
no-op trace callback. No original instructions are patched, calls are not
stubbed, and hardware I/O is forbidden. The actual mapped emulator library is
fingerprinted. Complete memory is compared only in RAM; only hashes, registers
and compact map/record outputs are retained, not full guest RAM images.

REA 6.7.0 with Ghidra 12.1.4 on WSL independently byte-verifies 15 selected
instructions and resolves `5586 -> 165A` and `5589 -> 4FDA`. The original target
is unchanged and the session closed with server exit 0. Selected static
observations are not proof of complete instruction recovery or gameplay.

The arithmetic unit test checks every previous word against every current
magnitude from 0 through 256: **16,842,752 comparisons**. Portable fixture tests
reject altered scope, sources, cases, instruction bytes, expected outputs and
compressed data; failed, timed-out and preflight-failed App probes retain
diagnostics.

```sh
env SDL_AUDIODRIVER=dummy ctest --test-dir build --output-on-failure \
  -R '^collapse_magnitude_wrap_(unit|fixture|checker|original)$'
```

Fresh GCC 13.3 C++23 and native Windows MSVC App builds match the 17 cases.
The MSVC arithmetic test passes `/std:c++latest /W4 /WX /permissive-`.
Existing collapse, retirement, capacity, lane-history and physics-dispatch
regressions pass. The fixed Linux App also matches the original bridge-access
and bridge-escape frame windows. All runtime validation uses dummy audio.
The newly linked MSVC App also matches all 761 bridge-escape RGB frames and
1522 covered state boundaries; its live SDL DLL path and hash were observed.

## Scope

These are controlled initial record states, not a naturally captured occurrence
of the high previous words. Ordinary seeding normally starts the magnitude in
0..256; this evidence does not claim natural reachability of every raw word.
The fix restores the original behavior for the record's full stored word.

The Level 4 navigation trials did not add destruction credit: progress remains
261 of 305, with 44 cells still needed. This correction does not establish
Level 4 completion, Level 5 entry, physical-input, wall-clock, all-actor-field,
audio-waveform, two-player or whole-game fidelity. Existing actor-stability
holds are unchanged.
