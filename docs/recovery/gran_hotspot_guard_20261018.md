# Copied GRAN Hotspot Diagnostic

Full Linux and Windows CI for #442 at `43bfc24` passed the repaired complete
corpse-storage step, then failed `production_actor_lifecycle_app` with
`active sprite bank physical hotspot mismatch` in run `39160461379`.
The actual Linux App reproduced that failure before this change.

The diagnostic used the generic constructor's derived hotspot rule for every
actor, including the seven boss records. The original `1000:08A5` group loader
instead copies byte 20 from each `GRAN.MST` record. All seven canonical source
bytes are zero. The authenticated unchanged-original loader projection in
`tests/fixtures/gran_loader` independently contains zero for all seven loaded
records, while preserving their other raw bytes. Production group loading
already matches that full original-backed projection.

Only `debugProductionActorLifecycle` changes. Its descriptor helper now checks
an explicit expected hotspot. Generic allocation probes retain the exact
sprite-31/derived-height rule. Boss initialization probes require the original
copied zero values, rather than deriving a different value from sprite height.
All 295 existing descriptor checks remain.

Seven new negative controls corrupt each boss's physical hotspot individually,
require the precise hotspot-mismatch failure, and restore the exact seeded
state and identities. The CTest contract requires all seven copied-hotspot
checks and all seven corruption rejections. No test is removed or skipped.
No production gameplay/loader/rendering function or original fixture changes.

A rebuilt complete Linux App passes 12 focused CTests: the lifecycle test,
actor bindings/storage, complete original GRAN loading and fixture controls,
the no-legacy physical boss render/damage/debris diagnostic, and both original
corpse lanes plus protocol/checker controls. All launches use dummy audio/video
and generated files remain in RAM. The pre-fix hosted failures are retained.

This is a bounded diagnostic correction backed by original data, not a new
natural-play or full-game parity claim. The new integration head still needs
completed exact-head review and full Linux/Windows CI before merging.
