#!/usr/bin/env python3
"""Summarize a single DOSBox-debug capture helper output directory."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import sys


CAPTURE_CONFIGS = {
    "behavior4_runtime": {
        "oracle": "behavior4",
        "flag": "--debug-behavior4-runtime-oracle",
        "required_keys": ["capture", "scenario", "level", "runtime_cs", "runtime_ds"],
        "required_records": ["spawner", "actor_before", "actor_after", "players"],
        "required_breaks": ["7a6b", "7c2c", "728c", "731b", "73e5", "741b"],
    },
    "actor_update_runtime": {
        "oracle": "actor_update",
        "flag": "--debug-actor-update-runtime-oracle",
        "required_keys": ["capture", "scenario", "level", "runtime_cs", "runtime_ds"],
        "required_records": ["actor_before", "actor_after", "contact_scan", "tile_probe"],
        "required_breaks": ["5cb0", "604f", "6053", "777f"],
    },
    "contact_scanner_runtime": {
        "oracle": "contact_scanner",
        "flag": "--debug-contact-scanner-runtime-oracle",
        "required_keys": ["capture", "scenario", "level", "runtime_cs", "runtime_ds"],
        "required_records": ["subject_actor", "other_actor", "contact_scan"],
        "required_record_fields": {
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
        },
        "required_breaks": ["5cb0", "604f"],
    },
    "visual_table": {
        "oracle": "visual_table",
        "flag": "--debug-visual-table-oracle",
        "required_keys": ["capture", "scenario", "level", "runtime_cs", "runtime_ds"],
        "required_records": ["actor", "visual", "effect_before", "effect_after"],
        "required_breaks": ["3108", "6053", "6148", "7c89", "7ddf"],
    },
}


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


def resolve_path(raw_path: str | None, manifest: Manifest) -> Path | None:
    if not raw_path:
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return manifest.path.parent / path


def fixture_lines(path: Path) -> tuple[list[str], list[str]]:
    all_lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    active_lines = [line for line in all_lines if not line.startswith("#")]
    return all_lines, active_lines


def candidate_readiness(capture: str, candidate: Path | None) -> CandidateReadiness:
    if candidate is None:
        return CandidateReadiness("none", [], False)
    if not candidate.exists():
        return CandidateReadiness("missing", ["file"], False)

    config = CAPTURE_CONFIGS[capture]
    all_lines, active_lines = fixture_lines(candidate)
    keys = {line.split("=", 1)[0] for line in active_lines if "=" in line}
    record_names = {
        line.split(" ", 1)[0]
        for line in active_lines
        if " " in line and "=" in line
    }
    record_fields = {
        record: {
            part.split("=", 1)[0]
            for part in line.split()[1:]
            if "=" in part
        }
        for line in active_lines
        if " " in line and "=" in line
        for record in [line.split(" ", 1)[0]]
    }
    break_offsets: set[str] = set()
    for line in active_lines:
        if not line.startswith("break "):
            continue
        match = re.search(r"\bghidra=1000:([0-9a-fA-F]{4})\b", line)
        if match:
            break_offsets.add(match.group(1).lower())

    missing = [key for key in config["required_keys"] if key not in keys]
    missing.extend(
        record
        for record in config["required_records"]
        if record not in record_names
    )
    for record, fields in config.get("required_record_fields", {}).items():
        if record not in record_names:
            continue
        present_fields = record_fields.get(record, set())
        missing.extend(
            f"{record}.{field}" for field in fields if field not in present_fields
        )
    missing.extend(
        f"break_{offset}"
        for offset in config["required_breaks"]
        if offset not in break_offsets
    )
    placeholders = any("<" in line or ">" in line for line in all_lines)
    status = "ready" if not missing and not placeholders else "incomplete"
    return CandidateReadiness(status, missing, placeholders)


def csv_or_none(values: list[str]) -> str:
    if not values:
        return "none"
    return ",".join(values)


def quote_command(command: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def display_path(path: Path | None) -> str:
    if path is None:
        return "none"
    return str(path.resolve())


def summarize(args: argparse.Namespace) -> tuple[str, Manifest, CandidateReadiness]:
    manifest = read_manifest(args.manifest)
    capture = manifest.values.get("capture", "unknown")
    if capture not in CAPTURE_CONFIGS:
        raise RuntimeError(f"unsupported capture type: {capture}")

    candidate = resolve_path(manifest.values.get("candidate_fixture"), manifest)
    readiness = candidate_readiness(capture, candidate)
    config = CAPTURE_CONFIGS[capture]
    oracle_command = "none"
    if candidate is not None:
        oracle_command = quote_command(
            [args.oracle_binary, config["flag"], str(candidate.resolve())]
        )

    fields = [
        "debug_capture_summary=ok",
        f"capture={capture}",
        f"scenario={manifest.values.get('scenario', 'unknown')}",
        f"level={manifest.values.get('expected_level', manifest.values.get('level', 'unknown'))}",
        f"route={manifest.values.get('route', 'unknown')}",
        f"environment_preflight={manifest.values.get('environment_preflight', 'unknown')}",
        f"runtime_metadata={manifest.values.get('runtime_metadata', 'unknown')}",
        f"runtime_cs={manifest.values.get('runtime_cs', 'unknown')}",
        f"runtime_ds={manifest.values.get('runtime_ds', 'unknown')}",
        f"candidate_status={readiness.status}",
        f"candidate_missing={csv_or_none(readiness.missing)}",
        f"candidate_placeholders={1 if readiness.placeholders else 0}",
        f"candidate_fixture={display_path(candidate)}",
        f"oracle={config['oracle']}",
        f"oracle_flag={config['flag']}",
        f"oracle_command={oracle_command}",
        f"manifest={manifest.path}",
        f"raw_dump={display_path(resolve_path(manifest.values.get('raw_debugger_dump'), manifest))}",
        f"debugger_commands_runtime={display_path(resolve_path(manifest.values.get('debugger_commands_runtime'), manifest))}",
        f"environment_preflight_log={display_path(resolve_path(manifest.values.get('environment_preflight_log'), manifest))}",
    ]
    return " ".join(fields), manifest, readiness


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Summarize DOSBox-debug capture helper artifacts."
    )
    parser.add_argument("manifest", type=Path, help="capture directory or manifest.txt")
    parser.add_argument(
        "--oracle-binary",
        default="./build/lezac_cpp",
        help="binary to use when printing the oracle command",
    )
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="exit nonzero unless the candidate fixture is promotion-ready",
    )
    parser.add_argument(
        "--require-environment-preflight",
        action="store_true",
        help="exit nonzero unless the manifest records environment_preflight=ok",
    )
    args = parser.parse_args()

    try:
        summary, manifest, readiness = summarize(args)
    except Exception as exc:
        print(f"debug_capture_summary=error reason={exc}", file=sys.stderr)
        return 1

    print(summary)

    if args.require_environment_preflight:
        preflight = manifest.values.get("environment_preflight", "unknown")
        if preflight != "ok":
            print(
                "debug_capture_summary=error "
                f"reason=environment_preflight_not_ok environment_preflight={preflight}",
                file=sys.stderr,
            )
            return 2
    if args.require_ready and readiness.status != "ready":
        print(
            "debug_capture_summary=error "
            f"reason=candidate_not_ready candidate_status={readiness.status} "
            f"candidate_missing={csv_or_none(readiness.missing)} "
            f"candidate_placeholders={1 if readiness.placeholders else 0}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
