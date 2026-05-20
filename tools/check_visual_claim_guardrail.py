#!/usr/bin/env python3
"""Require every DOSBox oracle fixture to state its visual-claim status."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile


LEDGER = Path("docs/recovery/visual_claim_promotions.md")
ARTIFACT_FIELDS = ("original_frame", "cpp_frame", "comparison")


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


def checked_in_path(root: Path, value: str, fixture: str, key: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise RuntimeError(f"{fixture}:{key}_absolute_path={value}")
    resolved_root = root.resolve()
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"{fixture}:{key}_outside_repo={value}") from exc
    if not resolved.exists():
        raise RuntimeError(f"{fixture}:missing_{key}={value}")
    return resolved


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

    required = ("visual_claim", *ARTIFACT_FIELDS, "docs")
    for name in promoted:
        fields = entries[name]
        for key in required:
            if key not in fields or not fields[key]:
                raise RuntimeError(f"{name}:missing_{key}")
        if fields["visual_claim"] != "1":
            raise RuntimeError(f"{name}:ledger_visual_claim={fields['visual_claim']}")
        for key in ARTIFACT_FIELDS:
            checked_in_path(root, fields[key], name, key)
        doc_path = checked_in_path(root, fields["docs"], name, "docs")
        try:
            doc_path.relative_to((root / "docs" / "recovery").resolve())
        except ValueError as exc:
            raise RuntimeError(f"{name}:docs_outside_recovery={fields['docs']}") from exc
    return 1


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="lezac-visual-claim-") as tmp:
        root = Path(tmp)
        fixture = "promoted_fixture.txt"
        write_text(root / "tests/fixtures/dosbox" / fixture, "visual_claim=1\n")
        write_text(root / "docs/recovery/note.md", "# Note\n")
        for artifact in (
            "docs/recovery/frames/original.ppm",
            "docs/recovery/frames/cpp.ppm",
            "docs/recovery/frames/diff.ppm",
        ):
            write_text(root / artifact, "P3\n1 1\n255\n0 0 0\n")
        write_text(
            root / LEDGER,
            "\n".join(
                (
                    "promotion_ledger=visual_claim",
                    "Current baseline mentions visual_claim=0.",
                    "- fixture=promoted_fixture.txt visual_claim=1 "
                    "original_frame=docs/recovery/frames/original.ppm "
                    "cpp_frame=docs/recovery/frames/cpp.ppm "
                    "comparison=docs/recovery/frames/diff.ppm "
                    "docs=docs/recovery/note.md",
                    "",
                )
            ),
        )
        fixtures, claim0, claim1, promoted = fixture_claims(root)
        if (fixtures, claim0, claim1, promoted) != (1, 0, 1, [fixture]):
            raise RuntimeError("selftest promoted fixture count mismatch")
        check_ledger(root, promoted)

        (root / "docs/recovery/frames/diff.ppm").unlink()
        try:
            check_ledger(root, promoted)
        except RuntimeError as exc:
            if "missing_comparison" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing artifact was not rejected")

        write_text(root / "docs/recovery/frames/diff.ppm", "P3\n1 1\n255\n0 0 0\n")
        write_text(
            root / LEDGER,
            "promotion_ledger=visual_claim\nvisual_claim=0\n"
            "- fixture=other.txt visual_claim=1 original_frame=docs/recovery/frames/original.ppm "
            "cpp_frame=docs/recovery/frames/cpp.ppm comparison=docs/recovery/frames/diff.ppm "
            "docs=docs/recovery/note.md\n",
        )
        try:
            check_ledger(root, promoted)
        except RuntimeError as exc:
            if "promoted fixture missing from ledger" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest mismatched ledger fixture was not rejected")

    print("visual_claim_guardrail_selftest=ok positive=1 missing_artifact=1 mismatch=1")
    return 0


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
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="exercise promoted-fixture ledger validation with temporary files",
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    if args.self_test:
        return self_test()

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
