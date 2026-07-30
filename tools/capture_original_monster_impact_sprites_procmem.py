#!/usr/bin/env python3
"""Capture 3: kill the level-1 walker with a bomb and trace the death frames.

Adaptive: samples the walker's live position each tick and places a bomb
~45 px ahead of its movement direction (small-bomb fuse is 41 ticks, walker
speed ~1 px/tick), then teleports the player clear. Retries until the actor
record shows the death conversion, then keeps sampling ~120 ticks for the
reward popup.

Whole-segment pread per tick, tick-locked on DS:0x78C2, as always.
"""
import argparse
import json
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import seed_original_level as seeder  # noqa: E402

FRAME = 0x78C2
PLAYER_X, PLAYER_Y = 0xC21E, 0xC220
ACTOR_TABLE, ACTOR_STRIDE, ACTOR_COUNT = 0x74A8, 0x1E, 0x79A6
VISUAL_TABLE, VISUAL_STRIDE, VISUAL_COUNT = 0xC21E, 8, 0xC496
ALLOC_COUNT = 0x208D
RANDSEED = 0x1AFE
ENERGY, LIVES, LEVEL = 0x79EC, 0x79EA, 0x79B7

SAFE_X, SAFE_Y = 104, 120
MAX_TICKS = 2600
POST_DEATH_TICKS = 140
# Ticks an armed bomb stayed allocated in run 1 (DS:0x208D 2->3 at frame
# 1326, back to 2 at 1350). Used only to lead the walker; the authoritative
# fuse measurement remains the 41 ticks in the route-timing fixture, which
# this run should also let us re-check.
ARMED_TICKS = 24


def u16(seg, off):
    return struct.unpack_from("<H", seg, off)[0]


def i16(seg, off):
    return struct.unpack_from("<h", seg, off)[0]


def sample(seg):
    count = seg[ACTOR_COUNT]
    vcount = seg[VISUAL_COUNT]
    if count > 64 or vcount > 64:
        raise RuntimeError("implausible counts")
    return {
        "frame": u16(seg, FRAME),
        "randseed": struct.unpack_from("<I", seg, RANDSEED)[0],
        "player": [i16(seg, PLAYER_X), i16(seg, PLAYER_Y)],
        "energy": seg[ENERGY],
        "lives": seg[LIVES],
        "alloc": seg[ALLOC_COUNT],
        "counts": [count, vcount],
        "actors": [seg[ACTOR_TABLE + i * ACTOR_STRIDE:
                       ACTOR_TABLE + (i + 1) * ACTOR_STRIDE].hex()
                   for i in range(count + 1)],
        "visuals": [[i16(seg, VISUAL_TABLE + i * VISUAL_STRIDE),
                     i16(seg, VISUAL_TABLE + i * VISUAL_STRIDE + 2),
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 4],
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 5],
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 6],
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 7]]
                    for i in range(vcount)],
    }


def run(pid, base, window, out_path):
    dsbase = base + (seeder.RUNTIME_DS << 4)

    def tap(key):
        # Run 1 (kill_ticks.jsonl, 1823 ticks) placed only ONE bomb out of
        # ~25 attempts: an instantaneous `xdotool key` press is shorter than
        # the interval at which the game samples the keyboard, so nearly every
        # tap fell between polls. Hold the key across several game ticks
        # instead, then release.
        subprocess.run(["xdotool", "windowactivate", "--sync", window],
                       stderr=subprocess.DEVNULL, timeout=3)
        subprocess.run(["xdotool", "keydown", "--clearmodifiers", key],
                       stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "keyup", "--clearmodifiers", key],
                       stderr=subprocess.DEVNULL)

    # BOMOMIMK walk band for the kind-1 walker: frames 43..46. The visual
    # sprite word maps to a frame as (word - 3698) / 170 (recovered earlier).
    def walker_frame(word):
        if word < 3698:
            return -1
        offset = word - 3698
        if offset % 170:
            return -1
        return offset // 170

    death_frame = None
    last_bomb_frame = -999
    walker_hist = []
    rows_written = 0
    deadline = time.monotonic() + 240.0
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem, \
            out_path.open("w") as sink:
        def seg():
            mem.seek(dsbase)
            return mem.read(0x10000)

        def wpos(x, y):
            mem.seek(dsbase + PLAYER_X); mem.write(struct.pack("<h", x))
            mem.seek(dsbase + PLAYER_Y); mem.write(struct.pack("<h", y))

        prev = None
        while time.monotonic() < deadline and rows_written < MAX_TICKS:
            s = seg()
            f = u16(s, FRAME)
            if f == prev:
                continue
            prev = f
            row = sample(s)
            sink.write(json.dumps(row) + "\n")
            sink.flush()
            rows_written += 1

            # Find the live walker among visual slots >= 2: the entry whose
            # sprite decodes into the 43..46 walk band.
            walker = None
            for vi in range(2, row["counts"][1]):
                v = row["visuals"][vi]
                word = v[4] | (v[5] << 8)
                frame = walker_frame(word)
                if 43 <= frame <= 46:
                    walker = (vi, v[0], v[1])
                    break
                if 47 <= frame <= 55 or frame in (18, 0x4F):
                    if death_frame is None:
                        death_frame = f
                        print(f"death_band_observed frame={f} slot={vi} "
                              f"band_frame={frame}", flush=True)
            if death_frame is None and walker is None and walker_hist:
                # Walker visual vanished or left the walk band entirely.
                death_frame = f
                print(f"walker_visual_gone frame={f}", flush=True)

            if death_frame is None and walker is not None:
                walker_hist.append((f, walker[1]))
                if len(walker_hist) >= 9 and f - last_bomb_frame > 45:
                    # Lead the walker by however far it travels while the
                    # bomb sits armed. Run 1's single placed bomb lived 24
                    # ticks (allocation count DS:0x208D 2->3 at frame 1326,
                    # 3->2 at 1350) while the walker covered ~1.14 px/tick,
                    # so the fixed 45 px lead put the bomb ~6 ticks beyond
                    # the walker's reach: it always detonated early.
                    span = walker_hist[-1][0] - walker_hist[-9][0]
                    dx = walker_hist[-1][1] - walker_hist[-9][1]
                    if span <= 0 or dx == 0:
                        continue
                    speed = abs(dx) / span
                    direction = 1 if dx > 0 else -1
                    lead = max(6, min(40, int(round(speed * ARMED_TICKS))))
                    target = walker[1] + direction * lead
                    if 40 <= target <= 460:
                        alloc_before = row["alloc"]
                        wpos(target, 170)
                        time.sleep(0.02)
                        tap("n")
                        time.sleep(0.02)
                        wpos(SAFE_X, SAFE_Y)
                        last_bomb_frame = f
                        print(f"bomb frame={f} walker_x={walker[1]} "
                              f"dir={direction} speed={speed:.2f} "
                              f"lead={lead} at={target} "
                              f"alloc_before={alloc_before}", flush=True)
            if death_frame is not None and f - death_frame > POST_DEATH_TICKS:
                break
    return rows_written, death_frame


def install_hook(out_path):
    original = seeder.write_runtime_state_snapshot

    def patched(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            window = subprocess.check_output(
                ["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
            print(f"kill_capture=start level={state['level']}", flush=True)
            written, death = run(pid, base, window, out_path)
            print(f"kill_capture=ok ticks={written} death_frame={death} "
                  f"out={out_path}", flush=True)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = patched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--out",
        help="JSONL sink for the per-tick samples "
             "(default: <run-dir>/kill_ticks.jsonl)")
    args = parser.parse_args()
    out_path = Path(args.out) if args.out else Path(args.run_dir) / "kill_ticks.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    install_hook(out_path)
    sys.argv = [
        "seed_original_level.py",
        "--run-dir", args.run_dir,
        "--approve-procmem",
        "--approve-runtime-instrumentation",
        "--dump-runtime-state",
    ]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
