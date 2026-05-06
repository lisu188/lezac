#!/usr/bin/env python3
"""Verify lane-result freeze patch descriptions without DOSBox/procmem access."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys


EXPECTED_BODY_PATCH = (
    "30e42ea380f28cc02ea382f22e893e84f28b46042ea386f28b46062ea388f2"
    "8a46f330e42ea38af28b46f02ea38cf28b46f62ea38ef2268a0530e42ea390f2ebfe"
)
EXPECTED_RESULT_WRITE_TAIL = (
    "8b46f63b46f075c58a46f3c47e04268805c9c20600"
)

EXPECTED_DESCRIPTIONS = {
    "1000:3D3F": {
        "ghidra_offset": 0x3D3F,
        "image_base": 0x0770,
        "file_offset": 0x44AF,
        "patch_bytes": "e9beb4",
    },
    "1000:3ED3": {
        "ghidra_offset": 0x3ED3,
        "image_base": 0x0770,
        "file_offset": 0x4643,
        "patch_bytes": "e92ab3",
    },
}


def load_capture_module():
    module_path = Path(__file__).with_name("capture_original_explosion_procmem.py")
    spec = importlib.util.spec_from_file_location(
        "capture_original_explosion_procmem", module_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to import {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require_equal(actual, expected, field: str, offset: str) -> None:
    if actual != expected:
        raise RuntimeError(
            f"{offset} {field} mismatch: expected {expected!r} actual {actual!r}"
        )


def check_offset(module, asset_dir: Path, offset: str, verbose: bool) -> None:
    description = module.describe_freeze_patch(
        asset_dir,
        module.parse_ghidra_offset(offset),
        module.FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH,
    )
    expected = EXPECTED_DESCRIPTIONS[offset]
    for field, value in expected.items():
        require_equal(description[field], value, field, offset)
    for field, value in {
        "patch_mode": module.FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH,
        "expected_original_bytes": "268805",
        "original_bytes": "268805",
        "patch_length": 3,
        "scratch_offset": 0xF280,
        "scratch_length": 0x12,
        "body_offset": 0xF200,
        "body_length": 65,
        "body_patch_bytes": EXPECTED_BODY_PATCH,
    }.items():
        require_equal(description[field], value, field, offset)
    exe = asset_dir / "LEZAC.EXE"
    data = exe.read_bytes()
    tail_start = description["file_offset"] - 14
    tail_end = description["file_offset"] + 7
    require_equal(
        data[tail_start:tail_end].hex(),
        EXPECTED_RESULT_WRITE_TAIL,
        "result_write_tail_bytes",
        offset,
    )
    if verbose:
        print(
            "lane_result_preflight_offset=ok "
            f"offset={offset} file_offset=0x{description['file_offset']:04x} "
            f"patch_bytes={description['patch_bytes']} "
            f"body_length={description['body_length']} result_tail=1 "
            f"result_tail_bytes={EXPECTED_RESULT_WRITE_TAIL}"
        )


def check_wrong_offset_guard(module, asset_dir: Path) -> None:
    try:
        module.describe_freeze_patch(
            asset_dir,
            module.parse_ghidra_offset("1000:3D2D"),
            module.FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH,
        )
    except RuntimeError as exc:
        if "only valid at 1000:3D3F or 1000:3ED3" in str(exc):
            return
        raise RuntimeError(f"unexpected wrong-offset error: {exc}") from exc
    raise RuntimeError("wrong-offset guard did not reject 1000:3D2D")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check lane-result freeze patch descriptions without launching DOSBox "
            "or reading process memory."
        )
    )
    parser.add_argument(
        "asset_dir",
        nargs="?",
        default=Path(__file__).resolve().parent.parent,
        type=Path,
        help="directory containing LEZAC.EXE; defaults to the repository root",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print one status line per checked offset",
    )
    args = parser.parse_args()

    module = load_capture_module()
    asset_dir = args.asset_dir.resolve()
    for offset in EXPECTED_DESCRIPTIONS:
        check_offset(module, asset_dir, offset, args.verbose)
    check_wrong_offset_guard(module, asset_dir)
    print(
        "lane_result_preflight=ok "
        f"asset_dir={asset_dir} offsets=1000:3D3F,1000:3ED3 "
        "expected_original_bytes=268805 scratch_offset=0xf280 "
        f"body_offset=0xf200 result_tail=1 "
        f"result_tail_bytes={EXPECTED_RESULT_WRITE_TAIL} wrong_offset_guard=1"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
