#!/usr/bin/env python3
"""Shared fixture guardrails for ready-result summary tools."""

from __future__ import annotations

import os
from pathlib import Path


ORIGINAL_FIXTURE_DIR = Path("tests") / "fixtures" / "dosbox"
RUNTIME_EVIDENCE_LEDGER = Path("docs") / "recovery" / "runtime_evidence_ledger.md"
EXPECTED_RUNTIME_EVIDENCE_LEDGER_KIND = "non_visual"
SINGLETON_FIXTURE_FIELDS = {"runtime_cs", "runtime_ds", "temp_copy", "visual_claim"}


def repo_root() -> Path:
    override = os.environ.get("LEZAC_READY_RESULT_REPO_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parent.parent


def parse_runtime_segment_value(key: str, raw_segment: str) -> str:
    if len(raw_segment) != 4 or any(
        character not in "0123456789abcdefABCDEF" for character in raw_segment
    ):
        raise ValueError(
            f"{key} must be a 4-digit hexadecimal segment: {raw_segment!r}"
        )
    return raw_segment.upper()


def resolve_existing_fixture_path(fixture: str) -> Path | None:
    fixture_path = Path(fixture)
    if not fixture_path.is_absolute():
        fixture_path = Path.cwd() / fixture_path
    fixture_path = fixture_path.resolve()
    if not fixture_path.exists():
        return None
    return fixture_path


def read_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in SINGLETON_FIXTURE_FIELDS and key in values:
            raise ValueError(f"duplicate fixture field: {key} in {path}")
        values[key] = value
    return values


def is_checked_in_original_fixture(root: Path, fixture_path: Path) -> bool:
    fixture_dir = (root / ORIGINAL_FIXTURE_DIR).resolve()
    try:
        fixture_path.relative_to(fixture_dir)
    except ValueError:
        return False
    return "original" in fixture_path.name


def read_runtime_ledger_entries(root: Path) -> dict[str, dict[str, str]]:
    ledger = root / RUNTIME_EVIDENCE_LEDGER
    if not ledger.exists():
        raise ValueError(f"runtime evidence ledger missing: {ledger}")
    entries: dict[str, dict[str, str]] = {}
    ledger_kind: str | None = None
    declared_count: int | None = None
    in_fence = False
    for raw_line in ledger.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("runtime_evidence_ledger="):
            if ledger_kind is not None:
                raise ValueError("duplicate runtime_evidence_ledger")
            ledger_kind = stripped.split("=", 1)[1]
            if ledger_kind != EXPECTED_RUNTIME_EVIDENCE_LEDGER_KIND:
                raise ValueError(
                    f"runtime_evidence_ledger={ledger_kind!r}; expected "
                    f"{EXPECTED_RUNTIME_EVIDENCE_LEDGER_KIND!r}"
                )
            continue
        if stripped.startswith("original_runtime_fixture_count="):
            if declared_count is not None:
                raise ValueError("duplicate original_runtime_fixture_count")
            raw_count = stripped.split("=", 1)[1]
            try:
                declared_count = int(raw_count, 10)
            except ValueError as exc:
                raise ValueError(
                    f"invalid original_runtime_fixture_count: {raw_count!r}"
                ) from exc
            if declared_count < 0:
                raise ValueError("original_runtime_fixture_count must be non-negative")
            continue
        if not stripped.startswith("- fixture="):
            continue
        fields: dict[str, str] = {}
        for token in stripped[2:].split():
            key, separator, value = token.partition("=")
            if separator:
                if key in fields:
                    raise ValueError(f"duplicate runtime evidence ledger field: {key}")
                fields[key] = value
        fixture = fields.get("fixture")
        if fixture:
            if fixture in entries:
                raise ValueError(f"duplicate runtime evidence ledger fixture: {fixture}")
            entries[fixture] = fields
    if ledger_kind is None:
        raise ValueError("runtime evidence ledger missing runtime_evidence_ledger")
    if declared_count is None:
        raise ValueError("runtime evidence ledger missing original_runtime_fixture_count")
    if declared_count != len(entries):
        raise ValueError(
            "original_runtime_fixture_count="
            f"{declared_count} does not match ledger entries={len(entries)}"
        )
    return entries


def validate_original_fixture_docs(
    prefix: str, root: Path, fixture_name: str, docs: str | None
) -> None:
    if not docs:
        raise ValueError(f"{prefix}_fixture {fixture_name} ledger entry missing docs")
    docs_path = Path(docs)
    if docs_path.is_absolute():
        raise ValueError(f"{prefix}_fixture {fixture_name} ledger docs is absolute")
    resolved = (root / docs_path).resolve()
    try:
        resolved.relative_to((root / "docs").resolve())
    except ValueError as exc:
        raise ValueError(
            f"{prefix}_fixture {fixture_name} ledger docs is outside docs: {docs}"
        ) from exc
    if not resolved.exists():
        raise ValueError(
            f"{prefix}_fixture {fixture_name} ledger docs is missing: {docs}"
        )
    if fixture_name not in resolved.read_text(encoding="utf-8"):
        raise ValueError(
            f"{prefix}_fixture {fixture_name} ledger docs does not name fixture"
        )


def validate_original_fixture_ledger(prefix: str, fixture_path: Path) -> None:
    root = repo_root()
    if not is_checked_in_original_fixture(root, fixture_path):
        return
    fixture_name = fixture_path.name
    fields = read_runtime_ledger_entries(root).get(fixture_name)
    if fields is None:
        raise ValueError(
            f"{prefix}_fixture {fixture_name} is missing from runtime evidence ledger"
        )
    if fields.get("visual_claim") != "0":
        raise ValueError(
            f"{prefix}_fixture {fixture_name} ledger visual_claim="
            f"{fields.get('visual_claim')!r}; expected '0'"
        )
    if fields.get("evidence") != "runtime_cs_runtime_ds_temp_copy":
        raise ValueError(
            f"{prefix}_fixture {fixture_name} ledger evidence="
            f"{fields.get('evidence')!r}; expected "
            "'runtime_cs_runtime_ds_temp_copy'"
        )
    validate_original_fixture_docs(prefix, root, fixture_name, fields.get("docs"))


def validate_runtime_fixture_evidence(
    prefix: str, fixture: str, runtime_cs: str, runtime_ds: str
) -> None:
    fixture_path = resolve_existing_fixture_path(fixture)
    if fixture_path is None:
        return
    fixture_values = read_key_values(fixture_path)
    visual_claim = fixture_values.get("visual_claim")
    if visual_claim is not None and visual_claim != "0":
        raise ValueError(
            f"{prefix}_fixture visual_claim={visual_claim!r} is not supported "
            "for runtime ready results"
        )
    temp_copy = fixture_values.get("temp_copy")
    if temp_copy is not None and temp_copy != "1":
        raise ValueError(
            f"{prefix}_fixture temp_copy={temp_copy!r} does not identify "
            "a temp-copy capture"
        )
    for key, expected in (("runtime_cs", runtime_cs), ("runtime_ds", runtime_ds)):
        if key not in fixture_values:
            continue
        actual = parse_runtime_segment_value(key, fixture_values[key])
        if actual != expected:
            raise ValueError(
                f"{prefix}_{key}={expected!r} does not match fixture "
                f"{key}={actual!r} in {fixture_path}"
            )
    validate_original_fixture_ledger(prefix, fixture_path)
