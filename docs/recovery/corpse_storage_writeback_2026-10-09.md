# Corpse Countdown And Reward Construction Writeback

## Recovered Contract

The normal kind-0x0c, behavior-2 path now writes its animation, common motion,
fraction words, visual coordinates and raw half-rate timer through physical
ActorSlots. The raw byte is authoritative for bound corpses; both zero and 255
expire after subtraction of the odd-frame bit. Existing remaining-update
diagnostics are a projection, not a replacement countdown. Boss debris remains
on its separate existing path.

Reward/fade conversion reuses the same actor and visual identity. Reward rolls
40..99 use inclusive bounds 65/71/78/83/89/93/100 and change only kind, timer,
VY, hotspot, animation mode and descriptor bytes. Rolls below 40 set the fade
timer/velocities/behavior/animation/descriptor while preserving fractions,
coordinates, animation backup and opaque record bytes. No converted actor is
dispatched a second time in that pass.

Two particles still consume four RNG draws after the selection/sound draws,
including allocation failures. Successful appends run in the same ordered
pass. The production SoundEngine retains request cursor/priority even when
the existing signed-byte priority gate rejects replacement of active sound.

## Original Evidence

The fixture executes the unmodified original shared actor pass under the
pinned native CPU executor. Two independent executions agree, and additional
within-conversion observations leave full memory/register state equal to the
neutral executor. The controlled matrix contains 940 cases, 3,252 complete
1,593-byte boundaries, 1,344 corpse-motion steps and eight full timer-25
countdowns. It covers every reward roll, counts 1/28/29/30, front/back corpse
positions, reversed visual references, inherited animation modes, both tick
parities, zero/one/255 timer boundaries and signed sound-priority edges.

Each state includes all 31 actor records, 33 visual rows, eight link rows,
counts, allocator result, RNG, pending bonuses, hit/alive gates, reward roll,
request cursor/priority and active sound cursor/priority/flag. Inactive tails
and opaque bytes are compared without masks.

Original LEZAC.EXE SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`

Raw requests SHA-256:
`2f623d2a057425b71466c1b3fa75d5c6968a9f347a094c0fc034aa7b2a659790`

Raw expected output SHA-256:
`5ecc7a2666dc2444261d5332bfbdc8ea162df13fa6a9c92c9b27d31b3408febc`

## Validation And Limits

The compiled shared-helper probe matches all 5,180,436 boundary state bytes.
AddressSanitizer/UndefinedBehaviorSanitizer replay also matches. Fourteen
compiled production mutants are rejected, covering timer parity/sentinels,
motion, reward thresholds/impulse/mode, fade animation, physical visual and
animation writes, descriptor/fraction/backup preservation and sound state.
The actual-App command seeds physical/typed state only at S boundaries, then
uses updateOrderedActors without legacy adoption. CTest checks helper/App
original replay, 36 malformed requests against each executable and checker
contracts. Focused CI retains complete comparison/protocol diagnostics on
both hosts; actual-App runtime acceptance requires inspecting those results.
The older direct corpse-playback diagnostics now advance the frame counter
between actor passes, matching the native half-rate countdown contract.

The evidence directory `evidence/corpse_storage_20261009` retains the native
producer/validator, independently repeated native reports, bounded compiled
validation, full-output compiled-mutant hashes and prepublication checks.
Large native JSON reports are losslessly gzip-encoded; their compressed and
raw hashes are recorded in the evidence manifest.

This is controlled corpse countdown and in-place conversion evidence, not
natural fatal-entry construction, direct reward allocation/cloud policy,
natural campaign reachability, rendered fidelity, sound ISR/playback parity,
or complete raw-record ownership. All broad completion and fidelity claims
remain false, and raw_prefix_guard_status remains failed.
