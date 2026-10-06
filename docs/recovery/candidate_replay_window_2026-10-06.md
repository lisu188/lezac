# Candidate Replay Window

`--replay-level1-scout ROUTE OUTPUT_DIR START_TICK` executes the complete ordinary
SDL-input route from its original seed, but stores gameplay checkpoints and
presentation images only from the positive, inclusive `START_TICK` onward.
The optional original-intro-wait, result-reels and result-typing flags retain
their existing order and behavior. Result observers still execute throughout
the route, including before the gameplay capture window.

This is a search aid for ordinary-input route candidates, not accepted replay
evidence. Its trace uses `lezac.level1.scout.v1` with `candidate_only=true` and
`capture_from_tick`; the existing full-trace validator rejects it. Original
checkpoint sequence numbers and full-route event/checkpoint totals are retained.
The footer separately reports retained checkpoints and actual retained gameplay
frames. Completion and fidelity claims remain false.

The normal `--replay-level1` contract is unchanged. An accepted candidate must
still be re-recorded through the full production replay and compared against
the original, including all required state, lifecycle, terrain and RGB gates.

The production integration regression compares every retained state, event,
clock, sequence number and PPM byte against full runs. It covers a held key
before the window, first/last tick windows, original-intro timing, result
observer streams, original-asset preservation, invalid windows/flags and
rejection by the full evidence validator. It does not prove whole-game fidelity,
later-level natural completion, wall-clock timing or sound parity.

Local Linux validation passed all four focused CTest targets: the candidate
window integration, full Level 1 replay, original evidence guards and campaign
boundary checks. A separate complete 8,953-tick ordinary-input Level 3 replay,
captured from tick 8,153, matched all 801 retained gameplay PPM files and every
retained checkpoint line byte-for-byte against its independently retained full
C++ run. The result-reel stream and images also matched. The new 800-tick suffix
is still C++-only evidence; this equivalence does not promote it to an original
comparison or establish natural Level 3 completion.
