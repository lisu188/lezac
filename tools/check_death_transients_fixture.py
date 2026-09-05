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
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    source = (root / "tests/fixtures/death_transients_original.txt").read_text(encoding="ascii")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    before = set(root.glob("*.ppm"))
    with tempfile.TemporaryDirectory(prefix="lezac-death-fixture-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, error=None):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run(
                [str(args.exe.resolve()), "--debug-death-transients-original", str(fixture)],
                cwd=root, env=env, capture_output=True, text=True, timeout=30,
            )
            output = result.stdout + result.stderr
            if error is None:
                valid = result.returncode == 0 and "death_transients_original=ok" in output
            else:
                valid = result.returncode != 0 and error in output and "death_transients_original=ok" not in output
            if not valid:
                raise RuntimeError(f"expected={error or 'success'}: {output}")

        run(source)
        run(source.replace("\n", "\r\n"))
        run("\n".join(line for line in source.splitlines() if not line.startswith("complete ")) + "\n",
            "missing death-effects completion")
        rows = source.splitlines()
        index = next(i for i, line in enumerate(rows) if line.startswith("tick "))
        fields = dict(token.split("=", 1) for token in rows[index].split()[1:])
        effects = fields["effects"]
        fields["effects"] = effects[:4] + "00" + effects[6:]
        rows[index] = "tick " + " ".join(f"{key}={value}" for key, value in fields.items())
        run("\n".join(rows) + "\n", "original death-effects mismatch: reward_even sample=0")
    if set(root.glob("*.ppm")) != before:
        raise RuntimeError("replay without output directory wrote frame files")
    print("death_transients_fixture=ok lf=1 crlf=1 truncated_rejected=1 timer_mutation_rejected=1 no_output_files=1")


if __name__ == "__main__":
    main()
