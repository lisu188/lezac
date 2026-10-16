# Original startup timing calibration

This is a bounded C++23 translation of original `CS:247f..2585`, not natural
startup, frame timing, IRQ behavior, or whole-game parity. The application is
not wired to this helper yet. Existing presentation constants are unchanged.

## Recovered behavior

The routine performs one `CRT.Delay(500)`, reads DOS GetTime, performs
`CRT.Delay(1000)`, and reads DOS GetTime again. It calculates the elapsed word
with 16-bit wrapping:

```text
(minute2-minute1)*6000 + (second2-second1)*100 + hundredth2-hundredth1
```

Hours are not included. Only raw words 1 through 299 are accepted. An invalid
word repeats the two clock reads and `Delay(1000)`, without another settling
`Delay(500)`. In particular, an hour rollover is not normalized. A legal
10-minute 55.37-second scripted jump wraps 65537 to 1 and is accepted; a
10-minute 55.36-second jump wraps to zero and retries.

The original software Real48 division and Round produce these words:

| Original word | Accepted elapsed E | Purpose |
| --- | --- | --- |
| DS:78ce | Round(8000/E) | Character delay |
| DS:78d0 | Round(1600/E) | Auxiliary delay, broader consumers still under investigation |
| DS:78ca | max(2, Round(200/E)) | Minimum word, broader consumers still under investigation |

Positive half ties round upward. The integer expression `(2*N+E)/(2*E)` matches
the original for all 299 accepted inputs and these three numerators. This is
not a general replacement for Real48. E=98 yields 82/16/2; E=99 yields 81/16/2;
E=128 yields 63/13/2. The observed 81 and 82 values are calibration outputs,
not universal presentation constants.

## Independent Original Oracle

`tools/capture_original_startup_timing.py` executes the checksummed shipped
`LEZAC.EXE` using optional Unicorn 2.1.4. The MZ image has 468 relocations and
is loaded at CS=1000, DS=1aa2, SS=8000. Non-image memory starts at zero.

The arithmetic entry at 24f8 is executed for all 65,536 input words. Its output
is packed into an 8,192-byte acceptance bitset and a 1,794-byte table of the
three words for accepted inputs in ascending order. A full 524,288-byte record
stream is hashed in the manifest but is not committed.

Ten complete calls execute from 247f through the original return, including
the original CRT.Delay loops, stack checks, Real48 division and rounding.
There are no original function-call stubs or instruction patches. Code bytes
and return stacks are checked. DOS INT 21/AH=2c returns declared scripted
clock samples; the CRT calibration word is seeded to 544 and COM1's base byte
at 0040:0000 to 248. Port I/O and unexpected interrupts are rejected. No
hardware IRQ delivery or natural wall-clock behavior is claimed.

The 55 recorded delay/GetTime service events cover 98/99, zero, negative and
upper-bound retries, hour rollover, positive half ties, maximum accepted input,
and accepted/zero 16-bit wraparound. Native tests compare the C++ callback
sequence directly with these original events and require all inputs consumed.

The fixture contract pins the executable, producer, manifest, acceptance bits
and word table hashes. CI does not require Unicorn. To reproduce the original
oracle, supply optional Unicorn 2.1.4 and a new output directory on a volume
that satisfies the repository disk guard:

```sh
env SDL_AUDIODRIVER=dummy PYTHONDONTWRITEBYTECODE=1 TMPDIR=/dev/shm \
  python3 -B tools/capture_original_startup_timing.py --out /dev/shm/lezac-startup-new
```

## Remaining Integration

The callback-based helper preserves the original algorithm without pretending
host sleeps provide a recovered DOS/CRT/IRQ clock. Natural startup must still
reproduce DOS timer quantization, CRT work and interrupt phase, then connect
the recovered outputs to their proven consumers. Synchronized full frame
streams, campaign completion, boss behavior and owner visual acceptance remain
separate obligations.
