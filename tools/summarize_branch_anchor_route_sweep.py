#!/usr/bin/env python3
"""Summarize original high-debris branch-anchor route-sweep manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys


CAPTURE_ROUTE_SWEEP = "branch_anchor_route_sweep"
TARGETS = {
    "high_debris_loop_entry": ("1000:492F", "loop"),
    "high_debris_target_sample": ("1000:4B3F", "loop"),
    "high_debris_target_byte_gate": ("1000:4B61", "loop"),
    "high_debris_zero_target_branch": ("1000:4B6A", "loop"),
    "high_debris_nonzero_target_branch": ("1000:4C20", "loop"),
    "high_debris_word_gate": ("1000:4C75", "bp4-cs-scratch"),
    "effect_forward_pass_call": ("1000:4C96", "loop"),
    "effect_reverse_pass_call": ("1000:4CA9", "loop"),
}
BP4_SCRATCH_OFFSET = "0x4c7e"


@dataclass(frozen=True)
class Manifest:
    path: Path
    values: dict[str, str]
    entries: list[tuple[str, str]]


@dataclass(frozen=True)
class Candidate:
    label: str
    target: str
    timing: str
    route_label: str
    offset: str
    patch_mode: str
    fixture: Path | None
    source_manifest: Path | None


@dataclass(frozen=True)
class CandidateReadiness:
    status: str
    missing: list[str]
    placeholders: bool
    patch_applied: bool
    freeze_observed: bool
    runtime_cs: str
    runtime_ds: str
    bp4_local_present: bool
    bp4_local_value: str
    high_debris_target_byte: str
    high_debris_word_layer_value: str
    patch_elapsed: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    observed_targets: list[str]
    observed_routes: list[str]
    route_hits: dict[str, list[str]]
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
    return [item for item in value.split(",") if item]


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


def csv_or_none(values: list[str]) -> str:
    ordered = unique_ordered(values)
    if not ordered:
        return "none"
    return ",".join(ordered)


def missing_or_none(values: list[str]) -> str:
    if not values:
        return "none"
    return ",".join(values)


def unique_ordered(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def wsl_drive_mount_to_windows_path(raw_path: str) -> Path | None:
    normalized = raw_path.replace("\\", "/")
    match = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", normalized)
    if match is None:
        return None
    drive = match.group(1).upper()
    rest = match.group(2) or ""
    return Path(f"{drive}:/{rest}")


def resolve_child_path(raw_path: str | None, parent_manifest: Path) -> Path | None:
    if raw_path is None:
        return None
    translated = wsl_drive_mount_to_windows_path(raw_path)
    if translated is not None and sys.platform == "win32":
        return translated
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return parent_manifest.parent / path


def target_from_label(label: str, fields: dict[str, str]) -> tuple[str, str, str]:
    target = fields.get("target", "unknown")
    route_label = fields.get("route", "unknown")
    timing = "unknown"
    for candidate_target in sorted(TARGETS, key=len, reverse=True):
        prefix = f"{candidate_target}_"
        if not label.startswith(prefix):
            continue
        target = candidate_target
        rest = label[len(prefix) :]
        for candidate_timing in ["before_bomb", "after_bomb", "selected_base"]:
            timing_prefix = f"{candidate_timing}_"
            if rest.startswith(timing_prefix):
                timing = candidate_timing
                route_label = rest[len(timing_prefix) :]
                return target, timing, route_label
    return target, timing, route_label


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


def collect_candidates(manifest: Manifest) -> list[Candidate]:
    candidates: list[Candidate] = []
    for key, value in manifest.entries:
        if not key.startswith("capture_status_"):
            continue
        label = key.removeprefix("capture_status_")
        fields = parse_status_fields(value)
        target, timing, route_label = target_from_label(label, fields)
        expected_offset, expected_patch_mode = TARGETS.get(target, ("unknown", "unknown"))
        source_manifest = resolve_child_path(fields.get("manifest"), manifest.path)
        fixture = resolve_child_path(fields.get("candidate"), manifest.path)
        if fixture is None and source_manifest is not None and source_manifest.exists():
            child = read_manifest(source_manifest)
            fixture = resolve_child_path(child.values.get("fixture_candidate"), child.path)
        candidates.append(
            Candidate(
                label=label,
                target=target,
                timing=timing,
                route_label=route_label,
                offset=fields.get("offset", expected_offset),
                patch_mode=fields.get("patch_mode", expected_patch_mode),
                fixture=fixture,
                source_manifest=source_manifest,
            )
        )
    return candidates


def candidate_readiness(candidate: Candidate) -> CandidateReadiness:
    if candidate.fixture is None:
        return CandidateReadiness(
            "missing", ["fixture"], False, False, False, "", "", False, "", "", "", ""
        )
    if not candidate.fixture.exists():
        return CandidateReadiness(
            "missing", ["file"], False, False, False, "", "", False, "", "", "", ""
        )

    values, nonempty = active_values(candidate.fixture)
    placeholders = any("<" in line or ">" in line for line in nonempty)
    patch_applied = bool_value(values.get("runtime_freeze_patch_applied"))
    freeze_observed = bool_value(values.get("instrumented_freeze_observed"))
    runtime_cs = values.get("runtime_cs", "")
    runtime_ds = values.get("runtime_ds", "")
    patch_mode = values.get("instrumented_freeze_patch_mode", "")
    expected_offset, expected_patch_mode = TARGETS.get(candidate.target, ("", ""))
    required = [
        "capture",
        "source",
        "temp_copy",
        "visual_claim",
        "runtime_cs",
        "runtime_ds",
        "instrumented_freeze_observed",
        "instrumented_freeze_patch_mode",
        "runtime_freeze_patch_applied",
    ]
    if patch_applied:
        required.append("runtime_freeze_old_bytes")
    missing = [key for key in required if not values.get(key)]
    if expected_offset and candidate.offset.upper() != expected_offset:
        missing.append(f"target_offset_{expected_offset}")
    if expected_patch_mode and patch_mode != expected_patch_mode:
        missing.append(f"patch_mode_{expected_patch_mode}")

    bp4_local_present = bool_value(values.get("instrumented_bp4_local_present"))
    bp4_local_value = values.get("instrumented_bp4_local_value", "")
    if candidate.target == "high_debris_word_gate":
        if freeze_observed and not bp4_local_present:
            missing.append("instrumented_bp4_local_present")
        if values.get("instrumented_bp4_local_cs_offset", "").lower() != BP4_SCRATCH_OFFSET:
            missing.append("instrumented_bp4_local_cs_offset_4c7e")
        if freeze_observed and not bp4_local_value:
            missing.append("instrumented_bp4_local_value")

    if missing or placeholders:
        status = "incomplete"
    elif not patch_applied:
        status = "no_patch"
    elif freeze_observed:
        status = "ready"
    else:
        status = "no_freeze"

    return CandidateReadiness(
        status=status,
        missing=missing,
        placeholders=placeholders,
        patch_applied=patch_applied,
        freeze_observed=freeze_observed,
        runtime_cs=runtime_cs,
        runtime_ds=runtime_ds,
        bp4_local_present=bp4_local_present,
        bp4_local_value=bp4_local_value,
        high_debris_target_byte=values.get("runtime_freeze_patch_high_debris_target_byte")
        or values.get("high_debris_target_byte", ""),
        high_debris_word_layer_value=values.get(
            "runtime_freeze_patch_high_debris_word_layer_value"
        )
        or values.get("high_debris_word_layer_value", ""),
        patch_elapsed=values.get("runtime_freeze_patch_elapsed_after_bomb", ""),
    )


def summarize(manifest: Manifest) -> SummaryResult:
    capture = manifest.values.get("capture", "unknown")
    if capture != CAPTURE_ROUTE_SWEEP:
        raise ValueError(
            f"unsupported manifest capture {capture!r}; expected {CAPTURE_ROUTE_SWEEP!r}"
        )
    candidates = collect_candidates(manifest)
    readings = [(candidate, candidate_readiness(candidate)) for candidate in candidates]
    readiness_counts = {
        "ready": 0,
        "no_patch": 0,
        "no_freeze": 0,
        "incomplete": 0,
        "missing": 0,
    }
    for _, readiness in readings:
        readiness_counts[readiness.status] = readiness_counts.get(readiness.status, 0) + 1
    route_hits: dict[str, list[str]] = {}
    for candidate, readiness in readings:
        if readiness.status != "ready":
            continue
        route_hits.setdefault(candidate.route_label, [])
        if candidate.target not in route_hits[candidate.route_label]:
            route_hits[candidate.route_label].append(candidate.target)
    observed_targets = unique_ordered(
        [candidate.target for candidate, readiness in readings if readiness.status == "ready"]
    )
    observed_routes = [route for route, targets in route_hits.items() if targets]
    expected_targets = parse_csv(manifest.values.get("targets"))
    missing_targets = [target for target in expected_targets if target not in observed_targets]
    route_hits_summary = [
        f"{route}:{','.join(targets)}" for route, targets in sorted(route_hits.items())
    ]
    environment_preflight = manifest.values.get("environment_preflight", "unknown")
    summary = (
        "branch_anchor_route_sweep_summary=ok "
        f"manifest={manifest.path} "
        f"environment_preflight={environment_preflight} "
        f"targets={manifest.values.get('targets', 'unknown')} "
        f"timings={manifest.values.get('timings', 'unknown')} "
        f"routes={manifest.values.get('routes', 'unknown')} "
        f"route_labels={manifest.values.get('route_labels', 'unknown')} "
        f"candidates={len(readings)} "
        f"observed_freezes={readiness_counts['ready']} "
        f"ready_candidates={readiness_counts['ready']} "
        f"no_patch_candidates={readiness_counts['no_patch']} "
        f"no_freeze_candidates={readiness_counts['no_freeze']} "
        f"incomplete_candidates={readiness_counts['incomplete']} "
        f"missing_candidates={readiness_counts['missing']} "
        f"observed_targets={csv_or_none(observed_targets)} "
        f"missing_targets={csv_or_none(missing_targets)} "
        f"observed_routes={csv_or_none(observed_routes)} "
        f"route_hits={csv_or_none(route_hits_summary)}"
    )
    details: list[str] = []
    for candidate, readiness in readings:
        details.append(
            "branch_anchor_route_sweep_detail "
            f"label={candidate.label} "
            f"target={candidate.target} "
            f"timing={candidate.timing} "
            f"route={candidate.route_label} "
            f"offset={candidate.offset} "
            f"patch_mode={candidate.patch_mode} "
            f"candidate_status={readiness.status} "
            f"candidate_missing={missing_or_none(readiness.missing)} "
            f"candidate_placeholders={1 if readiness.placeholders else 0} "
            f"patch_applied={1 if readiness.patch_applied else 0} "
            f"freeze_observed={1 if readiness.freeze_observed else 0} "
            f"runtime_cs={readiness.runtime_cs or 'unknown'} "
            f"runtime_ds={readiness.runtime_ds or 'unknown'} "
            f"bp4_local_present={1 if readiness.bp4_local_present else 0} "
            f"bp4_local_value={readiness.bp4_local_value or 'none'} "
            f"high_debris_target_byte={readiness.high_debris_target_byte or 'none'} "
            f"high_debris_word_layer_value={readiness.high_debris_word_layer_value or 'none'} "
            f"patch_elapsed_after_bomb={readiness.patch_elapsed or 'none'} "
            f"candidate_fixture={candidate.fixture or 'none'} "
            f"source_manifest={candidate.source_manifest or 'none'}"
        )
    return SummaryResult(
        summary=summary,
        details=details,
        readiness_counts=readiness_counts,
        observed_targets=observed_targets,
        observed_routes=observed_routes,
        route_hits=route_hits,
        environment_preflight=environment_preflight,
    )


def require_targets_error(result: SummaryResult, required_targets: list[str]) -> str | None:
    missing = [target for target in required_targets if target not in result.observed_targets]
    if not missing:
        return None
    return (
        "branch_anchor_route_sweep_summary=error reason=missing_required_targets "
        f"required_targets={csv_or_none(required_targets)} "
        f"missing_targets={csv_or_none(missing)} "
        f"observed_targets={csv_or_none(result.observed_targets)}"
    )


def require_route_with_targets_error(
    result: SummaryResult, required_targets: list[str]
) -> str | None:
    matches = [
        route
        for route, targets in result.route_hits.items()
        if all(target in targets for target in required_targets)
    ]
    if matches:
        return None
    return (
        "branch_anchor_route_sweep_summary=error reason=no_route_with_required_targets "
        f"required_targets={csv_or_none(required_targets)} "
        f"matching_routes=none observed_routes={csv_or_none(result.observed_routes)}"
    )


def require_environment_preflight_error(result: SummaryResult) -> str | None:
    if result.environment_preflight == "ok":
        return None
    return (
        "branch_anchor_route_sweep_summary=error "
        "reason=environment_preflight_not_ok "
        f"environment_preflight={result.environment_preflight}"
    )


def parse_target_csv(value: str) -> list[str]:
    targets = parse_csv(value)
    if not targets:
        raise argparse.ArgumentTypeError("target list must not be empty")
    invalid = [target for target in targets if target not in TARGETS]
    if invalid:
        raise argparse.ArgumentTypeError(f"unknown target(s): {','.join(invalid)}")
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize high-debris branch-anchor route-sweep manifests."
    )
    parser.add_argument("manifest", type=Path, help="manifest.txt or sweep directory")
    parser.add_argument(
        "--require-target",
        action="append",
        choices=sorted(TARGETS),
        help="exit nonzero unless this target has at least one ready freeze",
    )
    parser.add_argument(
        "--require-route-with-targets",
        type=parse_target_csv,
        help=(
            "comma-separated targets; exit nonzero unless at least one route "
            "has ready freezes for all listed targets"
        ),
    )
    parser.add_argument(
        "--require-environment-preflight",
        action="store_true",
        help="exit nonzero unless the source sweep manifest records environment_preflight=ok",
    )
    args = parser.parse_args()

    try:
        result = summarize(read_manifest(args.manifest))
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"branch_anchor_route_sweep_summary=error reason={exc}", file=sys.stderr)
        return 1
    print(result.summary)
    for detail in result.details:
        print(detail)

    if args.require_target:
        error = require_targets_error(result, args.require_target)
        if error is not None:
            print(error, file=sys.stderr)
            return 2
    if args.require_route_with_targets:
        error = require_route_with_targets_error(result, args.require_route_with_targets)
        if error is not None:
            print(error, file=sys.stderr)
            return 3
    if args.require_environment_preflight:
        error = require_environment_preflight_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
