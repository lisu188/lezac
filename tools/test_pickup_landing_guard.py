"""Require the native pickup fixture to be validated before the seeded replay."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/pickup_landing_original.bin"
SHA256 = "b272ab18f79ccd50223cd8a9fa15f50336b487e3950888441cdd82d05c5455d3"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    source = FIXTURE.read_bytes()
    if len(source) != 2798 or hashlib.sha256(source).hexdigest() != SHA256:
        raise RuntimeError("native pickup landing source fixture changed")
    out = args.out / ("run-" + uuid.uuid4().hex)
    out.mkdir(parents=True)
    changed_frame, changed_seed, changed_label = bytearray(source), bytearray(source), bytearray(source)
    changed_frame[12] ^= 1
    changed_seed[15] ^= 1
    changed_label[555] ^= 1
    cases = [("truncated", source[:-1], "size"), ("trailing", source + b"x", "size"),
             ("frame", changed_frame, "fingerprint"), ("seed", changed_seed, "fingerprint"),
             ("label_y", changed_label, "fingerprint")]
    results = []
    environment = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    for name, payload, reason in cases:
        fixture = out / (name + ".bin")
        fixture.write_bytes(payload)
        process = subprocess.run([str(args.exe.resolve()), "--debug-pickup-landing-original", str(fixture.resolve())],
                                 cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15)
        (out / (name + ".stdout.txt")).write_text(process.stdout)
        (out / (name + ".stderr.txt")).write_text(process.stderr)
        expected = f"pickup landing fixture {reason} differs"
        result = {"case": name, "returncode": process.returncode,
                  "rejected_before_replay": process.returncode == 1 and not process.stdout and expected in process.stderr}
        results.append(result)
        (out / "results.json").write_text(json.dumps(results, sort_keys=True) + "\n")
        if not result["rejected_before_replay"]:
            raise RuntimeError(f"pickup landing guard failed: {name}, diagnostics retained at {out}")
    print("pickup_landing_guard=ok cases=5 rejected_before_replay=1 immutable_fixture=1 audio=dummy")


if __name__ == "__main__":
    main()
