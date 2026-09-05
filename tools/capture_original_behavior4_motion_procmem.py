#!/usr/bin/env python3
"""Tick-locked level-2 capture of the original's behaviour-4 (flyer) motion.

Samples the REAL actor table DS:0x1BAE stride 0x26 -- not DS:0x74A8, which is
the level-file monster spawner table -- plus the visual table, once per
DS:0x78C2 change, with ONE 64 KiB pread of the data segment per tick so no
record can tear.
"""
import argparse
import json
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import seed_original_level as seeder  # noqa: E402

FRAME = 0x78C2
ACTOR_TABLE, ACTOR_STRIDE = 0x1BAE, 0x26
VISUAL_TABLE, VISUAL_STRIDE, VISUAL_COUNT = 0xC21E, 8, 0xC496
SPAWNER_COUNT = 0x79A6
ALLOC = 0x208D
RANDSEED = 0x1AFE
PLAYER_X, PLAYER_Y = 0xC21E, 0xC220
MAX_TICKS = 900


def u16(seg, off):
    return struct.unpack_from("<H", seg, off)[0]


def i16(seg, off):
    return struct.unpack_from("<h", seg, off)[0]


def sample(seg, nactors):
    vcount = seg[VISUAL_COUNT]
    if vcount > 64:
        raise RuntimeError("implausible visual count")
    return {
        "frame": u16(seg, FRAME),
        "randseed": struct.unpack_from("<I", seg, RANDSEED)[0],
        "alloc": seg[ALLOC],
        "spawners": seg[SPAWNER_COUNT],
        "vcount": vcount,
        "actors": [seg[ACTOR_TABLE + i * ACTOR_STRIDE:
                       ACTOR_TABLE + (i + 1) * ACTOR_STRIDE].hex()
                   for i in range(nactors + 1)],
        "visuals": [[i16(seg, VISUAL_TABLE + i * VISUAL_STRIDE),
                     i16(seg, VISUAL_TABLE + i * VISUAL_STRIDE + 2),
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 4],
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 5],
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 6],
                     seg[VISUAL_TABLE + i * VISUAL_STRIDE + 7]]
                    for i in range(vcount)],
    }


def run(pid, base, out_path, nactors, cap_seconds):
    dsbase = base + (seeder.RUNTIME_DS << 4)
    rows = 0
    deadline = time.monotonic() + cap_seconds
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem, \
            out_path.open("w") as sink:
        prev = None
        while time.monotonic() < deadline and rows < MAX_TICKS:
            mem.seek(dsbase)
            seg = mem.read(0x10000)
            f = u16(seg, FRAME)
            if f == prev:
                continue
            prev = f
            sink.write(json.dumps(sample(seg, nactors)) + "\n")
            sink.flush()
            rows += 1
    return rows


def install_hook(out_path, nactors, cap_seconds):
    original = seeder.write_runtime_state_snapshot

    def patched(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            print(f"b4_capture=start level={state['level']}", flush=True)
            n = run(pid, base, out_path, nactors, cap_seconds)
            print(f"b4_capture=ok ticks={n} out={out_path}", flush=True)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = patched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", type=int, default=2)
    ap.add_argument("--actors", type=int, default=8)
    ap.add_argument("--seconds", type=float, default=180.0)
    args = ap.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    install_hook(out, args.actors, args.seconds)
    sys.argv = [
        "seed_original_level.py",
        "--run-dir", args.run_dir,
        "--advance-to", str(args.level),
        "--approve-procmem",
        "--approve-runtime-instrumentation",
        "--dump-runtime-state",
    ]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
