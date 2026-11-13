# Actor Contact And Boss-Head Execution

## Recovered Span

`ActorContactOperation` recovers original `1000:654E..65A2` and the complete
behavior-6 boss-head scanner `5CB0..6052`. Its real nested callees are recovered
as well: reverse bomb attribution `3A56..3A7D`, fatal group conversion
`5BCC..5CAF`, tile-trigger rewrite `5740..5871`, and the sound-priority latch
`165A..167D`. There are 547 new game/helper instruction addresses, all reached
by the unchanged original in this corpus.

The existing verified descriptor helper, RNG and Pascal runtime operations are
reused one instruction at a time. There are no host-distance calculations,
semantic damage shortcuts, helper stubs or stage-boundary memory replacements.

`FrameActorContactOperation` composes the previous continuous prefix, links,
caller selection, actor prologue and precontact operation with this block on
one bus and live stack. It preserves instruction grants, string-copy grants,
snapshots and timer accounting, including delivery accounting before the first
IRQ instruction executes. Direct `654E` construction is available, but every
new original case starts at the real `6053` prologue instead.

Non-boss execution caches the original four-by-four map neighborhood and stops
before `65A2`. Boss execution returns from the complete scanner and stops before
motion integration at `73E5`. Neither handoff is a completed actor or frame.
The full-prefix `7903` interface is retained and checked for construction and
zero-budget behavior, not claimed as an independently captured full-frame entry.

## Preserved Raw Rules

- Four edge scans retain their packed byte dimensions, original far-map offset,
  16-bit wrapping, and inclusive `1..76`/bottom `1..82` ranges.
- The periodic gate retains division by 29, `Random(100) > 70`, even-tick sound
  selection, target-sign motion and the conditional bottom-collision jump.
- Interior scans visit every second column. Their byte count wraps, and the
  original signed `JLE` excludes counts 128 through 255 before attribution.
- Reverse attribution searches from the last bomb record and preserves the
  prior result if unmatched. A zero count retains the original underflow and
  multiplication high word; it is not normalized to an empty host container.
- Mass doubling wraps the count byte. Its later sign extension can suppress
  life loss while the same raw byte still subtracts from the HP byte.
- Fatal conversion compares a full head-owner word with each segment's byte
  owner, walks physical records in order, consumes the original RNG and then
  converts the head. Owner 256 is not silently truncated to owner zero.
- Trigger key 1000 is not a score award. The last matching trigger wins;
  masked word-plane ranges are inclusive, and successive mappings re-read the
  already changed tile, preserving chains such as `1 -> 2 -> 3 -> 4 -> 5`.
- Sound requests retain the signed byte comparison after decrementing the
  current priority. No speaker output is produced by the recovered latch.

## Independent Original Evidence

Captures `t243-a` and `t243-b` are independently generated and byte-identical,
including their manifests. The structurally relocated original executable is
unchanged. Pinned Unicorn 2.1.4 executes it without instruction patches, call
stubs, delivered interrupts or hardware I/O. The actual mapped emulator library,
three canonical assets and all eight producer sources are checked before and
after generation. Original startup instructions freshly generate the sine table.

| Evidence | Result |
| --- | --- |
| Total controlled cases | 5,570 |
| Continuous post-render prefix entries at 7A57 | 238 |
| Actor-caller entries at 7EBB | 796 |
| Retained actor/prologue profiles at 6053 | 2,124 |
| New targeted boss/contact profiles at 6053 | 2,412 |
| Register states including endpoints | 19,258,470 |
| Ordered writes | 3,245,802 |
| New instruction addresses reached | All 547 |
| Original code bytes verified unchanged | 43,552 |
| Expanded projection bytes | 817,059,120 |
| Compressed projection bytes | 42,703,912 |

The targeted profiles cover every width, height and existing sound-priority byte,
damage/count/mass boundaries, periodic RNG/parity/target signs, all edge masks,
extreme signed velocities, trigger banks/ranges/mapping chains, physical group
owners/counts, reverse/unmatched/zero-count attribution, far/visual/map aliases,
maximum packed boxes and real prologue stack failures. They include deliberately
malformed raw states and do not establish natural reachability.

Final outcomes are 2,943 tile-behavior handoffs, 2,408 motion-integration handoffs,
107 transient queues, 75 restarts, two end-run UI handoffs and 35 original runtime
errors. Observed and unobserved execution agree over all endpoint registers and
flags and complete 1 MiB memory. Ordered writes independently reconstruct that
complete final memory.

SHA-256 fingerprints:

- Manifest: `45ff32aeed92d4a5bf0595574d2075778344cf77808d8ea6783f4176c16e36be`
- Compressed projection: `7645df2d66599e3b9415d67727e9223420492c693cd89977d204607a95880aa6`
- Expanded projection: `05a43dfea6bec700e89814eb5f8a85bdf058224a7a94f59b2d711ed935b3c3ca`

## C++ Comparison

All nine instruction/string grant combinations pass: 1/17/4096 instructions and
1/2/65535 transfer bytes, with snapshot reconstruction after each grant. There
are 50,130 replays, 61,090,647 register/control comparisons and 172,852,956
dispatches. Every ordered write, full final memory and endpoint flag agrees.
Intermediate arithmetic flags remain excluded from comparison, while the
grant-1 lane checks each modeled boundary and control flag.

Strict GCC C++23 and native MSVC C++ latest `/W4 /WX /O2` pass the full corpus.
Complete ASan/UBSan replay passes too. Constructor tests cover 12 valid profiles,
60 invalid-mask controls, five entry/owner rejections and ten malformed-IRQ
rejections. Supported masks remain zero and `0x200000` on all six interfaces.

All 11 focused contact/adjacent-operation/source/frozen-checkout CTests pass.
Thirteen compiled faults are rejected: tile anchor, bottom range, periodic
modulo, signed flame gate, sample step, mass doubling, reverse attribution,
full owner word, last trigger match, inclusive upper range, mapping continuation,
signed sound priority and IRQ flags. Each fault uses the grant-1/string-65535
lane over the same corpus and computed IRQ checks; the separate positive test
retains all nine grant combinations. Production and replay source bytes are
preserved during mutation testing.

## Computed IRQ Scope

Twenty-seven computed IRQ checks cover prefix, caller, prologue, precontact,
tile cache, all four boss edges, damage, attribution, fatal conversion, trigger
rewrite, sound latch and both signed reflection divisions. Four enter with an
active sound latch. The original BIOS/game timer machinery executes 1,004
instructions in total and accounts for one delivery per case, immediately on
admission. Port callbacks are simulated, never sent to hardware.

Each check requires exact immediate CPU restoration and unchanged physical
actors, far actors and VGA during the handler. Nested and finished IRQ delivery
is rejected. From the actual post-IRQ state, grant-1 and grant-17/snapshot
continuations agree over complete snapshots, ordered writes and all 1 MiB memory.
The BDA timer advances from 100 to 101; sound state changes remain real.

The first terminal audit incorrectly required at least one final-register
difference relative to no-IRQ execution. All 50,130 ordinary replays had matched,
all 27 targets had run, and four used active sound, but that count was zero.
Unlike the earlier `654E` stop, the new tile-cache handoff overwrites those
registers. The earlier future-stack effect still remains in a selected-player
target local at `BP-4`/`BP-6`. The corrected audit compares those words directly
with unchanged-original final memory and requires the retained sensitive case:
`irq_register_sensitive=0`, `irq_target_locals_sensitive=1`. No stack padding or
future local is cleared, normalized or restored to force a neutral result.

These are computed context/resumability checks, not a new original-CPU IRQ
injection corpus, natural interrupt schedule or full-frame timing proof. Both
independent original captures above deliver zero interrupts.

## Remaining Boundary

The production App does not yet consume this composed CPU operation. Full actor
return, motion integration, later behavior dispatch, subsequent actors, complete
active-frame IRQ scheduling and whole-game equivalence remain incomplete.

A separate fresh Linux actual-App build and silent physical-boss diagnostic pass
eight controlled ticks, 48 physical-link checks, two changing rendered frames
and seven damage-driven conversions. It uses production helpers with the legacy
visual adapter disabled, but injects its later damage stimulus. It is neither
new contact-operation integration, original pixel comparison nor a natural boss
fight/victory. The pre-existing unrelated debris `snprintf` warning remains.

Only the compressed controlled projection and metadata are candidates for
publication; no full RAM dump, expanded projection or screenshot is published.
All generated local artifacts stay in RAM while C: exceeds the disk reserve.
Completed exact-head review and full hosted platform CI remain merge gates.
