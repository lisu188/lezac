# Flame Contact Signed-Word Arithmetic

The production flame-to-debris/collapse velocity blend is now shared with a
compiled regression. This extraction preserves the existing expression; no
arithmetic mismatch was found in the prior C++ implementation.

## Original Evidence

The fixture in `tests/gameplay/flame_contact_word_original.json` records hashes
from execution of the original relocated instructions at `1000:47DF..4850`
(114 bytes, file offsets `0x4F4F..0x4FC0`). The original executable SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Unicorn 2.1.4 executed these instructions without instruction patches or
stubbed calls. This is controlled instruction execution, not a DOSBox playthrough.

The original zero-extends mass and collision weight, multiplies signed-byte
velocities, adds the low words, then uses `CWD; IDIV` and stores the result byte.
The signed numerator therefore wraps to 16 bits before division. The production
`blendFlameVelocity` helper retains that order and truncation toward zero.

All 256 by 256 own/incoming velocity byte pairs were executed for each of the
three shipped masses (1, 9, 221) and seven selected boundary weights
(0, 1, 2, 8, 18, 128, 254): 21 groups and 1,376,256 cases. Both axes are checked;
Y uses the byte-negated input pair and independently covers the signed domain.
The eight-byte records contain inputs followed by both original result bytes.
The aggregate SHA-256 is
`32cf3bc4ab1007646427c621bc2d9ad6a0a8a7e8f46ae8aaab75cced03d18250`.

19,855 cases differ from unwrapped wide-integer arithmetic: 461 for mass 9,
weight 254; 5,157 for mass 221, weight 128; and 14,237 for mass 221, weight 254.
The fixture discriminates an otherwise plausible removal of word wrapping.

The optional analysis tool reproduces the original records with Unicorn 2.1.4
installed in an isolated analysis environment (not required for CTest):

```sh
python3 -B tools/capture_original_flame_contact_word.py --out /path/to/new-records.bin
```

It loads the pinned MZ executable, applies all 468 relocations, checks the loaded
instruction bytes, executes both arithmetic axes, and compares all resulting
record groups with the retained fixture. It refuses to overwrite an output.

## Regression And Scope

`flame_contact_word` runs the compiled production helper and compares each
record group and the aggregate with the executed-original hashes. It rejects
four output mutations. `flame_contact_word_contract` checks the role-aware
runtime consumer and rejects seven source-routing mutations; source checks
alone are not compiled evidence. Windows stdout is explicitly binary.

This evidence does not establish natural contact reachability, all possible
weights, full flame-update geometry, seeding, capacity, actor writeback,
explosion sprites, campaign completion, sound timing, or whole-game fidelity.
All broad completion and fidelity flags remain false. Local compilation is
subject to the unchanged memory/disk guards; CI results must be checked at the
exact pushed head before claiming compiled validation or merging.
