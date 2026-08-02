#!/usr/bin/env python3
"""Hunt the natural forward debris writeback at 1000:3D2D on level 2.

3D2D writes debris[0x0B*(tag-0x4E20) + 4] -- the struck record's vx field --
with the blended impact velocity. That write PERSISTS in the record, so a
tick-locked sampler can see its effect; what the earlier 201-tick window
lacked was a fragment-on-fragment strike, not the resolution to observe one.

Drops bombs at successive debris sites and samples the debris record table
(DS:0x2093, stride 0x0B) every tick, recording every record so the vx history
of each can be checked against bounce/friction afterwards.
"""
import argparse, json, struct, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import seed_original_level as seeder  # noqa: E402

FRAME = 0x78C2
DEBRIS_BASE, DEBRIS_STRIDE = 0x2093, 0x0B
DEBRIS_FIRST, DEBRIS_SCAN = 200, 80
DEBRIS_COUNT_OFF = 0x207E
PLAYER_X, PLAYER_Y = 0xC21E, 0xC220
RANDSEED = 0x1AFE
LANES = 0x78D2


def u16(s, o): return struct.unpack_from("<H", s, o)[0]
def i16(s, o): return struct.unpack_from("<h", s, o)[0]


def run(pid, base, window, out_path, sites, cap_seconds):
    dsbase = base + (seeder.RUNTIME_DS << 4)

    def tap(key):
        subprocess.run(["xdotool", "windowactivate", "--sync", window],
                       stderr=subprocess.DEVNULL, timeout=3)
        subprocess.run(["xdotool", "keydown", "--clearmodifiers", key],
                       stderr=subprocess.DEVNULL)
        time.sleep(0.15)
        subprocess.run(["xdotool", "keyup", "--clearmodifiers", key],
                       stderr=subprocess.DEVNULL)

    rows = 0
    deadline = time.monotonic() + cap_seconds
    site_i = 0
    last_bomb = -999
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem, out_path.open("w") as sink:
        def seg():
            mem.seek(dsbase); return mem.read(0x10000)

        def wpos(x, y):
            mem.seek(dsbase + PLAYER_X); mem.write(struct.pack("<h", x))
            mem.seek(dsbase + PLAYER_Y); mem.write(struct.pack("<h", y))

        prev = None
        while time.monotonic() < deadline:
            s = seg()
            f = u16(s, FRAME)
            if f == prev:
                continue
            prev = f
            recs = []
            for i in range(DEBRIS_FIRST, DEBRIS_FIRST + DEBRIS_SCAN):
                off = DEBRIS_BASE + i * DEBRIS_STRIDE
                if off + DEBRIS_STRIDE > 0x10000:
                    break
                raw = s[off:off + DEBRIS_STRIDE]
                if raw != b"\x00" * DEBRIS_STRIDE:
                    recs.append([i, raw.hex()])
            sink.write(json.dumps({
                "frame": f,
                "randseed": struct.unpack_from("<I", s, RANDSEED)[0],
                "dcount": u16(s, DEBRIS_COUNT_OFF),
                "lanes": s[LANES:LANES + 4].hex(),
                "recs": recs,
            }) + "\n")
            sink.flush()
            rows += 1
            # Cycle through candidate sites, bombing each once.
            if site_i < len(sites) and f - last_bomb > 60:
                x, y = sites[site_i]
                wpos(x, y)
                time.sleep(0.02)
                tap("n")
                time.sleep(0.02)
                last_bomb = f
                site_i += 1
                print(f"bomb site={site_i}/{len(sites)} at {x},{y} frame={f}", flush=True)
    return rows


def install_hook(out_path, sites, cap_seconds):
    original = seeder.write_runtime_state_snapshot

    def patched(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            w = subprocess.check_output(["xdotool", "search", "--name", "DOSBox"],
                                        text=True).split()[-1]
            print(f"d3d2d_capture=start level={state['level']}", flush=True)
            n = run(pid, base, w, out_path, sites, cap_seconds)
            print(f"d3d2d_capture=ok ticks={n} out={out_path}", flush=True)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = patched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sites", required=True,
                    help="semicolon-separated pixel sites, e.g. '208,304;216,304'")
    ap.add_argument("--seconds", type=float, default=200.0)
    args = ap.parse_args()
    sites = [tuple(int(v) for v in p.split(",")) for p in args.sites.split(";") if p]
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    install_hook(out, sites, args.seconds)
    sys.argv = ["seed_original_level.py", "--run-dir", args.run_dir,
                "--advance-to", "2", "--approve-procmem",
                "--approve-runtime-instrumentation", "--dump-runtime-state"]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
