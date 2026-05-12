#!/usr/bin/env python3
"""Summarize a batch of DOSBox-debug capture helper outputs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import sys

from summarize_debug_capture import (
    CAPTURE_CONFIGS,
    CandidateReadiness,
    Manifest,
    candidate_readiness,
    csv_or_none,
    read_manifest,
    resolve_path,
)


@dataclass(frozen=True)
class CaptureSummary:
    manifest: Manifest
    candidate: Path | None
    readiness: CandidateReadiness
    oracle: str
    oracle_flag: str
    oracle_command: str


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def manifest_paths(root: Path) -> list[Path]:
    root = root.resolve()
    if root.is_file():
        return [root]
    if not root.exists():
        raise FileNotFoundError(f"batch root not found: {root}")
    return sorted(path for path in root.rglob("manifest.txt") if path.is_file())


def summarize_manifest(path: Path, oracle_binary: str) -> CaptureSummary | None:
    manifest = read_manifest(path)
    capture = manifest.values.get("capture", "unknown")
    if capture not in CAPTURE_CONFIGS:
        return None

    candidate = resolve_path(manifest.values.get("candidate_fixture"), manifest)
    readiness = candidate_readiness(capture, candidate)
    config = CAPTURE_CONFIGS[capture]
    oracle_command = "none"
    if candidate is not None:
        oracle_command = quote_command(
            [oracle_binary, config["flag"], str(candidate.resolve())]
        )
    return CaptureSummary(
        manifest=manifest,
        candidate=candidate,
        readiness=readiness,
        oracle=config["oracle"],
        oracle_flag=config["flag"],
        oracle_command=oracle_command,
    )


def display_path(path: Path | None) -> str:
    if path is None:
        return "none"
    return str(path.resolve())


def count_by_status(summaries: list[CaptureSummary]) -> dict[str, int]:
    counts = {"ready": 0, "incomplete": 0, "missing": 0, "none": 0}
    for summary in summaries:
        counts[summary.readiness.status] = counts.get(summary.readiness.status, 0) + 1
    return counts


def ready_manifest_lines(
    root: Path, oracle_binary: str, summaries: list[CaptureSummary]
) -> list[str]:
    ready = [summary for summary in summaries if summary.readiness.status == "ready"]
    lines = [
        "promotion=debug_capture_ready_candidates",
        f"source_root={root.resolve()}",
        f"oracle_binary={oracle_binary}",
        f"ready_candidates={len(ready)}",
    ]
    for index, summary in enumerate(ready):
        values = summary.manifest.values
        prefix = f"candidate_{index}"
        lines.extend(
            [
                f"{prefix}_capture={values.get('capture', 'unknown')}",
                f"{prefix}_scenario={values.get('scenario', 'unknown')}",
                f"{prefix}_level={values.get('expected_level', values.get('level', 'unknown'))}",
                f"{prefix}_environment_preflight={values.get('environment_preflight', 'unknown')}",
                f"{prefix}_runtime_metadata={values.get('runtime_metadata', 'unknown')}",
                f"{prefix}_runtime_cs={values.get('runtime_cs', 'unknown')}",
                f"{prefix}_runtime_ds={values.get('runtime_ds', 'unknown')}",
                f"{prefix}_manifest={summary.manifest.path}",
                f"{prefix}_fixture={display_path(summary.candidate)}",
                f"{prefix}_oracle={summary.oracle}",
                f"{prefix}_oracle_flag={summary.oracle_flag}",
                f"{prefix}_oracle_command={summary.oracle_command}",
            ]
        )
    return lines


def write_ready_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def print_summary(
    root: Path,
    all_manifests: list[Path],
    summaries: list[CaptureSummary],
    unsupported: int,
) -> None:
    counts = count_by_status(summaries)
    environment_ok = sum(
        1
        for summary in summaries
        if summary.manifest.values.get("environment_preflight") == "ok"
    )
    environment_not_ok = len(summaries) - environment_ok
    runtime_observed = sum(
        1
        for summary in summaries
        if summary.manifest.values.get("runtime_metadata") == "observed"
    )
    ready_manifests = [
        str(summary.manifest.path)
        for summary in summaries
        if summary.readiness.status == "ready"
    ]
    print(
        "debug_capture_batch_summary=ok "
        f"root={root.resolve()} "
        f"manifests={len(all_manifests)} "
        f"supported={len(summaries)} "
        f"unsupported={unsupported} "
        f"ready={counts.get('ready', 0)} "
        f"incomplete={counts.get('incomplete', 0)} "
        f"missing={counts.get('missing', 0)} "
        f"none={counts.get('none', 0)} "
        f"environment_ok={environment_ok} "
        f"environment_not_ok={environment_not_ok} "
        f"runtime_observed={runtime_observed} "
        f"oracle_commands={sum(1 for summary in summaries if summary.oracle_command != 'none')} "
        f"ready_manifests={csv_or_none(ready_manifests)}"
    )
    for index, summary in enumerate(summaries):
        values = summary.manifest.values
        print(
            "debug_capture_batch_candidate "
            f"index={index} "
            f"capture={values.get('capture', 'unknown')} "
            f"scenario={values.get('scenario', 'unknown')} "
            f"level={values.get('expected_level', values.get('level', 'unknown'))} "
            f"environment_preflight={values.get('environment_preflight', 'unknown')} "
            f"runtime_metadata={values.get('runtime_metadata', 'unknown')} "
            f"candidate_status={summary.readiness.status} "
            f"candidate_missing={csv_or_none(summary.readiness.missing)} "
            f"candidate_placeholders={1 if summary.readiness.placeholders else 0} "
            f"candidate_fixture={display_path(summary.candidate)} "
            f"oracle_flag={summary.oracle_flag} "
            f"oracle_command={summary.oracle_command} "
            f"manifest={summary.manifest.path}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize all supported DOSBox-debug captures below a directory."
    )
    parser.add_argument("root", type=Path, help="batch directory or manifest.txt")
    parser.add_argument(
        "--oracle-binary",
        default="./build/lezac_cpp",
        help="binary to use when printing oracle commands",
    )
    parser.add_argument(
        "--write-ready-manifest",
        type=Path,
        help="write a key/value manifest containing ready candidates only",
    )
    parser.add_argument(
        "--require-any-ready",
        action="store_true",
        help="exit nonzero unless at least one supported capture is ready",
    )
    parser.add_argument(
        "--require-environment-preflight",
        action="store_true",
        help="exit nonzero unless every supported capture records environment_preflight=ok",
    )
    args = parser.parse_args()

    try:
        paths = manifest_paths(args.root)
        summaries: list[CaptureSummary] = []
        unsupported = 0
        for path in paths:
            summary = summarize_manifest(path, args.oracle_binary)
            if summary is None:
                unsupported += 1
                continue
            summaries.append(summary)
    except Exception as exc:
        print(f"debug_capture_batch_summary=error reason={exc}", file=sys.stderr)
        return 1

    if not summaries:
        print(
            "debug_capture_batch_summary=error reason=no_supported_captures",
            file=sys.stderr,
        )
        return 1

    print_summary(args.root, paths, summaries, unsupported)

    if args.write_ready_manifest is not None:
        try:
            ready_manifest = write_ready_manifest(
                args.write_ready_manifest,
                ready_manifest_lines(args.root, args.oracle_binary, summaries),
            )
        except Exception as exc:
            print(f"debug_capture_ready_manifest=error reason={exc}", file=sys.stderr)
            return 1
        ready_count = count_by_status(summaries).get("ready", 0)
        print(
            "debug_capture_ready_manifest=ok "
            f"path={ready_manifest} ready_candidates={ready_count}"
        )

    counts = count_by_status(summaries)
    if args.require_any_ready and counts.get("ready", 0) == 0:
        print(
            "debug_capture_batch_summary=error reason=no_ready_candidates",
            file=sys.stderr,
        )
        return 2
    if args.require_environment_preflight:
        not_ok = [
            summary.manifest.path
            for summary in summaries
            if summary.manifest.values.get("environment_preflight") != "ok"
        ]
        if not_ok:
            print(
                "debug_capture_batch_summary=error "
                "reason=environment_preflight_not_ok "
                f"manifests={csv_or_none([str(path) for path in not_ok])}",
                file=sys.stderr,
            )
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
