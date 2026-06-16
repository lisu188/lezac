#!/usr/bin/env python3
"""Summarize actor dispatch-gate sweep manifests."""

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


CAPTURE_DISPATCH_SWEEP = "actor_dispatch_gate_sweep"
CAPTURE_ROUTE_SWEEP = "actor_contact_route_sweep"
CONTACT_SCANNER_REQUIRED_RECORD_FIELDS = {
    "subject_actor": ["slot", "kind", "state", "x", "y", "w", "h", "flags"],
    "other_actor": ["slot", "kind", "state", "x", "y", "w", "h", "flags"],
    "contact_scan": [
        "subject_slot",
        "other_slot",
        "flags_before",
        "flags_after",
        "contact",
        "player_contact",
        "monster_contact",
        "object_contact",
        "damage_pending",
        "overlap_x",
        "overlap_y",
    ],
}
DISPATCH_GATE_TARGETS = {
    "actor_update_gate5",
    "actor_update_gate5_integration",
    "actor_update_gate5_exit",
    "actor_update_gate6",
    "contact_scanner_callsite",
}


@dataclass(frozen=True)
class Manifest:
    path: Path
    values: dict[str, str]
    entries: list[tuple[str, str]]


@dataclass(frozen=True)
class CaptureStatus:
    route_label: str
    target: str
    fields: dict[str, str]
    source_manifest: Path


@dataclass(frozen=True)
class CandidateReadiness:
    status: str
    missing: list[str]
    placeholders: bool


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    dispatch_gate_freezes: list[str]
    observed_targets: list[str]
    ready_manifest_lines: list[str]
    environment_preflight: str
    child_environment_preflights: list[str]


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
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
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
        if "=" in token:
            key, field_value = token.split("=", 1)
            fields[key] = field_value
    return fields


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part for part in value.split(",") if part]


def resolve_child_path(raw_path: str, parent_manifest: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return parent_manifest.parent / path


def is_freeze_observed(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {
        "1",
        "true",
        "yes",
        "observed",
        "runtime_child_memory_freeze_observed",
    }


def oracle_for_target(target: str) -> tuple[str, str]:
    if target in {"contact_scanner_start", "contact_scanner_end"}:
        return "contact_scanner", "--debug-contact-scanner-runtime-oracle"
    return "actor_update", "--debug-actor-update-runtime-oracle"


def dispatch_gate_candidate(target: str) -> str:
    if target in DISPATCH_GATE_TARGETS:
        return target
    return "none"


def active_fixture_lines(path: Path) -> list[str]:
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def nonempty_fixture_lines(path: Path) -> list[str]:
    return [
        raw_line.strip()
        for raw_line in path.read_text(encoding="utf-8").splitlines()
        if raw_line.strip()
    ]


def candidate_readiness(target: str, candidate_fixture: str | None) -> CandidateReadiness:
    if not candidate_fixture:
        return CandidateReadiness("none", [], False)
    path = Path(candidate_fixture)
    if not path.exists():
        return CandidateReadiness("missing", ["file"], False)

    all_lines = nonempty_fixture_lines(path)
    lines = [line for line in all_lines if not line.startswith("#")]
    keys = {line.split("=", 1)[0] for line in lines if "=" in line}
    record_names = {
        line.split(" ", 1)[0] for line in lines if " " in line and "=" in line
    }
    record_fields = {
        record: {
            part.split("=", 1)[0]
            for part in line.split()[1:]
            if "=" in part
        }
        for line in lines
        if " " in line and "=" in line
        for record in [line.split(" ", 1)[0]]
    }
    break_offsets: set[str] = set()
    for line in lines:
        if not line.startswith("break "):
            continue
        match = re.search(r"\bghidra=1000:([0-9a-fA-F]{4})\b", line)
        if match:
            break_offsets.add(match.group(1).lower())

    oracle, _ = oracle_for_target(target)
    required_keys = ["capture", "scenario", "level", "runtime_cs", "runtime_ds"]
    if oracle == "contact_scanner":
        required_records = ["subject_actor", "other_actor", "contact_scan"]
        required_breaks = ["5cb0", "604f"]
    else:
        required_records = ["actor_before", "actor_after", "contact_scan", "tile_probe"]
        required_breaks = ["5cb0", "604f", "6053", "777f"]

    missing = [key for key in required_keys if key not in keys]
    missing.extend(record for record in required_records if record not in record_names)
    if oracle == "contact_scanner":
        for record, fields in CONTACT_SCANNER_REQUIRED_RECORD_FIELDS.items():
            if record not in record_names:
                continue
            present_fields = record_fields.get(record, set())
            missing.extend(
                f"{record}.{field}" for field in fields if field not in present_fields
            )
    missing.extend(f"break_{offset}" for offset in required_breaks if offset not in break_offsets)
    placeholders = any("<" in line or ">" in line for line in all_lines)
    status = "ready" if not missing and not placeholders else "incomplete"
    return CandidateReadiness(status, missing, placeholders)


def route_statuses(manifest: Manifest, default_target: str | None = None) -> list[CaptureStatus]:
    statuses: list[CaptureStatus] = []
    target_from_manifest = default_target or manifest.values.get("target", "")
    for key, value in manifest.entries:
        if not key.startswith("capture_status_"):
            continue
        route_label = key.removeprefix("capture_status_")
        fields = parse_status_fields(value)
        target = fields.get("target", target_from_manifest)
        statuses.append(
            CaptureStatus(
                route_label=route_label,
                target=target,
                fields=fields,
                source_manifest=manifest.path,
            )
        )
    return statuses


def dispatch_child_manifests(manifest: Manifest) -> list[tuple[str, Manifest]]:
    children: list[tuple[str, Manifest]] = []
    for key, value in manifest.entries:
        if not key.startswith("sweep_manifest_"):
            continue
        target = key.removeprefix("sweep_manifest_")
        child_path = resolve_child_path(value, manifest.path)
        children.append((target, read_manifest(child_path)))
    return children


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def csv_or_none(values: list[str]) -> str:
    ordered = unique_ordered(values)
    if not ordered:
        return "none"
    return ",".join(ordered)


def oracle_command(binary: str, target: str, candidate_fixture: str | None) -> str:
    if not candidate_fixture:
        return "none"
    _, flag = oracle_for_target(target)
    return " ".join(shlex.quote(part) for part in [binary, flag, candidate_fixture])


def missing_or_none(missing: list[str]) -> str:
    if not missing:
        return "none"
    return ",".join(missing)


def ready_manifest_records(
    source_manifest: Path,
    source_environment_preflight: str,
    child_environment_preflights: list[str],
    oracle_binary: str,
    freeze_readiness: list[tuple[CaptureStatus, str | None, CandidateReadiness]],
) -> list[str]:
    ready_entries = [
        (status, candidate_fixture, readiness)
        for status, candidate_fixture, readiness in freeze_readiness
        if readiness.status == "ready" and candidate_fixture
    ]
    lines = [
        "promotion=actor_dispatch_gate_ready_candidates",
        f"source_manifest={source_manifest}",
        f"source_environment_preflight={source_environment_preflight}",
        f"child_environment_preflights={csv_or_none(child_environment_preflights)}",
        f"oracle_binary={oracle_binary}",
        f"ready_candidates={len(ready_entries)}",
    ]
    for index, (status, candidate_fixture, _) in enumerate(ready_entries):
        oracle, flag = oracle_for_target(status.target)
        prefix = f"candidate_{index}"
        runtime_cs = parse_runtime_segment_value(
            f"{prefix}_runtime_cs", status.fields.get("runtime_cs", "unknown")
        )
        runtime_ds = parse_runtime_segment_value(
            f"{prefix}_runtime_ds", status.fields.get("runtime_ds", "unknown")
        )
        validate_runtime_fixture_evidence(
            prefix, candidate_fixture, runtime_cs, runtime_ds
        )
        lines.extend(
            [
                f"{prefix}_target={status.target}",
                f"{prefix}_route={status.route_label}",
                f"{prefix}_ghidra={status.fields.get('ghidra', 'unknown')}",
                f"{prefix}_runtime_cs={runtime_cs}",
                f"{prefix}_runtime_ds={runtime_ds}",
                f"{prefix}_freeze_runtime={status.fields.get('freeze_runtime', 'unknown')}",
                f"{prefix}_fixture={candidate_fixture}",
                f"{prefix}_oracle={oracle}",
                f"{prefix}_oracle_flag={flag}",
                f"{prefix}_oracle_command={oracle_command(oracle_binary, status.target, candidate_fixture)}",
            ]
        )
    return lines


def write_ready_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def summarize(manifest: Manifest, oracle_binary: str) -> SummaryResult:
    capture = manifest.values.get("capture", "unknown")
    environment_preflight = manifest.values.get("environment_preflight", "unknown")
    child_environment_preflights: list[str] = []
    if capture == CAPTURE_DISPATCH_SWEEP:
        child_manifests = dispatch_child_manifests(manifest)
        targets = parse_csv(manifest.values.get("targets"))
        statuses: list[CaptureStatus] = []
        for target, child in child_manifests:
            child_environment_preflights.append(
                child.values.get("environment_preflight", "unknown")
            )
            statuses.extend(route_statuses(child, default_target=target))
        mode = "dispatch"
        route_sweeps = len(child_manifests)
    elif capture == CAPTURE_ROUTE_SWEEP:
        targets = parse_csv(manifest.values.get("target"))
        statuses = route_statuses(manifest)
        mode = "route"
        route_sweeps = 1
        child_environment_preflights = []
    else:
        raise ValueError(
            f"unsupported manifest capture {capture!r}; expected "
            f"{CAPTURE_DISPATCH_SWEEP!r} or {CAPTURE_ROUTE_SWEEP!r}"
        )

    freezes = [
        status
        for status in statuses
        if is_freeze_observed(status.fields.get("freeze_observed"))
    ]
    observed_targets = unique_ordered([status.target for status in freezes])
    dispatch_gate_freezes = [
        status.target for status in freezes if status.target in DISPATCH_GATE_TARGETS
    ]
    observed_dispatch_gates = unique_ordered(dispatch_gate_freezes)
    missing_targets = [target for target in targets if target not in observed_targets]
    candidate_fixtures = [
        status.fields.get("candidate_fixture", "")
        for status in freezes
        if status.fields.get("candidate_fixture")
    ]
    freeze_readiness = [
        (
            status,
            status.fields.get("candidate_fixture"),
            candidate_readiness(status.target, status.fields.get("candidate_fixture")),
        )
        for status in freezes
    ]
    readiness_counts = {
        "ready": 0,
        "incomplete": 0,
        "missing": 0,
        "none": 0,
    }
    for _, _, readiness in freeze_readiness:
        readiness_counts[readiness.status] = readiness_counts.get(readiness.status, 0) + 1
    summary = (
        "actor_dispatch_gate_sweep_summary=ok "
        f"manifest={manifest.path} "
        f"capture={capture} "
        f"mode={mode} "
        f"environment_preflight={environment_preflight} "
        f"child_environment_preflights={csv_or_none(child_environment_preflights)} "
        f"targets={len(targets)} "
        f"route_sweeps={route_sweeps} "
        f"captures={len(statuses)} "
        f"freezes={len(freezes)} "
        f"dispatch_gate_freezes={len(dispatch_gate_freezes)} "
        f"ready_candidates={readiness_counts['ready']} "
        f"incomplete_candidates={readiness_counts['incomplete']} "
        f"missing_candidates={readiness_counts['missing']} "
        f"none_candidates={readiness_counts['none']} "
        f"observed_targets={csv_or_none(observed_targets)} "
        f"observed_dispatch_gates={csv_or_none(observed_dispatch_gates)} "
        f"missing_targets={csv_or_none(missing_targets)} "
        f"candidate_fixtures={csv_or_none(candidate_fixtures)}"
    )
    details = []
    for status, candidate_fixture, readiness in freeze_readiness:
        details.append(
            "freeze "
            f"target={status.target} "
            f"dispatch_gate_candidate={dispatch_gate_candidate(status.target)} "
            f"route={status.route_label} "
            f"ghidra={status.fields.get('ghidra', 'unknown')} "
            f"runtime_cs={status.fields.get('runtime_cs', 'unknown')} "
            f"runtime_ds={status.fields.get('runtime_ds', 'unknown')} "
            f"freeze_runtime={status.fields.get('freeze_runtime', 'unknown')} "
            f"candidate_fixture={candidate_fixture or 'none'} "
            f"candidate_status={readiness.status} "
            f"candidate_missing={missing_or_none(readiness.missing)} "
            f"candidate_placeholders={1 if readiness.placeholders else 0} "
            f"oracle={oracle_for_target(status.target)[0]} "
            f"oracle_flag={oracle_for_target(status.target)[1]} "
            f"oracle_command={oracle_command(oracle_binary, status.target, candidate_fixture)} "
            f"raw_dump={status.fields.get('raw_dump', 'none')}"
        )
    return SummaryResult(
        summary=summary,
        details=details,
        readiness_counts=readiness_counts,
        dispatch_gate_freezes=dispatch_gate_freezes,
        observed_targets=observed_targets,
        ready_manifest_lines=ready_manifest_records(
            manifest.path,
            environment_preflight,
            child_environment_preflights,
            oracle_binary,
            freeze_readiness,
        ),
        environment_preflight=environment_preflight,
        child_environment_preflights=child_environment_preflights,
    )


def require_ready_error(readiness_counts: dict[str, int]) -> str | None:
    not_ready = (
        readiness_counts.get("incomplete", 0)
        + readiness_counts.get("missing", 0)
        + readiness_counts.get("none", 0)
    )
    if not_ready == 0:
        return None
    return (
        "actor_dispatch_gate_sweep_summary=error reason=candidates_not_ready "
        f"ready_candidates={readiness_counts.get('ready', 0)} "
        f"incomplete_candidates={readiness_counts.get('incomplete', 0)} "
        f"missing_candidates={readiness_counts.get('missing', 0)} "
        f"none_candidates={readiness_counts.get('none', 0)}"
    )


def require_environment_preflight_error(
    environment_preflight: str, child_environment_preflights: list[str]
) -> str | None:
    if environment_preflight == "ok":
        return None
    return (
        "actor_dispatch_gate_sweep_summary=error "
        "reason=environment_preflight_not_ok "
        f"environment_preflight={environment_preflight} "
        f"child_environment_preflights={csv_or_none(child_environment_preflights)}"
    )


def require_dispatch_gate_freeze_error(result: SummaryResult) -> str | None:
    if result.dispatch_gate_freezes:
        return None
    return (
        "actor_dispatch_gate_sweep_summary=error "
        "reason=no_dispatch_gate_freezes "
        f"freezes={sum(result.readiness_counts.values())} "
        "dispatch_gate_freezes=0 "
        f"observed_targets={csv_or_none(result.observed_targets)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize actor dispatch-gate or actor/contact route sweep manifests."
        )
    )
    parser.add_argument("manifest", type=Path, help="manifest.txt or sweep output dir")
    parser.add_argument(
        "--oracle-binary",
        default="./build/lezac_cpp",
        help="binary path to include in emitted oracle_command fields",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="exit nonzero if any observed freeze lacks a ready candidate fixture",
    )
    parser.add_argument(
        "--require-dispatch-gate-freeze",
        action="store_true",
        help=(
            "exit nonzero unless at least one observed freeze is one of the "
            "mapped actor/contact dispatch-gate targets"
        ),
    )
    parser.add_argument(
        "--write-ready-manifest",
        type=Path,
        help="write a key/value manifest containing only ready candidate fixtures",
    )
    parser.add_argument(
        "--require-environment-preflight",
        action="store_true",
        help="exit nonzero unless the source sweep manifest records a successful host preflight",
    )
    args = parser.parse_args()

    try:
        result = summarize(read_manifest(args.manifest), args.oracle_binary)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"actor_dispatch_gate_sweep_summary=error reason={exc}", file=sys.stderr)
        return 1
    print(result.summary)
    for detail in result.details:
        print(detail)
    if args.write_ready_manifest is not None:
        try:
            ready_manifest = write_ready_manifest(
                args.write_ready_manifest, result.ready_manifest_lines
            )
        except OSError as exc:
            print(
                f"actor_dispatch_gate_ready_manifest=error reason={exc}",
                file=sys.stderr,
            )
            return 1
        print(
            "actor_dispatch_gate_ready_manifest=ok "
            f"path={ready_manifest} "
            f"ready_candidates={result.readiness_counts.get('ready', 0)}"
        )
    if args.require_ready:
        error = require_ready_error(result.readiness_counts)
        if error is not None:
            print(error, file=sys.stderr)
            return 2
    if args.require_dispatch_gate_freeze:
        error = require_dispatch_gate_freeze_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 4
    if args.require_environment_preflight:
        error = require_environment_preflight_error(
            result.environment_preflight, result.child_environment_preflights
        )
        if error is not None:
            print(error, file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
