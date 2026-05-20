#!/usr/bin/env python3
"""Check that GRAN.MST remains opaque outside debug/resource preservation paths."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


DEBUG_FUNCTIONS = ("validate", "debugGranRawRoundtrip", "debugGran")


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def function_ranges(lines: list[str]) -> dict[str, tuple[int, int]]:
    ranges: dict[str, tuple[int, int]] = {}
    for index, line in enumerate(lines):
        match = re.match(r"\s+void\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{", line)
        if not match or match.group(1) not in DEBUG_FUNCTIONS:
            continue
        depth = 0
        end = index
        for cursor in range(index, len(lines)):
            depth += lines[cursor].count("{")
            depth -= lines[cursor].count("}")
            end = cursor
            if depth == 0:
                break
        ranges[match.group(1)] = (index + 1, end + 1)
    return ranges


def in_range(line_number: int, ranges: dict[str, tuple[int, int]]) -> bool:
    return any(start <= line_number <= end for start, end in ranges.values())


def check_source(root: Path) -> tuple[int, int, int, int]:
    lines = (root / "src" / "main.cpp").read_text(encoding="utf-8").splitlines()
    ranges = function_ranges(lines)
    missing = [name for name in DEBUG_FUNCTIONS if name not in ranges]
    if missing:
        raise RuntimeError("missing debug function range(s): " + ",".join(missing))

    source_refs = 0
    load_refs = 0
    debug_refs = 0
    member_refs = 0
    live_refs: list[str] = []
    for line_number, line in enumerate(lines, start=1):
        if "gran_" not in line:
            continue
        source_refs += 1
        if 'gran_ = loadGran("GRAN.MST.json")' in line:
            load_refs += 1
            continue
        if "GranBank gran_;" in line:
            member_refs += 1
            continue
        if in_range(line_number, ranges):
            debug_refs += 1
            continue
        live_refs.append(f"{line_number}:{line.strip()}")

    if live_refs:
        raise RuntimeError("unexpected live GRAN references: " + "; ".join(live_refs))
    if load_refs != 1 or member_refs != 1:
        raise RuntimeError(
            f"unexpected GRAN load/member counts: load={load_refs} member={member_refs}"
        )
    return source_refs, load_refs, debug_refs, member_refs


def check_cmake(root: Path) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_gran_usage_guardrail.py", "cmake:script")
    require(cmake, "add_test(NAME gran_usage_guardrail", "cmake:test")
    require(cmake, "gran_usage_guardrail=ok", "cmake:output")
    return 1


def check_docs(root: Path) -> int:
    docs = (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    )
    for relative in docs:
        text = (root / relative).read_text(encoding="utf-8")
        require(text, "check_gran_usage_guardrail.py", relative)
        require(text, "`GRAN.MST`", relative)
    return len(docs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check GRAN.MST usage stays limited to opaque preservation paths."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    source_refs, load_refs, debug_refs, member_refs = check_source(root)
    ctest = check_cmake(root)
    docs = check_docs(root)
    print(
        "gran_usage_guardrail=ok "
        f"source_refs={source_refs} load_refs={load_refs} "
        f"debug_refs={debug_refs} member_refs={member_refs} "
        f"live_refs=0 ctest={ctest} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
