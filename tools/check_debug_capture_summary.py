#!/usr/bin/env python3
"""Check DOSBox-debug capture summary classification."""

from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def run_tool(
    root: Path,
    args: list[str],
    expect_success: bool = True,
) -> str:
    command = [sys.executable, str(root / "tools" / "summarize_debug_capture.py"), *args]
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
            f"summarize_debug_capture.py failed with {result.returncode}: {args}\n"
            f"{result.stdout}"
        )
    if not expect_success and result.returncode == 0:
        raise RuntimeError(
            f"summarize_debug_capture.py unexpectedly passed: {args}\n"
            f"{result.stdout}"
        )
    return result.stdout


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing {snippet!r}\n{text}")


def write_behavior4_skeleton(base: Path) -> Path:
    capture_dir = base / "behavior4"
    candidate = capture_dir / "candidate_fixture.txt"
    write_text(
        capture_dir / "manifest.txt",
        "\n".join(
            [
                "capture=behavior4_runtime",
                "source=dosbox-debug",
                "scenario=monster_behavior4_target_selection",
                "expected_level=3",
                "route=debugger_seeded",
                f"raw_debugger_dump={capture_dir / 'raw_debugger_dump.txt'}",
                f"debugger_commands_runtime={capture_dir / 'debugger_commands_runtime.txt'}",
                f"candidate_fixture={candidate}",
                f"environment_preflight_log={capture_dir / 'environment_preflight.log'}",
                "environment_preflight=dry_run",
                "",
            ]
        ),
    )
    write_text(
        candidate,
        "\n".join(
            [
                "capture=behavior4_runtime",
                "source=dosbox-debug",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=monster_behavior4_target_selection",
                "level=3",
                "route=debugger_seeded",
                "# runtime_cs=<runtime-cs>",
                "# actor_before slot=<slot> behavior=4",
                "",
            ]
        ),
    )
    return capture_dir / "manifest.txt"


def write_behavior4_ready(base: Path) -> Path:
    capture_dir = base / "behavior4_ready"
    candidate = capture_dir / "candidate_fixture.txt"
    write_text(
        capture_dir / "manifest.txt",
        "\n".join(
            [
                "capture=behavior4_runtime",
                "source=dosbox-debug",
                "scenario=monster_behavior4_target_selection",
                "expected_level=3",
                "route=debugger_seeded",
                f"raw_debugger_dump={capture_dir / 'raw_debugger_dump.txt'}",
                f"debugger_commands_runtime={capture_dir / 'debugger_commands_runtime.txt'}",
                f"candidate_fixture={candidate}",
                f"environment_preflight_log={capture_dir / 'environment_preflight.log'}",
                "environment_preflight=ok",
                "runtime_metadata=observed",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "",
            ]
        ),
    )
    write_text(
        candidate,
        "\n".join(
            [
                "capture=behavior4_runtime",
                "source=dosbox-debug",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=monster_behavior4_target_selection",
                "level=3",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "break ghidra=1000:7A6B runtime=01ED:7A6B label=spawner_loop_start",
                "break ghidra=1000:7C2C runtime=01ED:7C2C label=spawner_loop_end",
                "break ghidra=1000:728C runtime=01ED:728C label=behavior4_branch_start",
                "break ghidra=1000:731B runtime=01ED:731B label=behavior4_branch_end",
                "break ghidra=1000:73E5 runtime=01ED:73E5 label=integration_8_8_start",
                "break ghidra=1000:741B runtime=01ED:741B label=integration_8_8_end",
                "spawner index=5 behavior=4 ai0=20 ai1=214 ai2=66 hp=4 spawn_timer=30",
                "actor_before slot=0 behavior=4 x=0x0068 y=0x00a8 vx8=0 vy8=0 motion_timer=0 target=2 hp=4 dead=0",
                "actor_after slot=0 behavior=4 x=0x0069 y=0x00a8 vx8=32 vy8=0 motion_timer=1 target=1 hp=4 dead=0",
                "players p1_dead=0 p2_dead=1 p1_state=0 p2_state=2 target_before=2 target_after=1",
                "dump DS:7900",
                "0C8F:7900  05 04 14 d6 42 04 1e 00 00 00 00 00 00 00 00 00",
                "0C8F:7910  68 00 a8 00 20 00 00 00 01 01 04 00 00 00 00 00",
                "",
            ]
        ),
    )
    return capture_dir


def write_actor_ready(base: Path) -> Path:
    capture_dir = base / "actor_ready"
    candidate = capture_dir / "candidate_fixture.txt"
    write_text(
        capture_dir / "manifest.txt",
        "\n".join(
            [
                "capture=actor_update_runtime",
                "source=dosbox-debug",
                "scenario=object_collision_jump_live",
                "expected_level=1",
                "route=debugger_seeded",
                f"raw_debugger_dump={capture_dir / 'raw_debugger_dump.txt'}",
                f"debugger_commands_runtime={capture_dir / 'debugger_commands_runtime.txt'}",
                f"candidate_fixture={candidate}",
                f"environment_preflight_log={capture_dir / 'environment_preflight.log'}",
                "environment_preflight=ok",
                "runtime_metadata=observed",
                "runtime_cs=01ED",
                "runtime_ds=0F3C",
                "",
            ]
        ),
    )
    write_text(
        candidate,
        "\n".join(
            [
                "capture=actor_update_runtime",
                "source=dosbox-debug",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=object_collision_jump_live",
                "level=1",
                "runtime_cs=01ED",
                "runtime_ds=0F3C",
                "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                "break ghidra=1000:6053 runtime=01ED:6053 label=actor_update_start",
                "break ghidra=1000:777F runtime=01ED:777F label=actor_update_end",
                "actor_before slot=0 behavior=3 kind=1 state=0 x=0x0068 y=0x00a8 vx8=32 vy8=0 hp=3 flags=0x0000 contact=0 on_ground=1",
                "actor_after slot=0 behavior=3 kind=1 state=0 x=0x0069 y=0x00a8 vx8=32 vy8=0 hp=3 flags=0x0005 contact=1 on_ground=1",
                "contact_scan subject_slot=0 other_slot=1 flags_before=0x0000 flags_after=0x0005 contact=1 player_contact=0 monster_contact=0 object_contact=1 damage_pending=0",
                "tile_probe tile_x=13 tile_y=22 tile=0x0025 object=0x0013 passable=0 standable=1",
                "",
            ]
        ),
    )
    return capture_dir


def write_contact_missing(base: Path) -> Path:
    capture_dir = base / "contact_missing"
    write_text(
        capture_dir / "manifest.txt",
        "\n".join(
            [
                "capture=contact_scanner_runtime",
                "scenario=monster_contact_damage_live",
                "expected_level=1",
                "route=debugger_seeded",
                f"candidate_fixture={capture_dir / 'missing_candidate.txt'}",
                "environment_preflight=error",
                "",
            ]
        ),
    )
    return capture_dir / "manifest.txt"


def write_contact_ready(base: Path) -> Path:
    capture_dir = base / "contact_ready"
    candidate = capture_dir / "candidate_fixture.txt"
    write_text(
        capture_dir / "manifest.txt",
        "\n".join(
            [
                "capture=contact_scanner_runtime",
                "source=dosbox-debug",
                "scenario=monster_contact_damage_live",
                "expected_level=1",
                "route=debugger_seeded",
                f"raw_debugger_dump={capture_dir / 'raw_debugger_dump.txt'}",
                f"debugger_commands_runtime={capture_dir / 'debugger_commands_runtime.txt'}",
                f"candidate_fixture={candidate}",
                f"environment_preflight_log={capture_dir / 'environment_preflight.log'}",
                "environment_preflight=ok",
                "runtime_metadata=observed",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "",
            ]
        ),
    )
    write_text(
        candidate,
        "\n".join(
            [
                "capture=contact_scanner_runtime",
                "source=dosbox-debug",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=monster_contact_damage_live",
                "level=1",
                "runtime_cs=01ED",
                "runtime_ds=0C8F",
                "break ghidra=1000:5CB0 runtime=01ED:5CB0 label=contact_scanner_start",
                "break ghidra=1000:604F runtime=01ED:604F label=contact_scanner_end",
                "subject_actor slot=0 kind=0 state=0 x=0x0068 y=0x00a8 w=16 h=24 flags=0x0000",
                "other_actor slot=1 kind=1 state=0 x=0x0070 y=0x00aa w=16 h=16 flags=0x0000",
                "contact_scan subject_slot=0 other_slot=1 flags_before=0x0000 flags_after=0x0003 contact=1 player_contact=1 monster_contact=1 object_contact=0 damage_pending=2 overlap_x=8 overlap_y=14",
                "dump DS:7900",
                "0C8F:7900  00 00 00 00 68 00 a8 00 10 18 00 00 03 00 02 00",
                "",
            ]
        ),
    )
    return capture_dir


def write_visual_table_ready(base: Path) -> Path:
    capture_dir = base / "visual_ready"
    candidate = capture_dir / "candidate_fixture.txt"
    write_text(
        capture_dir / "manifest.txt",
        "\n".join(
            [
                "capture=visual_table",
                "source=dosbox-debug",
                "scenario=state2_death_table_consumption",
                "expected_level=1",
                "route=debugger_seeded",
                f"raw_debugger_dump={capture_dir / 'raw_debugger_dump.txt'}",
                f"debugger_commands_runtime={capture_dir / 'debugger_commands_runtime.txt'}",
                f"candidate_fixture={candidate}",
                f"environment_preflight_log={capture_dir / 'environment_preflight.log'}",
                "environment_preflight=ok",
                "runtime_metadata=observed",
                "runtime_cs=1A2B",
                "runtime_ds=2B3C",
                "",
            ]
        ),
    )
    write_text(
        candidate,
        "\n".join(
            [
                "capture=visual_table",
                "source=dosbox-debug",
                "temp_copy=1",
                "visual_claim=0",
                "scenario=state2_death_table_consumption",
                "level=1",
                "runtime_cs=1A2B",
                "runtime_ds=2B3C",
                "break ghidra=1000:3108 runtime=1A2B:3108 label=state2_death_helper",
                "break ghidra=1000:6053 runtime=1A2B:6053 label=actor_update_animation",
                "break ghidra=1000:6148 runtime=1A2B:6148 label=actor_frame_consumer",
                "break ghidra=1000:7C89 runtime=1A2B:7C89 label=state2_countdown",
                "break ghidra=1000:7DDF runtime=1A2B:7DDF label=state2_return_active",
                "actor slot=0 kind=player1 state=2 anim_current=0x72 anim_first=0x72 anim_last=0x79 anim_counter=3 anim_delay=3 anim_mode=1 anim_step=1",
                "visual frame=0x72 row_addr=0xc4ea row=10,18,20,00 bank=BOMOMIMK sprite_index=16 sprite_source=row_byte0 draw_dx=24 draw_dy=32",
                "effect_before slot=0 x=0x0018 y=0x0028 frame=0x72 flags=0x0000",
                "effect_after slot=0 x=0x0018 y=0x0028 frame=0x72 flags=0x0000",
                "dump DS:C4EA",
                "2B3C:C4EA  10 18 20 00",
                "dump DS:C21E",
                "2B3C:C21E  18 00 28 00 72 00 00 00",
                "",
            ]
        ),
    )
    return capture_dir


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check summarize_debug_capture.py behavior."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-debug-summary-") as tmp:
        base = Path(tmp)

        behavior_manifest = write_behavior4_skeleton(base)
        behavior = run_tool(root, [str(behavior_manifest)])
        for snippet in [
            "debug_capture_summary=ok capture=behavior4_runtime",
            "scenario=monster_behavior4_target_selection",
            "environment_preflight=dry_run",
            "candidate_status=incomplete",
            "candidate_placeholders=1",
            "oracle_flag=--debug-behavior4-runtime-oracle",
        ]:
            require(behavior, snippet, "behavior_skeleton")
        cases += 1

        behavior_required = run_tool(
            root,
            [str(behavior_manifest), "--require-ready"],
            expect_success=False,
        )
        require(behavior_required, "reason=candidate_not_ready", "behavior_require_ready")
        require(behavior_required, "candidate_status=incomplete", "behavior_require_ready")
        cases += 1

        behavior_ready_dir = write_behavior4_ready(base)
        behavior_ready = run_tool(
            root,
            [
                str(behavior_ready_dir),
                "--require-ready",
                "--require-environment-preflight",
                "--oracle-binary",
                "./build/lezac_cpp",
            ],
        )
        for snippet in [
            "debug_capture_summary=ok capture=behavior4_runtime",
            "scenario=monster_behavior4_target_selection",
            "environment_preflight=ok",
            "runtime_metadata=observed",
            "candidate_status=ready",
            "candidate_missing=none",
            "oracle=behavior4",
            "oracle_flag=--debug-behavior4-runtime-oracle",
            "./build/lezac_cpp --debug-behavior4-runtime-oracle",
        ]:
            require(behavior_ready, snippet, "behavior_ready")
        cases += 1

        actor_dir = write_actor_ready(base)
        actor = run_tool(
            root,
            [
                str(actor_dir),
                "--require-ready",
                "--require-environment-preflight",
                "--oracle-binary",
                "./build/lezac_cpp",
            ],
        )
        for snippet in [
            "debug_capture_summary=ok capture=actor_update_runtime",
            "environment_preflight=ok",
            "runtime_metadata=observed",
            "candidate_status=ready",
            "candidate_missing=none",
            "oracle_flag=--debug-actor-update-runtime-oracle",
            "./build/lezac_cpp --debug-actor-update-runtime-oracle",
        ]:
            require(actor, snippet, "actor_ready")
        cases += 1

        contact_manifest = write_contact_missing(base)
        contact = run_tool(root, [str(contact_manifest)])
        for snippet in [
            "debug_capture_summary=ok capture=contact_scanner_runtime",
            "environment_preflight=error",
            "candidate_status=missing",
            "candidate_missing=file",
            "oracle_flag=--debug-contact-scanner-runtime-oracle",
        ]:
            require(contact, snippet, "contact_missing")
        cases += 1

        env_required = run_tool(
            root,
            [str(contact_manifest), "--require-environment-preflight"],
            expect_success=False,
        )
        require(
            env_required,
            "reason=environment_preflight_not_ok environment_preflight=error",
            "contact_require_environment",
        )
        cases += 1

        contact_ready_dir = write_contact_ready(base)
        contact_ready = run_tool(
            root,
            [
                str(contact_ready_dir),
                "--require-ready",
                "--require-environment-preflight",
                "--oracle-binary",
                "./build/lezac_cpp",
            ],
        )
        for snippet in [
            "debug_capture_summary=ok capture=contact_scanner_runtime",
            "scenario=monster_contact_damage_live",
            "environment_preflight=ok",
            "runtime_metadata=observed",
            "candidate_status=ready",
            "candidate_missing=none",
            "oracle=contact_scanner",
            "oracle_flag=--debug-contact-scanner-runtime-oracle",
            "./build/lezac_cpp --debug-contact-scanner-runtime-oracle",
        ]:
            require(contact_ready, snippet, "contact_ready")
        cases += 1

        visual_dir = write_visual_table_ready(base)
        visual = run_tool(
            root,
            [
                str(visual_dir),
                "--require-ready",
                "--require-environment-preflight",
            ],
        )
        for snippet in [
            "debug_capture_summary=ok capture=visual_table",
            "scenario=state2_death_table_consumption",
            "environment_preflight=ok",
            "runtime_metadata=observed",
            "candidate_status=ready",
            "candidate_missing=none",
            "oracle=visual_table",
            "oracle_flag=--debug-visual-table-oracle",
            "./build/lezac_cpp --debug-visual-table-oracle",
        ]:
            require(visual, snippet, "visual_table_ready")
        cases += 1

    print(f"debug_capture_summary_check=ok cases={cases}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
