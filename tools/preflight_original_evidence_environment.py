#!/usr/bin/env python3
"""Report whether this host can run original LEZAC evidence captures."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


ASSET_FILES = [
    "LEZAC.EXE",
    "BOMPAL.PAL",
    "LIVELS.SCH",
    "BOMOMIMK.SPR",
    "FONTS.SPR",
]
TOOL_NAMES = [
    "bash",
    "dosbox",
    "dosbox-debug",
    "xvfb-run",
    "xdotool",
    "python3",
    "pgrep",
    "zutty",
    "script",
    "Xvfb",
    "timeout",
]
REQUIREMENT_SETS = {
    "original_capture": [
        "bash",
        "dosbox",
        "dosbox-debug",
        "xvfb-run",
        "xdotool",
        "timeout",
    ],
    "frame_capture": ["bash", "dosbox", "xvfb-run", "xdotool"],
    "debug_capture": ["bash", "dosbox-debug", "xvfb-run", "timeout"],
    "procmem_capture": [
        "bash",
        "dosbox",
        "dosbox-debug",
        "Xvfb",
        "xdotool",
        "python3",
        "pgrep",
        "zutty",
        "script",
    ],
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def host_label() -> str:
    system = platform.system().lower()
    if system.startswith("windows"):
        return "windows"
    if system.startswith("linux"):
        return "linux"
    if system.startswith("darwin"):
        return "macos"
    return system or "unknown"


def clean_output(raw: bytes) -> str:
    if not raw:
        return ""
    if raw.count(b"\x00") > max(2, len(raw) // 8):
        text = raw.decode("utf-16le", errors="replace")
    else:
        text = raw.decode("utf-8", errors="replace")
    return " ".join(text.replace("\x00", "").split())


def run_command(command: list[str], timeout_seconds: float = 5.0) -> tuple[int, str]:
    resolved = shutil.which(command[0])
    actual_command = [resolved, *command[1:]] if resolved else command
    try:
        result = subprocess.run(
            actual_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout_seconds,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, str(exc)
    return result.returncode, clean_output(result.stdout)


def wsl_reason(output: str) -> str:
    lowered = output.lower()
    if "wsl_e_default_distro_not_found" in lowered:
        return "no_default_distro"
    if "no installed distributions" in lowered:
        return "no_default_distro"
    if "not recognized" in lowered or "not found" in lowered:
        return "missing_command"
    if not output:
        return "none"
    return "other"


def tool_status(name: str) -> tuple[str, str]:
    path = shutil.which(name)
    if path is None:
        return "missing", "none"
    return "found", path


def asset_status(root: Path) -> tuple[str, list[str]]:
    missing = [name for name in ASSET_FILES if not (root / name).exists()]
    if missing:
        return "missing", missing
    return "ok", []


def requirement_names(args: argparse.Namespace) -> list[str]:
    names: list[str] = []
    if args.require_original_capture:
        names.append("original_capture")
    if args.require_frame_capture:
        names.append("frame_capture")
    if args.require_debug_capture:
        names.append("debug_capture")
    if args.require_procmem_capture:
        names.append("procmem_capture")
    return names


def csv_or_none(values: list[str]) -> str:
    if not values:
        return "none"
    return ",".join(values)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preflight local tools needed for original DOSBox evidence."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    parser.add_argument(
        "--require-assets",
        action="store_true",
        help="exit nonzero if shipped LEZAC assets are missing",
    )
    parser.add_argument(
        "--require-original-capture",
        action="store_true",
        help="require the full original capture toolchain",
    )
    parser.add_argument(
        "--require-frame-capture",
        action="store_true",
        help="require the original DOSBox screenshot/frame toolchain",
    )
    parser.add_argument(
        "--require-debug-capture",
        action="store_true",
        help="require DOSBox-debug capture tools",
    )
    parser.add_argument(
        "--require-procmem-capture",
        action="store_true",
        help="require process-memory capture tools",
    )
    parser.add_argument(
        "--probe-wsl",
        action="store_true",
        help="also run `wsl --status` when the wsl command exists",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    assets, missing_assets = asset_status(root)
    tools = {name: tool_status(name) for name in TOOL_NAMES}
    wsl_status, wsl_path = tool_status("wsl")
    wsl_probe = "not_run"
    wsl_bash_probe = "not_run"
    wsl_bash_reason = "not_run"
    if args.probe_wsl and wsl_status == "found":
        code, status_output = run_command(["wsl", "--status"])
        wsl_probe = "ok" if code == 0 else f"error_{code}"
        bash_code, bash_output = run_command(["wsl", "-e", "bash", "-lc", "true"])
        wsl_bash_probe = "ok" if bash_code == 0 else f"error_{bash_code}"
        wsl_bash_reason = wsl_reason(bash_output)
        if wsl_bash_probe == "ok":
            wsl_bash_reason = "none"
        elif wsl_bash_reason == "none":
            wsl_bash_reason = wsl_reason(status_output)
    elif args.probe_wsl:
        wsl_bash_probe = "missing"
        wsl_bash_reason = "missing_command"

    required_sets = requirement_names(args)
    required_tools: list[str] = []
    for name in required_sets:
        for tool in REQUIREMENT_SETS[name]:
            if tool not in required_tools:
                required_tools.append(tool)
    missing_required = [
        tool for tool in required_tools if tools.get(tool, ("missing", ""))[0] != "found"
    ]
    require_assets = args.require_assets or bool(required_sets)

    summary_fields = [
        "original_evidence_environment=ok",
        f"host={host_label()}",
        f"root={root}",
        f"assets={assets}",
        f"missing_assets={csv_or_none(missing_assets)}",
        f"required={csv_or_none(required_sets)}",
        f"missing_required={csv_or_none(missing_required)}",
        f"wsl={wsl_status}",
        f"wsl_probe={wsl_probe}",
        f"wsl_bash_probe={wsl_bash_probe}",
        f"wsl_bash_reason={wsl_bash_reason}",
    ]
    for name in TOOL_NAMES:
        status, path = tools[name]
        summary_fields.append(f"tool_{name.replace('-', '_')}={status}")
        summary_fields.append(f"path_{name.replace('-', '_')}={path}")
    print(" ".join(summary_fields))

    if require_assets and assets != "ok":
        print(
            "original_evidence_environment=error "
            f"reason=missing_assets missing_assets={csv_or_none(missing_assets)}",
            file=sys.stderr,
        )
        return 2
    if missing_required:
        print(
            "original_evidence_environment=error "
            f"reason=missing_required missing_required={csv_or_none(missing_required)}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
