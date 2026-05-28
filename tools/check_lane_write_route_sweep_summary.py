#!/usr/bin/env python3
"""Exercise lane-write route-sweep summary and promotion output."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ready_result_checker_support import write_original_fixture_tree


OFFSET_MODEL = {
    "3d1b": ("1000:3D1B", "forward", "collapse", "888517"),
    "3d2d": ("1000:3D2D", "forward", "debris", "889597"),
    "3eaf": ("1000:3EAF", "reverse", "collapse", "888518"),
    "3ec1": ("1000:3EC1", "reverse", "debris", "889598"),
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_summary(
    root: Path,
    args: list[str],
    expect_success: bool = True,
    env: dict[str, str] | None = None,
) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_lane_write_route_sweep.py"),
        *args,
    ]
    process_env = os.environ.copy()
    if env is not None:
        process_env.update(env)
    result = subprocess.run(
        command,
        cwd=root,
        env=process_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if expect_success and result.returncode != 0:
        raise RuntimeError(
            f"summary command failed with {result.returncode}: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"summary command unexpectedly passed: {' '.join(args)}\n"
            f"{result.stdout}"
        )
    return result.stdout


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}\n{text}")


def write_candidate(
    path: Path,
    offset_label: str,
    freeze: bool,
    placeholder: bool = False,
) -> None:
    _, kind, target, old_bytes = OFFSET_MODEL[offset_label]
    lane_lines = []
    if freeze:
        lane_lines = [
            "instrumented_lane_write_scratch_present=1",
            "instrumented_lane_write_output=0x0035",
            "instrumented_lane_write_di=0x0898",
            "instrumented_lane_write_tag=0x4ee8",
            "instrumented_lane_write_active_count=0x0001",
            "instrumented_lane_write_loop_index=0x0001",
            "instrumented_lane_write_result_local=0x0035",
        ]
    else:
        lane_lines = ["instrumented_lane_write_scratch_present=0"]
    if placeholder:
        lane_lines.append("# fill me: <instrumented_lane_write_output>")
    write_text(
        path,
        "\n".join(
            [
                "capture=explosion_playback",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "instrumented_freeze_observed=" + ("1" if freeze else "0"),
                "instrumented_freeze_patch_mode=lane-write-cs-scratch",
                "instrumented_lane_write_cs_offset=0xf080",
                f"instrumented_lane_write_kind={kind}",
                f"instrumented_lane_write_target={target}",
                "runtime_freeze_patch_applied=1",
                f"runtime_freeze_old_bytes={old_bytes}",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                *lane_lines,
                "",
            ]
        ),
    )


def write_runtime_manifest(path: Path, candidate: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=original_explosion_process_memory",
                "asset_dir=/repo",
                f"fixture_candidate={candidate}",
                "",
            ]
        ),
    )


def write_route_sweep(
    path: Path,
    entries: list[tuple[str, str, Path, Path]],
    offset_labels: list[str] | None = None,
) -> None:
    labels = [route for route, _, _, _ in entries]
    if offset_labels is None:
        offset_labels = [offset for _, offset, _, _ in entries]
    offset_addresses = [OFFSET_MODEL[offset][0] for offset in offset_labels]
    lines = [
        "capture=lane_write_route_sweep",
        "asset_dir=/repo",
        f"offsets={len(offset_labels)}",
        "offset_labels=" + ",".join(offset_labels),
        "offset_addresses=" + ",".join(offset_addresses),
        f"routes={len(labels)}",
        "route_labels=" + ",".join(labels),
        "environment_preflight=ok",
    ]
    for route, offset, child, candidate in entries:
        lines.append(
            f"capture_status_{route}_{offset}=lane_write_capture=ok "
            f"route={route} offset={offset} offset_address={OFFSET_MODEL[offset][0]} "
            f"manifest={child} candidate={candidate}"
        )
    lines.append("")
    write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-write route-sweep summary behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-write-summary-") as tmp:
        base = Path(tmp)
        ready_candidate = base / "ready" / "candidate.txt"
        no_freeze_candidate = base / "no_freeze" / "candidate.txt"
        incomplete_candidate = base / "incomplete" / "candidate.txt"
        write_candidate(ready_candidate, "3d2d", freeze=True)
        write_candidate(no_freeze_candidate, "3ec1", freeze=False)
        write_candidate(incomplete_candidate, "3d2d", freeze=True, placeholder=True)

        ready_manifest = base / "ready" / "manifest.txt"
        no_freeze_manifest = base / "no_freeze" / "manifest.txt"
        incomplete_manifest = base / "incomplete" / "manifest.txt"
        write_runtime_manifest(ready_manifest, ready_candidate)
        write_runtime_manifest(no_freeze_manifest, no_freeze_candidate)
        write_runtime_manifest(incomplete_manifest, incomplete_candidate)

        sweep_manifest = base / "manifest.txt"
        write_route_sweep(
            sweep_manifest,
            [
                ("ready", "3d2d", ready_manifest, ready_candidate),
                ("no_freeze", "3ec1", no_freeze_manifest, no_freeze_candidate),
            ],
            ["3d2d", "3ec1"],
        )
        summary = run_summary(root, [str(sweep_manifest)])
        for snippet in [
            "lane_write_route_sweep_summary=ok",
            "mode=route",
            "environment_preflight=ok",
            "routes=2",
            "candidates=2",
            "observed_freezes=1",
            "ready_candidates=1",
            "no_freeze_candidates=1",
            "incomplete_candidates=0",
            "missing_candidates=0",
            "observed_offsets=3d2d",
            "missing_offsets=3ec1",
            "candidate route=ready offset=3d2d",
            "kind=forward",
            "target=debris",
            "candidate_status=ready",
            "candidate route=no_freeze offset=3ec1",
            "candidate_status=no_freeze",
            "oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(summary, snippet, "mixed_summary")
        cases += 1

        required = run_summary(root, [str(sweep_manifest), "--require-ready"])
        require(required, "ready_candidates=1", "mixed_require_ready")
        cases += 1

        required_preflight = run_summary(
            root, [str(sweep_manifest), "--require-environment-preflight"]
        )
        require(
            required_preflight,
            "environment_preflight=ok",
            "mixed_require_environment_preflight",
        )
        cases += 1

        promotion_manifest = base / "promotion" / "manifest.txt"
        promoted = run_summary(
            root,
            [
                str(sweep_manifest),
                "--write-ready-manifest",
                str(promotion_manifest),
            ],
        )
        require(promoted, "lane_write_ready_manifest=ok", "promotion_output")
        require(promoted, f"path={promotion_manifest.resolve()}", "promotion_output")
        promotion_text = promotion_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=lane_write_ready_candidates",
            "ready_candidates=1",
            "source_environment_preflight=ok",
            "candidate_0_route=ready",
            "candidate_0_offset_label=3d2d",
            "candidate_0_offset_address=1000:3D2D",
            "candidate_0_lane_write_kind=forward",
            "candidate_0_lane_write_target=debris",
            f"candidate_0_fixture={ready_candidate}",
            "candidate_0_oracle=explosion_playback",
            "candidate_0_oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(promotion_text, snippet, "promotion_manifest")
        cases += 1

        original_root = base / "original_root"
        original_fixture = write_original_fixture_tree(
            original_root,
            "explosion_playback_oracle_original_lane_write_unledgered.txt",
            runtime_ds="0C8F",
            include_ledger_entry=False,
        )
        write_candidate(original_fixture, "3d2d", freeze=True)
        bad_original_runtime = base / "bad_original" / "manifest.txt"
        write_runtime_manifest(bad_original_runtime, original_fixture)
        bad_original_sweep = base / "bad_original_sweep.txt"
        write_route_sweep(
            bad_original_sweep,
            [("original", "3d2d", bad_original_runtime, original_fixture)],
            ["3d2d"],
        )
        bad_original = run_summary(
            root,
            [
                str(bad_original_sweep),
                "--write-ready-manifest",
                str(base / "bad_original_promotion.txt"),
            ],
            expect_success=False,
            env={"LEZAC_READY_RESULT_REPO_ROOT": str(original_root)},
        )
        require(
            bad_original,
            "candidate_0_fixture explosion_playback_oracle_original_lane_write_unledgered.txt "
            "is missing from runtime evidence ledger",
            "bad_original_writer_fixture",
        )
        cases += 1

        no_ready_sweep = base / "no_ready_manifest.txt"
        write_route_sweep(
            no_ready_sweep,
            [("no_freeze", "3ec1", no_freeze_manifest, no_freeze_candidate)],
            ["3ec1"],
        )
        no_ready = run_summary(
            root, [str(no_ready_sweep), "--require-ready"], expect_success=False
        )
        require(no_ready, "reason=no_ready_candidates", "no_ready_required")
        require(no_ready, "no_freeze_candidates=1", "no_ready_required")
        cases += 1

        incomplete_sweep = base / "incomplete_manifest.txt"
        write_route_sweep(
            incomplete_sweep,
            [
                ("ready", "3d2d", ready_manifest, ready_candidate),
                (
                    "incomplete",
                    "3d2d",
                    incomplete_manifest,
                    incomplete_candidate,
                ),
            ],
            ["3d2d"],
        )
        incomplete = run_summary(
            root, [str(incomplete_sweep), "--require-ready"], expect_success=False
        )
        require(incomplete, "reason=candidates_not_ready", "incomplete_required")
        require(incomplete, "incomplete_candidates=1", "incomplete_required")
        require(incomplete, "candidate_placeholders=1", "incomplete_required")
        cases += 1

        direct = run_summary(root, [str(ready_manifest)])
        require(direct, "mode=runtime", "direct_runtime")
        require(direct, "environment_preflight=unknown", "direct_runtime")
        require(direct, "routes=1", "direct_runtime")
        require(direct, "candidate route=direct", "direct_runtime")
        cases += 1

        missing_preflight = run_summary(
            root,
            [str(ready_manifest), "--require-environment-preflight"],
            expect_success=False,
        )
        require(
            missing_preflight,
            "reason=environment_preflight_not_ok",
            "missing_environment_preflight",
        )
        require(
            missing_preflight,
            "environment_preflight=unknown",
            "missing_environment_preflight",
        )
        cases += 1

        duplicate_field_manifest = base / "duplicate_field_manifest.txt"
        write_text(
            duplicate_field_manifest,
            ready_manifest.read_text(encoding="ascii")
            + "capture=lane_write_route_sweep\n",
        )
        duplicate_field = run_summary(
            root,
            [str(duplicate_field_manifest)],
            expect_success=False,
        )
        require(
            duplicate_field,
            "duplicate manifest field: capture",
            "duplicate_field",
        )
        cases += 1

    print(f"lane_write_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
