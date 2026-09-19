#!/usr/bin/env python3
"""Ensure capture and validation helpers cannot inherit an audible SDL driver."""

import importlib
import os
from pathlib import Path
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SHELL_LAUNCHERS = (
    "capture_cpp_frames.sh",
    "capture_original_actor_contact_procmem.sh",
    "capture_original_actor_update_debug.sh",
    "capture_original_behavior4_debug.sh",
    "capture_original_behavior4_procmem.sh",
    "capture_original_contact_scanner_debug.sh",
    "capture_original_dosbox_frames.sh",
    "capture_original_sound_callsite_debug.sh",
    "capture_original_sound_callsite_procmem.sh",
    "capture_original_state2_visual_frames.sh",
    "capture_original_visual_table_debug.sh",
    "compare_original_cpp_frames.sh",
    "test_ui_xdotool.sh",
)
RUNNERS = (
    "run_actor_dispatch_ready_manifest",
    "run_debug_capture_ready_manifest",
    "run_lane_result_ready_manifest",
    "run_lane_write_ready_manifest",
)


def main():
    prologue = "#!/usr/bin/env bash\nset -euo pipefail\nexport SDL_AUDIODRIVER=dummy\n"
    for name in SHELL_LAUNCHERS:
        source = (ROOT / "tools" / name).read_text(encoding="utf-8")
        if not source.startswith(prologue) or source.count("SDL_AUDIODRIVER") != 1:
            raise RuntimeError(f"{name}: silent audio must be exported before any child")
    native = (ROOT / "tools/run_native_windows_validation.ps1").read_text(encoding="utf-8")
    if '$ErrorActionPreference = "Stop"\n$env:SDL_AUDIODRIVER = "dummy"\n' not in native:
        raise RuntimeError("Windows validation must force silent audio before running commands")

    grandchild = "import os; print(os.environ.get('SDL_AUDIODRIVER', 'missing'))"
    child = (
        "import os, subprocess, sys; "
        "print(os.environ.get('SDL_AUDIODRIVER', 'missing'), flush=True); "
        f"subprocess.run([sys.executable, '-c', {grandchild!r}], check=True)"
    )
    cases = 0
    for name in RUNNERS:
        runner = importlib.import_module(name)
        for inherited in (None, "", "pulseaudio", "wasapi"):
            with patch.dict(os.environ):
                if inherited is None:
                    os.environ.pop("SDL_AUDIODRIVER", None)
                else:
                    os.environ["SDL_AUDIODRIVER"] = inherited
                status, output, log = runner.run_candidate(
                    [sys.executable, "-c", child], None, 10.0, None
                )
                if status != 0 or output.splitlines() != ["dummy", "dummy"] or log != "none":
                    raise RuntimeError(f"{name}: inherited={inherited!r} status={status}: {output}")
                if os.environ.get("SDL_AUDIODRIVER") != inherited:
                    raise RuntimeError(f"{name}: changed the caller's environment")
            cases += 1
    print(f"silent_launchers=ok shell_policies={len(SHELL_LAUNCHERS)} native_policy=1 child_cases={cases} grandchildren={cases} games_started=0")


if __name__ == "__main__":
    main()
