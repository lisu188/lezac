#!/usr/bin/env python3
"""Summarize generic debug-capture ready-manifest oracle result manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import shlex
import sys


EXPECTED_RESULT = "debug_capture_ready_manifest"
ORACLE_FLAGS = {
    "behavior4": "--debug-behavior4-runtime-oracle",
    "actor_update": "--debug-actor-update-runtime-oracle",
    "contact_scanner": "--debug-contact-scanner-runtime-oracle",
    "visual_table": "--debug-visual-table-oracle",
}


@dataclass(frozen=True)
class ResultManifest:
    path: Path
    values: dict[str, str]


@dataclass(frozen=True)
class CandidateResult:
    index: int
    capture: str
    scenario: str
    level: str
    environment_preflight: str
    runtime_metadata: str
    runtime_cs: str
    runtime_ds: str
    fixture: str
    oracle: str
    oracle_flag: str
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


def parse_nonnegative_int(values: dict[str, str], key: str) -> int:
    raw_value = require(values, key)
    try:
        value = int(raw_value, 10)
    except ValueError as exc:
        raise ValueError(f"invalid {key} value: {raw_value!r}") from exc
    if value < 0:
        raise ValueError(f"{key} must be non-negative")
    return value


def parse_runtime_segment(values: dict[str, str], key: str) -> str:
    raw_segment = require(values, key)
    if len(raw_segment) != 4 or any(
        character not in "0123456789abcdefABCDEF" for character in raw_segment
    ):
        raise ValueError(
            f"{key} must be a 4-digit hexadecimal segment: {raw_segment!r}"
        )
    return raw_segment.upper()


def parse_oracle_flag(values: dict[str, str], prefix: str) -> tuple[str, str]:
    oracle = require(values, f"{prefix}_oracle")
    oracle_flag = require(values, f"{prefix}_oracle_flag")
    expected_flag = ORACLE_FLAGS.get(oracle)
    if expected_flag is None:
        raise ValueError(f"{prefix}_oracle has unsupported value: {oracle!r}")
    if oracle_flag != expected_flag:
        raise ValueError(
            f"{prefix}_oracle_flag={oracle_flag!r} does not match "
            f"{prefix}_oracle={oracle!r}; expected {expected_flag!r}"
        )
    return oracle, oracle_flag


def parse_command(
    values: dict[str, str], prefix: str, oracle_flag: str, fixture: str
) -> str:
    command = require(values, f"{prefix}_command")
    try:
        arguments = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"{prefix}_command is not parseable: {exc}") from exc
    expected_tail = [oracle_flag, fixture]
    if len(arguments) < len(expected_tail) or arguments[-2:] != expected_tail:
        actual_tail = arguments[-2:] if len(arguments) >= 2 else arguments
        raise ValueError(
            f"{prefix}_command does not end with oracle flag and fixture; "
            f"expected {expected_tail!r} got {actual_tail!r}"
        )
    return command


def candidate_indices(values: dict[str, str]) -> set[int]:
    indices: set[int] = set()
    for key in values:
        if not key.startswith("candidate_"):
            continue
        suffix = key[len("candidate_") :]
        index_text, separator, _ = suffix.partition("_")
        if not separator or not index_text.isdecimal():
            raise ValueError(f"invalid candidate field: {key}")
        indices.add(int(index_text, 10))
    return indices


def parse_candidates(values: dict[str, str]) -> list[CandidateResult]:
    result = require(values, "result")
    if result != EXPECTED_RESULT:
        raise ValueError(f"unsupported result {result!r}; expected {EXPECTED_RESULT!r}")
    count = parse_nonnegative_int(values, "ready_candidates")
    extras = sorted(index for index in candidate_indices(values) if index >= count)
    if extras:
        extra_text = ",".join(str(index) for index in extras)
        raise ValueError(
            "candidate index outside ready_candidates: "
            f"{extra_text} ready_candidates={count}"
        )
    candidates: list[CandidateResult] = []
    for index in range(count):
        prefix = f"candidate_{index}"
        oracle, oracle_flag = parse_oracle_flag(values, prefix)
        runtime_cs = parse_runtime_segment(values, f"{prefix}_runtime_cs")
        runtime_ds = parse_runtime_segment(values, f"{prefix}_runtime_ds")
        fixture = require(values, f"{prefix}_fixture")
        command = parse_command(values, prefix, oracle_flag, fixture)
        candidates.append(
            CandidateResult(
                index=index,
                capture=require(values, f"{prefix}_capture"),
                scenario=require(values, f"{prefix}_scenario"),
                level=require(values, f"{prefix}_level"),
                environment_preflight=require(
                    values, f"{prefix}_environment_preflight"
                ),
                runtime_metadata=require(values, f"{prefix}_runtime_metadata"),
                runtime_cs=runtime_cs,
                runtime_ds=runtime_ds,
                fixture=fixture,
                oracle=oracle,
                oracle_flag=oracle_flag,
                status=require(values, f"{prefix}_status"),
                returncode=require(values, f"{prefix}_returncode"),
                log=require(values, f"{prefix}_log"),
                command=command,
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


def returncode_expectation(candidate: CandidateResult) -> str | None:
    if candidate.status == "planned":
        return "not_run" if candidate.returncode != "not_run" else None
    if candidate.status == "ok":
        return "0" if candidate.returncode != "0" else None
    if candidate.status == "error":
        try:
            returncode = int(candidate.returncode, 10)
        except ValueError:
            return "positive_integer"
        return "positive_integer" if returncode <= 0 else None
    return None


def mode_status_error(mode: str, counts: dict[str, int], candidate_count: int) -> str | None:
    if mode == "run":
        if counts["planned"] != 0:
            return f"mode=run planned={counts['planned']} expected_planned=0"
        return None
    if mode == "dry_run":
        nonplanned = candidate_count - counts["planned"]
        if nonplanned != 0:
            return f"mode=dry_run nonplanned={nonplanned} expected_nonplanned=0"
        return None
    return f"unsupported_mode={mode} expected=run,dry_run"


def environment_counts(candidates: list[CandidateResult]) -> tuple[int, int]:
    ok = 0
    not_ok = 0
    for candidate in candidates:
        if candidate.environment_preflight == "ok":
            ok += 1
        else:
            not_ok += 1
    return ok, not_ok


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
        description="Summarize debug-capture ready-manifest oracle results."
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
    parser.add_argument(
        "--require-source-environment-preflight",
        action="store_true",
        help="exit nonzero unless every candidate has environment_preflight=ok",
    )
    args = parser.parse_args()

    try:
        manifest = read_manifest(args.manifest)
        mode = require(manifest.values, "mode")
        source_manifest = require(manifest.values, "source_ready_manifest")
        source_root = manifest.values.get("source_root", "unknown")
        oracle_binary = require(manifest.values, "oracle_binary")
        failures = parse_nonnegative_int(manifest.values, "failures")
        candidates = parse_candidates(manifest.values)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"debug_capture_ready_result_summary=error reason={exc}", file=sys.stderr)
        return 1

    counts = status_counts(candidates)
    if failures != counts["error"]:
        print(
            "debug_capture_ready_result_summary=error "
            "reason=failure_count_mismatch "
            f"failures={failures} error={counts['error']}",
            file=sys.stderr,
        )
        return 1
    mode_error = mode_status_error(mode, counts, len(candidates))
    if mode_error is not None:
        print(
            "debug_capture_ready_result_summary=error "
            f"reason=mode_status_mismatch {mode_error}",
            file=sys.stderr,
        )
        return 1
    for candidate in candidates:
        expected_returncode = returncode_expectation(candidate)
        if expected_returncode is not None:
            print(
                "debug_capture_ready_result_summary=error "
                "reason=status_returncode_mismatch "
                f"index={candidate.index} status={candidate.status} "
                f"returncode={candidate.returncode} expected={expected_returncode}",
                file=sys.stderr,
            )
            return 1
    env_ok, env_not_ok = environment_counts(candidates)
    logs_present, logs_missing = existing_log_count(candidates)
    executed = len(candidates) - counts["planned"]
    print(
        "debug_capture_ready_result_summary=ok "
        f"manifest={manifest.path} "
        f"mode={mode} "
        f"source_ready_manifest={source_manifest} "
        f"source_root={source_root} "
        f"oracle_binary={oracle_binary} "
        f"ready_candidates={len(candidates)} "
        f"failures={failures} "
        f"planned={counts['planned']} "
        f"ok={counts['ok']} "
        f"error={counts['error']} "
        f"other={counts['other']} "
        f"executed_candidates={executed} "
        f"environment_preflight_ok={env_ok} "
        f"environment_preflight_not_ok={env_not_ok} "
        f"logs_present={logs_present} "
        f"logs_missing={logs_missing}"
    )
    for candidate in candidates:
        print(
            "candidate_result "
            f"index={candidate.index} "
            f"capture={candidate.capture} "
            f"scenario={candidate.scenario} "
            f"level={candidate.level} "
            f"environment_preflight={candidate.environment_preflight} "
            f"runtime_metadata={candidate.runtime_metadata} "
            f"runtime_cs={candidate.runtime_cs} "
            f"runtime_ds={candidate.runtime_ds} "
            f"fixture={candidate.fixture} "
            f"oracle={candidate.oracle} "
            f"oracle_flag={candidate.oracle_flag} "
            f"status={candidate.status} "
            f"returncode={candidate.returncode} "
            f"log={candidate.log} "
            f"command={candidate.command}"
        )

    if (
        args.require_success
        and (failures != 0 or counts["error"] != 0 or counts["other"] != 0)
    ):
        print(
            "debug_capture_ready_result_summary=error "
            "reason=oracle_failures "
            f"failures={failures} error={counts['error']} other={counts['other']}",
            file=sys.stderr,
        )
        return 2
    if args.require_executed and counts["planned"] != 0:
        print(
            "debug_capture_ready_result_summary=error "
            f"reason=candidates_not_executed planned={counts['planned']}",
            file=sys.stderr,
        )
        return 3
    if args.require_source_environment_preflight and env_not_ok != 0:
        print(
            "debug_capture_ready_result_summary=error "
            "reason=source_environment_preflight_not_ok "
            f"environment_preflight_not_ok={env_not_ok}",
            file=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
