#!/usr/bin/env python3
"""Emit a visual-claim promotion ledger entry from a ready frame bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from summarize_frame_compare_bundle import (
    COMPARE_LABEL_RE,
    parse_fields,
    read_key_values,
    resolve_bundle,
    resolve_manifest_path,
    summarize,
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def repo_relative(root: Path, path: Path, field: str) -> str:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        relative = resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise RuntimeError(f"{field}_outside_repo={path}") from exc
    return relative.as_posix()


def require_existing(path: Path, field: str) -> Path:
    if not path.exists():
        raise RuntimeError(f"missing_{field}={path}")
    return path


def require_fixture_name(name: str) -> str:
    path = Path(name)
    if path.name != name or not name.endswith(".txt"):
        raise RuntimeError(f"bad_fixture_name={name}")
    return name


def compared_labels(summary_path: Path) -> list[str]:
    labels: list[str] = []
    if not summary_path.exists():
        return labels
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        match = COMPARE_LABEL_RE.match(line.strip())
        if not match:
            continue
        fields = parse_fields(match.group("body"))
        if fields.get("frame_compare") == "ok":
            labels.append(match.group("label"))
    return labels


def find_original_frame(original_dir: Path, label: str) -> Path | None:
    for extension in ("png", "bmp"):
        candidate = original_dir / f"{label}.{extension}"
        if candidate.exists():
            return candidate
    return None


def frame_artifacts(bundle: Path, label: str | None) -> tuple[str, Path, Path, Path]:
    manifest = read_key_values(bundle / "manifest.txt")
    summary_path = resolve_manifest_path(bundle, manifest.values.get("summary"), "frame_compare_summary.txt")
    cpp_dir = resolve_manifest_path(bundle, manifest.values.get("cpp_dir"), "cpp")
    original_dir = resolve_manifest_path(bundle, manifest.values.get("original_dir"), "original")
    diff_dir = resolve_manifest_path(bundle, manifest.values.get("diff_dir"), "diff")

    candidate_labels = [label] if label is not None else compared_labels(summary_path)
    if not candidate_labels:
        raise RuntimeError("no_compared_frame_labels")

    missing: list[str] = []
    for candidate_label in candidate_labels:
        cpp_frame = cpp_dir / f"{candidate_label}.ppm"
        original_frame = find_original_frame(original_dir, candidate_label)
        comparison = diff_dir / f"{candidate_label}.ppm"
        if cpp_frame.exists() and original_frame is not None and comparison.exists():
            return candidate_label, original_frame, cpp_frame, comparison
        missing.append(candidate_label)

    if label is not None:
        raise RuntimeError(f"missing_artifact_for_label={label}")
    raise RuntimeError("no_compared_label_with_artifacts=" + ",".join(missing))


def make_entry(root: Path, fixture: str, bundle_arg: Path, docs_arg: Path, label: str | None) -> tuple[str, str]:
    fixture = require_fixture_name(fixture)
    require_existing(root / "tests" / "fixtures" / "dosbox" / fixture, "fixture")
    docs_path = require_existing((root / docs_arg).resolve() if not docs_arg.is_absolute() else docs_arg, "docs")
    try:
        docs_path.resolve().relative_to((root / "docs" / "recovery").resolve())
    except ValueError as exc:
        raise RuntimeError(f"docs_outside_recovery={docs_arg}") from exc

    bundle = resolve_bundle((root / bundle_arg).resolve() if not bundle_arg.is_absolute() else bundle_arg)
    require_existing(bundle / "manifest.txt", "frame_compare_bundle_manifest")
    summary = summarize(bundle)
    if not summary.promotion_ready:
        raise RuntimeError(f"frame_compare_bundle_not_ready={bundle} reason={summary.reason}")

    selected_label, original_frame, cpp_frame, comparison = frame_artifacts(bundle, label)
    entry = (
        f"- fixture={fixture} visual_claim=1 "
        f"original_frame={repo_relative(root, original_frame, 'original_frame')} "
        f"cpp_frame={repo_relative(root, cpp_frame, 'cpp_frame')} "
        f"comparison={repo_relative(root, comparison, 'comparison')} "
        f"frame_compare_bundle={repo_relative(root, bundle, 'frame_compare_bundle')} "
        f"docs={repo_relative(root, docs_path, 'docs')}"
    )
    return selected_label, entry


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print a visual_claim=1 ledger entry for a promotion-ready frame bundle."
    )
    parser.add_argument("fixture", help="checked-in DOSBox fixture filename")
    parser.add_argument("frame_compare_bundle", type=Path, help="checked-in frame-compare bundle")
    parser.add_argument("docs", type=Path, help="supporting recovery note under docs/recovery")
    parser.add_argument("--label", help="semantic frame label to use; defaults to the first ready label with artifacts")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.repo_root.resolve()
    try:
        label, entry = make_entry(
            root,
            args.fixture,
            args.frame_compare_bundle,
            args.docs,
            args.label,
        )
    except Exception as exc:
        print(f"visual_claim_promotion_entry=error reason={exc}", file=sys.stderr)
        return 2

    print(
        "visual_claim_promotion_entry=ok "
        f"fixture={args.fixture} label={label} promotion_ready=1"
    )
    print(entry)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
