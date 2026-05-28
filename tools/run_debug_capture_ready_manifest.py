#!/usr/bin/env python3
"""Run or dry-run generic debug-capture ready-candidate manifests."""

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


EXPECTED_PROMOTION = "debug_capture_ready_candidates"
ORACLE_FLAGS = {
    "behavior4": "--debug-behavior4-runtime-oracle",
    "actor_update": "--debug-actor-update-runtime-oracle",
    "contact_scanner": "--debug-contact-scanner-runtime-oracle",
    "visual_table": "--debug-visual-table-oracle",
}


@dataclass(frozen=True)
class ReadyManifest:
    path: Path
    values: dict[str, str]


@dataclass(frozen=True)
class ReadyCandidate:
    index: int
    capture: str
    scenario: str
    level: str
    environment_preflight: str
    runtime_metadata: str
    runtime_cs: str
    runtime_ds: str
    source_manifest: Path
    fixture: Path
    oracle: str
    oracle_flag: str


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


def resolve_path(raw_path: str, manifest_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def parse_candidates(
    manifest: ReadyManifest,
    require_fixtures: bool,
    require_environment_preflight: bool,
) -> list[ReadyCandidate]:
    promotion = require(manifest.values, "promotion")
    if promotion != EXPECTED_PROMOTION:
        raise ValueError(
            f"unsupported promotion {promotion!r}; expected {EXPECTED_PROMOTION!r}"
        )
    count = parse_ready_count(manifest.values)
    extras = sorted(
        index for index in candidate_indices(manifest.values) if index >= count
    )
    if extras:
        extra_text = ",".join(str(index) for index in extras)
        raise ValueError(
            "candidate index outside ready_candidates: "
            f"{extra_text} ready_candidates={count}"
        )

    candidates: list[ReadyCandidate] = []
    for index in range(count):
        prefix = f"candidate_{index}"
        oracle = require(manifest.values, f"{prefix}_oracle")
        oracle_flag = require(manifest.values, f"{prefix}_oracle_flag")
        expected_flag = ORACLE_FLAGS.get(oracle)
        if expected_flag is None:
            raise ValueError(f"{prefix}_oracle has unsupported value: {oracle!r}")
        if oracle_flag != expected_flag:
            raise ValueError(
                f"{prefix}_oracle_flag={oracle_flag!r} does not match "
                f"{prefix}_oracle={oracle!r}; expected {expected_flag!r}"
            )
        environment_preflight = require(
            manifest.values, f"{prefix}_environment_preflight"
        )
        if require_environment_preflight and environment_preflight != "ok":
            raise ValueError(
                f"{prefix}_environment_preflight={environment_preflight!r}; "
                "expected 'ok'"
            )
        fixture = resolve_path(require(manifest.values, f"{prefix}_fixture"), manifest.path)
        if require_fixtures and not fixture.exists():
            raise FileNotFoundError(f"candidate fixture not found: {fixture}")
        runtime_cs = parse_runtime_segment_value(
            f"{prefix}_runtime_cs", require(manifest.values, f"{prefix}_runtime_cs")
        )
        runtime_ds = parse_runtime_segment_value(
            f"{prefix}_runtime_ds", require(manifest.values, f"{prefix}_runtime_ds")
        )
        validate_runtime_fixture_evidence(
            prefix, str(fixture), runtime_cs, runtime_ds
        )
        candidates.append(
            ReadyCandidate(
                index=index,
                capture=require(manifest.values, f"{prefix}_capture"),
                scenario=require(manifest.values, f"{prefix}_scenario"),
                level=require(manifest.values, f"{prefix}_level"),
                environment_preflight=environment_preflight,
                runtime_metadata=require(manifest.values, f"{prefix}_runtime_metadata"),
                runtime_cs=runtime_cs,
                runtime_ds=runtime_ds,
                source_manifest=resolve_path(
                    require(manifest.values, f"{prefix}_manifest"), manifest.path
                ),
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


def safe_log_name(candidate: ReadyCandidate) -> str:
    label = f"{candidate.index}_{candidate.capture}_{candidate.scenario}"
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in label)
    return f"candidate_{safe}.log"


def write_log(log_dir: Path | None, candidate: ReadyCandidate, output: str) -> str:
    if log_dir is None:
        return "none"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / safe_log_name(candidate)
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
        f"{prefix}_capture={candidate.capture}",
        f"{prefix}_scenario={candidate.scenario}",
        f"{prefix}_level={candidate.level}",
        f"{prefix}_environment_preflight={candidate.environment_preflight}",
        f"{prefix}_runtime_metadata={candidate.runtime_metadata}",
        f"{prefix}_runtime_cs={candidate.runtime_cs}",
        f"{prefix}_runtime_ds={candidate.runtime_ds}",
        f"{prefix}_manifest={candidate.source_manifest}",
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
    source_root: str,
    oracle_binary: str,
    candidate_count: int,
    failures: int,
    candidate_lines: list[str],
) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "result=debug_capture_ready_manifest",
        f"mode={mode}",
        f"source_ready_manifest={source_manifest}",
        f"source_root={source_root}",
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
        description="Run oracle commands from a debug-capture ready manifest."
    )
    parser.add_argument("manifest", type=Path, help="ready promotion manifest")
    parser.add_argument("--dry-run", action="store_true", help="print commands only")
    parser.add_argument(
        "--oracle-binary",
        help="override the oracle binary recorded in the ready manifest",
    )
    parser.add_argument(
        "--allow-missing-fixtures",
        action="store_true",
        help="allow missing fixtures for dry-run forensic review",
    )
    parser.add_argument(
        "--require-source-environment-preflight",
        action="store_true",
        help="exit nonzero unless every ready candidate has environment_preflight=ok",
    )
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--log-dir", type=Path)
    parser.add_argument("--write-result-manifest", type=Path)
    parser.add_argument(
        "--allow-repo-output",
        action="store_true",
        help="allow logs/result manifests inside the repository",
    )
    args = parser.parse_args()

    if args.allow_missing_fixtures and not args.dry_run:
        print(
            "debug_capture_ready_manifest=error "
            "reason=--allow-missing-fixtures requires --dry-run",
            file=sys.stderr,
        )
        return 2

    try:
        ready_manifest = read_manifest(args.manifest)
        oracle_binary = args.oracle_binary or require(
            ready_manifest.values, "oracle_binary"
        )
        require_fixtures = not (args.dry_run and args.allow_missing_fixtures)
        candidates = parse_candidates(
            ready_manifest,
            require_fixtures=require_fixtures,
            require_environment_preflight=args.require_source_environment_preflight,
        )
        if args.log_dir is not None:
            require_output_outside_repo(
                args.log_dir, "log directory", args.allow_repo_output
            )
        if args.write_result_manifest is not None:
            require_output_outside_repo(
                args.write_result_manifest,
                "result manifest",
                args.allow_repo_output,
            )
    except Exception as exc:
        print(f"debug_capture_ready_manifest=error reason={exc}", file=sys.stderr)
        return 1

    mode = "dry_run" if args.dry_run else "run"
    print(
        "debug_capture_ready_manifest=ok "
        f"mode={mode} ready_candidates={len(candidates)} "
        f"source={ready_manifest.path}"
    )

    failures = 0
    result_lines: list[str] = []
    for candidate in candidates:
        command = command_for_candidate(oracle_binary, candidate)
        if args.dry_run:
            status = "planned"
            returncode = "not_run"
            log_path = "none"
        else:
            code, _, log_path = run_candidate(
                command, candidate, args.timeout_seconds, args.log_dir
            )
            status = "ok" if code == 0 else "error"
            returncode = str(code)
            if code != 0:
                failures += 1
        result_lines.extend(
            candidate_result_lines(candidate, command, status, returncode, log_path)
        )
        print(
            "debug_capture_ready_candidate "
            f"index={candidate.index} "
            f"capture={candidate.capture} "
            f"scenario={candidate.scenario} "
            f"oracle={candidate.oracle} "
            f"status={status} "
            f"returncode={returncode} "
            f"log={log_path} "
            f"command={quote_command(command)}"
        )

    if args.write_result_manifest is not None:
        result_path = write_result_manifest(
            args.write_result_manifest,
            mode,
            ready_manifest.path,
            ready_manifest.values.get("source_root", "unknown"),
            oracle_binary,
            len(candidates),
            failures,
            result_lines,
        )
        print(
            "debug_capture_ready_result_manifest=ok "
            f"path={result_path} failures={failures}"
        )
    if failures:
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
