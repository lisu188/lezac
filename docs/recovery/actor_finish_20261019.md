# Common actor tail and real near return

This work extends the reviewed actor-contact operation on the same live bus and
stack. It models the original common `1000:73E5..7783` tail, including fractional
motion, ordinary four-cell damage, physical visual/record writeback, expiry,
pickups, debris allocation, and `LEAVE; RET 4`. The instruction after the return
is deliberately not executed.

The new operation also retains the actual helper instructions at `56B6..5715`,
`0495..056B`, and `3FA6..432A`. These implement the four-cell query, last-match
owner-packet registration with four three-byte RTL copies, and Real48 flame
expansion. Existing recovered descriptor, allocation, random, software Real48,
sound-latch, and RTL Move instructions are reused one instruction at a time.
There are 802 game-instruction cases and 315 dedicated RTL cases in the new
headers. `actor_real48.hpp` adds the software addition, comparison, slow multiply,
and sine/cosine polynomial paths needed by these fixed burst arguments. It is
not a general floating-point API, and leaves the established RTL headers intact.

## Boundaries

- Inputs begin at the existing prefix/caller/actor entries, not at an injected
  tail state. Direct `6053` inputs receive their real near-return address in the
  initial stack before original execution starts.
- All 5,570 preceding inputs are retained. Another 566 controlled inputs cover
  the kind byte, fractional motion, expiry parity/underflow, burst capacity,
  overlapping packet keys, debris/graphics limits, pickup selection, and ordinary
  damage. Malformed controlled inputs are not claims of natural reachability.
- Non-boss tile behavior still stops before `65A2`. The composition does not
  execute the next NPC/player iteration or a complete gameplay frame.
- The `7903` full-prefix constructor is checked for ownership and inert zero
  budget only; it is not an active-prefix original replay claim.
- Computed timer deliveries use the recovered handler and live stack, including
  partial packet copies while RTL Move borrows DS from SS. Original corpus
  execution itself delivers no IRQ and performs no hardware I/O.
- Production App/gameplay/render/resource/sound bytes are unchanged. The new
  operation is not yet a production gameplay path, natural route, screenshot
  alignment, whole-frame proof, or whole-game parity claim.

## Verification Status

The canonical executable SHA-256 remains
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The producer authenticates nine source files, three assets, Unicorn 2.1.4's
actually mapped library, and the original sine initializer before and after the
run. Observed and unobserved original execution agree on complete registers and
all 1 MiB of memory. Ordered writes independently reconstruct that final memory.

Two fresh corrected captures have byte-identical gzip projections and manifests.
Each has 6,136 cases, 20,226,439 register states and 3,401,255
ordered writes. Its expanded projection is 888,862,269 bytes with SHA-256
`5efb30add42b9914a929c642c0a7dd728b9ed888a1459c9be20a851ffac6bb3a`.
The frozen manifest SHA-256 is
`9f7cb94e4a7dd4dd8ea2275f5c10128fcdb9e9e62daab3288700ad3b004a0745`.
The initial diagnostic capture and its exact producer are retained separately;
that capture exposed the ordinary-damage geometry gap and is not the final
fixture or independent repeat.

Strict GCC, native MSVC and ASan/UBSan replays pass all 55,224 replays across
three instruction grants and three string grants: 64,171,750 register/control
comparisons and 181,558,719 logical dispatches. All ordered writes, complete
memory and endpoint flags agree. Forty-three computed IRQ checkpoints account
for 1,580 handler instructions, four active-sound deliveries, immediate CPU
restoration and two retained caller-local stack effects. Snapshot restoration
and resumed grant-1/grant-17 continuations agree.
The late packet-copy IRQ is delivered after an actual byte write, with DS=SS and
CX=2; a compiled forced-game-DS restoration fault is detected at this checkpoint.

Dynamic game coverage is 799/802 addresses. `7436` is ruled out by the preceding
kind-1..8 guard; `7698` is bypassed by the unconditional jump at `7695`.
The `759B` behavior-5 exit requires the still-unrecovered tile-behavior path;
it is retained but not dynamically proved here. RTL coverage is 276/315 cases;
the other cases are not reached by the fixed burst arguments in this corpus.
Neither figure is promoted to universal instruction or whole-game coverage.

All 20 compiled fault controls pass with both source headers and the test source
preserved. The final focused CTest batch passes 12/12. Both Python fixture tests
pass on Linux and native Windows; Windows takes 1141.569 seconds over the RAM UNC
share without relaxing an assertion. Native Windows cold checkout passes for
19 families, 63 files and all 19 CRLF negative controls. Source ownership checks,
the complete App build, and the silent App boss diagnostic also pass.
The App build retains the pre-existing debris `snprintf` warning. A copied
fixture input-catalog typo was detected, corrected, and covered by a manifest
catalog-equality regression.

Completed current-head review and full hosted Linux/Windows CI remain merge
gates. Local validation does not imply those hosted gates or App integration.
