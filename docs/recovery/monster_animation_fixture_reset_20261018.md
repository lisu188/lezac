# Independent Boss Animation Fixture Storage

Full Linux CI on reviewed heads `68c5b146` (#442, run 39162795505,
job 117779436670) and `1788fd75` (#443, run 39162860484,
job 117779627060) passed the repaired corpse and lifecycle gates, then failed
`monster_animation_original_app` with `GRAN group exceeds physical storage`.
The other seven tests in that focused group passed. Complete job logs are
retained in the RAM-only `lezac-ci-monster-failure-t240` evidence directory.

The diagnostic independently loads shipped and modified boss animation-backup
samples. It cleared only the typed monster vector and restarted typed identity
allocation, leaving physical actor, visual and link state from preceding work.
The recovered loader correctly rejects an inconsistent base or another six-link
group when only seven physical link rows are supported.

Only `debugMonsterAnimationOriginal` and its CTest success marker change. Each
sample now uses the existing physical level reset and checks zero active actors,
two player visuals and zero links before loading. After loading it requires seven
physical actors, nine visuals and six links, in addition to all fourteen existing
animation-backup byte comparisons. Each sample then attempts a second real load,
requires the precise unchanged capacity error and verifies preservation of the
complete physical state, typed actor/link counts and next identity.

No production loader, capacity rule, actor updater or original fixture changes.
This is a seeded diagnostic integration repair, not new original runtime, natural
route, visual or whole-game fidelity evidence. The full hosted platform suites
must rerun on the new heads; the prior failure is not treated as a pass.

The rebuilt App passes all fourteen selected monster/corpse animation, GRAN,
lifecycle, physical ownership and source-guardrail CTests. This includes the
actual App skip-animation mutant. The first local selection could not run that
adjacent mutant because its executable was not built; after building the target,
the complete rerun passes. A fresh silent App boss-ownership run also passes eight
ticks, 48 physical link checks, two distinct rendered frames and seven controlled
death conversions. It is seeded and does not compare the original game's pixels.
