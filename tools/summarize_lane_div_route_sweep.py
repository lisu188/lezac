#!/usr/bin/env python3
"""Summarize original lane-div route-sweep manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import sys


CAPTURE_ROUTE_SWEEP = "lane_div_route_sweep"
CAPTURE_PROCMEM = "original_explosion_process_memory"
ORACLE = "explosion_playback"
ORACLE_FLAG = "--debug-explosion-playback-oracle"
FORWARD_ROUTE_PROMOTION = "lane_div_forward_route_candidates"
OFFSET_ADDRESSES = {
    "3cd4": "1000:3CD4",
    "3ce3": "1000:3CE3",
    "3e68": "1000:3E68",
    "3e77": "1000:3E77",
}
OFFSET_MODEL = {
    "3cd4": ("forward", "setup"),
    "3ce3": ("forward", "divide"),
    "3e68": ("reverse", "setup"),
    "3e77": ("reverse", "divide"),
}
LANE_DIV_FIELDS = [
    "ax",
    "dx",
    "cx",
    "bx",
    "active_count",
    "loop_index",
    "weight_local",
    "numerator_low",
    "numerator_high",
]


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
    lane_div_present: bool
    lane_div_kind: str
    lane_div_phase: str
    runtime_cs: str
    runtime_ds: str
    lane_div_ax: str
    lane_div_dx: str
    lane_div_cx: str
    lane_div_bx: str
    lane_div_active_count: str
    lane_div_loop_index: str
    lane_div_weight_local: str
    lane_div_numerator_low: str
    lane_div_numerator_high: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    forward_candidates: int
    forward_divide_candidates: int
    forward_setup_candidates: int
    reverse_candidates: int
    reverse_divide_candidates: int
    reverse_setup_candidates: int
    forward_route_candidates: list[tuple[Candidate, CandidateReadiness]]
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


def offset_label_from_address(value: str) -> str:
    if ":" in value:
        return value.split(":", 1)[1].lower()
    return value.lower()


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


def expected_model(offset_label: str) -> tuple[str, str] | None:
    return OFFSET_MODEL.get(offset_label_from_address(offset_label))


def empty_readiness(status: str, missing: list[str]) -> CandidateReadiness:
    return CandidateReadiness(
        status=status,
        missing=missing,
        placeholders=False,
        patch_applied=False,
        freeze_observed=False,
        lane_div_present=False,
        lane_div_kind="",
        lane_div_phase="",
        runtime_cs="",
        runtime_ds="",
        lane_div_ax="",
        lane_div_dx="",
        lane_div_cx="",
        lane_div_bx="",
        lane_div_active_count="",
        lane_div_loop_index="",
        lane_div_weight_local="",
        lane_div_numerator_low="",
        lane_div_numerator_high="",
    )


def candidate_readiness(candidate: Candidate) -> CandidateReadiness:
    if candidate.fixture is None:
        return empty_readiness("missing", ["fixture"])
    if not candidate.fixture.exists():
        return empty_readiness("missing", ["file"])

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
        "instrumented_lane_div_cs_offset",
        "instrumented_lane_div_kind",
        "runtime_freeze_patch_applied",
    ]
    if patch_applied:
        required_keys.append("runtime_freeze_old_bytes")
    missing = [key for key in required_keys if not values.get(key)]
    freeze_observed = bool_value(values.get("instrumented_freeze_observed"))
    lane_div_present = bool_value(values.get("instrumented_lane_div_scratch_present"))
    lane_div_kind = values.get("instrumented_lane_div_kind", "")
    lane_div_phase = ""
    if values.get("instrumented_freeze_patch_mode") != "lane-div-cs-scratch":
        missing.append("lane_div_patch_mode")
    model = expected_model(candidate.offset_label)
    if model is None:
        missing.append("known_lane_div_offset")
    else:
        expected_kind, lane_div_phase = model
        if lane_div_kind != expected_kind:
            missing.append(f"lane_div_kind_{expected_kind}")
    if lane_div_present:
        lane_keys = [f"instrumented_lane_div_{field}" for field in LANE_DIV_FIELDS]
        missing.extend(key for key in lane_keys if not values.get(key))
    elif freeze_observed:
        missing.append("instrumented_lane_div_scratch")

    if missing or placeholders:
        status = "incomplete"
    elif not patch_applied:
        status = "no_patch"
    elif freeze_observed and lane_div_present:
        status = "ready"
    else:
        status = "no_freeze"
    return CandidateReadiness(
        status=status,
        missing=missing,
        placeholders=placeholders,
        patch_applied=patch_applied,
        freeze_observed=freeze_observed,
        lane_div_present=lane_div_present,
        lane_div_kind=lane_div_kind,
        lane_div_phase=lane_div_phase,
        runtime_cs=values.get("runtime_cs", ""),
        runtime_ds=values.get("runtime_ds", ""),
        lane_div_ax=values.get("instrumented_lane_div_ax", ""),
        lane_div_dx=values.get("instrumented_lane_div_dx", ""),
        lane_div_cx=values.get("instrumented_lane_div_cx", ""),
        lane_div_bx=values.get("instrumented_lane_div_bx", ""),
        lane_div_active_count=values.get("instrumented_lane_div_active_count", ""),
        lane_div_loop_index=values.get("instrumented_lane_div_loop_index", ""),
        lane_div_weight_local=values.get("instrumented_lane_div_weight_local", ""),
        lane_div_numerator_low=values.get("instrumented_lane_div_numerator_low", ""),
        lane_div_numerator_high=values.get("instrumented_lane_div_numerator_high", ""),
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


def is_forward_ready(readiness: CandidateReadiness) -> bool:
    return readiness.status == "ready" and readiness.lane_div_kind == "forward"


def is_forward_divide_ready(readiness: CandidateReadiness) -> bool:
    return is_forward_ready(readiness) and readiness.lane_div_phase == "divide"


def forward_route_manifest_records(
    source_manifest: Path,
    source_environment_preflight: str,
    candidates: list[tuple[Candidate, CandidateReadiness]],
) -> list[str]:
    matching: list[tuple[Candidate, CandidateReadiness]] = []
    seen_routes: set[str] = set()
    for candidate, readiness in candidates:
        if not is_forward_divide_ready(readiness):
            continue
        if candidate.route_label in seen_routes:
            continue
        seen_routes.add(candidate.route_label)
        matching.append((candidate, readiness))
    lines = [
        f"promotion={FORWARD_ROUTE_PROMOTION}",
        f"source_manifest={source_manifest}",
        f"source_environment_preflight={source_environment_preflight}",
        "required_candidate=forward_divide",
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
                f"{prefix}_lane_div_weight_local={readiness.lane_div_weight_local}",
                f"{prefix}_lane_div_numerator_low={readiness.lane_div_numerator_low}",
                f"{prefix}_lane_div_numerator_high={readiness.lane_div_numerator_high}",
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
    forward_readings = [
        (candidate, readiness)
        for candidate, readiness in readings
        if is_forward_ready(readiness)
    ]
    forward_candidates = len(forward_readings)
    forward_divide_readings = [
        (candidate, readiness)
        for candidate, readiness in readings
        if is_forward_divide_ready(readiness)
    ]
    forward_divide_candidates = len(forward_divide_readings)
    forward_setup_candidates = sum(
        1
        for _, readiness in readings
        if is_forward_ready(readiness) and readiness.lane_div_phase == "setup"
    )
    reverse_candidates = sum(
        1
        for _, readiness in readings
        if readiness.status == "ready" and readiness.lane_div_kind == "reverse"
    )
    reverse_divide_candidates = sum(
        1
        for _, readiness in readings
        if (
            readiness.status == "ready"
            and readiness.lane_div_kind == "reverse"
            and readiness.lane_div_phase == "divide"
        )
    )
    reverse_setup_candidates = sum(
        1
        for _, readiness in readings
        if (
            readiness.status == "ready"
            and readiness.lane_div_kind == "reverse"
            and readiness.lane_div_phase == "setup"
        )
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
        "lane_div_route_sweep_summary=ok "
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
        f"forward_candidates={forward_candidates} "
        f"forward_divide_candidates={forward_divide_candidates} "
        f"forward_setup_candidates={forward_setup_candidates} "
        f"reverse_candidates={reverse_candidates} "
        f"reverse_divide_candidates={reverse_divide_candidates} "
        f"reverse_setup_candidates={reverse_setup_candidates} "
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
            f"kind={readiness.lane_div_kind or 'unknown'} "
            f"phase={readiness.lane_div_phase or 'unknown'} "
            f"runtime_cs={readiness.runtime_cs or 'unknown'} "
            f"runtime_ds={readiness.runtime_ds or 'unknown'} "
            f"patch_applied={1 if readiness.patch_applied else 0} "
            f"freeze_observed={1 if readiness.freeze_observed else 0} "
            f"lane_div_present={1 if readiness.lane_div_present else 0} "
            f"lane_div_ax={readiness.lane_div_ax or 'none'} "
            f"lane_div_dx={readiness.lane_div_dx or 'none'} "
            f"lane_div_cx={readiness.lane_div_cx or 'none'} "
            f"lane_div_bx={readiness.lane_div_bx or 'none'} "
            f"lane_div_active_count={readiness.lane_div_active_count or 'none'} "
            f"lane_div_loop_index={readiness.lane_div_loop_index or 'none'} "
            f"lane_div_weight_local={readiness.lane_div_weight_local or 'none'} "
            f"lane_div_numerator_low={readiness.lane_div_numerator_low or 'none'} "
            f"lane_div_numerator_high={readiness.lane_div_numerator_high or 'none'} "
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
        forward_candidates=forward_candidates,
        forward_divide_candidates=forward_divide_candidates,
        forward_setup_candidates=forward_setup_candidates,
        reverse_candidates=reverse_candidates,
        reverse_divide_candidates=reverse_divide_candidates,
        reverse_setup_candidates=reverse_setup_candidates,
        forward_route_candidates=forward_divide_readings,
        environment_preflight=environment_preflight,
        source_manifest=manifest.path,
    )


def write_forward_route_manifest(path: Path, lines: list[str]) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def require_ready_error(result: SummaryResult) -> str | None:
    if result.readiness_counts.get("ready", 0) == 0:
        return (
            "lane_div_route_sweep_summary=error reason=no_ready_candidates "
            f"ready_candidates={result.readiness_counts.get('ready', 0)} "
            f"no_patch_candidates={result.readiness_counts.get('no_patch', 0)} "
            f"no_freeze_candidates={result.readiness_counts.get('no_freeze', 0)} "
            f"incomplete_candidates={result.readiness_counts.get('incomplete', 0)} "
            f"missing_candidates={result.readiness_counts.get('missing', 0)}"
        )
    not_ready = result.readiness_counts.get("incomplete", 0) + result.readiness_counts.get(
        "missing", 0
    )
    if not_ready == 0:
        return None
    return (
        "lane_div_route_sweep_summary=error reason=candidates_not_ready "
        f"ready_candidates={result.readiness_counts.get('ready', 0)} "
        f"no_patch_candidates={result.readiness_counts.get('no_patch', 0)} "
        f"no_freeze_candidates={result.readiness_counts.get('no_freeze', 0)} "
        f"incomplete_candidates={result.readiness_counts.get('incomplete', 0)} "
        f"missing_candidates={result.readiness_counts.get('missing', 0)}"
    )


def require_forward_divide_error(result: SummaryResult) -> str | None:
    if result.forward_divide_candidates > 0:
        return None
    return (
        "lane_div_route_sweep_summary=error "
        "reason=no_forward_divide_candidates "
        f"ready_candidates={result.readiness_counts.get('ready', 0)} "
        f"forward_candidates={result.forward_candidates} "
        f"forward_divide_candidates={result.forward_divide_candidates} "
        f"forward_setup_candidates={result.forward_setup_candidates} "
        f"reverse_candidates={result.reverse_candidates}"
    )


def require_environment_preflight_error(environment_preflight: str) -> str | None:
    if environment_preflight == "ok":
        return None
    return (
        "lane_div_route_sweep_summary=error "
        "reason=environment_preflight_not_ok "
        f"environment_preflight={environment_preflight}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize lane-div route-sweep manifests."
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
        help="exit nonzero unless at least one lane-div freeze candidate is ready",
    )
    parser.add_argument(
        "--require-forward-divide",
        action="store_true",
        help="exit nonzero unless at least one ready forward 1000:3CE3 divide is observed",
    )
    parser.add_argument(
        "--write-forward-route-manifest",
        type=Path,
        help=(
            "write a lane_div_forward_route_candidates manifest for routes "
            "satisfying --require-forward-divide"
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
        print(f"lane_div_route_sweep_summary=error reason={exc}", file=sys.stderr)
        return 1
    print(result.summary)
    for detail in result.details:
        print(detail)
    if args.write_forward_route_manifest is not None:
        if not args.require_forward_divide:
            print(
                "lane_div_forward_route_manifest=error "
                "reason=write_requires_require_forward_divide",
                file=sys.stderr,
            )
            return 5
        error = require_forward_divide_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 4
        try:
            route_manifest_lines = forward_route_manifest_records(
                result.source_manifest,
                result.environment_preflight,
                result.forward_route_candidates,
            )
            route_manifest = write_forward_route_manifest(
                args.write_forward_route_manifest,
                route_manifest_lines,
            )
        except (OSError, ValueError) as exc:
            print(f"lane_div_forward_route_manifest=error reason={exc}", file=sys.stderr)
            return 6
        matching_routes = next(
            (
                line.split("=", 1)[1]
                for line in route_manifest_lines
                if line.startswith("matching_routes=")
            ),
            "0",
        )
        print(
            "lane_div_forward_route_manifest=ok "
            f"path={route_manifest} "
            f"matching_routes={matching_routes}"
        )
    if args.require_ready:
        error = require_ready_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 2
    if args.require_forward_divide:
        error = require_forward_divide_error(result)
        if error is not None:
            print(error, file=sys.stderr)
            return 4
    if args.require_environment_preflight:
        error = require_environment_preflight_error(result.environment_preflight)
        if error is not None:
            print(error, file=sys.stderr)
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
