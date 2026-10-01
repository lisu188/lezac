# Original Main Menu Character Translation

This extends the [ready-menu choice recovery](main_menu_choices_2026-10-01.md)
from domain commands to the observed host-key character translation. It does
not establish whole-game, keyboard-layout, other-page navigation, complete
buffer eligibility, wall-clock timing or manual-input parity.

## Original Observations

Sixteen successful observations use silent private Xvfb/DOSBox runs in owned
temporary copies of the shipped game. Startup uses its natural clock; the
observer restores its one clock hook and does not seed gameplay, gate delays
or write game state. Each run waits for the exact complete Italian menu, then
waits another 300 ms for the final text delay. Input is scripted physical X11
input, not manual play. All successful original children exit with code 0.

The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
The full-menu 320x200 RGB SHA-256 remains
`a6e2f9867be3fac329c8862529e751aedffd76f84d846c1c70700eb42bb3a914`.

| Physical Input | Observed DS:2058 Byte | Result |
| --- | --- | --- |
| Shift+L | 76 (`L`) | Menu unchanged at all five post-key observations |
| Caps Lock+L | Not sampled in this frame-only probe | Same unchanged full-menu pixels |
| Caps Lock+Shift+L | 108 (`l`) | Completed English menu, then fresh one-player control |
| Shift+1 | 33 (`!`) | Menu unchanged, then fresh one-player control |
| Ctrl+L | 12 | Menu unchanged, then fresh one-player control |
| Alt+F5 | 108 (`l`) | Completed English menu, then fresh one-player control |
| Alt+F2 | 105 (`i`) | Information-page entry; subsequent navigation not observed |
| Alt+3 | 122 (`z`) | Instructions-page entry; subsequent navigation not observed |
| Keypad 1, Num off, Shift released | 79 (extended scan byte) | Menu unchanged, then fresh one-player control |
| Keypad 2, Num off, Shift released | 80 (extended scan byte) | Menu unchanged, then fresh one-player control |
| Keypad 1, Num on, Shift released | 49 (`1`) | Intro; DS:79b8 is 1 |
| Keypad 2, Num on, Shift released | 50 (`2`) | Intro; DS:79b8 is 2 |
| Keypad 1, Num off, Shift held | 49 (`1`) | Intro; DS:79b8 is 1 |
| Keypad 2, Num off, Shift held | 50 (`2`) | Intro; DS:79b8 is 2 |
| Keypad 1, Num on, Shift held | 49 (`1`) | Intro; DS:79b8 is 1 |
| Keypad 2, Num on, Shift held | 50 (`2`) | Intro; DS:79b8 is 2 |

The Shift-held keypad observations use direct `XTestFakeKeyEvent`, not
xdotool's keysym translation, which can temporarily release modifiers.
The BIOS flags at `0040:0017` are still `02` after the keypad press with Num
off and `22` with Num on. These physical captures support `Num OR Shift`,
not the initially assumed XOR, for keypad 1/2 in this original-game path.
The cause of that host/emulator translation is not resolved here; this is not
a claim about every BIOS or keyboard layout.

## Static And C++ Mapping

The CRT reader at file `8f1f..8f40` returns ASCII directly. When INT 16h yields
zero ASCII, it retains the scan byte at DS:7f6d for the next read; there is no
lowercase conversion. The ready-menu comparisons are lowercase-only, as
documented in the earlier choice recovery. The Alt aliases expose scan bytes
`69`, `6c` and `7a`, which collide with accepted lowercase characters.

`InputMapper::mainMenuKey` now handles letter case, shifted top-row choices,
Control/Alt translation, those three aliases, and keypad 1/2's observed lock
rule. `App` supplies the SDL event's modifier snapshot only for the main menu.
Other UI pages still use their existing mapper; the physical gameplay mapper,
key ownership and release/repress behavior are unchanged.

## Preserved Evidence

All committed records, representative PNGs, exact compressed executed sources
and the focused CTest log are under
`evidence/main_menu_characters_20261001/`. `manifest.json` pins their bytes;
the directory is excluded from Git text conversion. The archived probes have
checkout-relative imports and are not standalone production launchers.

Five failed records remain failures: the old C++ Shift+L behavior, two C++
keypad-XOR negatives, an original Shift-only keypad probe with an incorrect
unchanged-menu expectation, and an original allocation-guard startup failure.
The failed expectation's observed byte 49 and intro are counterevidence, not a
relabeled pass. A separate fresh correctly scoped Shift-only run succeeds.
The allocation failure has no input or frames and proves no game behavior.
Other unique exploratory runs remain in their named `/dev/shm/lezac-*-main-*`
directories; they are not erased or promoted.

The pre-change release executable is `57da6e28...`; the intermediate wrong-XOR
build is `9a37e3a0...`; the corrected local executable is `4dc99d50...`.
The full hashes are retained in their records and the evidence checker.
The paired Num+Shift intro PNGs are naturally seeded and are not pixel aligned.

## Validation And Remaining Scope

- All 24 selected CTests pass in 161.62 seconds, covering menu models/pixels,
  source/silence/status guards, UI/records/intro behavior, the five sealed Level
  1 routes, the original evidence guard and the replay contract.
- The expanded normal-window harness passes 14 checkpoints, 25 ignored
  choices, two held Returns, Caps+Shift language selection, Alt+F5, and all
  four keypad 1 lock/Shift combinations. The previous XOR executable fails
  that same physical matrix at Num+Shift.
- All seven key-ownership movement/jump cases and all three buffered-input
  physical cases pass with dummy audio against the corrected executable.
- `main_menu_character_evidence` checks 16 original observations, five failed
  records, source/manifest integrity and six rejection mutations. It does not
  rerun DOSBox or infer a completion claim from stored records.

Full Linux/Windows suites and extracted-package validation remain required
before merge. Complete keyboard buffer eligibility, Alt+numpad character
composition, non-US layouts, other pages' typing/blocking input, broader
campaign/actor/collapse/two-player behavior and manual acceptance remain open.
`port_functionally_complete=0` and `original_fidelity_claim=0` are unchanged.
