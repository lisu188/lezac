# Monster animation GRAN boundary repair

PR337 at `2f17e4a0ae991df0b70a135217900277d13e2067` passed the
compiled helper, production App animation regression, and fixture contract
in Linux CI run `37856882002`. The full Linux suite nevertheless failed its
`gran_usage_guardrail`: the new `spawnLevel7Boss(gran_)` call in `resetLevel`
moved the resource reference outside the approved production consumer.
The completed job was `113583088502`; the retained full log SHA-256 is
`b419d46db92664c71f808a23648b793b8452d323118b72d4a8ca2a41205099af`.
That failed run is evidence of the defect, not acceptance of the repaired code.

The repair restores the existing no-argument `spawnLevel7Boss()` production
entry. It forwards the catalog-owned bank to `spawnLevel7BossFromBank`, which
contains the unchanged construction body. The seeded regression uses the same
explicit-bank construction helper to check the shipped and distinct backup
bytes. No GRAN whitelist, source-count expectation, fixture, or animation
rule is relaxed or changed.

Both hosted jobs now run the three focused animation tests and two GRAN
ownership checks immediately after building, and retain that `LastTest.log`
before later CTests can replace it. The full suites remain required.

Local validation is bounded: source/ownership guards and their rejection
controls, App syntax, the compiled animation helper and fixture contract, and
CTest/workflow registration. It is not a new local production App build or
runtime proof. New exact-head hosted CI and completed review remain mandatory
before merge. Natural routes, full actor-storage integration, sound parity,
and whole-game fidelity/completion remain unverified.
