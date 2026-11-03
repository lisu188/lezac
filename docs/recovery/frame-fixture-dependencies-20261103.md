# Frame Fixture Dependency Repair

## Confirmed Hosted Failure

PR #472 head `d5f265d3b8240cfd111f10b158d329a8e89f0e9d` finishes its
[Windows full-suite job](https://github.com/lisu188/lezac/actions/runs/41530681835/job/125570544684)
with six failed or not-run tests out of 1191. The frame-iteration and
post-render fixture manifests still pin the old `oracle_failure_report.py`,
before its Windows dangling-link preservation repair. Both authenticators and
their rejection tests fail; the dependent original C++ replays are not run.
The historical job remains failed. It has not been rerun or reclassified.

## Fresh Original Recapture

Both canonical original producers run again in RAM with the current helper,
the pinned original `LEZAC.EXE` and Unicorn 2.1.4. Complete observed and
unobserved original memory/register/port results agree within each producer.
Each new compressed projection is byte-equal to its entire frozen projection,
and the complete decoded projections also compare byte-for-byte equal.

| Corpus | Cases | Original Instructions | Projection Bytes |
| --- | ---: | ---: | ---: |
| Actor-to-frame-end iteration | 1102 | 3744434 | 20887011 |
| Post-render-to-frame-end | 1348 | 4983001 | 28447607 |

The only generated manifest difference is the source hash of the reporting
helper, from `b8ead7266fb75a33a8aecb2e67291f4185d28d0565817983066c452bf75048a9`
to `3151b22c1cac49cdd022b100e6e78283868d8c66096146452a83645d7e4ed883`.
The manifests and their exact authenticator pins are refreshed only after
these comparisons. Neither compressed fixture, the original executable nor
any production C++ operation changes.

## Regression Results

All six affected CTests pass locally, including both authenticators, both
rejection suites and both original C++ replays. The unchanged canonical replay
source is compiled afresh with GCC, C++23, `-O1`, `-Wall -Wextra -Werror
-pedantic`; the two original checks complete 14700 budgeted replays.

Native Windows Python runs both seven-test rejection suites successfully.
Each skips its hard-link case because the RAM-backed WSL UNC path does not
support native Windows hard links. That coverage is present in the Linux
suite; Windows hard-link coverage and native Windows C++ are not claimed.
New-head hosted CI is separate and is not represented as green by local runs.

The [compact receipt](frame-fixture-dependencies-20261103.json) retains whole
lengths, hashes, equality outcomes, validation scope and private report hashes.
Compiler scratch, producers, runtime outputs and temporary test copies remain
RAM-backed with dummy audio and disabled cores. No full guest RAM is exported.

## Unchanged Hold

This fixes the confirmed fixture dependency gap. It does not fix or explain
the separately [captured actor guard failure](actor-preallocation-20261103.md).
The actor-pass integration hold, `actual_app_integration=0`,
`full_frame_claim=0` and natural-campaign completion limits remain unchanged.
