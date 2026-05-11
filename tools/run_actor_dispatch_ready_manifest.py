#!/usr/bin/env python3
"""Run or dry-run actor dispatch-gate ready-candidate oracle manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shlex
import subprocess
import sys


EXPECTED_PROMOTION = "actor_dispatch_gate_ready_candidates"


@dataclass(frozen=True)
class ReadyManifest:
    path: Path
    values: dict[str, str]


@dataclass(frozen=True)
class ReadyCandidate:
    index: int
    target: str
    route: str
    ghidra: str
    runtime_cs: str
    runtime_ds: str
    freeze_runtime: str
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


def resolve_fixture(raw_fixture: str, manifest_path: Path) -> Path:
    path = Path(raw_fixture)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def parse_candidates(values: dict[str, str], manifest_path: Path) -> list[ReadyCandidate]:
    promotion = require(values, "promotion")
    if promotion != EXPECTED_PROMOTION:
        raise ValueError(
            f"unsupported promotion {promotion!r}; expected {EXPECTED_PROMOTION!r}"
        )
    candidates: list[ReadyCandidate] = []
    for index in range(parse_ready_count(values)):
        prefix = f"candidate_{index}"
        candidates.append(
            ReadyCandidate(
                index=index,
                target=require(values, f"{prefix}_target"),
                route=require(values, f"{prefix}_route"),
                ghidra=require(values, f"{prefix}_ghidra"),
                runtime_cs=require(values, f"{prefix}_runtime_cs"),
                runtime_ds=require(values, f"{prefix}_runtime_ds"),
                freeze_runtime=require(values, f"{prefix}_freeze_runtime"),
                fixture=resolve_fixture(require(values, f"{prefix}_fixture"), manifest_path),
                oracle=require(values, f"{prefix}_oracle"),
                oracle_flag=require(values, f"{prefix}_oracle_flag"),
            )
        )
    return candidates


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def command_for_candidate(binary: str, candidate: ReadyCandidate) -> list[str]:
    return [binary, candidate.oracle_flag, str(candidate.fixture)]


def write_log(log_dir: Path | None, candidate: ReadyCandidate, output: str) -> str:
    if log_dir is None:
        return "none"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"candidate_{candidate.index}_{candidate.target}.log"
    log_path.write_text(output, encoding="utf-8")
    return str(log_path)


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
        description="Run oracle commands from an actor dispatch ready manifest."
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
    parser.add_argument("--log-dir", type=Path, help="write oracle output logs")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    try:
        manifest = read_manifest(manifest_path)
        candidates = parse_candidates(manifest.values, manifest.path)
        oracle_binary = args.oracle_binary or require(manifest.values, "oracle_binary")
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"actor_dispatch_ready_manifest=error reason={exc}", file=sys.stderr)
        return 1

    mode = "dry_run" if args.dry_run else "run"
    print(
        "actor_dispatch_ready_manifest=ok "
        f"mode={mode} "
        f"manifest={manifest.path} "
        f"ready_candidates={len(candidates)} "
        f"oracle_binary={oracle_binary}"
    )

    failures = 0
    for candidate in candidates:
        command = command_for_candidate(oracle_binary, candidate)
        display = quote_command(command)
        if args.dry_run:
            print(
                "ready_candidate "
                f"index={candidate.index} "
                f"target={candidate.target} "
                f"route={candidate.route} "
                f"ghidra={candidate.ghidra} "
                f"runtime_cs={candidate.runtime_cs} "
                f"runtime_ds={candidate.runtime_ds} "
                f"freeze_runtime={candidate.freeze_runtime} "
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
        print(
            "ready_candidate "
            f"index={candidate.index} "
            f"target={candidate.target} "
            f"route={candidate.route} "
            f"oracle={candidate.oracle} "
            f"status={status} "
            f"returncode={returncode} "
            f"log={log_path} "
            f"command={display}"
        )
        if returncode != 0 and args.log_dir is None and output:
            print(output.rstrip())

    if failures:
        print(
            "actor_dispatch_ready_manifest=error "
            f"reason=oracle_failures failures={failures}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
