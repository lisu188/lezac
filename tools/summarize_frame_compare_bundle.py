#!/usr/bin/env python3
"""Summarize an original-vs-C++ frame comparison bundle."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


KEY_VALUE_RE = re.compile(r"^(?P<key>[A-Za-z0-9_]+)=(?P<value>.*)$")
COMPARE_LABEL_RE = re.compile(r"^compare label=(?P<label>\S+) (?P<body>.*)$")


@dataclass(frozen=True)
class Manifest:
    path: Path
    values: dict[str, str]


@dataclass(frozen=True)
class Summary:
    bundle: Path
    scenario: str
    original_capture_exit: str
    compare_exit: str
    cpp_frames: int
    original_frames: int
    diff_frames: int
    compared: int
    missing_original: int
    compare_errors: int
    exact_matches: int
    max_exact_different_pixels: int
    max_mean_abs_delta: str
    environment_preflight: str
    environment_preflight_exit: str
    wsl_bash_reason: str
    promotion_ready: bool
    reason: str


def read_key_values(path: Path) -> Manifest:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = KEY_VALUE_RE.match(line.strip())
        if match:
            values[match.group("key")] = match.group("value")
    return Manifest(path=path, values=values)


def resolve_bundle(path: Path) -> Path:
    path = path.resolve()
    if path.is_dir():
        return path
    if path.name == "manifest.txt":
        return path.parent
    raise ValueError(f"expected frame compare bundle directory or manifest.txt: {path}")


def resolve_manifest_path(bundle: Path, raw: str | None, fallback: str) -> Path:
    if not raw:
        return bundle / fallback
    path = Path(raw)
    if path.is_absolute():
        return path
    return bundle / path


def count_frames(path: Path, patterns: list[str]) -> int:
    if not path.exists() or not path.is_dir():
        return 0
    total = 0
    for pattern in patterns:
        total += sum(1 for _ in path.glob(pattern))
    return total


def parse_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in text.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields[key] = value
    return fields


def parse_summary(path: Path) -> tuple[int, int, int, int, int, str]:
    if not path.exists():
        return 0, 0, 0, 0, 0, "0.000000"
    compared = 0
    missing_original = 0
    compare_errors = 0
    exact_matches = 0
    max_exact_different_pixels = 0
    max_mean_abs_delta = 0.0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        match = COMPARE_LABEL_RE.match(line)
        if not match:
            continue
        fields = parse_fields(match.group("body"))
        if fields.get("status") == "missing_original":
            missing_original += 1
            continue
        if fields.get("frame_compare") == "error":
            compare_errors += 1
            continue
        if fields.get("frame_compare") == "ok":
            compared += 1
            if fields.get("exact_match") == "1":
                exact_matches += 1
            try:
                max_exact_different_pixels = max(
                    max_exact_different_pixels,
                    int(fields.get("exact_different_pixels", "0")),
                )
            except ValueError:
                compare_errors += 1
            try:
                max_mean_abs_delta = max(
                    max_mean_abs_delta,
                    float(fields.get("mean_abs_delta", "0.0")),
                )
            except ValueError:
                compare_errors += 1
    return (
        compared,
        missing_original,
        compare_errors,
        exact_matches,
        max_exact_different_pixels,
        f"{max_mean_abs_delta:.6f}",
    )


def first_preflight_reason(path: Path) -> str:
    if not path.exists():
        return "unknown"
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"\bwsl_bash_reason=([^ \r\n]+)", text)
    if match:
        return match.group(1)
    match = re.search(r"\breason=([^ \r\n]+)", text)
    if match:
        return match.group(1)
    return "none"


def promotion_block_reason(
    original_capture_exit: str,
    compare_exit: str,
    missing_original: int,
    compare_errors: int,
    compared: int,
) -> str:
    if original_capture_exit != "0":
        return f"original_capture_exit_{original_capture_exit}"
    if compare_exit != "0":
        return f"compare_exit_{compare_exit}"
    if missing_original:
        return "missing_original"
    if compare_errors:
        return "compare_errors"
    if compared == 0:
        return "no_compared_frames"
    return "none"


def summarize(path: Path) -> Summary:
    bundle = resolve_bundle(path)
    manifest = read_key_values(bundle / "manifest.txt")
    summary_path = resolve_manifest_path(bundle, manifest.values.get("summary"), "frame_compare_summary.txt")
    original_manifest_path = resolve_manifest_path(
        bundle, manifest.values.get("original_capture_manifest"), "original/manifest.txt"
    )
    original_preflight_log = resolve_manifest_path(
        bundle,
        manifest.values.get("original_environment_preflight_log"),
        "original/environment_preflight.log",
    )
    original_manifest = (
        read_key_values(original_manifest_path)
        if original_manifest_path.exists()
        else Manifest(path=original_manifest_path, values={})
    )

    compared, missing_original, compare_errors, exact_matches, max_diff, max_mean = (
        parse_summary(summary_path)
    )
    original_capture_exit = manifest.values.get("original_capture_exit", "unknown")
    compare_exit = manifest.values.get("compare_exit", "unknown")
    reason = promotion_block_reason(
        original_capture_exit,
        compare_exit,
        missing_original,
        compare_errors,
        compared,
    )
    return Summary(
        bundle=bundle,
        scenario=manifest.values.get("scenario", "unknown"),
        original_capture_exit=original_capture_exit,
        compare_exit=compare_exit,
        cpp_frames=count_frames(resolve_manifest_path(bundle, manifest.values.get("cpp_dir"), "cpp"), ["*.ppm"]),
        original_frames=count_frames(
            resolve_manifest_path(bundle, manifest.values.get("original_dir"), "original"),
            ["*.png", "*.bmp"],
        ),
        diff_frames=count_frames(resolve_manifest_path(bundle, manifest.values.get("diff_dir"), "diff"), ["*.ppm"]),
        compared=compared,
        missing_original=missing_original,
        compare_errors=compare_errors,
        exact_matches=exact_matches,
        max_exact_different_pixels=max_diff,
        max_mean_abs_delta=max_mean,
        environment_preflight=original_manifest.values.get("environment_preflight", "unknown"),
        environment_preflight_exit=original_manifest.values.get(
            "environment_preflight_exit", "unknown"
        ),
        wsl_bash_reason=first_preflight_reason(original_preflight_log),
        promotion_ready=reason == "none",
        reason=reason,
    )


def print_summary(summary: Summary) -> None:
    print(
        "frame_compare_bundle_summary=ok "
        f"bundle={summary.bundle} "
        f"scenario={summary.scenario} "
        f"original_capture_exit={summary.original_capture_exit} "
        f"compare_exit={summary.compare_exit} "
        f"cpp_frames={summary.cpp_frames} "
        f"original_frames={summary.original_frames} "
        f"diff_frames={summary.diff_frames} "
        f"compared={summary.compared} "
        f"missing_original={summary.missing_original} "
        f"compare_errors={summary.compare_errors} "
        f"exact_matches={summary.exact_matches} "
        f"max_exact_different_pixels={summary.max_exact_different_pixels} "
        f"max_mean_abs_delta={summary.max_mean_abs_delta} "
        f"environment_preflight={summary.environment_preflight} "
        f"environment_preflight_exit={summary.environment_preflight_exit} "
        f"wsl_bash_reason={summary.wsl_bash_reason} "
        f"promotion_ready={1 if summary.promotion_ready else 0} "
        f"reason={summary.reason}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize a frame comparison bundle produced by compare_original_cpp_frames.sh."
    )
    parser.add_argument("bundle", type=Path, help="bundle directory or manifest.txt")
    parser.add_argument(
        "--require-promotion-ready",
        action="store_true",
        help="exit nonzero unless original capture and all paired comparisons are complete",
    )
    args = parser.parse_args()

    try:
        summary = summarize(args.bundle)
    except Exception as exc:
        print(f"frame_compare_bundle_summary=error reason={exc}", file=sys.stderr)
        return 2

    print_summary(summary)
    if args.require_promotion_ready and not summary.promotion_ready:
        print(
            "frame_compare_bundle_summary=error "
            f"reason=not_promotion_ready block={summary.reason}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
