#!/usr/bin/env python3
"""Write a visual-claim promotion candidate manifest."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

from plan_visual_claim_promotions import PROMOTION_KIND, VISUAL_CLAIM_LEDGER, display_path
from summarize_frame_compare_bundle import resolve_bundle
from write_visual_claim_promotion_entry import (
    repo_relative,
    require_existing,
    require_fixture_name,
)


@dataclass(frozen=True)
class Candidate:
    fixture: str
    bundle: Path
    docs: Path
    label: str | None


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def token(value: object) -> str:
    return re.sub(r"\s+", "_", str(value))


def resolve_arg(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def reject_spaces(value: str, field: str) -> None:
    if any(char.isspace() for char in value):
        raise RuntimeError(f"{field}_contains_whitespace={value!r}")


def parse_candidate(raw: list[str]) -> Candidate:
    if len(raw) not in (3, 4):
        raise RuntimeError(f"candidate_requires_3_or_4_values={len(raw)}")
    fixture, bundle, docs = raw[:3]
    label = raw[3] if len(raw) == 4 else None
    for field, value in (
        ("fixture", fixture),
        ("frame_compare_bundle", bundle),
        ("docs", docs),
        ("label", label or ""),
    ):
        if value:
            reject_spaces(value, field)
    if label in ("", "none"):
        label = None
    return Candidate(fixture=fixture, bundle=Path(bundle), docs=Path(docs), label=label)


def checked_candidate(root: Path, candidate: Candidate) -> Candidate:
    fixture = require_fixture_name(candidate.fixture)
    require_existing(root / "tests" / "fixtures" / "dosbox" / fixture, "fixture")

    bundle = resolve_bundle(resolve_arg(root, candidate.bundle).resolve())
    require_existing(bundle / "manifest.txt", "frame_compare_bundle_manifest")

    docs = require_existing(resolve_arg(root, candidate.docs).resolve(), "docs")
    try:
        docs.relative_to((root / "docs" / "recovery").resolve())
    except ValueError as exc:
        raise RuntimeError(f"docs_outside_recovery={candidate.docs.as_posix()}") from exc

    return Candidate(fixture=fixture, bundle=bundle, docs=docs, label=candidate.label)


def reject_real_ledger_output(root: Path, path: Path) -> None:
    if path.resolve() == (root / VISUAL_CLAIM_LEDGER).resolve():
        raise RuntimeError(
            f"refusing_to_overwrite_visual_claim_ledger={VISUAL_CLAIM_LEDGER.as_posix()}"
        )


def manifest_lines(root: Path, candidates: list[Candidate]) -> list[str]:
    lines = [
        f"promotion={PROMOTION_KIND}",
        f"candidates={len(candidates)}",
    ]
    for index, candidate in enumerate(candidates):
        prefix = f"candidate_{index}"
        lines.extend(
            [
                f"{prefix}_fixture={candidate.fixture}",
                f"{prefix}_frame_compare_bundle={repo_relative(root, candidate.bundle, 'frame_compare_bundle')}",
                f"{prefix}_docs={repo_relative(root, candidate.docs, 'docs')}",
            ]
        )
        if candidate.label:
            lines.append(f"{prefix}_label={candidate.label}")
    return lines


def write_manifest(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write a key/value manifest for plan_visual_claim_promotions.py."
    )
    parser.add_argument("out_manifest", type=Path)
    parser.add_argument(
        "--candidate",
        action="append",
        nargs="+",
        metavar="VALUE",
        help="candidate fixture, frame-compare bundle, docs note, and optional label",
    )
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    try:
        raw_candidates = args.candidate or []
        if not raw_candidates:
            raise RuntimeError("no_candidates")
        out_path = resolve_arg(root, args.out_manifest).resolve()
        reject_real_ledger_output(root, out_path)
        candidates = [checked_candidate(root, parse_candidate(raw)) for raw in raw_candidates]
        write_manifest(out_path, manifest_lines(root, candidates))
    except Exception as exc:
        print(f"visual_claim_promotion_manifest=error reason={token(exc)}", file=sys.stderr)
        return 2

    print(
        "visual_claim_promotion_manifest=ok "
        f"path={display_path(root, out_path)} "
        f"candidates={len(candidates)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
