#!/usr/bin/env python3
"""Summarize sound-callsite process-memory route-sweep manifests."""

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


CAPTURE_ROUTE_SWEEP = "sound_callsite_route_sweep"
ORACLE = "sound_callsite"
ORACLE_FLAG = "--debug-sound-callsite-oracle"
TARGETS = {
    "contact_scanner_runtime_sound": "5e81",
    "actor_update_runtime_cursor_0024_sound": "6844",
    "actor_update_runtime_cursor_0035_sound": "6924",
    "actor_update_runtime_cursor_0021_sound": "7386",
}
REQUIRED_KEYS = ["capture", "scenario", "level", "runtime_cs", "runtime_ds"]
REQUIRED_REQUEST_FIELDS = [
    "label",
    "callsite",
    "latch",
    "cursor",
    "priority",
    "active_before",
    "current_priority_before",
    "pending_cursor",
    "pending_priority",
    "accepted",
    "active_after",
    "current_priority_after",
    "current_cursor_after",
    "direct_sweep",
]


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
    values: dict[str, str]


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
    runtime_cs: str
    runtime_ds: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    details: list[str]
    readiness_counts: dict[str, int]
    observed_freezes: int
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


def label_parts(label: str, fallback_target: str) -> tuple[str, str, str]:
    for candidate_target in sorted(TARGETS, key=len, reverse=True):
        prefix = f"{candidate_target}_"
        if not label.startswith(prefix):
            continue
        rest = label[len(prefix) :]
        for timing in ["before_bomb", "before_route"]:
            timing_prefix = f"{timing}_"
            if rest.startswith(timing_prefix):
                return candidate_target, timing, rest[len(timing_prefix) :]
        return candidate_target, "unknown", rest
    for timing in ["before_bomb", "before_route"]:
        prefix = f"{timing}_"
        if label.startswith(prefix):
            return fallback_target, timing, label[len(prefix) :]
    return fallback_target, "unknown", label


def parse_record_fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in line.split()[1:]:
        key, separator, value = token.partition("=")
        if separator and key and value:
            fields[key] = value
    return fields


def fixture_lines(path: Path) -> tuple[list[str], list[str]]:
    all_lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    active_lines = [line for line in all_lines if not line.startswith("#")]
    return all_lines, active_lines


def target_for_candidate(
    fixture_values: dict[str, str], fallback_target: str
) -> str:
    return fixture_values.get("target") or fixture_values.get("scenario") or fallback_target


def candidate_readiness(
    candidate: Path | None, fallback_target: str
) -> CandidateReadiness:
    if candidate is None:
        return CandidateReadiness("missing", ["fixture"], False, {})
    if not candidate.exists():
        return CandidateReadiness("missing", ["file"], False, {})

    all_lines, active_lines = fixture_lines(candidate)
    values: dict[str, str] = {}
    break_offsets: set[str] = set()
    sound_request_fields: dict[str, str] | None = None
    for line in active_lines:
        if "=" in line and not line.startswith("break ") and " " not in line:
            key, value = line.split("=", 1)
            values[key] = value
            continue
        if line.startswith("break "):
            match = re.search(r"\bghidra=1000:([0-9a-fA-F]{4})\b", line)
            if match:
                break_offsets.add(match.group(1).lower())
            continue
        if line.startswith("sound_request "):
            sound_request_fields = parse_record_fields(line)

    target = target_for_candidate(values, fallback_target)
    target_offset = TARGETS.get(target)
    missing = [key for key in REQUIRED_KEYS if key not in values]
    if values.get("capture") not in {None, "sound_callsite"}:
        missing.append("capture_sound_callsite")
    if target_offset is None:
        missing.append("target_known")
    else:
        for offset in [target_offset, "165a"]:
            if offset not in break_offsets:
                missing.append(f"break_{offset}")
    if sound_request_fields is None:
        missing.append("sound_request")
    else:
        missing.extend(
            f"sound_request_{field}"
            for field in REQUIRED_REQUEST_FIELDS
            if field not in sound_request_fields
        )
    placeholders = any("<" in line or ">" in line for line in all_lines)
    status = "ready" if not missing and not placeholders else "incomplete"
    return CandidateReadiness(status, missing, placeholders, values)


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
    label_target, timing, route_label = label_parts(
        label, manifest.values.get("target", "unknown")
    )
    target = fields.get("target", label_target)
    candidate = resolve_child_path(fields.get("candidate_fixture"), manifest.path)
    readiness = candidate_readiness(candidate, target)
    freeze_observed = bool_value(
        fields.get("freeze_observed") or fields.get("instrumented_freeze_observed")
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
        runtime_cs=fields.get("runtime_cs", readiness.values.get("runtime_cs", "unknown")),
        runtime_ds=fields.get("runtime_ds", readiness.values.get("runtime_ds", "unknown")),
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
    details: list[str] = []
    ready_manifests: list[str] = []
    missing_labels: list[str] = []
    for capture_summary in captures:
        readiness_counts[capture_summary.readiness.status] += 1
        if capture_summary.freeze_observed:
            observed_freezes += 1
        if capture_summary.readiness.status == "ready":
            ready_manifests.append(str(capture_summary.candidate))
        if capture_summary.readiness.status == "missing":
            missing_labels.append(capture_summary.label)
        details.append(
            "sound_callsite_route_sweep_detail "
            f"label={capture_summary.label} "
            f"target={capture_summary.target} "
            f"timing={capture_summary.timing} "
            f"route_label={capture_summary.route_label} "
            f"candidate_status={capture_summary.readiness.status} "
            f"candidate_missing={csv_or_none(capture_summary.readiness.missing)} "
            f"candidate_placeholders={1 if capture_summary.readiness.placeholders else 0} "
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
            "sound_callsite_route_sweep_summary=ok",
            f"target={manifest.values.get('target', 'unknown')}",
            f"targets={manifest.values.get('targets', 'unknown')}",
            f"target_names={manifest.values.get('target_names', 'unknown')}",
            f"timings={manifest.values.get('timings', 'unknown')}",
            f"routes={manifest.values.get('routes', 'unknown')}",
            f"route_labels={manifest.values.get('route_labels', 'unknown')}",
            f"capture_commands={len(labels)}",
            f"completed_captures={len([c for c in captures if c.status_line])}",
            f"observed_freezes={observed_freezes}",
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
        scenario = capture.readiness.values.get("scenario", capture.target)
        level = capture.readiness.values.get("level", "unknown")
        lines.extend(
            [
                f"{prefix}_capture=sound_callsite",
                f"{prefix}_scenario={scenario}",
                f"{prefix}_level={level}",
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
        description="Summarize sound-callsite process-memory route-sweep artifacts."
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
        "--require-environment-preflight",
        action="store_true",
        help="exit nonzero unless the sweep manifest records environment_preflight=ok",
    )
    parser.add_argument(
        "--write-ready-manifest",
        type=Path,
        help=(
            "write a debug_capture_ready_candidates manifest for ready "
            "sound-callsite candidates"
        ),
    )
    args = parser.parse_args()

    try:
        result = summarize(args)
    except Exception as exc:
        print(f"sound_callsite_route_sweep_summary=error reason={exc}", file=sys.stderr)
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
                f"sound_callsite_ready_manifest=error reason={exc}",
                file=sys.stderr,
            )
            return 5
        print(
            "sound_callsite_ready_manifest=ok "
            f"path={ready_manifest} "
            f"ready_candidates={result.readiness_counts['ready']}"
        )

    if args.require_environment_preflight and result.environment_preflight != "ok":
        print(
            "sound_callsite_route_sweep_summary=error "
            f"reason=environment_preflight_not_ok "
            f"environment_preflight={result.environment_preflight}",
            file=sys.stderr,
        )
        return 2
    if args.require_ready and (
        result.readiness_counts["incomplete"] or result.readiness_counts["missing"]
    ):
        print(
            "sound_callsite_route_sweep_summary=error "
            "reason=candidates_not_ready "
            f"incomplete_candidates={result.readiness_counts['incomplete']} "
            f"missing_candidates={result.readiness_counts['missing']}",
            file=sys.stderr,
        )
        return 3
    if args.require_observed_freeze and result.observed_freezes == 0:
        print(
            "sound_callsite_route_sweep_summary=error "
            "reason=no_observed_freezes",
            file=sys.stderr,
        )
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
