# Timed Fixture Physical Seed Isolation

Exact-head PR345 CI run `37887541169` failed `timed_writeback_original`
and `timed_writeback_replay_guard` on both Linux and Windows. The complete
logs are retained losslessly with raw and compressed SHA-256 values.

The older typed diagnostic reuses actor identity 1 across independent
fixture rows. After raw corpse countdown became authoritative, its adapter
did not overwrite the physical slot on each row. A later case could inherit
the preceding timer and expire instead of replaying its independent seed.

Reset physical slots at each explicit diagnostic row boundary, before
constructing either typed caller. This does not add a production projection
fallback or change corpse update, allocator, countdown, motion, animation,
fixtures or expected state bytes.

A standalone compiled regression checks the raw input/output timers of all
592 corpse rows in the unchanged 1,184-case fixture using actual `ActorSlots`
and the production countdown helper. Omitting the reset is a failing
negative control. This narrow test does not execute the complete App or
claim full motion/storage equivalence.

Both CI hosts run the standalone seed test and the two affected actual-App
replays immediately after build, retaining focused logs before the full
suite. Fresh exact-head App/Windows/Linux results and completed external
review remain required before merging. Prior focused corpse-storage success
does not override the failed full suite. No live CI head is replaced.
