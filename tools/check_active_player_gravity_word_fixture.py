#!/usr/bin/env python3
"""Validate original active airborne gravity bytes, recaptures and replay rejection."""
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
FIXTURE_SHA = "8a6d797055605ef34d8a16d89ba07cf65c4abb5236c90be97ee33e87b322cf5e"
EXE_SHA = "7579255148c2cb540b26f70dc8181c50b218b6808d8fa5208c832391bafa53ec"
VELOCITIES = (-32768, -32767, -65, -64, -1, 0, 1, 63, 1982, 1983, 1984, 2047, 2048, 32703, 32704, 32767)
RAW = bytes.fromhex("8346f240817ef2ff077e05c746f2ff07")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate(data: bytes, exe: bytes) -> None:
    require(len(data) == 448 and hashlib.sha256(data).hexdigest() == FIXTURE_SHA, "fixture extent/hash differs")
    require(data[:8] == b"LZAGv1\0\0" and struct.unpack_from("<HHHH", data, 8) == (32, 12, 0x6743, 0x6753), "fixture header differs")
    require(hashlib.sha256(exe).hexdigest() == EXE_SHA and data[16:48] == bytes.fromhex(EXE_SHA), "original executable differs")
    require(data[48:64] == RAW == exe[0x770 + 0x6743:0x770 + 0x6753], "original instruction window differs")
    rows = [struct.unpack_from("<BBhhhhBB", data, 64 + index * 12) for index in range(32)]
    require([(row[0], row[1], row[2], row[6], row[7]) for row in rows] ==
            [(index, 0, VELOCITIES[index % 16], 1 + index // 16, index // 16) for index in range(32)], "case coverage/order differs")
    require(all(row[4] == row[5] == 99 for row in rows) and
            sum(row[1] == 0 and row[2] >= 32704 and row[3] < 0 for row in rows) == 4, "airborne word-wrap coverage differs")


def rejected(data: bytes, exe: bytes) -> None:
    try:
        validate(data, exe)
    except ValueError:
        return
    raise AssertionError("malformed fixture accepted")


def validate_capture(directory: Path, data: bytes, producer: Path) -> None:
    capture = strict_json((directory / "capture.json").read_text(encoding="utf-8"))
    require(not (directory / "failure.json").exists() and capture["schema"] == "lezac-active-player-gravity-word-v1" and
            capture["complete"] is True and capture["case_count"] == len(capture["cases"]) == 32 and
            capture["kind_coverage"] == [0] and capture["player_coverage"] == [1, 2], "native capture is failed/incomplete")
    require(capture["producer_sha256"] == hashlib.sha256(producer.read_bytes()).hexdigest() and
            capture["audio_driver"] == "dummy" and capture["owned_child_returncode"] is not None and
            capture["hook_free_stack_preserved"] is True and capture["unseeded_bootstrap_ticks"] == 1 and
            capture["selected_actor_parameter_guard"] is True and capture["gravity_only_airborne"] is True and
            capture["observed_entry_exit"] == [0x6743, 0x6813] and
            capture["natural_campaign_claim"] is False and capture["original_fidelity_claim"] is False and
            capture["full_actor_update_parity_claim"] is False and capture["pixel_parity_claim"] is False,
            "native provenance/closure/scope differs")
    require(capture["instruction_window"] == [0x6743, 0x6753] and capture["instruction_window_hex"] == RAW.hex() and
            capture["instruction_windows_sha256"] == hashlib.sha256(RAW).hexdigest(), "native instruction window differs")
    require(capture["hooks"] == [[0x7EC5, "c70682200100"], [0x6743, "8346f240"], [0x6813, "a0841b"]], "native hook extent differs")
    for name, digest in capture["files"].items():
        require(hashlib.sha256(safe_file(directory, name).read_bytes()).hexdigest() == digest, "native file differs")
    require(len(capture["assets_sha256"]) == 11 and capture["assets_sha256"]["LEZAC.EXE"] == EXE_SHA, "native asset scope differs")
    for name, digest in capture["assets_sha256"].items():
        require(hashlib.sha256(safe_file(ROOT, name).read_bytes()).hexdigest() == digest, "source asset differs")
    for name, digest in (capture["support_dependencies_sha256"] | capture["dependency_sha256"]).items():
        require(hashlib.sha256(safe_file(ROOT / "tools", name).read_bytes()).hexdigest() == digest, "capture dependency differs")
    require(strict_json((directory / "restoration.json").read_text(encoding="utf-8")) ==
            {"hooks_restored": True, "scratch_restored": True, "child_retained_stopped": True, "installed_hooks": 3}, "restoration differs")
    bootstrap = bytes.fromhex(capture["bootstrap_players_hex"])
    require(len(bootstrap) == 76 and len(bytes.fromhex(capture["bootstrap_visuals_hex"])) == 16,
            "original two-player bootstrap extent differs")
    for slot in (0, 1):
        player = bootstrap[slot * 38:(slot + 1) * 38]
        require((player[0], player[1], player[0x14], player[0x15]) == (0, slot, 0, slot),
                "original two-player bootstrap roles differ")
    records = []
    allowed = {0x3A - 0x0E, 0x3A - 0x0D}
    for index, row in enumerate(capture["cases"]):
        before, after = row["before"], row["after"]
        player, bottom, vy = 1 + index // 16, 0, VELOCITIES[index % 16]
        actor_offset = 0x1B88 + (player - 1) * 38
        require(row["index"] == index and row["seed_kind"] == before["kind"] == after["kind"] == 0 and
                row["seed_player"] == player and row["actor_offset"] == actor_offset and
                row["seed_bottom"] == before["bottom"] == after["bottom"] == bottom and row["seed_vy"] == before["vy"] == vy and
                before["y"] == after["y"] == 99 and before["x"] == after["x"] == 336 and before["behavior"] == after["behavior"] == 0 and
                before["registers"] == after["registers"] and len(before["registers"]) == 6 and
                before["actor_pointer"] == after["actor_pointer"] == [actor_offset, before["registers"][1]],
                "native case inputs/registers/player pointer differ")
        seed = bytes.fromhex(row["seeded_actor_hex"])
        expected_seed = bytearray(bootstrap[(player - 1) * 38:player * 38])
        struct.pack_into("<hhhh", expected_seed, 6, 0, vy, 0, 0)
        require(seed == expected_seed, "declared player seed differs from preserved original bootstrap")
        old, new = bytes.fromhex(before["stack_hex"]), bytes.fromhex(after["stack_hex"])
        require(len(old) == len(new) == 0x3A and all(a == b for at, (a, b) in enumerate(zip(old, new)) if at not in allowed),
                "undeclared original local differs")
        records.append(struct.pack("<BBhhhhBB", index, bottom, vy, after["vy"], 99, after["y"], player, player - 1))
    require(b"".join(records) == data[64:], "complete native result does not reproduce pinned fixture")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=ROOT / "tests/fixtures/active_player_gravity_word_original.bin")
    parser.add_argument("--original-exe", type=Path, default=ROOT / "LEZAC.EXE")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--replay-exe", type=Path)
    parser.add_argument("--capture", type=Path)
    parser.add_argument("--producer-file", type=Path, default=ROOT / "tools/capture_original_active_player_gravity.py")
    args = parser.parse_args()
    data, exe = args.fixture.read_bytes(), args.original_exe.read_bytes()
    validate(data, exe)
    if args.capture:
        validate_capture(args.capture, data, args.producer_file)
        print("active_player_gravity_native_capture=ok cases=32 players=1,2 kind=0 fixture_byte_match=1 hooks_restored=1 child_closed=1 audio=dummy natural_route_claim=0")
    elif args.self_test:
        for index in range(len(data)):
            mutation = bytearray(data)
            mutation[index] ^= 1
            rejected(bytes(mutation), exe)
        rejected(data[:-1], exe)
        rejected(data + b"\0", exe)
        rejected(data, exe[:-1])
        print("active_player_gravity_fixture_selftest=ok cases=32 byte_mutations=448 truncated=1 trailing=1 original_mutation=1")
    elif args.replay_exe:
        environment = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
        command = [str(args.replay_exe.resolve()), "--debug-active-player-gravity-word-evidence"]
        positive = subprocess.run([*command, str(args.fixture.resolve())], cwd=ROOT, env=environment,
                                  capture_output=True, text=True, timeout=30)
        require(positive.returncode == 0 and "active_player_gravity_word=ok cases=32 helper_updates=32 caller_updates=32" in positive.stdout,
                "positive production replay did not pass")
        mutations = [data[:-1], data + b"\0"]
        for index in (0, 8, 12, 16, 48, 64, 65, 68, 74, 76, 232, 236, 256, 260, 446, 447):
            changed = bytearray(data)
            changed[index] ^= 1
            mutations.append(bytes(changed))
        with tempfile.TemporaryDirectory(prefix="lezac-active-player-gravity-guard-") as directory:
            for index, mutation in enumerate(mutations):
                fixture = Path(directory) / f"mutation-{index}.bin"
                fixture.write_bytes(mutation)
                result = subprocess.run([*command, str(fixture)], cwd=ROOT, env=environment,
                                        capture_output=True, text=True, timeout=10)
                require(result.returncode != 0 and "active player gravity fixture bytes changed" in result.stderr and
                        "active_player_gravity_word=ok" not in result.stdout, f"production accepted malformed case {index}")
        print("active_player_gravity_replay_guard=ok positive=1 rejected=18 audio=dummy")
    else:
        print("active_player_gravity_fixture=ok cases=32 bytes=448 players=1,2 kind=0 word_wrap=4 airborne_only=1 landing_claim=0 original_window=0x6743..0x6753")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
