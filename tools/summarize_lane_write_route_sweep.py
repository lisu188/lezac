#!/usr/bin/env python3
"""Summarize original lane-write route-sweep manifests."""

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


CAPTURE_ROUTE_SWEEP = "lane_write_route_sweep"
CAPTURE_PROCMEM = "original_explosion_process_memory"
ORACLE = "explosion_playback"
ORACLE_FLAG = "--debug-explosion-playback-oracle"
FORWARD_DEBRIS_ROUTE_PROMOTION = "lane_write_forward_debris_route_candidates"
OFFSET_ADDRESSES = {
    "3d1b": "1000:3D1B",
    "3d2d": "1000:3D2D",
    "3eaf": "1000:3EAF",
    "3ec1": "1000:3EC1",
}
OFFSET_MODEL = {
    "3d1b": ("forward", "collapse", "888517"),
    "3d2d": ("forward", "debris", "889597"),
    "3eaf": ("reverse", "collapse", "888518"),
    "3ec1": ("reverse", "debris", "889598"),
}
LANE_WRITE_FIELDS = [
    "output",
    "di",
    "tag",
    "active_count",
    "loop_index",
    "result_local",
]
DEBRIS_TAG_BASE = 0x4E20


@dataclass(frozen=True)
class Manifest:
    path: Path
    values: dict[str, str]
    entries: list[tuple[str, str]]


@dataclass(frozen=True)
class Candidate:
    capture_label: str
    route_label: str
    route_steps: list[str]
    offset_label: str
    offset_address: str
    fixture: Path | None
    source_manifest: Path


@dataclass(frozen=True)
class CandidateReadiness:
    status: str
    missing: list[str]
    placeholders: bool
    patch_applied: bool
    freeze_observed: bool
    lane_write_present: bool
    lane_write_kind: str
    lane_write_target: str
    runtime_cs: str
    runtime_ds: str
    lane_write_output: str
    lane_write_di: str
    lane_write_tag: str
    lane_write_active_count: str
    lane_write_loop_index: str
    lane_write_result_local: str
    lane_write_tag_class: str
    lane_write_tag_value: int | None


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    debris_tag_candidates: int
    forward_debris_tag_candidates: int
    reverse_debris_tag_candidates: int
    collapse_tag_candidates: int
    unknown_tag_candidates: int
    ready_manifest_lines: list[str]
    forward_debris_route_candidates: list[tuple[Candidate, CandidateReadiness]]
    environment_preflight: str
    source_manifest: Path


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


def parse_hex_int(value: str | None) -> int | None:
    if not value:
        return None
    token = value.strip().lower()
    try:
        return int(token, 0)
    except ValueError:
        return None


def classify_lane_write_tag(value: str | None) -> tuple[str, int | None]:
    parsed = parse_hex_int(value)
    if parsed is None:
        return "unknown", None
    if parsed >= DEBRIS_TAG_BASE:
        return "debris", parsed
    return "collapse", parsed


def offset_label_from_address(value: str) -> str:
    token = value.lower()
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


def hex_or_none(value: int | None) -> str:
    if value is None:
        return "none"
    return f"0x{value:04x}"


def oracle_command(binary: str, candidate_fixture: Path | None) -> str:
    if candidate_fixture is None:
        return "none"
    return " ".join(
        shlex.quote(part) for part in [binary, ORACLE_FLAG, str(candidate_fixture)]
    )


def extract_route_steps(command: str | None) -> list[str]:
    if not command:
        return []
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    steps: list[str] = []
    index = 0
    while index < len(tokens):
        if tokens[index] == "--route-step" and index + 1 < len(tokens):
            steps.append(tokens[index + 1])
            index += 2
            continue
        index += 1
    return steps


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


def expected_model(offset_label: str) -> tuple[str, str, str] | None:
    return OFFSET_MODEL.get(offset_label_from_address(offset_label))


def candidate_readiness(candidate: Candidate) -> CandidateReadiness:
    if candidate.fixture is None:
        return CandidateReadiness(
            "missing",
            ["fixture"],
            False,
            False,
            False,
            False,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "unknown",
            None,
        )
    if not candidate.fixture.exists():
        return CandidateReadiness(
            "missing",
            ["file"],
            False,
            False,
            False,
            False,
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "unknown",
            None,
        )

    values, nonempty = active_values(candidate.fixture)
    placeholders = any("<" in line or ">" in line for line in nonempty)
    patch_applied = bool_value(values.get("runtime_freeze_patch_applied"))
    required_keys = [
        "capture",
        "source",
        "temp_copy",
        "visual_claim",
        "runtime_cs",
        "runtime_ds",
        "instrumented_freeze_observed",
        "instrumented_freeze_patch_mode",
        "instrumented_lane_write_cs_offset",
        "instrumented_lane_write_kind",
        "instrumented_lane_write_target",
        "runtime_freeze_patch_applied",
    ]
    if patch_applied:
        required_keys.append("runtime_freeze_old_bytes")
    missing = [key for key in required_keys if not values.get(key)]
    freeze_observed = bool_value(values.get("instrumented_freeze_observed"))
    lane_write_present = bool_value(
        values.get("instrumented_lane_write_scratch_present")
    )
    lane_write_kind = values.get("instrumented_lane_write_kind", "")
    lane_write_target = values.get("instrumented_lane_write_target", "")
    lane_write_output = values.get("instrumented_lane_write_output", "")
    lane_write_di = values.get("instrumented_lane_write_di", "")
    lane_write_tag = values.get("instrumented_lane_write_tag", "")
    lane_write_active_count = values.get(
        "instrumented_lane_write_active_count", ""
    )
    lane_write_loop_index = values.get("instrumented_lane_write_loop_index", "")
    lane_write_result_local = values.get("instrumented_lane_write_result_local", "")
    lane_write_tag_class, lane_write_tag_value = classify_lane_write_tag(
        lane_write_tag if lane_write_present else None
    )

    if values.get("instrumented_freeze_patch_mode") != "lane-write-cs-scratch":
        missing.append("lane_write_patch_mode")
    if values.get("instrumented_lane_write_cs_offset", "").lower() != "0xf080":
        missing.append("instrumented_lane_write_cs_offset_f080")
    model = expected_model(candidate.offset_label)
    if model is None:
        missing.append("known_lane_write_offset")
    else:
        expected_kind, expected_target, expected_old_bytes = model
        if lane_write_kind != expected_kind:
            missing.append(f"lane_write_kind_{expected_kind}")
        if lane_write_target != expected_target:
            missing.append(f"lane_write_target_{expected_target}")
        if patch_applied and not values.get(
            "runtime_freeze_old_bytes", ""
        ).lower().startswith(expected_old_bytes):
            missing.append(f"runtime_freeze_old_bytes_{expected_old_bytes}")
    if lane_write_present:
        lane_keys = [
            *[f"instrumented_lane_write_{field}" for field in LANE_WRITE_FIELDS],
        ]
        missing.extend(key for key in lane_keys if not values.get(key))
    elif freeze_observed:
        missing.append("instrumented_lane_write_scratch")

    runtime_cs = values.get("runtime_cs", "")
    runtime_ds = values.get("runtime_ds", "")
    if missing or placeholders:
        status = "incomplete"
    elif not patch_applied:
        status = "no_patch"
    elif freeze_observed and lane_write_present:
        status = "ready"
    else:
        status = "no_freeze"
    return CandidateReadiness(
        status=status,
        missing=missing,
        placeholders=placeholders,
        patch_applied=patch_applied,
        freeze_observed=freeze_observed,
        lane_write_present=lane_write_present,
        lane_write_kind=lane_write_kind,
        lane_write_target=lane_write_target,
        runtime_cs=runtime_cs,
        runtime_ds=runtime_ds,
        lane_write_output=lane_write_output,
        lane_write_di=lane_write_di,
        lane_write_tag=lane_write_tag,
        lane_write_active_count=lane_write_active_count,
        lane_write_loop_index=lane_write_loop_index,
        lane_write_result_local=lane_write_result_local,
        lane_write_tag_class=lane_write_tag_class,
        lane_write_tag_value=lane_write_tag_value,
    )


def procmem_candidate(manifest: Manifest, route_label: str, offset_label: str) -> Candidate:
    raw_fixture = manifest.values.get("fixture_candidate")
    fixture = (
        resolve_child_path(raw_fixture, manifest.path)
        if raw_fixture is not None
        else None
    )
    return Candidate(
        capture_label="direct",
        route_label=route_label,
        route_steps=[],
        offset_label=offset_label_from_address(offset_label),
        offset_address=offset_address_from_label(offset_label),
        fixture=fixture,
        source_manifest=manifest.path,
    )


def route_sweep_candidates(manifest: Manifest) -> list[Candidate]:
    candidates: list[Candidate] = []
    for key, value in manifest.entries:
        if not key.startswith("capture_status_"):
            continue
        capture_label = key.removeprefix("capture_status_")
        fields = parse_status_fields(value)
        route_label = fields.get("route", capture_label)
        route_steps = extract_route_steps(
            manifest.values.get(f"capture_command_{capture_label}")
        )
        offset_label = offset_label_from_address(fields.get("offset", "unknown"))
        offset_address = fields.get("offset_address", offset_address_from_label(offset_label))
        raw_fixture = fields.get("candidate")
        fixture: Path | None = None
        if raw_fixture is not None:
            fixture = resolve_child_path(raw_fixture, manifest.path)
        else:
            raw_manifest = fields.get("manifest")
            if raw_manifest is not None:
                child = read_manifest(resolve_child_path(raw_manifest, manifest.path))
                child_fixture = child.values.get("fixture_candidate")
                if child_fixture is not None:
                    fixture = resolve_child_path(child_fixture, child.path)
        candidates.append(
            Candidate(
                capture_label=capture_label,
                route_label=route_label,
                route_steps=route_steps,
                offset_label=offset_label,
                offset_address=offset_address,
                fixture=fixture,
                source_manifest=manifest.path,
            )
        )
    return candidates


def collect_candidates(manifest: Manifest) -> tuple[str, list[str], list[Candidate]]:
    capture = manifest.values.get("capture", "unknown")
    if capture == CAPTURE_ROUTE_SWEEP:
        mode = "route"
        expected_offsets = [
            offset_label_from_address(offset)
            for offset in parse_csv(manifest.values.get("offset_labels"))
        ]
        return mode, expected_offsets, route_sweep_candidates(manifest)
    if capture == CAPTURE_PROCMEM:
        mode = "runtime"
        candidate = procmem_candidate(
            manifest,
            manifest.values.get("route_label", "direct"),
            manifest.values.get("offset_label", "unknown"),
        )
        return mode, [], [candidate]
    raise ValueError(
        f"unsupported manifest capture {capture!r}; expected "
        f"{CAPTURE_ROUTE_SWEEP!r} or {CAPTURE_PROCMEM!r}"
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
        "promotion=lane_write_ready_candidates",
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
                f"{prefix}_lane_write_kind={readiness.lane_write_kind}",
                f"{prefix}_lane_write_target={readiness.lane_write_target}",
                f"{prefix}_runtime_cs={runtime_cs}",
                f"{prefix}_runtime_ds={runtime_ds}",
                f"{prefix}_fixture={candidate.fixture}",
                f"{prefix}_oracle={ORACLE}",
                f"{prefix}_oracle_flag={ORACLE_FLAG}",
                f"{prefix}_oracle_command={oracle_command(oracle_binary, candidate.fixture)}",
            ]
        )
    return lines


def is_forward_debris_ready(
    readiness: CandidateReadiness,
) -> bool:
    return (
        readiness.status == "ready"
        and readiness.lane_write_kind == "forward"
        and readiness.lane_write_target == "debris"
        and readiness.lane_write_tag_class == "debris"
    )


def is_reverse_debris_ready(
    readiness: CandidateReadiness,
) -> bool:
    return (
        readiness.status == "ready"
        and readiness.lane_write_kind == "reverse"
        and readiness.lane_write_target == "debris"
        and readiness.lane_write_tag_class == "debris"
    )


def forward_debris_route_manifest_records(
    source_manifest: Path,
    source_environment_preflight: str,
    candidates: list[tuple[Candidate, CandidateReadiness]],
) -> list[str]:
    matching: list[tuple[Candidate, CandidateReadiness]] = []
    seen_routes: set[str] = set()
    for candidate, readiness in candidates:
        if not is_forward_debris_ready(readiness):
            continue
        if candidate.route_label in seen_routes:
            continue
        seen_routes.add(candidate.route_label)
        matching.append((candidate, readiness))
    lines = [
        f"promotion={FORWARD_DEBRIS_ROUTE_PROMOTION}",
        f"source_manifest={source_manifest}",
        f"source_environment_preflight={source_environment_preflight}",
        "required_candidate=forward_debris_tag",
        f"matching_routes={len(matching)}",
    ]
    for index, (candidate, readiness) in enumerate(matching):
        if not candidate.route_steps:
            raise ValueError(f"route_steps_missing route={candidate.route_label}")
        prefix = f"route_{index}"
        lines.extend(
            [
                f"{prefix}_label={candidate.route_label}",
                f"{prefix}_steps={','.join(candidate.route_steps)}",
                f"{prefix}_offset_label={candidate.offset_label}",
                f"{prefix}_offset_address={candidate.offset_address}",
                f"{prefix}_lane_write_tag={readiness.lane_write_tag}",
                f"{prefix}_lane_write_di={readiness.lane_write_di}",
                f"{prefix}_fixture={candidate.fixture}",
            ]
        )
    return lines


def summarize(manifest: Manifest, oracle_binary: str) -> SummaryResult:
    mode, expected_offsets, candidates = collect_candidates(manifest)
    environment_preflight = manifest.values.get("environment_preflight", "unknown")
    readings = [(candidate, candidate_readiness(candidate)) for candidate in candidates]
    readiness_counts = {
        "ready": 0,
        "no_patch": 0,
        "no_freeze": 0,
        "incomplete": 0,
        "missing": 0,
    }
    for _, readiness in readings:
        readiness_counts[readiness.status] = (
            readiness_counts.get(readiness.status, 0) + 1
        )
    ready_tag_classes = [
        readiness.lane_write_tag_class
        for _, readiness in readings
        if readiness.status == "ready"
    ]
    debris_tag_candidates = ready_tag_classes.count("debris")
    forward_debris_readings = [
        (candidate, readiness)
        for candidate, readiness in readings
        if is_forward_debris_ready(readiness)
    ]
    forward_debris_tag_candidates = len(forward_debris_readings)
    reverse_debris_tag_candidates = sum(
        1 for _, readiness in readings if is_reverse_debris_ready(readiness)
    )
    collapse_tag_candidates = ready_tag_classes.count("collapse")
    unknown_tag_candidates = ready_tag_classes.count("unknown")
    max_lane_write_tag = max(
        (
            readiness.lane_write_tag_value
            for _, readiness in readings
            if readiness.status == "ready"
            and readiness.lane_write_tag_value is not None
        ),
        default=None,
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
        "lane_write_route_sweep_summary=ok "
        f"manifest={manifest.path} "
        f"capture={manifest.values.get('capture', 'unknown')} "
        f"mode={mode} "
        f"environment_preflight={environment_preflight} "
        f"routes={len(routes)} "
        f"candidates={len(readings)} "
        f"observed_freezes={len(observed_freeze_offsets)} "
        f"ready_candidates={readiness_counts['ready']} "
        f"no_patch_candidates={readiness_counts['no_patch']} "
        f"no_freeze_candidates={readiness_counts['no_freeze']} "
        f"incomplete_candidates={readiness_counts['incomplete']} "
        f"missing_candidates={readiness_counts['missing']} "
        f"debris_tag_candidates={debris_tag_candidates} "
        f"forward_debris_tag_candidates={forward_debris_tag_candidates} "
        f"reverse_debris_tag_candidates={reverse_debris_tag_candidates} "
        f"collapse_tag_candidates={collapse_tag_candidates} "
        f"unknown_tag_candidates={unknown_tag_candidates} "
        f"max_lane_write_tag={hex_or_none(max_lane_write_tag)} "
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
            f"route_steps={csv_or_none(candidate.route_steps)} "
            f"kind={readiness.lane_write_kind or 'unknown'} "
            f"target={readiness.lane_write_target or 'unknown'} "
            f"runtime_cs={readiness.runtime_cs or 'unknown'} "
            f"runtime_ds={readiness.runtime_ds or 'unknown'} "
            f"patch_applied={1 if readiness.patch_applied else 0} "
            f"freeze_observed={1 if readiness.freeze_observed else 0} "
            f"lane_write_present={1 if readiness.lane_write_present else 0} "
            f"lane_write_output={readiness.lane_write_output or 'none'} "
            f"lane_write_di={readiness.lane_write_di or 'none'} "
            f"lane_write_tag={readiness.lane_write_tag or 'none'} "
            f"lane_write_tag_class={readiness.lane_write_tag_class} "
            f"lane_write_debris_tag={1 if readiness.lane_write_tag_class == 'debris' else 0} "
            f"lane_write_active_count={readiness.lane_write_active_count or 'none'} "
            f"lane_write_loop_index={readiness.lane_write_loop_index or 'none'} "
            f"lane_write_result_local={readiness.lane_write_result_local or 'none'} "
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
        debris_tag_candidates=debris_tag_candidates,
        forward_debris_tag_candidates=forward_debris_tag_candidates,
        reverse_debris_tag_candidates=reverse_debris_tag_candidates,
        collapse_tag_candidates=collapse_tag_candidates,
        unknown_tag_candidates=unknown_tag_candidates,
        ready_manifest_lines=ready_manifest_records(
            manifest.path, environment_preflight, oracle_binary, readings
        ),
        forward_debris_route_candidates=forward_debris_readings,
        environment_preflight=environment_preflight,
        source_manifest=manifest.path,
    )


def write_ready_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def write_forward_debris_route_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def require_ready_error(readiness_counts: dict[str, int]) -> str | None:
    if readiness_counts.get("ready", 0) == 0:
        return (
            "lane_write_route_sweep_summary=error reason=no_ready_candidates "
            f"ready_candidates={readiness_counts.get('ready', 0)} "
            f"no_patch_candidates={readiness_counts.get('no_patch', 0)} "
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
        "lane_write_route_sweep_summary=error reason=candidates_not_ready "
        f"ready_candidates={readiness_counts.get('ready', 0)} "
        f"no_patch_candidates={readiness_counts.get('no_patch', 0)} "
        f"no_freeze_candidates={readiness_counts.get('no_freeze', 0)} "
        f"incomplete_candidates={readiness_counts.get('incomplete', 0)} "
        f"missing_candidates={readiness_counts.get('missing', 0)}"
    )


def require_environment_preflight_error(environment_preflight: str) -> str | None:
    if environment_preflight == "ok":
        return None
    return (
        "lane_write_route_sweep_summary=error "
        "reason=environment_preflight_not_ok "
        f"environment_preflight={environment_preflight}"
    )


def require_debris_tag_error(result: SummaryResult) -> str | None:
    if result.debris_tag_candidates > 0:
        return None
    return (
        "lane_write_route_sweep_summary=error reason=no_debris_tag_candidates "
        f"ready_candidates={result.readiness_counts.get('ready', 0)} "
        f"debris_tag_candidates={result.debris_tag_candidates} "
        f"collapse_tag_candidates={result.collapse_tag_candidates} "
        f"unknown_tag_candidates={result.unknown_tag_candidates}"
    )


def require_forward_debris_tag_error(result: SummaryResult) -> str | None:
    if result.forward_debris_tag_candidates > 0:
        return None
    return (
        "lane_write_route_sweep_summary=error "
        "reason=no_forward_debris_tag_candidates "
        f"ready_candidates={result.readiness_counts.get('ready', 0)} "
        f"debris_tag_candidates={result.debris_tag_candidates} "
        f"forward_debris_tag_candidates={result.forward_debris_tag_candidates} "
        f"reverse_debris_tag_candidates={result.reverse_debris_tag_candidates} "
        f"collapse_tag_candidates={result.collapse_tag_candidates} "
        f"unknown_tag_candidates={result.unknown_tag_candidates}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize lane-write route-sweep manifests."
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
        "--require-debris-tag",
        action="store_true",
        help=(
            "exit nonzero unless at least one ready lane-write candidate has "
            "a scratch tag at or above the 0x4e20 debris-marker base"
        ),
    )
    parser.add_argument(
        "--require-forward-debris-tag",
        action="store_true",
        help=(
            "exit nonzero unless at least one ready lane-write candidate is "
            "the natural forward debris writeback with a scratch tag at or "
            "above the 0x4e20 debris-marker base"
        ),
    )
    parser.add_argument(
        "--write-ready-manifest",
        type=Path,
        help="write a key/value manifest containing ready freeze candidates",
    )
    parser.add_argument(
        "--write-forward-debris-route-manifest",
        type=Path,
        help=(
            "write a lane_write_forward_debris_route_candidates manifest for "
            "routes satisfying --require-forward-debris-tag"
        ),
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
        print(f"lane_write_route_sweep_summary=error reason={exc}", file=sys.stderr)
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
            print(f"lane_write_ready_manifest=error reason={exc}", file=sys.stderr)
            return 1
        print(
            "lane_write_ready_manifest=ok "
            f"path={ready_manifest} "
            f"ready_candidates={result.readiness_counts.get('ready', 0)}"
        )
    if args.write_forward_debris_route_manifest is not None:
        if not args.require_forward_debris_tag:
            print(
                "lane_write_forward_debris_route_manifest=error "
                "reason=write_requires_require_forward_debris_tag",
                file=sys.stderr,
            )
            return 6
        error = require_forward_debris_tag_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 5
        try:
            route_manifest_lines = forward_debris_route_manifest_records(
                result.source_manifest,
                result.environment_preflight,
                result.forward_debris_route_candidates,
            )
            route_manifest = write_forward_debris_route_manifest(
                args.write_forward_debris_route_manifest,
                route_manifest_lines,
            )
        except (OSError, ValueError) as exc:
            print(
                f"lane_write_forward_debris_route_manifest=error reason={exc}",
                file=sys.stderr,
            )
            return 7
        matching_routes = next(
            (
                line.split("=", 1)[1]
                for line in route_manifest_lines
                if line.startswith("matching_routes=")
            ),
            "0",
        )
        print(
            "lane_write_forward_debris_route_manifest=ok "
            f"path={route_manifest} "
            f"matching_routes={matching_routes}"
        )
    if args.require_ready:
        error = require_ready_error(result.readiness_counts)
        if error is not None:
            print(error, file=sys.stderr)
            return 2
    if args.require_debris_tag:
        error = require_debris_tag_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 4
    if args.require_forward_debris_tag:
        error = require_forward_debris_tag_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 5
    if args.require_environment_preflight:
        error = require_environment_preflight_error(result.environment_preflight)
        if error is not None:
            print(error, file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
