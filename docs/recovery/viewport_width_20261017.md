# Original Viewport Width Recovery

## Production Corrections

The unchanged executable's handlers at game CS:820F..8283 use `e` to decrease
DS:C1EA by one tile and `r` to increase it by one tile. The inclusive legal
single-player range is 21..40 tiles, or 168..320 pixels including the frame.
The old App reversed the keys, changed width by 32 pixels, and allowed 160.

The handler clears only screen rows 0..159, calls geometry helper 0838, stores
the new width in DS:79EE, consumes the character as `9`, and calls frame
initializer 2959. A blocked bound or player-count gate does not repaint. The
HUD remains intact. The App now invokes the matching renderer operation only
when width actually changes. Future E/R repeat events are accepted during
single-player gameplay; pause, intro, outro and two-player gating are retained.

The complete frame is centred at `(320 - pitch)/2`; the world begins four
pixels inside it and has width `pitch-8`. The old renderer kept a full-width
outer frame and added non-original yellow lines around the narrowed interior.
Those lines are removed. Indexed margins survive ordinary repainting, and
palette-owned retained pixels resolve through the current palette.

Helper 0838 computes DS:78BC as `floor((pitch/8 - 2)/2)*8`, not the old
`interiorWidth/2 - 4` expression. These differ by four pixels for odd tile
counts. Camera clamping and fine-scroll/shake row carry are otherwise retained.
Backdrop pitch stays latched at 320; shrinking does not repack its backing.

## Independent Original Execution

`tools/viewport_width_oracle.py` executes unchanged original code and callees
under Unicorn 2.1.4. The executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The RAM origin is the authenticated natural foreground capture's
`gameplay-middle` sample, bound through `render_view_gate_origin.py`, its frozen
parent sources/observations/recipe, and all 14 canonical assets.

All 43,552 relocated code bytes before DS are checked against the shipped MZ
image, both before execution and at every final endpoint. Each case runs with
and without the observer; complete 1 MiB memory and all registers/flags must
match. Interrupts and IN/OUT are rejected. No call is stubbed and no instruction
is patched. Unicorn steps are not DOSBox work-clock credits.

The geometry helper receives a declared controlled near-call stack argument
and return. Initialisation, frame setup and render blocks are then entered at
explicit original boundaries. This is not continuous original level startup.
Render inputs retain the original map, 60,000-byte backdrop and sprite backing,
and explicitly isolate one player visual. The frozen payload checks the sprite
against the actual AssetCatalog loader before the C++ renderer uses it.

Coverage is 44 control cases and 60 views:

- E/R at every legal width, including both ignored bounds.
- Two blocked controls at the original 20-tile two-player geometry, plus two
  unrelated characters.
- All 20 legal widths at minimum, middle/shake and maximum/background-off
  camera profiles, including fine-scroll row carry.

`tests/fixtures/viewport_width/oracle.bin.gz` is 119,614 bytes. Its decoded
6,721,438-byte projection has SHA-256
`7c2338a3fd270a925179de2d71babd73e8a9779d892e3a13ad2bffca77fffdfe`.
Manifest SHA-256 is
`f27c9a82089f0bf6eae475d3ce738f0c97b1576626d596448908ba5a822517f2`.
It contains compact indexed endpoints and declared render inputs, not full RAM
dumps or PNG captures. A second final producer execution reproduces the earlier
valid projection byte-for-byte. Early expected-call assertions omitted the two
real rectangle calls nested inside frame initialisation; those failed probes
were retained and not promoted.

## Validation

The actual pre-fix production UI/renderer libraries disagree with all 40 E/R
cases and 464,091 of 3,072,000 playfield pixels. A private baseline callback
adapter mirrors the old App's clamp and absence of frame reset. After the fix,
`viewport_width_original_test.cpp` checks 2,816,000 control pixels, including
the retained HUD, and 3,072,000 playfield pixels with zero differences.

The full Linux App builds and 36 final focused CTests pass. These include
original single/split/tall render corpora, viewport state gates/initialisation,
the new width corpus, HUD and palette regressions, actual-App original/JSON
control smoke tests, physical-key ownership model, and two-player progression.
The App smoke test traverses both bounds with repeated E/R events, verifies
ignored keys do not repaint, and checks the latched backdrop remains intact.

Native MSVC 14.44.35207 compiles four production renderer/UI translation units
at /W4 and the new test at /W4 /WX. The new corpus, UI components, and previous
viewport gate/initialisation tests pass. Verified unchanged dependent objects
are reused. The native and final Linux RGB dumps are byte-identical at SHA-256
`f9d8fa5fffe2faa9e61ed59496f800fe70910100f75ced9f4c04387872baadee`.
This is native component replay, not a full native Windows App build. Existing
unrelated production warnings remain.

The frozen checker binds its manifest, original producer/helper sources, parent
RAM provenance and canonical assets before exporting anything. Two Python test
methods and 88 changed/missing/new/existing-output rejection controls pass on
Linux and Windows. Matching decoded outputs are not rewritten.

Five isolated C++ mutations are detected: old camera centre (59,998 bad view
pixels), full-width frame (1,083,879), clearing the HUD (486,400 bad control
pixels), reversed keys (40 bad controls), and 32-pixel steps (36 bad controls).
Production sources are unchanged by these mutation runs.

A first actual-App repeated-key replay exposed the remaining event-filter
bug: only widths 320 and 312 appeared. That executable, source blob and failed
replay are retained. After fixing the filter, the final actual-App replay
visits all 20 widths and passes 547,356 frame/margin pixel assertions. Its
minimum-width full-scene capture was inspected. This uses normalized SDL event
injection, not original host typematic timing.

A fresh final App walk still matches the pinned original capture across 41
full frames, 82 projected states and 2,624,000 pixels. Existing controlled RNG,
normalized inputs, paused-original-main and actor-field projection limits are
unchanged. The separate live SDL regression passes seven physical movement/jump
cases on the pre-repeat-filter build; all 220 generated frames and logs are
retained. It does not establish original E/R host timing.

## Remaining Fidelity Work

Original DS:79B8 counts players not yet eliminated, including waiting state 2.
The configured two-player case is
blocked here, but natural elimination can change that count and has its own
viewport clearing/reconfiguration path. Equivalence after a player is naturally
eliminated is not proved by these controlled state/width cases and needs a fresh
end-to-end investigation. Global App keyboard queue draining/coalescing and
instruction-work timing also remain unrecovered; accepting future E/R repeats
does not claim multiple queued events are applied at the original phase.

The later [survivor viewport investigation](survivor_viewport_20261017.md)
recovers controlled elimination, survivor resize and next-level pitch behavior.
It does not close the natural-death-route or keyboard-phase limits above.

Whole-game cadence/owner-bus integration, natural interrupt delivery during
rendering, IRQ1, sound waveform fidelity, all campaign paths and owner visual
acceptance remain incomplete. No full-game or unrestricted visual-fidelity
claim is made.
