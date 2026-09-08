# Resource Reader Bounds and Failure Atomicity

## Scope

This change hardens the existing binary-resource reader API. It does not change
valid resource formats, game rules, original fixtures, or completion claims.
No new dependency or test target is introduced: the existing `resource_binary`
CTest runs the expanded regression suite in both CI jobs.

## Reproduced failure

Baseline: `main` at `de9a2692f2c2d136dbe4df6661bca1dd180a9c92`.
The local copies of `binary.cpp`, `binary.hpp`, and their test were checked
against the upstream Git blob hashes before editing.

Passing `std::numeric_limits<std::size_t>::max()` as the offset to `le16`
with a four-byte vector bypassed `off + 2 > data.size()` after unsigned
wraparound. AddressSanitizer reported a one-byte heap-buffer-overflow read
immediately before the vector allocation at `binary.cpp:9`; the reproducer
exited with status 1. This demonstrates an invalid-offset API failure, not
that a particular shipped asset reaches that state.

`le32` and `getBytes` used the same addition-before-validation pattern.
`recLe16` had no record-boundary validation. Record payload validation also
multiplied the count by the record width before comparing the result.

## Changes

- Validate the offset first, then compare the requested width to the remaining
  bytes. Oversized offsets and lengths are rejected without wrapping arithmetic.
- Add the corresponding guard to `recLe16`, including empty and one-byte arrays.
- Validate fixed-record payloads through division before copying. Preserve
  zero-count and zero-width behavior without dividing by zero.
- Commit the fixed-record cursor only after successful parsing. Missing counts,
  truncated payloads, and allocation exceptions do not consume caller state.
  This deliberately improves failed-read behavior; successful reads are unchanged.
- Use vector iterator `difference_type` rather than `long` for iterator offsets.
- Assemble 32-bit little-endian values using unsigned operands before shifting.

Existing exception types and existing error messages are retained; the newly
checked record word read reports `unexpected EOF while reading record u16`.

## Regression coverage

The existing test now additionally checks:

- empty, exact-end, past-end and near-`SIZE_MAX` offsets;
- empty blocks, overflowing block lengths and unchanged failed-read cursors;
- all 65,536 two-byte values through `le16`, `recLe16` and `getU16`;
- 1,025 four-byte values, varying each byte across 0..255 and checking `UINT32_MAX`;
- every fixed-record count from 0 through 255, nonzero starting offsets,
  exact payload consumption, trailing bytes and payload contents;
- all 255 nonempty truncated-record cases with cursor rollback;
- all 256 zero-width record counts, plus missing record counts.

The original CTest success prefix is emitted only after the new checks pass.
Tests use explicit failures rather than assertions, so Release/NDEBUG builds
still execute the checks.

## Validation

Focused local validation passed with GCC and Clang in C++17 Release/NDEBUG
mode, with `-Wall -Wextra -Wpedantic -Werror`. The same regression executable
passed AddressSanitizer and UndefinedBehaviorSanitizer with recovery disabled
and leak detection enabled. The original minimal reproducer now exits 0 by
catching the expected `std::runtime_error`, with no sanitizer diagnostic.

From a complete checkout, the focused test can be reproduced without SDL:

```sh
g++ -std=c++17 -O2 -DNDEBUG -Wall -Wextra -Wpedantic -Werror -Isrc src/resources/binary.cpp tests/resources/resource_binary_test.cpp -o /tmp/lezac-resource-binary-test
/tmp/lezac-resource-binary-test
g++ -std=c++17 -g -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer -Isrc src/resources/binary.cpp tests/resources/resource_binary_test.cpp -o /tmp/lezac-resource-binary-sanitized
ASAN_OPTIONS=detect_leaks=1 /tmp/lezac-resource-binary-sanitized
```

Local validation used only the relevant source files, not a full SDL build.
The full application suite and Windows coverage belong to the PR's existing CI
checks and must be reported separately. No DOSBox behavior or visual parity
was tested or inferred by this change.
