#!/usr/bin/env python3
"""Check that GRAN.MST remains opaque outside debug/resource preservation paths."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile


DEBUG_FUNCTIONS = (
    "validate",
    "debugShippedFileManifest",
    "debugGranRawRoundtrip",
    "debugGran",
    "debugOriginalAssetLoad",
)


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
        if (
            'gran_ = loadGran("GRAN.MST.json")' in line
            or 'gran_ = loadRawGran("GRAN.MST")' in line
        ):
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
    if load_refs != 2 or member_refs != 1:
        raise RuntimeError(
            f"unexpected GRAN load/member counts: load={load_refs} member={member_refs}"
        )
    return source_refs, load_refs, debug_refs, member_refs


def check_cmake(root: Path) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_gran_usage_guardrail.py", "cmake:script")
    require(cmake, "add_test(NAME gran_usage_guardrail", "cmake:test")
    require(cmake, "gran_usage_guardrail=ok", "cmake:output")
    require(cmake, "add_test(NAME gran_raw_roundtrip", "cmake:raw_roundtrip_test")
    require(cmake, "raw_json_match=1", "cmake:raw_roundtrip_output")
    require(cmake, "add_test(NAME gran_profile", "cmake:profile_test")
    return 3


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


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_contract_files(root: Path) -> None:
    write_text(
        root / "CMakeLists.txt",
        "\n".join(
            (
                "add_test(NAME gran_usage_guardrail",
                "  COMMAND python tools/check_gran_usage_guardrail.py)",
                "set_tests_properties(gran_usage_guardrail PROPERTIES",
                '  PASS_REGULAR_EXPRESSION "gran_usage_guardrail=ok")',
                "add_test(NAME gran_raw_roundtrip",
                "  COMMAND lezac_cpp --debug-gran-raw-roundtrip)",
                "set_tests_properties(gran_raw_roundtrip PROPERTIES",
                '  PASS_REGULAR_EXPRESSION "raw_json_match=1")',
                "add_test(NAME gran_profile",
                "  COMMAND lezac_cpp --debug-gran)",
                "",
            )
        ),
    )
    for relative in (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    ):
        write_text(
            root / relative,
            "`GRAN.MST` remains opaque; see tools/check_gran_usage_guardrail.py.\n",
        )


def write_source(root: Path, live_line: str = "", include_debug: bool = True) -> None:
    debug_functions = (
        "\n".join(
            (
                "    void validate() {",
                "        if (gran_.records.empty()) {",
                "            throw Error();",
                "        }",
                "    }",
                "",
                "    void debugShippedFileManifest() {",
                '        dump("exe_gran_anchor");',
                "    }",
                "",
                "    void debugGranRawRoundtrip() {",
                "        dump(gran_.records);",
                "    }",
                "",
                "    void debugGran() {",
                "        dump(gran_.recordSize);",
                "    }",
                "",
                "    void debugOriginalAssetLoad() {",
                "        auto jsonGran = gran_;",
                "        dump(gran_.records.size());",
                "    }",
                "",
            )
        )
        if include_debug
        else ""
    )
    write_text(
        root / "src" / "main.cpp",
        "\n".join(
            (
                "class Game {",
                "    void loadAssets() {",
                '        gran_ = loadGran("GRAN.MST.json");',
                '        gran_ = loadRawGran("GRAN.MST");',
                "    }",
                "",
                debug_functions,
                "    void updateLive() {",
                f"        {live_line}",
                "    }",
                "",
                "    GranBank gran_;",
                "};",
                "",
            )
        ),
    )


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="lezac-gran-guardrail-") as tmp:
        root = Path(tmp)
        write_contract_files(root)
        write_source(root)
        source_refs, load_refs, debug_refs, member_refs = check_source(root)
        if (source_refs, load_refs, debug_refs, member_refs) != (9, 2, 6, 1):
            raise RuntimeError("selftest positive source counts mismatch")
        check_cmake(root)
        check_docs(root)

        write_source(root, "auto live_count = gran_.records.size();")
        try:
            check_source(root)
        except RuntimeError as exc:
            if "unexpected live GRAN references" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest live GRAN reference was not rejected")

        write_source(root, include_debug=False)
        try:
            check_source(root)
        except RuntimeError as exc:
            if "missing debug function range" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing debug function was not rejected")

        write_source(root)
        write_text(root / "README_RECONSTRUCTION.md", "`GRAN.MST` remains opaque.\n")
        try:
            check_docs(root)
        except RuntimeError as exc:
            if "check_gran_usage_guardrail.py" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing docs guardrail reference was not rejected")

    print(
        "gran_usage_guardrail_selftest=ok "
        "positive=1 live_ref=1 missing_debug=1 docs=1"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check GRAN.MST usage stays limited to opaque preservation paths."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="exercise synthetic positive and rejection cases",
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    if args.self_test:
        return self_test()

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
