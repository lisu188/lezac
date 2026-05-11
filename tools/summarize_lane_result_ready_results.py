#!/usr/bin/env python3
"""Summarize lane-result ready-manifest oracle result manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


EXPECTED_RESULT = "lane_result_ready_manifest"


@dataclass(frozen=True)
class ResultManifest:
    path: Path
    values: dict[str, str]


@dataclass(frozen=True)
class CandidateResult:
    index: int
    route: str
    offset_label: str
    offset_address: str
    oracle: str
    status: str
    returncode: str
    log: str
    command: str


def read_manifest(path: Path) -> ResultManifest:
    if path.is_dir():
        path = path / "result_manifest.txt"
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return ResultManifest(path=path, values=values)


def require(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if value is None or value == "":
        raise ValueError(f"missing required manifest field: {key}")
    return value


def parse_count(values: dict[str, str]) -> int:
    raw_count = require(values, "ready_candidates")
    try:
        count = int(raw_count, 10)
    except ValueError as exc:
        raise ValueError(f"invalid ready_candidates value: {raw_count!r}") from exc
    if count < 0:
        raise ValueError("ready_candidates must be non-negative")
    return count


def parse_failures(values: dict[str, str]) -> int:
    raw_failures = require(values, "failures")
    try:
        failures = int(raw_failures, 10)
    except ValueError as exc:
        raise ValueError(f"invalid failures value: {raw_failures!r}") from exc
    if failures < 0:
        raise ValueError("failures must be non-negative")
    return failures


def parse_candidates(values: dict[str, str]) -> list[CandidateResult]:
    result = require(values, "result")
    if result != EXPECTED_RESULT:
        raise ValueError(f"unsupported result {result!r}; expected {EXPECTED_RESULT!r}")
    candidates: list[CandidateResult] = []
    for index in range(parse_count(values)):
        prefix = f"candidate_{index}"
        candidates.append(
            CandidateResult(
                index=index,
                route=require(values, f"{prefix}_route"),
                offset_label=require(values, f"{prefix}_offset_label"),
                offset_address=require(values, f"{prefix}_offset_address"),
                oracle=require(values, f"{prefix}_oracle"),
                status=require(values, f"{prefix}_status"),
                returncode=require(values, f"{prefix}_returncode"),
                log=require(values, f"{prefix}_log"),
                command=require(values, f"{prefix}_command"),
            )
        )
    return candidates


def status_counts(candidates: list[CandidateResult]) -> dict[str, int]:
    counts = {"planned": 0, "ok": 0, "error": 0, "other": 0}
    for candidate in candidates:
        if candidate.status in counts:
            counts[candidate.status] += 1
        else:
            counts["other"] += 1
    return counts


def existing_log_count(candidates: list[CandidateResult]) -> tuple[int, int]:
    present = 0
    missing = 0
    for candidate in candidates:
        if candidate.log == "none":
            continue
        if Path(candidate.log).exists():
            present += 1
        else:
            missing += 1
    return present, missing


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize lane-result ready-manifest oracle results."
    )
    parser.add_argument("manifest", type=Path, help="result manifest or directory")
    parser.add_argument(
        "--require-success",
        action="store_true",
        help="exit nonzero if any oracle candidate failed",
    )
    parser.add_argument(
        "--require-executed",
        action="store_true",
        help="exit nonzero if any candidate is only planned/not-run",
    )
    args = parser.parse_args()

    try:
        manifest = read_manifest(args.manifest)
        mode = require(manifest.values, "mode")
        source_manifest = require(manifest.values, "source_ready_manifest")
        oracle_binary = require(manifest.values, "oracle_binary")
        failures = parse_failures(manifest.values)
        candidates = parse_candidates(manifest.values)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"lane_result_ready_result_summary=error reason={exc}", file=sys.stderr)
        return 1

    counts = status_counts(candidates)
    logs_present, logs_missing = existing_log_count(candidates)
    executed = len(candidates) - counts["planned"]
    print(
        "lane_result_ready_result_summary=ok "
        f"manifest={manifest.path} "
        f"mode={mode} "
        f"source_ready_manifest={source_manifest} "
        f"oracle_binary={oracle_binary} "
        f"ready_candidates={len(candidates)} "
        f"failures={failures} "
        f"planned={counts['planned']} "
        f"ok={counts['ok']} "
        f"error={counts['error']} "
        f"other={counts['other']} "
        f"executed_candidates={executed} "
        f"logs_present={logs_present} "
        f"logs_missing={logs_missing}"
    )
    for candidate in candidates:
        print(
            "candidate_result "
            f"index={candidate.index} "
            f"route={candidate.route} "
            f"offset={candidate.offset_label} "
            f"offset_address={candidate.offset_address} "
            f"oracle={candidate.oracle} "
            f"status={candidate.status} "
            f"returncode={candidate.returncode} "
            f"log={candidate.log} "
            f"command={candidate.command}"
        )

    if args.require_success and (failures != 0 or counts["error"] != 0):
        print(
            "lane_result_ready_result_summary=error "
            f"reason=oracle_failures failures={failures} error={counts['error']}",
            file=sys.stderr,
        )
        return 2
    if args.require_executed and counts["planned"] != 0:
        print(
            "lane_result_ready_result_summary=error "
            f"reason=candidates_not_executed planned={counts['planned']}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
