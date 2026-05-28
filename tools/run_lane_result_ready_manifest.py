#!/usr/bin/env python3
"""Run or dry-run lane-result ready-candidate oracle manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import sys

from ready_result_fixture_guardrails import (
    parse_runtime_segment_value,
    validate_runtime_fixture_evidence,
)


EXPECTED_PROMOTION = "lane_result_ready_candidates"
EXPECTED_ORACLE = "explosion_playback"
EXPECTED_ORACLE_FLAG = "--debug-explosion-playback-oracle"
TOOL_PREFIX = "lane_result"


@dataclass(frozen=True)
class ReadyManifest:
    path: Path
    values: dict[str, str]


@dataclass(frozen=True)
class ReadyCandidate:
    index: int
    route: str
    offset_label: str
    offset_address: str
    runtime_cs: str
    runtime_ds: str
    fixture: Path
    oracle: str
    oracle_flag: str


def read_manifest(path: Path) -> ReadyManifest:
    if path.is_dir():
        path = path / "manifest.txt"
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"duplicate manifest field: {key}")
        values[key] = value
    return ReadyManifest(path=path, values=values)


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def require_output_outside_repo(path: Path, label: str, allow_repo_output: bool) -> None:
    if allow_repo_output:
        return
    if is_within(path, repo_root()):
        raise ValueError(f"{label} must be outside the repository")


def require(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if value is None or value == "":
        raise ValueError(f"missing required manifest field: {key}")
    return value


def parse_ready_count(values: dict[str, str]) -> int:
    raw_count = require(values, "ready_candidates")
    try:
        count = int(raw_count, 10)
    except ValueError as exc:
        raise ValueError(f"invalid ready_candidates value: {raw_count!r}") from exc
    if count < 0:
        raise ValueError("ready_candidates must be non-negative")
    return count


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


def resolve_fixture(raw_fixture: str, manifest_path: Path) -> Path:
    path = Path(raw_fixture)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def parse_candidates(
    values: dict[str, str],
    manifest_path: Path,
    require_fixtures: bool,
) -> list[ReadyCandidate]:
    promotion = require(values, "promotion")
    if promotion != EXPECTED_PROMOTION:
        raise ValueError(
            f"unsupported promotion {promotion!r}; expected {EXPECTED_PROMOTION!r}"
        )
    count = parse_ready_count(values)
    extras = sorted(index for index in candidate_indices(values) if index >= count)
    if extras:
        extra_text = ",".join(str(index) for index in extras)
        raise ValueError(
            "candidate index outside ready_candidates: "
            f"{extra_text} ready_candidates={count}"
        )
    candidates: list[ReadyCandidate] = []
    for index in range(count):
        prefix = f"candidate_{index}"
        fixture = resolve_fixture(require(values, f"{prefix}_fixture"), manifest_path)
        oracle = require(values, f"{prefix}_oracle")
        oracle_flag = require(values, f"{prefix}_oracle_flag")
        if oracle != EXPECTED_ORACLE:
            raise ValueError(
                f"{prefix}_oracle has unsupported value: {oracle!r}; "
                f"expected {EXPECTED_ORACLE!r}"
            )
        if oracle_flag != EXPECTED_ORACLE_FLAG:
            raise ValueError(
                f"{prefix}_oracle_flag={oracle_flag!r} does not match "
                f"{prefix}_oracle={oracle!r}; expected {EXPECTED_ORACLE_FLAG!r}"
            )
        if require_fixtures and not fixture.exists():
            raise FileNotFoundError(f"candidate fixture not found: {fixture}")
        runtime_cs = parse_runtime_segment_value(
            f"{prefix}_runtime_cs", require(values, f"{prefix}_runtime_cs")
        )
        runtime_ds = parse_runtime_segment_value(
            f"{prefix}_runtime_ds", require(values, f"{prefix}_runtime_ds")
        )
        validate_runtime_fixture_evidence(
            prefix, str(fixture), runtime_cs, runtime_ds
        )
        candidates.append(
            ReadyCandidate(
                index=index,
                route=require(values, f"{prefix}_route"),
                offset_label=require(values, f"{prefix}_offset_label"),
                offset_address=require(values, f"{prefix}_offset_address"),
                runtime_cs=runtime_cs,
                runtime_ds=runtime_ds,
                fixture=fixture,
                oracle=oracle,
                oracle_flag=oracle_flag,
            )
        )
    return candidates


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def command_for_candidate(binary: str, candidate: ReadyCandidate) -> list[str]:
    return [binary, candidate.oracle_flag, str(candidate.fixture)]


def log_name(candidate: ReadyCandidate) -> str:
    safe_route = "".join(
        ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in candidate.route
    )
    return f"candidate_{candidate.index}_{candidate.offset_label}_{safe_route}.log"


def write_log(log_dir: Path | None, candidate: ReadyCandidate, output: str) -> str:
    if log_dir is None:
        return "none"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / log_name(candidate)
    log_path.write_text(output, encoding="utf-8")
    return str(log_path)


def candidate_result_lines(
    candidate: ReadyCandidate,
    command: list[str],
    status: str,
    returncode: str,
    log_path: str,
) -> list[str]:
    prefix = f"candidate_{candidate.index}"
    return [
        f"{prefix}_route={candidate.route}",
        f"{prefix}_offset_label={candidate.offset_label}",
        f"{prefix}_offset_address={candidate.offset_address}",
        f"{prefix}_runtime_cs={candidate.runtime_cs}",
        f"{prefix}_runtime_ds={candidate.runtime_ds}",
        f"{prefix}_fixture={candidate.fixture}",
        f"{prefix}_oracle={candidate.oracle}",
        f"{prefix}_oracle_flag={candidate.oracle_flag}",
        f"{prefix}_status={status}",
        f"{prefix}_returncode={returncode}",
        f"{prefix}_log={log_path}",
        f"{prefix}_command={quote_command(command)}",
    ]


def write_result_manifest(
    path: Path,
    mode: str,
    source_manifest: Path,
    source_environment_preflight: str,
    oracle_binary: str,
    candidate_count: int,
    failures: int,
    candidate_lines: list[str],
) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"result={TOOL_PREFIX}_ready_manifest",
        f"mode={mode}",
        f"source_ready_manifest={source_manifest}",
        f"source_environment_preflight={source_environment_preflight}",
        f"oracle_binary={oracle_binary}",
        f"ready_candidates={candidate_count}",
        f"failures={failures}",
        *candidate_lines,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def run_candidate(
    command: list[str],
    candidate: ReadyCandidate,
    timeout_seconds: float,
    log_dir: Path | None,
) -> tuple[int, str, str]:
    env = os.environ.copy()
    env.setdefault("SDL_VIDEODRIVER", "dummy")
    env.setdefault("SDL_AUDIODRIVER", "dummy")
    try:
        result = subprocess.run(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
            env=env,
        )
        output = result.stdout
        return result.returncode, output, write_log(log_dir, candidate, output)
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output += f"\ncommand timed out after {timeout_seconds:.1f}s\n"
        return 124, output, write_log(log_dir, candidate, output)
    except OSError as exc:
        output = f"{exc}\n"
        return 127, output, write_log(log_dir, candidate, output)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run oracle commands from a lane-result ready manifest."
    )
    parser.add_argument("manifest", type=Path, help="ready promotion manifest")
    parser.add_argument("--dry-run", action="store_true", help="print commands only")
    parser.add_argument(
        "--oracle-binary",
        help="override the oracle binary recorded in the manifest",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="per-candidate oracle timeout for live runs",
    )
    parser.add_argument(
        "--allow-missing-fixtures",
        action="store_true",
        help="allow dry-run review when candidate fixture paths are unavailable",
    )
    parser.add_argument("--log-dir", type=Path, help="write oracle output logs")
    parser.add_argument(
        "--write-result-manifest",
        type=Path,
        help="write a key/value manifest describing planned or executed oracles",
    )
    parser.add_argument(
        "--allow-repo-output",
        action="store_true",
        help="allow --log-dir or --write-result-manifest paths inside the repository",
    )
    parser.add_argument(
        "--require-source-environment-preflight",
        action="store_true",
        help="exit nonzero unless the ready manifest records source_environment_preflight=ok",
    )
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    require_fixtures = not args.allow_missing_fixtures
    if args.allow_missing_fixtures and not args.dry_run:
        print(
            f"{TOOL_PREFIX}_ready_manifest=error "
            "reason=--allow-missing-fixtures requires --dry-run",
            file=sys.stderr,
        )
        return 1
    try:
        if args.log_dir is not None:
            require_output_outside_repo(
                args.log_dir, "--log-dir", args.allow_repo_output
            )
        if args.write_result_manifest is not None:
            require_output_outside_repo(
                args.write_result_manifest,
                "--write-result-manifest",
                args.allow_repo_output,
            )
        manifest = read_manifest(manifest_path)
        candidates = parse_candidates(manifest.values, manifest.path, require_fixtures)
        oracle_binary = args.oracle_binary or require(manifest.values, "oracle_binary")
        source_environment_preflight = manifest.values.get(
            "source_environment_preflight", "unknown"
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"{TOOL_PREFIX}_ready_manifest=error reason={exc}", file=sys.stderr)
        return 1

    if (
        args.require_source_environment_preflight
        and source_environment_preflight != "ok"
    ):
        print(
            f"{TOOL_PREFIX}_ready_manifest=error "
            "reason=source_environment_preflight_not_ok "
            f"source_environment_preflight={source_environment_preflight}",
            file=sys.stderr,
        )
        return 1

    mode = "dry_run" if args.dry_run else "run"
    print(
        f"{TOOL_PREFIX}_ready_manifest=ok "
        f"mode={mode} "
        f"manifest={manifest.path} "
        f"source_environment_preflight={source_environment_preflight} "
        f"ready_candidates={len(candidates)} "
        f"oracle_binary={oracle_binary}"
    )

    failures = 0
    candidate_lines: list[str] = []
    for candidate in candidates:
        command = command_for_candidate(oracle_binary, candidate)
        display = quote_command(command)
        if args.dry_run:
            candidate_lines.extend(
                candidate_result_lines(candidate, command, "planned", "not_run", "none")
            )
            print(
                "ready_candidate "
                f"index={candidate.index} "
                f"route={candidate.route} "
                f"offset={candidate.offset_label} "
                f"offset_address={candidate.offset_address} "
                f"runtime_cs={candidate.runtime_cs} "
                f"runtime_ds={candidate.runtime_ds} "
                f"oracle={candidate.oracle} "
                f"oracle_flag={candidate.oracle_flag} "
                f"fixture={candidate.fixture} "
                f"command={display}"
            )
            continue

        returncode, output, log_path = run_candidate(
            command, candidate, args.timeout_seconds, args.log_dir
        )
        status = "ok" if returncode == 0 else "error"
        if returncode != 0:
            failures += 1
        candidate_lines.extend(
            candidate_result_lines(
                candidate, command, status, str(returncode), log_path
            )
        )
        print(
            "ready_candidate "
            f"index={candidate.index} "
            f"route={candidate.route} "
            f"offset={candidate.offset_label} "
            f"oracle={candidate.oracle} "
            f"status={status} "
            f"returncode={returncode} "
            f"log={log_path} "
            f"command={display}"
        )
        if returncode != 0 and args.log_dir is None and output:
            print(output.rstrip())

    if args.write_result_manifest is not None:
        try:
            result_manifest = write_result_manifest(
                args.write_result_manifest,
                mode,
                manifest.path,
                source_environment_preflight,
                oracle_binary,
                len(candidates),
                failures,
                candidate_lines,
            )
        except OSError as exc:
            print(
                f"{TOOL_PREFIX}_ready_result_manifest=error reason={exc}",
                file=sys.stderr,
            )
            return 1
        print(
            f"{TOOL_PREFIX}_ready_result_manifest=ok "
            f"path={result_manifest} "
            f"ready_candidates={len(candidates)} "
            f"failures={failures}"
        )

    if failures:
        print(
            f"{TOOL_PREFIX}_ready_manifest=error "
            f"reason=oracle_failures failures={failures}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
