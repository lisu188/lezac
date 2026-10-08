# Complete Collapse Updater Oracle

The optional capture tool executes original `1000:5102` with no patched
instructions, call stubs, DOS services or hardware I/O. All 468 MZ relocations
are applied and every invocation must return at its normal CS/IP/SP boundary.
The original word-plane segment cache at `DS:206E` is initialized consistently
with the far word-plane pointer. The original setup stores that cache at code
`1000:2B28` (file `0x3298`).

Before every case, four original startup instructions at `1000:293D..2949`
(file `0x30AD..30B9`) initialize `DS:207A=0x6620` and `DS:207C=0x209E`.
Their bytes and digest, execution count, end IP and resulting bases are checked.
These are the collapse and debris table bases used by live-record removal.

## Corrected Initialization Precondition

The first PR #314 oracle omitted the collapse-table base, leaving it zero.
Both compiled platforms disagreed in exactly 90 of 2,395 cases: removing a
collapse record with a following survivor compacted the wrong original memory.
Inputs, maps, RNG, counters and debris outputs otherwise agreed. The failed
head, fixture, raw outputs and CI artifacts are preserved, not overwritten.

The base values are established by original startup instructions, not inferred
from C++ output. An independent retained native Level 4 DS capture also contains
`0x6620` and `0x209E`. Its gzip SHA-256 is
`2e62fa99c8f7ab277931706d82d5f0e504fb00592ec0a67effcf1f4107595191`;
the first 65,536-byte DS snapshot SHA-256 is
`a97b7a5dc3439c63aa9a25abb5882e788a183abe75b38986232fb384c5354674`.

Executing those startup instructions before each case changes exactly the 90
failed expected outputs. All input bytes and 27 native cross-checks stay
unchanged. All 2,395 corrected outputs match both retained compiled-platform
outputs byte-for-byte. Production C++ is unchanged. This is a corrected original
execution precondition, not normalized output or a new native gameplay capture.
Fresh-head CI is still required independently of the retained-output comparison.

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
compares every output byte, rejects an output mutation, eight source-routing
mutations and eight initialization mutations. CI runs it early on both platforms
before unchanged complete suites.
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
