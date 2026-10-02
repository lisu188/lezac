# Static-Range Walker Facing Reset

## Original Evidence

The natural Level 1/2 route reaches Level 3 before 900 further gameplay
frames. Twenty additional normalized control-bank events exercise movement,
jumps, weapon selection and two bomb placements; no new gameplay state or
teleport is injected. This is instrumented original execution, not authentic
physical keyboard input or a whole-game acceptance run.

The original executable SHA256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The complete native Level 3 gzip stream SHA256 is
`e1dad814c0e7f234a2b2802820ee9b8383d60af1b4a78e70ac52e11847481d10`.
The full 4,676-tick route SHA256 is
`4ce19929ad2763d15c0de766dfa773d7f7d43868d97a620bdf844a589a2f244d`.

At sample 345, native frame 3015 / C++ route tick 4122, the first kind-4,
behavior-3 monster has these original 38-byte actor and 8-byte visual records:

```text
pre_actor=0402000d0d00f8fe0000a0000000080100000000000336363802020101000000000000000401
pre_visual=830288001010fc32
post_actor=0402000d0d0008010000a8000000080100000000000336363800020101000000000000000401
post_visual=840288001010fc33
```

Its position changes from `(643,136)` to `(644,136)`, velocity from `-264`
to `264`, and fractional X from `160` to `168`. The animation counter advances
from 2 to 0 and the visible descriptor advances, but the cursor returns to
the range base: raw actor byte `+0x16 = 54`, or zero-based cursor 53. The
left and right profile selectors are both 13; sharing a range does not make
the facing-reselection operation a no-op.

The original code at `1000:727D..732C` (file offsets `0x79ED..0x7A9C`, code
image base `0x770`) checks the terrain-reselection flag and the sign of VX.
Both nonzero-VX branches load their selected range and write its first value
back to the cursor. There is no distinct-left/right-range condition. Zero VX
selects neither branch. Neither branch rewrites the visible descriptor or
the animation counter.

## Failure And Regression

The unchanged port's full replay completed, but its comparator failed first
at this boundary: cursor 54 instead of 53. Across all 900 images, all
57,600,000 RGB pixels matched and the three spawners matched; 827 live-monster
boundaries had a projected-state difference. Pixel equality did not establish
actor-state equality. The failed comparison and full replay remain retained
and must not be relabelled as passing after a later fix.

`monster_static_facing` seeds the observed kind-4 boundary on the shipped
Level 3 map and executes the production monster update. Nine additional
helper cases cover static-range kinds 2, 3 and 4 with negative, positive and
zero VX, preserving the visible frame and counter. These are focused seeded
regressions, not natural campaign completion. Full corrected-route comparison
and delivery validation remain separate gates.

## Corrected Full Route

The corrected executable SHA256 is
`aa9191aa0b84704f04fa4cfa7c32fb3844f166a4399c2ca5ffdc183ac7c8365b`.
Its complete trace SHA256 is
`8240de4159741dc74984f48314fe9d361eb336728d155a115ea832fa57061324`.
The comparison producer SHA256 is
`63d4487e3980c8ae24ecd89e293a7813cf7f7882da5a61f9b1896a774223a3df`.

The new full 4,676-tick replay completed with 4,677 images, 17,598 checkpoints
and all 136 route events. The unchanged Level 1/2 and early Level 3 prefix
matched 15,199 structured records, 4,077 complete PPM file hashes and 77
result-stream/image files against the retained earlier replay. Only the
expected route-header length and route fingerprint differed for the extension.

All 900 original Level 3 images matched all 57,600,000 RGB pixels. All 1,800
mapped present/post-update boundaries matched the existing gameplay
projection, including 1,289 boundaries containing live monsters. There were
zero projected monster or spawner differences. All nine existing projection
mutation guards remained active; no cursor field or failing boundary was
excluded. The earlier 827-difference replay remains a separate failed result.

The new regression failed on the unfixed fresh build with the expected native
boundary error (CTest exit 8); its executable, source snapshot and log were
retained before rebuilding. After removing only the static-range shortcut,
all eight focused monster tests passed. The four existing motion/turn/ledge
tests also passed. These 12 local checks do not substitute for full platform
CI, extracted-package validation or whole-game release acceptance.

## Remaining Scope

The native capture also retains differing DOS clock bytes. Gameplay comparison
does not claim wall-clock parity, every actor byte, every stored DAC entry,
visible monster descriptor parity, two-player coverage, later campaign levels,
the natural Level 7 boss fight or release acceptance.
