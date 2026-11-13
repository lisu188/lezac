# Original Main Menu Choices

This recovers the ready main menu's choice dispatch in the C++ UI controller.
It does not establish whole-game, other-page input, keyboard-layout/case
translation, calibrated wall-clock or authentic manual-input parity.

## Original Rule

The shipped executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Using the main segment's offsets, `23c2..23d3` drains pending CRT keys, and
`23d5` reads a fresh choice. The file offsets below include the MZ base `0770`.

| File Offset | Character | Effect |
| --- | --- | --- |
| `2b4d` | `1` | Start one player |
| `2b61` | `2` | Start two players |
| `2b75` | `i` | Information pages, then redraw main |
| `2b90` | `z` | Instruction pages, then redraw main |
| `2bac` | `r` | Records, then redraw main |
| `2bbe` | `l` | Toggle language, then redraw main |
| `2bd4` | Escape (`1b`) | Exit |

The default path at file `2be4..2bea` returns directly to the blocking read at
`2b45`. There is no Return (`0d`) or `s` choice. In particular, `s` does not
change a retained gameplay-background option at the main menu.

## Natural Original Observation

`evidence/main_menu_return_original_20261001.json` records a silent private
Xvfb/DOSBox session in an owned temporary game copy. The natural-clock observer
does not replace the clock, set a seed, gate delays or write gameplay state.
Input is scripted physical X11 input, not manual play.

The fully drawn Italian menu is reached naturally. After an additional 300 ms
to pass the final text delay, one Return is pressed. The ready frame and all
five post-key observations (approximately 0.05, 0.2, 0.5, 1 and 2.5 seconds)
have identical complete 320x200 RGB pixels. A fresh `1` in that same session
then opens the intro, providing a positive selection control. The natural
clock hook is restored and the owned child exits with code 0.

The complete menu RGB SHA-256 is
`a6e2f9867be3fac329c8862529e751aedffd76f84d846c1c70700eb42bb3a914`.
The retained original screenshot is
`evidence/main_menu_return_original_20261001.png`.
The compressed exact observer is
`evidence/main_menu_return_observer_20261001.py.gz`, with decompressed SHA-256
`0ce460582d38c1cbdd5332db4c8340c3425b1c23fc19700939a8fc1a44d08b16`.
Its repository-relative imports require placing the probe under a temporary
directory in this checkout when rerunning it; the archive is not a standalone
production launcher.

The original record SHA-256 is
`cfee0283b69ebf2f977c633d2b6a5f84021d8affcc4d8e0f14bafec46fbd3d65`.
All raw frames remain in `/dev/shm/lezac-original-main-return-control-20261001`.

## Recovery And Negative Evidence

The C++ ready-menu switch now admits only the seven recovered domain choices.
The filter runs after the existing fade/text branch, so a buffered key can
still be consumed as a presentation skip. The previously incorrect Return
one-player alias and main-menu `s` background toggle are no longer reachable.
Other menu pages, intro acknowledgements, name entry, end-run confirmation,
gameplay commands and typematic policies are not changed by this filter.

The pre-fix packaged executable SHA-256 is
`1d6405052e88b4c5a84c816c0ab8cc19ce01c5967cc094154f60f038aa4a4eca`.
The extended normal-window regression failed with
`ready menu changed after Return`, retaining an actual intro frame. Its failed
record, screenshot and exact executed harness are preserved as
`evidence/main_menu_return_cpp_negative_20261001.json`,
`evidence/main_menu_return_cpp_negative_20261001.png`, and
`evidence/main_menu_choice_negative_harness_20261001.py.gz`.
The harness's decompressed SHA-256 is
`2ff579c5fc7c480f2c72f775402d0d0694e5a7582c97abb7fba547466bbd39d1`.
That earlier failure record lacks executable/child-exit fields; provenance
comes from the launch command and independently hashed extracted package.
The final harness records these fields on both success and failure. The earlier
failure is not rewritten or promoted to a pass.

## Verification

The final local production executable SHA-256 is
`57da6e289bb8f02b3944b25910ac7ef3edc215b18a37569cb5fef6d7edad2a7a`.
The same Enter-then-`1` probe passes against it through the normal entry point.
All six menu observations match the original full-frame RGB hash; the fresh
selection still opens the intro and the child exits with code 0. The record
and 2.5-second screenshot are retained as
`evidence/main_menu_return_cpp_20261001.json` and
`evidence/main_menu_return_cpp_20261001.png`. Both original/C++ PNG files have
SHA-256 `f7de733556986356bd542967922035ad931f69c54b009627b5f8f76edf3e3114`.
This is equality of the observed menu frames, not equal startup/intro timing
or equality of naturally seeded intro backgrounds.

- `main_menu_models` checks 33 ignored domain keys in both languages, with
  both background settings and three ready states: static diagnostics, natural
  typing completion and consumed Return typing skip. No UI field or callback
  changes. All seven accepted commands are exercised independently, including
  both fresh player choices after ignored input.
- `main_menu_live_xvfb` preserves eight rendered checkpoints. It checks Return,
  keypad Enter, `s`, Space, F5, Page Up and Page Down at the ready menu in both
  languages, plus two held-Return observations. Fresh selection and later intro
  acknowledgement still reach gameplay. The queued-selection check alone is
  briefly input-batch gated; natural startup is not gated.
- All 28 selected CTests passed in 146.60 seconds against this executable,
  including the five sealed Level 1 routes and evidence/replay guards, exact
  original menu phases, UI/record/end-run behavior and source/silence guards.
  The subsequently expanded seven-command model test and original menu pixels
  passed again. Original fixture bytes, replay routes and acceptance gates are
  unchanged. Full Linux/Windows suites remain required before merge.
- All three buffered-input physical cases and all seven key-ownership physical
  cases passed with dummy audio. The normal-window result is retained at
  `/dev/shm/lezac-main-menu-choices-fixed-20261001/result.json` (SHA-256
  `1a08169d0d8034474a825d9f357ddf3ec33f9d5396179a6fb3f5ae56d83dd523`).
  The CTest log remains at `/dev/shm/lezac-main-menu-choices-focused-20261001.log`
  (SHA-256 `d1afd2e6f03b2812290ba29d0f951fdadc6e6fb6d1e322ea3cf8592d98916693`).

All launches are silent and generated runtime evidence stays in RAM. Windows
disk usage was below 90% before the bounded build. Broad local builds and
cleanup of unique evidence are not part of this change. Uppercase/layout/keypad
character translation and help/instructions/records typing and blocking-key
behavior still need their own original observations. The broader campaign,
actor/collapse, two-player and manual acceptance frontier remains open.
