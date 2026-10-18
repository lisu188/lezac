"""Check frozen render/execution inputs in an actual autocrlf-enabled cold checkout."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


FAMILIES = ("frame_view_copy", "frame_camera", "frame_world_raster", "frame_spawner", "frame_render", "reserve_hud", "ammo_hud", "player_start", "waiting_placement", "frame_waiting", "frame_prefix")
RULES = tuple(f"tests/fixtures/{name}/** -text" for name in FAMILIES)


def check(root, out, git):
    stage = out / "stage"
    stage.mkdir()
    environment = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        environment.pop(key, None)
    environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                       GIT_ATTR_NOSYSTEM="1")

    def run(*arguments):
        command = [git, "-c", "core.autocrlf=true", "-c", "core.safecrlf=false",
                   "-c", "core.attributesfile=" + os.devnull,
                   "-c", "safe.directory=" + stage.as_posix(), *arguments]
        result = subprocess.run(command, cwd=stage, env=environment,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode:
            raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
        return result.stdout

    paths = [Path(".gitattributes")]
    manifests = []
    for name in FAMILIES:
        directory = Path("tests/fixtures") / name
        if not (root / directory).is_dir():
            continue
        manifest = directory / "manifest.json"
        manifests.append(manifest)
        stream = directory / "oracle.bin.gz" if (root / directory / "oracle.bin.gz").exists() else directory / "oracle.bin"
        paths.extend((manifest, stream))
        paths.extend(path.relative_to(root) for path in sorted(
            (root / directory).glob("*.bin")) if path.relative_to(root) != stream)
        paths.extend(path.relative_to(root) for path in sorted(
            (root / "tools").glob(name + "_*.py")))
    if not manifests:
        raise ValueError("No frozen render fixtures found")
    if len(paths) != len(set(paths)):
        raise ValueError("Duplicate frozen render checkout input")
    for relative in paths:
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, target)
    run("init", "--quiet")
    run("add", "--", ".")
    attributes = run("check-attr", "-z", "text", "--", *(
        f"tests/fixtures/{name}/manifest.json" for name in FAMILIES)).split(b"\0")
    if attributes[-1:] != [b""] or len(attributes) != len(FAMILIES) * 3 + 1:
        raise ValueError("Unexpected Git attribute result")
    if any(attributes[i] != b"text" or attributes[i + 1] != b"unset"
           for i in range(1, len(FAMILIES) * 3, 3)):
        raise ValueError("Frozen render manifests must have text conversion disabled")
    cold = out / "cold"
    cold.mkdir()
    run("checkout-index", "--all", "--prefix=../cold/")
    for relative in paths:
        if (cold / relative).read_bytes() != (root / relative).read_bytes():
            raise ValueError("Cold checkout changed " + relative.as_posix())

    # Removing only the protected-family rules must reproduce the Windows fault.
    original_attributes = (stage / ".gitattributes").read_text(encoding="utf-8")
    lines = original_attributes.splitlines()
    if any(lines.count(rule) != 1 for rule in RULES):
        raise ValueError("Expected one protection rule for each frozen render family")
    (stage / ".gitattributes").write_bytes(("\n".join(
        line for line in lines if line not in RULES) + "\n").encode("utf-8"))
    run("add", "--", ".gitattributes")
    negative = out / "negative"
    negative.mkdir()
    run("checkout-index", "--all", "--prefix=../negative/")
    for relative in manifests:
        source = (root / relative).read_bytes()
        changed = (negative / relative).read_bytes()
        if b"\r" in source or b"\n" not in source:
            raise ValueError("Control requires canonical LF input")
        if changed == source or changed.replace(b"\r\n", b"\n") != source:
            raise ValueError("Negative control did not reproduce CRLF conversion")
    for relative in paths:
        if relative.suffix == ".py" and (
                negative / relative).read_bytes() != (root / relative).read_bytes():
            raise ValueError("Producer LF policy changed")
    return dict(passed=True, families=len(manifests), files=len(paths),
                crlf_negative_controls=len(manifests))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--git", default="git")
    arguments = parser.parse_args()
    arguments.out.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="cold-checkout-", dir=arguments.out)).resolve()
    root = Path(__file__).resolve().parents[1]
    try:
        report = check(root, out, arguments.git)
    except Exception as error:
        report = dict(passed=False, error=str(error))
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                          encoding="utf-8")
        raise
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n",
                                      encoding="utf-8")
    print("frozen_render_checkout=ok " + json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
