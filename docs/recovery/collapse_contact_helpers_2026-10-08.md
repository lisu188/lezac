# Collapse Contact Helper Execution

## Scope

The optional `tools/capture_original_collapse_contacts.py` executes the complete
original forward (`1000:3BB2`) and reverse (`1000:3D46`) contact helpers. It loads
the hash-pinned MZ executable with all 468 relocations, executes the original
matchers, seeder, Pascal stack check and signed long divider, and checks the
normal return CS, IP and SP after every invocation. No instruction or called
routine is patched or stubbed. Unexpected interrupts and hardware I/O fail.

The checked-in compressed fixture contains actual original outputs, not a
second arithmetic implementation. Each output includes the caller's lane,
live 11-byte debris records, live 15-byte collapse records, 128 word-plane
cells and 128 object-plane bytes. The metadata pins the executable, original
instruction windows, generator and input/output byte digests.

## Matrix

- 6,880 existing-target cases: both directions; signed byte extrema and zero;
  own weights 1, 2, 18, 128, 254 and 255; collapse weights including 8 and 18;
  and 0, 1, 2, 3, 5, 10 or 30 staged contacts.
- 2,304 allocation cases: new debris alone, existing contacts before/after new
  contacts, and mixed 30-contact lists; initial high-slot bounds 200, 1598,
  1599 and 1600; both directions and the same own velocity/weight matrix.
- 1,248 allocation failures, including 672 cases where earlier allocations
  survive a later failure. Failure returns before division or lane writeback.
- Successful calls use the original signed 32-bit accumulation/division path.
  The different signed-word wrap contract of the flame blend does not apply.

The first debris slot is 200 and the inclusive final slot is 1600: 1,401 live
records. The existing C++ capacity check already represents that limit.

## Production Regression

`blendCollapseContacts` is the existing `updateCollapseRecords` blend lambda
extracted without an intended behavior change. The ordinary runtime and
`--debug-collapse-contacts-original INPUT OUTPUT` call that same helper. The
diagnostic decodes fixed binary fixture records and serializes the resulting
live state; it does not calculate expected outputs.

`tools/check_collapse_contacts_original.py --exe PATH` compares every output
byte with the executed-original fixture. It rejects four output mutations.
`--self-check` rejects ten source-contract mutations and verifies that both
the runtime and diagnostic call the same helper. These source checks are not
a substitute for the compiled comparison. Both tests run before the unchanged
full suite on Linux and Windows CI. Existing package validation is unchanged.

To reproduce the oracle, use an empty destination and the optional analysis-only
Unicorn 2.1.4 installation:

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_collapse_contacts.py \
  --exe LEZAC.EXE --unicorn-path /path/to/unicorn-2.1.4 \
  --out /path/to/empty/collapse_contacts_original.bin.gz \
  --metadata /path/to/empty/collapse_contacts_original.json
```

The production build and CI do not depend on Unicorn. Capture destinations use
exclusive creation so existing evidence cannot be overwritten.

## Remaining Evidence

This is controlled helper execution, not a DOSBox/native timing capture or a
natural campaign route. It does not cover the contact collector, full collapse
movement/update, unflagged collapse-group allocation, missing-key inputs, zero
total mass, or natural explosion sprite playback. Duplicate-key selection and
two-player/full actor state still need their separate evidence. All broad
original-fidelity, sound-parity and whole-game completion claims remain false.
