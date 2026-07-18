#!/usr/bin/env python3
"""Require original DOSBox runtime fixtures to stay explicitly non-visual."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile


LEDGER = Path("docs/recovery/runtime_evidence_ledger.md")
SEGMENT_RE = re.compile(r"^[0-9A-Fa-f]{1,4}$")


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


def single_value(fixture: Path, key: str) -> str:
    prefix = f"{key}="
    values = [
        line.strip().split("=", 1)[1]
        for line in fixture.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith(prefix)
    ]
    if len(values) != 1:
        raise RuntimeError(f"{fixture.name}:{key}_count={len(values)}")
    return values[0]


def checked_in_doc_path(root: Path, value: str, fixture: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise RuntimeError(f"{fixture}:docs_absolute_path={value}")
    resolved_root = root.resolve()
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"{fixture}:docs_outside_repo={value}") from exc
    if not resolved.exists():
        raise RuntimeError(f"{fixture}:missing_docs={value}")
    try:
        resolved.relative_to((root / "docs").resolve())
    except ValueError as exc:
        raise RuntimeError(f"{fixture}:docs_not_under_docs={value}") from exc
    return resolved


def fixture_counts(root: Path) -> tuple[int, int, int, int, int, list[str]]:
    fixture_dir = root / "tests" / "fixtures" / "dosbox"
    fixtures = sorted(
        fixture
        for fixture in fixture_dir.glob("*.txt")
        if not fixture.name.endswith("-LIS.txt")
    )
    if not fixtures:
        raise RuntimeError(f"no fixtures found under {fixture_dir}")

    original = [fixture for fixture in fixtures if "original" in fixture.name]
    if not original:
        raise RuntimeError("no original runtime fixtures found")

    visual_claim0 = 0
    temp_copy = 0
    runtime_segments = 0
    names: list[str] = []
    for fixture in original:
        names.append(fixture.name)
        visual_claim = single_value(fixture, "visual_claim")
        if visual_claim != "0":
            raise RuntimeError(f"{fixture.name}:visual_claim={visual_claim}")
        visual_claim0 += 1

        temp = single_value(fixture, "temp_copy")
        if temp != "1":
            raise RuntimeError(f"{fixture.name}:temp_copy={temp}")
        temp_copy += 1

        cs = single_value(fixture, "runtime_cs")
        ds = single_value(fixture, "runtime_ds")
        if not SEGMENT_RE.match(cs) or not SEGMENT_RE.match(ds):
            raise RuntimeError(f"{fixture.name}:bad_runtime_segments={cs},{ds}")
        runtime_segments += 1

    return len(fixtures), len(original), visual_claim0, temp_copy, runtime_segments, names


def check_ledger(root: Path, original_names: list[str]) -> int:
    ledger_path = root / LEDGER
    text = ledger_path.read_text(encoding="utf-8")
    require(text, "runtime_evidence_ledger=non_visual", str(LEDGER))
    require(text, "visual_claim=0", str(LEDGER))
    require(text, f"original_runtime_fixture_count={len(original_names)}", str(LEDGER))

    entries: dict[str, dict[str, str]] = {}
    in_fence = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped.startswith("- fixture="):
            continue
        fields = parse_fields(stripped[2:])
        fixture = fields.get("fixture")
        if fixture:
            entries[fixture] = fields

    missing = [name for name in original_names if name not in entries]
    if missing:
        raise RuntimeError("original runtime fixture missing from ledger: " + ",".join(missing))

    extra = [name for name in entries if name not in original_names]
    if extra:
        raise RuntimeError("ledger entry without original runtime fixture: " + ",".join(extra))

    for name in original_names:
        fields = entries[name]
        if fields.get("visual_claim") != "0":
            raise RuntimeError(f"{name}:ledger_visual_claim={fields.get('visual_claim')}")
        if fields.get("evidence") != "runtime_cs_runtime_ds_temp_copy":
            raise RuntimeError(f"{name}:ledger_evidence={fields.get('evidence')}")
        docs = fields.get("docs")
        if not docs:
            raise RuntimeError(f"{name}:missing_docs")
        doc_path = checked_in_doc_path(root, docs, name)
        if doc_path.resolve() == ledger_path.resolve():
            raise RuntimeError(f"{name}:docs_points_to_ledger")
        doc_text = doc_path.read_text(encoding="utf-8")
        if name not in doc_text:
            raise RuntimeError(f"{name}:docs_missing_fixture_name={docs}")

    return 1


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="lezac-runtime-evidence-") as tmp:
        root = Path(tmp)
        fixture = "sample_original_runtime.txt"
        write_text(
            root / "tests/fixtures/dosbox" / fixture,
            "\n".join(
                (
                    "temp_copy=1",
                    "visual_claim=0",
                    "runtime_cs=01ED",
                    "runtime_ds=0C8F",
                    "",
                )
            ),
        )
        write_text(
            root / "docs/recovery/original_runtime_fixture_notes.md",
            f"# Runtime Notes\n\n{fixture} is named here as supporting evidence.\n",
        )
        write_text(
            root / LEDGER,
            "\n".join(
                (
                    "runtime_evidence_ledger=non_visual",
                    "original_runtime_fixture_count=1",
                    "visual_claim=0",
                    "- fixture=sample_original_runtime.txt visual_claim=0 "
                    "evidence=runtime_cs_runtime_ds_temp_copy "
                    "docs=docs/recovery/original_runtime_fixture_notes.md",
                    "",
                )
            ),
        )

        counts = fixture_counts(root)
        if counts != (1, 1, 1, 1, 1, [fixture]):
            raise RuntimeError(f"selftest fixture count mismatch: {counts!r}")
        check_ledger(root, [fixture])

        write_text(
            root / "docs/recovery/original_runtime_fixture_notes.md",
            "# Runtime Notes\n\nThis note omits the fixture filename.\n",
        )
        try:
            check_ledger(root, [fixture])
        except RuntimeError as exc:
            if "docs_missing_fixture_name" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing fixture doc was not rejected")

        write_text(
            root / "docs/recovery/original_runtime_fixture_notes.md",
            f"# Runtime Notes\n\n{fixture} is named here as supporting evidence.\n",
        )
        write_text(
            root / "tests/fixtures/dosbox" / fixture,
            "temp_copy=1\nvisual_claim=0\nruntime_cs=01EG\nruntime_ds=0C8F\n",
        )
        try:
            fixture_counts(root)
        except RuntimeError as exc:
            if "bad_runtime_segments" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest bad runtime segment was not rejected")

    print(
        "runtime_evidence_guardrail_selftest=ok "
        "positive=1 missing_fixture_doc=1 bad_segment=1"
    )
    return 0


def check_cmake(root: Path) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_runtime_evidence_guardrail.py", "cmake:script")
    require(cmake, "add_test(NAME runtime_evidence_guardrail", "cmake:test")
    require(cmake, "add_test(NAME runtime_evidence_guardrail_selftest", "cmake:selftest")
    require(cmake, "runtime_evidence_guardrail=ok", "cmake:output")
    return 1


def check_docs(root: Path) -> int:
    docs = (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    )
    for relative in docs:
        text = (root / relative).read_text(encoding="utf-8")
        require(text, "check_runtime_evidence_guardrail.py", relative)
        require(text, str(LEDGER).replace("\\", "/"), relative)
        require(text, "docs/recovery/original_runtime_fixture_notes.md", relative)
        require(text, "visual_claim=0", relative)
    return len(docs)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check original DOSBox runtime fixtures are explicit non-visual evidence."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="exercise fixture metadata and supporting-note validation",
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    root = args.root.resolve()
    fixtures, original, visual_claim0, temp_copy, runtime_segments, names = fixture_counts(root)
    ledger = check_ledger(root, names)
    ctest = check_cmake(root)
    docs = check_docs(root)
    print(
        "runtime_evidence_guardrail=ok "
        f"fixtures={fixtures} original_runtime={original} visual_claim0={visual_claim0} "
        f"temp_copy={temp_copy} runtime_segments={runtime_segments} "
        f"ledger={ledger} ctest={ctest} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
