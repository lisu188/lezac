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
    object_collision_jump_live|monster_contact_damage_live|monster_behavior4_chase) ;;
    *)
        echo "unsupported actor-update scenario: $scenario" >&2
        exit 65
        ;;
esac

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        echo "missing required command: $1" >&2
        exit 69
    fi
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
log="$out_dir/actor_update_debug_capture.log"
commands_file="$out_dir/debugger_commands.txt"
candidate_fixture="$out_dir/candidate_fixture.txt"

runtime_route=debugger_seeded
expected_level=1

cat >"$commands_file" <<'EOF_COMMANDS'
# DOSBox debugger command plan.
# Replace <CS> with the runtime code segment after stopping in LEZAC.EXE.
# Keep Ghidra offsets unchanged when translating 1000:offset to <CS>:offset.
BP <CS>:5CB0  # contact scanner start
BP <CS>:604F  # contact scanner end
BP <CS>:6053  # actor update start
BP <CS>:777F  # actor update end
R
D DS:7900
D DS:79E0
D DS:7A00
EOF_COMMANDS

{
    echo "capture=actor_update_runtime"
    echo "source=dosbox-debug"
    echo "scenario=$scenario"
    echo "expected_level=$expected_level"
    echo "route=$runtime_route"
    echo "asset_dir=$asset_dir"
    echo "out_dir=$out_dir"
    echo "debugger_commands=$commands_file"
    echo "raw_debugger_dump=$raw_dump"
    echo "candidate_fixture=$candidate_fixture"
    echo "anchors=1000:5CB0..604F,1000:6053..777F"
    echo "visual_claim=0"
} >"$manifest"

cat >"$candidate_fixture" <<EOF_FIXTURE
# LEZAC actor-update runtime oracle candidate
# Fill this from raw DOSBox-debug output before promotion.
capture=actor_update_runtime
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
# break ghidra=1000:6053 runtime=<runtime-cs>:6053 label=actor_update_start
# break ghidra=1000:777F runtime=<runtime-cs>:777F label=actor_update_end
#
# actor_before slot=<slot> behavior=<behavior> kind=<kind> state=<state> x=0x0000 y=0x0000 vx8=<vx8> vy8=<vy8> hp=<hp> flags=0x0000 contact=<0-or-1> on_ground=<0-or-1>
# actor_after slot=<slot> behavior=<behavior> kind=<kind> state=<state> x=0x0000 y=0x0000 vx8=<vx8> vy8=<vy8> hp=<hp> flags=0x0000 contact=<0-or-1> on_ground=<0-or-1>
# contact_scan subject_slot=<slot> other_slot=<slot> flags_before=0x0000 flags_after=0x0000 contact=<0-or-1> player_contact=<0-or-1> monster_contact=<0-or-1> object_contact=<0-or-1> damage_pending=<n>
# tile_probe tile_x=<x> tile_y=<y> tile=0x0000 object=0x0000 passable=<0-or-1> standable=<0-or-1>
#
# dump DS:7900
# <runtime-ds>:7900  <bytes>
EOF_FIXTURE

{
    echo "actor_update_debug_capture=planned"
    echo "scenario=$scenario"
    echo "route=$runtime_route"
    echo "expected_level=$expected_level"
    echo "anchor_contact_scanner=1000:5CB0..604F"
    echo "anchor_actor_update=1000:6053..777F"
    echo "candidate_fixture=$candidate_fixture"
    echo "fixture_command=./build/lezac_cpp --debug-actor-update-runtime-oracle <candidate-fixture>"
} >"$raw_dump"

{
    echo "capture=actor_update_runtime"
    echo "scenario=$scenario"
    echo "route=$runtime_route"
    echo "manifest=$manifest"
    echo "raw_debugger_dump=$raw_dump"
    echo "candidate_fixture=$candidate_fixture"
} >"$log"

if [[ ! -e "$asset_dir/LEZAC.EXE" ]]; then
    echo "missing $asset_dir/LEZAC.EXE" >&2
    exit 67
fi

if [[ "${LEZAC_ACTOR_UPDATE_DEBUG_DRY_RUN:-0}" == "1" ]]; then
    echo "actor_update_debug_capture=ok mode=dry_run scenario=$scenario route=$runtime_route manifest=$manifest raw_dump=$raw_dump candidate_fixture=$candidate_fixture"
    exit 0
fi

require dosbox-debug
require xvfb-run
require timeout

run_dir=$(mktemp -d /tmp/lezac-actor-update-debug.XXXXXX)
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
    env TERM=xterm-256color xvfb-run -a timeout "${LEZAC_ACTOR_UPDATE_DEBUG_TIMEOUT_SECONDS:-20s}"
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
echo "dosbox_debug_exit=$status" >>"$manifest"
echo "dosbox_debug_exit=$status" >>"$raw_dump"

if [[ $status -ne 0 ]]; then
    echo "actor_update_debug_capture=error scenario=$scenario reason=dosbox_debug_exit_$status manifest=$manifest raw_dump=$raw_dump"
    exit "$status"
fi

echo "actor_update_debug_capture=ok mode=capture scenario=$scenario route=$runtime_route manifest=$manifest raw_dump=$raw_dump candidate_fixture=$candidate_fixture"
