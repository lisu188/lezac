# Controlled Actor-To-Frame-End Corpus

`oracle.bin.gz` is a compact projection of 1,102 independent executions of the
unchanged canonical `LEZAC.EXE`, starting at `1000:7EBB`. It contains the exact
52,384-byte MZ, controlled initial-memory differences, register boundaries,
ordered writes, and ordered VGA DAC outputs. It contains no full guest RAM dump.

The original runs the actor pass, transient queues, and frame tail continuously;
no state is injected between these phases. Every case is executed both with
observers and with endpoint-only observation, comparing all registers, all
1 MiB of memory, and DAC outputs. Ordered writes must independently reconstruct
the complete endpoint memory. The actual mapped Unicorn 2.1.4 library is pinned.

The 876 actor profiles are extended with 48 coupled actor/queue profiles,
90 tail routes, 16 countdown/callback profiles, and 72 view-boundary profiles.
There are 64 dense instruction traces. Of the 1,102 cases, 1,030 reach all three
phases; 70 stop in actors and two in queues. The outcomes are 952 next frames,
30 restarts, 53 completions, nine escapes, 16 view changes, 24 runtime errors,
and 18 divide errors. UI and error handlers are handoffs, not executed owners.

Frozen hashes and all 20 producer/helper sources plus the original executable
are authenticated by `tools/check_frame_iteration_fixture.py`. The C++ consumer
also pins the decoded size, FNV fingerprint, exact embedded MZ bytes, case count,
and observed outcome/phase coverage. FNV is an accidental-corruption check; the
Python contract supplies SHA-256 authentication.

Decoded: 20,887,011 bytes, SHA-256
`64eda1655482da61f8dfcbe6ea8eb5a75795dcbcd8f51a7ac5f5bf9728626ab7`.
Compressed: 1,941,447 bytes, SHA-256
`4136afc5fb8b65789242954a71b6bdeaef829819df300c0e39b0a85a3d17cb52`.

This is controlled original-executable evidence, not a natural campaign capture.
The rendering prefix, hardware inputs, IRQ scheduling, production App integration,
and full-frame equivalence are not established by this corpus. The separate
computed-IRQ tests are structural controls, not original IRQ-schedule evidence.
The unresolved actor-pass stability hold from PR #458 is not cleared.
