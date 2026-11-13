"""Private route controller; changes only normal input after the verified handoff."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import level1_fidelity as fidelity
import level1_original as original

BASE = ROOT / "build-codex-tmp/capture-natural-level2-extension-20261001.py"
BASE_SHA256 = "acb311ed85fb594afc1d92d6774036a742388339b920bcc0f81206cabfb30dec"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("record", "capture", "compare"))
    parser.add_argument("--frames", type=int, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--exe", type=Path)
    parser.add_argument("--native", type=Path)
    parser.add_argument("--cpp", type=Path)
    parser.add_argument("--approve-procmem", action="store_true")
    parser.add_argument("--approve-runtime-instrumentation", action="store_true")
    args = parser.parse_args()
    fidelity.require(1 <= args.frames <= 3000, "invalid exploration frame count")
    fidelity.require(fidelity.sha256(BASE) == BASE_SHA256, "base observer changed")
    events = fidelity.strict_json(args.events.read_text())
    fidelity.require(isinstance(events, dict), "event object required")
    parsed = {}
    for key, items in events.items():
        fidelity.require(key.isdigit() and str(int(key)) == key and int(key) < args.frames
                         and isinstance(items, list) and items, "invalid event index")
        for item in items:
            fidelity.require(isinstance(item, list) and len(item) == 2 and item[0] in ("down", "up")
                             and item[1] in original.BANK, "non-gameplay event")
        parsed[int(key)] = [tuple(item) for item in items]
    spec = importlib.util.spec_from_file_location("private_level2_base", BASE)
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    base.FRAMES, base.EVENTS = args.frames, parsed
    metadata = {"schema": "lezac-private-level2-route-controller-v1", "frames": args.frames,
                "events": events, "controller_sha256": fidelity.sha256(Path(__file__)),
                "base_observer_sha256": BASE_SHA256, "events_file_sha256": fidelity.sha256(args.events),
                "seed_scope": "one unchanged Level 1 prefix seed only", "state_injections": False,
                "original_fidelity_claim": False, "port_functionally_complete": False}
    out = args.out.resolve()
    fidelity.require(out.parent == Path("/dev/shm") and not out.exists(), "new RAM output required")
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    planned = (743 + args.frames) * 285000 + 8 * 1024 * 1024 if args.command == "record" else 32 * 1024 * 1024
    base.reserve(planned)
    provenance = out.with_name(out.name + "-controller.json")
    fidelity.require(not provenance.exists(), "controller provenance already exists")
    provenance.write_bytes(original.json_bytes(metadata))
    parent_session = base.ExtensionSession

    class ProgressSession(parent_session):
        def extend(self, emit):
            def with_controller(row):
                if row["kind"] == "header":
                    row["controller"] = metadata
                emit(row)
            super().extend(with_controller)

    base.ExtensionSession = ProgressSession
    try:
        if args.command == "record":
            base.record(args.exe, out)
        elif args.command == "capture":
            fidelity.require(args.approve_procmem and args.approve_runtime_instrumentation,
                             "explicit observer approvals required")
            base.capture(out)
        else:
            base.compare(args.native.resolve(), args.cpp.resolve(), out)
    finally:
        if out.is_dir():
            shutil.copyfile(Path(__file__), out / "route-controller.py")
            shutil.copyfile(BASE, out / "base-observer.py")
            (out / "controller.json").write_bytes(original.json_bytes(metadata))


if __name__ == "__main__":
    main()
