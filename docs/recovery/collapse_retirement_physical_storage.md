# Normal Collapse Retirement Storage

The original `1000:5602..5651` writes normal motion, fractions, bounds and
magnitude back to the current record before `1000:5655` tests the byte timer
for equality with 95. The earlier flag writes and `1000:552C` timer increment
also remain in the physical record. `1000:508B` removes the live entry without
clearing the stale tail. The C++ normal path must commit its local record
before erasing it. The fracture path branches before normal motion writeback
and is intentionally unchanged by this recovery.

## Original Evidence

`capture_original_collapse_retirement.py` executes unmodified seeder `370E`
and updater `5102` with explicit object/word segment bindings, including
`DS:C1FE=4000` and `DS:206E=5000`. The executor is compiled directly from its
attributed source buffer. No original instructions, calls or hardware I/O
are replaced. Independent executions compare full 1 MiB memory and fourteen
registers for every case.

The 176 cases cover timer bytes 0, 93, 94, 95, 254 and 255; horizontal
velocities 0, 1, 29 and 30; flags 0/83; two vertical fractions; and all
nonempty retirement masks across two and three live records. There are 144
timer removals and 312 normal writebacks. No fracture or actor construction
is reached. Five complete physical record slots are retained per case,
including two salted slots beyond the maximum live count. Comparison covers
both full terrain planes, counts, RNG, destruction/fragment counters and
all 75 physical record bytes, without masks.

The raw fixture is 2,122,576 bytes, SHA-256
`34396a2cf00e8b40f1ee1e29924dc5c40c636df7e3017f0365dc33fd474ceed3`.
Its deterministic gzip is 7,750 bytes, SHA-256
`b8b9afdc566ceabcb608751474cf7038d3c7c9f8bc3400e6ce64d01e1ba8d5da`.
The expected output includes a sixteen-byte protocol header and 1,060,752
state bytes, SHA-256
`76be0e1ca3b563c17a6af6576ee23287c5b1fc05ce075bd846ab1877d029195e`.

## Reproduction

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 python3 \
  tools/capture_original_collapse_retirement.py --root . \
  --out-directory /tmp/lezac-original-retirement \
  --unicorn-path /path/to/unicorn-2.1.4
env SDL_AUDIODRIVER=dummy SDL_VIDEODRIVER=dummy python3 -S -B \
  tools/check_collapse_retirement.py --exe build/lezac_cpp \
  --out /tmp/lezac-app-retirement
```

The diagnostic seeds only input state, calls production
`updateCollapseRecords()`, and writes actual output before the independent
checker compares it. Expected fixture bytes are skipped, not installed as
application state. Checker contracts and original CPU execution are separate
from actual-App acceptance, which requires retained raw output from the
compiled executable. Full exact-head CI, dependency integration and completed
external review remain separate delivery requirements.

## Limits

This is a seeded normal-retirement storage check, not complete physical-bank,
fracture-retirement, sound-interrupt, natural-route, rendered-pixel or
whole-game equivalence. Earlier probes that omitted segment bindings, and
the corrected probe's initial `vx == 30` expectation failure, are retained
as failed evidence. They do not establish a production gameplay mismatch.
