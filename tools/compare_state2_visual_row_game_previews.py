#!/usr/bin/env python3
"""Compare state-2 visual row game-preview frames against original captures."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


FRAME_SUFFIXES = ("4a", "4b", "4c", "4d", "4e", "4f")
ORIGINAL_EXTENSIONS = ("png", "bmp", "ppm", "pnm")


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require_file(path: Path, label: str) -> Path:
    if not path.exists() or not path.is_file():
        raise RuntimeError(f"missing_{label}={path}")
    return path


def prepare_output_dir(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()):
        if not overwrite:
            raise RuntimeError(f"output_directory_not_empty={path}")
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    path.mkdir(parents=True, exist_ok=True)


def copy_file(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)


def original_candidates(original_dir: Path, suffix: str) -> list[Path]:
    stems = (
        f"state2_game_{suffix}",
        f"state2_game_current_{suffix}",
        f"state2_original_{suffix}",
        f"state2_game_original_{suffix}",
        f"state2_game_cursor_{suffix}",
        f"state2_game_row3_{suffix}",
        f"state2_row3_{suffix}",
    )
    return [original_dir / f"{stem}.{ext}" for stem in stems for ext in ORIGINAL_EXTENSIONS]


def find_original_frame(original_dir: Path, suffix: str) -> Path | None:
    for candidate in original_candidates(original_dir, suffix):
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def run_cpp_preview(root: Path, cpp_exe: Path, raw_cpp_dir: Path) -> None:
    raw_cpp_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(cpp_exe), "--capture-state2-visual-row-game-preview", str(raw_cpp_dir)],
        cwd=root,
        check=True,
    )


def run_frame_compare(
    root: Path,
    frame_compare: Path,
    cpp_frame: Path,
    original_frame: Path,
    diff_frame: Path,
) -> tuple[int, str]:
    diff_frame.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(frame_compare),
            str(cpp_frame),
            str(original_frame),
            "--diff",
            str(diff_frame),
        ],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def write_manifest(
    path: Path,
    original_source_dir: Path,
    cpp_dir: Path,
    original_dir: Path,
    diff_dir: Path,
    summary: Path,
    original_capture_exit: int,
    compare_exit: int,
) -> None:
    path.write_text(
        "\n".join(
            [
                "scenario=state2_visual_row_game_preview",
                "source=lezac_cpp",
                "current_renderer=effect_entry_row_byte3",
                "current_base=state2_effect_entry",
                "cursor_renderer=debug_only",
                "visual_claim=0",
                f"original_source_dir={original_source_dir}",
                f"cpp_dir={cpp_dir}",
                f"original_dir={original_dir}",
                f"diff_dir={diff_dir}",
                f"summary={summary}",
                f"original_capture_exit={original_capture_exit}",
                f"original_capture_manifest={original_source_dir / 'manifest.txt'}",
                f"original_environment_preflight_log={original_source_dir / 'environment_preflight.log'}",
                f"compare_exit={compare_exit}",
                "",
            ]
        ),
        encoding="utf-8",
    )


def build_bundle(
    out_dir: Path,
    cpp_exe: Path,
    original_source_dir: Path,
    frame_compare: Path,
    overwrite: bool,
) -> tuple[int, int, int]:
    root = repo_root()
    require_file(cpp_exe, "cpp_exe")
    require_file(frame_compare, "frame_compare")
    prepare_output_dir(out_dir, overwrite)

    raw_cpp_dir = out_dir / "raw_cpp_preview"
    cpp_dir = out_dir / "cpp"
    original_dir = out_dir / "original"
    diff_dir = out_dir / "diff"
    summary_path = out_dir / "frame_compare_summary.txt"
    for directory in (raw_cpp_dir, cpp_dir, original_dir, diff_dir):
        directory.mkdir(parents=True, exist_ok=True)

    run_cpp_preview(root, cpp_exe, raw_cpp_dir)

    compared = 0
    missing_original = 0
    compare_exit = 0
    summary_lines: list[str] = []
    original_capture_exit = 0 if original_source_dir.exists() else 66

    for suffix in FRAME_SUFFIXES:
        original_frame = find_original_frame(original_source_dir, suffix)
        for variant, source_stem in (
            ("current", f"state2_game_current_{suffix}"),
            ("cursor", f"state2_game_cursor_{suffix}"),
        ):
            label = f"state2_{variant}_{suffix}"
            cpp_src = raw_cpp_dir / f"{source_stem}.ppm"
            cpp_dst = cpp_dir / f"{label}.ppm"
            copy_file(require_file(cpp_src, source_stem), cpp_dst)

            if original_frame is None:
                missing_original += 1
                summary_lines.append(f"compare label={label} status=missing_original")
                continue

            original_dst = original_dir / f"{label}{original_frame.suffix.lower()}"
            copy_file(original_frame, original_dst)
            status, output = run_frame_compare(
                root,
                frame_compare,
                cpp_dst,
                original_dst,
                diff_dir / f"{label}.ppm",
            )
            if status > 1:
                compare_exit = status
            if output:
                for line in output.splitlines():
                    summary_lines.append(f"compare label={label} {line}")
            else:
                summary_lines.append(f"compare label={label} frame_compare=error reason=no_output")
                compare_exit = max(compare_exit, 2)
            compared += 1

    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    write_manifest(
        out_dir / "manifest.txt",
        original_source_dir,
        cpp_dir,
        original_dir,
        diff_dir,
        summary_path,
        original_capture_exit,
        compare_exit,
    )
    return compared, missing_original, compare_exit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("cpp_exe", type=Path)
    parser.add_argument("original_dir", type=Path)
    parser.add_argument(
        "--frame-compare",
        type=Path,
        default=repo_root() / "tools" / "frame_compare.py",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        compared, missing_original, compare_exit = build_bundle(
            args.out_dir.resolve(),
            args.cpp_exe.resolve(),
            args.original_dir.resolve(),
            args.frame_compare.resolve(),
            args.overwrite,
        )
    except Exception as exc:  # noqa: BLE001 - command-line diagnostic.
        print(f"state2_visual_row_compare_bundle=error reason={exc}", file=sys.stderr)
        return 1

    status = "ok" if compare_exit == 0 else "error"
    print(
        f"state2_visual_row_compare_bundle={status} "
        f"scenario=state2_visual_row_game_preview "
        f"compared={compared} "
        f"missing_original={missing_original} "
        f"compare_exit={compare_exit} "
        f"out_dir={args.out_dir.resolve()} "
        f"manifest={args.out_dir.resolve() / 'manifest.txt'} "
        f"summary={args.out_dir.resolve() / 'frame_compare_summary.txt'}"
    )
    return compare_exit


if __name__ == "__main__":
    raise SystemExit(main())
