#!/usr/bin/env python3
"""Check runtime-oracle lanes share optional original fixture conventions."""

from __future__ import annotations

import argparse
from pathlib import Path


LANES = (
    {
        "name": "actor_update",
        "script": Path("tools/check_actor_update_runtime_oracle_fixtures.py"),
        "prefix": "actor_update_runtime_oracle_original",
        "summary": "actor_update_runtime_oracle_fixtures=ok",
        "ctest": "actor_update_runtime_oracle_fixture_expectations",
    },
    {
        "name": "contact_scanner",
        "script": Path("tools/check_contact_scanner_runtime_oracle_fixtures.py"),
        "prefix": "contact_scanner_runtime_oracle_original",
        "summary": "contact_scanner_runtime_oracle_fixtures=ok",
        "ctest": "contact_scanner_runtime_oracle_fixture_expectations",
    },
    {
        "name": "behavior4",
        "script": Path("tools/check_behavior4_runtime_oracle_fixtures.py"),
        "prefix": "behavior4_runtime_oracle_original",
        "summary": "behavior4_runtime_oracle_fixtures=ok",
        "ctest": "behavior4_runtime_oracle_fixture_expectations",
    },
    {
        "name": "visual_table",
        "script": Path("tools/check_visual_table_oracle_fixtures.py"),
        "prefix": "visual_table_oracle_original",
        "summary": "visual_table_oracle_fixtures=ok",
        "ctest": "visual_table_oracle_fixture_expectations",
    },
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def check_script(root: Path, lane: dict[str, str | Path]) -> None:
    script = lane["script"]
    assert isinstance(script, Path)
    prefix = str(lane["prefix"])
    text = (root / script).read_text(encoding="utf-8")
    label = str(script)
    require(text, f'ORIGINAL_PREFIX = "{prefix}"', label)
    require(text, "def expected_outcome_for", label)
    require(text, "name.startswith(ORIGINAL_PREFIX)", label)
    require(text, 'return "ok"', label)
    require(text, "expected_outcome_for(name) is None", label)
    require(text, "original_count = 0", label)
    require(text, "original_count += 1", label)
    require(text, "original={original_count}", label)


def check_cmake(root: Path) -> int:
    text = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(text, "check_optional_original_oracle_fixtures.py", "CMakeLists.txt:script")
    require(
        text,
        "add_test(NAME optional_original_oracle_fixture_conventions",
        "CMakeLists.txt:test",
    )
    require(text, "optional_original_oracle_fixtures=ok", "CMakeLists.txt:output")
    for lane in LANES:
        require(text, str(lane["ctest"]), f"CMakeLists.txt:{lane['name']}:ctest")
        require(text, str(lane["summary"]), f"CMakeLists.txt:{lane['name']}:summary")
        require(text, "original=0", f"CMakeLists.txt:{lane['name']}:baseline")
    return len(LANES)


def check_docs(root: Path) -> int:
    docs = (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    )
    for relative in docs:
        text = (root / relative).read_text(encoding="utf-8")
        for lane in LANES:
            require(text, str(lane["prefix"]), f"{relative}:{lane['name']}:prefix")
        require(text, "visual_claim=0", relative)
    return len(docs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check optional original runtime-oracle fixture conventions."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    for lane in LANES:
        check_script(root, lane)
    cmake = check_cmake(root)
    docs = check_docs(root)
    print(
        "optional_original_oracle_fixtures=ok "
        f"lanes={len(LANES)} scripts={len(LANES)} prefixes={len(LANES)} "
        f"original_counts={len(LANES)} cmake={cmake} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
