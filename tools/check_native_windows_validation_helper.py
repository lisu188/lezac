#!/usr/bin/env python3
"""Check the native Windows validation helper contract."""

from __future__ import annotations

import argparse
from pathlib import Path


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, label: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{label} missing snippet: {snippet}")


def collapse_ws(text: str) -> str:
    return " ".join(text.split())


def test_block(text: str, name: str) -> str:
    start = text.find(f"add_test(NAME {name}")
    if start < 0:
        raise RuntimeError(f"missing CMake add_test for {name}")
    prop_start = text.find(f"set_tests_properties({name}", start)
    if prop_start < 0:
        raise RuntimeError(f"missing CMake properties for {name}")
    next_test = text.find("\n        add_test(NAME ", prop_start + 1)
    if next_test < 0:
        next_test = text.find("\n    endif()", prop_start + 1)
    if next_test < 0:
        next_test = len(text)
    return text[start:next_test]


def check_script(script_path: Path) -> None:
    text = script_path.read_text(encoding="utf-8")
    for snippet in [
        "Set-SinglePathVariable",
        "[System.Environment]::SetEnvironmentVariable(\"PATH\", $null, \"Process\")",
        "[System.Environment]::SetEnvironmentVariable(\"Path\", $pathValue, \"Process\")",
        "C:\\vcpkg",
        "sdl2_x64-windows",
        "SDL2.lib",
        "SDL2.dll",
        "pkg-config.exe",
        "VsDevCmd.bat",
        "Visual Studio 17 2022",
        "PKG_CONFIG_PATH",
        "CMAKE_GENERATOR_INSTANCE",
        "cmake --build",
        "built executable",
        "built SDL2 runtime copy",
        "sdl2_runtime=1",
        "ctest --test-dir",
        "native_windows_validation=ok",
        "[switch]$SkipTests",
    ]:
        require(text, snippet, "PowerShell helper")


def check_cmake(cmake_path: Path) -> None:
    text = cmake_path.read_text(encoding="utf-8")
    require(text, "check_native_windows_validation_helper.py", "CMake")
    block = test_block(text, "native_windows_validation_helper_expectations")
    for snippet in [
        "tools/check_native_windows_validation_helper.py",
        "${CMAKE_CURRENT_SOURCE_DIR}",
        "^native_windows_validation_helper=ok script=1 cmake=1 docs=2",
    ]:
        if collapse_ws(snippet) not in collapse_ws(block):
            raise RuntimeError(
                "native_windows_validation_helper_expectations missing snippet: "
                f"{snippet}"
            )


def check_docs(root: Path) -> None:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")
    for text, label in [(readme, "README"), (status, "RECOVERY_STATUS")]:
        require(text, "tools/run_native_windows_validation.ps1", label)
        require(text, "build-win-codex-vs3", label)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check native Windows validation helper coverage."
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=Path,
        default=default_repo_root(),
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    check_script(root / "tools" / "run_native_windows_validation.ps1")
    check_cmake(root / "CMakeLists.txt")
    check_docs(root)
    print("native_windows_validation_helper=ok script=1 cmake=1 docs=2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
