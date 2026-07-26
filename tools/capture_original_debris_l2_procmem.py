#!/usr/bin/env python3
"""Capture 1: natural forward-debris writeback at Ghidra 1000:3D2D, level 2.

Staging (derived statically, with falsifiable predictions):
  Level 2, crate column x=26 rows 36..39 standing on the floor slab rows 40..41.
  Bomb block top-left (25,38)  ->  bomb pixel px in [196,203], py in [304,311].
  Predictions at the blast tick:
    DS:C1E8 == 3824  (= 38*100 + 25 - 1)
    DS:207E 0x00C7 -> 0x00C8   (first debris record of the level is index 200)
    staging tag DS:65D4+2 == 0x4EE8, DI == 0x0898, target word == 0xC00A

Method matches the boss/contact captures: reuse tools/seed_original_level.py's
hardened launch + level-advance path, then sample tick-locked on DS:0x78C2 with
one 64 KiB pread of the whole data segment per tick.

The spawner cooldown is 256 ticks and a monster appearing mid-blast perturbs the
RNG, so we idle well past it before placing the single bomb.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("/home/user/lezac/tools")))
import seed_original_level as seeder  # noqa: E402

FRAME = 0x78C2
PLAYER_X, PLAYER_Y = 0xC21E, 0xC220
BOMB_BLOCK_INDEX = 0xC1E8          # expect 3824 at 1000:6CBF
DEBRIS_COUNT = 0x207E              # expect 0xC7 -> 0xC8
DEBRIS_BASE = 0x2093               # record stride 0x0B
DEBRIS_STRIDE = 0x0B
DEBRIS_FIRST = 200
STAGING_TAG = 0x65D4
LAST_MATCH = 0x2074
COLLAPSE_QUEUE = 0x2080
RANDSEED = 0x1AFE
LEVEL_BYTE = 0x79B7
LANE = (0x78D2, 0x78D3, 0x78D4, 0x78D5)
LANE_ACC = 0x2090

TARGET_PX, TARGET_PY = 200, 308
IDLE_TICKS_BEFORE_BOMB = 340       # > the 256-tick spawner cooldown
SAMPLE_TICKS = 200

OUT = Path(os.environ.get("LEZAC_DEBRIS_OUT", "debris_l2_ticks.jsonl"))


def u16(seg, off):
    return struct.unpack_from("<H", seg, off)[0]


def i16(seg, off):
    return struct.unpack_from("<h", seg, off)[0]


def sample(seg):
    recs = {}
    for k in range(DEBRIS_FIRST, DEBRIS_FIRST + 8):
        off = DEBRIS_BASE + DEBRIS_STRIDE * k
        recs[k] = seg[off:off + DEBRIS_STRIDE].hex()
    return {
        "frame": u16(seg, FRAME),
        "level": seg[LEVEL_BYTE],
        "randseed": struct.unpack_from("<I", seg, RANDSEED)[0],
        "player": [i16(seg, PLAYER_X), i16(seg, PLAYER_Y)],
        "block_index": u16(seg, BOMB_BLOCK_INDEX),
        "debris_count": u16(seg, DEBRIS_COUNT),
        "last_match": u16(seg, LAST_MATCH),
        "collapse_queue": u16(seg, COLLAPSE_QUEUE),
        "staging_tag": [u16(seg, STAGING_TAG + 2 * i) for i in range(4)],
        "lane": [seg[o] for o in LANE],
        "lane_acc": i16(seg, LANE_ACC),
        "records": recs,
    }


def run(pid, base, window):
    dsbase = base + (seeder.RUNTIME_DS << 4)

    def focus():
        subprocess.run(["xdotool", "windowactivate", "--sync", window],
                       stderr=subprocess.DEVNULL, timeout=3)

    def tap(key):
        focus()
        subprocess.run(["xdotool", "key", "--clearmodifiers", key],
                       stderr=subprocess.DEVNULL)

    rows = []
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        def seg():
            mem.seek(dsbase)
            return mem.read(0x10000)

        def tick():
            mem.seek(dsbase + FRAME)
            return struct.unpack("<H", mem.read(2))[0]

        # Idle past the spawner cooldown so no monster perturbs the RNG.
        start = tick()
        while (tick() - start) & 0xFFFF < IDLE_TICKS_BEFORE_BOMB:
            time.sleep(0.01)

        # Park the player on the staging cell, then let a few ticks settle.
        mem.seek(dsbase + PLAYER_X); mem.write(struct.pack("<h", TARGET_PX))
        mem.seek(dsbase + PLAYER_Y); mem.write(struct.pack("<h", TARGET_PY))
        settle = tick()
        while (tick() - settle) & 0xFFFF < 8:
            time.sleep(0.005)

        pre = sample(seg())
        print("pre_bomb "
              f"player={pre['player']} block_index={pre['block_index']}"
              f" debris_count=0x{pre['debris_count']:04x}"
              f" frame={pre['frame']}", flush=True)

        tap("n")  # player-1 fire/bomb gate (scan code 0x31)

        prev = tick()
        rows.append(sample(seg()))
        while len(rows) < SAMPLE_TICKS:
            now = tick()
            if now == prev:
                continue
            prev = now
            rows.append(sample(seg()))
    return pre, rows


def install_hook():
    original = seeder.write_runtime_state_snapshot

    def patched(run_dir, pid, base, state, phase):
        if phase == "pre_capture" and state["level"] == 2:
            window = subprocess.check_output(
                ["xdotool", "search", "--name", "DOSBox"], text=True).split()[-1]
            print(f"debris_capture=start level={state['level']}", flush=True)
            pre, rows = run(pid, base, window)
            with OUT.open("w") as handle:
                handle.write(json.dumps({"pre_bomb": pre}) + "\n")
                for row in rows:
                    handle.write(json.dumps(row) + "\n")
            seen = sorted({r["debris_count"] for r in rows})
            print("debris_capture=ok"
                  f" ticks={len(rows)}"
                  f" debris_counts={[hex(v) for v in seen][:8]}"
                  f" block_index={pre['block_index']}"
                  f" out={OUT}", flush=True)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = patched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()
    install_hook()
    sys.argv = [
        "seed_original_level.py",
        "--run-dir", args.run_dir,
        "--advance-to", "2",
        "--approve-procmem",
        "--approve-runtime-instrumentation",
        "--dump-runtime-state",
    ]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
