# Buffered Menu And Intro Input

This recovers future typematic input at the main menu and level introduction,
and the introduction's consumed typing-key boundary. It is not whole-game,
manual-input, natural timing or other-page repeat parity.

## Original Evidence

The shipped executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
At main-segment `23c2..23d3`, the menu drains pending CRT keys, then reads a new
choice at `23d5`. It tests the returned character, not a key-down edge. The
introduction also calls CRT.ReadKey, at `2c72`, after its text renderer returns.
The CRT entry `084a:02fd` checks BIOS INT 16h/AH=1; `084a:030f` uses AH=0 to
read a character. These are file offsets `8f0d` and `8f1f`, using MZ base `0770`.

Three ungated observations use private Xvfb, dummy audio and an owned temporary
DOSBox copy. Each installs only the existing natural startup-clock observation
hook, without replacing clock values, setting a seed, gating delays or writing
gameplay state. Physical X11 input is scripted, not authentic manual play.
All three captures restored their clock hook and exited with code 0.

A fourth capture, `evidence/intro_queued_buffer_original_20260930.json`, briefly
stops only the owned DOSBox to enqueue Space and Return in one physical input
batch. After resuming, both are consumed by typing; the full intro remains
unchanged through two seconds and Shift until a fresh Return. This input batch
is gated, unlike the three ungated observations; text delays and RNG are not gated
or replaced. Its clock hook was restored and its child exited with code 0.
The accompanying compressed observer's decompressed SHA-256 is
`c6199fbbb65274388b902d7206a7a041939bdbfe492ee5a8954c54644b3ae1f5`.

- `evidence/menu_held_choice_original_20260930.json`: one key-down of `1`
  during natural Italian menu typing, held for three seconds. The initial key
  completes the menu; later repeat input reaches live level-1 gameplay before
  release. The X display's repeat delay/rate was 660 ms/25 Hz. The original
  gameplay screenshot is `evidence/menu_held_choice_gameplay_20260930.png`.
- `evidence/intro_buffer_original_20260930.json`: select `1` from the ready
  menu, press Space during intro typing, wait two seconds, press standalone
  left Shift, then press Return. The initial caption had 31 white pixels;
  after Space, the complete caption had 620. The frame remains identical
  through the wait and Shift, and only Return reaches gameplay. The retained
  waiting frame is `evidence/intro_buffer_awaiting_20260930.png`.
- `evidence/menu_held_two_original_20260930.json`: the same natural-menu
  experiment with one held `2`, using the same 660 ms/25 Hz X repeat setting.
  The retained three-second screenshot shows live split-screen two-player
  gameplay before key release. The observer source's decompressed SHA-256 is
  `e3bc8c1bba1201baf1d1d330c4cdd65cff8da268fd75a31fe8d9a0fb47eff8df`;
  its full-frame RGB SHA-256 is
  `dbb5a54adcbc665b6a9a4eac5d00f8d003097e099186c3b3439a4ea27a4e49f4`.
  The screenshot is `evidence/menu_held_two_gameplay_20260930.png`, and the raw
  record remains in `/dev/shm/lezac-original-menu-held-two-20260930`.

Compressed observer snapshots beside these records preserve the exact executed
source. Their decompressed SHA-256 values are, respectively:

```text
896459868114f63da1ce0b95ca43c32e672d8f118e44aabe8d02b183143425bf
41c08a95ddc7abe6d80f36ed854ec105c3f2c19ea88fce52af2d78582d5d4b32
```

The raw captures remain in `/dev/shm/lezac-original-menu-held-choice-20260930`
and `/dev/shm/lezac-original-intro-buffer-20260930`. Before this change, the
packaged C++ executable `5aa3bc3dbf05952fb051ad6cbe6227b7a77724f3c92a9e020a3fbd37f48249d9`
stayed at the completed menu throughout the same held-`1` observation. That
negative result remains in
`/dev/shm/lezac-cpp-menu-held-choice-9b3333d-20260930`; it is not a parity pass.

## Recovery

The App's SDL repeat gate now admits buffered keys at the main menu and intro.
Main-menu skipping still consumes the triggering key and drains queued key-downs;
future repeats are not discarded. Pure modifiers, locks, GUI and unknown keys
remain non-buffered, including during the intro. Gameplay fire and command
repeat policies, and the separately recovered name-entry policy, are unchanged.

`LevelFlow` distinguishes typing from its blocking key wait. A key while typing
reveals the whole caption and is consumed, without loading gameplay. A later
key acknowledges the intro. Pending key-downs are drained at the typing skip,
so a queued acknowledgement does not leak through. Starting another intro clears the skipped flag.
The inherited normalized intro delay/rendering model is not promoted to full
phase or calibrated wall-clock parity by this input change.

The existing reserve-life diagnostic and physical helpers now supply both keys.
Four deterministic replay routes add Return down/up at ticks 1/2 as the consumed
typing skip. Their existing acknowledgement at tick 3, seeds, step duration and
all gameplay inputs retain their previous values. No captured original gameplay
fixture, acceptance threshold or evidence status is reseeded or relaxed.

The sealed original gameplay fixtures have a different prelude: their recorder
waits for the complete original caption before the tick-3 acknowledgement,
then begins gameplay samples at tick 4. Their immutable route files omit that
wall-clock wait. The C++ recorder's explicit `--original-intro-wait` mode advances
only its virtual presentation clock to the natural complete-caption boundary
before that acknowledgement. It does not add keys, mutate RNG/gameplay state,
change the route's sampled gameplay clock, or change the original fixture bytes.
The trace identifies this adapter as `sdl-events-original-intro-wait-v1`, and
validation rejects a different prelude. Ordinary recording and interactive play
never enable it. Original comparison still requires byte-identical input streams
and unchanged full-frame/state projections. The pre-fix parity failures remain
negative diagnostics, not passes.

## Verification

- `ui_components` checks natural wait boundaries, unsigned clock rollover,
  complete-caption skipping, retained blocking wait and reset on the next intro.
- `buffered_menu_repeat_dummy` pumps actual SDL key-downs with `repeat=1` for
  both player choices: consumed menu skip, later selection, ignored modifiers,
  consumed intro skip and later acknowledgement. It also checks unchanged
  repeated gameplay commands, consumed Escape and rendered intro/game frames.
- `buffered_menu_repeat_live_xvfb` uses the normal interactive loop, with the
  existing read-only held-key observer configured for `1` or `2`. Each held case
  must reach a gameplay sample with at least three SDL repeat events, no key-up,
  the physical key still held and the selected player count. Window captures
  must show actual gameplay, not merely an intro or a changed menu frame.
- A third physical case checks that intro Space and Shift leave the fully drawn
  intro blocking until a fresh Return, including a gated Space/Return input
  batch that must both be consumed. CI retains every case's event trace,
  screenshots, executable/harness hashes and failure records.

The final local production executable SHA-256 is
`1d6405052e88b4c5a84c816c0ab8cc19ce01c5967cc094154f60f038aa4a4eca`.
Its three physical cases passed in
`/dev/shm/lezac-buffered-menu-presentation-clock-final-20261001`, with dummy
audio and no forced gameplay seed. Original/C++ held-choice screenshots are
comparable states, not frame-aligned or pixel-parity claims.

All 16 selected local CTests passed in 140.38 seconds. The five sealed original
routes (walk, bomb, objective, held fire and rapid fire) compare 1,369 complete
frames, 87,616,000 pixels and 2,738 present/post state projections with zero
differences. The original guard still rejects its 16 mutations, and the replay
suite's 16 tests include 14 prelude mutations across both player choices. The
guard checks byte-identical route data and unchanged normalized replay clocks.
The full CTest log is retained at
`/dev/shm/lezac-buffered-menu-final-focused-tests-20261001.log`, SHA-256
`dd04112c4490be9b9cc61f13cc670128fa01536eb25ef6c8a6f363bb13bea392`.
The silent-launcher policy also passed separately.

The preceding CI head `c8a68fd` failed six original fixture/guard checks because
its replay omitted the original intro wait. The Linux live check also failed
before gameplay observation because `xset` was absent. CI now explicitly installs
`x11-xserver-utils`; that failure is not an input-parity result. The unchanged
fixture and negative-run records remain preserved.

Windows disk usage was rechecked below 90% before the bounded production target
was built in RAM. Broad local builds remain avoided; full Linux/Windows suites
run in CI. Pending CI checks must not be described as passes.
