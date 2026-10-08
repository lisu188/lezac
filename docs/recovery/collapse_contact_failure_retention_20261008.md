# Collapse-contact failure retention

Review finding:
https://github.com/lisu188/lezac/pull/318#discussion_r4215517686

The compiled-contact checker now copies real failed probe inputs, expected
output, and any actual output to a unique directory under
`build/collapse-contact-failures/` before its temporary directory is removed.
`failure.json` records the error, command, return code, stdout/stderr, validated
expected record sizes and a replay command targeting a new output file.
Timeout diagnostics retain partial stdout/stderr when available. Errors still
propagate. A retention error is reported separately and does not hide the
original failure.

The comparator reports the first absolute differing byte, zero-based expected
case and byte within that case, and actual/expected file sizes. It uses expected
record lengths, not potentially corrupted actual headers. Appended output is
reported as `case_index=after_last`. Both Linux and Windows CI upload retained
directories with `if: always()`. Intentional output-mutation controls run outside
the real-failure retention block and are not saved as failed probes.

`tools/check_collapse_contact_failure_retention.py` covers ten mocked probe modes:
success, nonzero exit, stderr, wrong stdout, absent output, first/second-case
mismatch, truncation, appended bytes, and timeout. Twelve direct comparison
cases include record and 65,536-byte read boundaries. It verifies that original
temporary inputs disappear while retained copies remain byte-exact, and that a
successful probe's four deliberate mutation controls create no failure folder.
The baseline failed because no retained directory existed for failed probes.

The initial Windows MSYS2 CI run exposed a test-only path spelling difference:
`Path.iterdir()` and the printed retention path used equivalent mixed slash
forms. All nine failure modes had already verified their retained binary files.
The reporting assertion now parses the single reported path and checks its
filesystem identity with `Path.samefile()`, retaining exact file-content checks.
The original failed job log and live Linux head are preserved; a fresh branch
requires new MSYS2 CI and exact-head review before delivery.

This follow-up changes diagnostics only. The original fixture, generator,
metadata and production C++ are unchanged from the integration branch. Mocked
tests do not establish compiled comparison, original execution, natural gameplay
or whole-game parity. Exact-head hosted validation is required before merge.
