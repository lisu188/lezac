#!/usr/bin/env python3
"""Check original-evidence environment preflight behavior."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile


FAKE_REQUIRED = ["bash", "dosbox", "dosbox-debug", "xvfb-run", "xdotool"]
ASSET_FILES = ["LEZAC.EXE", "BOMPAL.PAL", "LIVELS.SCH", "BOMOMIMK.SPR", "FONTS.SPR"]


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_preflight(
    root: Path,
    args: list[str],
    env: dict[str, str] | None = None,
    expect_success: bool = True,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "preflight_original_evidence_environment.py"),
        *args,
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        env=env,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"preflight failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"preflight unexpectedly passed: {' '.join(args)}\n{result.stdout}"
        )
    return result.stdout


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def make_assets(root: Path) -> None:
    for name in ASSET_FILES:
        write_text(root / name, "placeholder\n")


def make_fake_tool(bin_dir: Path, name: str) -> None:
    if os.name == "nt":
        write_text(
            bin_dir / f"{name}.cmd",
            "\r\n".join(["@echo off", f"echo fake {name}", "exit /b 0", ""]),
        )
        return
    path = bin_dir / name
    write_text(path, "\n".join(["#!/bin/sh", f"echo fake {name}", "exit 0", ""]))
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def fake_env(bin_dir: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = str(bin_dir)
    return env


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check original evidence environment preflight output."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    current = run_preflight(root, [str(root)])
    require(current, "original_evidence_environment=ok", "current_report")
    require(current, "required=none", "current_report")
    require(current, "missing_required=none", "current_report")
    cases += 1

    with tempfile.TemporaryDirectory(prefix="lezac-evidence-env-") as tmp:
        base = Path(tmp)
        asset_root = base / "assets"
        make_assets(asset_root)

        fake_bin = base / "fake-bin"
        fake_bin.mkdir()
        for name in FAKE_REQUIRED:
            make_fake_tool(fake_bin, name)
        ok = run_preflight(
            root,
            [str(asset_root), "--require-original-capture"],
            env=fake_env(fake_bin),
        )
        for snippet in [
            "original_evidence_environment=ok",
            "assets=ok",
            "required=original_capture",
            "missing_required=none",
            "tool_bash=found",
            "tool_dosbox=found",
            "tool_dosbox_debug=found",
            "tool_xvfb_run=found",
            "tool_xdotool=found",
        ]:
            require(ok, snippet, "fake_original_capture")
        cases += 1

        debug_bin = base / "debug-bin"
        debug_bin.mkdir()
        for name in ["bash", "dosbox-debug", "xvfb-run"]:
            make_fake_tool(debug_bin, name)
        debug = run_preflight(
            root,
            [str(asset_root), "--require-debug-capture"],
            env=fake_env(debug_bin),
        )
        require(debug, "required=debug_capture", "debug_capture")
        require(debug, "missing_required=none", "debug_capture")
        cases += 1

        missing_bin = base / "missing-bin"
        missing_bin.mkdir()
        missing = run_preflight(
            root,
            [str(asset_root), "--require-original-capture"],
            env=fake_env(missing_bin),
            expect_success=False,
        )
        require(missing, "reason=missing_required", "missing_required")
        for name in ["bash", "dosbox", "dosbox-debug", "xvfb-run", "xdotool"]:
            require(missing, name, "missing_required")
        cases += 1

        empty_root = base / "empty-root"
        empty_root.mkdir()
        asset_error = run_preflight(
            root,
            [str(empty_root), "--require-assets"],
            expect_success=False,
        )
        require(asset_error, "reason=missing_assets", "missing_assets")
        require(asset_error, "LEZAC.EXE", "missing_assets")
        cases += 1

        procmem_bin = base / "procmem-bin"
        procmem_bin.mkdir()
        for name in [*FAKE_REQUIRED, "python3", "pgrep"]:
            make_fake_tool(procmem_bin, name)
        procmem = run_preflight(
            root,
            [str(asset_root), "--require-procmem-capture"],
            env=fake_env(procmem_bin),
        )
        require(procmem, "required=procmem_capture", "procmem_capture")
        require(procmem, "tool_python3=found", "procmem_capture")
        require(procmem, "tool_pgrep=found", "procmem_capture")
        cases += 1

    print(f"original_evidence_environment_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
