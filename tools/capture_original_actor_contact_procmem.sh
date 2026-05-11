#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 out_dir [asset_dir] target" >&2
    echo "targets: actor_update_start actor_update_end contact_scanner_start contact_scanner_end" >&2
}

if [[ $# -lt 2 || $# -gt 3 ]]; then
    usage
    exit 64
fi

out_dir=$1
if [[ $# -eq 2 ]]; then
    asset_dir=.
    target=$2
else
    asset_dir=$2
    target=$3
fi

case "$target" in
    actor_update_start)
        ghidra=1000:6053
        label=actor_update_start
        scenario=object_collision_jump_live
        ;;
    actor_update_end)
        ghidra=1000:777F
        label=actor_update_end
        scenario=object_collision_jump_live
        ;;
    contact_scanner_start)
        ghidra=1000:5CB0
        label=contact_scanner_start
        scenario=monster_contact_damage_live
        ;;
    contact_scanner_end)
        ghidra=1000:604F
        label=contact_scanner_end
        scenario=monster_contact_damage_live
        ;;
    *)
        echo "unsupported actor/contact process-memory target: $target" >&2
        usage
        exit 65
        ;;
esac

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required command: $1" >&2
        exit 69
    fi
}

manifest_value() {
    local key=$1
    local path=$2
    awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2); exit }' "$path"
}

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

manifest="$out_dir/manifest.txt"
raw_dump="$out_dir/raw_debugger_dump.txt"
procmem_out="$out_dir/procmem"
procmem_manifest="$procmem_out/manifest.txt"
procmem_candidate="$procmem_out/explosion_playback_oracle_original_candidate.txt"

sample_seconds=${LEZAC_ACTOR_CONTACT_PROCMEM_SAMPLE_SECONDS:-0.5}
sample_interval=${LEZAC_ACTOR_CONTACT_PROCMEM_SAMPLE_INTERVAL:-0.1}
tail_freeze_seconds=${LEZAC_ACTOR_CONTACT_PROCMEM_TAIL_FREEZE_SECONDS:-0.2}

procmem_command=(
    python3
    "$repo_dir/tools/capture_original_explosion_procmem.py"
    "$procmem_out"
    "$asset_dir"
    --approve-procmem
    --approve-instrumentation
    --approve-runtime-instrumentation
    --freeze-ghidra-offset "$ghidra"
    --runtime-freeze-before-bomb
    --sample-seconds "$sample_seconds"
    --sample-interval "$sample_interval"
    --route-state-interval 0
    --sample-screenshot-seconds ""
    --tail-freeze-check-seconds "$tail_freeze_seconds"
)

{
    echo "capture=actor_contact_process_memory"
    echo "source=dosbox-debug-process-memory"
    echo "target=$target"
    echo "label=$label"
    echo "scenario=$scenario"
    echo "route=focused_no_window_original_controls_process_memory"
    echo "ghidra=$ghidra"
    echo "asset_dir=$asset_dir"
    echo "out_dir=$out_dir"
    echo "procmem_out=$procmem_out"
    echo "procmem_manifest=$procmem_manifest"
    echo "procmem_candidate=$procmem_candidate"
    echo "visual_claim=0"
} >"$manifest"

{
    echo "actor_contact_procmem=planned"
    echo "target=$target"
    echo "label=$label"
    echo "scenario=$scenario"
    echo "ghidra=$ghidra"
    echo "procmem_out=$procmem_out"
    echo "procmem_manifest=$procmem_manifest"
    echo "procmem_candidate=$procmem_candidate"
    echo "command=${procmem_command[*]}"
} >"$raw_dump"

if [[ ! -e "$asset_dir/LEZAC.EXE" ]]; then
    echo "missing $asset_dir/LEZAC.EXE" >&2
    exit 67
fi

if [[ "${LEZAC_ACTOR_CONTACT_PROCMEM_DRY_RUN:-0}" == "1" ]]; then
    echo "actor_contact_procmem=ok mode=dry_run target=$target ghidra=$ghidra manifest=$manifest raw_dump=$raw_dump procmem_out=$procmem_out"
    exit 0
fi

if [[ "${LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM:-0}" != "1" ]]; then
    echo "refusing process-memory capture without LEZAC_ACTOR_CONTACT_APPROVE_PROCMEM=1" >&2
    exit 64
fi
if [[ "${LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION:-0}" != "1" ]]; then
    echo "refusing runtime instrumentation without LEZAC_ACTOR_CONTACT_APPROVE_RUNTIME_INSTRUMENTATION=1" >&2
    exit 64
fi

require python3

"${procmem_command[@]}"

if [[ ! -e "$procmem_manifest" ]]; then
    echo "missing process-memory manifest: $procmem_manifest" >&2
    exit 70
fi

runtime_cs=$(manifest_value runtime_cs "$procmem_manifest")
runtime_ds=$(manifest_value runtime_ds "$procmem_manifest")
freeze_runtime=$(manifest_value freeze_runtime "$procmem_manifest")
freeze_old_bytes=$(manifest_value freeze_old_bytes "$procmem_manifest")
freeze_patch_bytes=$(manifest_value freeze_patch_bytes "$procmem_manifest")
freeze_loaded_bytes=$(manifest_value freeze_loaded_bytes "$procmem_manifest")
freeze_runtime_patch_applied=$(manifest_value freeze_runtime_patch_applied "$procmem_manifest")
instrumented_freeze_observed=$(manifest_value instrumented_freeze_observed "$procmem_manifest")
instrumented_freeze_tail_frame=$(manifest_value instrumented_freeze_tail_frame "$procmem_manifest")

{
    echo "runtime_cs=$runtime_cs"
    echo "runtime_ds=$runtime_ds"
    echo "freeze_runtime=$freeze_runtime"
    echo "freeze_old_bytes=$freeze_old_bytes"
    echo "freeze_patch_bytes=$freeze_patch_bytes"
    echo "freeze_loaded_bytes=$freeze_loaded_bytes"
    echo "freeze_runtime_patch_applied=$freeze_runtime_patch_applied"
    echo "instrumented_freeze_observed=$instrumented_freeze_observed"
    echo "instrumented_freeze_tail_frame=$instrumented_freeze_tail_frame"
} >>"$manifest"

{
    echo "actor_contact_procmem=complete"
    echo "runtime_cs=$runtime_cs"
    echo "runtime_ds=$runtime_ds"
    echo "freeze_runtime=$freeze_runtime"
    echo "freeze_old_bytes=$freeze_old_bytes"
    echo "freeze_patch_bytes=$freeze_patch_bytes"
    echo "freeze_loaded_bytes=$freeze_loaded_bytes"
    echo "freeze_runtime_patch_applied=$freeze_runtime_patch_applied"
    echo "instrumented_freeze_observed=$instrumented_freeze_observed"
    echo "instrumented_freeze_tail_frame=$instrumented_freeze_tail_frame"
} >>"$raw_dump"

echo "actor_contact_procmem=ok mode=capture target=$target ghidra=$ghidra runtime_cs=$runtime_cs runtime_ds=$runtime_ds freeze_runtime=$freeze_runtime freeze_observed=$instrumented_freeze_observed manifest=$manifest raw_dump=$raw_dump procmem_manifest=$procmem_manifest"
