#!/usr/bin/env python3
"""One-shot raw data-segment dump of the original at level-1 gameplay.

Purpose: read the live sprite-descriptor table (around DS:0xC322) to settle
whether DGROUP sprite-frame values are 0- or 1-based over the SPR bank -- the
+-1 that decides every table-derived sprite range in the port, including the
empirical +6 state-2 rebase. One pread, no breakpoints, no writes.
"""
import argparse
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path("/home/user/lezac/tools")))
import seed_original_level as seeder  # noqa: E402

def install_hook(out_path: Path):
    original = seeder.write_runtime_state_snapshot

    def patched(run_dir, pid, base, state, phase):
        if phase == "pre_capture":
            dsbase = base + (seeder.RUNTIME_DS << 4)
            with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
                # settle a few ticks so all load-time tables are final
                mem.seek(dsbase + 0x78C2)
                start = struct.unpack("<H", mem.read(2))[0]
                while True:
                    mem.seek(dsbase + 0x78C2)
                    now = struct.unpack("<H", mem.read(2))[0]
                    if (now - start) & 0xFFFF >= 5:
                        break
                    time.sleep(0.01)
                mem.seek(dsbase)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(mem.read(0x10000))
            print(f"segdump=ok level={state['level']} out={out_path}", flush=True)
        return original(run_dir, pid, base, state, phase)

    seeder.write_runtime_state_snapshot = patched


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--out", type=Path, default=None,
                        help="output path for the 64 KiB dump "
                             "(default: <run-dir>/l1_segdump.bin)")
    args = parser.parse_args()
    out_path = args.out if args.out else Path(args.run_dir) / "l1_segdump.bin"
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
