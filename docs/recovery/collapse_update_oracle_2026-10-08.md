# Complete Collapse Updater Oracle

The optional capture tool executes original `1000:5102` with no patched
instructions, call stubs, DOS services or hardware I/O. All 468 MZ relocations
are applied and every invocation must return at its normal CS/IP/SP boundary.
The original word-plane segment cache at `DS:206E` is initialized consistently
with the far word-plane pointer. The original setup stores that cache at code
`1000:2B28` (file `0x3298`).

## Independent Native Cross-Check

Before expanding cases, execution reproduces all 27 retained DOSBox collapse
cases. Complete live 11-byte debris and 15-byte collapse records, selected
native map cells, RNG, destruction and fragment-word counter agree. The native
fixture does not provide the full initial map outside its controlled region;
whole-map native equivalence is not claimed there. Sprite descriptors come
from the independently retained fracture-actor fixture.

## Controlled Expansion

There are 2,395 cases: 27 native cross-checks, 1,728 horizontal/vertical/diagonal
supported and airborne cases, 128 debris contacts, and 512 collapse contacts.
Signed-byte velocity/fraction extremes, flags, resting-counter wrap and
retirement boundaries, zero/high target mass, fractures and live pool changes
are explicit controlled states, not claims about natural reachability.

The real original routines execute 301 actor constructors, 507 seeders, 388
removals, 1,429 RNG calls and 423 sound-latch calls. The maximum is 2,585
instructions per case. Actor records and sound state are not compared.

The fixture retains complete initial/final object and word planes, every live
debris/collapse record byte and count, RNG, destroyed count and next fragment
word. Executable, relocated image, instruction window, generator/dependencies,
native fixtures, and fixture/input/output digests are pinned. Legacy text
fixtures and metadata are `-text` so checkout cannot change their raw hashes.

```sh
env SDL_AUDIODRIVER=dummy python3 tools/capture_original_collapse_update.py \
  --exe LEZAC.EXE --levels LIVELS.SCH --native-fixtures-dir tests/fixtures \
  --unicorn-path /path/to/unicorn-2.1.4 \
  --out /path/to/empty/collapse_update_original.bin.gz \
  --metadata /path/to/empty/collapse_update_original.json
```

## Production Comparison

`--debug-original-collapse-update INPUT OUTPUT` shares the debris diagnostic's
binary deserializer/serializer but calls the actual `updateCollapseRecords`.
The existing debris wire format and command remain unchanged. The checker
compares every output byte, rejects an output mutation and eight source-routing
mutations. CI runs it early on both platforms before unchanged complete suites.
Failed compiled inputs, reference and actual outputs are retained and uploaded.
Source/oracle checks alone do not establish compiled parity.

This batch includes the contact-helper, seeder and byte-preserved debris
prerequisites in a fresh branch; their running source heads remain untouched.

## Limits

The actor pool starts empty. Actor records, sound state, physical timer cadence,
rendering, arbitrary memory and inactive tails are excluded. Cases are seeded
original-CPU/production replays, not a new native capture, natural collision
route, full actor interaction, two-player campaign or whole-game completion.
No broad original-fidelity or completion flag changes.
