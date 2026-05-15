#!/usr/bin/env python3
"""Run or dry-run lane-write ready-candidate oracle manifests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def load_lane_result_runner():
    script = Path(__file__).resolve().parent / "run_lane_result_ready_manifest.py"
    spec = importlib.util.spec_from_file_location("lane_result_ready_runner", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_lane_result_runner()
    module.EXPECTED_PROMOTION = "lane_write_ready_candidates"
    module.TOOL_PREFIX = "lane_write"
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
