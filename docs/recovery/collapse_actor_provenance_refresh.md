# Collapse Actor Provenance Refresh

PR #358 corrected the source contract for the two deliberate monster-pool
clears in the physical fracture diagnostic. The collapse-actor manifest still
pinned the preceding `check_original_collapse_update.py`, so PR #359's Windows
CI stopped before executing its legacy collapse-actor comparison.

The unmodified original was re-executed with Unicorn 2.1.4 for all 2,476 actor
cases. The deterministic compressed fixture is byte-identical to the committed
fixture (`a81f73c6bb9a3224d3c3bd5151c8491d8d1381348dcd5a231db6db6e73ceae57`).
The regenerated metadata differs only in the collapse checker's dependency
hash, from `984b053ae617df271f192c3dac9d51863124215a1bba3dbc9518d60c60a110bd`
to `ac7e10c907bfc7fa3a86ecfc2af75fd8fae1b8463be49ab226a4fef40a5170cc`.
Its strict metadata pin is refreshed accordingly.

No expected state, original instruction, production C++ code, fixture byte,
coverage count, or evidence-scope flag changed. The existing actor checker
now also verifies that truncation, appended data, and corruption are rejected
for the metadata and each of its 11 provenance dependencies. The legacy
source contract and byte-for-byte comparator remain enforced.

This is a provenance repair, not new natural-gameplay, rendered-pixel, sound,
or whole-game equivalence evidence. Exact-head integrated CI and external
review remain separate delivery gates.
