#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "usage: $0 out_dir [asset_dir]" >&2
    exit 64
fi

mkdir -p "$1"
out_dir=$(cd "$1" && pwd)
asset_dir=$(realpath "${2:-.}")

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required command: $1" >&2
        exit 69
    fi
}

require dosbox
require xdotool
require xvfb-run

if [[ "${LEZAC_ORIGINAL_CAPTURE_INSIDE_XVFB:-0}" != "1" ]]; then
    LEZAC_ORIGINAL_CAPTURE_INSIDE_XVFB=1 exec xvfb-run -a "$0" "$out_dir" "$asset_dir"
fi

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

log="$out_dir/original_capture.log"
: >"$log"
echo "capture=original_dosbox" >>"$log"
echo "asset_dir=$asset_dir" >>"$log"
echo "run_dir=$run_dir" >>"$log"
echo "captures=$out_dir" >>"$log"
echo "command=dosbox -conf $conf -c \"mount c $run_dir\" -c \"c:\" -c \"LEZAC.EXE\"" >>"$log"

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
    xdotool windowfocus "$win"
    sleep 0.1
}

capture() {
    local label=$1
    focus
    echo "checkpoint=$label time=$(date -Is)" >>"$log"
    xdotool key --clearmodifiers ctrl+F5
    sleep 0.25
}

sleep 2.0
capture 000_menu
xdotool key --clearmodifiers 1
sleep 1.0
capture 010_level1_start
xdotool keydown Right
sleep 1.25
xdotool keyup Right
sleep 0.25
capture 020_level1_tile24_approx
xdotool key --clearmodifiers n
sleep 0.30
capture 030_level1_bomb
sleep 0.75
capture 040_level1_explosion_candidate
sleep 0.25
capture 050_level1_playback_candidate

xdotool key --clearmodifiers Escape
sleep 0.1
xdotool key --clearmodifiers Escape
sleep 0.2

echo "original_frames=$out_dir"
