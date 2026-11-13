#!/usr/bin/env python3
"""Validate the original walker gravity fixture and malformed replay rejection."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from level1_fidelity import safe_file, strict_json

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SHA = "17c7c33a7ef9c94fc69332e220ead2d0337fc765b2f6383650dd516188803df5"
EXE_SHA = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
VELOCITIES = (-32768, -32767, -65, -64, -1, 0, 1, 63, 1982, 1983, 1984, 2047, 2048, 32703, 32704, 32767)
RAW = bytes.fromhex("807edf007406837ef2007d128346f240817ef2ff077e05c746f2ff07eb18837ef2007e1231c08946f28b46d225f8ff8946d2c646e001")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(data: bytes, exe: bytes) -> None:
    require(len(data) == 486 and hashlib.sha256(data).hexdigest() == FIXTURE_SHA, "fixture extent/hash differs")
    require(data[:8] == b"LZGWv1\0\0" and struct.unpack_from("<HHHH", data, 8) == (32, 12, 0x716E, 0x71A4), "fixture header differs")
    require(hashlib.sha256(exe).hexdigest() == EXE_SHA and data[16:48] == bytes.fromhex(EXE_SHA), "original executable differs")
    require(data[48:102] == RAW == exe[0x770 + 0x716E:0x770 + 0x71A4], "original instruction window differs")
    rows = [struct.unpack_from("<BBhhhhBB", data, 102 + index * 12) for index in range(32)]
    require([(row[0], row[1], row[2]) for row in rows] ==
            [(index, index // 16, VELOCITIES[index % 16]) for index in range(32)], "case coverage/order differs")
    require(all(row[4] == 99 and row[6] == 0 and row[7] in (0, 1) for row in rows), "seed/local flag differs")
    require(sum(row[1] == 0 and row[2] >= 32704 and row[3] < 0 for row in rows) == 2 and
            sum(row[7] == 1 and row[5] == 96 for row in rows) == 10, "word-wrap/landing coverage differs")


def rejected(data: bytes, exe: bytes) -> None:
    try:
        validate(data, exe)
    except ValueError:
        return
    raise AssertionError("malformed fixture accepted")


def validate_capture(directory: Path, data: bytes, producer: Path) -> None:
    captured = strict_json((directory / "capture.json").read_text(encoding="utf-8"))
    require(not (directory / "failure.json").exists() and captured["schema"] == "lezac-walker-gravity-word-v1" and
            captured["complete"] is True and captured["case_count"] == len(captured["cases"]) == 32,
            "native capture is failed/incomplete")
    require(captured["assets_sha256"]["LEZAC.EXE"] == EXE_SHA and captured["producer_sha256"] == hashlib.sha256(producer.read_bytes()).hexdigest() and
            captured["audio_driver"] == "dummy" and captured["owned_child_returncode"] is not None and
            captured["hook_free_stack_preserved"] is True and captured["unseeded_bootstrap_ticks"] == 1 and
            captured["natural_campaign_claim"] is False and captured["original_fidelity_claim"] is False and
            captured["full_actor_update_parity_claim"] is False and captured["pixel_parity_claim"] is False,
            "native producer/closure/scope differs")
    require(captured["instruction_window"] == [0x716E, 0x71A4] and captured["instruction_window_hex"] == RAW.hex() and
            captured["instruction_windows_sha256"] == hashlib.sha256(RAW).hexdigest(), "native instruction window differs")
    require(captured["hooks"] == [[0x7EC5, "c70682200100"], [0x716E, "807edf00"], [0x71A4, "807edf00"]], "native hook extent differs")
    for name, digest in captured["files"].items():
        require(hashlib.sha256(safe_file(directory, name).read_bytes()).hexdigest() == digest, "native captured file differs")
    require(len(captured["assets_sha256"]) == 11, "native original asset scope differs")
    for name, digest in captured["assets_sha256"].items():
        require(hashlib.sha256(safe_file(ROOT, name).read_bytes()).hexdigest() == digest, "original source asset differs")
    for name, digest in captured["support_dependencies_sha256"].items():
        require(hashlib.sha256(safe_file(ROOT / "tools", name).read_bytes()).hexdigest() == digest, "native support dependency differs")
    require(strict_json((directory / "restoration.json").read_text(encoding="utf-8")) ==
            {"hooks_restored": True, "scratch_restored": True, "child_retained_stopped": True, "installed_hooks": 3},
            "native hooks/scratch were not restored")
    allowed = {0x3A - 0x0E, 0x3A - 0x0D, 0x3A - 0x2E, 0x3A - 0x2D, 0x3A - 0x20}
    records = []
    for index, row in enumerate(captured["cases"]):
        before, after = row["before"], row["after"]
        require(row["index"] == index and row["seed_bottom"] == before["bottom"] == after["bottom"] == index // 16 and
                row["seed_vy"] == before["vy"] == VELOCITIES[index % 16] and before["y"] == 99 and
                before["x"] == after["x"] == 336 and before["kind"] == after["kind"] == 1 and
                before["behavior"] == after["behavior"] == 3 and before["facing_dirty"] == 0 and
                before["registers"] == after["registers"] and len(before["registers"]) == 6,
                "native case input/registers differ")
        old, new = bytes.fromhex(before["stack_hex"]), bytes.fromhex(after["stack_hex"])
        require(len(old) == len(new) == 0x3A and
                all(a == b for at, (a, b) in enumerate(zip(old, new)) if at not in allowed),
                "native undeclared local byte differs")
        records.append(struct.pack("<BBhhhhBB", index, before["bottom"], before["vy"], after["vy"],
                                   before["y"], after["y"], before["facing_dirty"], after["facing_dirty"]))
    require(b"".join(records) == data[102:], "native original result does not reproduce the complete pinned fixture")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=ROOT / "tests/fixtures/walker_gravity_word_original.bin")
    parser.add_argument("--original-exe", type=Path, default=ROOT / "LEZAC.EXE")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--replay-exe", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--producer-file", type=Path, default=ROOT / "tools/capture_original_walker_gravity.py")
    args = parser.parse_args()
    data, exe = args.fixture.read_bytes(), args.original_exe.read_bytes()
    validate(data, exe)
    if args.capture:
        validate_capture(args.capture, data, args.producer_file)
        print("walker_gravity_native_capture=ok cases=32 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy natural_route_claim=0")
    elif args.self_test:
        for index in range(len(data)):
            changed = bytearray(data)
            changed[index] ^= 1
            rejected(bytes(changed), exe)
        rejected(data[:-1], exe)
        rejected(data + b"\0", exe)
        rejected(data, exe[:-1])
        print("walker_gravity_fixture_selftest=ok cases=32 byte_mutations=486 truncated=1 trailing=1 original_mutation=1")
    elif args.replay_exe:
        environment = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
        checked = subprocess.run([str(args.replay_exe.resolve()), "--debug-walker-gravity-word-evidence", str(args.fixture.resolve())],
                                 cwd=ROOT, env=environment, capture_output=True, text=True, timeout=30)
        require(checked.returncode == 0 and "walker_gravity_word=ok cases=32 production_updates=32" in checked.stdout,
                "positive production replay did not pass")
        mutations = [data[:-1], data + b"\0"]
        for index in (0, 8, 12, 16, 48, 102, 103, 106, 112, 114, 270, 274, 282, 286, 484, 485):
            changed = bytearray(data)
            changed[index] ^= 1
            mutations.append(bytes(changed))
        with tempfile.TemporaryDirectory(prefix="lezac-walker-gravity-guard-") as directory:
            for index, mutation in enumerate(mutations):
                fixture = Path(directory) / f"mutation-{index}.bin"
                fixture.write_bytes(mutation)
                result = subprocess.run([str(args.replay_exe.resolve()), "--debug-walker-gravity-word-evidence", str(fixture)],
                                        cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and "walker gravity fixture bytes changed" in result.stderr and
                        "walker_gravity_word=ok" not in result.stdout, f"production accepted malformed case {index}")
        print("walker_gravity_replay_guard=ok positive=1 rejected=18 audio=dummy")
    else:
        print("walker_gravity_fixture=ok cases=32 bytes=486 word_wrap=2 landing=10 original_window=0x716e..0x71a4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
