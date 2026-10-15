# C++ Modernization Contract

Checked against primary sources on 2026-10-13. Use C++23 as the required portable
baseline, without GNU extensions or silent standard fallback. ISO lists
ISO/IEC 14882:2024 (C++23) as published and its 2026 successor as a draft;
GCC and Clang still document incomplete or experimental C++26 support.
CMake 3.20 is the minimum version that recognizes `CXX_STANDARD 23`.

## Coding Rules

- Follow the C++ Core Guidelines for explicit interfaces, RAII resource ownership,
  const correctness, narrow scope, and non-owning views where lifetime is clear.
- Prefer the rule of zero. Use `unique_ptr` for exclusive heap or foreign-resource
  ownership; custom deleters must not throw. Do not add shared ownership without
  a genuine shared lifetime.
- Use supported standard-library facilities when they simplify the operation.
  Do not add ranges, concepts, modules, inheritance, or allocations merely to use
  a newer language feature.
- Preserve recovered integer widths, wrapping, record layouts, queue tails,
  update order, error contracts, resource formats, and public ownership contracts.
  Modernization is not permission to redesign gameplay or introduce an ECS.
- Keep changes reviewable by subsystem. Add boundary and failure-path tests.
  Retain pinned original producers and fixtures unchanged; old extraction modes
  remain explicitly scoped historical evidence, not a C++23 full-App result.
- Keep tests and game execution silent. Source checks, compiler checks, unit tests,
  actual packaged execution, original comparisons, and visual acceptance are
  distinct evidence levels.

## First Batch

The build requires C++23 for all project targets and propagates this requirement
from the two independent library roots. A compile/run contract checks
`std::to_underlying`, `std::byteswap`, `string_view::contains`, and `std::span`.

`SdlDisplay` builds a complete replacement in local RAII owners and commits it only
after all SDL operations succeed. Existing display resources survive a failed
replacement; successful replacement releases texture, renderer, then window.
Failure injection tests verify initialization, fallback, repeated replacement,
presentation errors, and release order. These are mocked SDL ownership tests,
not actual SDL rendering or gameplay-parity evidence.

Remaining work includes staged modernization of parsing, borrowed buffer
interfaces, constants and enum conversions, and class-level const/noexcept
contracts. The entire codebase is not yet audited against every guideline.

## Sources

- [ISO C++ publication status](https://www.iso.org/standard/83626.html)
- [C++ Core Guidelines](https://isocpp.github.io/CppCoreGuidelines/CppCoreGuidelines)
- [GCC C++ implementation status](https://gcc.gnu.org/projects/cxx-status.html)
- [Clang C++ implementation status](https://clang.llvm.org/cxx_status.html)
- [CMake CXX_STANDARD](https://cmake.org/cmake/help/latest/prop_tgt/CXX_STANDARD.html)
