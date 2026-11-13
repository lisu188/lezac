#!/usr/bin/env python3
"""Check sealed original menu observations against the production renderer."""

import argparse
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/main_menu_original"
MANIFEST_SHA = "eb09054b54bd92855aefd69f6530cca624ab3dc09cb4a79d44c27cec2868f860"
HEADER = b"P6\n320 200\n255\n"
LENGTHS = {"italian": [25, 26, 16, 14, 16, 11, 15], "english": [28, 29, 9, 16, 16, 12, 10]}


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_manifest(manifest):
    require(manifest["version"] == 1, "manifest version")
    capture = manifest["capture"]
    require(capture["status"] == "observed" and capture["audio"] == "dummy", "capture not observed silently")
    require(capture["clock_forced"] is False and capture["gameplay_seeded"] is False, "forced original state")
    require(capture["text_loop_gated"] is True and capture["fade_loop_gated"] is True and
            capture["natural_wall_clock_timing"] is False, "capture timing scope")
    require(capture["hooks_restored"] == 3 and capture["child_exit_code"] == 0, "capture cleanup")
    require(len(capture["menu_rng_samples"]) == 2, "missing RNG boundaries")
    for language, row in zip(LENGTHS, capture["menu_rng_samples"]):
        require(row["phase"] == language + "-full" and row["clock_calls"] == 1 and row["draws"] == 0 and
                row["rng"] == row["initialized_rng"] == row["clock_cx"] | (row["clock_dx"] << 16), "menu RNG chain")
    fades = [(language, factor) for language in LENGTHS for factor in range(64)]
    require([(r["language"], r["factor"]) for r in capture["fade_samples"]] == fades and
            [r["sequence"] for r in capture["fade_samples"]] == list(range(1, 129)), "fade sequence")
    expected = [(language, line, iteration, length) for language, lengths in LENGTHS.items()
                for line, length in enumerate(lengths) for iteration in range(1, length + 6)]
    require(len(capture["samples"]) == len(expected) == 313, "text sample count")
    for sequence, (row, (language, line, iteration, length)) in enumerate(zip(capture["samples"], expected), 1):
        require((row["language"], row["line"], row["iteration"], row["sequence"]) ==
                (language, line, iteration, sequence), "text sequence")
        require((row["cell"], row["shadow"], row["color_first"], row["color_last"], row["y"], row["x"]) ==
                (9, 6, 6, 10, 77 + line * 10, 160 - length * 9 // 2), "original text arguments")
        require(row["delay_word"] == 81, "captured calibrated delay word")
    names = {language + suffix for language, lengths in LENGTHS.items()
             for suffix in ("-fade0", "-fade31", "-fade63", "-line0-step01", "-line0-step02",
                            "-line0-step06", f"-line0-step{lengths[0] + 5:02d}", "-full")}
    require(len(manifest["frames"]) == 16 and {f["name"] for f in manifest["frames"]} == names, "frame inventory")
    require(len(capture["captures"]) == 16 and {f["name"] for f in capture["captures"]} == names, "capture inventory")
    originals = {f["name"]: f["sha256"] for f in capture["captures"]}
    for frame in manifest["frames"]:
        require(frame["original_png_sha256"] == originals[frame["name"]] and
                frame["file"] == frame["ppm_sha256"] + ".ppm.gz", "frame provenance")


def load_fixture():
    data = (FIXTURE / "manifest.json").read_bytes()
    require(sha(data) == MANIFEST_SHA, "sealed manifest hash")
    manifest = json.loads(data)
    validate_manifest(manifest)
    capture = manifest["capture"]
    require(sha((ROOT / "LEZAC.EXE").read_bytes()) == capture["original_exe_sha256"], "original executable changed")
    require(sha((ROOT / "SFONLEF.ZBG").read_bytes()) == capture["background_sha256"], "original title changed")
    for path, checksum in capture["sources"].items():
        require(sha((ROOT / path).read_bytes().replace(b"\r\n", b"\n")) == checksum, "capture source changed: " + path)
    frames = {}
    for frame in manifest["frames"]:
        compressed = (FIXTURE / frame["file"]).read_bytes()
        require(sha(compressed) == frame["gzip_sha256"], "compressed frame hash")
        data = gzip.decompress(compressed)
        require(len(data) == len(HEADER) + 64000 * 3 and data.startswith(HEADER) and
                sha(data) == frame["ppm_sha256"], "original PPM frame changed")
        frames[frame["name"]] = data
    require({p.name for p in FIXTURE.iterdir()} == {"manifest.json"} | {f["file"] for f in manifest["frames"]}, "fixture files")
    return manifest, frames


def mutation_checks(manifest):
    changes = (("status", "failed"), ("audio", "pulseaudio"), ("clock_forced", True),
               ("gameplay_seeded", True), ("text_loop_gated", False), ("fade_loop_gated", False),
               ("natural_wall_clock_timing", True), ("hooks_restored", 2), ("child_exit_code", 1))
    for key, value in changes:
        changed = copy.deepcopy(manifest)
        changed["capture"][key] = value
        try:
            validate_manifest(changed)
        except RuntimeError:
            continue
        raise RuntimeError("accepted invalid capture: " + key)
    for field in ("cell", "shadow", "y", "x", "delay_word", "iteration"):
        changed = copy.deepcopy(manifest)
        changed["capture"]["samples"][0][field] += 1
        try:
            validate_manifest(changed)
        except RuntimeError:
            continue
        raise RuntimeError("accepted invalid text sample: " + field)
    return len(changes) + 6


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, required=True)
    args = parser.parse_args()
    manifest, originals = load_fixture()
    mutations = mutation_checks(manifest)
    with tempfile.TemporaryDirectory(prefix="lezac-main-menu-") as directory:
        output = Path(directory) / "frames"
        env = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
        subprocess.run([str(args.exe.resolve()), str(output)], cwd=ROOT, env=env, check=True, timeout=30)
        require({p.stem for p in output.iterdir()} == set(originals), "C++ frame inventory")
        for name, original in originals.items():
            require((output / (name + ".ppm")).read_bytes() == original, "C++ pixels differ: " + name)
    print(f"main_menu_original=ok frames=16 pixels=1024000 text_steps=313 fade_steps=128 mutations={mutations} whole_game_parity=0")


if __name__ == "__main__":
    main()
