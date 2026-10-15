# Wrapped Debris Cell Identity

The physical falling-fragment seeder retains the raw cell for record position
and object-byte lookup. Only the word-plane accessor applies its segment wrap.
For the above-cell underflow `40 - 60`, raw cell 65516 aliases word cell 32748,
but object bytes at those cells are distinct.

Original `1000:3792..3798` stores `[bp+0xc]` in the debris record. Original
`1000:37AF..37B8` uses that same raw argument for the object-byte read. The
physical seeder passes the raw address to explicit read/write callbacks;
`MapPlaneMemory` owns word address translation. This keeps memory layout policy
out of record construction and preserves admission, flagging and insertion order.
The existing logical adapter retains its `size_t` indexing and checked access.

## Validation Scope

- The new C++ unit test covers 96 combinations across vector and retained queues,
  two raw cells, six word values and four capacity boundaries. Distinct raw and
  aliased glyphs expose accidental normalization. Salted records and retained
  candidates check noninterference.
- The existing 48 logical seeder cases and flame cursor guard remain registered.
  A logical index above 65535 checks that the public adapter was not narrowed.
- The logical collapse adapter also reads its key at the original `size_t`
  index before the 16-bit geometry wraps. Seeds 32768, 65535 and 65536 with
  different aliased keys check this pre-refactor contract.
- The new original-capture adapter pins the historical producer byte-for-byte.
  Its self-check proves that only scene input and read-only observer additions
  differ; it does not execute the emulator or establish App parity.
- CI captures two debris-class wrapped scenes using the unmodified original
  dispatcher and hash-pinned Unicorn 2.1.4. Original RAM/register neutrality and
  raw record/glyph observations must pass before accepting the capture.

## Executed Counterexample

Original capture run 38380163226 at source `725bbc7` passed both scenes. Its
artifact SHA-256 is `dfb975e6b6a2821767caa7e971564eafe4953fabb81b52ecdc3ee473979f77e4`.
Independent event replay checks all 16 reads and 8 writes, both complete map
planes, the unchanged original code and the original full-RAM hash chain.
The final original records retain cell 65516 and glyphs 39 and 56.

The actual Linux package from the old PR379 head `731e76c` differs at state
byte 5953 (the record cell's high byte). The Linux package at `725bbc7` matches
all 315592 original state bytes with no masks. Six new nonblank Level 7 boss
frames were also captured silently. These results are specific seeded
transitions and rendered checkpoints, not natural-route or visual-parity proof.

The separate wrapped fixtures and complete-state checker retain this capture
as a permanent regression. Original historical fixtures remain unchanged.
Fresh full Linux/Windows CI and completed current-head review remain required
before merge. No audiovisual parity or whole-game completion is claimed.

The refactor follows the project's [C++ modernization contract](../cpp-modernization.md)
and the [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
for explicit interfaces and focused ownership. It does not introduce an ECS,
new shared ownership or draft-only language features.
