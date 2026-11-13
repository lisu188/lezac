"""Require the natural-source walker fixture to be validated before the seeded replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/walker_ledge_original.bin"
SHA256 = "f2d40e15c0e9425e1c1f8cd11389b0fc0af4e614c2ad8cca4b6d875724b66269"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = FIXTURE.read_bytes()
    if len(source) != 2193 or hashlib.sha256(source).hexdigest() != SHA256:
        raise RuntimeError("native walker ledge source fixture changed")
    out = args.out / ("run-" + uuid.uuid4().hex)
    out.mkdir(parents=True)
    frame, floor, velocity = bytearray(source), bytearray(source), bytearray(source)
    frame[12] ^= 1
    floor[27] ^= 1
    velocity[617] ^= 1
    cases = [("truncated", source[:-1], "size"), ("trailing", source + b"x", "size"),
             ("frame", frame, "fingerprint"), ("floor", floor, "fingerprint"),
             ("velocity", velocity, "fingerprint")]
    results = []
    environment = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    for name, payload, reason in cases:
        fixture = out / (name + ".bin")
        fixture.write_bytes(payload)
        process = subprocess.run([str(args.exe.resolve()), "--debug-walker-ledge-original", str(fixture.resolve())],
                                 cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15)
        (out / (name + ".stdout.txt")).write_text(process.stdout)
        (out / (name + ".stderr.txt")).write_text(process.stderr)
        result = {"case": name, "returncode": process.returncode,
                  "rejected_before_replay": process.returncode == 1 and not process.stdout and
                  f"walker ledge fixture {reason} differs" in process.stderr}
        results.append(result)
        (out / "results.json").write_text(json.dumps(results, sort_keys=True) + "\n")
        if not result["rejected_before_replay"]:
            raise RuntimeError(f"walker ledge guard failed: {name}, diagnostics retained at {out}")
    print("walker_ledge_guard=ok cases=5 rejected_before_replay=1 immutable_fixture=1 audio=dummy")


if __name__ == "__main__":
    main()
