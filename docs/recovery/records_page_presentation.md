# Original Records Page

## Recovered Contract

`LEZAC.EXE` SHA-256 is
`7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec`.
Addresses are CS offsets; add `0x770` for file offsets.

The records routine at `20AC` calls the procedural background at `01FC`,
then draws `punteggi migliori` (literal `2095`) at y=10. Seven record lines
start at y=72 with pitch 11. Each line is one centered Pascal name followed
by four spaces and a signed 32-bit decimal score. All text uses 9-pixel cells,
the small font, color 10 and shadow 6. These indices retain the title-screen
palette, not BOMPAL's gameplay colors. No rank, level, extra branding, overlay,
or back hint is present. The title is unconditional in this routine.

The original contiguous font mapping displays stored `:` padding as dots.
The Pascal length, not the full eight-byte storage capacity, controls the
visible name. `2160` performs a blocking ReadKey and returns to the menu;
the acknowledgement must not dispatch a new-game or another menu command.

## Original Observations

Two isolated, silent DOSBox runs entered records from the settled main menu.
One used the shipped record file unchanged; the other used a declared file
fixture with lengths `8,1,0,2,3,4,7` and nonblank hidden tails. Neither run
wrote process memory or seeded gameplay, code, RNG, clock, or heap state.
Eight retained 1-MiB RAM snapshots independently preserve all 43,552 relocated
code bytes. All 80 typing PNGs and eight boundary PNGs are hash-verified.
After Return, both full frames exactly equal their initial settled main menu.
Canonical original files remain unchanged. RAM reads were not atomic.

`tests/fixtures/records_page_original.json` pins both producers/reports,
record inputs and complete 320x200 RGB oracles. Background h/v inputs and
seven colors are inferred from unoccluded background pixels, not injected
into the original. The regression compares every final pixel, including all
text, without masks, cropping, resampling, or tolerated differences.

## Port Integration

`Record::nameLength` occupies existing padding on the tested GCC and MSVC
layouts; compile-time checks preserve size, alignment and every prior field
offset. Current repository consumers do not use positional Record aggregate
initializers. This is not a cross-toolchain ABI guarantee.

Raw decoding uses only the declared length for decoded metadata, preserves
eight opaque storage bytes, and sets unknown port-only level metadata to 0.
JSON gains optional `name_length` (legacy default 8), while existing `level`
values remain supported. Raw and JSON saves retain the explicit length and
all eight storage bytes. Lengths above 8 fail closed; matching unsafe original
behavior for malformed records is not claimed.

Every port records-page entry prepares one frozen background through the
existing eight-draw pattern generator. Redrawing does not consume RNG. The
full-App menu regression checks eight entry draws and zero redraw draws.
The component test covers both port language settings, 40 domain keys,
short/zero names, exact raw/JSON round trips, and existing field layout.
Original Game Over and record-save component regressions remain required.

## Evidence Boundaries

These are settled component frames matched to original observations, not
naturally RNG-aligned full-App replays. The English port uses the unconditional
binary title contract; these observations did not toggle the original language.
Full-App builds and tests run in CI because the Windows disk exceeds the
repository threshold. Component results do not replace that evidence.

Records typing/recolor timing, queued-key behavior during typing, end-of-run
record ordering, cutoff equality, name-entry presentation, audio runtime
parity, whole-game fidelity and completion remain open. In particular, the
port's post-name-entry records page is not proof of the original end-flow order.
