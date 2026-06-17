#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 out_dir [asset_dir] target" >&2
    echo "targets: spawner_loop_start spawner_loop_end behavior4_branch_start behavior4_branch_end integration_8_8_start integration_8_8_end" >&2
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
    spawner_loop_start)
        ghidra=1000:7A6B
        label=spawner_loop_start
        static_region=spawner_loop
        ;;
    spawner_loop_end)
        ghidra=1000:7C2C
        label=spawner_loop_end
        static_region=spawner_loop
        ;;
    behavior4_branch_start)
        ghidra=1000:728C
        label=behavior4_branch_start
        static_region=behavior4_branch
        ;;
    behavior4_branch_end)
        ghidra=1000:731B
        label=behavior4_branch_end
        static_region=behavior4_branch
        ;;
    integration_8_8_start)
        ghidra=1000:73E5
        label=integration_8_8_start
        static_region=integration_8_8
        ;;
    integration_8_8_end)
        ghidra=1000:741B
        label=integration_8_8_end
        static_region=integration_8_8
        ;;
    *)
        echo "unsupported behavior-4 process-memory target: $target" >&2
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

quote_command() {
    printf "%q " "$@"
}

manifest_value() {
    local key=$1
    local path=$2
    awk -F= -v key="$key" '$1 == key { print substr($0, length(key) + 2); exit }' "$path"
}

run_environment_preflight() {
    if [[ "${LEZAC_BEHAVIOR4_PROCMEM_SKIP_ENVIRONMENT_PREFLIGHT:-0}" == "1" ]]; then
        {
            echo "environment_preflight=skipped"
            echo "environment_preflight_log=$environment_preflight_log"
        } >>"$manifest"
        echo "environment_preflight=skipped" >>"$raw_dump"
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
    echo "environment_preflight_log=$environment_preflight_log" >>"$raw_dump"

    if [[ $preflight_status -ne 0 ]]; then
        echo "environment_preflight=error" >>"$manifest"
        echo "environment_preflight=error" >>"$raw_dump"
        cat "$environment_preflight_log"
        echo "behavior4_procmem=error target=$target reason=environment_preflight_exit_$preflight_status manifest=$manifest raw_dump=$raw_dump environment_preflight_log=$environment_preflight_log"
        exit "$preflight_status"
    fi

    echo "environment_preflight=ok" >>"$manifest"
    echo "environment_preflight=ok" >>"$raw_dump"
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

capture_class=behavior4_runtime
scenario=${LEZAC_BEHAVIOR4_PROCMEM_SCENARIO:-monster_behavior4_target_selection}
expected_level=${LEZAC_BEHAVIOR4_PROCMEM_EXPECTED_LEVEL:-3}
runtime_route=focused_no_window_original_controls_process_memory
manifest="$out_dir/manifest.txt"
raw_dump="$out_dir/raw_debugger_dump.txt"
candidate_fixture="$out_dir/${target}_behavior4_candidate.txt"
procmem_out="$out_dir/procmem"
procmem_manifest="$procmem_out/manifest.txt"
environment_preflight_log="$out_dir/environment_preflight.log"
environment_preflight_command=(
    python3
    "$repo_dir/tools/preflight_original_evidence_environment.py"
    "$asset_dir"
    --probe-wsl
    --require-wsl-bash-on-windows
    --require-procmem-capture
)

sample_seconds=${LEZAC_BEHAVIOR4_PROCMEM_SAMPLE_SECONDS:-0.5}
sample_interval=${LEZAC_BEHAVIOR4_PROCMEM_SAMPLE_INTERVAL:-0.1}
tail_freeze_seconds=${LEZAC_BEHAVIOR4_PROCMEM_TAIL_FREEZE_SECONDS:-0.2}
start_key=${LEZAC_BEHAVIOR4_START_KEY:-1}
start_taps=${LEZAC_BEHAVIOR4_START_TAPS:-2}
level_start_seconds=${LEZAC_BEHAVIOR4_LEVEL_START_SECONDS:-3.0}
right_key=${LEZAC_BEHAVIOR4_RIGHT_KEY:-x}
right_hold_seconds=${LEZAC_BEHAVIOR4_RIGHT_HOLD_SECONDS:-2.0}
bomb_key=${LEZAC_BEHAVIOR4_BOMB_KEY:-n}
bomb_hold_seconds=${LEZAC_BEHAVIOR4_BOMB_HOLD_SECONDS:-0.25}
route_steps_csv=${LEZAC_BEHAVIOR4_ROUTE_STEPS:-}
runtime_freeze_before_route=${LEZAC_BEHAVIOR4_RUNTIME_FREEZE_BEFORE_ROUTE:-0}

procmem_command=(
    python3
    "$repo_dir/tools/capture_original_explosion_procmem.py"
    "$procmem_out"
    "$asset_dir"
    --approve-procmem
    --approve-instrumentation
    --approve-runtime-instrumentation
    --freeze-ghidra-offset "$ghidra"
    --start-key "$start_key"
    --start-taps "$start_taps"
    --level-start-seconds "$level_start_seconds"
    --right-key "$right_key"
    --right-hold-seconds "$right_hold_seconds"
    --bomb-key "$bomb_key"
    --bomb-hold-seconds "$bomb_hold_seconds"
    --sample-seconds "$sample_seconds"
    --sample-interval "$sample_interval"
    --route-state-interval 0
    --sample-screenshot-seconds ""
    --tail-freeze-check-seconds "$tail_freeze_seconds"
)
if [[ "$runtime_freeze_before_route" == "1" ]]; then
    procmem_command+=(--runtime-freeze-before-route)
else
    procmem_command+=(--runtime-freeze-before-bomb)
fi
if [[ -n "$route_steps_csv" ]]; then
    IFS=',' read -r -a route_steps <<<"$route_steps_csv"
    for route_step in "${route_steps[@]}"; do
        if [[ -n "$route_step" ]]; then
            procmem_command+=(--route-step "$route_step")
        fi
    done
fi

write_candidate_skeleton() {
    local runtime_cs=${1:-}
    local runtime_ds=${2:-}
    local freeze_runtime_value=${3:-}
    local freeze_observed_value=${4:-}

    {
        echo "# LEZAC behavior-4 process-memory oracle candidate."
        echo "# Candidate only: fill semantic rows before promotion."
        echo "# source_wrapper=$0"
        echo "capture=behavior4_runtime"
        echo "source=dosbox-debug-process-memory"
        echo "temp_copy=1"
        echo "visual_claim=0"
        echo "instrumented_runtime_child_memory=1"
        echo "target=$target"
        echo "scenario=$scenario"
        echo "level=$expected_level"
        echo "capture_class=$capture_class"
        echo "static_region=$static_region"
        echo "route=$runtime_route"
        if [[ -n "$runtime_cs" ]]; then
            echo "runtime_cs=$runtime_cs"
        else
            echo "# runtime_cs=<runtime-cs>"
        fi
        if [[ -n "$runtime_ds" ]]; then
            echo "runtime_ds=$runtime_ds"
        else
            echo "# runtime_ds=<runtime-ds>"
        fi
        echo "break ghidra=$ghidra runtime=${freeze_runtime_value:-<runtime-cs>:${ghidra#*:}} label=$label observed=process_memory_runtime_freeze_${freeze_observed_value:-unknown}"
        echo "# break ghidra=1000:7A6B runtime=${runtime_cs:-<runtime-cs>}:7A6B label=spawner_loop_start"
        echo "# break ghidra=1000:7C2C runtime=${runtime_cs:-<runtime-cs>}:7C2C label=spawner_loop_end"
        echo "# break ghidra=1000:728C runtime=${runtime_cs:-<runtime-cs>}:728C label=behavior4_branch_start"
        echo "# break ghidra=1000:731B runtime=${runtime_cs:-<runtime-cs>}:731B label=behavior4_branch_end"
        echo "# break ghidra=1000:73E5 runtime=${runtime_cs:-<runtime-cs>}:73E5 label=integration_8_8_start"
        echo "# break ghidra=1000:741B runtime=${runtime_cs:-<runtime-cs>}:741B label=integration_8_8_end"
        echo
        echo "# spawner index=<index> behavior=4 ai0=<byte> ai1=<byte> ai2=<byte> hp=<hp> spawn_timer=<ticks>"
        echo "# actor_before slot=<slot> behavior=4 x=0x0000 y=0x0000 vx8=<vx8> vy8=<vy8> motion_timer=<ticks> target=<slot> hp=<hp> dead=<0-or-1>"
        echo "# actor_after slot=<slot> behavior=4 x=0x0000 y=0x0000 vx8=<vx8> vy8=<vy8> motion_timer=<ticks> target=<slot> hp=<hp> dead=<0-or-1>"
        echo "# players p1_dead=<0-or-1> p2_dead=<0-or-1> p1_state=<state> p2_state=<state> target_before=<slot> target_after=<slot>"
        echo "# freeze_old_bytes=$freeze_old_bytes"
        echo "# freeze_patch_bytes=$freeze_patch_bytes"
        echo "# freeze_loaded_bytes=$freeze_loaded_bytes"
        echo "# freeze_runtime_patch_applied=$freeze_runtime_patch_applied"
        echo "# freeze_runtime_before_route=$runtime_freeze_before_route"
        echo "# instrumented_freeze_tail_frame=$instrumented_freeze_tail_frame"
        echo
        echo "# dump DS:7900"
        echo "# <runtime-ds>:7900  <actor/player state bytes>"
        echo "# dump DS:7A00"
        echo "# <runtime-ds>:7A00  <spawner/behavior state bytes>"
        echo "# dump DS:7B00"
        echo "# <runtime-ds>:7B00  <nearby behavior state bytes>"
        echo "# route_state_dumps=$procmem_out/route_state_dumps.txt"
    } >"$candidate_fixture"
}

freeze_old_bytes=
freeze_patch_bytes=
freeze_loaded_bytes=
freeze_runtime_patch_applied=
instrumented_freeze_tail_frame=
write_candidate_skeleton

{
    echo "capture=behavior4_process_memory"
    echo "source=dosbox-debug-process-memory"
    echo "target=$target"
    echo "label=$label"
    echo "scenario=$scenario"
    echo "expected_level=$expected_level"
    echo "capture_class=$capture_class"
    echo "static_region=$static_region"
    echo "route=$runtime_route"
    echo "ghidra=$ghidra"
    echo "asset_dir=$asset_dir"
    echo "out_dir=$out_dir"
    echo "procmem_out=$procmem_out"
    echo "procmem_manifest=$procmem_manifest"
    echo "candidate_fixture=$candidate_fixture"
    echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
    echo "environment_preflight_log=$environment_preflight_log"
    echo "input_start_key=$start_key"
    echo "input_start_taps=$start_taps"
    echo "input_level_start_seconds=$level_start_seconds"
    echo "input_right_key=$right_key"
    echo "input_right_hold_seconds=$right_hold_seconds"
    echo "input_route_steps=$route_steps_csv"
    echo "input_bomb_key=$bomb_key"
    echo "input_bomb_hold_seconds=$bomb_hold_seconds"
    echo "input_runtime_freeze_before_route=$runtime_freeze_before_route"
    echo "visual_claim=0"
} >"$manifest"

{
    echo "behavior4_procmem=planned"
    echo "target=$target"
    echo "label=$label"
    echo "scenario=$scenario"
    echo "expected_level=$expected_level"
    echo "capture_class=$capture_class"
    echo "static_region=$static_region"
    echo "ghidra=$ghidra"
    echo "procmem_out=$procmem_out"
    echo "procmem_manifest=$procmem_manifest"
    echo "candidate_fixture=$candidate_fixture"
    echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
    echo "environment_preflight_log=$environment_preflight_log"
    echo "command=${procmem_command[*]}"
} >"$raw_dump"

if [[ ! -e "$asset_dir/LEZAC.EXE" ]]; then
    echo "missing $asset_dir/LEZAC.EXE" >&2
    exit 67
fi

if [[ "${LEZAC_BEHAVIOR4_PROCMEM_DRY_RUN:-0}" == "1" ]]; then
    echo "environment_preflight=dry_run" >>"$manifest"
    echo "environment_preflight=dry_run" >>"$raw_dump"
    echo "behavior4_procmem=ok mode=dry_run target=$target ghidra=$ghidra capture_class=$capture_class static_region=$static_region manifest=$manifest raw_dump=$raw_dump candidate_fixture=$candidate_fixture procmem_out=$procmem_out environment_preflight=dry_run"
    exit 0
fi

if [[ "${LEZAC_BEHAVIOR4_APPROVE_PROCMEM:-0}" != "1" ]]; then
    echo "refusing process-memory capture without LEZAC_BEHAVIOR4_APPROVE_PROCMEM=1" >&2
    exit 64
fi
if [[ "${LEZAC_BEHAVIOR4_APPROVE_RUNTIME_INSTRUMENTATION:-0}" != "1" ]]; then
    echo "refusing runtime instrumentation without LEZAC_BEHAVIOR4_APPROVE_RUNTIME_INSTRUMENTATION=1" >&2
    exit 64
fi

run_environment_preflight

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
    echo "runtime_metadata=observed"
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
    echo "behavior4_procmem=complete"
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

write_candidate_skeleton "$runtime_cs" "$runtime_ds" "$freeze_runtime" "$instrumented_freeze_observed"
if [[ -e "$procmem_out/route_state_dumps.txt" ]]; then
    {
        echo
        cat "$procmem_out/route_state_dumps.txt"
    } >>"$candidate_fixture"
fi

echo "behavior4_procmem=ok mode=capture target=$target ghidra=$ghidra runtime_cs=$runtime_cs runtime_ds=$runtime_ds freeze_runtime=$freeze_runtime freeze_runtime_patch_applied=$freeze_runtime_patch_applied freeze_observed=$instrumented_freeze_observed manifest=$manifest raw_dump=$raw_dump candidate_fixture=$candidate_fixture procmem_manifest=$procmem_manifest"
