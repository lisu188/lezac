#!/usr/bin/env python3
"""Guard original shared-death captures and their production-path replays."""

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile

from check_reentry_wait_evidence import parse, pixels


ROOT = Path(__file__).resolve().parent.parent
CASES = (
    ("reentry_wait", "reentry", "massive_even", 420, 22, 304,
     "e26aa4f34969721fecc384ba3cd9932d506789a33465845418635e4c0f876ce8",
     "435fc2eee069e6064cfc14669c3c3b99ab9ddbbdf204c9ddd458e66b81017a22",
     "20526d0385d08e1782922fb6c4a8a2e82b7e4391f0f0dfd606c245f86856ce98"),
    ("zero_reserve", "zero-reserve", "zero_reserve_even", 420, 22, 307,
     "defd26902afec04e0fa1c407b780bd3326d0d9f6b3e57e370861e83d0794febd",
     "2b28e18d36f6d288507fbb2178e1465b386bd29330807be0d4658e309be16c10",
     "e655b553b586c575d5242c62c9309825f97b509b9550250b62897a24bf630914"),
    ("fire_reentry", "fire-reentry", "fire_reentry_even", 140, 16, 101,
     "9aca04234b9f4e7562825f4257f35ac7d080b91ffb6600606598ac0a9470c7fb", None, None),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-reentry-") as directory:
        temporary = Path(directory)
        fixture = temporary / "fixture.txt"
        for filename, command, name, samples, views, transition, digest, intro_hash, ppm_hash in CASES:
            source = (ROOT / "tests/fixtures" / f"boss_{filename}_original_level7.txt").read_text(encoding="ascii")
            if hashlib.sha256(source.encode("ascii")).hexdigest() != digest:
                raise RuntimeError(f"changed original capture: {name}")
            rows = parse(source)
            original_views = [f for tag, f in rows if tag == "view"]
            if len(original_views) != views:
                raise RuntimeError("original view count")
            for view in original_views:
                raw = pixels(view["pixels"], 312 * 152)
                if len(set(raw)) < 16 or hashlib.sha256(raw).hexdigest() != view["indexed_sha256"]:
                    raise RuntimeError("original indexed view/hash")
            if intro_hash:
                image = ROOT / "tests/fixtures" / f"boss_{filename}_original_intro.png"
                intro = next(f for tag, f in rows if tag == "intro")
                if hashlib.sha256(image.read_bytes()).hexdigest() != intro_hash or intro["sha256"] != intro_hash:
                    raise RuntimeError("original introduction hash")

            def run(text, valid=False, frames=False):
                fixture.write_bytes(text.encode("ascii"))
                argv = [str(args.exe.resolve()), f"--debug-boss-{command}-original", str(fixture)]
                output_dir = temporary / name
                if frames:
                    argv.append(str(output_dir))
                result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, text=True, timeout=90)
                output = result.stdout + result.stderr
                success = result.returncode == 0 and f"boss_reentry_original=ok cases=1 samples={samples}" in output
                failure = result.returncode != 0 and "boss-continuous" in output and "boss_reentry_original=ok" not in output
                if not (success if valid else failure):
                    raise RuntimeError(f"{name} expected_valid={valid}: {output}")
                if frames:
                    if len(list(output_dir.glob("*.ppm"))) != views + bool(intro_hash):
                        raise RuntimeError("replay frame count")
                    if ppm_hash and hashlib.sha256((output_dir / f"{name}_intro.ppm").read_bytes()).hexdigest() != ppm_hash:
                        raise RuntimeError("replay introduction pixels")

            run(source, True, True)
            run(source.replace("\n", "\r\n"), True)

            def changed(tag, sample, field, transform):
                nonlocal mutations
                modified = [(t, f.copy()) for t, f in rows]
                index = next(i for i, (t, f) in enumerate(modified)
                             if t == tag and (sample is None or f.get("sample") == str(sample)))
                value = modified[index][1][field]
                modified[index][1][field] = transform(value)
                if modified[index][1][field] == value:
                    raise RuntimeError("no-op fixture mutation")
                text = "\n".join(("" if "=" in t else t + " ") + " ".join(f"{k}={v}" for k, v in f.items()) for t, f in modified) + "\n"
                run(text)
                mutations += 1

            def byte(value, at):
                raw = bytearray.fromhex(value)
                raw[at] ^= 1
                return raw.hex()

            for tick in (transition - 1, transition, transition + 1, samples - 1):
                for field in ("fallback", "lives", "player_state", "resets"):
                    changed("tick", tick, field, lambda v: str(int(v) + 1))
                for at in (16, 21, 22, 25):
                    changed("tick", tick, "p1", lambda v, at=at: byte(v, at))
            for field in ("counter", "frame", "gate"):
                changed("boundary", None, field, lambda v: str(int(v) + 1))
            for field, at in (("rng", 0), ("regs", 2), ("flags", 1), ("p1", 16), ("visuals", 0)):
                changed("boundary", None, field, lambda v, at=at: byte(v, at))
            if filename == "fire_reentry":
                changed("key", 100, "sample", lambda _: "99")
                changed("key", 100, "after_state_prepass", lambda _: "0")
            else:
                changed("tick", transition, "links", lambda v: byte(v, 11))
            for modified in ("\n".join(source.splitlines()[:-1]) + "\n", source + "complete cases=1 samples=0 views=0\n"):
                run(modified)
                mutations += 1
            print(f"boss_reentry_fixture case={name} samples={samples} views={views} original_hash=1 production_replay=1", flush=True)
    print(f"boss_reentry_fixture=ok cases=3 samples=980 views=60 mutations={mutations} newline_variants=2 silent_children=1 whole_game_parity=0")


if __name__ == "__main__":
    main()
