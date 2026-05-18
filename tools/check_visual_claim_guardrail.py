#!/usr/bin/env python3
"""Require every DOSBox oracle fixture to state its visual-claim status."""

from __future__ import annotations

import argparse
from pathlib import Path


LEDGER = Path("docs/recovery/visual_claim_promotions.md")


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def parse_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in line.split():
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields[key] = value.strip("`")
    return fields


def fixture_claims(root: Path) -> tuple[int, int, int, list[str]]:
    fixture_dir = root / "tests" / "fixtures" / "dosbox"
    fixtures = sorted(fixture_dir.glob("*.txt"))
    if not fixtures:
        raise RuntimeError(f"no fixtures found under {fixture_dir}")

    claim0 = 0
    claim1 = 0
    promoted: list[str] = []
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
            promoted.append(fixture.name)
        else:
            errors.append(f"{fixture.name}:visual_claim={values[0]}")

    if errors:
        raise RuntimeError("fixture visual claim errors: " + "; ".join(errors))
    return len(fixtures), claim0, claim1, promoted


def check_ledger(root: Path, promoted: list[str]) -> int:
    ledger_path = root / LEDGER
    text = ledger_path.read_text(encoding="utf-8")
    require(text, "promotion_ledger=visual_claim", str(LEDGER))
    require(text, "visual_claim=0", str(LEDGER))

    entries: dict[str, dict[str, str]] = {}
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped.startswith("- fixture="):
            continue
        fields = parse_fields(stripped[2:])
        fixture = fields.get("fixture")
        if fixture:
            entries[fixture] = fields

    missing = [name for name in promoted if name not in entries]
    if missing:
        raise RuntimeError("promoted fixture missing from ledger: " + ",".join(missing))

    extra = [name for name in entries if name not in promoted]
    if extra:
        raise RuntimeError("ledger entry without promoted fixture: " + ",".join(extra))

    required = ("visual_claim", "original_frame", "cpp_frame", "comparison", "docs")
    for name in promoted:
        fields = entries[name]
        for key in required:
            if key not in fields or not fields[key]:
                raise RuntimeError(f"{name}:missing_{key}")
        if fields["visual_claim"] != "1":
            raise RuntimeError(f"{name}:ledger_visual_claim={fields['visual_claim']}")
        doc_path = root / fields["docs"]
        if not doc_path.exists():
            raise RuntimeError(f"{name}:missing_docs={fields['docs']}")
    return 1


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
        require(text, str(LEDGER).replace("\\", "/"), relative)
    return len(docs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check DOSBox oracle fixtures carry explicit visual_claim values."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    fixtures, claim0, claim1, promoted = fixture_claims(root)
    ledger = check_ledger(root, promoted)
    ctest = check_cmake(root)
    docs = check_docs(root)
    print(
        "visual_claim_guardrail=ok "
        f"fixtures={fixtures} claim0={claim0} claim1={claim1} "
        f"ledger={ledger} promoted={len(promoted)} ctest={ctest} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
