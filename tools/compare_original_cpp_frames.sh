#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
    echo "usage: $0 out_dir [asset_dir] [scenario]" >&2
    exit 64
fi

out_dir=$(realpath -m "$1")
asset_dir=$(realpath "${2:-.}")
scenario=${3:-level1_bomb_route}

repo_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cpp_exe="$repo_dir/build/lezac_cpp"

if [[ "$out_dir" == "/" ]]; then
    echo "refusing to use filesystem root as output directory" >&2
    exit 64
fi

case "$out_dir/" in
    "$repo_dir/"*)
        echo "choose an output directory outside the repository, for example /tmp/lezac-frame-compare" >&2
        exit 64
        ;;
esac

if [[ ! -x "$cpp_exe" ]]; then
    echo "missing executable: $cpp_exe" >&2
    echo "run: cmake --build build" >&2
    exit 66
fi

mkdir -p "$out_dir"
cpp_dir="$out_dir/cpp"
original_dir="$out_dir/original"
diff_dir="$out_dir/diff"
rm -rf "$cpp_dir" "$original_dir" "$diff_dir"
mkdir -p "$cpp_dir" "$original_dir" "$diff_dir"

"$repo_dir/tools/capture_cpp_frames.sh" "$cpp_exe" "$cpp_dir" "$scenario"

if [[ "$scenario" != "level1_bomb_route" ]]; then
    echo "original capture currently supports level1_bomb_route only" >&2
    exit 65
fi

"$repo_dir/tools/capture_original_dosbox_frames.sh" "$original_dir" "$asset_dir"

summary="$out_dir/frame_compare_summary.txt"
: >"$summary"
while IFS= read -r cpp_frame; do
    label=$(basename "$cpp_frame" .ppm)
    original_frame="$original_dir/$label.png"
    if [[ ! -f "$original_frame" ]]; then
        echo "compare label=$label status=missing_original" | tee -a "$summary"
        continue
    fi
    diff_frame="$diff_dir/$label.ppm"
    set +e
    compare_output=$("$repo_dir/tools/frame_compare.py" "$cpp_frame" "$original_frame" \
        --diff "$diff_frame" 2>&1)
    compare_status=$?
    set -e
    echo "$compare_output" | sed "s/^/compare label=$label /" | tee -a "$summary"
    if [[ $compare_status -gt 1 ]]; then
        exit "$compare_status"
    fi
done < <(find "$cpp_dir" -maxdepth 1 -name '*.ppm' -printf '%p\n' | sort)

{
    echo "scenario=$scenario"
    echo "asset_dir=$asset_dir"
    echo "cpp_dir=$cpp_dir"
    echo "original_dir=$original_dir"
    echo "diff_dir=$diff_dir"
    echo "summary=$summary"
} >"$out_dir/manifest.txt"

echo "frame_compare_bundle=$out_dir"
