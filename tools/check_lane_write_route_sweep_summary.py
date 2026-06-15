#!/usr/bin/env python3
"""Exercise lane-write route-sweep summary and promotion output."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


READY_FIXTURE = """capture=explosion_playback
source=dosbox-regular-process-memory
temp_copy=1
visual_claim=0
runtime_cs=01ED
runtime_ds=0C8F
instrumented_freeze_observed=1
instrumented_freeze_patch_mode=lane-write-cs-scratch
instrumented_lane_write_scratch_present=1
instrumented_lane_write_cs_offset=0xf080
instrumented_lane_write_kind=forward
instrumented_lane_write_target=debris
instrumented_lane_write_output=0x0035
instrumented_lane_write_di=0x0898
instrumented_lane_write_tag=0x4ee8
instrumented_lane_write_active_count=0x0001
instrumented_lane_write_loop_index=0x0001
instrumented_lane_write_result_local=0x0035
runtime_freeze_patch_applied=1
runtime_freeze_old_bytes=889597
"""


NO_FREEZE_FIXTURE = """capture=explosion_playback
source=dosbox-regular-process-memory
temp_copy=1
visual_claim=0
runtime_cs=01ED
runtime_ds=0C8F
instrumented_freeze_observed=0
instrumented_freeze_patch_mode=lane-write-cs-scratch
instrumented_lane_write_scratch_present=0
instrumented_lane_write_cs_offset=0xf080
instrumented_lane_write_kind=forward
instrumented_lane_write_target=debris
runtime_freeze_patch_applied=1
runtime_freeze_old_bytes=889597
"""


INCOMPLETE_FIXTURE = """capture=explosion_playback
source=dosbox-regular-process-memory
temp_copy=1
visual_claim=0
runtime_cs=01ED
runtime_ds=0C8F
instrumented_freeze_observed=1
instrumented_freeze_patch_mode=lane-write-cs-scratch
instrumented_lane_write_scratch_present=1
instrumented_lane_write_cs_offset=0xf080
instrumented_lane_write_kind=forward
instrumented_lane_write_target=debris
instrumented_lane_write_output=0x0035
instrumented_lane_write_di=0x0898
instrumented_lane_write_tag=0x4ee8
instrumented_lane_write_active_count=0x0001
runtime_freeze_patch_applied=1
runtime_freeze_old_bytes=889597
"""


SEEDED_FIXTURE = READY_FIXTURE + "runtime_seeded=1\n"


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")
    return path


def runtime_manifest(path: Path, fixture: Path | None, offset: str = "3d2d") -> Path:
    lines = [
        "capture=lane_write_runtime",
        f"offset_labels={offset}",
        f"offset_addresses=1000:{offset.upper()}",
    ]
    if fixture is not None:
        lines.append(f"candidate_{offset}={fixture}")
    return write(path, "\n".join(lines) + "\n")


def route_manifest(
    path: Path,
    child_manifest: Path | None,
    *,
    environment_preflight: str = "ok",
    route_label: str = "x2p00",
) -> Path:
    lines = [
        "capture=lane_write_route_sweep",
        "offset=forward",
        "routes=1",
        f"route_labels={route_label}",
        f"environment_preflight={environment_preflight}",
    ]
    if child_manifest is not None:
        lines.append(
            f"capture_status_{route_label}=lane_write_capture_orchestrator=ok "
            f"mode=capture manifest={child_manifest} candidates=1 "
            "offset_labels=3d2d offset_addresses=1000:3D2D"
        )
    else:
        lines.append(
            f"capture_status_{route_label}=lane_write_capture_orchestrator=ok "
            "mode=capture candidates=0 offset_labels=3d2d"
        )
    return write(path, "\n".join(lines) + "\n")


def run_summary(
    root: Path, manifest: Path, extra: list[str] | None = None, expect_success: bool = True
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_lane_write_route_sweep.py"),
        str(manifest),
        *(extra or []),
    ]
    result = subprocess.run(
        command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"summary command failed with {result.returncode}: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"summary command unexpectedly passed: {' '.join(command)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-write route-sweep summary behavior."
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
        help="repository root containing tools",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    cases = 0

    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-summary-") as tmp:
        base = Path(tmp)
        ready_fixture = write(base / "ready.txt", READY_FIXTURE)
        no_freeze_fixture = write(base / "no-freeze.txt", NO_FREEZE_FIXTURE)
        incomplete_fixture = write(base / "incomplete.txt", INCOMPLETE_FIXTURE)
        seeded_fixture = write(base / "seeded.txt", SEEDED_FIXTURE)

        ready_runtime = runtime_manifest(base / "ready-runtime.txt", ready_fixture)
        ready = run_summary(root, ready_runtime)
        for snippet in [
            "lane_write_route_sweep_summary=ok",
            "capture=lane_write_runtime",
            "mode=runtime",
            "routes=1",
            "candidates=1",
            "ready_candidates=1",
            "observed_offsets=3d2d",
            "missing_offsets=none",
            "candidate_status=ready",
            "lane_write_present=1",
            "--debug-explosion-playback-oracle",
        ]:
            require(ready, snippet, "ready_runtime")
        cases += 1

        no_freeze_runtime = runtime_manifest(
            base / "no-freeze-runtime.txt", no_freeze_fixture
        )
        no_freeze = run_summary(root, no_freeze_runtime)
        for snippet in [
            "ready_candidates=0",
            "no_freeze_candidates=1",
            "observed_offsets=none",
            "missing_offsets=3d2d",
            "candidate_status=no_freeze",
            "freeze_observed=0",
        ]:
            require(no_freeze, snippet, "no_freeze")
        cases += 1

        incomplete_runtime = runtime_manifest(
            base / "incomplete-runtime.txt", incomplete_fixture
        )
        incomplete = run_summary(root, incomplete_runtime)
        for snippet in [
            "incomplete_candidates=1",
            "candidate_status=incomplete",
            "candidate_missing=instrumented_lane_write_loop_index",
        ]:
            require(incomplete, snippet, "incomplete")
        cases += 1

        seeded_runtime = runtime_manifest(base / "seeded-runtime.txt", seeded_fixture)
        seeded = run_summary(root, seeded_runtime)
        require(seeded, "candidate_missing=runtime_seeded_not_natural", "seeded")
        cases += 1

        missing_runtime = runtime_manifest(base / "missing-runtime.txt", None)
        missing = run_summary(root, missing_runtime)
        require(missing, "missing_candidates=1", "missing")
        require(missing, "candidate_status=missing", "missing")
        cases += 1

        route_child = runtime_manifest(base / "route-child.txt", ready_fixture)
        route = route_manifest(base / "route" / "manifest.txt", route_child)
        route_summary = run_summary(root, route)
        for snippet in [
            "capture=lane_write_route_sweep",
            "mode=route",
            "environment_preflight=ok",
            "routes=1",
            "ready_candidates=1",
            "source_manifest=",
        ]:
            require(route_summary, snippet, "route")
        cases += 1

        ready_manifest = base / "ready-manifest.txt"
        route_ready = run_summary(
            root,
            route,
            ["--require-ready", "--write-ready-manifest", str(ready_manifest)],
        )
        require(route_ready, "lane_write_ready_manifest=ok", "ready_manifest")
        ready_text = ready_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=lane_write_ready_candidates",
            "ready_candidates=1",
            "candidate_0_route=x2p00",
            "candidate_0_offset_address=1000:3D2D",
            "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(ready_text, snippet, "ready_manifest_file")
        cases += 1

        no_ready = run_summary(
            root, no_freeze_runtime, ["--require-ready"], expect_success=False
        )
        require(no_ready, "reason=no_ready_candidates", "no_ready")
        cases += 1

        bad_environment = route_manifest(
            base / "bad-env" / "manifest.txt",
            route_child,
            environment_preflight="skipped",
        )
        bad_env = run_summary(
            root,
            bad_environment,
            ["--require-environment-preflight"],
            expect_success=False,
        )
        require(bad_env, "reason=environment_preflight_not_ok", "bad_env")
        cases += 1

        missing_manifest = run_summary(
            root,
            base / "missing-manifest.txt",
            expect_success=False,
        )
        require(missing_manifest, "manifest not found", "missing_manifest")
        cases += 1

    print(f"lane_write_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
