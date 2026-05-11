#!/usr/bin/env python3
"""Summarize actor dispatch-gate sweep manifests."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys


CAPTURE_DISPATCH_SWEEP = "actor_dispatch_gate_sweep"
CAPTURE_ROUTE_SWEEP = "actor_contact_route_sweep"


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


def summarize(manifest: Manifest) -> tuple[str, list[str]]:
    capture = manifest.values.get("capture", "unknown")
    if capture == CAPTURE_DISPATCH_SWEEP:
        child_manifests = dispatch_child_manifests(manifest)
        targets = parse_csv(manifest.values.get("targets"))
        statuses: list[CaptureStatus] = []
        for target, child in child_manifests:
            statuses.extend(route_statuses(child, default_target=target))
        mode = "dispatch"
        route_sweeps = len(child_manifests)
    elif capture == CAPTURE_ROUTE_SWEEP:
        targets = parse_csv(manifest.values.get("target"))
        statuses = route_statuses(manifest)
        mode = "route"
        route_sweeps = 1
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
    missing_targets = [target for target in targets if target not in observed_targets]
    candidate_fixtures = [
        status.fields.get("candidate_fixture", "")
        for status in freezes
        if status.fields.get("candidate_fixture")
    ]
    summary = (
        "actor_dispatch_gate_sweep_summary=ok "
        f"manifest={manifest.path} "
        f"capture={capture} "
        f"mode={mode} "
        f"targets={len(targets)} "
        f"route_sweeps={route_sweeps} "
        f"captures={len(statuses)} "
        f"freezes={len(freezes)} "
        f"observed_targets={csv_or_none(observed_targets)} "
        f"missing_targets={csv_or_none(missing_targets)} "
        f"candidate_fixtures={csv_or_none(candidate_fixtures)}"
    )
    details = [
        "freeze "
        f"target={status.target} "
        f"route={status.route_label} "
        f"ghidra={status.fields.get('ghidra', 'unknown')} "
        f"runtime_cs={status.fields.get('runtime_cs', 'unknown')} "
        f"runtime_ds={status.fields.get('runtime_ds', 'unknown')} "
        f"freeze_runtime={status.fields.get('freeze_runtime', 'unknown')} "
        f"candidate_fixture={status.fields.get('candidate_fixture', 'none')} "
        f"raw_dump={status.fields.get('raw_dump', 'none')}"
        for status in freezes
    ]
    return summary, details


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Summarize actor dispatch-gate or actor/contact route sweep manifests."
        )
    )
    parser.add_argument("manifest", type=Path, help="manifest.txt or sweep output dir")
    args = parser.parse_args()

    try:
        summary, details = summarize(read_manifest(args.manifest))
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"actor_dispatch_gate_sweep_summary=error reason={exc}", file=sys.stderr)
        return 1
    print(summary)
    for detail in details:
        print(detail)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
