#!/usr/bin/env python3
"""Require every DOSBox oracle fixture to state its visual-claim status."""

from __future__ import annotations

import argparse
from pathlib import Path


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def fixture_claims(root: Path) -> tuple[int, int, int]:
    fixture_dir = root / "tests" / "fixtures" / "dosbox"
    fixtures = sorted(fixture_dir.glob("*.txt"))
    if not fixtures:
        raise RuntimeError(f"no fixtures found under {fixture_dir}")

    claim0 = 0
    claim1 = 0
    errors: list[str] = []
    for fixture in fixtures:
        values: list[str] = []
        for line in fixture.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("visual_claim="):
                values.append(stripped.split("=", 1)[1])

        if len(values) != 1:
            errors.append(f"{fixture.name}:visual_claim_count={len(values)}")
            continue
        if values[0] == "0":
            claim0 += 1
        elif values[0] == "1":
            claim1 += 1
        else:
            errors.append(f"{fixture.name}:visual_claim={values[0]}")

    if errors:
        raise RuntimeError("fixture visual claim errors: " + "; ".join(errors))
    return len(fixtures), claim0, claim1


def check_cmake(root: Path) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_visual_claim_guardrail.py", "cmake:script")
    require(cmake, "add_test(NAME visual_claim_guardrail", "cmake:test")
    require(cmake, "visual_claim_guardrail=ok", "cmake:output")
    return 1


def check_docs(root: Path) -> int:
    docs = (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    )
    for relative in docs:
        text = (root / relative).read_text(encoding="utf-8")
        require(text, "check_visual_claim_guardrail.py", relative)
        require(text, "visual_claim=0", relative)
    return len(docs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check DOSBox oracle fixtures carry explicit visual_claim values."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    fixtures, claim0, claim1 = fixture_claims(root)
    ctest = check_cmake(root)
    docs = check_docs(root)
    print(
        "visual_claim_guardrail=ok "
        f"fixtures={fixtures} claim0={claim0} claim1={claim1} "
        f"ctest={ctest} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
