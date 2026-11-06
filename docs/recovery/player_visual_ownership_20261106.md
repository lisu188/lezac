# Player Visual Ownership

Production rendering now reads both player rows directly from `ActorSlots`,
alongside the nonplayer rows. Gameplay owns their coordinate and descriptor
writes. Rendering neither reconstructs these rows from typed players nor
backfills the physical storage. Explicitly seeded standalone/legacy rendering
diagnostics retain their separate typed projection.

## Original Owners

REA 6.7.0 with Ghidra 12.1.4 on WSL checked complete code windows against the
immutable 52,384-byte original MZ, SHA-256
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The independent MZ relocation-table check verifies loaded bytes and undoes
relocations before comparing every original file byte. These are static
instruction observations, not whole-program execution equivalence.

| Window (End Exclusive) | Bytes | File SHA-256 |
| --- | ---: | --- |
| `1000:2BA4..2EF2` | 846 | `58f2fe7f489b8585096f96116ed63b02206a2535333cbdacc8a80bfa0b2d0f12` |
| `1000:2F30..2F3A` | 10 | `601a36455911b77aec29fc6befd628bcc1983def7699adf577827620d6a9edfd` |
| `1000:7CE9..7CFF` | 22 | `bbaa7522c98a0c26fde31ea9cf68d9817a7376a44ef5430c9330e4c98997a12a` |
| `1000:5A75..5AFD` | 136 | `33c9d81763d3c7523957867c4d5df3218d533af5e615caf4a7663cdbcb88e4d5` |
| `1000:6053..615A` | 263 | `431e5ac77197ad7515fde8e91a09b892742940854b739abb4a12e6bcc325175d` |

Level setup selects the portal locator only for global state 1. Other states
receive X=10000 and Y=6000 at `2E1E/2E24` or `2E3D/2E43`. Later elimination
at `7CF9` changes only X; it must not replace the retained Y or descriptor.
The initial broader disassembly stopped at undecodable inline data at `2EF2`;
that partial result is preserved, not forced into a code interpretation.

Animation writes only the sprite-offset WORD at `6156`. Full posture/idle
selection uses `5A75`, which replaces offset, width and height. Waiting entry
likewise replaces only the offset at `7D9A`; a false reentry gate additionally
reduces width and height to one at `7DA8/7DB0`. The owned API keeps these
distinct writes separate. Motion, portal placement, dying motion and waiting
Y adjustment write at their gameplay owners, not on draw or capture.

An independent execution of unchanged original `2E0B..2E49` and the real
`056B` portal/CRT callees covers 54 seeded fragment cases: both players' global
states 0/1/2, three portal layouts and two inherited byte patterns. All 65,536
data-segment bytes match the expected touched-field boundaries. Observed and
unobserved full 1 MiB memory and registers agree, and the recorded writes
reconstruct the complete output. No interrupts or hardware calls were injected.
This is fragment evidence, not a natural complete level initialization.
Full memory pairs are retained in a private compressed backup, not published.

## Regression And Runtime Evidence

`--debug-player-visual-ownership` runs actual App owners with the legacy seed
adapter disabled. It checks both players, active/inactive setup, animation
dimension retention, motion, full landing pose, waiting placement/dimensions
and X-only elimination: 20 observations. It fails on the earlier App at the
missing owned setup position and passes after the change. Both executable
versions and logs are retained privately. Its stimuli are explicitly seeded.

The slot contract adds whole-row/unrelated-storage preservation checks for
all six player-visual APIs, signed-word edge bit patterns and 12 invalid-index
rejections. The raster contract supplies explicit physical player rows, then
conflicts the typed position, sprite and single-pixel flag with an independently
positioned 5-by-3 latched descriptor. Pixels must come from the physical owner,
and rendering must leave that owner unchanged. Two new mutation controls
exercise player-row bypass and draw-time descriptor reconstruction.

Full native GCC C++23 and MSVC builds pass, along with 37 focused Linux CTests
and an additional 26-test player/render selection, including fixture setup
dependencies and overlapping owner checks. These counts are not 63 distinct
tests. Native MSVC ownership units also pass with `/W4 /WX /permissive-`.

The private, adapter-free ordinary-startup replay executes all 18,700 ticks
without later gameplay-state injections and retains level-4 combat ticks
18500..18700. On both native platforms, all 201 full RGB frames and 402 paired
gameplay boundaries match the independently retained original. All 778 active
nonplayer records still match. The entire 33-row visual pool now matches:
106,128 bytes per platform, including both player rows, inactive tails and
guard row 32. All 264 one-byte payload mutation controls are rejected per
platform. The earlier frame images already matched; this fixes physical
ownership and previously differing storage, not an invented new pixel result.

## Remaining Limits

The raw reserved player-2 health byte, link row 0 and shared result WORD still
differ and remain unmasked. Player 1's separate actor record is not part of
`ActorStorage::State`. Whole storage/frame equivalence, full campaign and
level-7 boss completion, frame-pass stability, physical-input timing and owner
acceptance remain open. No broad fidelity flag is changed by this work.
