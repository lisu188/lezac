#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "usage: $0 out_dir [asset_dir] scenario" >&2
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
    monster_contact_damage_live|object_collision_jump_live|monster_behavior4_chase) ;;
    *)
        echo "unsupported contact-scanner scenario: $scenario" >&2
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

run_environment_preflight() {
    if [[ "${LEZAC_CONTACT_SCANNER_DEBUG_SKIP_ENVIRONMENT_PREFLIGHT:-0}" == "1" ]]; then
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
        echo "contact_scanner_debug_capture=error scenario=$scenario reason=environment_preflight_exit_$preflight_status manifest=$manifest raw_dump=$raw_dump environment_preflight_log=$environment_preflight_log"
        exit "$preflight_status"
    fi

    echo "environment_preflight=ok" >>"$manifest"
    echo "environment_preflight=ok" >>"$raw_dump"
}

write_runtime_command_plan() {
    local runtime_cs=$1
    local runtime_ds=$2
    local dump_segment=DS

    if [[ -z "$runtime_cs" ]]; then
        return
    fi
    if [[ -n "$runtime_ds" ]]; then
        dump_segment=$runtime_ds
    fi

    {
        echo "# DOSBox debugger commands expanded from observed runtime registers."
        echo "# runtime_cs=$runtime_cs"
        if [[ -n "$runtime_ds" ]]; then
            echo "# runtime_ds=$runtime_ds"
        fi
        grep -v '^#' "$commands_file" |
            sed -e "s/<CS>/$runtime_cs/g" -e "s/D DS:/D $dump_segment:/g"
    } >"$runtime_commands_file"
}

append_runtime_registers() {
    local runtime_cs
    local runtime_ds

    runtime_cs=$(grep -aoE 'CS=[0-9A-Fa-f]{4}' "$log" 2>/dev/null | tail -n 1 | cut -d= -f2 || true)
    runtime_ds=$(grep -aoE 'DS=[0-9A-Fa-f]{4}' "$log" 2>/dev/null | tail -n 1 | cut -d= -f2 || true)

    if [[ -z "$runtime_cs" && -z "$runtime_ds" ]]; then
        return
    fi

    {
        echo "runtime_metadata=observed"
        if [[ -n "$runtime_cs" ]]; then
            echo "runtime_cs=$runtime_cs"
        fi
        if [[ -n "$runtime_ds" ]]; then
            echo "runtime_ds=$runtime_ds"
        fi
        echo "ghidra_segment=1000"
    } >>"$raw_dump"

    {
        if [[ -n "$runtime_cs" ]]; then
            echo "runtime_cs=$runtime_cs"
        fi
        if [[ -n "$runtime_ds" ]]; then
            echo "runtime_ds=$runtime_ds"
        fi
    } >>"$manifest"

    write_runtime_command_plan "$runtime_cs" "$runtime_ds"
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
log="$out_dir/contact_scanner_debug_capture.log"
commands_file="$out_dir/debugger_commands.txt"
runtime_commands_file="$out_dir/debugger_commands_runtime.txt"
candidate_fixture="$out_dir/candidate_fixture.txt"
environment_preflight_log="$out_dir/environment_preflight.log"
environment_preflight_command=(
    python3
    "$repo_dir/tools/preflight_original_evidence_environment.py"
    "$asset_dir"
    --require-debug-capture
)

runtime_route=debugger_seeded
expected_level=1

cat >"$commands_file" <<'EOF_COMMANDS'
# DOSBox debugger command plan.
# Replace <CS> with the runtime code segment after stopping in LEZAC.EXE.
# Keep Ghidra offsets unchanged when translating 1000:offset to <CS>:offset.
BP <CS>:5CB0  # contact scanner start
BP <CS>:604F  # contact scanner end
R
D DS:7900
D DS:79E0
EOF_COMMANDS

cat >"$runtime_commands_file" <<'EOF_RUNTIME_COMMANDS'
# Runtime DOSBox debugger command plan.
# A live capture overwrites this after runtime CS/DS is observed.
EOF_RUNTIME_COMMANDS

{
    echo "capture=contact_scanner_runtime"
    echo "source=dosbox-debug"
    echo "scenario=$scenario"
    echo "expected_level=$expected_level"
    echo "route=$runtime_route"
    echo "asset_dir=$asset_dir"
    echo "out_dir=$out_dir"
    echo "debugger_commands=$commands_file"
    echo "debugger_commands_runtime=$runtime_commands_file"
    echo "raw_debugger_dump=$raw_dump"
    echo "candidate_fixture=$candidate_fixture"
    echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
    echo "environment_preflight_log=$environment_preflight_log"
    echo "anchors=1000:5CB0..604F"
    echo "visual_claim=0"
} >"$manifest"

cat >"$candidate_fixture" <<EOF_FIXTURE
# LEZAC contact-scanner runtime oracle candidate
# Fill this from raw DOSBox-debug output before promotion.
capture=contact_scanner_runtime
source=dosbox-debug
temp_copy=1
visual_claim=0
scenario=$scenario
level=$expected_level
route=$runtime_route

# runtime_cs=<runtime-cs>
# runtime_ds=<runtime-ds>
#
# break ghidra=1000:5CB0 runtime=<runtime-cs>:5CB0 label=contact_scanner_start
# break ghidra=1000:604F runtime=<runtime-cs>:604F label=contact_scanner_end
#
# subject_actor slot=<slot> kind=<kind> state=<state> x=0x0000 y=0x0000 w=<w> h=<h> flags=0x0000
# other_actor slot=<slot> kind=<kind> state=<state> x=0x0000 y=0x0000 w=<w> h=<h> flags=0x0000
# contact_scan subject_slot=<slot> other_slot=<slot> flags_before=0x0000 flags_after=0x0000 contact=<0-or-1> player_contact=<0-or-1> monster_contact=<0-or-1> object_contact=<0-or-1> damage_pending=<n> overlap_x=<n> overlap_y=<n>
#
# dump DS:7900
# <runtime-ds>:7900  <bytes>
EOF_FIXTURE

{
    echo "contact_scanner_debug_capture=planned"
    echo "scenario=$scenario"
    echo "route=$runtime_route"
    echo "expected_level=$expected_level"
    echo "anchor_contact_scanner=1000:5CB0..604F"
    echo "candidate_fixture=$candidate_fixture"
    echo "debugger_commands_runtime=$runtime_commands_file"
    echo "environment_preflight_command=$(quote_command "${environment_preflight_command[@]}")"
    echo "environment_preflight_log=$environment_preflight_log"
    echo "fixture_command=./build/lezac_cpp --debug-contact-scanner-runtime-oracle <candidate-fixture>"
} >"$raw_dump"

{
    echo "capture=contact_scanner_runtime"
    echo "scenario=$scenario"
    echo "route=$runtime_route"
    echo "manifest=$manifest"
    echo "raw_debugger_dump=$raw_dump"
    echo "candidate_fixture=$candidate_fixture"
    echo "debugger_commands_runtime=$runtime_commands_file"
    echo "environment_preflight_log=$environment_preflight_log"
} >"$log"

if [[ ! -e "$asset_dir/LEZAC.EXE" ]]; then
    echo "missing $asset_dir/LEZAC.EXE" >&2
    exit 67
fi

if [[ "${LEZAC_CONTACT_SCANNER_DEBUG_DRY_RUN:-0}" == "1" ]]; then
    echo "environment_preflight=dry_run" >>"$manifest"
    echo "environment_preflight=dry_run" >>"$raw_dump"
    echo "contact_scanner_debug_capture=ok mode=dry_run scenario=$scenario route=$runtime_route manifest=$manifest raw_dump=$raw_dump candidate_fixture=$candidate_fixture debugger_commands_runtime=$runtime_commands_file environment_preflight=dry_run environment_preflight_log=$environment_preflight_log"
    exit 0
fi

run_environment_preflight
require dosbox-debug
require xvfb-run
require timeout

run_dir=$(mktemp -d /tmp/lezac-contact-scanner-debug.XXXXXX)
cleanup() {
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
cp "${assets[@]}" "$run_dir/"

dosbox_command=(
    env TERM=xterm-256color xvfb-run -a timeout "${LEZAC_CONTACT_SCANNER_DEBUG_TIMEOUT_SECONDS:-20s}"
    dosbox-debug
    -c "mount c $run_dir"
    -c "c:"
    -c "DEBUG LEZAC.EXE"
)

{
    echo "command=${dosbox_command[*]}"
    echo "run_dir=$run_dir"
} >>"$manifest"

set +e
"${dosbox_command[@]}" >>"$log" 2>&1
status=$?
set -e
append_runtime_registers
echo "dosbox_debug_exit=$status" >>"$manifest"
echo "dosbox_debug_exit=$status" >>"$raw_dump"

if [[ $status -ne 0 ]]; then
    echo "contact_scanner_debug_capture=error scenario=$scenario reason=dosbox_debug_exit_$status manifest=$manifest raw_dump=$raw_dump"
    exit "$status"
fi

echo "contact_scanner_debug_capture=ok mode=capture scenario=$scenario route=$runtime_route manifest=$manifest raw_dump=$raw_dump candidate_fixture=$candidate_fixture"
