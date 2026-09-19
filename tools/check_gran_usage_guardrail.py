#!/usr/bin/env python3
"""Check that GRAN.MST remains opaque outside debug/resource preservation paths."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from source_guardrails import source_files, function_ranges as cpp_function_ranges


DEBUG_FUNCTIONS = (
    "validate",
    "debugShippedFileManifest",
    "debugPortCompletionStatus",
    "debugGranStaticConsumerModel",
    "debugGranBossModel",
    "debugGranRawRoundtrip",
    "debugGran",
    "debugOriginalAssetLoad",
)

# Live consumers must be backed by recovered-consumer evidence before being
# added here. spawnLevel7Boss implements the level-7 boss decoded by the
# static consumer model (--debug-gran-static-consumer-model /
# --debug-gran-boss-model) from the shipped executable's reader at
# 1000:08A5 behind the DS:0x79B7 == 7 level gate.
LIVE_FUNCTIONS = ("spawnLevel7Boss",)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def function_ranges(lines: list[str],
                    names: tuple[str, ...] = DEBUG_FUNCTIONS) -> dict[str, tuple[int, int]]:
    return cpp_function_ranges("\n".join(lines), names)


def in_range(line_number: int, ranges: dict[str, tuple[int, int]]) -> bool:
    return any(start <= line_number <= end for start, end in ranges.values())


def check_source(root: Path) -> tuple[int, int, int, int, int]:
    sources = source_files(root, roles=("runtime", "diagnostics", "dispatch"))
    found_debug = set()
    found_live = set()
    source_refs = load_refs = debug_refs = member_refs = live_consumer_refs = 0
    live_refs: list[str] = []
    for source in sources:
        lines = source.text.splitlines()
        ranges = function_ranges(lines) if "diagnostics" in source.roles else {}
        live_ranges = function_ranges(lines, LIVE_FUNCTIONS) if "runtime" in source.roles else {}
        if found_debug.intersection(ranges) or found_live.intersection(live_ranges):
            raise RuntimeError(f"{source.relative}: duplicate GRAN consumer definition")
        found_debug.update(ranges)
        found_live.update(live_ranges)
        for line_number, line in enumerate(lines, start=1):
            if "gran_" not in line:
                continue
            source_refs += 1
            if "runtime" in source.roles and (
                'gran_ = loadGran("GRAN.MST.json")' in line
                or 'gran_ = loadRawGran("GRAN.MST")' in line
            ):
                load_refs += 1
            elif "runtime" in source.roles and "GranBank gran_;" in line:
                member_refs += 1
            elif in_range(line_number, ranges):
                debug_refs += 1
            elif in_range(line_number, live_ranges):
                live_consumer_refs += 1
            else:
                live_refs.append(f"{source.relative}:{line_number}:{line.strip()}")

    missing = [name for name in DEBUG_FUNCTIONS if name not in found_debug]
    if missing:
        raise RuntimeError("missing debug function range(s): " + ",".join(missing))
    missing_live = [name for name in LIVE_FUNCTIONS if name not in found_live]
    if missing_live:
        raise RuntimeError("missing live consumer function range(s): " + ",".join(missing_live))

    if live_refs:
        raise RuntimeError("unexpected live GRAN references: " + "; ".join(live_refs))
    if load_refs != 2 or member_refs != 1:
        raise RuntimeError(
            f"unexpected GRAN load/member counts: load={load_refs} member={member_refs}"
        )
    return source_refs, load_refs, debug_refs, member_refs, live_consumer_refs


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
    write_text(root / "tools/source_ownership.json", json.dumps({
        "version": 1,
        "owners": {
            "app": {"runtime": ["src/app/app.cpp"], "dispatch": ["src/app/app.cpp"]},
            "diagnostics": {"diagnostics": ["src/app/app.cpp"]},
        },
    }))
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
                "    void debugPortCompletionStatus() {",
                '        dump("gran_mst_preservation");',
                "    }",
                "",
                "    void debugGranStaticConsumerModel() {",
                '        dump("gran_static_consumer_model=ok");',
                "    }",
                "",
                "    void debugGranBossModel() {",
                '        dump("gran_boss_model=ok");',
                "    }",
                "",
                "    void spawnLevel7Boss() {",
                "        auto records = gran_.records;",
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
        root / "src" / "app" / "app.cpp",
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
        source_refs, load_refs, debug_refs, member_refs, live_consumer_refs = \
            check_source(root)
        if (source_refs, load_refs, debug_refs, member_refs,
                live_consumer_refs) != (13, 2, 9, 1, 1):
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
    source_refs, load_refs, debug_refs, member_refs, live_consumer_refs = \
        check_source(root)
    ctest = check_cmake(root)
    docs = check_docs(root)
    print(
        "gran_usage_guardrail=ok "
        f"source_refs={source_refs} load_refs={load_refs} "
        f"debug_refs={debug_refs} member_refs={member_refs} "
        f"live_consumer_refs={live_consumer_refs} "
        f"live_refs=0 ctest={ctest} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
