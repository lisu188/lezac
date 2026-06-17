#!/usr/bin/env python3
"""Summarize behavior-4 process-memory route-sweep manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import sys

from ready_result_fixture_guardrails import (
    parse_runtime_segment_value,
    validate_runtime_fixture_evidence,
)


CAPTURE_ROUTE_SWEEP = "behavior4_procmem_route_sweep"
ORACLE = "behavior4"
ORACLE_FLAG = "--debug-behavior4-runtime-oracle"
TARGETS = [
    "spawner_loop_start",
    "spawner_loop_end",
    "behavior4_branch_start",
    "behavior4_branch_end",
    "integration_8_8_start",
    "integration_8_8_end",
]
REQUIRED_KEYS = ["capture", "scenario", "level", "runtime_cs", "runtime_ds"]
REQUIRED_RECORDS = ["spawner", "actor_before", "actor_after", "players"]
REQUIRED_BREAKS = ["7a6b", "7c2c", "728c", "731b", "73e5", "741b"]


@dataclass(frozen=True)
class Manifest:
    path: Path
    values: dict[str, str]
    entries: list[tuple[str, str]]


@dataclass(frozen=True)
class CandidateReadiness:
    status: str
    missing: list[str]
    placeholders: bool


@dataclass(frozen=True)
class CaptureSummary:
    label: str
    target: str
    timing: str
    route_label: str
    status_line: str | None
    status_fields: dict[str, str]
    candidate: Path | None
    readiness: CandidateReadiness
    freeze_observed: bool
    runtime_patch_applied: bool
    runtime_cs: str
    runtime_ds: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    observed_freezes: int
    runtime_patches_applied: int
    patched_no_freeze: int
    environment_preflight: str
    manifest: Manifest
    captures: list[CaptureSummary]


def read_manifest(path: Path) -> Manifest:
    if path.is_dir():
        path = path / "manifest.txt"
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")
    values: dict[str, str] = {}
    entries: list[tuple[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"duplicate manifest field: {key}")
        values[key] = value
        entries.append((key, value))
    return Manifest(path=path, values=values, entries=entries)


def parse_status_fields(value: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in value.split():
        if "=" not in token:
            continue
        key, field_value = token.split("=", 1)
        fields[key] = field_value
    return fields


def wsl_drive_mount_to_windows_path(raw_path: str) -> Path | None:
    normalized = raw_path.replace("\\", "/")
    match = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", normalized)
    if match is None:
        return None
    drive = match.group(1).upper()
    rest = match.group(2) or ""
    return Path(f"{drive}:/{rest}")


def resolve_child_path(raw_path: str | None, parent_manifest: Path) -> Path | None:
    if not raw_path:
        return None
    translated = wsl_drive_mount_to_windows_path(raw_path)
    if translated is not None and sys.platform == "win32":
        return translated
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return parent_manifest.parent / path


def csv_or_none(values: list[str]) -> str:
    if not values:
        return "none"
    return ",".join(values)


def bool_value(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {
        "1",
        "true",
        "yes",
        "observed",
        "runtime_child_memory_freeze_observed",
        "process_memory_runtime_freeze_observed",
    }


def manifest_field(path: Path | None, key: str) -> str | None:
    if path is None or not path.exists():
        return None
    prefix = f"{key}="
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(prefix):
            return line[len(prefix) :]
    return None


def label_parts(label: str, fields: dict[str, str]) -> tuple[str, str, str]:
    target = fields.get("target", "unknown")
    timing = "unknown"
    route_label = "unknown"
    for candidate_target in sorted(TARGETS, key=len, reverse=True):
        prefix = f"{candidate_target}_"
        if not label.startswith(prefix):
            continue
        target = candidate_target
        rest = label[len(prefix) :]
        for candidate_timing in ["before_bomb", "before_route"]:
            timing_prefix = f"{candidate_timing}_"
            if rest.startswith(timing_prefix):
                timing = candidate_timing
                route_label = rest[len(timing_prefix) :]
                return target, timing, route_label
    return target, timing, route_label


def fixture_lines(path: Path) -> tuple[list[str], list[str]]:
    all_lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    active_lines = [line for line in all_lines if not line.startswith("#")]
    return all_lines, active_lines


def candidate_readiness(candidate: Path | None) -> CandidateReadiness:
    if candidate is None:
        return CandidateReadiness("missing", ["fixture"], False)
    if not candidate.exists():
        return CandidateReadiness("missing", ["file"], False)

    all_lines, active_lines = fixture_lines(candidate)
    keys = {line.split("=", 1)[0] for line in active_lines if "=" in line}
    record_names = {
        line.split(" ", 1)[0] for line in active_lines if " " in line and "=" in line
    }
    break_offsets: set[str] = set()
    for line in active_lines:
        if not line.startswith("break "):
            continue
        match = re.search(r"\bghidra=1000:([0-9a-fA-F]{4})\b", line)
        if match:
            break_offsets.add(match.group(1).lower())

    missing = [key for key in REQUIRED_KEYS if key not in keys]
    missing.extend(record for record in REQUIRED_RECORDS if record not in record_names)
    missing.extend(
        f"break_{offset}" for offset in REQUIRED_BREAKS if offset not in break_offsets
    )
    placeholders = any("<" in line or ">" in line for line in all_lines)
    status = "ready" if not missing and not placeholders else "incomplete"
    return CandidateReadiness(status, missing, placeholders)


def oracle_command(binary: str, candidate_fixture: Path | None) -> str:
    if candidate_fixture is None:
        return "none"
    return " ".join(
        shlex.quote(part) for part in [binary, ORACLE_FLAG, str(candidate_fixture)]
    )


def display_path(path: Path | None) -> str:
    if path is None:
        return "none"
    return str(path.resolve())


def capture_labels(manifest: Manifest) -> list[str]:
    labels: list[str] = []
    for key, _ in manifest.entries:
        if not key.startswith("capture_command_"):
            continue
        labels.append(key[len("capture_command_") :])
    return labels


def summarize_capture(manifest: Manifest, label: str) -> CaptureSummary:
    status_line = manifest.values.get(f"capture_status_{label}")
    fields = parse_status_fields(status_line) if status_line else {}
    target, timing, route_label = label_parts(label, fields)
    candidate = resolve_child_path(fields.get("candidate_fixture"), manifest.path)
    child_manifest = resolve_child_path(fields.get("manifest"), manifest.path)
    readiness = candidate_readiness(candidate)
    freeze_observed = bool_value(
        fields.get("freeze_observed") or fields.get("instrumented_freeze_observed")
    )
    runtime_patch_applied = bool_value(
        fields.get("freeze_runtime_patch_applied")
        or manifest_field(child_manifest, "freeze_runtime_patch_applied")
    )
    return CaptureSummary(
        label=label,
        target=target,
        timing=timing,
        route_label=route_label,
        status_line=status_line,
        status_fields=fields,
        candidate=candidate,
        readiness=readiness,
        freeze_observed=freeze_observed,
        runtime_patch_applied=runtime_patch_applied,
        runtime_cs=fields.get("runtime_cs", "unknown"),
        runtime_ds=fields.get("runtime_ds", "unknown"),
    )


def summarize(args: argparse.Namespace) -> SummaryResult:
    manifest = read_manifest(args.manifest)
    capture = manifest.values.get("capture", "unknown")
    if capture != CAPTURE_ROUTE_SWEEP:
        raise RuntimeError(f"unsupported capture type: {capture}")

    labels = capture_labels(manifest)
    captures = [summarize_capture(manifest, label) for label in labels]
    readiness_counts = {"ready": 0, "incomplete": 0, "missing": 0}
    observed_freezes = 0
    runtime_patches_applied = 0
    patched_no_freeze = 0
    details: list[str] = []
    ready_manifests: list[str] = []
    missing_labels: list[str] = []
    for capture_summary in captures:
        readiness_counts[capture_summary.readiness.status] += 1
        if capture_summary.runtime_patch_applied:
            runtime_patches_applied += 1
        if capture_summary.freeze_observed:
            observed_freezes += 1
        elif capture_summary.runtime_patch_applied:
            patched_no_freeze += 1
        if capture_summary.readiness.status == "ready":
            ready_manifests.append(str(capture_summary.candidate))
        if capture_summary.readiness.status == "missing":
            missing_labels.append(capture_summary.label)
        details.append(
            "behavior4_procmem_route_sweep_detail "
            f"label={capture_summary.label} "
            f"target={capture_summary.target} "
            f"timing={capture_summary.timing} "
            f"route_label={capture_summary.route_label} "
            f"candidate_status={capture_summary.readiness.status} "
            f"candidate_missing={csv_or_none(capture_summary.readiness.missing)} "
            f"candidate_placeholders={1 if capture_summary.readiness.placeholders else 0} "
            f"runtime_patch_applied={1 if capture_summary.runtime_patch_applied else 0} "
            f"freeze_observed={1 if capture_summary.freeze_observed else 0} "
            f"runtime_cs={capture_summary.runtime_cs} "
            f"runtime_ds={capture_summary.runtime_ds} "
            f"oracle={ORACLE} "
            f"oracle_flag={ORACLE_FLAG} "
            f"oracle_command={oracle_command(args.oracle_binary, capture_summary.candidate)} "
            f"candidate_fixture={capture_summary.candidate or 'none'}"
        )

    environment_preflight = manifest.values.get("environment_preflight", "unknown")
    summary = " ".join(
        [
            "behavior4_procmem_route_sweep_summary=ok",
            f"scenario={manifest.values.get('scenario', 'unknown')}",
            f"expected_level={manifest.values.get('expected_level', 'unknown')}",
            f"targets={manifest.values.get('targets', 'unknown')}",
            f"target_names={manifest.values.get('target_names', 'unknown')}",
            f"timings={manifest.values.get('timings', 'unknown')}",
            f"routes={manifest.values.get('routes', 'unknown')}",
            f"route_labels={manifest.values.get('route_labels', 'unknown')}",
            f"capture_commands={len(labels)}",
            f"completed_captures={len([c for c in captures if c.status_line])}",
            f"observed_freezes={observed_freezes}",
            f"runtime_patches_applied={runtime_patches_applied}",
            f"patched_no_freeze_candidates={patched_no_freeze}",
            f"ready_candidates={readiness_counts['ready']}",
            f"incomplete_candidates={readiness_counts['incomplete']}",
            f"missing_candidates={readiness_counts['missing']}",
            f"missing_labels={csv_or_none(missing_labels)}",
            f"ready_manifests={csv_or_none(ready_manifests)}",
            f"environment_preflight={environment_preflight}",
            f"manifest={manifest.path}",
        ]
    )
    return SummaryResult(
        summary=summary,
        details=details,
        readiness_counts=readiness_counts,
        observed_freezes=observed_freezes,
        runtime_patches_applied=runtime_patches_applied,
        patched_no_freeze=patched_no_freeze,
        environment_preflight=environment_preflight,
        manifest=manifest,
        captures=captures,
    )


def ready_manifest_lines(result: SummaryResult, oracle_binary: str) -> list[str]:
    ready = [
        capture
        for capture in result.captures
        if capture.readiness.status == "ready"
    ]
    lines = [
        "promotion=debug_capture_ready_candidates",
        f"source_root={result.manifest.path.parent}",
        f"oracle_binary={oracle_binary}",
        f"ready_candidates={len(ready)}",
    ]
    for index, capture in enumerate(ready):
        prefix = f"candidate_{index}"
        runtime_cs = parse_runtime_segment_value(
            f"{prefix}_runtime_cs", capture.runtime_cs
        )
        runtime_ds = parse_runtime_segment_value(
            f"{prefix}_runtime_ds", capture.runtime_ds
        )
        validate_runtime_fixture_evidence(
            prefix, display_path(capture.candidate), runtime_cs, runtime_ds
        )
        lines.extend(
            [
                f"{prefix}_capture=behavior4_runtime",
                f"{prefix}_scenario={result.manifest.values.get('scenario', 'unknown')}",
                f"{prefix}_level={result.manifest.values.get('expected_level', 'unknown')}",
                f"{prefix}_environment_preflight={result.environment_preflight}",
                f"{prefix}_runtime_metadata=observed",
                f"{prefix}_runtime_cs={runtime_cs}",
                f"{prefix}_runtime_ds={runtime_ds}",
                f"{prefix}_manifest={result.manifest.path}",
                f"{prefix}_fixture={display_path(capture.candidate)}",
                f"{prefix}_oracle={ORACLE}",
                f"{prefix}_oracle_flag={ORACLE_FLAG}",
                f"{prefix}_oracle_command={oracle_command(oracle_binary, capture.candidate)}",
                f"{prefix}_source_label={capture.label}",
                f"{prefix}_target={capture.target}",
                f"{prefix}_timing={capture.timing}",
                f"{prefix}_route_label={capture.route_label}",
            ]
        )
    return lines


def write_ready_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize behavior-4 process-memory route-sweep artifacts."
    )
    parser.add_argument("manifest", type=Path, help="sweep directory or manifest.txt")
    parser.add_argument(
        "--oracle-binary",
        default="./build/lezac_cpp",
        help="binary to use when printing oracle commands",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="exit nonzero unless every capture candidate is ready",
    )
    parser.add_argument(
        "--require-observed-freeze",
        action="store_true",
        help="exit nonzero unless at least one capture reports an observed freeze",
    )
    parser.add_argument(
        "--require-runtime-patch",
        action="store_true",
        help="exit nonzero unless at least one capture reports a runtime patch",
    )
    parser.add_argument(
        "--require-environment-preflight",
        action="store_true",
        help="exit nonzero unless the sweep manifest records environment_preflight=ok",
    )
    parser.add_argument(
        "--write-ready-manifest",
        type=Path,
        help=(
            "write a debug_capture_ready_candidates manifest for ready "
            "behavior-4 candidates"
        ),
    )
    args = parser.parse_args()

    try:
        result = summarize(args)
    except Exception as exc:
        print(f"behavior4_procmem_route_sweep_summary=error reason={exc}", file=sys.stderr)
        return 1

    print(result.summary)
    for detail in result.details:
        print(detail)

    if args.write_ready_manifest is not None:
        try:
            ready_manifest = write_ready_manifest(
                args.write_ready_manifest,
                ready_manifest_lines(result, args.oracle_binary),
            )
        except Exception as exc:
            print(
                f"behavior4_procmem_ready_manifest=error reason={exc}",
                file=sys.stderr,
            )
            return 5
        print(
            "behavior4_procmem_ready_manifest=ok "
            f"path={ready_manifest} "
            f"ready_candidates={result.readiness_counts['ready']}"
        )

    if args.require_environment_preflight and result.environment_preflight != "ok":
        print(
            "behavior4_procmem_route_sweep_summary=error "
            f"reason=environment_preflight_not_ok "
            f"environment_preflight={result.environment_preflight}",
            file=sys.stderr,
        )
        return 2
    if args.require_ready and (
        result.readiness_counts["incomplete"] or result.readiness_counts["missing"]
    ):
        print(
            "behavior4_procmem_route_sweep_summary=error "
            "reason=candidates_not_ready "
            f"incomplete_candidates={result.readiness_counts['incomplete']} "
            f"missing_candidates={result.readiness_counts['missing']}",
            file=sys.stderr,
        )
        return 3
    if args.require_observed_freeze and result.observed_freezes == 0:
        print(
            "behavior4_procmem_route_sweep_summary=error "
            "reason=no_observed_freezes",
            file=sys.stderr,
        )
        return 4
    if args.require_runtime_patch and result.runtime_patches_applied == 0:
        print(
            "behavior4_procmem_route_sweep_summary=error "
            "reason=no_runtime_patches_applied",
            file=sys.stderr,
        )
        return 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
