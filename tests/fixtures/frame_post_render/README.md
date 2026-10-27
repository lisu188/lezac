# Continuous Post-Render Frame Corpus

The unchanged canonical `LEZAC.EXE` executes continuously from `1000:7A57`
through spawners, the waiting prepass, actors, transient queues, and frame tail.
Initial memory is controlled; no state is injected between these owners.
The 1,348 cases comprise the earlier 1,102 actor/body profiles, 64 waiting-state
profiles, 54 spawner profiles, and 128 coherent death/reserve/reentry profiles.

Observer and endpoint-only runs compare every register, complete 1 MiB memory,
and ordered DAC outputs. Ordered writes must reconstruct complete final memory.
The original executable, 21 producer/helper sources, and actual mapped Unicorn
2.1.4 library are pinned. No instructions are patched and no calls are stubbed.

There are 4,983,001 original instructions, 1,431,749 ordered writes, 480 DAC
outputs, and 67 dense traces. All 1,348 cases enter the prefix; 1,332 reach actors,
1,220 reach queues, and 1,218 reach the frame tail. Sixteen cases stop at the
original game-over UI handoff before executing that UI.

Outcomes: 1,140 next frames, 16 UI handoffs, 72 restarts, 53 completions,
nine escapes, 16 view changes, 24 runtime errors, and 18 divide errors.
The whole window contains 40 placement calls and 24 clear helper calls.
Helper totals are window-wide, not per-phase counts. No new coverage of `326E`
or collapse-copy helper `50BE` is claimed by this corpus.

The decoded projection is 28,447,607 bytes, SHA-256
`ada29ff0c33bf4c1d945260e9d958e5946c4fa4b90f1a03c8d89638ede9a0a9c`.
The gzip is 3,349,853 bytes, SHA-256
`f885ce1d91425da17bb1f554f53c70d1d52dfa0e5a72dd5a9300006ef8e85cb9`.
It contains the exact MZ, compact initial differences, selected register traces,
ordered writes and ports, not a full guest RAM image. Independent regeneration
reproduces both frozen files byte-for-byte.

The C++ consumer admits exactly this corpus and the earlier actor/body corpus,
with separate size/FNV/count/entry/coverage contracts. Python supplies SHA-256
authentication; FNV is only an accidental-corruption check.

This is controlled original-executable proof, not natural campaign evidence.
It does not execute the active rendering/clock prefix at `7903`, deliver
hardware inputs/IRQs, integrate the operation into App, or prove a full frame.
The independent actor-pass instability hold remains in effect.
