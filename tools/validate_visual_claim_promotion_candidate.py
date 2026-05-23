#!/usr/bin/env python3
"""Dry-run a visual-claim promotion before editing the real ledger."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from check_visual_claim_guardrail import (
    ARTIFACT_FIELDS,
    BUNDLE_FIELD,
    checked_in_path,
    check_frame_compare_bundle,
    parse_fields,
)
from summarize_frame_compare_bundle import summarize
from write_visual_claim_promotion_entry import make_entry, require_fixture_name


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_arg(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def fixture_visual_claim(root: Path, fixture: str) -> str:
    fixture = require_fixture_name(fixture)
    fixture_path = root / "tests" / "fixtures" / "dosbox" / fixture
    if not fixture_path.exists():
        raise RuntimeError(f"missing_fixture={fixture_path}")

    values: list[str] = []
    for line in fixture_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("visual_claim="):
            values.append(stripped.split("=", 1)[1])

    if len(values) != 1:
        raise RuntimeError(f"{fixture}:visual_claim_count={len(values)}")
    if values[0] not in {"0", "1"}:
        raise RuntimeError(f"{fixture}:visual_claim={values[0]}")
    return values[0]


def validate_generated_entry(root: Path, fixture: str, entry: str) -> None:
    stripped = entry.strip()
    if not stripped.startswith("- fixture="):
        raise RuntimeError("entry_missing_fixture_prefix")

    fields = parse_fields(stripped[2:])
    required = ("fixture", "visual_claim", *ARTIFACT_FIELDS, BUNDLE_FIELD, "docs")
    for key in required:
        if key not in fields or not fields[key]:
            raise RuntimeError(f"{fixture}:missing_{key}")

    if fields["fixture"] != fixture:
        raise RuntimeError(f"{fixture}:entry_fixture={fields['fixture']}")
    if fields["visual_claim"] != "1":
        raise RuntimeError(f"{fixture}:entry_visual_claim={fields['visual_claim']}")

    for key in ARTIFACT_FIELDS:
        checked_in_path(root, fields[key], fixture, key)

    check_frame_compare_bundle(root, fields[BUNDLE_FIELD], fixture)

    docs = checked_in_path(root, fields["docs"], fixture, "docs")
    try:
        docs.relative_to((root / "docs" / "recovery").resolve())
    except ValueError as exc:
        raise RuntimeError(f"{fixture}:docs_outside_recovery={fields['docs']}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check that a fixture, frame bundle, and docs note can form a valid "
            "visual_claim=1 promotion ledger entry without editing the ledger."
        )
    )
    parser.add_argument("fixture", help="checked-in DOSBox fixture filename")
    parser.add_argument("frame_compare_bundle", type=Path, help="checked-in frame-compare bundle")
    parser.add_argument("docs", type=Path, help="supporting recovery note under docs/recovery")
    parser.add_argument("--label", help="semantic frame label to use; defaults to the first ready label")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    try:
        current_claim = fixture_visual_claim(root, args.fixture)
        summary = summarize(resolve_arg(root, args.frame_compare_bundle).resolve())
        if not summary.promotion_ready:
            raise RuntimeError(
                f"frame_compare_bundle_not_ready={summary.bundle} reason={summary.reason}"
            )
        label, entry = make_entry(
            root,
            args.fixture,
            args.frame_compare_bundle,
            args.docs,
            args.label,
        )
        validate_generated_entry(root, args.fixture, entry)
    except Exception as exc:
        print(f"visual_claim_promotion_candidate=error reason={exc}", file=sys.stderr)
        return 2

    print(
        "visual_claim_promotion_candidate=ok "
        f"fixture={args.fixture} "
        f"label={label} "
        f"fixture_current_visual_claim={current_claim} "
        "promotion_ready=1 "
        "entry_valid=1 "
        f"compared={summary.compared} "
        f"exact_matches={summary.exact_matches}"
    )
    print(entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
