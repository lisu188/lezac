#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "usage: $0 out_dir [asset_dir] [scenario]" >&2
    exit 64
fi

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mkdir -p "$1"
out_dir=$(cd "$1" && pwd)
asset_dir=$(realpath "${2:-.}")
scenario=${3:-level1_bomb_route}

case "$scenario" in
    level1_bomb_route|monster_bomb_reward) ;;
    *)
        echo "unsupported original capture scenario: $scenario" >&2
        exit 65
        ;;
esac

if [[ "$scenario" == "monster_bomb_reward" ]]; then
    route="keyboard_partial"
else
    route="keyboard_original_controls"
fi

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required command: $1" >&2
        exit 69
    fi
}

quote_command() {
    printf "%q " "$@"
}

log="$out_dir/original_capture.log"
manifest="$out_dir/manifest.txt"
environment_preflight_log="$out_dir/environment_preflight.log"
environment_preflight_command=(
    python3
    "$repo_dir/tools/preflight_original_evidence_environment.py"
    "$asset_dir"
    --require-frame-capture
    --probe-wsl
    --require-wsl-bash-on-windows
)

write_initial_metadata() {
    : >"$log"
    : >"$manifest"
    {
        echo "capture=original_dosbox"
        echo "scenario=$scenario"
        echo "route=$route"
        echo "asset_dir=$asset_dir"
        echo "captures=$out_dir"
        echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
        echo "environment_preflight_log=$environment_preflight_log"
    } >>"$log"
    {
        echo "scenario=$scenario"
        echo "source=LEZAC.EXE via DOSBox"
        echo "route=$route"
        echo "asset_dir=$asset_dir"
        echo "captures=$out_dir"
        echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
        echo "environment_preflight_log=$environment_preflight_log"
        echo "startup_seconds=${LEZAC_ORIGINAL_STARTUP_SECONDS:-6.0}"
        echo "level_start_seconds=${LEZAC_ORIGINAL_LEVEL_START_SECONDS:-1.5}"
        echo "start_key=${LEZAC_ORIGINAL_START_KEY:-1}"
        echo "start_taps=${LEZAC_ORIGINAL_START_TAPS:-2}"
        echo "start_tap_gap_seconds=${LEZAC_ORIGINAL_START_TAP_GAP_SECONDS:-0.4}"
        echo "start_text=${LEZAC_ORIGINAL_START_TEXT:-}"
        echo "right_key=${LEZAC_ORIGINAL_ROUTE_RIGHT_KEY:-x}"
        echo "right_hold_seconds=${LEZAC_ORIGINAL_ROUTE_RIGHT_SECONDS:-2.0}"
        echo "fire_key=${LEZAC_ORIGINAL_FIRE_KEY:-n}"
        echo "fire_hold_seconds=${LEZAC_ORIGINAL_FIRE_HOLD_SECONDS:-0.25}"
    } >>"$manifest"
}

run_environment_preflight() {
    if [[ "${LEZAC_ORIGINAL_FRAME_CAPTURE_SKIP_ENVIRONMENT_PREFLIGHT:-0}" == "1" ]]; then
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
        echo "original_frame_capture=error scenario=$scenario reason=environment_preflight_exit_$preflight_status manifest=$manifest environment_preflight_log=$environment_preflight_log"
        exit "$preflight_status"
    fi

    echo "environment_preflight=ok" >>"$manifest"
    echo "environment_preflight=ok" >>"$log"
}

if [[ "${LEZAC_ORIGINAL_CAPTURE_PREFLIGHT_DONE:-0}" != "1" ]]; then
    write_initial_metadata
    run_environment_preflight
fi

if [[ "${LEZAC_ORIGINAL_CAPTURE_INSIDE_XVFB:-0}" != "1" ]]; then
    LEZAC_ORIGINAL_CAPTURE_INSIDE_XVFB=1 \
    LEZAC_ORIGINAL_CAPTURE_PREFLIGHT_DONE=1 \
        exec xvfb-run -a "$0" "$out_dir" "$asset_dir" "$scenario"
fi

require dosbox
require xdotool

run_dir=$(mktemp -d /tmp/lezac-original-frame-capture.XXXXXX)
cleanup() {
    if [[ -n "${dosbox_pid:-}" ]]; then
        kill "$dosbox_pid" 2>/dev/null || true
        wait "$dosbox_pid" 2>/dev/null || true
    fi
    rm -rf "$run_dir"
}
trap cleanup EXIT

shopt -s nullglob
assets=(
    "$asset_dir"/LEZAC.EXE
    "$asset_dir"/*.DAT
    "$asset_dir"/*.SPR
    "$asset_dir"/*.PAL
    "$asset_dir"/*.SCH
    "$asset_dir"/*.SON
    "$asset_dir"/*.MST
    "$asset_dir"/*.CAR
    "$asset_dir"/*.ZBG
    "$asset_dir"/*.DOC
)
shopt -u nullglob

if [[ ! -e "$asset_dir/LEZAC.EXE" ]]; then
    echo "missing $asset_dir/LEZAC.EXE" >&2
    exit 66
fi
cp "${assets[@]}" "$run_dir/"

conf="$run_dir/dosbox-frame-capture.conf"
cat >"$conf" <<EOF_CONF
[sdl]
fullscreen=false
fulldouble=false
output=surface

[dosbox]
captures=$out_dir

[render]
frameskip=0
aspect=false
scaler=none

[cpu]
cycles=fixed 6000
EOF_CONF

echo "run_dir=$run_dir" >>"$log"
echo "command=dosbox -conf $conf -c \"mount c $run_dir\" -c \"c:\" -c \"LEZAC.EXE\"" >>"$log"
{
    echo "run_dir=$run_dir"
    echo "command=dosbox -conf $conf -c \"mount c $run_dir\" -c \"c:\" -c \"LEZAC.EXE\""
} >>"$manifest"

dosbox -conf "$conf" \
    -c "mount c $run_dir" \
    -c "c:" \
    -c "LEZAC.EXE" &
dosbox_pid=$!

win=""
for _ in $(seq 1 80); do
    win=$(xdotool search --name DOSBox 2>/dev/null | head -n 1 || true)
    if [[ -n "$win" ]]; then
        break
    fi
    sleep 0.1
done

if [[ -z "$win" ]]; then
    echo "window_not_found" >&2
    exit 1
fi

focus() {
    xdotool windowactivate --sync "$win" 2>/dev/null || xdotool windowfocus "$win"
    sleep 0.1
}

press() {
    focus
    xdotool key --clearmodifiers "$@"
    sleep 0.18
}

type_text() {
    focus
    xdotool type --delay 50 "$1"
    sleep 0.1
}

key_down() {
    focus
    xdotool keydown "$@"
}

key_up() {
    focus
    xdotool keyup "$@"
    sleep 0.1
}

hold_key() {
    local key_name=$1
    local seconds=$2
    focus
    xdotool keydown "$key_name"
    sleep "$seconds"
    xdotool keyup "$key_name"
    sleep 0.1
}

fire() {
    hold_key "${LEZAC_ORIGINAL_FIRE_KEY:-n}" "${LEZAC_ORIGINAL_FIRE_HOLD_SECONDS:-0.25}"
}

snapshot_files() {
    find "$out_dir" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.bmp' \) \
        -printf '%f\n' | sort
}

capture() {
    local label=$1
    local before="$run_dir/before-$label.txt"
    local after="$run_dir/after-$label.txt"
    snapshot_files >"$before"
    focus
    echo "checkpoint=$label time=$(date -Is)" >>"$log"
    xdotool key --clearmodifiers ctrl+F5
    sleep 0.35
    snapshot_files >"$after"
    local new_file
    new_file=$(comm -13 "$before" "$after" | tail -n 1 || true)
    if [[ -n "$new_file" ]]; then
        local ext=${new_file##*.}
        ext=${ext,,}
        local target="$label.$ext"
        mv -f "$out_dir/$new_file" "$out_dir/$target"
        echo "frame label=$label file=$target" >>"$manifest"
        echo "captured=$target" >>"$log"
    else
        echo "frame label=$label file=missing" >>"$manifest"
        echo "capture_missing=$label" >>"$log"
    fi
}

start_level() {
    sleep "${LEZAC_ORIGINAL_STARTUP_SECONDS:-6.0}"
    capture 000_menu
    if [[ -n "${LEZAC_ORIGINAL_START_TEXT:-}" ]]; then
        type_text "$LEZAC_ORIGINAL_START_TEXT"
    else
        for ((tap = 0; tap < ${LEZAC_ORIGINAL_START_TAPS:-2}; tap++)); do
            press "${LEZAC_ORIGINAL_START_KEY:-1}"
            sleep "${LEZAC_ORIGINAL_START_TAP_GAP_SECONDS:-0.4}"
        done
    fi
    sleep "${LEZAC_ORIGINAL_LEVEL_START_SECONDS:-1.5}"
}

capture_level1_bomb_route() {
    start_level
    capture 010_level1_start
    hold_key "${LEZAC_ORIGINAL_ROUTE_RIGHT_KEY:-x}" "${LEZAC_ORIGINAL_ROUTE_RIGHT_SECONDS:-2.0}"
    sleep 0.25
    capture 020_level1_tile24_aligned
    fire
    sleep 0.30
    capture 030_level1_tile24_bomb
    sleep 0.75
    capture 040_level1_tile24_explosion
    sleep 0.25
    capture 050_level1_tile24_playback_4
    sleep 0.25
    capture 060_level1_tile24_playback_12
}

capture_monster_bomb_reward() {
    start_level
    capture 010_monster_bomb_start
    fire
    sleep 0.30
    capture 020_monster_bomb_armed
    {
        echo "frame label=030_monster_bomb_death file=not_captured reason=synthetic_cpp_fixture_requires_debugger_seed"
        echo "frame label=040_monster_bomb_reward_collected file=not_captured reason=synthetic_cpp_fixture_requires_debugger_seed"
    } >>"$manifest"
    {
        echo "capture_skipped=030_monster_bomb_death reason=synthetic_cpp_fixture_requires_debugger_seed"
        echo "capture_skipped=040_monster_bomb_reward_collected reason=synthetic_cpp_fixture_requires_debugger_seed"
    } >>"$log"
}

if [[ "$scenario" == "monster_bomb_reward" ]]; then
    capture_monster_bomb_reward
else
    capture_level1_bomb_route
fi

press Escape
sleep 0.1
press Escape
sleep 0.2

echo "original_frames=$out_dir"
