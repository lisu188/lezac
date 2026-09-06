#!/usr/bin/env python3
"""Check death-effect fixture newlines, completeness, and field sensitivity."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--reward-lifecycle", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    name = "reward_lifecycle" if args.reward_lifecycle else "death_transients"
    source = (root / f"tests/fixtures/{name}_original.txt").read_text(encoding="ascii")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    before = set(root.glob("*.ppm"))
    with tempfile.TemporaryDirectory(prefix="lezac-death-fixture-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, error=None):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run(
                [str(args.exe.resolve()), f"--debug-{name.replace('_', '-')}-original", str(fixture)],
                cwd=root, env=env, capture_output=True, text=True, timeout=30,
            )
            output = result.stdout + result.stderr
            if error is None:
                valid = result.returncode == 0 and f"{name}_original=ok" in output
            else:
                valid = result.returncode != 0 and error in output and f"{name}_original=ok" not in output
            if not valid:
                raise RuntimeError(f"expected={error or 'success'}: {output}")

        run(source)
        run(source.replace("\n", "\r\n"))
        run("\n".join(line for line in source.splitlines() if not line.startswith("complete ")) + "\n",
            "missing death-effects completion")
        rows = source.splitlines()
        index = next(i for i, line in enumerate(rows) if line.startswith("tick "))
        fields = dict(token.split("=", 1) for token in rows[index].split()[1:])
        target = "rewards" if args.reward_lifecycle else "effects"
        offset = 16 if args.reward_lifecycle else 4
        value = fields[target]
        fields[target] = value[:offset] + "00" + value[offset + 2:]
        rows[index] = "tick " + " ".join(f"{key}={value}" for key, value in fields.items())
        case = "expiry_even" if args.reward_lifecycle else "reward_even"
        run("\n".join(rows) + "\n", f"original death-effects mismatch: {case} sample=0")
    if set(root.glob("*.ppm")) != before:
        raise RuntimeError("replay without output directory wrote frame files")
    mutation = "velocity" if args.reward_lifecycle else "timer"
    print(f"{name}_fixture=ok lf=1 crlf=1 truncated_rejected=1 {mutation}_mutation_rejected=1 no_output_files=1")


if __name__ == "__main__":
    main()
