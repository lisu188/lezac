from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Iterator

ASSETS = (
    "LEZAC.EXE", "LIVELS.SCH", "CARO.CAR", "BOMOMIMK.SPR", "PROVA.SPR",
    "FONTS.SPR", "BOMPAL.PAL", "SFONLEF.ZBG", "PROEFS.SON", "GRAN.MST", "RECS.DAT",
)
KEYS = {"1", "2", "return", "escape", "l", "s", "e", "r", "p", "z", "x", "m", "n", "c",
        "left", "right", "up", "down", "insert"}
STATE_KEYS = {
    "level", "logic_tick", "random_seed", "player_count", "flow", "presentation", "progress",
    "dimensions", "tiles_hex", "words_hex", "palette_rgb_hex", "backdrop_fnv1a64", "players",
    "reentry", "intro", "outro", "next_actor_order", "sound_latch", "bombs", "monsters", "rewards",
    "effects", "flames", "debris", "collapse", "spawners", "transients", "markers", "flashes",
}
HEADER_KEYS = {
    "kind", "schema", "source", "phase_model", "state_scope", "input_model", "asset_fnv1a64",
    "route_fnv1a64", "ticks", "step_us", "seed", "width", "height", "original_fidelity_claim",
}


class EvidenceError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()


def fnv1a64(data: bytes) -> str:
    value = 14695981039346656037
    for byte in data:
        value = ((value ^ byte) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
    return f"{value:016x}"


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def strict_json(text: str) -> Any:
    def invalid(value: str) -> None:
        raise EvidenceError(f"non-finite JSON number: {value}")
    return json.loads(text, object_pairs_hook=unique_object, parse_constant=invalid)


def integer(value: Any, low: int, high: int) -> bool:
    return type(value) is int and low <= value <= high


def read_route(path: Path) -> tuple[dict[str, int], dict[int, list[dict[str, str]]]]:
    require(path.stat().st_size <= 2 * 1024 * 1024, "route exceeds 2 MiB")
    lines = path.read_text(encoding="utf-8").splitlines()
    lines = [line for line in lines if line]
    require(bool(lines) and lines[0] == "LEZAC_LEVEL1_ROUTE_V1", "invalid route header")
    settings: dict[str, int] = {}
    events: dict[int, list[dict[str, str]]] = {}
    held: set[str] = set()
    ended, count, last_tick = False, 0, 0
    for line in lines[1:]:
        require(not ended, "route data after end")
        parts = line.split()
        require(bool(parts), "empty route record")
        if parts == ["end"] and len(settings) == 3:
            ended = True
        elif len(parts) == 2 and parts[0] in {"seed", "ticks", "step_us"} and not events:
            key, value = parts
            require(key not in settings and re.fullmatch(r"[0-9]{1,10}", value) is not None, "invalid route setting")
            settings[key] = int(value)
            bounds = {"seed": (0, 2**32 - 1), "ticks": (1, 20000), "step_us": (1000, 1000000)}
            require(integer(settings[key], *bounds[key]), "route setting out of range")
        elif len(parts) == 4 and parts[0] == "event" and len(settings) == 3:
            _, at, action, key = parts
            require(re.fullmatch(r"[0-9]{1,10}", at) is not None, "invalid route event tick")
            tick = int(at)
            require(last_tick <= tick < settings["ticks"] and key in KEYS and count < 100000, "invalid route event")
            require(action in {"down", "up", "repeat"}, "invalid key action")
            require((action == "down" and key not in held) or (action != "down" and key in held), "invalid key ownership transition")
            if action == "up":
                held.remove(key)
            else:
                held.add(key)
            events.setdefault(tick, []).append({"action": action, "key": key})
            count, last_tick = count + 1, tick
        else:
            raise EvidenceError("unexpected route record")
    require(ended and count > 0, "incomplete route")
    return settings, events


def safe_file(root: Path, name: str) -> Path:
    require(isinstance(name, str) and Path(name).name == name and name not in {"", ".", ".."}, "unsafe artifact name")
    path = root / name
    require(not path.is_symlink() and path.is_file() and path.resolve().parent == root.resolve(), f"missing or unsafe artifact: {name}")
    return path


def read_ppm(path: Path) -> bytes:
    require(path.stat().st_size <= 200000, "oversized frame")
    data = path.read_bytes()
    header = b"P6\n320 200\n255\n"
    require(data.startswith(header) and len(data) == len(header) + 320 * 200 * 3, "invalid full-frame PPM")
    return data[len(header):]


def validate_state(state: Any) -> None:
    require(isinstance(state, dict) and set(state) == STATE_KEYS, "invalid observation fields")
    for key, bounds in {"level": (1, 7), "logic_tick": (0, 2**32 - 1), "random_seed": (0, 2**32 - 1),
                        "player_count": (1, 2), "next_actor_order": (1, 2**64 - 1)}.items():
        require(integer(state[key], *bounds), f"invalid state {key}")
    for key, length in {"flow": 8, "presentation": 7, "progress": 7, "dimensions": 2,
                        "reentry": 3, "intro": 4, "outro": 10, "sound_latch": 8}.items():
        require(isinstance(state[key], list) and len(state[key]) == length and all(type(v) is int for v in state[key]), f"invalid state {key}")
    width, height = state["dimensions"]
    require(1 <= width <= 1024 and 1 <= height <= 1024, "invalid level dimensions")
    for key, size in {"tiles_hex": width * height, "words_hex": width * height * 2, "palette_rgb_hex": 768}.items():
        value = state[key]
        require(isinstance(value, str) and len(value) == size * 2 and re.fullmatch(r"[0-9a-f]*", value) is not None, f"invalid {key}")
    require(re.fullmatch(r"[0-9a-f]{16}", state["backdrop_fnv1a64"]) is not None, "invalid backdrop fingerprint")
    players = state["players"]
    require(isinstance(players, list) and len(players) == 2, "invalid player observations")
    for player in players:
        require(isinstance(player, dict) and set(player) == {"x", "y", "vx8", "vy8", "frac_x", "frac_y",
                "animation", "animation_backup", "sprite", "health", "waiting", "score", "inventory", "cooldowns"}, "invalid player fields")
        for key in ("x", "y"):
            require(type(player[key]) in (int, float) and math.isfinite(player[key]), "invalid player position")
        for key in ("vx8", "vy8"):
            require(integer(player[key], -32768, 32767), "invalid player velocity")
        for key in ("frac_x", "frac_y"):
            require(integer(player[key], 0, 255), "invalid fractional carry")
        for key, length in {"animation": 7, "animation_backup": 7, "sprite": 5, "health": 5,
                            "waiting": 4, "inventory": 5, "cooldowns": 3}.items():
            require(isinstance(player[key], list) and len(player[key]) == length and all(type(v) is int for v in player[key]), f"invalid player {key}")
        require(integer(player["score"], 0, 2**32 - 1), "invalid player score")
    for key in ("bombs", "monsters", "rewards", "effects", "flames", "debris", "collapse", "spawners", "transients", "markers", "flashes"):
        require(isinstance(state[key], list) and len(state[key]) <= 10000, f"invalid actor array {key}")


def trace_rows(root: Path, manifest: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    settings, route_events = read_route(safe_file(root, "route.txt"))
    expected_route_hash = fnv1a64((root / "route.txt").read_bytes())
    seq, tick, frames, event_count = 0, 0, 0, 0
    expected = "initial"
    header = None
    ended, completion_seen, level2_playable = False, False, False
    frame_names: set[str] = set()
    with safe_file(root, "trace.jsonl").open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            require(len(line) <= 10 * 1024 * 1024 and line.strip() != "", f"invalid trace line {line_number}")
            require(not ended, "trace data after completion")
            row = strict_json(line)
            require(isinstance(row, dict), "trace record must be an object")
            if header is None:
                require(set(row) == HEADER_KEYS and row["kind"] == "header", "invalid trace header")
                require(row["schema"] == "lezac.level1.trace.v1" and row["source"] == "cpp" and
                        row["phase_model"] == "cpp-post-update-v1" and row["state_scope"] == "level1-observations-v1" and
                        row["input_model"] == "sdl-events-keyboard-adapter-v1", "unsupported trace contract")
                require(row["original_fidelity_claim"] is False and type(row["width"]) is int and row["width"] == 320 and type(row["height"]) is int and row["height"] == 200, "invalid fidelity claim or frame size")
                require(all(type(row[key]) is int and row[key] == value for key, value in settings.items()), "route settings differ from trace")
                require(row["route_fnv1a64"] == expected_route_hash, "route fingerprint mismatch")
                require(isinstance(row["asset_fnv1a64"], dict) and set(row["asset_fnv1a64"]) == set(ASSETS) and
                        all(isinstance(v, str) and re.fullmatch(r"[0-9a-f]{16}", v) for v in row["asset_fnv1a64"].values()), "invalid asset fingerprints")
                header = row
            elif row.get("kind") == "checkpoint":
                phase = row.get("phase")
                require(type(row.get("seq")) is int and row["seq"] == seq, "missing, duplicate or reordered checkpoint")
                require(type(row.get("tick")) is int and row["tick"] == tick and tick <= settings["ticks"], "invalid checkpoint tick")
                require(phase == expected or (expected == "after_nonplayers" and phase == "post_update"), "invalid checkpoint phase")
                has_frame = phase in {"initial", "present"}
                keys = {"kind", "seq", "tick", "phase", "time_ms", "events", "state"}
                if has_frame:
                    keys |= {"frame", "rgb_fnv1a64"}
                require(set(row) == keys, "invalid checkpoint fields")
                require(type(row["time_ms"]) is int and row["time_ms"] == max(0, tick - 1) * settings["step_us"] // 1000, "invalid clock sample")
                expected_events = route_events.get(tick - 1, []) if tick else []
                require(row["events"] == expected_events, "event log differs from route")
                validate_state(row["state"])
                if phase == "post_update":
                    state = row["state"]
                    completion_seen |= state["level"] == 1 and state["flow"][4] == 1
                    level2_playable |= completion_seen and state["level"] == 2 and state["flow"][0] == 0 and state["flow"][2] == 0 and state["flow"][3] == 0 and state["flow"][4] == 0
                if has_frame:
                    name = f"frame_{tick:06d}.ppm"
                    require(row["frame"] == name, "incorrect or unsafe frame name")
                    path = safe_file(root, name)
                    require(fnv1a64(read_ppm(path)) == row["rgb_fnv1a64"], "frame fingerprint mismatch")
                    if manifest is not None:
                        require(manifest["frames"].get(name) == sha256(path), "frame SHA-256 mismatch")
                    frame_names.add(name)
                    frames += 1
                    tick += 1
                    expected = "input"
                elif phase == "input":
                    event_count += len(expected_events)
                    expected = "after_nonplayers"
                else:
                    expected = "post_update" if phase == "after_nonplayers" else "present"
                seq += 1
            elif row.get("kind") == "complete":
                require(set(row) == {"kind", "ticks", "checkpoints", "frames", "events", "level1_route_complete",
                        "original_fidelity_claim", "port_functionally_complete"}, "invalid completion fields")
                require(expected == "input" and tick == settings["ticks"] + 1 and frames == tick, "truncated route")
                require(all(type(row[key]) is int and row[key] == value for key, value in
                        {"ticks": settings["ticks"], "checkpoints": seq, "frames": frames, "events": event_count}.items()), "completion counts differ")
                require(type(row["level1_route_complete"]) is bool and row["level1_route_complete"] == level2_playable,
                        "fabricated level completion")
                require(row["original_fidelity_claim"] is False and row["port_functionally_complete"] is False, "unsupported completion claim")
                ended = True
            else:
                raise EvidenceError("unexpected trace record")
            yield row
    require(ended, "missing trace completion marker")
    if manifest is not None:
        require(set(manifest["frames"]) == frame_names, "manifest frame set differs")


def load_manifest(root: Path) -> dict[str, Any]:
    path = safe_file(root, "manifest.json")
    require(path.stat().st_size <= 4 * 1024 * 1024, "oversized bundle manifest")
    manifest = strict_json(path.read_text(encoding="utf-8"))
    keys = {"schema", "trace_sha256", "route_sha256", "executable_sha256", "asset_sha256", "frames",
            "source", "environment", "original_fidelity_claim"}
    require(isinstance(manifest, dict) and set(manifest) == keys and
            manifest["schema"] == "lezac.level1.bundle.v1", "invalid bundle manifest")
    digest = lambda value: isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None
    require(digest(manifest["executable_sha256"]), "invalid executable fingerprint")
    require(manifest["trace_sha256"] == sha256(safe_file(root, "trace.jsonl")), "trace SHA-256 mismatch")
    require(manifest["route_sha256"] == sha256(safe_file(root, "route.txt")), "route SHA-256 mismatch")
    require(isinstance(manifest["frames"], dict) and 2 <= len(manifest["frames"]) <= 20001 and
            all(re.fullmatch(r"frame_[0-9]{6}\.ppm", key) and digest(value)
                for key, value in manifest["frames"].items()), "invalid frame manifest")
    require(isinstance(manifest["asset_sha256"], dict) and set(manifest["asset_sha256"]) == set(ASSETS), "missing asset manifest")
    require(all(digest(value) for value in manifest["asset_sha256"].values()), "invalid asset SHA-256")
    source = manifest["source"]
    require(isinstance(source, dict) and set(source) == {"revision", "dirty"}, "invalid source provenance")
    require((source["revision"] is None and source["dirty"] is None) or
            (isinstance(source["revision"], str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source["revision"]) and
             type(source["dirty"]) is bool), "invalid source revision")
    require(manifest["environment"] == {"SDL_AUDIODRIVER": "dummy", "SDL_VIDEODRIVER": "dummy"}, "invalid capture environment")
    require(manifest["original_fidelity_claim"] is False, "unverified bundle fidelity claim")
    return manifest


def source_version(root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        try:
            result = subprocess.run(["git", "-C", str(root), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10)
            return result.stdout.strip() if result.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""
    revision = git("rev-parse", "HEAD")
    return {"revision": revision or None, "dirty": bool(git("status", "--porcelain")) if revision else None}


def record(exe: Path, root: Path, route: Path, out: Path, timeout: float = 600) -> dict[str, Any]:
    exe, root, route, out = exe.resolve(), root.resolve(), route.resolve(), out.resolve()
    require(not out.exists(), "output already exists")
    require(exe.is_file(), "missing C++ executable")
    read_route(route)
    assets = {name: sha256(safe_file(root, name)) for name in ASSETS}
    asset_fnv = {name: fnv1a64((root / name).read_bytes()) for name in ASSETS}
    environment = dict(os.environ, SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy",
                       LEZAC_LOAD_JSON_ASSETS="0", LEZAC_LOAD_ORIGINAL_ASSETS="1")
    result = subprocess.run([str(exe), "--replay-level1", str(route), str(out)], cwd=root, env=environment,
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    require(result.returncode == 0, f"C++ replay failed ({result.returncode}): {result.stderr.strip()}")
    (out / "stdout.txt").write_text(result.stdout, encoding="utf-8")
    (out / "stderr.txt").write_text(result.stderr, encoding="utf-8")
    shutil.copyfile(route, out / "route.txt")
    require(assets == {name: sha256(root / name) for name in ASSETS}, "replay changed source assets")
    frames = {}
    header, footer = None, None
    for row in trace_rows(out):
        if row["kind"] == "header":
            header = row
        if "frame" in row:
            frames[row["frame"]] = sha256(out / row["frame"])
        footer = row
    require(header is not None and header["asset_fnv1a64"] == asset_fnv, "C++ asset provenance differs")
    manifest = {"schema": "lezac.level1.bundle.v1", "trace_sha256": sha256(out / "trace.jsonl"),
                "route_sha256": sha256(out / "route.txt"), "executable_sha256": sha256(exe),
                "asset_sha256": assets, "frames": frames, "source": source_version(root),
                "environment": {"SDL_AUDIODRIVER": "dummy", "SDL_VIDEODRIVER": "dummy"},
                "original_fidelity_claim": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"status": "recorded", "output": str(out), "summary": footer, "original_fidelity_claim": False}


def first_difference(reference: Any, candidate: Any, path: str = "$") -> dict[str, Any] | None:
    if type(reference) != type(candidate):
        return {"path": path, "reference": reference, "candidate": candidate}
    if isinstance(reference, dict):
        if reference.keys() != candidate.keys():
            return {"path": path, "reference_keys": sorted(reference), "candidate_keys": sorted(candidate)}
        for key in sorted(reference):
            found = first_difference(reference[key], candidate[key], f"{path}.{key}")
            if found:
                return found
    elif isinstance(reference, list):
        if len(reference) != len(candidate):
            return {"path": path + ".length", "reference": len(reference), "candidate": len(candidate)}
        for index, (left, right) in enumerate(zip(reference, candidate)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found:
                return found
    elif reference != candidate:
        if isinstance(reference, str) and path.endswith("_hex") and len(reference) == len(candidate):
            index = next(i for i in range(0, len(reference), 2) if reference[i:i+2] != candidate[i:i+2])
            return {"path": path, "byte_offset": index // 2, "reference": reference[index:index+2], "candidate": candidate[index:index+2]}
        return {"path": path, "reference": reference, "candidate": candidate}
    return None


def compare(reference: Path, candidate: Path, out: Path | None = None) -> dict[str, Any]:
    left_manifest, right_manifest = load_manifest(reference), load_manifest(candidate)
    require(left_manifest["route_sha256"] == right_manifest["route_sha256"], "cannot compare different input routes")
    require(left_manifest["asset_sha256"] == right_manifest["asset_sha256"], "cannot compare different original assets")
    sentinel = object()
    mismatch = None
    checkpoints = frames = 0
    candidate_checkpoints = 0
    for left, right in itertools.zip_longest(trace_rows(reference, left_manifest), trace_rows(candidate, right_manifest), fillvalue=sentinel):
        if left is sentinel or right is sentinel:
            remaining = right if left is sentinel else left
            if mismatch is None:
                mismatch = {"seq": remaining.get("seq"), "tick": remaining.get("tick"),
                            "phase": remaining.get("phase"), "path": "$.record_count"}
            if remaining.get("kind") == "checkpoint":
                if left is sentinel:
                    candidate_checkpoints += 1
                else:
                    checkpoints += 1
            continue
        if right.get("kind") == "checkpoint":
            candidate_checkpoints += 1
        if left.get("kind") == "checkpoint":
            checkpoints += 1
        if "frame" in left:
            frames += 1
        found = first_difference(left, right)
        if found is not None and mismatch is None:
            mismatch = {"seq": left.get("seq"), "tick": left.get("tick"), "phase": left.get("phase"), **found}
    for name in sorted(left_manifest["frames"]):
        left_pixels = read_ppm(safe_file(reference, name))
        right_pixels = read_ppm(safe_file(candidate, name))
        if left_pixels != right_pixels:
            frame_tick = int(name[6:12])
            if mismatch is None or (type(mismatch.get("tick")) is int and frame_tick < mismatch["tick"]):
                pixel = next(i for i in range(0, len(left_pixels), 3) if left_pixels[i:i+3] != right_pixels[i:i+3]) // 3
                mismatch = {"seq": None, "tick": frame_tick, "phase": "initial" if frame_tick == 0 else "present",
                            "path": "$.frame.rgb", "x": pixel % 320, "y": pixel // 320}
    report = {"status": "match" if mismatch is None else "diverged", "checkpoints": checkpoints,
              "candidate_checkpoints": candidate_checkpoints,
              "frames": len(left_manifest["frames"]), "pixels": len(left_manifest["frames"]) * 320 * 200, "first_divergence": mismatch,
              "comparison_scope": "cpp-replay-regression", "original_fidelity_claim": False}
    if out is not None:
        require(not out.exists(), "report output already exists")
        out.mkdir(parents=True)
        if mismatch is not None and type(mismatch["tick"]) is int:
            name = f"frame_{mismatch['tick']:06d}.ppm"
            left = read_ppm(safe_file(reference, name))
            right = read_ppm(safe_file(candidate, name))
            shutil.copyfile(reference / name, out / "reference.ppm")
            shutil.copyfile(candidate / name, out / "candidate.ppm")
            different = bytes(abs(a-b) for a, b in zip(left, right))
            (out / "difference.ppm").write_bytes(b"P6\n320 200\n255\n" + different)
            report["frame_differing_pixels"] = sum(left[i:i+3] != right[i:i+3] for i in range(0, len(left), 3))
        (out / "comparison.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Record and compare production Level 1 C++ input replays; no original-game parity claim.")
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser("record")
    capture.add_argument("--exe", type=Path, required=True)
    capture.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    capture.add_argument("--route", type=Path, required=True)
    capture.add_argument("--out", type=Path, required=True)
    capture.add_argument("--timeout", type=float, default=600)
    verify = commands.add_parser("validate")
    verify.add_argument("bundle", type=Path)
    diff = commands.add_parser("compare")
    diff.add_argument("reference", type=Path)
    diff.add_argument("candidate", type=Path)
    diff.add_argument("--out", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "record":
            require(math.isfinite(args.timeout) and 1 <= args.timeout <= 3600, "timeout must be 1..3600 seconds")
            report = record(args.exe, args.root, args.route, args.out, args.timeout)
        elif args.command == "validate":
            manifest = load_manifest(args.bundle)
            count = sum(1 for _ in trace_rows(args.bundle, manifest))
            report = {"status": "valid", "records": count, "original_fidelity_claim": False}
        else:
            report = compare(args.reference, args.candidate, args.out)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 1 if report["status"] == "diverged" else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"status": "invalid", "error": str(error), "original_fidelity_claim": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
