#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "usage: $0 /path/to/lezac_cpp out_dir [scenario]" >&2
    exit 64
fi

exe=$1
out_dir=$2
scenario=${3:-level1_bomb_route}

mkdir -p "$out_dir"

SDL_VIDEODRIVER=${SDL_VIDEODRIVER:-dummy} \
SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy} \
    "$exe" --capture-frame-sequence "$scenario" "$out_dir"

echo "cpp_frames=$out_dir"
