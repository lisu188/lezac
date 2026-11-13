# Pull Request Review History Audit

The 2026-10-08 read-only audit covered all 314 repository pull requests. It
retained 63 review submissions, 62 inline review threads, and 220 conversation
comments, including resolved and outdated feedback. GitHub thread status is not
used as proof that the current implementation is correct.

The adjacent `pr_review_history_inventory_20261008.json` records every inline
thread and its initial disposition. This is a review backlog, not a declaration
that every historical finding remains a bug or that every finding is fixed.
The original API responses remain retained in the local audit evidence.

## First Repair Batch

Five findings were confirmed in main `e3b6e3ee2cf376f7c43692f34ea0e31b56738cc7`:

| Historical PR | Finding | Proposed Repair |
| --- | --- | --- |
| [#240](https://github.com/lisu188/lezac/pull/240#discussion_r4090832710) | Rendering consumers do not inherit SDL library search directories. | Export the existing SDL link directories through the rendering target. |
| [#266](https://github.com/lisu188/lezac/pull/266#discussion_r4172168879) | Duplicate evidence records overwrite earlier records. | Reject duplicate record names and cover identical/conflicting duplicates in either order. |
| [#267](https://github.com/lisu188/lezac/pull/267#discussion_r4172420050) | Target-probe triggers omit runtime imports. | Include all local capture dependencies. |
| [#269](https://github.com/lisu188/lezac/pull/269#discussion_r4173194808) | Walker-probe triggers omit runtime imports. | Include all local capture dependencies. |
| [#304](https://github.com/lisu188/lezac/pull/304#discussion_r4212612375) | The support-column guard has little timeout headroom. | Increase its 60-second limit to 120 seconds. |

The repair branch also records the standing code-review gate in `AGENTS.md`.
These repairs are not merged merely because this document exists. They still
require current-head review and successful validation.

## Already Present And Pending Verification

The byte-preservation rules requested on #300 and capture-dependency triggers
requested on #278 are present in current main. The #279 producer checks and
typed monster mutations also have source fixes. Their source presence is
recorded separately from fresh execution of their original-backed validations.

All other historical gameplay and tooling findings remain explicitly queued
for current-code verification. In particular, do not change recovered update
order, sound, pool allocation, or collapse geometry solely from an old review
comment; check the original-backed evidence and add an appropriate regression.
Do not resolve a GitHub thread until its disposition is verified.

## Fresh Open-PR Reviews

Fresh review requests were made for all nine open PR heads without changing
their branches or interrupting CI. The first refresh reported completed bot
reviews for those exact heads, with two new inline findings:

- [#308: Bound sound catch-up work after long stalls](https://github.com/lisu188/lezac/pull/308#discussion_r4215037113).
  Head `2321b34d9f0b1f7a633ac0496c4b2f9980a6ad48` remains blocked on the
  unbounded stale-audio synthesis loop. Preserve any live CI source; implement
  and validate a bounded catch-up change in a fresh source or after terminal CI.
- [#243: Bypass the diagnostic replay adapter for live ticks](https://github.com/lisu188/lezac/pull/243#discussion_r4215028209).
  Head `e8cc951f1cf2cb2fcde39ddff60a70201c215117` remains blocked on the live
  diagnostic adapter and its repeated state copies. Check the current ownership
  boundary and runtime evidence before integrating this older branch.

The seven other refreshed heads had no inline findings in that snapshot. This
is not approval, successful CI, or permission to skip another pre-merge check.

## Validation Boundaries

`tools/test_review_history_repairs.py` checks the five source contracts, walks
the local Python import graph for three capture workflows, and rejects trigger
removal mutations. The behavior-4 fixture checker now rejects 45 malformed-input
cases, including 16 whole-record duplicates. These checks do not demonstrate a
custom-prefix SDL link, a fresh native capture, or whole-game parity. Compiled
tests and capture workflow outcomes must be reported separately.
