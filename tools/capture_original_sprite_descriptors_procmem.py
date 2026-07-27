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

OUT = Path("/tmp/claude-0/-home-user-lezac/"
           "064a09b8-e325-5628-8402-832b91172260/scratchpad/l1_segdump.bin")


def install_hook():
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
                OUT.write_bytes(mem.read(0x10000))
            print(f"segdump=ok level={state['level']} out={OUT}", flush=True)
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
        "--approve-procmem",
        "--approve-runtime-instrumentation",
        "--dump-runtime-state",
    ]
    return seeder.main()


if __name__ == "__main__":
    raise SystemExit(main())
