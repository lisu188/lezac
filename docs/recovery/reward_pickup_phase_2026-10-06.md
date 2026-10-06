# Reward Pickup Phase Recovery

## Original rule

`LEZAC.EXE` SHA-256:
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Code-image file offset is `0x770`; addresses below use the recovered `1000:` CS.

The actor pass latches a reward independently for each touching active player.
`63F6` and `6497` reject an occupied per-player latch (`DS:79AE/79AF`). Both
contact tests use the cached original reward kind, so both players can receive
the same reward. Contact uses the existing signed-word strict ten-pixel test.

Conversion at `6447/64E8` consumes `Random(3) + 1`, multiplied by `-100`, for
each accepted player. It reuses the actor slot as kind 11, behavior 5, timer 26
(25 after an odd-frame decrement), and preserves position fractions. The current
dispatch still uses the cached reward motion path; later ticks use behavior 5.
The one-based marker descriptor table at `AA64` is `88,86,87,88,89,86,90`.

The player dispatch copies the pending latch at `61C2/622F`. The grant gate at
`6E42` follows the cached objective-tile scan, allowing intervening actors to
consume random numbers first. Yellow grants use `Random(10)+1` and
`Random(4)+1`; green grants use `Random(13)+1`, `Random(5)+2`, and
`Random(2)+1`. Neither grant changes the selected weapon.

The C++ port previously awarded immediately, omitted the conversion draw and
floating score marker, chose only the nearer touching player, and could change
weapon selection. Recovery replaces those behaviors with the original order.

## Runtime observation

An unchanged ordinary-input Level 3 route, SHA-256
`481b2e36fccf6a0692a949824972ca067139e83014fccb1879ff570506f06bda`, collects a
yellow reward at route tick 7719. The pre-pickup seed is `1850251855`.
The original consumes five draws: conversion, two later hopper draws, and two
player-phase ammunition grants. The resulting seed is `1117830504`, medium
ammunition is 16 and large ammunition is 1. The old port consumed four draws
and first differed at the post-update boundary of this tick.

The corrected replay matches the unchanged original capture over 748 RGB
frames and 1,496 mapped lifecycle boundaries (fork tick 7353 through 8100).
The raw suffix has 2,241 DS boundary records. Comparison also checks mapped
terrain and bounded live/corpse actors, with 102 bounded score-marker
observations. Eight deliberate projection mutations are rejected.
At the endpoint both versions have nine objectives, 110 destroyed tiles,
health 66, medium ammunition 13, large ammunition 1 and seed `412283955`.

Original capture SHA-256:
`4e3a2b86f4cee69c7bd919669fd53a29bcbdb357f9ac9461ffd888ef291e6b08`.
Raw DS suffix SHA-256:
`657c54bc29f7bc2c533acfe95c37dd05863317cc2a5ee2cbef06125a6cde631b`.
The original bytes are independently retained under
`refs/notes/qa-natural-level3-20261005-yellow-ammo-original-20261006-raw`
and its chunk refs, anchored at `2912cb1ccfc6a7903f6753dab7b88192defd85c0`.
The local control reports are in
`build-codex-tmp/bonus-pickup-rng-work-20261006/`.

## Regression coverage and limits

`reward_pickup_phase` covers seven reward kinds, two frame parities and two
seeds: 28 deterministic cases, plus both-player latches and strict contact.
It checks conversion, inherited fractions, slot identity, deferred grants,
intervening draws, health, scores and preserved selection. These are explicit
helper tests, not 28 native or ordinary-play routes. The opcode checks pin 13
original windows and reject 198 single-byte mutations.

The initial focused local CTest run passed 17 of 18 tests, including reward
lifecycle and the existing natural Level 1/2 campaign replay. The full Level 3
return replay exhausted RAM output space and failed with
`basic_ios::clear: iostream error`; it did not reach a fidelity comparison.
Its partial output is preserved. Previously independently retained working
duplicates were byte-reverified and retired to restore the unchanged reserve
floor. The large local replay is not represented as passing.
After reserve restoration, 16 bounded focused tests pass, including the new
pickup and opcode checks, existing reward lifecycle and natural-route guards.
That rerun excludes the two full-frame producers and does not replace them.

All launched gameplay and test processes use dummy audio. This work does not
establish audible sound parity, all actor bytes, full-prefix C++ comparison,
physical timing parity, Level 3 completion, later levels or whole-game fidelity.
