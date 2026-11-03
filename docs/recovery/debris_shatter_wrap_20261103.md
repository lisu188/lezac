# Debris Shatter WORD-Sum Rollover

## Original Rule

Fresh REA 6.7.0 / Ghidra 12.1.4 observations on WSL verify all eight original
instructions at `1000:4AFA..4B0B` against their exact MZ file bytes:

```text
4AFA  MOV AX,[78C2]
4AFD  ADD AX,[BP-2]
4B00  XOR DX,DX
4B02  MOV CX,6
4B05  DIV CX
4B07  XCHG AX,DX
4B08  CMP AX,2
4B0B  JBE 4B35
```

The bytes are `a1c2780346fe31d2b90600f7f1923d02007628`. The addition wraps
to a WORD before division. The old production expression used the wide
`logicTick_ + slot` sum directly. At frame `65535`, slot `200`, the original
divides `199` and gets remainder one, while the old port gets remainder five
from `65735`. That wrongly starts the shatter animation. Other inputs miss a
shatter that the original starts. The fix casts the sum to `uint16_t` before
modulo; no update order, counter phase, sound policy or other behavior changes.

## Executed Original Regression

The optional `tools/capture_original_debris_wrap.py` runs the complete original
`1000:45FA` updater in Unicorn 2.1.4. It first reproduces all eighteen frozen
native cross-check outputs from the existing debris corpus. It then executes
276 controlled cases: 23 frame values around ordinary residues and rollover,
and twelve physical slots from 200 through 1600. Padding records explicitly
establish each slot. This is controlled initialization, not a natural route.

The complete 43,552-byte relocated code region stays byte-equal after every
case. Actual CS/IP/SP return is required, instructions and calls are unchanged,
and unexpected interrupts or I/O fail. Compared outputs contain the full
controlled map planes, all live debris/collapse records, counts and RNG.
No full guest RAM is exported. The existing 1,061-case corpus is unchanged.

The frozen 11,057-byte fixture and its producer inputs are SHA-256 bound by
`tests/gameplay/debris_wrap_original.json`. CTest drives the actual production
`App::updateDebrisRecords` through its existing diagnostic consumer. The old
compiled App disagrees in 108 cases, with glyph `70` versus `76`; the fixed App
matches all 960,526 output bytes. The remaining 168 cases protect ordinary and
non-differing boundary behavior. An output-byte mutation is also rejected.

## Validation And Limits

The full GCC 13 C++23 App builds with `-O1 -Wall -Wextra -Werror -pedantic`.
Twenty-five focused CTests pass, including both new checks, the retained 1,061
debris and 2,395 collapse cases, contact/rest/shatter tests, source guardrails
and the Level 4 support-column guard. Five fixture/safety methods pass on Linux
and native Windows Python. Seven ordinary Level 1 PPM frames are byte-identical
between the unfixed and fixed C++ builds; these are not original pixel parity.

Native MSVC compiles the changed App translation unit with the project's
normal `/W3` warning policy. A separate stricter `/W4 /WX` probe fails on both
unchanged main and the fixed source with the same 53 normalized warning
instances. It is not reported as a strict native pass. No fresh linked native
Windows App replay or new natural original rollover run is claimed.

The existing `debris_shatter_dice_phase` counter-alignment item remains open.
So do the separate intermittent actor-pass issue, actual recovered-frame App
integration, campaign completion and whole-game/frame fidelity. No broad
completion, visual or original-fidelity claim changes.
