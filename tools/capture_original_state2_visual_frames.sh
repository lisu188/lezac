#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 out_dir [asset_dir] state2_death_table_consumption" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage
    exit 64
fi

out_dir=$1
if [[ $# -eq 2 ]]; then
    asset_dir=.
    scenario=$2
else
    asset_dir=$2
    scenario=$3
fi

case "$scenario" in
    state2_death_table_consumption) ;;
    *)
        echo "unsupported state-2 visual frame scenario: $scenario" >&2
        exit 65
        ;;
esac

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$out_dir"
out_dir=$(cd "$out_dir" && pwd)
asset_dir=$(cd "$asset_dir" && pwd)

case "$out_dir" in
    "$repo_dir"|"$repo_dir"/*)
        echo "choose an output directory outside the repository" >&2
        exit 66
        ;;
esac

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required command: $1" >&2
        exit 69
    fi
}

quote_command() {
    printf "%q " "$@"
}

manifest="$out_dir/manifest.txt"
log="$out_dir/original_state2_visual_frames.log"
environment_preflight_log="$out_dir/environment_preflight.log"
frame_plan="$out_dir/frame_plan.txt"
route=debugger_seeded
visual_claim=0
environment_preflight_command=(
    python3
    "$repo_dir/tools/preflight_original_evidence_environment.py"
    "$asset_dir"
    --require-frame-capture
    --probe-wsl
    --require-wsl-bash-on-windows
)

write_frame_plan() {
    {
        echo "frame label=state2_game_4a file=state2_game_4a.png visual_frame=0x4a row3_sprite=67 row=10,10,7d,43"
        echo "frame label=state2_game_4b file=state2_game_4b.png visual_frame=0x4b row3_sprite=68 row=10,10,7d,44"
        echo "frame label=state2_game_4c file=state2_game_4c.png visual_frame=0x4c row3_sprite=69 row=10,10,7d,45"
        echo "frame label=state2_game_4d file=state2_game_4d.png visual_frame=0x4d row3_sprite=70 row=10,10,7d,46"
        echo "frame label=state2_game_4e file=state2_game_4e.png visual_frame=0x4e row3_sprite=71 row=10,10,7d,47"
        echo "frame label=state2_game_4f file=state2_game_4f.png visual_frame=0x4f row3_sprite=72 row=10,10,7d,48"
    } >"$frame_plan"
}

write_initial_metadata() {
    write_frame_plan
    {
        echo "scenario=$scenario"
        echo "capture=state2_visual_frames"
        echo "source=LEZAC.EXE via DOSBox"
        echo "route=$route"
        echo "asset_dir=$asset_dir"
        echo "captures=$out_dir"
        echo "visual_claim=$visual_claim"
        echo "frame_plan=$frame_plan"
        echo "expected_frame_count=6"
        echo "expected_labels=state2_game_4a,state2_game_4b,state2_game_4c,state2_game_4d,state2_game_4e,state2_game_4f"
        echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
        echo "environment_preflight_log=$environment_preflight_log"
        echo "compare_command=python3 $repo_dir/tools/compare_state2_visual_row_game_previews.py <bundle-out> <lezac_cpp> $out_dir"
        cat "$frame_plan"
    } >"$manifest"
    {
        echo "capture=state2_visual_frames"
        echo "scenario=$scenario"
        echo "route=$route"
        echo "manifest=$manifest"
        echo "frame_plan=$frame_plan"
        echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
        echo "environment_preflight_log=$environment_preflight_log"
    } >"$log"
}

run_environment_preflight() {
    if [[ "${LEZAC_STATE2_VISUAL_FRAME_CAPTURE_SKIP_ENVIRONMENT_PREFLIGHT:-0}" == "1" ]]; then
        echo "environment_preflight=skipped" >>"$manifest"
        echo "environment_preflight=skipped" >>"$log"
        return
    fi

    set +e
    "${environment_preflight_command[@]}" >"$environment_preflight_log" 2>&1
    preflight_status=$?
    set -e

    {
        echo "environment_preflight_exit=$preflight_status"
        echo "environment_preflight_log=$environment_preflight_log"
    } >>"$manifest"
    {
        echo "environment_preflight_exit=$preflight_status"
        echo "environment_preflight_log=$environment_preflight_log"
    } >>"$log"

    if [[ $preflight_status -ne 0 ]]; then
        echo "environment_preflight=error" >>"$manifest"
        echo "environment_preflight=error" >>"$log"
        echo "state2_visual_frame_capture=error scenario=$scenario reason=environment_preflight_exit_$preflight_status manifest=$manifest environment_preflight_log=$environment_preflight_log"
        exit "$preflight_status"
    fi

    echo "environment_preflight=ok" >>"$manifest"
    echo "environment_preflight=ok" >>"$log"
}

write_initial_metadata

if [[ ! -e "$asset_dir/LEZAC.EXE" ]]; then
    echo "missing $asset_dir/LEZAC.EXE" >&2
    exit 67
fi

if [[ "${LEZAC_STATE2_VISUAL_FRAME_CAPTURE_DRY_RUN:-0}" == "1" ]]; then
    echo "environment_preflight=dry_run" >>"$manifest"
    echo "environment_preflight=dry_run" >>"$log"
    echo "state2_visual_frame_capture=ok mode=dry_run scenario=$scenario route=$route expected_frames=6 manifest=$manifest frame_plan=$frame_plan environment_preflight=dry_run environment_preflight_log=$environment_preflight_log"
    exit 0
fi

run_environment_preflight
require dosbox
require xdotool
require xvfb-run
require timeout

{
    echo "capture_note=live automation for this scenario still requires debugger-seeded setup"
    echo "recommended_debug_helper=$repo_dir/tools/capture_original_visual_table_debug.sh"
    echo "compare_after_capture=python3 $repo_dir/tools/compare_state2_visual_row_game_previews.py <bundle-out> <lezac_cpp> $out_dir"
} >>"$manifest"

echo "state2_visual_frame_capture=error scenario=$scenario reason=debugger_seeded_frame_capture_not_automated manifest=$manifest frame_plan=$frame_plan"
exit 70
