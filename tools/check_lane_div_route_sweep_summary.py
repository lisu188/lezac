#!/usr/bin/env python3
"""Exercise lane-div route-sweep summary and route handoff output."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


OFFSET_MODEL = {
    "3cd4": ("1000:3CD4", "forward", "setup"),
    "3ce3": ("1000:3CE3", "forward", "divide"),
    "3e68": ("1000:3E68", "reverse", "setup"),
    "3e77": ("1000:3E77", "reverse", "divide"),
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def run_summary(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_lane_div_route_sweep.py"),
        *args,
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
    patch_applied: bool = True,
    ax: str = "0xfff3",
    dx: str = "0xffff",
    cx: str = "0x0021",
    bx: str = "0x0000",
    active_count: str = "0x0001",
    loop_index: str = "0x0001",
    weight_local: str = "0x0021",
    numerator_low: str = "0xfff3",
    numerator_high: str = "0xffff",
) -> None:
    _, kind, _ = OFFSET_MODEL[offset_label]
    lane_lines = []
    if freeze:
        lane_lines = [
            "instrumented_lane_div_scratch_present=1",
            f"instrumented_lane_div_ax={ax}",
            f"instrumented_lane_div_dx={dx}",
            f"instrumented_lane_div_cx={cx}",
            f"instrumented_lane_div_bx={bx}",
            f"instrumented_lane_div_active_count={active_count}",
            f"instrumented_lane_div_loop_index={loop_index}",
            f"instrumented_lane_div_weight_local={weight_local}",
            f"instrumented_lane_div_numerator_low={numerator_low}",
            f"instrumented_lane_div_numerator_high={numerator_high}",
        ]
    else:
        lane_lines = ["instrumented_lane_div_scratch_present=0"]
    if placeholder:
        lane_lines.append("# fill me: <instrumented_lane_div_ax>")
    patch_lines = [f"runtime_freeze_patch_applied={1 if patch_applied else 0}"]
    if patch_applied:
        patch_lines.append("runtime_freeze_old_bytes=9a4509")
    write_text(
        path,
        "\n".join(
            [
                "capture=explosion_playback",
                "source=synthetic",
                "temp_copy=1",
                "visual_claim=0",
                "instrumented_freeze_observed=" + ("1" if freeze else "0"),
                "instrumented_freeze_patch_mode=lane-div-cs-scratch",
                "instrumented_lane_div_cs_offset=0x3d33",
                f"instrumented_lane_div_kind={kind}",
                *patch_lines,
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
        "capture=lane_div_route_sweep",
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
            f"capture_command_{route}_{offset}=python helper "
            "--route-step x:2.00 --route-step m:0.35"
        )
        lines.append(
            f"capture_status_{route}_{offset}=lane_div_capture=ok "
            f"route={route} offset={offset} offset_address={OFFSET_MODEL[offset][0]} "
            f"manifest={child} candidate={candidate}"
        )
    lines.append("")
    write_text(path, "\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check lane-div route-sweep summary behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-div-summary-") as tmp:
        base = Path(tmp)
        ready_candidate = base / "ready" / "candidate.txt"
        setup_candidate = base / "setup_ready" / "candidate.txt"
        reverse_candidate = base / "reverse_ready" / "candidate.txt"
        no_freeze_candidate = base / "no_freeze" / "candidate.txt"
        no_patch_candidate = base / "no_patch" / "candidate.txt"
        incomplete_candidate = base / "incomplete" / "candidate.txt"
        write_candidate(ready_candidate, "3ce3", freeze=True)
        write_candidate(
            setup_candidate,
            "3cd4",
            freeze=True,
            ax="0xfff8",
            dx="0xffff",
            cx="0x0005",
            weight_local="0x0005",
            numerator_low="0xfff8",
        )
        write_candidate(reverse_candidate, "3e77", freeze=True)
        write_candidate(no_freeze_candidate, "3ce3", freeze=False)
        write_candidate(no_patch_candidate, "3ce3", freeze=False, patch_applied=False)
        write_candidate(incomplete_candidate, "3ce3", freeze=True, placeholder=True)

        ready_manifest = base / "ready" / "manifest.txt"
        setup_manifest = base / "setup_ready" / "manifest.txt"
        reverse_manifest = base / "reverse_ready" / "manifest.txt"
        no_freeze_manifest = base / "no_freeze" / "manifest.txt"
        no_patch_manifest = base / "no_patch" / "manifest.txt"
        incomplete_manifest = base / "incomplete" / "manifest.txt"
        write_runtime_manifest(ready_manifest, ready_candidate)
        write_runtime_manifest(setup_manifest, setup_candidate)
        write_runtime_manifest(reverse_manifest, reverse_candidate)
        write_runtime_manifest(no_freeze_manifest, no_freeze_candidate)
        write_runtime_manifest(no_patch_manifest, no_patch_candidate)
        write_runtime_manifest(incomplete_manifest, incomplete_candidate)

        sweep_manifest = base / "manifest.txt"
        write_route_sweep(
            sweep_manifest,
            [
                ("ready", "3ce3", ready_manifest, ready_candidate),
                ("no_freeze", "3ce3", no_freeze_manifest, no_freeze_candidate),
            ],
            ["3ce3"],
        )
        summary = run_summary(root, [str(sweep_manifest)])
        for snippet in [
            "lane_div_route_sweep_summary=ok",
            "mode=route",
            "environment_preflight=ok",
            "routes=2",
            "candidates=2",
            "observed_freezes=1",
            "ready_candidates=1",
            "no_freeze_candidates=1",
            "forward_candidates=1",
            "forward_divide_candidates=1",
            "forward_setup_candidates=0",
            "reverse_candidates=0",
            "observed_offsets=3ce3",
            "missing_offsets=none",
            "candidate route=ready offset=3ce3",
            "route_steps=x:2.00,m:0.35",
            "kind=forward",
            "phase=divide",
            "lane_div_ax=0xfff3",
            "lane_div_weight_local=0x0021",
            "candidate_status=ready",
            "candidate route=no_freeze offset=3ce3",
            "candidate_status=no_freeze",
            "oracle_flag=--debug-explosion-playback-oracle",
        ]:
            require(summary, snippet, "mixed_summary")
        cases += 1

        require_ready = run_summary(root, [str(sweep_manifest), "--require-ready"])
        require(require_ready, "ready_candidates=1", "require_ready")
        cases += 1

        require_forward = run_summary(
            root, [str(sweep_manifest), "--require-forward-divide"]
        )
        require(
            require_forward,
            "forward_divide_candidates=1",
            "require_forward",
        )
        cases += 1

        require_preflight = run_summary(
            root, [str(sweep_manifest), "--require-environment-preflight"]
        )
        require(require_preflight, "environment_preflight=ok", "require_preflight")
        cases += 1

        route_manifest = base / "forward_routes" / "manifest.txt"
        route_manifest_out = run_summary(
            root,
            [
                str(sweep_manifest),
                "--require-forward-divide",
                "--write-forward-route-manifest",
                str(route_manifest),
            ],
        )
        require(
            route_manifest_out,
            "lane_div_forward_route_manifest=ok",
            "route_manifest_output",
        )
        require(
            route_manifest_out,
            f"path={route_manifest.resolve()}",
            "route_manifest_output",
        )
        require(route_manifest_out, "matching_routes=1", "route_manifest_output")
        route_manifest_text = route_manifest.read_text(encoding="ascii")
        for snippet in [
            "promotion=lane_div_forward_route_candidates",
            f"source_manifest={sweep_manifest.resolve()}",
            "source_environment_preflight=ok",
            "required_candidate=forward_divide",
            "matching_routes=1",
            "route_0_label=ready",
            "route_0_steps=x:2.00,m:0.35",
            "route_0_offset_label=3ce3",
            "route_0_offset_address=1000:3CE3",
            "route_0_lane_div_weight_local=0x0021",
            "route_0_lane_div_numerator_low=0xfff3",
            "route_0_lane_div_numerator_high=0xffff",
            f"route_0_fixture={ready_candidate}",
        ]:
            require(route_manifest_text, snippet, "route_manifest")
        cases += 1

        no_step_sweep = base / "no_step_manifest.txt"
        write_text(
            no_step_sweep,
            "\n".join(
                [
                    "capture=lane_div_route_sweep",
                    "asset_dir=/repo",
                    "offsets=1",
                    "offset_labels=3ce3",
                    "offset_addresses=1000:3CE3",
                    "routes=1",
                    "route_labels=ready",
                    "environment_preflight=ok",
                    "capture_status_ready_3ce3=lane_div_capture=ok "
                    f"route=ready offset=3ce3 offset_address=1000:3CE3 "
                    f"manifest={ready_manifest} candidate={ready_candidate}",
                    "",
                ]
            ),
        )
        no_step_route_manifest = run_summary(
            root,
            [
                str(no_step_sweep),
                "--require-forward-divide",
                "--write-forward-route-manifest",
                str(base / "no-step-routes.txt"),
            ],
            expect_success=False,
        )
        require(
            no_step_route_manifest,
            "route_steps_missing route=ready",
            "no_step_route_manifest",
        )
        cases += 1

        missing_forward_gate = run_summary(
            root,
            [
                str(sweep_manifest),
                "--write-forward-route-manifest",
                str(base / "missing-gate.txt"),
            ],
            expect_success=False,
        )
        require(
            missing_forward_gate,
            "reason=write_requires_require_forward_divide",
            "missing_forward_gate",
        )
        cases += 1

        setup_only_sweep = base / "setup_only_manifest.txt"
        write_route_sweep(
            setup_only_sweep,
            [("setup_ready", "3cd4", setup_manifest, setup_candidate)],
            ["3cd4"],
        )
        setup_not_forward_divide = run_summary(
            root,
            [str(setup_only_sweep), "--require-forward-divide"],
            expect_success=False,
        )
        require(
            setup_not_forward_divide,
            "reason=no_forward_divide_candidates",
            "setup_not_forward_divide",
        )
        require(
            setup_not_forward_divide,
            "forward_setup_candidates=1",
            "setup_not_forward_divide",
        )
        cases += 1

        reverse_only_sweep = base / "reverse_only_manifest.txt"
        write_route_sweep(
            reverse_only_sweep,
            [("reverse_ready", "3e77", reverse_manifest, reverse_candidate)],
            ["3e77"],
        )
        reverse_not_forward = run_summary(
            root,
            [str(reverse_only_sweep), "--require-forward-divide"],
            expect_success=False,
        )
        require(
            reverse_not_forward,
            "reason=no_forward_divide_candidates",
            "reverse_not_forward",
        )
        require(reverse_not_forward, "reverse_divide_candidates=1", "reverse_not_forward")
        cases += 1

        no_ready_sweep = base / "no_ready_manifest.txt"
        write_route_sweep(
            no_ready_sweep,
            [("no_freeze", "3ce3", no_freeze_manifest, no_freeze_candidate)],
            ["3ce3"],
        )
        no_ready = run_summary(
            root, [str(no_ready_sweep), "--require-ready"], expect_success=False
        )
        require(no_ready, "reason=no_ready_candidates", "no_ready_required")
        require(no_ready, "no_freeze_candidates=1", "no_ready_required")
        cases += 1

        no_patch_sweep = base / "no_patch_manifest.txt"
        write_route_sweep(
            no_patch_sweep,
            [("no_patch", "3ce3", no_patch_manifest, no_patch_candidate)],
            ["3ce3"],
        )
        no_patch = run_summary(
            root, [str(no_patch_sweep), "--require-ready"], expect_success=False
        )
        require(no_patch, "no_patch_candidates=1", "no_patch_required")
        require(no_patch, "candidate_status=no_patch", "no_patch_required")
        cases += 1

        incomplete_sweep = base / "incomplete_manifest.txt"
        write_route_sweep(
            incomplete_sweep,
            [
                ("ready", "3ce3", ready_manifest, ready_candidate),
                ("incomplete", "3ce3", incomplete_manifest, incomplete_candidate),
            ],
            ["3ce3"],
        )
        incomplete = run_summary(
            root, [str(incomplete_sweep), "--require-ready"], expect_success=False
        )
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
        cases += 1

        duplicate_field_manifest = base / "duplicate_field_manifest.txt"
        write_text(
            duplicate_field_manifest,
            ready_manifest.read_text(encoding="ascii")
            + "capture=lane_div_route_sweep\n",
        )
        duplicate_field = run_summary(
            root,
            [str(duplicate_field_manifest)],
            expect_success=False,
        )
        require(duplicate_field, "duplicate manifest field: capture", "duplicate_field")
        cases += 1

    print(f"lane_div_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
