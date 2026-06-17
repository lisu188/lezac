#!/usr/bin/env python3
"""Check branch-anchor route-sweep summary classification."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


TARGETS = {
    "high_debris_target_sample": ("1000:4B3F", "loop"),
    "high_debris_word_gate": ("1000:4C75", "bp4-cs-scratch"),
    "effect_forward_pass_call": ("1000:4C96", "loop"),
    "effect_reverse_pass_call": ("1000:4CA9", "loop"),
}


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def run_summary(root: Path, args: list[str], expect_success: bool = True) -> str:
    command = [
        sys.executable,
        str(root / "tools" / "summarize_branch_anchor_route_sweep.py"),
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
            "summarize_branch_anchor_route_sweep.py failed with "
            f"{result.returncode}: {args}\n{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            "summarize_branch_anchor_route_sweep.py unexpectedly passed: "
            f"{args}\n{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing {snippet!r}\n{text}")


def write_candidate(
    path: Path,
    target: str,
    freeze: bool,
    patch_applied: bool = True,
    include_bp4: bool = True,
    placeholder: bool = False,
) -> None:
    _, patch_mode = TARGETS[target]
    lines = [
        "capture=explosion_playback",
        "source=synthetic",
        "temp_copy=1",
        "visual_claim=0",
        f"instrumented_freeze_observed={1 if freeze else 0}",
        f"instrumented_freeze_patch_mode={patch_mode}",
        f"runtime_freeze_patch_applied={1 if patch_applied else 0}",
        "runtime_cs=01ED",
        "runtime_ds=0C8F",
        "runtime_freeze_patch_high_debris_target_byte=0x00",
        "runtime_freeze_patch_high_debris_word_layer_value=0x8002",
        "runtime_freeze_patch_elapsed_after_bomb=2.781",
    ]
    if patch_applied:
        lines.append("runtime_freeze_old_bytes=ebfe")
    if patch_mode == "bp4-cs-scratch":
        lines.append(f"instrumented_bp4_local_present={1 if freeze and include_bp4 else 0}")
        lines.append("instrumented_bp4_local_cs_offset=0x4c7e")
        if include_bp4:
            lines.append("instrumented_bp4_local_value=0x8002")
    if placeholder:
        lines.append("# fill me: <branch-anchor>")
    lines.append("")
    write_text(path, "\n".join(lines))


def write_child_manifest(path: Path, fixture: Path) -> None:
    write_text(
        path,
        "\n".join(
            [
                "capture=original_explosion_process_memory",
                f"fixture_candidate={fixture}",
                "",
            ]
        ),
    )


def write_sweep(base: Path, environment_preflight: str = "ok") -> Path:
    ready_word = base / "ready-word" / "candidate.txt"
    ready_forward = base / "ready-forward" / "candidate.txt"
    no_freeze = base / "no-freeze" / "candidate.txt"
    no_patch = base / "no-patch" / "candidate.txt"
    incomplete = base / "incomplete" / "candidate.txt"
    write_candidate(ready_word, "high_debris_word_gate", True)
    write_candidate(ready_forward, "effect_forward_pass_call", True)
    write_candidate(no_freeze, "high_debris_target_sample", False)
    write_candidate(no_patch, "effect_forward_pass_call", False, patch_applied=False)
    write_candidate(incomplete, "high_debris_word_gate", True, include_bp4=False)

    ready_word_manifest = base / "ready-word" / "manifest.txt"
    ready_forward_manifest = base / "ready-forward" / "manifest.txt"
    no_freeze_manifest = base / "no-freeze" / "manifest.txt"
    no_patch_manifest = base / "no-patch" / "manifest.txt"
    incomplete_manifest = base / "incomplete" / "manifest.txt"
    write_child_manifest(ready_word_manifest, ready_word)
    write_child_manifest(ready_forward_manifest, ready_forward)
    write_child_manifest(no_freeze_manifest, no_freeze)
    write_child_manifest(no_patch_manifest, no_patch)
    write_child_manifest(incomplete_manifest, incomplete)

    manifest = base / "manifest.txt"
    write_text(
        manifest,
        "\n".join(
            [
                "capture=branch_anchor_route_sweep",
                "targets=high_debris_target_sample,high_debris_word_gate,effect_forward_pass_call",
                "timings=before_bomb",
                "routes=4",
                "route_labels=x2p00,x2p00_m0p35,x2p00_c0p35,x2p00_c0p65",
                f"environment_preflight={environment_preflight}",
                "capture_status_high_debris_word_gate_before_bomb_x2p00_m0p35=branch_anchor_capture=ok route=x2p00_m0p35 target=high_debris_word_gate offset=1000:4C75 patch_mode=bp4-cs-scratch manifest="
                + str(ready_word_manifest)
                + " candidate="
                + str(ready_word),
                "capture_status_effect_forward_pass_call_before_bomb_x2p00_m0p35=branch_anchor_capture=ok route=x2p00_m0p35 target=effect_forward_pass_call offset=1000:4C96 patch_mode=loop manifest="
                + str(ready_forward_manifest),
                "capture_status_high_debris_target_sample_before_bomb_x2p00=branch_anchor_capture=ok route=x2p00 target=high_debris_target_sample offset=1000:4B3F patch_mode=loop manifest="
                + str(no_freeze_manifest)
                + " candidate="
                + str(no_freeze),
                "capture_status_effect_forward_pass_call_before_bomb_x2p00_c0p35=branch_anchor_capture=ok route=x2p00_c0p35 target=effect_forward_pass_call offset=1000:4C96 patch_mode=loop manifest="
                + str(no_patch_manifest)
                + " candidate="
                + str(no_patch),
                "capture_status_high_debris_word_gate_before_bomb_x2p00_c0p65=branch_anchor_capture=ok route=x2p00_c0p65 target=high_debris_word_gate offset=1000:4C75 patch_mode=bp4-cs-scratch manifest="
                + str(incomplete_manifest)
                + " candidate="
                + str(incomplete),
                "",
            ]
        ),
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check branch-anchor route-sweep summaries."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-branch-anchor-summary-") as tmp:
        base = Path(tmp)
        sweep = write_sweep(base / "mixed")
        summary = run_summary(root, [str(sweep)])
        for snippet in [
            "branch_anchor_route_sweep_summary=ok",
            "environment_preflight=ok",
            "targets=high_debris_target_sample,high_debris_word_gate,effect_forward_pass_call",
            "routes=4",
            "candidates=5",
            "observed_freezes=2",
            "ready_candidates=2",
            "no_patch_candidates=1",
            "no_freeze_candidates=1",
            "incomplete_candidates=1",
            "missing_candidates=0",
            "observed_targets=high_debris_word_gate,effect_forward_pass_call",
            "missing_targets=high_debris_target_sample",
            "observed_routes=x2p00_m0p35",
            "route_hits=x2p00_m0p35:high_debris_word_gate,effect_forward_pass_call",
            "branch_anchor_route_sweep_detail label=high_debris_word_gate_before_bomb_x2p00_m0p35",
            "candidate_status=ready",
            "bp4_local_present=1",
            "bp4_local_value=0x8002",
            "high_debris_target_byte=0x00",
            "high_debris_word_layer_value=0x8002",
            "branch_anchor_route_sweep_detail label=effect_forward_pass_call_before_bomb_x2p00_m0p35",
            "target=effect_forward_pass_call",
            "patch_mode=loop",
            "branch_anchor_route_sweep_detail label=high_debris_target_sample_before_bomb_x2p00",
            "candidate_status=no_freeze",
            "branch_anchor_route_sweep_detail label=effect_forward_pass_call_before_bomb_x2p00_c0p35",
            "candidate_status=no_patch",
            "branch_anchor_route_sweep_detail label=high_debris_word_gate_before_bomb_x2p00_c0p65",
            "candidate_missing=instrumented_bp4_local_present,instrumented_bp4_local_value",
        ]:
            require(summary, snippet, "mixed_summary")
        cases += 1

        require_target = run_summary(
            root, [str(sweep), "--require-target", "effect_forward_pass_call"]
        )
        require(
            require_target,
            "observed_targets=high_debris_word_gate,effect_forward_pass_call",
            "require_target",
        )
        cases += 1

        require_route = run_summary(
            root,
            [
                str(sweep),
                "--require-route-with-targets",
                "high_debris_word_gate,effect_forward_pass_call",
            ],
        )
        require(require_route, "route_hits=x2p00_m0p35:", "require_route")
        cases += 1

        missing_target = run_summary(
            root,
            [str(sweep), "--require-target", "high_debris_target_sample"],
            expect_success=False,
        )
        require(
            missing_target,
            "reason=missing_required_targets",
            "missing_target",
        )
        require(
            missing_target,
            "missing_targets=high_debris_target_sample",
            "missing_target",
        )
        cases += 1

        missing_route = run_summary(
            root,
            [
                str(sweep),
                "--require-route-with-targets",
                "high_debris_word_gate,effect_reverse_pass_call",
            ],
            expect_success=False,
        )
        require(
            missing_route,
            "reason=no_route_with_required_targets",
            "missing_route",
        )
        require(
            missing_route,
            "required_targets=high_debris_word_gate,effect_reverse_pass_call",
            "missing_route",
        )
        cases += 1

        skipped = write_sweep(base / "skipped", "skipped")
        preflight = run_summary(
            root,
            [str(skipped), "--require-environment-preflight"],
            expect_success=False,
        )
        require(
            preflight,
            "reason=environment_preflight_not_ok environment_preflight=skipped",
            "preflight",
        )
        cases += 1

        bad_manifest = base / "bad" / "manifest.txt"
        write_text(bad_manifest, "capture=other\n")
        bad = run_summary(root, [str(bad_manifest)], expect_success=False)
        require(
            bad,
            "unsupported manifest capture 'other'",
            "bad_manifest",
        )
        cases += 1

    print(f"branch_anchor_route_sweep_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
