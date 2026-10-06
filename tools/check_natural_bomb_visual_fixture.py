#!/usr/bin/env python3
"""Pin native-only bomb evidence and challenge C++ collision/visual mappings."""

import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "tests/fixtures/natural_bomb_visual_original.jsonl.gz"
SHA256 = "c369b38f74fa2352b461b7207af02277f89fddbeabc5f06d405fa9b56198ff67"


def load():
    data = FIXTURE.read_bytes()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("changed natural bomb fixture")
    rows = [json.loads(line) for line in gzip.decompress(data).splitlines()]
    header, footer = rows[0], rows[-1]
    if len(rows) != 356 or header["source"] != "original" or header["cpp_derived_expectations"] is not False:
        raise ValueError("invalid native-only provenance")
    if header["observation_method"] != "stopped_single_ds_snapshot" or header["whole_game_complete"] is not False:
        raise ValueError("invalid observation method or scope")
    if footer != dict(kind="complete", observations=354, scanned_boundaries=2878,
                      naturally_observed_actor_kinds=[14], whole_game_complete=False):
        raise ValueError("incomplete natural bomb fixture")
    return rows


def serialize(rows):
    header = rows[0]
    lines = ["capture=native_bomb_visual_v1 natural=1 observations=354 whole_game=0 "
             f"exe_sha256={header['executable_sha256']} stream_sha256={header['native_stream_sha256']}"]
    for index, row in enumerate(rows[1:-1]):
        if set(row) != {"kind", "tick", "phase", "actor_pool_slot", "actor_raw", "visual_raw"} or row["kind"] != "sample":
            raise ValueError("invalid natural observation fields")
        lines.append(f"sample index={index} tick={row['tick']} phase={row['phase']} slot={row['actor_pool_slot']} "
                     f"raw={row['actor_raw']} visual={row['visual_raw']}")
    lines.append("complete observations=354 whole_game=0")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    rows = load()
    source = serialize(rows)
    env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy",
               LEZAC_LOAD_JSON_ASSETS="0", LEZAC_LOAD_ORIGINAL_ASSETS="1")
    mutations = 0
    with tempfile.TemporaryDirectory(prefix="lezac-natural-bomb-visual-") as directory:
        fixture = Path(directory) / "fixture.txt"

        def run(content, valid=False):
            fixture.write_bytes(content.encode("ascii"))
            result = subprocess.run([str(args.exe.resolve()), "--debug-natural-bomb-visual-original", str(fixture)],
                                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            success = result.returncode == 0 and "natural_bomb_visual_original=ok observations=354" in output
            rejected = result.returncode != 0 and "fatal:" in output and "natural_bomb_visual_original=ok" not in output
            if not (success if valid else rejected):
                raise RuntimeError(f"valid={valid} status={result.returncode}: {output}")

        run(source, True)
        run(source.replace("\n", "\r\n"), True)
        for field, offsets in (("actor_raw", (0, 20, 21)), ("visual_raw", (4, 5, 6, 7))):
            for offset in offsets:
                changed = copy.deepcopy(rows)
                value = bytearray.fromhex(changed[1][field])
                value[offset] ^= 1
                changed[1][field] = value.hex()
                run(serialize(changed))
                mutations += 1
        lines = source.splitlines()
        variants = ["\n".join(lines[:-1]) + "\n", "\n".join(lines[:-2] + lines[-1:]) + "\n",
                    source + lines[1] + "\n", source.replace("natural=1", "natural=0", 1),
                    source.replace("whole_game=0", "whole_game=1", 1),
                    source.replace("sample index=0 ", "sample index=1 ", 1),
                    source.replace(" phase=post_update ", " phase=invalid ", 1),
                    source.replace("sample index=0 ", "sample extra=1 index=0 ", 1),
                    source.replace("sample index=0 ", "sample index=0 index=0 ", 1)]
        for variant in variants:
            if variant == source:
                raise RuntimeError("no-op natural bomb mutation")
            run(variant)
            mutations += 1
    print(f"natural_bomb_visual_fixture=ok observations=354 natural_types=1 newline_variants=2 "
          f"mutations_rejected={mutations} whole_game_parity=0 silent_children=1")


if __name__ == "__main__":
    main()
