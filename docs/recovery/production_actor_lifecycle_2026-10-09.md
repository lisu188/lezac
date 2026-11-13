# Production Actor Lifecycle Integration

This candidate integrates physical allocation, stable retirement, and retained
animation backup bytes into the production App. It depends on the animation,
corpse-prologue, transient-backup, corpse-identity and reward-mode recovery
branches. It is not full 38-byte record ownership or natural campaign proof.

## Ownership Boundary

`ActorSlots` binds a nonzero typed gameplay identity to the physical slot in the
original-backed `ActorStorage`. Constructors for transient effects, launch and
portal markers, bombs, spawner monsters, independent rewards and GRAN boss
records allocate through this owner. Capacity comes from the physical count,
not a fresh sum of typed vectors. Expiry retires physical slots stably. Ordinary
level reset uses the recovered partial reset and retains inactive nonplayer
bytes, including the seven backup animation bytes at record offsets 29..35.

Transient and monster constructors inherit backup bytes from the physical
slot. The boss reader explicitly installs the copied GRAN backup. Corpse to
reward/fade, bomb to fade, and reward to score marker/fade keep the existing
identity and backup; these transitions are not new allocations. Bulk bomb
expiry reserves every pending conversion while the typed bomb vector is
temporarily absent, so intervening capacity checks cannot release those slots.

The underlying allocator's original proof is documented in
`physical_actor_storage_2026-10-08.md`: 5,852 operations and 9,216,900 compared
table/scalar bytes. That standalone proof is not new App runtime evidence.

## Explicit Diagnostic Adapter

Historical diagnostic, replay and frame-capture entrypoints directly seed,
clear or resize typed actor vectors. They enable a separate compatibility
adapter, which adopts these fixture identities and explicitly supplied typed
backup fields and retires removed fixture bindings. Adoption and retirement
counters record these adaptations. Interactive play does not enable this
adapter, does not reconcile records from typed vectors each tick, and rejects
the legacy identity-only constructor helper.

The new `--debug-production-actor-lifecycle` regression disables that adapter
before any actor operation and asserts both counters remain zero. It seeds
inactive backup bytes explicitly, then calls production constructors, update
and expiry paths. It covers stable deletion/reallocation and mode-3 restoration,
capacity failure, retained backup after level reset, seven constructor groups,
full-capacity bomb and corpse conversions, reward expiry, and boss backup copy.
It is a controlled lifecycle test, not a natural route or native DOS capture.
Existing diagnostic passes with adaptation enabled do not prove ownership.

## Validation and Remaining Work

`actor_slots_binding_contract` performs 1,800 append, retire, reset and backup
write operations. Local ASan/UBSan execution repeats those operations. Three
compiled negative controls reject clearing constructor backup bytes, keeping
a deleted identity during compaction, and clearing the retired physical tail.
The fixture restoration API rejects count 255 before indexing the identity
array, duplicate/missing identities, player-2 identity, inactive identity, and
invalid core counts without altering the previous state.

Local bounded validation passes the binding tests, App syntax, source ownership
and GRAN guardrails. Full local App builds are deferred because the Windows
backing volume is above the repository reserve threshold. Linux and Windows CI
run and retain the focused actual-App regression before the remaining full
suite. An authored test and a configured CTest entry are not a runtime pass;
exact-head results must be inspected before asserting App validation.

Typed vectors still own active motion, timers, kinds, animation cursors and
other gameplay fields. Those fields are not yet fully written through physical
records before retirement. The physical visual table, boss links, immutable
descriptor guard and rendering are not yet authoritative App consumers. Natural
initial and stale-slot contents, all record fields, campaign progression,
physical timing and sound remain open. This stage must not be represented as
complete physical-table integration or complete game parity. No broad status
or completion flag changes. Every agent-launched run uses dummy audio.
