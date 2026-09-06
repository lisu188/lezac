#!/usr/bin/env python3
"""Exercise flame replay completeness, newline handling, and byte sensitivity."""

import argparse
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    parser.add_argument("--fatal", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    name = "flame_fatal_lifecycle" if args.fatal else "flame_lifecycle"
    source = (root / f"tests/fixtures/{name}_original.txt").read_text(encoding="ascii")
    env = dict(os.environ, SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy")
    before = set(root.glob("*.ppm"))
    with tempfile.TemporaryDirectory(prefix="lezac-flame-fixture-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, error=None):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-flame-lifecycle-original", str(fixture)],
                                    cwd=root, env=env, capture_output=True, text=True, timeout=90)
            output = result.stdout + result.stderr
            success = "flame_lifecycle_original=ok cases=8 samples=520 records=3666 player_states=520"
            valid = (result.returncode == 0 and success in output) if error is None else (
                result.returncode != 0 and error in output and "flame_lifecycle_original=ok" not in output)
            if not valid:
                raise RuntimeError(f"expected={error or 'success'}: {output}")

        run(source)
        run(source.replace("\n", "\r\n"))
        rows = source.splitlines()
        run("\n".join(row for row in rows if not row.startswith("complete ")) + "\n",
            "missing flame completion")

        def mutate(prefix, field, transform, error):
            changed = rows.copy()
            index = next(i for i, row in enumerate(changed) if row.startswith(prefix))
            fields = dict(token.split("=", 1) for token in changed[index].split()[1:])
            value = transform(fields[field])
            if value is None:
                del fields[field]
            else:
                if value == fields[field]:
                    raise RuntimeError("fixture mutation is a no-op")
                fields[field] = value
            changed[index] = changed[index].split()[0] + " " + " ".join(f"{key}={value}" for key, value in fields.items())
            run("\n".join(changed) + "\n", error)

        mutate("flames sample=0 ", "records", lambda value: value[:8] + "00" + value[10:], "record=1")
        mutate("flames sample=0 ", "count", lambda value: "7", "count=8")
        mutate("flames sample=0 ", "words", lambda value: "0:0000", "word")
        mutate("tick sample=1 ", "player", lambda value: value[:72] + "63" + value[74:], "player motion/energy/death")
        mutate("tick sample=1 ", "player", lambda value: None, "missing flame player state")
        mutate("tick sample=1 ", "rng", lambda value: "00000000", "RNG")
        mutate("tick sample=1 ", "frame", lambda value: str(int(value) + 1), "nonconsecutive flame tick")
        mutate("tick sample=0 ", "others", lambda value: value[:4] + "00" + value[6:], "effect=0")
        if args.fatal:
            mutate("tick sample=2 ", "target", lambda value: value[:4] + "18" + value[6:], "corpse countdown")
            mutate("tick sample=52 ", "target", lambda value: "18" + value[2:], "reward")
    if set(root.glob("*.ppm")) != before:
        raise RuntimeError("replay without output directory wrote frames")
    mutations = 10 if args.fatal else 8
    print(f"{name}_fixture=ok lf=1 crlf=1 truncated_rejected=1 mutations_rejected={mutations} no_output_files=1")


if __name__ == "__main__":
    main()
