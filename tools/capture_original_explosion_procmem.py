#!/usr/bin/env python3
"""Capture original LEZAC explosion bytes from a temporary DOSBox process.

This helper is intentionally guarded because it reads /proc/<pid>/mem from the
DOSBox child process it starts. Keep output directories outside the repository.
Candidate fixtures still need frame inspection before promotion.

When --freeze-ghidra-offset is used, the helper also patches only the temporary
copied executable with an infinite loop. That mode is instrumentation evidence,
not pristine original evidence.

When --runtime-freeze-after-* is used with --freeze-ghidra-offset, the helper
instead writes the freeze loop into the child DOSBox process after a route-state
gate. That mode requires a separate approval flag and is also instrumentation
evidence, not pristine original evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import glob
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ASSETS = [
    "LEZAC.EXE",
    "BOMPAL.PAL",
    "CARO.CAR",
    "FONTS.SPR",
    "GRAN.MST",
    "LIVELS.SCH",
    "PROEFS.SON",
    "PROVA.SPR",
    "RECS.DAT",
    "SFONLEF.ZBG",
    "BOMOMIMK.SPR",
    "ENGLISH.DOC",
    "ITALIANO.DOC",
]

ENTRY_SIGNATURE = bytes.fromhex(
    "9a00000d0b9a2d07990a9a0000370a9a11011a0a5589e5"
)
DATA_SIGNATURE = b"larax e zaco versione"
RUNTIME_CS = 0x01ED
RUNTIME_DS = 0x0C8F
ENTRY_IP = 0x7783
DATA_STRING_OFFSET = 0x008B
DEBRIS_BASE = 0x2093
DEBRIS_STRIDE = 0x0B
COLLAPSE_BASE = 0x6611
COLLAPSE_STRIDE = 0x0F
EFFECT_BASE = 0xC21E
EFFECT_STRIDE = 0x08
DEBRIS_DUMP_BASE = 0x2090
COLLAPSE_DUMP_BASE = 0x6610
DEBRIS_DUMP_LENGTH = COLLAPSE_DUMP_BASE - DEBRIS_DUMP_BASE
COLLAPSE_DUMP_LENGTH = 0x60
EFFECT_INPUT_DUMP_BASE = 0x78C0
EFFECT_INPUT_DUMP_LENGTH = 0x30
FREEZE_LOOP_PATCH = bytes.fromhex("ebfe")
FREEZE_PATCH_MODE_LOOP = "loop"
FREEZE_PATCH_MODE_BP4_CS_SCRATCH = "bp4-cs-scratch"
FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH = "lane-div-cs-scratch"
FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH = "lane-write-cs-scratch"
FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH = "lane-result-cs-scratch"
DEFAULT_SEEDED_DEBRIS_WORD = 0xC004
DEFAULT_SAMPLE_SCREENSHOTS = "0.5,1.0,1.5,2.0,3.0"
ROUTE_STATE_RANGES = [
    ("DS:0060", 0x0060, 0x80),
    ("DS:1B70", 0x1B70, 0x20),
    ("DS:2070", 0x2070, 0x60),
    ("DS:2090", DEBRIS_DUMP_BASE, DEBRIS_DUMP_LENGTH),
    ("DS:6610", COLLAPSE_DUMP_BASE, COLLAPSE_DUMP_LENGTH),
    ("DS:78C0", 0x78C0, 0x20),
    ("DS:7900", 0x7900, 0xE0),
    ("DS:7990", 0x7990, 0x40),
    ("DS:79E0", 0x79E0, 0x40),
    ("DS:7A00", 0x7A00, 0x80),
    ("DS:C1E0", 0xC1E0, 0x40),
    ("DS:C21E", 0xC21E, 0x40),
    ("DS:C320", 0xC320, 0x60),
]


SampleRecord = tuple[float, bytes, bytes, bytes, bytes, bytes, bytes]


@dataclass
class RouteStateRecord:
    label: str
    elapsed_after_bomb: float | None
    dumps: dict[str, bytes]


@dataclass(frozen=True)
class RouteStep:
    key: str
    seconds: float


def run(args: list[str], env: dict[str, str], check: bool = True) -> str:
    completed = subprocess.run(
        args,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(args)}\n"
            f"{completed.stdout}"
        )
    return completed.stdout


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"missing required command: {name}")


def copy_assets(asset_dir: Path, run_dir: Path) -> None:
    for name in ASSETS:
        src = asset_dir / name
        if src.exists():
            shutil.copy2(src, run_dir / name)
    if not (run_dir / "LEZAC.EXE").exists():
        raise RuntimeError(f"missing {asset_dir / 'LEZAC.EXE'}")


def parse_ghidra_offset(value: str) -> int:
    text = value.strip().lower()
    if ":" in text:
        segment, text = text.split(":", 1)
        if segment not in {"1000", "0x1000"}:
            raise ValueError(f"freeze offset must use Ghidra segment 1000, got {segment}")
    if text.startswith("0x"):
        text = text[2:]
    if not text or len(text) > 4:
        raise ValueError(f"bad Ghidra offset: {value}")
    return int(text, 16)


def near_jump(from_offset: int, to_offset: int) -> bytes:
    delta = (to_offset - ((from_offset + 3) & 0xFFFF)) & 0xFFFF
    return bytes([0xE9, delta & 0xFF, delta >> 8])


def near_call(from_offset: int, to_offset: int) -> bytes:
    delta = (to_offset - ((from_offset + 3) & 0xFFFF)) & 0xFFFF
    return bytes([0xE8, delta & 0xFF, delta >> 8])


def build_freeze_patch(
    patch_mode: str, ghidra_offset: int
) -> tuple[bytes, int | None, int, int | None, bytes]:
    if patch_mode == FREEZE_PATCH_MODE_LOOP:
        return FREEZE_LOOP_PATCH, None, 0, None, b""
    if patch_mode == FREEZE_PATCH_MODE_BP4_CS_SCRATCH:
        if ghidra_offset != 0x4C75:
            raise RuntimeError("--freeze-patch-mode bp4-cs-scratch is only valid at 1000:4C75")
        scratch_offset = (ghidra_offset + 9) & 0xFFFF
        # 8B46FC: mov ax,[bp-4]
        # 2EA3xxxx: mov cs:[scratch],ax
        # EBFE: jmp $
        patch = bytes(
            [
                0x8B,
                0x46,
                0xFC,
                0x2E,
                0xA3,
                scratch_offset & 0xFF,
                scratch_offset >> 8,
                0xEB,
                0xFE,
            ]
        )
        return patch, scratch_offset, 2, None, b""
    if patch_mode == FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH:
        if ghidra_offset not in {0x3CD4, 0x3CE3, 0x3E68, 0x3E77}:
            raise RuntimeError(
                "--freeze-patch-mode lane-div-cs-scratch is only valid at "
                "1000:3CD4, 1000:3CE3, 1000:3E68, or 1000:3E77"
            )
        scratch_offset = (ghidra_offset + 0x50) & 0xFFFF

        def mov_cs_reg(opcode: int, offset: int) -> list[int]:
            return [0x2E, 0x89, opcode, offset & 0xFF, offset >> 8]

        def mov_ax_to_cs(offset: int) -> list[int]:
            return [0x2E, 0xA3, offset & 0xFF, offset >> 8]

        patch_bytes: list[int] = []
        if ghidra_offset in {0x3CE3, 0x3E77}:
            # At 1000:3CE3/3E77, the lane helper has already loaded:
            #   DX:AX = signed numerator, BX:CX = positive divisor/weight sum.
            patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x00))
            patch_bytes.extend(mov_cs_reg(0x16, scratch_offset + 0x02))  # DX
            patch_bytes.extend(mov_cs_reg(0x0E, scratch_offset + 0x04))  # CX
            patch_bytes.extend(mov_cs_reg(0x1E, scratch_offset + 0x06))  # BX
        else:
            # At 1000:3CD4/3E68, the same numerator/weight locals are ready but
            # the register setup has not run yet. Store the would-be register
            # values; this mode is runtime-only because the larger body can
            # overlap relocated far-call words in the DOS-loaded image.
            for local_offset, scratch_delta in [
                (0xFC, 0x00),  # would-be AX: numerator low.
                (0xFE, 0x02),  # would-be DX: numerator high.
                (0xF8, 0x04),  # would-be CX: denominator/weight sum.
            ]:
                patch_bytes.extend([0x8B, 0x46, local_offset])
                patch_bytes.extend(mov_ax_to_cs(scratch_offset + scratch_delta))
            patch_bytes.extend([0x31, 0xC0])  # would-be BX high word is zero.
            patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x06))
        for local_offset, scratch_delta in [
            (0xF0, 0x08),  # [BP-10] active count cached before the writeback loop.
            (0xF6, 0x0A),  # [BP-0A] final staging loop index.
            (0xF8, 0x0C),  # [BP-08] denominator/weight sum local.
            (0xFC, 0x0E),  # [BP-04] numerator low local.
            (0xFE, 0x10),  # [BP-02] numerator high local.
        ]:
            patch_bytes.extend([0x8B, 0x46, local_offset])
            patch_bytes.extend(mov_ax_to_cs(scratch_offset + scratch_delta))
        patch_bytes.extend([0xEB, 0xFE])
        return bytes(patch_bytes), scratch_offset, 0x12, None, b""
    if patch_mode == FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH:
        if ghidra_offset not in {0x3D1B, 0x3D2D, 0x3EAF, 0x3EC1}:
            raise RuntimeError(
                "--freeze-patch-mode lane-write-cs-scratch is only valid at "
                "1000:3D1B, 1000:3D2D, 1000:3EAF, or 1000:3EC1"
            )
        body_offset = 0xF000
        scratch_offset = 0xF080

        def mov_ax_to_cs(offset: int) -> list[int]:
            return [0x2E, 0xA3, offset & 0xFF, offset >> 8]

        def mov_cs_reg(opcode: int, offset: int) -> list[int]:
            return [0x2E, 0x89, opcode, offset & 0xFF, offset >> 8]

        patch_bytes = []
        if ghidra_offset in {0x3D1B, 0x3EAF}:
            patch_bytes.extend([0x30, 0xE4])  # AL holds the lane byte.
        else:
            patch_bytes.extend([0x88, 0xD0, 0x30, 0xE4])  # DL holds the lane byte.
        patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x00))
        patch_bytes.extend(mov_cs_reg(0x3E, scratch_offset + 0x02))  # DI write offset.
        for local_offset, scratch_delta in [
            (0xF8, 0x04),  # [BP-08] selected tag.
            (0xF0, 0x06),  # [BP-10] active count.
            (0xF6, 0x08),  # [BP-0A] writeback loop index.
        ]:
            patch_bytes.extend([0x8B, 0x46, local_offset])
            patch_bytes.extend(mov_ax_to_cs(scratch_offset + scratch_delta))
        patch_bytes.extend([0x8A, 0x46, 0xF3, 0x30, 0xE4])
        patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x0A))
        patch_bytes.extend([0xEB, 0xFE])
        return near_jump(ghidra_offset, body_offset), scratch_offset, 0x0C, body_offset, bytes(patch_bytes)
    if patch_mode == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH:
        if ghidra_offset not in {0x3D3F, 0x3ED3}:
            raise RuntimeError(
                "--freeze-patch-mode lane-result-cs-scratch is only valid at "
                "1000:3D3F or 1000:3ED3"
            )
        body_offset = 0xF200
        scratch_offset = 0xF280

        def mov_ax_to_cs(offset: int) -> list[int]:
            return [0x2E, 0xA3, offset & 0xFF, offset >> 8]

        def mov_cs_reg(opcode: int, offset: int) -> list[int]:
            return [0x2E, 0x89, opcode, offset & 0xFF, offset >> 8]

        patch_bytes = []
        patch_bytes.extend([0x30, 0xE4])  # AL holds the helper result byte.
        patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x00))
        patch_bytes.extend([0x8C, 0xC0])  # mov ax,es
        patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x02))
        patch_bytes.extend(mov_cs_reg(0x3E, scratch_offset + 0x04))  # DI
        for local_offset, scratch_delta in [
            (0x04, 0x06),  # [BP+4] far pointer offset.
            (0x06, 0x08),  # [BP+6] far pointer segment.
        ]:
            patch_bytes.extend([0x8B, 0x46, local_offset])
            patch_bytes.extend(mov_ax_to_cs(scratch_offset + scratch_delta))
        patch_bytes.extend([0x8A, 0x46, 0xF3, 0x30, 0xE4])
        patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x0A))
        for local_offset, scratch_delta in [
            (0xF0, 0x0C),  # [BP-10] active count.
            (0xF6, 0x0E),  # [BP-0A] writeback loop index.
        ]:
            patch_bytes.extend([0x8B, 0x46, local_offset])
            patch_bytes.extend(mov_ax_to_cs(scratch_offset + scratch_delta))
        patch_bytes.extend([0x26, 0x8A, 0x05, 0x30, 0xE4])  # mov al,es:[di]
        patch_bytes.extend(mov_ax_to_cs(scratch_offset + 0x10))
        patch_bytes.extend([0xEB, 0xFE])
        return near_jump(ghidra_offset, body_offset), scratch_offset, 0x12, body_offset, bytes(patch_bytes)
    raise RuntimeError(f"unsupported freeze patch mode: {patch_mode}")


def expected_freeze_original_bytes(
    patch_mode: str, ghidra_offset: int
) -> bytes | None:
    if (
        patch_mode == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH
        and ghidra_offset in {0x3D3F, 0x3ED3}
    ):
        return bytes([0x26, 0x88, 0x05])  # mov es:[di],al
    return None


def require_expected_freeze_original_bytes(
    patch_mode: str, ghidra_offset: int, original: bytes
) -> None:
    expected = expected_freeze_original_bytes(patch_mode, ghidra_offset)
    if expected is None:
        return
    actual = original[: len(expected)]
    if actual != expected:
        raise RuntimeError(
            f"freeze original bytes mismatch at 1000:{ghidra_offset:04X}: "
            f"expected {expected.hex()} actual {actual.hex()}"
        )


def patch_freeze(
    run_dir: Path, ghidra_offset: int, patch_mode: str
) -> dict[str, int | str]:
    exe = run_dir / "LEZAC.EXE"
    data = bytearray(exe.read_bytes())
    if data[:2] != b"MZ":
        raise RuntimeError(f"{exe} is not an MZ executable")
    header_paragraphs = data[8] | (data[9] << 8)
    image_base = header_paragraphs * 16
    patch, scratch_offset, scratch_length, body_offset, body_patch = build_freeze_patch(
        patch_mode, ghidra_offset
    )
    file_offset = image_base + ghidra_offset
    if file_offset < image_base or file_offset + len(patch) > len(data):
        raise RuntimeError(
            f"freeze offset 1000:{ghidra_offset:04X} maps outside {exe}"
        )
    if scratch_offset is not None:
        scratch_file_offset = image_base + scratch_offset
        if (
            scratch_file_offset < image_base
            or scratch_file_offset + scratch_length > len(data)
        ):
            scratch_file_offset = -1
    if body_offset is not None:
        body_file_offset = image_base + body_offset
        if (
            body_file_offset < image_base
            or body_file_offset + len(body_patch) > len(data)
        ):
            raise RuntimeError(
                f"body offset 1000:{body_offset:04X} maps outside {exe}"
            )
    original = bytes(data[file_offset : file_offset + len(patch)])
    scratch_original = (
        bytes(
            data[
                scratch_file_offset :
                scratch_file_offset + scratch_length
            ]
        )
        if scratch_offset is not None and scratch_file_offset >= 0
        else b""
    )
    body_original = (
        bytes(data[body_file_offset : body_file_offset + len(body_patch)])
        if body_offset is not None
        else b""
    )
    require_expected_freeze_original_bytes(patch_mode, ghidra_offset, original)
    data[file_offset : file_offset + len(patch)] = patch
    if body_offset is not None:
        data[body_file_offset : body_file_offset + len(body_patch)] = body_patch
    exe.write_bytes(data)
    return {
        "ghidra_offset": ghidra_offset,
        "image_base": image_base,
        "file_offset": file_offset,
        "expected_original_bytes": (
            expected_freeze_original_bytes(patch_mode, ghidra_offset) or b""
        ).hex(),
        "original_bytes": original.hex(),
        "patch_bytes": patch.hex(),
        "patch_mode": patch_mode,
        "patch_length": len(patch),
        "scratch_length": scratch_length,
        "scratch_offset": scratch_offset if scratch_offset is not None else 0,
        "scratch_original_bytes": scratch_original.hex(),
        "body_offset": body_offset if body_offset is not None else 0,
        "body_patch_bytes": body_patch.hex(),
        "body_original_bytes": body_original.hex(),
        "body_length": len(body_patch),
    }


def describe_freeze_patch(
    run_dir: Path, ghidra_offset: int, patch_mode: str
) -> dict[str, int | str]:
    exe = run_dir / "LEZAC.EXE"
    data = exe.read_bytes()
    if data[:2] != b"MZ":
        raise RuntimeError(f"{exe} is not an MZ executable")
    header_paragraphs = data[8] | (data[9] << 8)
    image_base = header_paragraphs * 16
    patch, scratch_offset, scratch_length, body_offset, body_patch = build_freeze_patch(
        patch_mode, ghidra_offset
    )
    file_offset = image_base + ghidra_offset
    if file_offset < image_base or file_offset + len(patch) > len(data):
        raise RuntimeError(
            f"freeze offset 1000:{ghidra_offset:04X} maps outside {exe}"
        )
    if scratch_offset is not None:
        scratch_file_offset = image_base + scratch_offset
        if (
            scratch_file_offset < image_base
            or scratch_file_offset + scratch_length > len(data)
        ):
            scratch_file_offset = -1
    original = data[file_offset : file_offset + len(patch)]
    require_expected_freeze_original_bytes(patch_mode, ghidra_offset, original)
    scratch_original = (
        data[
            scratch_file_offset :
            scratch_file_offset + scratch_length
        ]
        if scratch_offset is not None and scratch_file_offset >= 0
        else b""
    )
    if body_offset is not None:
        body_file_offset = image_base + body_offset
        body_original = (
            data[body_file_offset : body_file_offset + len(body_patch)]
            if image_base <= body_file_offset
            and body_file_offset + len(body_patch) <= len(data)
            else b""
        )
    else:
        body_original = b""
    return {
        "ghidra_offset": ghidra_offset,
        "image_base": image_base,
        "file_offset": file_offset,
        "expected_original_bytes": (
            expected_freeze_original_bytes(patch_mode, ghidra_offset) or b""
        ).hex(),
        "original_bytes": original.hex(),
        "patch_bytes": patch.hex(),
        "patch_mode": patch_mode,
        "patch_length": len(patch),
        "scratch_length": scratch_length,
        "scratch_offset": scratch_offset if scratch_offset is not None else 0,
        "scratch_original_bytes": scratch_original.hex(),
        "body_offset": body_offset if body_offset is not None else 0,
        "body_patch_bytes": body_patch.hex(),
        "body_original_bytes": body_original.hex(),
        "body_length": len(body_patch),
    }


def build_runtime_seed_debris_writeback_patch(
    freeze_ghidra_offset: int, seed_word: int
) -> dict[str, int | str]:
    if freeze_ghidra_offset in {0x3D2D, 0x3D3F}:
        call_site = 0x4C96
        helper_target = 0x3BB2
        return_offset = 0x4C99
        body_offset = 0xF120
        direction = "forward"
    elif freeze_ghidra_offset in {0x3EC1, 0x3ED3}:
        call_site = 0x4CA9
        helper_target = 0x3D46
        return_offset = 0x4CAC
        body_offset = 0xF160
        direction = "reverse"
    else:
        raise RuntimeError(
            "--runtime-seed-debris-writeback is only valid with "
            "--freeze-ghidra-offset 1000:3D2D, 1000:3D3F, 1000:3EC1, "
            "or 1000:3ED3"
        )
    body = bytes(
        [
            0xC7,
            0x06,
            0x5E,
            0x65,
            seed_word & 0xFF,
            seed_word >> 8,
        ]
    )
    body += near_call(body_offset + len(body), helper_target)
    body += near_jump(body_offset + len(body), return_offset)
    return {
        "kind": "debris-writeback",
        "direction": direction,
        "call_site": call_site,
        "helper_target": helper_target,
        "return_offset": return_offset,
        "body_offset": body_offset,
        "entry_patch_bytes": near_jump(call_site, body_offset).hex(),
        "body_patch_bytes": body.hex(),
        "seed_word": seed_word,
    }


def write_conf(path: Path, capture_dir: Path) -> None:
    path.write_text(
        "[sdl]\n"
        "fullscreen=false\n"
        "fulldouble=false\n"
        "output=surface\n\n"
        "[dosbox]\n"
        f"captures={capture_dir}\n\n"
        "[render]\n"
        "frameskip=0\n"
        "aspect=false\n"
        "scaler=none\n\n"
        "[cpu]\n"
        "cycles=fixed 6000\n",
        encoding="ascii",
    )


def scan_process(pid: int, pattern: bytes) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    maps = Path(f"/proc/{pid}/maps").read_text(encoding="utf-8").splitlines()
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        for line in maps:
            parts = line.split()
            if len(parts) < 2 or "r" not in parts[1]:
                continue
            start_text, end_text = parts[0].split("-")
            start = int(start_text, 16)
            end = int(end_text, 16)
            size = end - start
            if size <= 0 or size > 64 * 1024 * 1024:
                continue
            try:
                mem.seek(start)
                data = mem.read(size)
            except OSError:
                continue
            index = data.find(pattern)
            while index >= 0:
                found.append((start + index, line))
                index = data.find(pattern, index + 1)
    return found


def find_debug_pid(run_dir: Path) -> int:
    output = subprocess.check_output(["pgrep", "-a", "dosbox-debug"], text=True)
    candidates = [
        int(line.split()[0])
        for line in output.splitlines()
        if str(run_dir) in line
    ]
    if not candidates:
        raise RuntimeError("could not find dosbox-debug child for run directory")
    return candidates[-1]


def format_dump(segment: int, offset: int, data: bytes) -> str:
    lines = []
    for index in range(0, len(data), 16):
        chunk = data[index : index + 16]
        bytes_text = " ".join(f"{value:02x}" for value in chunk)
        lines.append(f"{segment:04X}:{offset + index:04X}  {bytes_text}")
    return "\n".join(lines)


def activate_window(env: dict[str, str], window: str) -> None:
    run(["xdotool", "windowactivate", "--sync", window], env, check=False)
    time.sleep(0.12)


def key(env: dict[str, str], window: str, name: str) -> None:
    activate_window(env, window)
    run(["xdotool", "key", "--clearmodifiers", name], env, check=False)
    time.sleep(0.2)


def hold_key(env: dict[str, str], window: str, name: str, seconds: float) -> None:
    activate_window(env, window)
    run(["xdotool", "keydown", name], env, check=False)
    time.sleep(seconds)
    run(["xdotool", "keyup", name], env, check=False)
    time.sleep(0.15)


def held_tap(env: dict[str, str], window: str, name: str, seconds: float) -> None:
    activate_window(env, window)
    run(["xdotool", "keydown", name], env, check=False)
    time.sleep(seconds)
    run(["xdotool", "keyup", name], env, check=False)
    time.sleep(0.2)


def snapshot(env: dict[str, str], out_dir: Path, window: str, label: str) -> None:
    before = set(glob.glob(str(out_dir / "*.png")))
    activate_window(env, window)
    run(["xdotool", "key", "--clearmodifiers", "ctrl+F5"], env, check=False)
    time.sleep(0.3)
    new_files = sorted(set(glob.glob(str(out_dir / "*.png"))) - before)
    if new_files:
        Path(new_files[-1]).rename(out_dir / f"{label}.png")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_emulated(pid: int, base: int, segment: int, offset: int, length: int) -> bytes:
    host = base + ((segment << 4) + offset)
    with open(f"/proc/{pid}/mem", "rb", buffering=0) as mem:
        mem.seek(host)
        return mem.read(length)


def write_emulated(
    pid: int, base: int, segment: int, offset: int, patch: bytes
) -> bytes:
    host = base + ((segment << 4) + offset)
    with open(f"/proc/{pid}/mem", "r+b", buffering=0) as mem:
        mem.seek(host)
        original = mem.read(len(patch))
        mem.seek(host)
        mem.write(patch)
        mem.flush()
    return original


def capture_route_state(
    pid: int, base: int, label: str, elapsed_after_bomb: float | None
) -> RouteStateRecord:
    return RouteStateRecord(
        label=label,
        elapsed_after_bomb=elapsed_after_bomb,
        dumps={
            name: read_emulated(pid, base, RUNTIME_DS, offset, length)
            for name, offset, length in ROUTE_STATE_RANGES
        },
    )


def route_bytes(record: RouteStateRecord, offset: int, length: int) -> bytes:
    for name, start, _ in ROUTE_STATE_RANGES:
        data = record.dumps[name]
        if start <= offset and offset + length <= start + len(data):
            return data[offset - start : offset - start + length]
    raise KeyError(f"route state did not capture DS:{offset:04X}..{offset + length:04X}")


def route_u8(record: RouteStateRecord, offset: int) -> int:
    return route_bytes(record, offset, 1)[0]


def route_u16(record: RouteStateRecord, offset: int) -> int:
    return le16(route_bytes(record, offset, 2), 0)


def route_state_fields(record: RouteStateRecord) -> dict[str, int | str | float | None]:
    decoded = decode_sample(
        (
            record.elapsed_after_bomb or 0.0,
            record.dumps["DS:2070"],
            record.dumps["DS:2090"],
            record.dumps["DS:6610"],
            record.dumps["DS:C1E0"],
            record.dumps["DS:C21E"],
            record.dumps["DS:78C0"],
        )
    )
    return {
        "label": record.label,
        "elapsed_after_bomb": record.elapsed_after_bomb,
        "p1_input_gate_1b7b": route_u8(record, 0x1B7B),
        "p2_input_gate_1b80": route_u8(record, 0x1B80),
        "action_gate_79a3": route_u8(record, 0x79A3),
        "active_players_79b8": route_u8(record, 0x79B8),
        "fallback_79b9": route_u8(record, 0x79B9),
        "sound_cursor_2074": route_u16(record, 0x2074),
        "sound_current_78c0": route_u16(record, 0x78C0),
        "sound_active_79c4": route_u8(record, 0x79C4),
        "sound_pending_priority_799f": route_u8(record, 0x799F),
        "p1_state_79e5": route_u8(record, 0x79E5),
        "p2_state_79e6": route_u8(record, 0x79E6),
        "p1_damage_79e8": route_u8(record, 0x79E8),
        "p2_damage_79e9": route_u8(record, 0x79E9),
        "p1_life_counter_79ea": route_u8(record, 0x79EA),
        "p2_life_counter_79eb": route_u8(record, 0x79EB),
        "input_nonzero": nonzero_count(record.dumps["DS:1B70"]),
        "player_state_nonzero": nonzero_count(record.dumps["DS:79E0"]),
        "debris_nonzero": nonzero_count(record.dumps["DS:2090"]),
        "collapse_nonzero": nonzero_count(record.dumps["DS:6610"]),
        "effect_nonzero": nonzero_count(record.dumps["DS:C21E"]),
        "frame_table_nonzero": nonzero_count(record.dumps["DS:C320"]),
        "queue_score": sample_score(
            (
                record.elapsed_after_bomb or 0.0,
                record.dumps["DS:2070"],
                record.dumps["DS:2090"],
                record.dumps["DS:6610"],
                record.dumps["DS:C1E0"],
                record.dumps["DS:C21E"],
                record.dumps["DS:78C0"],
            )
        ),
        "debris_queue_count": decoded["debris_queue_count"],
        "collapse_queue_count": decoded["collapse_queue_count"],
        "selected_debris_base": decoded["selected_debris_base"],
        "selected_collapse_base": decoded["selected_collapse_base"],
        "selected_effect_base": decoded["selected_effect_base"],
        "selected_debris_source": decoded["selected_debris_source"],
        "selected_collapse_source": decoded["selected_collapse_source"],
        "high_debris_target_delta": decoded["high_debris_target_delta"],
        "high_debris_target_offset": decoded["high_debris_target_offset"],
        "high_debris_lookup_segment": decoded["high_debris_lookup_segment"],
        "high_debris_word_layer_offset": decoded["high_debris_word_layer_offset"],
        "high_debris_word_layer_segment": decoded["high_debris_word_layer_segment"],
        "high_debris_word_layer_address": decoded["high_debris_word_layer_address"],
        "high_debris_c204": decoded["high_debris_c204"],
        "debris_tile_index": decoded["debris_tile_index"],
        "collapse_word": decoded["collapse_word"],
        "effect_sprite": decoded["effect_sprite"],
    }


def write_route_state_samples(
    tsv_path: Path, dump_path: Path, records: list[RouteStateRecord]
) -> None:
    fields = [
        "label",
        "elapsed_after_bomb",
        "p1_input_gate_1b7b",
        "p2_input_gate_1b80",
        "action_gate_79a3",
        "active_players_79b8",
        "fallback_79b9",
        "sound_cursor_2074",
        "sound_current_78c0",
        "sound_active_79c4",
        "sound_pending_priority_799f",
        "p1_state_79e5",
        "p2_state_79e6",
        "p1_damage_79e8",
        "p2_damage_79e9",
        "p1_life_counter_79ea",
        "p2_life_counter_79eb",
        "input_nonzero",
        "player_state_nonzero",
        "debris_nonzero",
        "collapse_nonzero",
        "effect_nonzero",
        "frame_table_nonzero",
        "queue_score",
        "debris_queue_count",
        "collapse_queue_count",
        "selected_debris_base",
        "selected_collapse_base",
        "selected_effect_base",
        "selected_debris_source",
        "selected_collapse_source",
        "high_debris_target_delta",
        "high_debris_target_offset",
        "high_debris_lookup_segment",
        "high_debris_word_layer_offset",
        "high_debris_word_layer_segment",
        "high_debris_word_layer_address",
        "high_debris_c204",
        "debris_tile_index",
        "collapse_word",
        "effect_sprite",
    ]
    with tsv_path.open("w", encoding="ascii") as out:
        out.write("\t".join(fields) + "\n")
        for record in records:
            decoded = route_state_fields(record)
            values: list[str] = []
            for field in fields:
                value = decoded[field]
                if value is None:
                    values.append("")
                elif field == "label":
                    values.append(str(value))
                elif field == "elapsed_after_bomb":
                    values.append(f"{float(value):.3f}")
                elif isinstance(value, str):
                    values.append(value)
                else:
                    values.append(f"0x{int(value):04x}")
            out.write("\t".join(values) + "\n")

    with dump_path.open("w", encoding="ascii") as out:
        out.write("# LEZAC original process-memory route-state dumps.\n")
        out.write("# Captured from the temp DOSBox child; raw bytes are evidence, labels are route checkpoints.\n")
        for record in records:
            elapsed = (
                ""
                if record.elapsed_after_bomb is None
                else f" elapsed_after_bomb={record.elapsed_after_bomb:.3f}"
            )
            out.write(f"\n# route_state label={record.label}{elapsed}\n")
            for name, offset, _ in ROUTE_STATE_RANGES:
                out.write(f"\ndump {name}\n")
                out.write(format_dump(RUNTIME_DS, offset, record.dumps[name]) + "\n")


def parse_time_list(value: str) -> list[float]:
    if not value:
        return []
    times: list[float] = []
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        parsed = float(item)
        if parsed < 0:
            raise ValueError("sample screenshot times must be non-negative")
        times.append(parsed)
    return sorted(set(times))


def parse_route_step(value: str) -> RouteStep:
    if ":" not in value:
        raise argparse.ArgumentTypeError("route step must be KEY:SECONDS")
    key_name, seconds_text = value.split(":", 1)
    key_name = key_name.strip()
    if not key_name:
        raise argparse.ArgumentTypeError("route step key must not be empty")
    try:
        seconds = float(seconds_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"route step seconds must be numeric: {seconds_text}"
        ) from exc
    if seconds < 0:
        raise argparse.ArgumentTypeError("route step seconds must be non-negative")
    return RouteStep(key=key_name, seconds=seconds)


def route_steps_text(steps: list[RouteStep]) -> str:
    return ",".join(f"{step.key}:{step.seconds:.2f}" for step in steps)


def route_step_label(step: RouteStep, index: int) -> str:
    key_text = "".join(ch if ch.isalnum() else "_" for ch in step.key.lower())
    key_text = key_text.strip("_") or "key"
    return f"020_route_step_{index:02d}_{key_text}"


def parse_int_auto(value: str) -> int:
    try:
        return int(value, 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected integer, got {value}") from exc


def optional_int_text(value: int | None) -> str:
    return "" if value is None else str(value)


def optional_hex_text(value: int | None) -> str:
    return "" if value is None else f"0x{value:04x}"


def apply_runtime_freeze_preset(args: argparse.Namespace) -> None:
    if args.runtime_freeze_preset != "late-collapse":
        return
    if args.runtime_freeze_min_queue_score is None:
        args.runtime_freeze_min_queue_score = 100
    if args.runtime_freeze_min_debris_nonzero is None:
        args.runtime_freeze_min_debris_nonzero = 10
    if args.runtime_freeze_min_collapse_nonzero is None:
        args.runtime_freeze_min_collapse_nonzero = 18
    if args.runtime_freeze_min_effect_nonzero is None:
        args.runtime_freeze_min_effect_nonzero = 20
    if args.sample_screenshot_seconds == DEFAULT_SAMPLE_SCREENSHOTS:
        args.sample_screenshot_seconds = ""


def le16(data: bytes, index: int) -> int:
    if index + 1 >= len(data):
        return 0
    return data[index] | (data[index + 1] << 8)


def i16(value: int) -> int:
    value &= 0xFFFF
    return value - 0x10000 if value & 0x8000 else value


def nonzero_count(data: bytes) -> int:
    return sum(1 for value in data if value != 0)


def debris_slot_fields(dump2090: bytes, slot: int) -> dict[str, int]:
    index = (DEBRIS_BASE - DEBRIS_DUMP_BASE) + slot * DEBRIS_STRIDE
    return {
        "slot": slot,
        "addr": DEBRIS_BASE + slot * DEBRIS_STRIDE,
        "tile_index": le16(dump2090, index),
        "flagged": le16(dump2090, index + 2),
        "forward": dump2090[index + 4] if index + 4 < len(dump2090) else 0,
        "reverse": dump2090[index + 5] if index + 5 < len(dump2090) else 0,
        "lookup": dump2090[index + 9] if index + 9 < len(dump2090) else 0,
    }


def collapse_slot_fields(dump6610: bytes, slot: int) -> dict[str, int]:
    index = (COLLAPSE_BASE - COLLAPSE_DUMP_BASE) + slot * COLLAPSE_STRIDE
    flagged = le16(dump6610, index + 4)
    affected = dump6610[index + 0x0E] if index + 0x0E < len(dump6610) else 0
    return {
        "slot": slot,
        "addr": COLLAPSE_BASE + slot * COLLAPSE_STRIDE,
        "start": le16(dump6610, index),
        "end": le16(dump6610, index + 2),
        "word": flagged & 0x7FFF,
        "flagged": flagged,
        "forward": dump6610[index + 6] if index + 6 < len(dump6610) else 0,
        "reverse": dump6610[index + 7] if index + 7 < len(dump6610) else 0,
        "lane8": dump6610[index + 8] if index + 8 < len(dump6610) else 0,
        "lane9": dump6610[index + 9] if index + 9 < len(dump6610) else 0,
        "magnitude": le16(dump6610, index + 0x0A),
        "affected": affected,
        "count": affected // 2,
    }


def effect_slot_fields(dumpc21e: bytes, slot: int) -> dict[str, int]:
    index = slot * EFFECT_STRIDE
    return {
        "slot": slot,
        "addr": EFFECT_BASE + slot * EFFECT_STRIDE,
        "x": le16(dumpc21e, index),
        "y": le16(dumpc21e, index + 2),
        "sprite": dumpc21e[index + 4] if index + 4 < len(dumpc21e) else 0,
        "detail": dumpc21e[index + 5] if index + 5 < len(dumpc21e) else 0,
        "timer": dumpc21e[index + 6] if index + 6 < len(dumpc21e) else 0,
        "variant": dumpc21e[index + 7] if index + 7 < len(dumpc21e) else 0,
    }


def debris_slot_score(fields: dict[str, int]) -> int:
    score = 0
    if 0 < fields["tile_index"] < 0x4000 and (fields["flagged"] & 0x8000):
        score += 30
    if fields["forward"] or fields["reverse"]:
        score += 10
    if fields["lookup"]:
        score += 10
    return score


def collapse_slot_score(fields: dict[str, int]) -> int:
    score = 0
    if 0 < fields["start"] <= fields["end"] < 0x4000:
        score += 35
    if 0 < fields["count"] <= 16:
        score += 20
    if 0 < fields["word"] < 0x4000:
        score += 20
    if fields["word"] == 0x0009:
        score += 40
    if fields["flagged"] & 0x8000:
        score += 15
    if fields["forward"] or fields["reverse"]:
        score += 10
    return score


def effect_slot_score(fields: dict[str, int]) -> int:
    score = 0
    if 0x84 <= fields["sprite"] <= 0x89:
        score += 50
    if fields["detail"] == 0x75:
        score += 30
    if fields["timer"] or fields["variant"]:
        score += 10
    return score


def best_scored_slot(
    values: list[dict[str, int]], scorer
) -> tuple[dict[str, int], int]:
    best = max(values, key=scorer)
    return best, scorer(best)


def slot_is_covered(base: int, dump: bytes, addr: int, stride: int) -> bool:
    return base <= addr and addr + stride <= base + len(dump)


def candidate_slots(
    first_slots: int, count: int, record_base: int, dump_base: int, dump: bytes, stride: int
) -> list[int]:
    slots = list(range(first_slots))
    addr = record_base + count * stride
    if count > 0 and slot_is_covered(dump_base, dump, addr, stride):
        slots.append(count)
    return sorted(set(slots))


def choose_slot(
    values: list[dict[str, int]], count: int, scorer
) -> tuple[dict[str, int], int, str]:
    best, best_score = best_scored_slot(values, scorer)
    if count > 0:
        for fields in values:
            if fields["slot"] == count:
                score = scorer(fields)
                if score > 0:
                    return fields, score, "count"
                break
    return best, best_score, "score"


def high_debris_target_static_fields(record: SampleRecord) -> dict[str, int]:
    _, dump2070, dump2090, dump6610, dumpc1e0, _, _ = record
    debris_queue_count = le16(dump2070, 0x207E - 0x2070)
    debris_slots = candidate_slots(
        4,
        debris_queue_count,
        DEBRIS_BASE,
        DEBRIS_DUMP_BASE,
        dump2090,
        DEBRIS_STRIDE,
    )
    debris, _, _ = choose_slot(
        [debris_slot_fields(dump2090, slot) for slot in debris_slots],
        debris_queue_count,
        debris_slot_score,
    )
    target_delta = le16(dump2090, 0)
    target_offset = (debris["tile_index"] + i16(target_delta)) & 0xFFFF
    word_layer_offset = le16(dump6610, 0x6612 - 0x6610)
    return {
        "high_debris_target_delta": target_delta,
        "high_debris_target_offset": target_offset,
        "high_debris_lookup_segment": le16(dumpc1e0, 0xC1FE - 0xC1E0),
        "high_debris_word_layer_offset": word_layer_offset,
        "high_debris_word_layer_segment": le16(dump6610, 0x6614 - 0x6610),
        "high_debris_word_layer_address": (word_layer_offset + target_offset * 2) & 0xFFFF,
        "high_debris_c204": le16(dumpc1e0, 0xC204 - 0xC1E0),
    }


def resolve_high_debris_target(
    pid: int, base: int, record: SampleRecord
) -> dict[str, int]:
    fields = high_debris_target_static_fields(record)
    target_offset = fields["high_debris_target_offset"]
    lookup_segment = fields["high_debris_lookup_segment"]
    word_layer_segment = fields["high_debris_word_layer_segment"]
    fields["high_debris_target_byte"] = read_emulated(
        pid, base, lookup_segment, target_offset, 1
    )[0]
    word_offset = fields["high_debris_word_layer_address"]
    word_bytes = read_emulated(pid, base, word_layer_segment, word_offset, 2)
    fields["high_debris_word_layer_value"] = le16(word_bytes, 0)
    return fields


def decode_sample(record: SampleRecord) -> dict[str, int | float | str]:
    elapsed, dump2070, dump2090, dump6610, dumpc1e0, dumpc21e, dump78c0 = record
    debris_queue_count = le16(dump2070, 0x207E - 0x2070)
    collapse_queue_count = le16(dump2070, 0x2080 - 0x2070)
    debris_slots = candidate_slots(
        4,
        debris_queue_count,
        DEBRIS_BASE,
        DEBRIS_DUMP_BASE,
        dump2090,
        DEBRIS_STRIDE,
    )
    collapse_slots = candidate_slots(
        4,
        collapse_queue_count,
        COLLAPSE_BASE,
        COLLAPSE_DUMP_BASE,
        dump6610,
        COLLAPSE_STRIDE,
    )
    debris, debris_score, debris_source = choose_slot(
        [debris_slot_fields(dump2090, slot) for slot in debris_slots],
        debris_queue_count,
        debris_slot_score,
    )
    collapse, collapse_score, collapse_source = choose_slot(
        [collapse_slot_fields(dump6610, slot) for slot in collapse_slots],
        collapse_queue_count,
        collapse_slot_score,
    )
    effect, effect_score = best_scored_slot(
        [effect_slot_fields(dumpc21e, slot) for slot in range(8)], effect_slot_score
    )
    return {
        "elapsed": elapsed,
        **high_debris_target_static_fields(record),
        "lane_update_flag_value": dump2070[0x2078 - 0x2070],
        "lane_word_global_value": le16(dump2090, 0x655E - DEBRIS_DUMP_BASE),
        "lane_target_offset_global_value": le16(
            dump2090, 0x659A - DEBRIS_DUMP_BASE
        ),
        "effect_forward_input_global_value": dump78c0[
            0x78D2 - EFFECT_INPUT_DUMP_BASE
        ],
        "effect_reverse_input_global_value": dump78c0[
            0x78D4 - EFFECT_INPUT_DUMP_BASE
        ],
        "selected_debris_base": debris["addr"],
        "selected_collapse_base": collapse["addr"],
        "selected_effect_base": effect["addr"],
        "selected_debris_slot": debris["slot"],
        "selected_collapse_slot": collapse["slot"],
        "selected_effect_slot": effect["slot"],
        "selected_debris_source": debris_source,
        "selected_collapse_source": collapse_source,
        "debris_queue_count": debris_queue_count,
        "collapse_queue_count": collapse_queue_count,
        "debris_score": debris_score,
        "collapse_score": collapse_score,
        "effect_score": effect_score,
        "debris_nonzero": nonzero_count(dump2090),
        "collapse_nonzero": nonzero_count(dump6610),
        "lookup_nonzero": nonzero_count(dumpc1e0),
        "effect_nonzero": nonzero_count(dumpc21e),
        "debris_tile_index": debris["tile_index"],
        "debris_flagged": debris["flagged"],
        "debris_forward": debris["forward"],
        "debris_reverse": debris["reverse"],
        "debris_lookup": debris["lookup"],
        "collapse_start": collapse["start"],
        "collapse_end": collapse["end"],
        "collapse_word": collapse["word"],
        "collapse_flagged": collapse["flagged"],
        "collapse_forward": collapse["forward"],
        "collapse_reverse": collapse["reverse"],
        "collapse_lane8": collapse["lane8"],
        "collapse_lane9": collapse["lane9"],
        "collapse_magnitude": collapse["magnitude"],
        "collapse_affected": collapse["affected"],
        "collapse_count": collapse["count"],
        "effect_x": effect["x"],
        "effect_y": effect["y"],
        "effect_sprite": effect["sprite"],
        "effect_detail": effect["detail"],
        "effect_timer": effect["timer"],
        "effect_variant": effect["variant"],
    }


def sample_score(record: SampleRecord) -> int:
    fields = decode_sample(record)
    score = 0
    score += int(fields["debris_score"])
    score += int(fields["collapse_score"])
    score += int(fields["effect_score"])
    return score


def choose_sample(records: list[SampleRecord]) -> SampleRecord:
    scored = [(sample_score(record), record) for record in records]
    best_score, best_record = max(scored, key=lambda item: item[0])
    if best_score > 0:
        return best_record
    for record in records:
        _, _, debris, _, lookup, effect, _ = record
        del lookup
        if any(debris[3:14]) or any(effect[:16]):
            return record
    return max(records, key=lambda item: sum(1 for value in item[3] if value))


def write_sample_summary(path: Path, records: list[SampleRecord]) -> None:
    fields = [
        "elapsed",
        "score",
        "selected_debris_base",
        "selected_collapse_base",
        "selected_effect_base",
        "selected_debris_slot",
        "selected_collapse_slot",
        "selected_effect_slot",
        "selected_debris_source",
        "selected_collapse_source",
        "high_debris_target_delta",
        "high_debris_target_offset",
        "high_debris_lookup_segment",
        "high_debris_word_layer_offset",
        "high_debris_word_layer_segment",
        "high_debris_word_layer_address",
        "high_debris_c204",
        "lane_update_flag_value",
        "lane_word_global_value",
        "lane_target_offset_global_value",
        "effect_forward_input_global_value",
        "effect_reverse_input_global_value",
        "debris_queue_count",
        "collapse_queue_count",
        "debris_score",
        "collapse_score",
        "effect_score",
        "debris_nonzero",
        "collapse_nonzero",
        "lookup_nonzero",
        "effect_nonzero",
        "debris_tile_index",
        "debris_flagged",
        "debris_forward",
        "debris_reverse",
        "debris_lookup",
        "collapse_start",
        "collapse_end",
        "collapse_word",
        "collapse_flagged",
        "collapse_forward",
        "collapse_reverse",
        "collapse_lane8",
        "collapse_lane9",
        "collapse_magnitude",
        "collapse_affected",
        "collapse_count",
        "effect_x",
        "effect_y",
        "effect_sprite",
        "effect_detail",
        "effect_timer",
        "effect_variant",
    ]
    with path.open("w", encoding="ascii") as out:
        out.write("\t".join(fields) + "\n")
        for record in records:
            decoded = decode_sample(record)
            values: list[str] = []
            for field in fields:
                if field == "score":
                    values.append(str(sample_score(record)))
                elif field == "elapsed":
                    values.append(f"{float(decoded[field]):.3f}")
                elif isinstance(decoded[field], str):
                    values.append(str(decoded[field]))
                else:
                    values.append(f"0x{int(decoded[field]):04x}")
            out.write("\t".join(values) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("asset_dir", nargs="?", default=".")
    parser.add_argument(
        "--approve-procmem",
        action="store_true",
        help="required: approve reading /proc/<pid>/mem from the child DOSBox process",
    )
    parser.add_argument("--mode", choices=["debug", "regular"], default="debug")
    parser.add_argument("--start-key", default="1")
    parser.add_argument("--start-taps", type=int, default=2)
    parser.add_argument("--level-start-seconds", type=float, default=3.0)
    parser.add_argument("--right-key", default="x")
    parser.add_argument(
        "--x-hold-seconds",
        "--right-hold-seconds",
        dest="right_hold_seconds",
        type=float,
        default=2.0,
    )
    parser.add_argument(
        "--route-step",
        dest="route_steps",
        action="append",
        type=parse_route_step,
        metavar="KEY:SECONDS",
        help=(
            "repeatable original-control hold step before bomb input; "
            "defaults to --right-key/--right-hold-seconds when omitted"
        ),
    )
    parser.add_argument("--sample-seconds", type=float, default=8.0)
    parser.add_argument("--sample-interval", type=float, default=0.08)
    parser.add_argument(
        "--tail-freeze-check-seconds",
        type=float,
        default=0.5,
        help="seconds between final tail screenshots used to detect a frozen frame; 0 disables",
    )
    parser.add_argument(
        "--route-state-interval",
        type=float,
        default=0.25,
        help="seconds between extra DS route-state snapshots after bomb input; 0 keeps only checkpoints",
    )
    parser.add_argument(
        "--sample-screenshot-seconds",
        default=DEFAULT_SAMPLE_SCREENSHOTS,
        help="comma-separated seconds after bomb input for visual checkpoints",
    )
    parser.add_argument("--bomb-key", default="n")
    parser.add_argument("--bomb-hold-seconds", type=float, default=0.25)
    parser.add_argument(
        "--approve-instrumentation",
        action="store_true",
        help="required with --freeze-ghidra-offset: approve freeze-loop instrumentation",
    )
    parser.add_argument(
        "--approve-runtime-instrumentation",
        action="store_true",
        help="required when runtime freeze patching writes to the child DOSBox process",
    )
    parser.add_argument(
        "--freeze-ghidra-offset",
        help="patch temp-copy LEZAC.EXE at Ghidra offset, e.g. 1000:3BB2",
    )
    parser.add_argument(
        "--describe-freeze-patch",
        action="store_true",
        help=(
            "print the freeze patch bytes for --freeze-ghidra-offset and exit "
            "without launching DOSBox or reading process memory"
        ),
    )
    parser.add_argument(
        "--freeze-patch-mode",
        choices=[
            FREEZE_PATCH_MODE_LOOP,
            FREEZE_PATCH_MODE_BP4_CS_SCRATCH,
            FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH,
            FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH,
            FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH,
        ],
        default=FREEZE_PATCH_MODE_LOOP,
        help=(
            "instrumentation body used with --freeze-ghidra-offset; "
            "bp4-cs-scratch is only valid at 1000:4C75 and stores [BP-4] "
            "into a nearby CS scratch word before freezing; "
            "lane-div-cs-scratch is valid at 1000:3CD4/3CE3/3E68/3E77 "
            "and stores pre-division registers or equivalent BP locals into "
            "nearby CS scratch; lane-write-cs-scratch is valid at "
            "1000:3D1B/3D2D/3EAF/3EC1 and stores queue writeback state; "
            "lane-result-cs-scratch is valid at 1000:3D3F/3ED3 and stores "
            "the final helper far-pointer result write"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-after-bomb-seconds",
        type=float,
        help=(
            "with --freeze-ghidra-offset, write EB FE into child memory only "
            "after this many seconds after bomb input"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-before-route",
        action="store_true",
        help=(
            "with --freeze-ghidra-offset, write EB FE into child memory after "
            "the level starts but before route-step input; intended for helpers "
            "that may only run during movement/contact"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-before-bomb",
        action="store_true",
        help=(
            "with --freeze-ghidra-offset, write the runtime freeze patch after "
            "route positioning but before bomb input; intended for helpers that "
            "can run during the bomb key tap"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-preset",
        choices=["late-collapse"],
        help=(
            "apply a repeatable runtime gate preset; late-collapse waits for "
            "queue score >=100 and active debris/collapse/effect bytes, and "
            "disables timed screenshots unless explicitly overridden"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-min-queue-score",
        type=parse_int_auto,
        help=(
            "with runtime freeze patching, also wait until decoded queue score "
            "is at least this value"
        ),
    )
    parser.add_argument(
        "--runtime-freeze-min-debris-nonzero",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for at least this many nonzero DS:2090 bytes",
    )
    parser.add_argument(
        "--runtime-freeze-min-collapse-nonzero",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for at least this many nonzero DS:6610 bytes",
    )
    parser.add_argument(
        "--runtime-freeze-min-effect-nonzero",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for at least this many nonzero DS:C21E bytes",
    )
    parser.add_argument(
        "--runtime-freeze-require-debris-base",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for selected_debris_base to equal this DS offset",
    )
    parser.add_argument(
        "--runtime-freeze-require-collapse-base",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for selected_collapse_base to equal this DS offset",
    )
    parser.add_argument(
        "--runtime-freeze-require-effect-base",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for selected_effect_base to equal this DS offset",
    )
    parser.add_argument(
        "--runtime-freeze-require-high-debris-target-byte",
        type=parse_int_auto,
        help="with runtime freeze patching, wait for the sampled high-debris target byte",
    )
    parser.add_argument(
        "--runtime-seed-debris-writeback",
        action="store_true",
        help=(
            "with runtime lane-write/lane-result freeze patching at "
            "1000:3D2D/3D3F or 1000:3EC1/3ED3, "
            "patch the matching 4C96/4CA9 call site to seed DS:655E=0xC004 "
            "immediately before calling the original helper; labels output as "
            "runtime-seeded evidence"
        ),
    )
    parser.add_argument(
        "--runtime-seed-debris-word",
        type=parse_int_auto,
        default=DEFAULT_SEEDED_DEBRIS_WORD,
        help=(
            "word to place in DS:655E when --runtime-seed-debris-writeback is "
            "active; defaults to 0xC004"
        ),
    )
    args = parser.parse_args()

    if args.describe_freeze_patch:
        if not args.freeze_ghidra_offset:
            raise RuntimeError("--describe-freeze-patch requires --freeze-ghidra-offset")
        asset_dir = Path(args.asset_dir).resolve()
        try:
            description = describe_freeze_patch(
                asset_dir,
                parse_ghidra_offset(args.freeze_ghidra_offset),
                str(args.freeze_patch_mode),
            )
        except Exception as exc:
            print(f"freeze_patch_description=error reason={exc}", file=sys.stderr)
            return 1
        fields = [
            "ghidra_offset",
            "image_base",
            "file_offset",
            "patch_mode",
            "expected_original_bytes",
            "original_bytes",
            "patch_bytes",
            "patch_length",
            "scratch_offset",
            "scratch_length",
            "body_offset",
            "body_length",
            "body_original_bytes",
            "body_patch_bytes",
        ]
        print(
            "freeze_patch_description=ok "
            + " ".join(
                f"{field}="
                + (
                    f"0x{int(description[field]):04x}"
                    if isinstance(description[field], int)
                    and field.endswith(("offset", "base"))
                    else str(description[field])
                )
                for field in fields
            )
        )
        return 0

    if not args.approve_procmem:
        print("refusing to read /proc/<pid>/mem without --approve-procmem", file=sys.stderr)
        return 64
    apply_runtime_freeze_preset(args)

    for tool in ["Xvfb", "xdotool", "dosbox", "python3"]:
        require_tool(tool)
    if args.mode == "debug":
        for tool in ["dosbox-debug", "zutty", "script", "pgrep"]:
            require_tool(tool)

    out_dir = Path(args.out_dir).resolve()
    asset_dir = Path(args.asset_dir).resolve()
    repo_dir = Path.cwd().resolve()
    if args.route_state_interval < 0:
        raise RuntimeError("--route-state-interval must be non-negative")
    if args.tail_freeze_check_seconds < 0:
        raise RuntimeError("--tail-freeze-check-seconds must be non-negative")
    if args.right_hold_seconds < 0:
        raise RuntimeError("--right-hold-seconds must be non-negative")
    if repo_dir in out_dir.parents or out_dir == repo_dir:
        raise RuntimeError("choose an output directory outside the repository")
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_screenshot_seconds = parse_time_list(args.sample_screenshot_seconds)
    route_steps = args.route_steps or [
        RouteStep(key=args.right_key, seconds=args.right_hold_seconds)
    ]
    runtime_freeze = (
        args.runtime_freeze_before_route
        or args.runtime_freeze_before_bomb
        or args.runtime_freeze_after_bomb_seconds is not None
        or args.runtime_freeze_min_queue_score is not None
        or args.runtime_freeze_min_debris_nonzero is not None
        or args.runtime_freeze_min_collapse_nonzero is not None
        or args.runtime_freeze_min_effect_nonzero is not None
        or args.runtime_freeze_require_debris_base is not None
        or args.runtime_freeze_require_collapse_base is not None
        or args.runtime_freeze_require_effect_base is not None
        or args.runtime_freeze_require_high_debris_target_byte is not None
    )
    if args.runtime_freeze_before_route:
        if args.runtime_freeze_before_bomb:
            raise RuntimeError(
                "--runtime-freeze-before-route cannot be combined with "
                "--runtime-freeze-before-bomb"
            )
        if args.runtime_freeze_after_bomb_seconds is not None:
            raise RuntimeError(
                "--runtime-freeze-before-route cannot be combined with "
                "--runtime-freeze-after-bomb-seconds"
            )
        for arg_name in [
            "runtime_freeze_min_queue_score",
            "runtime_freeze_min_debris_nonzero",
            "runtime_freeze_min_collapse_nonzero",
            "runtime_freeze_min_effect_nonzero",
            "runtime_freeze_require_debris_base",
            "runtime_freeze_require_collapse_base",
            "runtime_freeze_require_effect_base",
            "runtime_freeze_require_high_debris_target_byte",
        ]:
            if getattr(args, arg_name) is not None:
                raise RuntimeError(
                    "--runtime-freeze-before-route cannot be combined with "
                    f"--{arg_name.replace('_', '-')}"
                )
    if args.runtime_freeze_before_bomb:
        if args.runtime_freeze_after_bomb_seconds is not None:
            raise RuntimeError(
                "--runtime-freeze-before-bomb cannot be combined with "
                "--runtime-freeze-after-bomb-seconds"
            )
        for arg_name in [
            "runtime_freeze_min_queue_score",
            "runtime_freeze_min_debris_nonzero",
            "runtime_freeze_min_collapse_nonzero",
            "runtime_freeze_min_effect_nonzero",
            "runtime_freeze_require_debris_base",
            "runtime_freeze_require_collapse_base",
            "runtime_freeze_require_effect_base",
            "runtime_freeze_require_high_debris_target_byte",
        ]:
            if getattr(args, arg_name) is not None:
                raise RuntimeError(
                    "--runtime-freeze-before-bomb cannot be combined with "
                    f"--{arg_name.replace('_', '-')}"
                )
    if args.runtime_freeze_after_bomb_seconds is not None:
        if args.runtime_freeze_after_bomb_seconds < 0:
            raise RuntimeError("--runtime-freeze-after-bomb-seconds must be non-negative")
    for arg_name in [
        "runtime_freeze_min_queue_score",
        "runtime_freeze_min_debris_nonzero",
        "runtime_freeze_min_collapse_nonzero",
        "runtime_freeze_min_effect_nonzero",
        "runtime_freeze_require_debris_base",
        "runtime_freeze_require_collapse_base",
        "runtime_freeze_require_effect_base",
        "runtime_freeze_require_high_debris_target_byte",
    ]:
        value = getattr(args, arg_name)
        if value is not None and value < 0:
            raise RuntimeError(f"--{arg_name.replace('_', '-')} must be non-negative")
    if (
        args.runtime_freeze_require_high_debris_target_byte is not None
        and args.runtime_freeze_require_high_debris_target_byte > 0xFF
    ):
        raise RuntimeError("--runtime-freeze-require-high-debris-target-byte must fit in a byte")
    if args.runtime_seed_debris_writeback:
        if not runtime_freeze:
            raise RuntimeError("--runtime-seed-debris-writeback requires runtime freeze patching")
        if not args.freeze_ghidra_offset:
            raise RuntimeError("--runtime-seed-debris-writeback requires --freeze-ghidra-offset")
        if args.freeze_patch_mode not in {
            FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH,
            FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH,
        }:
            raise RuntimeError(
                "--runtime-seed-debris-writeback requires "
                "--freeze-patch-mode lane-write-cs-scratch or "
                "lane-result-cs-scratch"
            )
        if args.runtime_seed_debris_word < 0 or args.runtime_seed_debris_word > 0xFFFF:
            raise RuntimeError("--runtime-seed-debris-word must fit in a word")
    if runtime_freeze and not args.freeze_ghidra_offset:
        raise RuntimeError("runtime freeze patching requires --freeze-ghidra-offset")
    if runtime_freeze and not args.approve_runtime_instrumentation:
        print(
            "refusing to write a runtime freeze patch without "
            "--approve-runtime-instrumentation",
            file=sys.stderr,
        )
        return 64
    if (
        args.freeze_patch_mode == FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH
        and not runtime_freeze
    ):
        raise RuntimeError(
            "--freeze-patch-mode lane-div-cs-scratch requires runtime child-memory "
            "patching; the instrumentation body overlaps a relocated far-call "
            "segment word in temp-copy runs"
        )
    if (
        args.freeze_patch_mode == FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH
        and not runtime_freeze
    ):
        raise RuntimeError(
            "--freeze-patch-mode lane-write-cs-scratch requires runtime child-memory "
            "patching; it is intended to capture live helper writeback registers"
        )
    if (
        args.freeze_patch_mode == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH
        and not runtime_freeze
    ):
        raise RuntimeError(
            "--freeze-patch-mode lane-result-cs-scratch requires runtime child-memory "
            "patching; it captures live ES:DI far-pointer result state"
        )
    freeze_patch: dict[str, int | str] | None = None
    if args.freeze_ghidra_offset:
        if not args.approve_instrumentation:
            print(
                "refusing freeze instrumentation without --approve-instrumentation",
                file=sys.stderr,
            )
            return 64
        freeze_patch = {
            "ghidra_offset": parse_ghidra_offset(args.freeze_ghidra_offset)
        }
    elif args.freeze_patch_mode != FREEZE_PATCH_MODE_LOOP:
        raise RuntimeError("--freeze-patch-mode requires --freeze-ghidra-offset")
    run_dir = out_dir / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    copy_assets(asset_dir, run_dir)
    if freeze_patch is not None:
        if runtime_freeze:
            freeze_patch = describe_freeze_patch(
                run_dir,
                int(freeze_patch["ghidra_offset"]),
                str(args.freeze_patch_mode),
            )
        else:
            freeze_patch = patch_freeze(
                run_dir,
                int(freeze_patch["ghidra_offset"]),
                str(args.freeze_patch_mode),
            )
    runtime_seed_patch: dict[str, int | str] | None = None
    if args.runtime_seed_debris_writeback:
        if freeze_patch is None:
            raise RuntimeError("--runtime-seed-debris-writeback requires a freeze patch")
        runtime_seed_patch = build_runtime_seed_debris_writeback_patch(
            int(freeze_patch["ghidra_offset"]),
            int(args.runtime_seed_debris_word),
        )
    conf = run_dir / "dosbox.conf"
    write_conf(conf, out_dir)

    display = ":137"
    xvfb = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1024x768x24"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    env = os.environ.copy()
    env.update({"DISPLAY": display, "TERM": "xterm-256color", "SDL_AUDIODRIVER": "dummy"})
    proc: subprocess.Popen[str] | None = None
    zutty: subprocess.Popen[str] | None = None

    try:
        time.sleep(0.5)
        if args.mode == "debug":
            command = (
                f'env TERM=xterm-256color SDL_AUDIODRIVER=dummy dosbox-debug '
                f'-conf "{conf}" -c "mount c {run_dir}" -c "c:" '
                f'-c "DEBUG LEZAC.EXE"'
            )
            zutty = subprocess.Popen(
                [
                    "zutty",
                    "-title",
                    "LEZACPROCMEMCAP",
                    "-geometry",
                    "100x50",
                    "-e",
                    "script",
                    "-q",
                    "-f",
                    str(out_dir / "dosbox_debug_terminal.log"),
                    "-c",
                    command,
                ],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            time.sleep(5.0)
            pid = find_debug_pid(run_dir)
            entries = scan_process(pid, ENTRY_SIGNATURE)
            if len(entries) != 1:
                raise RuntimeError(f"expected one entry signature, found {len(entries)}")
            base = entries[0][0] - ((RUNTIME_CS << 4) + ENTRY_IP)
            terminal = run(["xdotool", "search", "--name", "LEZACPROCMEMCAP"], env).split()[0]
            activate_window(env, terminal)
            run(["xdotool", "key", "--window", terminal, "F5"], env, check=False)
            time.sleep(6.0)
        else:
            command = (
                f'dosbox -conf "{conf}" -c "mount c {run_dir}" -c "c:" '
                f'-c "LEZAC.EXE"'
            )
            proc = subprocess.Popen(
                ["dosbox", "-conf", str(conf), "-c", f"mount c {run_dir}", "-c", "c:", "-c", "LEZAC.EXE"],
                cwd=run_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            time.sleep(6.0)
            pid = proc.pid
            data_matches = scan_process(pid, DATA_SIGNATURE)
            if not data_matches:
                raise RuntimeError("runtime data signature not found")
            base = data_matches[-1][0] - ((RUNTIME_DS << 4) + DATA_STRING_OFFSET)

        data_matches = scan_process(pid, DATA_SIGNATURE)
        if data_matches:
            inferred_ds = ((data_matches[-1][0] - base) - DATA_STRING_OFFSET) // 16
        else:
            inferred_ds = RUNTIME_DS
        if inferred_ds != RUNTIME_DS:
            raise RuntimeError(f"unexpected runtime DS 0x{inferred_ds:04x}")
        freeze_loaded_bytes = b""
        freeze_body_loaded_bytes = b""
        freeze_body_loaded_before_runtime_patch = b""
        freeze_loaded_before_runtime_patch = b""
        runtime_freeze_old_bytes = b""
        runtime_freeze_body_old_bytes = b""
        runtime_seed_entry_loaded_before = b""
        runtime_seed_entry_old_bytes = b""
        runtime_seed_entry_loaded_bytes = b""
        runtime_seed_body_loaded_before = b""
        runtime_seed_body_old_bytes = b""
        runtime_seed_body_loaded_bytes = b""
        runtime_seed_patch_applied = False
        runtime_freeze_patch_elapsed: float | None = None
        runtime_freeze_patch_phase = ""
        runtime_freeze_patch_score = 0
        runtime_freeze_patch_fields: dict[str, int | float] = {}
        runtime_bp4_local_value: int | None = None
        runtime_lane_div_scratch: dict[str, int] | None = None
        runtime_lane_write_scratch: dict[str, int] | None = None
        runtime_lane_result_scratch: dict[str, int] | None = None
        patch_bytes = (
            bytes.fromhex(str(freeze_patch["patch_bytes"]))
            if freeze_patch is not None
            else b""
        )
        body_patch_bytes = (
            bytes.fromhex(str(freeze_patch.get("body_patch_bytes", "")))
            if freeze_patch is not None
            else b""
        )
        runtime_seed_entry_patch_bytes = (
            bytes.fromhex(str(runtime_seed_patch["entry_patch_bytes"]))
            if runtime_seed_patch is not None
            else b""
        )
        runtime_seed_body_patch_bytes = (
            bytes.fromhex(str(runtime_seed_patch["body_patch_bytes"]))
            if runtime_seed_patch is not None
            else b""
        )
        freeze_probe_length = max(8, len(patch_bytes) + 4)
        if freeze_patch is not None:
            freeze_loaded_bytes = read_emulated(
                pid,
                base,
                RUNTIME_CS,
                int(freeze_patch["ghidra_offset"]),
                freeze_probe_length,
            )
            if body_patch_bytes:
                freeze_body_loaded_bytes = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )

        def apply_runtime_seed_patch() -> None:
            nonlocal runtime_seed_entry_loaded_before
            nonlocal runtime_seed_entry_old_bytes
            nonlocal runtime_seed_entry_loaded_bytes
            nonlocal runtime_seed_body_loaded_before
            nonlocal runtime_seed_body_old_bytes
            nonlocal runtime_seed_body_loaded_bytes
            nonlocal runtime_seed_patch_applied
            if runtime_seed_patch is None or runtime_seed_patch_applied:
                return
            call_site = int(runtime_seed_patch["call_site"])
            body_offset = int(runtime_seed_patch["body_offset"])
            runtime_seed_entry_loaded_before = read_emulated(
                pid, base, RUNTIME_CS, call_site, len(runtime_seed_entry_patch_bytes)
            )
            runtime_seed_body_loaded_before = read_emulated(
                pid,
                base,
                RUNTIME_CS,
                body_offset,
                len(runtime_seed_body_patch_bytes),
            )
            runtime_seed_body_old_bytes = write_emulated(
                pid,
                base,
                RUNTIME_CS,
                body_offset,
                runtime_seed_body_patch_bytes,
            )
            runtime_seed_entry_old_bytes = write_emulated(
                pid,
                base,
                RUNTIME_CS,
                call_site,
                runtime_seed_entry_patch_bytes,
            )
            runtime_seed_body_loaded_bytes = read_emulated(
                pid,
                base,
                RUNTIME_CS,
                body_offset,
                len(runtime_seed_body_patch_bytes),
            )
            runtime_seed_entry_loaded_bytes = read_emulated(
                pid, base, RUNTIME_CS, call_site, len(runtime_seed_entry_patch_bytes)
            )
            runtime_seed_patch_applied = True

        game = run(["xdotool", "search", "--name", "DOSBox"], env).split()[0]
        snapshot(env, out_dir, game, "000_menu")
        route_state_records: list[RouteStateRecord] = [
            capture_route_state(pid, base, "000_menu", None)
        ]

        def read_sample_record(elapsed: float) -> SampleRecord:
            return (
                elapsed,
                read_emulated(pid, base, RUNTIME_DS, 0x2070, 0x60),
                read_emulated(pid, base, RUNTIME_DS, DEBRIS_DUMP_BASE, DEBRIS_DUMP_LENGTH),
                read_emulated(
                    pid, base, RUNTIME_DS, COLLAPSE_DUMP_BASE, COLLAPSE_DUMP_LENGTH
                ),
                read_emulated(pid, base, RUNTIME_DS, 0xC1E0, 0x40),
                read_emulated(pid, base, RUNTIME_DS, 0xC21E, 0x40),
                read_emulated(
                    pid,
                    base,
                    RUNTIME_DS,
                    EFFECT_INPUT_DUMP_BASE,
                    EFFECT_INPUT_DUMP_LENGTH,
                ),
            )

        for _ in range(max(args.start_taps, 1)):
            key(env, game, args.start_key)
            time.sleep(0.4)
        time.sleep(args.level_start_seconds)
        snapshot(env, out_dir, game, "010_level_start")
        route_state_records.append(
            capture_route_state(pid, base, "010_level_start", None)
        )
        if args.runtime_freeze_before_route:
            patch_offset = int(freeze_patch["ghidra_offset"])
            immediate_record = read_sample_record(0.0)
            current_fields = decode_sample(immediate_record)
            current_score = sample_score(immediate_record)
            freeze_loaded_before_runtime_patch = read_emulated(
                pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
            )
            require_expected_freeze_original_bytes(
                str(freeze_patch["patch_mode"]),
                patch_offset,
                freeze_loaded_before_runtime_patch,
            )
            apply_runtime_seed_patch()
            if body_patch_bytes:
                freeze_body_loaded_before_runtime_patch = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )
                runtime_freeze_body_old_bytes = write_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    body_patch_bytes,
                )
                freeze_body_loaded_bytes = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )
            runtime_freeze_old_bytes = write_emulated(
                pid, base, RUNTIME_CS, patch_offset, patch_bytes
            )
            freeze_loaded_bytes = read_emulated(
                pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
            )
            runtime_freeze_patch_elapsed = 0.0
            runtime_freeze_patch_phase = "before_route"
            runtime_freeze_patch_score = current_score
            runtime_freeze_patch_fields = dict(current_fields)
            route_state_records.append(
                capture_route_state(
                    pid, base, "runtime_freeze_patch_before_route", None
                )
            )
        for index, step in enumerate(route_steps, start=1):
            hold_key(env, game, step.key, step.seconds)
            route_state_records.append(
                capture_route_state(
                    pid, base, route_step_label(step, index), None
                )
            )
        snapshot(env, out_dir, game, "020_route_position")
        route_state_records.append(
            capture_route_state(pid, base, "020_route_position", None)
        )

        if args.runtime_freeze_before_bomb and runtime_freeze_patch_elapsed is None:
            patch_offset = int(freeze_patch["ghidra_offset"])
            immediate_record = read_sample_record(0.0)
            current_fields = decode_sample(immediate_record)
            current_score = sample_score(immediate_record)
            freeze_loaded_before_runtime_patch = read_emulated(
                pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
            )
            require_expected_freeze_original_bytes(
                str(freeze_patch["patch_mode"]),
                patch_offset,
                freeze_loaded_before_runtime_patch,
            )
            apply_runtime_seed_patch()
            if body_patch_bytes:
                freeze_body_loaded_before_runtime_patch = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )
                runtime_freeze_body_old_bytes = write_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    body_patch_bytes,
                )
                freeze_body_loaded_bytes = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )
            runtime_freeze_old_bytes = write_emulated(
                pid, base, RUNTIME_CS, patch_offset, patch_bytes
            )
            freeze_loaded_bytes = read_emulated(
                pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
            )
            runtime_freeze_patch_elapsed = 0.0
            runtime_freeze_patch_phase = "before_bomb"
            runtime_freeze_patch_score = current_score
            runtime_freeze_patch_fields = dict(current_fields)
            route_state_records.append(
                capture_route_state(
                    pid, base, "runtime_freeze_patch_before_bomb", None
                )
            )

        held_tap(env, game, args.bomb_key, args.bomb_hold_seconds)
        immediate_runtime_freeze_ok = (
            runtime_freeze
            and freeze_patch is not None
            and runtime_freeze_patch_elapsed is None
            and args.runtime_freeze_after_bomb_seconds is not None
            and args.runtime_freeze_after_bomb_seconds <= 0
            and args.runtime_freeze_min_queue_score is None
            and args.runtime_freeze_min_debris_nonzero is None
            and args.runtime_freeze_min_collapse_nonzero is None
            and args.runtime_freeze_min_effect_nonzero is None
            and args.runtime_freeze_require_debris_base is None
            and args.runtime_freeze_require_collapse_base is None
            and args.runtime_freeze_require_effect_base is None
            and args.runtime_freeze_require_high_debris_target_byte is None
        )
        if immediate_runtime_freeze_ok:
            patch_offset = int(freeze_patch["ghidra_offset"])
            immediate_record = read_sample_record(0.0)
            current_fields = decode_sample(immediate_record)
            current_score = sample_score(immediate_record)
            freeze_loaded_before_runtime_patch = read_emulated(
                pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
            )
            require_expected_freeze_original_bytes(
                str(freeze_patch["patch_mode"]),
                patch_offset,
                freeze_loaded_before_runtime_patch,
            )
            apply_runtime_seed_patch()
            if body_patch_bytes:
                freeze_body_loaded_before_runtime_patch = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )
                runtime_freeze_body_old_bytes = write_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    body_patch_bytes,
                )
                freeze_body_loaded_bytes = read_emulated(
                    pid,
                    base,
                    RUNTIME_CS,
                    int(freeze_patch["body_offset"]),
                    len(body_patch_bytes),
                )
            runtime_freeze_old_bytes = write_emulated(
                pid, base, RUNTIME_CS, patch_offset, patch_bytes
            )
            freeze_loaded_bytes = read_emulated(
                pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
            )
            runtime_freeze_patch_elapsed = 0.0
            runtime_freeze_patch_phase = "after_bomb"
            runtime_freeze_patch_score = current_score
            runtime_freeze_patch_fields = dict(current_fields)
            route_state_records.append(
                capture_route_state(pid, base, "runtime_freeze_patch", 0.0)
            )
        time.sleep(0.3)
        snapshot(env, out_dir, game, "030_bomb_key")

        records: list[SampleRecord] = []
        captured_sample_screenshots: list[str] = []
        pending_screenshots = list(sample_screenshot_seconds)
        started = time.time()
        route_state_records.append(capture_route_state(pid, base, "030_bomb_key", 0.0))
        next_route_state_elapsed = (
            args.route_state_interval if args.route_state_interval > 0 else None
        )
        while time.time() - started < args.sample_seconds:
            elapsed = time.time() - started
            record = read_sample_record(elapsed)
            records.append(record)
            current_fields = decode_sample(record)
            if args.runtime_freeze_require_high_debris_target_byte is not None:
                try:
                    current_fields.update(resolve_high_debris_target(pid, base, record))
                except OSError:
                    pass
            current_score = sample_score(record)
            after_bomb_ok = (
                args.runtime_freeze_after_bomb_seconds is None
                or elapsed >= args.runtime_freeze_after_bomb_seconds
            )
            score_ok = (
                args.runtime_freeze_min_queue_score is None
                or current_score >= args.runtime_freeze_min_queue_score
            )
            debris_nonzero_ok = (
                args.runtime_freeze_min_debris_nonzero is None
                or int(current_fields["debris_nonzero"])
                >= args.runtime_freeze_min_debris_nonzero
            )
            collapse_nonzero_ok = (
                args.runtime_freeze_min_collapse_nonzero is None
                or int(current_fields["collapse_nonzero"])
                >= args.runtime_freeze_min_collapse_nonzero
            )
            effect_nonzero_ok = (
                args.runtime_freeze_min_effect_nonzero is None
                or int(current_fields["effect_nonzero"])
                >= args.runtime_freeze_min_effect_nonzero
            )
            debris_base_ok = (
                args.runtime_freeze_require_debris_base is None
                or int(current_fields["selected_debris_base"])
                == args.runtime_freeze_require_debris_base
            )
            collapse_base_ok = (
                args.runtime_freeze_require_collapse_base is None
                or int(current_fields["selected_collapse_base"])
                == args.runtime_freeze_require_collapse_base
            )
            effect_base_ok = (
                args.runtime_freeze_require_effect_base is None
                or int(current_fields["selected_effect_base"])
                == args.runtime_freeze_require_effect_base
            )
            high_debris_target_byte_ok = (
                args.runtime_freeze_require_high_debris_target_byte is None
                or (
                    "high_debris_target_byte" in current_fields
                    and int(current_fields["high_debris_target_byte"])
                    == args.runtime_freeze_require_high_debris_target_byte
                )
            )
            if (
                runtime_freeze
                and freeze_patch is not None
                and runtime_freeze_patch_elapsed is None
                and after_bomb_ok
                and score_ok
                and debris_nonzero_ok
                and collapse_nonzero_ok
                and effect_nonzero_ok
                and debris_base_ok
                and collapse_base_ok
                and effect_base_ok
                and high_debris_target_byte_ok
            ):
                patch_offset = int(freeze_patch["ghidra_offset"])
                freeze_loaded_before_runtime_patch = read_emulated(
                    pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
                )
                require_expected_freeze_original_bytes(
                    str(freeze_patch["patch_mode"]),
                    patch_offset,
                    freeze_loaded_before_runtime_patch,
                )
                apply_runtime_seed_patch()
                if body_patch_bytes:
                    freeze_body_loaded_before_runtime_patch = read_emulated(
                        pid,
                        base,
                        RUNTIME_CS,
                        int(freeze_patch["body_offset"]),
                        len(body_patch_bytes),
                    )
                    runtime_freeze_body_old_bytes = write_emulated(
                        pid,
                        base,
                        RUNTIME_CS,
                        int(freeze_patch["body_offset"]),
                        body_patch_bytes,
                    )
                    freeze_body_loaded_bytes = read_emulated(
                        pid,
                        base,
                        RUNTIME_CS,
                        int(freeze_patch["body_offset"]),
                        len(body_patch_bytes),
                    )
                runtime_freeze_old_bytes = write_emulated(
                    pid, base, RUNTIME_CS, patch_offset, patch_bytes
                )
                freeze_loaded_bytes = read_emulated(
                    pid, base, RUNTIME_CS, patch_offset, freeze_probe_length
                )
                runtime_freeze_patch_elapsed = elapsed
                runtime_freeze_patch_phase = "after_bomb"
                runtime_freeze_patch_score = current_score
                runtime_freeze_patch_fields = dict(current_fields)
                route_state_records.append(
                    capture_route_state(
                        pid,
                        base,
                        "runtime_freeze_patch",
                        elapsed,
                    )
                )
            if (
                next_route_state_elapsed is not None
                and elapsed >= next_route_state_elapsed
            ):
                label_seconds = f"{next_route_state_elapsed:.2f}".replace(".", "p")
                route_state_records.append(
                    capture_route_state(
                        pid,
                        base,
                        f"sample_{label_seconds}s",
                        elapsed,
                    )
                )
                while next_route_state_elapsed <= elapsed:
                    next_route_state_elapsed += args.route_state_interval
            while pending_screenshots and elapsed >= pending_screenshots[0]:
                target_seconds = pending_screenshots.pop(0)
                label_seconds = f"{target_seconds:.2f}".replace(".", "p")
                label = f"{40 + len(captured_sample_screenshots):03d}_sample_{label_seconds}s"
                snapshot(env, out_dir, game, label)
                captured_sample_screenshots.append(label)
            time.sleep(args.sample_interval)
        snapshot(env, out_dir, game, "090_after_sampling")
        if args.tail_freeze_check_seconds > 0:
            time.sleep(args.tail_freeze_check_seconds)
            snapshot(env, out_dir, game, "091_tail_freeze_check")
        route_state_records.append(
            capture_route_state(
                pid,
                base,
                "090_after_sampling",
                time.time() - started,
            )
        )

        chosen = choose_sample(records)
        sample_summary = out_dir / "sample_summary.tsv"
        write_sample_summary(sample_summary, records)
        route_state_summary = out_dir / "route_state_samples.tsv"
        route_state_dumps = out_dir / "route_state_dumps.txt"
        write_route_state_samples(
            route_state_summary, route_state_dumps, route_state_records
        )
        screenshot_hashes: list[tuple[str, str]] = []
        for image_path in sorted(out_dir.glob("*.png")):
            screenshot_hashes.append((image_path.name, sha256_file(image_path)))
        after_hash = next(
            (digest for name, digest in screenshot_hashes if name == "090_after_sampling.png"),
            "",
        )
        tail_confirm_hash = next(
            (digest for name, digest in screenshot_hashes if name == "091_tail_freeze_check.png"),
            "",
        )
        tail_match_frame = ""
        if after_hash and tail_confirm_hash and after_hash == tail_confirm_hash:
            tail_match_frame = "091_tail_freeze_check.png"
        elif after_hash:
            for name, digest in reversed(screenshot_hashes):
                if name != "090_after_sampling.png" and digest == after_hash:
                    tail_match_frame = name
                    break
        patch_active = freeze_patch is not None and (
            not runtime_freeze or runtime_freeze_patch_elapsed is not None
        )
        freeze_observed = patch_active and bool(tail_match_frame)
        if (
            freeze_observed
            and freeze_patch is not None
            and str(freeze_patch.get("patch_mode", "")) == FREEZE_PATCH_MODE_BP4_CS_SCRATCH
        ):
            scratch_offset = int(freeze_patch["scratch_offset"])
            runtime_bp4_local_value = le16(
                read_emulated(pid, base, RUNTIME_CS, scratch_offset, 2), 0
            )
        if (
            freeze_observed
            and freeze_patch is not None
            and str(freeze_patch.get("patch_mode", ""))
            == FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH
        ):
            scratch_offset = int(freeze_patch["scratch_offset"])
            scratch_length = int(freeze_patch["scratch_length"])
            scratch = read_emulated(
                pid, base, RUNTIME_CS, scratch_offset, scratch_length
            )
            runtime_lane_div_scratch = {
                "ax": le16(scratch, 0x00),
                "dx": le16(scratch, 0x02),
                "cx": le16(scratch, 0x04),
                "bx": le16(scratch, 0x06),
                "active_count": le16(scratch, 0x08),
                "loop_index": le16(scratch, 0x0A),
                "weight_local": le16(scratch, 0x0C),
                "numerator_low": le16(scratch, 0x0E),
                "numerator_high": le16(scratch, 0x10),
            }
        if (
            freeze_observed
            and freeze_patch is not None
            and str(freeze_patch.get("patch_mode", ""))
            == FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH
        ):
            scratch_offset = int(freeze_patch["scratch_offset"])
            scratch_length = int(freeze_patch["scratch_length"])
            scratch = read_emulated(
                pid, base, RUNTIME_CS, scratch_offset, scratch_length
            )
            runtime_lane_write_scratch = {
                "output": le16(scratch, 0x00),
                "di": le16(scratch, 0x02),
                "tag": le16(scratch, 0x04),
                "active_count": le16(scratch, 0x06),
                "loop_index": le16(scratch, 0x08),
                "result_local": le16(scratch, 0x0A),
            }
        if (
            freeze_observed
            and freeze_patch is not None
            and str(freeze_patch.get("patch_mode", ""))
            == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH
        ):
            scratch_offset = int(freeze_patch["scratch_offset"])
            scratch_length = int(freeze_patch["scratch_length"])
            scratch = read_emulated(
                pid, base, RUNTIME_CS, scratch_offset, scratch_length
            )
            runtime_lane_result_scratch = {
                "output": le16(scratch, 0x00),
                "es": le16(scratch, 0x02),
                "di": le16(scratch, 0x04),
                "arg_offset": le16(scratch, 0x06),
                "arg_segment": le16(scratch, 0x08),
                "result_local": le16(scratch, 0x0A),
                "active_count": le16(scratch, 0x0C),
                "loop_index": le16(scratch, 0x0E),
                "target_before": le16(scratch, 0x10),
            }
        chosen_score = sample_score(chosen)
        chosen_fields = decode_sample(chosen)
        try:
            chosen_target_fields = resolve_high_debris_target(pid, base, chosen)
        except OSError:
            chosen_target_fields = high_debris_target_static_fields(chosen)
        elapsed, dump2070, dump2090, dump6610, dumpc1e0, dumpc21e, dump78c0 = chosen
        fixture = out_dir / "explosion_playback_oracle_original_candidate.txt"
        with fixture.open("w", encoding="ascii") as out:
            out.write("# LEZAC original explosion playback oracle candidate.\n")
            out.write("# Candidate only: inspect frames before promoting to tests/fixtures.\n")
            out.write(f"# chosen_sample_seconds_after_bomb={elapsed:.2f}\n")
            out.write(f"# chosen_sample_score={chosen_score}\n")
            out.write(
                "# chosen_selected_bases="
                f"debris:{int(chosen_fields['selected_debris_base']):04X},"
                f"collapse:{int(chosen_fields['selected_collapse_base']):04X},"
                f"effect:{int(chosen_fields['selected_effect_base']):04X}\n"
            )
            out.write(
                "# chosen_queue_counts="
                f"debris:{int(chosen_fields['debris_queue_count'])},"
                f"collapse:{int(chosen_fields['collapse_queue_count'])}\n"
            )
            out.write(
                "# chosen_selected_sources="
                f"debris:{chosen_fields['selected_debris_source']},"
                f"collapse:{chosen_fields['selected_collapse_source']}\n"
            )
            out.write(
                "# chosen_high_debris_target="
                f"delta:{int(chosen_target_fields['high_debris_target_delta']):04X},"
                f"offset:{int(chosen_target_fields['high_debris_target_offset']):04X},"
                f"lookup_segment:{int(chosen_target_fields['high_debris_lookup_segment']):04X},"
                f"word_layer:{int(chosen_target_fields['high_debris_word_layer_segment']):04X}:"
                f"{int(chosen_target_fields['high_debris_word_layer_address']):04X},"
                f"c204:{int(chosen_target_fields['high_debris_c204']):04X}"
            )
            if "high_debris_target_byte" in chosen_target_fields:
                out.write(
                    f",target_byte:{int(chosen_target_fields['high_debris_target_byte']):02X},"
                    "word:"
                    f"{int(chosen_target_fields['high_debris_word_layer_value']):04X}"
                )
            out.write("\n")
            out.write(f"# sample_summary={sample_summary.name}\n")
            if captured_sample_screenshots:
                out.write(
                    "# sample_screenshots="
                    + ",".join(f"{label}.png" for label in captured_sample_screenshots)
                    + "\n"
                )
            out.write(f"# route_state_samples={route_state_summary.name}\n")
            out.write(f"# route_state_dumps={route_state_dumps.name}\n")
            out.write("capture=explosion_playback\n")
            out.write(f"source=dosbox-{args.mode}-process-memory\n")
            out.write("temp_copy=1\nvisual_claim=0\n")
            if freeze_patch is not None:
                out.write(f"instrumented_temp_copy={0 if runtime_freeze else 1}\n")
                out.write(f"instrumented_runtime_child_memory={1 if runtime_freeze else 0}\n")
                out.write(
                    f"instrumented_freeze_observed={1 if freeze_observed else 0}\n"
                )
                out.write(
                    f"instrumented_freeze_patch_mode={freeze_patch['patch_mode']}\n"
                )
                out.write(
                    "freeze_expected_old_bytes="
                    f"{freeze_patch['expected_original_bytes']}\n"
                )
                freeze_old_bytes = (
                    runtime_freeze_old_bytes.hex()
                    if runtime_freeze_old_bytes
                    else str(freeze_patch["original_bytes"])
                )
                out.write(f"freeze_old_bytes={freeze_old_bytes}\n")
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_BP4_CS_SCRATCH
                ):
                    out.write(
                        "instrumented_bp4_local_present="
                        f"{1 if runtime_bp4_local_value is not None and freeze_observed else 0}\n"
                    )
                    out.write(
                        "instrumented_bp4_local_cs_offset="
                        f"0x{int(freeze_patch['scratch_offset']):04x}\n"
                    )
                    if runtime_bp4_local_value is not None:
                        out.write(
                            "instrumented_bp4_local_value="
                            f"0x{runtime_bp4_local_value:04x}\n"
                        )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH
                ):
                    out.write(
                        "instrumented_lane_div_scratch_present="
                        f"{1 if runtime_lane_div_scratch is not None and freeze_observed else 0}\n"
                    )
                    out.write(
                        "instrumented_lane_div_cs_offset="
                        f"0x{int(freeze_patch['scratch_offset']):04x}\n"
                    )
                    out.write(
                        "instrumented_lane_div_kind="
                        f"{'forward' if int(freeze_patch['ghidra_offset']) in {0x3CD4, 0x3CE3} else 'reverse'}\n"
                    )
                    if runtime_lane_div_scratch is not None:
                        for field in [
                            "ax",
                            "dx",
                            "cx",
                            "bx",
                            "active_count",
                            "loop_index",
                            "weight_local",
                            "numerator_low",
                            "numerator_high",
                        ]:
                            out.write(
                                f"instrumented_lane_div_{field}="
                                f"0x{runtime_lane_div_scratch[field]:04x}\n"
                            )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH
                ):
                    ghidra_offset = int(freeze_patch["ghidra_offset"])
                    lane_kind = (
                        "forward"
                        if ghidra_offset in {0x3D1B, 0x3D2D}
                        else "reverse"
                    )
                    lane_target = (
                        "collapse"
                        if ghidra_offset in {0x3D1B, 0x3EAF}
                        else "debris"
                    )
                    out.write(
                        "instrumented_lane_write_scratch_present="
                        f"{1 if runtime_lane_write_scratch is not None and freeze_observed else 0}\n"
                    )
                    out.write(
                        "instrumented_lane_write_cs_offset="
                        f"0x{int(freeze_patch['scratch_offset']):04x}\n"
                    )
                    out.write(f"instrumented_lane_write_kind={lane_kind}\n")
                    out.write(f"instrumented_lane_write_target={lane_target}\n")
                    if runtime_lane_write_scratch is not None:
                        for field in [
                            "output",
                            "di",
                            "tag",
                            "active_count",
                            "loop_index",
                            "result_local",
                        ]:
                            out.write(
                                f"instrumented_lane_write_{field}="
                                f"0x{runtime_lane_write_scratch[field]:04x}\n"
                            )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH
                ):
                    ghidra_offset = int(freeze_patch["ghidra_offset"])
                    lane_kind = "forward" if ghidra_offset == 0x3D3F else "reverse"
                    out.write(
                        "instrumented_lane_result_scratch_present="
                        f"{1 if runtime_lane_result_scratch is not None and freeze_observed else 0}\n"
                    )
                    out.write(
                        "instrumented_lane_result_cs_offset="
                        f"0x{int(freeze_patch['scratch_offset']):04x}\n"
                    )
                    out.write(f"instrumented_lane_result_kind={lane_kind}\n")
                    if runtime_lane_result_scratch is not None:
                        for field in [
                            "output",
                            "es",
                            "di",
                            "arg_offset",
                            "arg_segment",
                            "result_local",
                            "active_count",
                            "loop_index",
                            "target_before",
                        ]:
                            out.write(
                                f"instrumented_lane_result_{field}="
                                f"0x{runtime_lane_result_scratch[field]:04x}\n"
                            )
                if tail_match_frame:
                    out.write(f"instrumented_freeze_tail_frame={tail_match_frame}\n")
                if runtime_freeze:
                    if runtime_seed_patch is not None:
                        out.write("runtime_seeded=1\n")
                        out.write(
                            "runtime_seed_kind="
                            f"{runtime_seed_patch['kind']}\n"
                        )
                        out.write(
                            "runtime_seed_direction="
                            f"{runtime_seed_patch['direction']}\n"
                        )
                        out.write(
                            "runtime_seed_word="
                            f"0x{int(runtime_seed_patch['seed_word']):04x}\n"
                        )
                        out.write(
                            "runtime_seed_call_site="
                            f"0x{int(runtime_seed_patch['call_site']):04x}\n"
                        )
                        out.write(
                            "runtime_seed_helper_target="
                            f"0x{int(runtime_seed_patch['helper_target']):04x}\n"
                        )
                        out.write(
                            "runtime_seed_return_offset="
                            f"0x{int(runtime_seed_patch['return_offset']):04x}\n"
                        )
                        out.write(
                            "runtime_seed_body_offset="
                            f"0x{int(runtime_seed_patch['body_offset']):04x}\n"
                        )
                        out.write(
                            "runtime_seed_patch_applied="
                            f"{1 if runtime_seed_patch_applied else 0}\n"
                        )
                        out.write(
                            "runtime_seed_entry_loaded_before="
                            f"{runtime_seed_entry_loaded_before.hex()}\n"
                        )
                        out.write(
                            "runtime_seed_entry_old_bytes="
                            f"{runtime_seed_entry_old_bytes.hex()}\n"
                        )
                        out.write(
                            "runtime_seed_entry_loaded_bytes="
                            f"{runtime_seed_entry_loaded_bytes.hex()}\n"
                        )
                        out.write(
                            "runtime_seed_body_loaded_before="
                            f"{runtime_seed_body_loaded_before.hex()}\n"
                        )
                        out.write(
                            "runtime_seed_body_old_bytes="
                            f"{runtime_seed_body_old_bytes.hex()}\n"
                        )
                        out.write(
                            "runtime_seed_body_loaded_bytes="
                            f"{runtime_seed_body_loaded_bytes.hex()}\n"
                        )
                    out.write(
                        "runtime_freeze_patch_applied="
                        f"{1 if runtime_freeze_patch_elapsed is not None else 0}\n"
                    )
                    out.write(
                        f"runtime_freeze_preset={args.runtime_freeze_preset or ''}\n"
                    )
                    out.write(
                        "runtime_freeze_before_route="
                        f"{1 if args.runtime_freeze_before_route else 0}\n"
                    )
                    out.write(
                        "runtime_freeze_before_bomb="
                        f"{1 if args.runtime_freeze_before_bomb else 0}\n"
                    )
                    out.write(
                        "runtime_freeze_after_bomb_seconds="
                        f"{args.runtime_freeze_after_bomb_seconds if args.runtime_freeze_after_bomb_seconds is not None else ''}\n"
                    )
                    out.write(
                        "runtime_freeze_min_queue_score="
                        f"{args.runtime_freeze_min_queue_score if args.runtime_freeze_min_queue_score is not None else ''}\n"
                    )
                    out.write(
                        "runtime_freeze_min_debris_nonzero="
                        f"{optional_int_text(args.runtime_freeze_min_debris_nonzero)}\n"
                    )
                    out.write(
                        "runtime_freeze_min_collapse_nonzero="
                        f"{optional_int_text(args.runtime_freeze_min_collapse_nonzero)}\n"
                    )
                    out.write(
                        "runtime_freeze_min_effect_nonzero="
                        f"{optional_int_text(args.runtime_freeze_min_effect_nonzero)}\n"
                    )
                    out.write(
                        "runtime_freeze_require_debris_base="
                        f"{optional_hex_text(args.runtime_freeze_require_debris_base)}\n"
                    )
                    out.write(
                        "runtime_freeze_require_collapse_base="
                        f"{optional_hex_text(args.runtime_freeze_require_collapse_base)}\n"
                    )
                    out.write(
                        "runtime_freeze_require_effect_base="
                        f"{optional_hex_text(args.runtime_freeze_require_effect_base)}\n"
                    )
                    out.write(
                        "runtime_freeze_require_high_debris_target_byte="
                        f"{optional_hex_text(args.runtime_freeze_require_high_debris_target_byte)}\n"
                    )
                    if runtime_freeze_patch_elapsed is not None:
                        out.write(
                            "runtime_freeze_patch_phase="
                            f"{runtime_freeze_patch_phase}\n"
                        )
                        out.write(
                            "runtime_freeze_patch_elapsed_after_bomb="
                            f"{runtime_freeze_patch_elapsed:.3f}\n"
                        )
                        out.write(
                            f"runtime_freeze_patch_queue_score={runtime_freeze_patch_score}\n"
                        )
                        out.write(
                            "runtime_freeze_loaded_before="
                            f"{freeze_loaded_before_runtime_patch.hex()}\n"
                        )
                        out.write(
                            f"runtime_freeze_old_bytes={runtime_freeze_old_bytes.hex()}\n"
                        )
                        if body_patch_bytes:
                            out.write(
                                "runtime_freeze_body_loaded_before="
                                f"{freeze_body_loaded_before_runtime_patch.hex()}\n"
                            )
                            out.write(
                                "runtime_freeze_body_old_bytes="
                                f"{runtime_freeze_body_old_bytes.hex()}\n"
                            )
                        for field in [
                            "debris_queue_count",
                            "collapse_queue_count",
                            "debris_nonzero",
                            "collapse_nonzero",
                            "effect_nonzero",
                            "selected_debris_base",
                            "selected_collapse_base",
                            "selected_effect_base",
                            "high_debris_target_offset",
                            "high_debris_target_byte",
                            "high_debris_word_layer_value",
                            "lane_update_flag_value",
                            "lane_word_global_value",
                            "lane_target_offset_global_value",
                            "effect_forward_input_global_value",
                            "effect_reverse_input_global_value",
                        ]:
                            if field in runtime_freeze_patch_fields:
                                value = int(runtime_freeze_patch_fields[field])
                                if field in [
                                    "high_debris_target_byte",
                                    "lane_update_flag_value",
                                    "effect_forward_input_global_value",
                                    "effect_reverse_input_global_value",
                                ]:
                                    out.write(f"runtime_freeze_patch_{field}=0x{value:02x}\n")
                                elif (
                                    field.startswith("selected_")
                                    or field.startswith("high_debris_")
                                    or field.startswith("lane_")
                                ):
                                    out.write(f"runtime_freeze_patch_{field}=0x{value:04x}\n")
                                else:
                                    out.write(f"runtime_freeze_patch_{field}={value}\n")
                out.write(
                    f"instrumentation=freeze_loop_patch "
                    f"mode={'runtime_child_memory_patch' if runtime_freeze else 'temp_copy_exe_patch'} "
                    f"patch_mode={freeze_patch['patch_mode']} "
                    f"ghidra=1000:{int(freeze_patch['ghidra_offset']):04X} "
                    f"runtime={RUNTIME_CS:04X}:{int(freeze_patch['ghidra_offset']):04X} "
                    f"file_offset=0x{int(freeze_patch['file_offset']):x} "
                    f"expected_old_bytes={freeze_patch['expected_original_bytes']} "
                    f"old_bytes={freeze_patch['original_bytes']} "
                    f"patch_bytes={freeze_patch['patch_bytes']} "
                    f"loaded_bytes={freeze_loaded_bytes.hex()}"
                )
                if body_patch_bytes:
                    out.write(
                        f" body_cs={RUNTIME_CS:04X}:{int(freeze_patch['body_offset']):04X}"
                        f" body_old_bytes={freeze_patch['body_original_bytes']}"
                        f" body_patch_bytes={freeze_patch['body_patch_bytes']}"
                        f" body_loaded_bytes={freeze_body_loaded_bytes.hex()}"
                    )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_BP4_CS_SCRATCH
                ):
                    out.write(
                        f" scratch_cs={RUNTIME_CS:04X}:{int(freeze_patch['scratch_offset']):04X}"
                        f" scratch_old_bytes={freeze_patch['scratch_original_bytes']}"
                    )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH
                ):
                    out.write(
                        f" scratch_cs={RUNTIME_CS:04X}:{int(freeze_patch['scratch_offset']):04X}"
                        f" scratch_len={int(freeze_patch['scratch_length'])}"
                        f" scratch_old_bytes={freeze_patch['scratch_original_bytes']}"
                    )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH
                ):
                    out.write(
                        f" scratch_cs={RUNTIME_CS:04X}:{int(freeze_patch['scratch_offset']):04X}"
                        f" scratch_len={int(freeze_patch['scratch_length'])}"
                        f" scratch_old_bytes={freeze_patch['scratch_original_bytes']}"
                    )
                if (
                    str(freeze_patch["patch_mode"])
                    == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH
                ):
                    out.write(
                        f" scratch_cs={RUNTIME_CS:04X}:{int(freeze_patch['scratch_offset']):04X}"
                        f" scratch_len={int(freeze_patch['scratch_length'])}"
                        f" scratch_old_bytes={freeze_patch['scratch_original_bytes']}"
                    )
                out.write("\n")
            out.write(f"command={command}\n")
            out.write("route=focused_no_window_original_controls_process_memory\n")
            out.write(f"input_start_key={args.start_key}\n")
            out.write(f"input_start_taps={max(args.start_taps, 1)}\n")
            out.write(f"input_right_key={args.right_key}\n")
            out.write(f"input_right_hold_seconds={args.right_hold_seconds:.2f}\n")
            out.write(f"input_route_steps={route_steps_text(route_steps)}\n")
            out.write(f"input_bomb_key={args.bomb_key}\n")
            out.write(f"input_bomb_hold_seconds={args.bomb_hold_seconds:.2f}\n")
            out.write(f"runtime_cs={RUNTIME_CS:04X}\n")
            out.write(f"runtime_ds={RUNTIME_DS:04X}\n")
            out.write(f"debris_queue_count={int(chosen_fields['debris_queue_count'])}\n")
            out.write(f"collapse_queue_count={int(chosen_fields['collapse_queue_count'])}\n")
            out.write(f"selected_debris_base={int(chosen_fields['selected_debris_base']):04X}\n")
            out.write(f"selected_collapse_base={int(chosen_fields['selected_collapse_base']):04X}\n")
            out.write(f"selected_effect_base={int(chosen_fields['selected_effect_base']):04X}\n")
            out.write(f"selected_debris_source={chosen_fields['selected_debris_source']}\n")
            out.write(f"selected_collapse_source={chosen_fields['selected_collapse_source']}\n")
            chosen_oracle_fields = dict(chosen_target_fields)
            for field in [
                "lane_update_flag_value",
                "lane_word_global_value",
                "lane_target_offset_global_value",
                "effect_forward_input_global_value",
                "effect_reverse_input_global_value",
            ]:
                chosen_oracle_fields[field] = chosen_fields[field]
            for field in [
                "high_debris_target_delta",
                "high_debris_target_offset",
                "high_debris_lookup_segment",
                "high_debris_word_layer_offset",
                "high_debris_word_layer_segment",
                "high_debris_word_layer_address",
                "high_debris_c204",
                "lane_update_flag_value",
                "lane_word_global_value",
                "lane_target_offset_global_value",
                "effect_forward_input_global_value",
                "effect_reverse_input_global_value",
                "high_debris_target_byte",
                "high_debris_word_layer_value",
            ]:
                if field in chosen_oracle_fields:
                    value = int(chosen_oracle_fields[field])
                    if field in [
                        "high_debris_target_byte",
                        "lane_update_flag_value",
                        "effect_forward_input_global_value",
                        "effect_reverse_input_global_value",
                    ]:
                        out.write(f"{field}=0x{value:02x}\n")
                    else:
                        out.write(f"{field}=0x{value:04x}\n")
            for ghidra, offset, label in [
                ("1000:75F1", 0x75F1, "bomb_expire_dispatch_call"),
                ("1000:414A", 0x414A, "explosion_dispatcher"),
                ("1000:370E", 0x370E, "tile_damage_queue"),
                ("1000:3A7E", 0x3A7E, "damage_forward_lookup"),
                ("1000:3B18", 0x3B18, "damage_reverse_lookup"),
                ("1000:3BB2", 0x3BB2, "collapse_forward_pass"),
                ("1000:3CD4", 0x3CD4, "collapse_forward_lane_divide_setup"),
                ("1000:3CE3", 0x3CE3, "collapse_forward_lane_divide"),
                ("1000:3D1B", 0x3D1B, "collapse_forward_lane_write_collapse"),
                ("1000:3D2D", 0x3D2D, "collapse_forward_lane_write_debris"),
                ("1000:3D3F", 0x3D3F, "collapse_forward_lane_result_write"),
                ("1000:3D46", 0x3D46, "collapse_reverse_pass"),
                ("1000:3E68", 0x3E68, "collapse_reverse_lane_divide_setup"),
                ("1000:3E77", 0x3E77, "collapse_reverse_lane_divide"),
                ("1000:3EAF", 0x3EAF, "collapse_reverse_lane_write_collapse"),
                ("1000:3EC1", 0x3EC1, "collapse_reverse_lane_write_debris"),
                ("1000:3ED3", 0x3ED3, "collapse_reverse_lane_result_write"),
                ("1000:3FA6", 0x3FA6, "effect_constructor_candidate"),
                ("1000:45FA", 0x45FA, "effect_debris_update_entry"),
                ("1000:432A", 0x432A, "effect_playback_candidate"),
                ("1000:492F", 0x492F, "high_debris_loop_entry"),
                ("1000:4B3F", 0x4B3F, "high_debris_target_sample"),
                ("1000:4B61", 0x4B61, "high_debris_target_byte_gate"),
                ("1000:4B6A", 0x4B6A, "high_debris_zero_target_branch"),
                ("1000:4C20", 0x4C20, "high_debris_nonzero_target_branch"),
                ("1000:4C75", 0x4C75, "high_debris_word_gate"),
                ("1000:4C96", 0x4C96, "effect_forward_pass_call"),
                ("1000:4C99", 0x4C99, "effect_forward_pass_return"),
                ("1000:4CA9", 0x4CA9, "effect_reverse_pass_call"),
                ("1000:4CAC", 0x4CAC, "effect_reverse_pass_return"),
            ]:
                observed = "process_memory_sampling_no_debugger_break"
                if freeze_patch is not None and offset == int(freeze_patch["ghidra_offset"]):
                    mode_label = (
                        "runtime_child_memory"
                        if runtime_freeze
                        else "instrumented_temp_copy"
                    )
                    if runtime_freeze and runtime_freeze_patch_elapsed is None:
                        observed = "runtime_child_memory_patch_not_applied"
                    else:
                        observed = (
                            f"{mode_label}_freeze_observed"
                            if freeze_observed
                            else f"{mode_label}_patch_loaded_no_freeze_observed"
                        )
                out.write(
                    f"break ghidra={ghidra} runtime={RUNTIME_CS:04X}:{offset:04X} "
                    f"label={label} observed={observed}\n"
                )
            for label, offset, data in [
                ("DS:2070", 0x2070, dump2070),
                ("DS:2090", 0x2090, dump2090),
                ("DS:6610", 0x6610, dump6610),
                ("DS:78C0", EFFECT_INPUT_DUMP_BASE, dump78c0),
                ("DS:C1E0", 0xC1E0, dumpc1e0),
                ("DS:C21E", 0xC21E, dumpc21e),
            ]:
                out.write(f"\ndump {label}\n")
                out.write(format_dump(RUNTIME_DS, offset, data) + "\n")

        instrumentation_manifest = ""
        if freeze_patch is not None:
            instrumentation_manifest = (
                f"freeze_ghidra=1000:{int(freeze_patch['ghidra_offset']):04X}\n"
                f"freeze_runtime={RUNTIME_CS:04X}:{int(freeze_patch['ghidra_offset']):04X}\n"
                f"freeze_file_offset=0x{int(freeze_patch['file_offset']):x}\n"
                f"freeze_patch_mode={freeze_patch['patch_mode']}\n"
                f"freeze_expected_old_bytes={freeze_patch['expected_original_bytes']}\n"
                f"freeze_old_bytes={freeze_patch['original_bytes']}\n"
                f"freeze_patch_bytes={freeze_patch['patch_bytes']}\n"
                f"freeze_loaded_bytes={freeze_loaded_bytes.hex()}\n"
                f"freeze_runtime_child_memory={1 if runtime_freeze else 0}\n"
                "freeze_runtime_patch_applied="
                f"{1 if runtime_freeze_patch_elapsed is not None else 0}\n"
            )
            if body_patch_bytes:
                instrumentation_manifest += (
                    f"freeze_body_runtime={RUNTIME_CS:04X}:"
                    f"{int(freeze_patch['body_offset']):04X}\n"
                    f"freeze_body_length={int(freeze_patch['body_length'])}\n"
                    "freeze_body_old_bytes="
                    f"{freeze_patch['body_original_bytes']}\n"
                    "freeze_body_patch_bytes="
                    f"{freeze_patch['body_patch_bytes']}\n"
                    f"freeze_body_loaded_bytes={freeze_body_loaded_bytes.hex()}\n"
                )
            if runtime_seed_patch is not None:
                instrumentation_manifest += (
                    "runtime_seeded=1\n"
                    f"runtime_seed_kind={runtime_seed_patch['kind']}\n"
                    f"runtime_seed_direction={runtime_seed_patch['direction']}\n"
                    f"runtime_seed_word=0x{int(runtime_seed_patch['seed_word']):04x}\n"
                    "runtime_seed_call_site="
                    f"{RUNTIME_CS:04X}:{int(runtime_seed_patch['call_site']):04X}\n"
                    "runtime_seed_helper_target="
                    f"{RUNTIME_CS:04X}:{int(runtime_seed_patch['helper_target']):04X}\n"
                    "runtime_seed_return_offset="
                    f"{RUNTIME_CS:04X}:{int(runtime_seed_patch['return_offset']):04X}\n"
                    "runtime_seed_body_runtime="
                    f"{RUNTIME_CS:04X}:{int(runtime_seed_patch['body_offset']):04X}\n"
                    f"runtime_seed_patch_applied={1 if runtime_seed_patch_applied else 0}\n"
                    "runtime_seed_entry_patch_bytes="
                    f"{runtime_seed_patch['entry_patch_bytes']}\n"
                    "runtime_seed_body_patch_bytes="
                    f"{runtime_seed_patch['body_patch_bytes']}\n"
                    "runtime_seed_entry_loaded_before="
                    f"{runtime_seed_entry_loaded_before.hex()}\n"
                    "runtime_seed_entry_old_bytes="
                    f"{runtime_seed_entry_old_bytes.hex()}\n"
                    "runtime_seed_entry_loaded_bytes="
                    f"{runtime_seed_entry_loaded_bytes.hex()}\n"
                    "runtime_seed_body_loaded_before="
                    f"{runtime_seed_body_loaded_before.hex()}\n"
                    "runtime_seed_body_old_bytes="
                    f"{runtime_seed_body_old_bytes.hex()}\n"
                    "runtime_seed_body_loaded_bytes="
                    f"{runtime_seed_body_loaded_bytes.hex()}\n"
                )
            if (
                str(freeze_patch["patch_mode"])
                == FREEZE_PATCH_MODE_BP4_CS_SCRATCH
            ):
                instrumentation_manifest += (
                    f"freeze_bp4_scratch_runtime={RUNTIME_CS:04X}:"
                    f"{int(freeze_patch['scratch_offset']):04X}\n"
                    "freeze_bp4_scratch_old_bytes="
                    f"{freeze_patch['scratch_original_bytes']}\n"
                )
                if runtime_bp4_local_value is not None:
                    instrumentation_manifest += (
                        f"freeze_bp4_local_value=0x{runtime_bp4_local_value:04x}\n"
                    )
            if (
                str(freeze_patch["patch_mode"])
                == FREEZE_PATCH_MODE_LANE_DIV_CS_SCRATCH
            ):
                instrumentation_manifest += (
                    f"freeze_lane_div_scratch_runtime={RUNTIME_CS:04X}:"
                    f"{int(freeze_patch['scratch_offset']):04X}\n"
                    f"freeze_lane_div_scratch_length={int(freeze_patch['scratch_length'])}\n"
                    "freeze_lane_div_scratch_old_bytes="
                    f"{freeze_patch['scratch_original_bytes']}\n"
                )
                if runtime_lane_div_scratch is not None:
                    for field in [
                        "ax",
                        "dx",
                        "cx",
                        "bx",
                        "active_count",
                        "loop_index",
                        "weight_local",
                        "numerator_low",
                        "numerator_high",
                    ]:
                        instrumentation_manifest += (
                            f"freeze_lane_div_{field}=0x"
                            f"{runtime_lane_div_scratch[field]:04x}\n"
                        )
            if (
                str(freeze_patch["patch_mode"])
                == FREEZE_PATCH_MODE_LANE_WRITE_CS_SCRATCH
            ):
                instrumentation_manifest += (
                    f"freeze_lane_write_scratch_runtime={RUNTIME_CS:04X}:"
                    f"{int(freeze_patch['scratch_offset']):04X}\n"
                    f"freeze_lane_write_scratch_length={int(freeze_patch['scratch_length'])}\n"
                    "freeze_lane_write_scratch_old_bytes="
                    f"{freeze_patch['scratch_original_bytes']}\n"
                )
                if runtime_lane_write_scratch is not None:
                    for field in [
                        "output",
                        "di",
                        "tag",
                        "active_count",
                        "loop_index",
                        "result_local",
                    ]:
                        instrumentation_manifest += (
                            f"freeze_lane_write_{field}=0x"
                            f"{runtime_lane_write_scratch[field]:04x}\n"
                        )
            if (
                str(freeze_patch["patch_mode"])
                == FREEZE_PATCH_MODE_LANE_RESULT_CS_SCRATCH
            ):
                instrumentation_manifest += (
                    f"freeze_lane_result_scratch_runtime={RUNTIME_CS:04X}:"
                    f"{int(freeze_patch['scratch_offset']):04X}\n"
                    f"freeze_lane_result_scratch_length={int(freeze_patch['scratch_length'])}\n"
                    "freeze_lane_result_scratch_old_bytes="
                    f"{freeze_patch['scratch_original_bytes']}\n"
                )
                if runtime_lane_result_scratch is not None:
                    for field in [
                        "output",
                        "es",
                        "di",
                        "arg_offset",
                        "arg_segment",
                        "result_local",
                        "active_count",
                        "loop_index",
                        "target_before",
                    ]:
                        instrumentation_manifest += (
                            f"freeze_lane_result_{field}=0x"
                            f"{runtime_lane_result_scratch[field]:04x}\n"
                        )
            if runtime_freeze:
                after_bomb_seconds = (
                    ""
                    if args.runtime_freeze_after_bomb_seconds is None
                    else f"{args.runtime_freeze_after_bomb_seconds:.3f}"
                )
                min_queue_score = (
                    ""
                    if args.runtime_freeze_min_queue_score is None
                    else str(args.runtime_freeze_min_queue_score)
                )
                patch_elapsed = (
                    ""
                    if runtime_freeze_patch_elapsed is None
                    else f"{runtime_freeze_patch_elapsed:.3f}"
                )
                instrumentation_manifest += (
                    f"freeze_runtime_preset={args.runtime_freeze_preset or ''}\n"
                    f"freeze_runtime_before_route={1 if args.runtime_freeze_before_route else 0}\n"
                    f"freeze_runtime_before_bomb={1 if args.runtime_freeze_before_bomb else 0}\n"
                    f"freeze_runtime_after_bomb_seconds={after_bomb_seconds}\n"
                    f"freeze_runtime_min_queue_score={min_queue_score}\n"
                    "freeze_runtime_min_debris_nonzero="
                    f"{optional_int_text(args.runtime_freeze_min_debris_nonzero)}\n"
                    "freeze_runtime_min_collapse_nonzero="
                    f"{optional_int_text(args.runtime_freeze_min_collapse_nonzero)}\n"
                    "freeze_runtime_min_effect_nonzero="
                    f"{optional_int_text(args.runtime_freeze_min_effect_nonzero)}\n"
                    "freeze_runtime_require_debris_base="
                    f"{optional_hex_text(args.runtime_freeze_require_debris_base)}\n"
                    "freeze_runtime_require_collapse_base="
                    f"{optional_hex_text(args.runtime_freeze_require_collapse_base)}\n"
                    "freeze_runtime_require_effect_base="
                    f"{optional_hex_text(args.runtime_freeze_require_effect_base)}\n"
                    "freeze_runtime_require_high_debris_target_byte="
                    f"{optional_hex_text(args.runtime_freeze_require_high_debris_target_byte)}\n"
                    f"freeze_runtime_patch_phase={runtime_freeze_patch_phase}\n"
                    f"freeze_runtime_patch_elapsed_after_bomb={patch_elapsed}\n"
                )
                instrumentation_manifest += (
                    f"freeze_runtime_patch_queue_score={runtime_freeze_patch_score}\n"
                    "freeze_runtime_loaded_before="
                    f"{freeze_loaded_before_runtime_patch.hex()}\n"
                    f"freeze_runtime_old_bytes={runtime_freeze_old_bytes.hex()}\n"
                )
                if body_patch_bytes:
                    instrumentation_manifest += (
                        "freeze_runtime_body_loaded_before="
                        f"{freeze_body_loaded_before_runtime_patch.hex()}\n"
                        "freeze_runtime_body_old_bytes="
                        f"{runtime_freeze_body_old_bytes.hex()}\n"
                    )
                if runtime_freeze_patch_elapsed is not None:
                    for field in [
                        "debris_queue_count",
                        "collapse_queue_count",
                        "debris_nonzero",
                        "collapse_nonzero",
                        "effect_nonzero",
                        "selected_debris_base",
                        "selected_collapse_base",
                        "selected_effect_base",
                        "high_debris_target_offset",
                        "high_debris_target_byte",
                        "high_debris_word_layer_value",
                        "lane_update_flag_value",
                        "lane_word_global_value",
                        "lane_target_offset_global_value",
                        "effect_forward_input_global_value",
                        "effect_reverse_input_global_value",
                    ]:
                        if field not in runtime_freeze_patch_fields:
                            continue
                        value = int(runtime_freeze_patch_fields[field])
                        if field in [
                            "high_debris_target_byte",
                            "lane_update_flag_value",
                            "effect_forward_input_global_value",
                            "effect_reverse_input_global_value",
                        ]:
                            instrumentation_manifest += (
                                f"freeze_runtime_patch_{field}=0x{value:02x}\n"
                            )
                        elif (
                            field.startswith("selected_")
                            or field.startswith("high_debris_")
                            or field.startswith("lane_")
                        ):
                            instrumentation_manifest += (
                                f"freeze_runtime_patch_{field}=0x{value:04x}\n"
                            )
                        else:
                            instrumentation_manifest += (
                                f"freeze_runtime_patch_{field}={value}\n"
                            )
        target_manifest = ""
        for field in [
            "high_debris_target_delta",
            "high_debris_target_offset",
            "high_debris_lookup_segment",
            "high_debris_word_layer_offset",
            "high_debris_word_layer_segment",
            "high_debris_word_layer_address",
            "high_debris_c204",
            "high_debris_target_byte",
            "high_debris_word_layer_value",
        ]:
            if field in chosen_target_fields:
                value = int(chosen_target_fields[field])
                if field == "high_debris_target_byte":
                    target_manifest += f"{field}=0x{value:02x}\n"
                else:
                    target_manifest += f"{field}=0x{value:04x}\n"
        manifest = out_dir / "manifest.txt"
        manifest.write_text(
            f"capture=original_explosion_process_memory\n"
            f"mode={args.mode}\n"
            f"method=approved_process_memory_scan_limited_to_child_dosbox_process\n"
            f"run_dir={run_dir}\n"
            f"fixture_candidate={fixture}\n"
            f"runtime_cs={RUNTIME_CS:04X}\n"
            f"runtime_ds={RUNTIME_DS:04X}\n"
            f"instrumented_temp_copy={1 if freeze_patch is not None and not runtime_freeze else 0}\n"
            f"{instrumentation_manifest}"
            f"instrumented_freeze_observed={1 if freeze_observed else 0}\n"
            f"instrumented_freeze_tail_frame={tail_match_frame}\n"
            f"input_start_key={args.start_key}\n"
            f"input_start_taps={max(args.start_taps, 1)}\n"
            f"input_level_start_seconds={args.level_start_seconds:.2f}\n"
            f"input_right_key={args.right_key}\n"
            f"input_right_hold_seconds={args.right_hold_seconds:.2f}\n"
            f"input_route_steps={route_steps_text(route_steps)}\n"
            f"input_bomb_key={args.bomb_key}\n"
            f"input_bomb_hold_seconds={args.bomb_hold_seconds:.2f}\n"
            f"sample_seconds={args.sample_seconds:.2f}\n"
            f"sample_interval={args.sample_interval:.3f}\n"
            f"tail_freeze_check_seconds={args.tail_freeze_check_seconds:.3f}\n"
            f"sample_summary={sample_summary}\n"
            f"route_state_interval={args.route_state_interval:.3f}\n"
            f"route_state_samples={route_state_summary}\n"
            f"route_state_dumps={route_state_dumps}\n"
            f"sample_screenshots="
            f"{','.join(label + '.png' for label in captured_sample_screenshots)}\n"
            f"chosen_sample_seconds_after_bomb={elapsed:.2f}\n"
            f"chosen_sample_score={chosen_score}\n"
            f"debris_queue_count={int(chosen_fields['debris_queue_count'])}\n"
            f"collapse_queue_count={int(chosen_fields['collapse_queue_count'])}\n"
            f"selected_debris_base={int(chosen_fields['selected_debris_base']):04X}\n"
            f"selected_collapse_base={int(chosen_fields['selected_collapse_base']):04X}\n"
            f"selected_effect_base={int(chosen_fields['selected_effect_base']):04X}\n"
            f"selected_debris_source={chosen_fields['selected_debris_source']}\n"
            f"selected_collapse_source={chosen_fields['selected_collapse_source']}\n"
            f"{target_manifest}"
            f"screenshot_sha256="
            f"{','.join(name + ':' + digest for name, digest in screenshot_hashes)}\n"
            f"visual_claim=0\n",
            encoding="ascii",
        )
        print(f"candidate={fixture}")
        return 0
    finally:
        if zutty is not None:
            zutty.terminate()
            try:
                zutty.wait(timeout=3)
            except subprocess.TimeoutExpired:
                zutty.kill()
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        xvfb.terminate()
        try:
            xvfb.wait(timeout=3)
        except subprocess.TimeoutExpired:
            xvfb.kill()


if __name__ == "__main__":
    raise SystemExit(main())
