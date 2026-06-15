#!/usr/bin/env python3
"""Summarize original lane-result route-sweep manifests."""

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


CAPTURE_ROUTE_SWEEP = "lane_result_route_sweep"
CAPTURE_RUNTIME = "lane_result_runtime"
ORACLE = "explosion_playback"
ORACLE_FLAG = "--debug-explosion-playback-oracle"
OFFSET_ADDRESSES = {
    "3d3f": "1000:3D3F",
    "3ed3": "1000:3ED3",
}
OFFSET_ALIASES = {
    "forward": "3d3f",
    "reverse": "3ed3",
}
LANE_RESULT_FIELDS = [
    "output",
    "es",
    "di",
    "arg_offset",
    "arg_segment",
    "result_local",
    "active_count",
    "loop_index",
    "target_before",
]


@dataclass(frozen=True)
class Manifest:
    path: Path
    values: dict[str, str]
    entries: list[tuple[str, str]]


@dataclass(frozen=True)
class Candidate:
    route_label: str
    offset_label: str
    offset_address: str
    fixture: Path | None
    source_manifest: Path


@dataclass(frozen=True)
class CandidateReadiness:
    status: str
    missing: list[str]
    placeholders: bool
    freeze_observed: bool
    lane_result_present: bool
    runtime_cs: str
    runtime_ds: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    ready_manifest_lines: list[str]
    environment_preflight: str


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


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [part for part in value.split(",") if part]


def wsl_drive_mount_to_windows_path(raw_path: str) -> Path | None:
    normalized = raw_path.replace("\\", "/")
    match = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", normalized)
    if match is None:
        return None
    drive = match.group(1).upper()
    rest = match.group(2) or ""
    return Path(f"{drive}:/{rest}")


def resolve_child_path(raw_path: str, parent_manifest: Path) -> Path:
    translated = wsl_drive_mount_to_windows_path(raw_path)
    if translated is not None and sys.platform == "win32":
        return translated
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return parent_manifest.parent / path


def bool_value(value: str | None) -> bool:
    if value is None:
        return False
    return value.lower() in {
        "1",
        "true",
        "yes",
        "observed",
        "runtime_child_memory_freeze_observed",
    }


def offset_label_from_address(value: str) -> str:
    token = value.lower()
    if token in OFFSET_ALIASES:
        return OFFSET_ALIASES[token]
    if ":" in value:
        return value.split(":", 1)[1].lower()
    return token


def offset_address_from_label(value: str) -> str:
    label = offset_label_from_address(value)
    return OFFSET_ADDRESSES.get(label, f"1000:{label.upper()}")


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


def missing_or_none(missing: list[str]) -> str:
    if not missing:
        return "none"
    return ",".join(missing)


def oracle_command(binary: str, candidate_fixture: Path | None) -> str:
    if candidate_fixture is None:
        return "none"
    return " ".join(
        shlex.quote(part) for part in [binary, ORACLE_FLAG, str(candidate_fixture)]
    )


def active_values(path: Path) -> tuple[dict[str, str], list[str]]:
    values: dict[str, str] = {}
    nonempty: list[str] = []
    key_re = re.compile(r"^([A-Za-z0-9_]+)=(.*)$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        nonempty.append(line)
        if line.startswith("#"):
            continue
        match = key_re.match(line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values, nonempty


def candidate_readiness(candidate: Candidate) -> CandidateReadiness:
    if candidate.fixture is None:
        return CandidateReadiness("missing", ["fixture"], False, False, False, "", "")
    if not candidate.fixture.exists():
        return CandidateReadiness("missing", ["file"], False, False, False, "", "")

    values, nonempty = active_values(candidate.fixture)
    placeholders = any("<" in line or ">" in line for line in nonempty)
    required_keys = [
        "capture",
        "source",
        "temp_copy",
        "visual_claim",
        "runtime_cs",
        "runtime_ds",
        "instrumented_freeze_observed",
        "instrumented_freeze_patch_mode",
        "freeze_expected_old_bytes",
        "freeze_old_bytes",
        "runtime_freeze_patch_applied",
    ]
    missing = [key for key in required_keys if not values.get(key)]
    freeze_observed = bool_value(values.get("instrumented_freeze_observed"))
    lane_result_present = bool_value(
        values.get("instrumented_lane_result_scratch_present")
    )
    if values.get("instrumented_freeze_patch_mode") != "lane-result-cs-scratch":
        missing.append("lane_result_patch_mode")
    if values.get("freeze_expected_old_bytes", "").lower() != "268805":
        missing.append("freeze_expected_old_bytes_268805")
    if not values.get("freeze_old_bytes", "").lower().startswith("268805"):
        missing.append("freeze_old_bytes_268805")
    if lane_result_present:
        lane_keys = [
            "instrumented_lane_result_cs_offset",
            "instrumented_lane_result_kind",
            *[f"instrumented_lane_result_{field}" for field in LANE_RESULT_FIELDS],
        ]
        missing.extend(key for key in lane_keys if not values.get(key))
    elif freeze_observed:
        missing.append("instrumented_lane_result_scratch")

    runtime_cs = values.get("runtime_cs", "")
    runtime_ds = values.get("runtime_ds", "")
    if missing or placeholders:
        status = "incomplete"
    elif freeze_observed and lane_result_present:
        status = "ready"
    else:
        status = "no_freeze"
    return CandidateReadiness(
        status=status,
        missing=missing,
        placeholders=placeholders,
        freeze_observed=freeze_observed,
        lane_result_present=lane_result_present,
        runtime_cs=runtime_cs,
        runtime_ds=runtime_ds,
    )


def runtime_candidates(manifest: Manifest, route_label: str) -> list[Candidate]:
    offsets = parse_csv(manifest.values.get("offset_labels"))
    if not offsets:
        offsets = [
            key.removeprefix("candidate_")
            for key, _ in manifest.entries
            if key.startswith("candidate_")
        ]
    candidates: list[Candidate] = []
    for offset in offsets:
        label = offset_label_from_address(offset)
        raw_fixture = manifest.values.get(f"candidate_{label}")
        fixture = (
            resolve_child_path(raw_fixture, manifest.path)
            if raw_fixture is not None
            else None
        )
        candidates.append(
            Candidate(
                route_label=route_label,
                offset_label=label,
                offset_address=offset_address_from_label(label),
                fixture=fixture,
                source_manifest=manifest.path,
            )
        )
    return candidates


def route_sweep_candidates(manifest: Manifest) -> list[Candidate]:
    candidates: list[Candidate] = []
    for key, value in manifest.entries:
        if not key.startswith("capture_status_"):
            continue
        route_label = key.removeprefix("capture_status_")
        fields = parse_status_fields(value)
        raw_manifest = fields.get("manifest")
        if raw_manifest is None:
            candidates.append(
                Candidate(
                    route_label=route_label,
                    offset_label="unknown",
                    offset_address="unknown",
                    fixture=None,
                    source_manifest=manifest.path,
                )
            )
            continue
        child = read_manifest(resolve_child_path(raw_manifest, manifest.path))
        candidates.extend(runtime_candidates(child, route_label))
    return candidates


def collect_candidates(manifest: Manifest) -> tuple[str, list[str], list[Candidate]]:
    capture = manifest.values.get("capture", "unknown")
    if capture == CAPTURE_ROUTE_SWEEP:
        mode = "route"
        expected_offsets = [
            offset_label_from_address(manifest.values.get("offset", ""))
        ]
        expected_offsets = [offset for offset in expected_offsets if offset]
        return mode, expected_offsets, route_sweep_candidates(manifest)
    if capture == CAPTURE_RUNTIME:
        mode = "runtime"
        expected_offsets = [
            offset_label_from_address(offset)
            for offset in parse_csv(manifest.values.get("offset_labels"))
        ]
        return mode, expected_offsets, runtime_candidates(manifest, "direct")
    raise ValueError(
        f"unsupported manifest capture {capture!r}; expected "
        f"{CAPTURE_ROUTE_SWEEP!r} or {CAPTURE_RUNTIME!r}"
    )


def ready_manifest_records(
    source_manifest: Path,
    source_environment_preflight: str,
    oracle_binary: str,
    candidates: list[tuple[Candidate, CandidateReadiness]],
) -> list[str]:
    ready_entries = [
        (candidate, readiness)
        for candidate, readiness in candidates
        if readiness.status == "ready"
    ]
    lines = [
        "promotion=lane_result_ready_candidates",
        f"source_manifest={source_manifest}",
        f"source_environment_preflight={source_environment_preflight}",
        f"oracle_binary={oracle_binary}",
        f"ready_candidates={len(ready_entries)}",
    ]
    for index, (candidate, readiness) in enumerate(ready_entries):
        prefix = f"candidate_{index}"
        runtime_cs = parse_runtime_segment_value(
            f"{prefix}_runtime_cs", readiness.runtime_cs
        )
        runtime_ds = parse_runtime_segment_value(
            f"{prefix}_runtime_ds", readiness.runtime_ds
        )
        validate_runtime_fixture_evidence(
            prefix, str(candidate.fixture), runtime_cs, runtime_ds
        )
        lines.extend(
            [
                f"{prefix}_route={candidate.route_label}",
                f"{prefix}_offset_label={candidate.offset_label}",
                f"{prefix}_offset_address={candidate.offset_address}",
                f"{prefix}_runtime_cs={runtime_cs}",
                f"{prefix}_runtime_ds={runtime_ds}",
                f"{prefix}_fixture={candidate.fixture}",
                f"{prefix}_oracle={ORACLE}",
                f"{prefix}_oracle_flag={ORACLE_FLAG}",
                f"{prefix}_oracle_command={oracle_command(oracle_binary, candidate.fixture)}",
            ]
        )
    return lines


def summarize(manifest: Manifest, oracle_binary: str) -> SummaryResult:
    mode, expected_offsets, candidates = collect_candidates(manifest)
    environment_preflight = manifest.values.get("environment_preflight", "unknown")
    readings = [(candidate, candidate_readiness(candidate)) for candidate in candidates]
    readiness_counts = {
        "ready": 0,
        "no_freeze": 0,
        "incomplete": 0,
        "missing": 0,
    }
    for _, readiness in readings:
        readiness_counts[readiness.status] = (
            readiness_counts.get(readiness.status, 0) + 1
        )
    observed_freeze_offsets = [
        candidate.offset_label
        for candidate, readiness in readings
        if readiness.status == "ready"
    ]
    missing_offsets = [
        offset for offset in expected_offsets if offset not in observed_freeze_offsets
    ]
    fixture_paths = [
        str(candidate.fixture)
        for candidate, readiness in readings
        if candidate.fixture is not None and readiness.status != "missing"
    ]
    routes = unique_ordered([candidate.route_label for candidate, _ in readings])
    summary = (
        "lane_result_route_sweep_summary=ok "
        f"manifest={manifest.path} "
        f"capture={manifest.values.get('capture', 'unknown')} "
        f"mode={mode} "
        f"environment_preflight={environment_preflight} "
        f"routes={len(routes)} "
        f"candidates={len(readings)} "
        f"observed_freezes={len(observed_freeze_offsets)} "
        f"ready_candidates={readiness_counts['ready']} "
        f"no_freeze_candidates={readiness_counts['no_freeze']} "
        f"incomplete_candidates={readiness_counts['incomplete']} "
        f"missing_candidates={readiness_counts['missing']} "
        f"observed_offsets={csv_or_none(observed_freeze_offsets)} "
        f"missing_offsets={csv_or_none(missing_offsets)} "
        f"candidate_fixtures={csv_or_none(fixture_paths)}"
    )
    details: list[str] = []
    for candidate, readiness in readings:
        details.append(
            "candidate "
            f"route={candidate.route_label} "
            f"offset={candidate.offset_label} "
            f"offset_address={candidate.offset_address} "
            f"runtime_cs={readiness.runtime_cs or 'unknown'} "
            f"runtime_ds={readiness.runtime_ds or 'unknown'} "
            f"freeze_observed={1 if readiness.freeze_observed else 0} "
            f"lane_result_present={1 if readiness.lane_result_present else 0} "
            f"candidate_fixture={candidate.fixture or 'none'} "
            f"candidate_status={readiness.status} "
            f"candidate_missing={missing_or_none(readiness.missing)} "
            f"candidate_placeholders={1 if readiness.placeholders else 0} "
            f"oracle={ORACLE} "
            f"oracle_flag={ORACLE_FLAG} "
            f"oracle_command={oracle_command(oracle_binary, candidate.fixture)} "
            f"source_manifest={candidate.source_manifest}"
        )
    return SummaryResult(
        summary=summary,
        details=details,
        readiness_counts=readiness_counts,
        ready_manifest_lines=ready_manifest_records(
            manifest.path, environment_preflight, oracle_binary, readings
        ),
        environment_preflight=environment_preflight,
    )


def write_ready_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def require_ready_error(readiness_counts: dict[str, int]) -> str | None:
    if readiness_counts.get("ready", 0) == 0:
        return (
            "lane_result_route_sweep_summary=error reason=no_ready_candidates "
            f"ready_candidates={readiness_counts.get('ready', 0)} "
            f"no_freeze_candidates={readiness_counts.get('no_freeze', 0)} "
            f"incomplete_candidates={readiness_counts.get('incomplete', 0)} "
            f"missing_candidates={readiness_counts.get('missing', 0)}"
        )
    not_ready = readiness_counts.get("incomplete", 0) + readiness_counts.get(
        "missing", 0
    )
    if not_ready == 0:
        return None
    return (
        "lane_result_route_sweep_summary=error reason=candidates_not_ready "
        f"ready_candidates={readiness_counts.get('ready', 0)} "
        f"no_freeze_candidates={readiness_counts.get('no_freeze', 0)} "
        f"incomplete_candidates={readiness_counts.get('incomplete', 0)} "
        f"missing_candidates={readiness_counts.get('missing', 0)}"
    )


def require_environment_preflight_error(environment_preflight: str) -> str | None:
    if environment_preflight == "ok":
        return None
    return (
        "lane_result_route_sweep_summary=error "
        "reason=environment_preflight_not_ok "
        f"environment_preflight={environment_preflight}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize lane-result route-sweep or runtime manifests."
    )
    parser.add_argument("manifest", type=Path, help="manifest.txt or output dir")
    parser.add_argument(
        "--oracle-binary",
        default="./build/lezac_cpp",
        help="binary path to include in emitted oracle_command fields",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="exit nonzero unless at least one freeze candidate is ready",
    )
    parser.add_argument(
        "--write-ready-manifest",
        type=Path,
        help="write a key/value manifest containing ready freeze candidates",
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
        print(f"lane_result_route_sweep_summary=error reason={exc}", file=sys.stderr)
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
            print(f"lane_result_ready_manifest=error reason={exc}", file=sys.stderr)
            return 1
        print(
            "lane_result_ready_manifest=ok "
            f"path={ready_manifest} "
            f"ready_candidates={result.readiness_counts.get('ready', 0)}"
        )
    if args.require_ready:
        error = require_ready_error(result.readiness_counts)
        if error is not None:
            print(error, file=sys.stderr)
            return 2
    if args.require_environment_preflight:
        error = require_environment_preflight_error(result.environment_preflight)
        if error is not None:
            print(error, file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
