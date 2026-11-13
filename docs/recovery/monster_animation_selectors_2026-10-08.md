# Living Monster Animation Selectors

Original actor bytes `+3` and `+4` retain the left and right animation-set
selectors independently of the current animation cursor and visible sprite.
The shipped spawner constructor writes them at `1000:7BDA` and `1000:7BF2`
from `DS:0080/0081[2 * spawner[11]]`. The observed right-facing consumer at
`1000:72E3` reads actor `+4`, then indexes the frame-pair table at `DS:0058`.

The unchanged executable is SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The native profile fixture is SHA-256
`b1c71fb54958a9cac974c30813ba55c157ff50cdb5bfa33688a97ab0cbfe79ea`.
Its 45 constructors and 5,805 constructor/pre/post states retain selector pairs
`{1,2}`, `{11,11}`, `{12,12}`, and `{13,13}` for shipped kinds 1 through 4.

The production spawner now stores both selectors on `ActiveMonster`. Animation
refresh and facing reselection consume those stored fields. Zero selectors
retain the existing kind-derived fallback for diagnostics that seed typed
monsters directly. The known shipped ranges and zero-velocity behavior are
unchanged; this is recovered state representation, not a newly discovered
shipped gameplay divergence.

`monster_animation_selectors` compiles the production header and checks all
retained selector bytes, 17,415 directional range lookups, two synthetic
stored-selector overrides, and 15 legacy fallback cases. The full production
`shipped_monster_profiles_original` replay additionally compares the two
stored selector fields at construction and every pre/post boundary. A passing
standalone helper test does not substitute for that compiled application run.

The earlier C++ profile comparator checked 26 of the 38 actor bytes. Adding
these two fields increases its direct typed comparison to 28; it still does
not prove complete raw-record storage or equality. Visual-slot identity,
timer byte `+2`, and preserved bytes `+5` and `+29..35` remain outside this
comparison. Separate synthetic original-code controls show the latter eight
bytes survive the bounded living-monster trajectories unread and unwritten.
Natural stale-slot reachability, other callers/kinds, full shared-pool
preservation, campaign and global fidelity claims remain open.
