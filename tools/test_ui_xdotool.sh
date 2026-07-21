#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 /path/to/lezac_cpp" >&2
    exit 64
fi

exe=$1

set -euo pipefail

"$exe" &
pid=$!

cleanup() {
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
}
trap cleanup EXIT

win=""
for _ in $(seq 1 100); do
    win=$(xdotool search --onlyvisible --pid "$pid" 2>/dev/null | head -n 1 || true)
    if [[ -z "$win" ]]; then
        win=$(xdotool search --name Larax 2>/dev/null | head -n 1 || true)
    fi
    if [[ -n "$win" ]]; then
        break
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
        set +e
        wait "$pid"
        status=$?
        set -e
        trap - EXIT
        echo "process_exited_before_window status=$status" >&2
        exit 1
    fi
    sleep 0.1
done

if [[ -z "$win" ]]; then
    echo "window_not_found pid=$pid" >&2
    exit 1
fi

xdotool windowfocus "$win"
sleep 0.1

xdotool key i
sleep 0.1
xdotool key z
sleep 0.1
xdotool key r
sleep 0.1
xdotool key Escape
sleep 0.1
xdotool key 2
sleep 0.2
xdotool key n
sleep 0.2
xdotool key Insert
sleep 0.2
xdotool key Escape
sleep 0.1
xdotool key 1
sleep 0.2
xdotool keydown Right
sleep 0.4
xdotool keyup Right
xdotool keydown Left
sleep 0.2
xdotool keyup Left
xdotool key m
xdotool key n
sleep 0.5
xdotool key space
xdotool key s
xdotool key r
xdotool key e
xdotool key Page_Up
xdotool key Page_Down
xdotool key F5
xdotool key Escape
sleep 0.1
xdotool key Escape
sleep 0.3

if kill -0 "$pid" 2>/dev/null; then
    echo "app_still_running_after_escape" >&2
    exit 2
fi

trap - EXIT
wait "$pid"
echo "ui_xdotool=ok"
