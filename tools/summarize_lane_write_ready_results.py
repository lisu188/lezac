#!/usr/bin/env python3
"""Summarize lane-write ready-manifest oracle result manifests."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


def load_lane_result_summarizer():
    script = Path(__file__).resolve().parent / "summarize_lane_result_ready_results.py"
    spec = importlib.util.spec_from_file_location("lane_result_ready_results", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    module = load_lane_result_summarizer()
    module.EXPECTED_RESULT = "lane_write_ready_manifest"
    module.TOOL_PREFIX = "lane_write"
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
