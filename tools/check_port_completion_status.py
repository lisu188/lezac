#!/usr/bin/env python3
"""Check the port-completion status diagnostic stays aligned with docs/CTest.

The C++ diagnostic ``--debug-port-completion-status`` declares the functional
port subsystem table and the open original-evidence (fidelity verification)
backlog. This checker keeps that declaration honest: every subsystem and open
item in the source table must be documented in
``docs/recovery/port_completion_status.md``, the CTest expectation must pin the
same counts, and the diagnostic must keep ``original_fidelity_claim=0`` so the
completion claim never silently promotes original-evidence semantics.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import tempfile


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def parse_source(root: Path) -> tuple[list[tuple[str, str]], list[str]]:
    text = (root / "src" / "app" / "app.cpp").read_text(encoding="utf-8")
    require(text, "--debug-port-completion-status", "source:dispatch")
    require(text, "void debugPortCompletionStatus()", "source:method")
    require(text, "original_fidelity_claim=0", "source:fidelity_claim")

    subsystem_block = re.search(
        r"std::array<PortSubsystem,\s*(\d+)>\s*kPortSubsystems\{\{(.*?)\}\};",
        text,
        re.DOTALL,
    )
    if not subsystem_block:
        raise RuntimeError("source:kPortSubsystems table not found")
    subsystems = re.findall(
        r'\{"([a-z0-9_]+)",\s*"([^"]+)"\}', subsystem_block.group(2)
    )
    if len(subsystems) != int(subsystem_block.group(1)):
        raise RuntimeError(
            "source:kPortSubsystems declared size "
            f"{subsystem_block.group(1)} != parsed {len(subsystems)}"
        )

    item_block = re.search(
        r"std::array<const char\*,\s*(\d+)>\s*kOpenOriginalEvidenceItems\{\{(.*?)\}\};",
        text,
        re.DOTALL,
    )
    if not item_block:
        raise RuntimeError("source:kOpenOriginalEvidenceItems table not found")
    items = re.findall(r'"([a-z0-9_]+)"', item_block.group(2))
    if len(items) != int(item_block.group(1)):
        raise RuntimeError(
            "source:kOpenOriginalEvidenceItems declared size "
            f"{item_block.group(1)} != parsed {len(items)}"
        )

    if len(set(name for name, _ in subsystems)) != len(subsystems):
        raise RuntimeError("source:duplicate subsystem names")
    if len(set(items)) != len(items):
        raise RuntimeError("source:duplicate open evidence items")
    return subsystems, items


def check_cmake(root: Path, subsystem_count: int, item_count: int) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "add_test(NAME port_completion_status", "cmake:test")
    require(
        cmake,
        "port_completion_status=ok"
        f" subsystems={subsystem_count} implemented={subsystem_count}"
        f" open_original_evidence_items={item_count}"
        " port_functionally_complete=1 original_fidelity_claim=0",
        "cmake:summary",
    )
    require(cmake, "check_port_completion_status.py", "cmake:checker")
    require(
        cmake,
        "add_test(NAME port_completion_status_checker_selftest",
        "cmake:selftest",
    )
    return 3


def check_docs(
    root: Path, subsystems: list[tuple[str, str]], items: list[str]
) -> int:
    doc_path = root / "docs" / "recovery" / "port_completion_status.md"
    doc = doc_path.read_text(encoding="utf-8")
    require(doc, "check_port_completion_status.py", "doc:checker")
    require(doc, "original_fidelity_claim=0", "doc:fidelity_claim")
    for name, _validation in subsystems:
        require(doc, f"`{name}`", f"doc:subsystem:{name}")
    for item in items:
        require(doc, f"`{item}`", f"doc:item:{item}")

    for relative in ("README_RECONSTRUCTION.md", "RECOVERY_STATUS.md"):
        text = (root / relative).read_text(encoding="utf-8")
        require(text, "--debug-port-completion-status", relative)
    return 3


def synthetic_source(
    subsystems: list[tuple[str, str]], items: list[str]
) -> str:
    subsystem_rows = "\n".join(
        f'            {{"{name}", "{validation}"}},'
        for name, validation in subsystems
    )
    item_rows = "\n".join(f'            "{item}",' for item in items)
    return "\n".join(
        (
            "class Game {",
            "    void debugPortCompletionStatus() {",
            f"        static const std::array<PortSubsystem, {len(subsystems)}>"
            " kPortSubsystems{{",
            subsystem_rows,
            "        }};",
            f"        static const std::array<const char*, {len(items)}>"
            " kOpenOriginalEvidenceItems{{",
            item_rows,
            "        }};",
            '        std::cout << " original_fidelity_claim=0";',
            "    }",
            "};",
            'if (flag == "--debug-port-completion-status") {}',
            "",
        )
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_synthetic_tree(
    root: Path, subsystems: list[tuple[str, str]], items: list[str]
) -> None:
    write_text(root / "src" / "app" / "app.cpp", synthetic_source(subsystems, items))
    write_text(
        root / "CMakeLists.txt",
        "\n".join(
            (
                "add_test(NAME port_completion_status",
                "  COMMAND lezac_cpp --debug-port-completion-status)",
                '"port_completion_status=ok'
                f" subsystems={len(subsystems)} implemented={len(subsystems)}"
                f" open_original_evidence_items={len(items)}"
                ' port_functionally_complete=1 original_fidelity_claim=0"',
                "add_test(NAME port_completion_status_checker",
                "  COMMAND python tools/check_port_completion_status.py)",
                "add_test(NAME port_completion_status_checker_selftest",
                "  COMMAND python tools/check_port_completion_status.py"
                " --self-test)",
                "",
            )
        ),
    )
    doc_rows = ["# Port completion status", "check_port_completion_status.py",
                "original_fidelity_claim=0"]
    doc_rows += [f"- `{name}`" for name, _ in subsystems]
    doc_rows += [f"- `{item}`" for item in items]
    write_text(
        root / "docs" / "recovery" / "port_completion_status.md",
        "\n".join(doc_rows) + "\n",
    )
    for relative in ("README_RECONSTRUCTION.md", "RECOVERY_STATUS.md"):
        write_text(root / relative, "--debug-port-completion-status\n")


def self_test() -> int:
    subsystems = [("resource_loading", "--validate"), ("menu_ui", "--smoke-ui")]
    items = ["gran_mst_runtime_motion_timing",
             "exact_explosion_sprite_playback"]
    with tempfile.TemporaryDirectory(prefix="lezac-port-completion-") as tmp:
        root = Path(tmp)
        write_synthetic_tree(root, subsystems, items)
        parsed_subsystems, parsed_items = parse_source(root)
        if parsed_subsystems != subsystems or parsed_items != items:
            raise RuntimeError("selftest positive parse mismatch")
        check_cmake(root, len(subsystems), len(items))
        check_docs(root, parsed_subsystems, parsed_items)

        bad = synthetic_source(subsystems, items).replace(
            "std::array<PortSubsystem, 2>", "std::array<PortSubsystem, 3>"
        )
        write_text(root / "src" / "app" / "app.cpp", bad)
        try:
            parse_source(root)
        except RuntimeError as exc:
            if "declared size" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest size mismatch was not rejected")

        write_synthetic_tree(root, subsystems, items)
        doc_path = root / "docs" / "recovery" / "port_completion_status.md"
        doc_text = doc_path.read_text(encoding="utf-8")
        write_text(
            doc_path,
            doc_text.replace("- `gran_mst_runtime_motion_timing`\n", ""),
        )
        try:
            check_docs(root, subsystems, items)
        except RuntimeError as exc:
            if "doc:item:gran_mst_runtime_motion_timing" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing doc item was not rejected")

        write_synthetic_tree(root, subsystems, items)
        write_text(
            root / "CMakeLists.txt",
            "add_test(NAME port_completion_status\n",
        )
        try:
            check_cmake(root, len(subsystems), len(items))
        except RuntimeError as exc:
            if "cmake:summary" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing cmake summary was not rejected")

    print(
        "port_completion_status_checker_selftest=ok "
        "positive=1 size_mismatch=1 missing_doc_item=1 missing_cmake=1"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check the port-completion status diagnostic contract."
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="exercise synthetic positive and rejection cases",
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    if args.self_test:
        return self_test()

    root = args.root.resolve()
    subsystems, items = parse_source(root)
    ctest = check_cmake(root, len(subsystems), len(items))
    docs = check_docs(root, subsystems, items)
    print(
        "port_completion_status_checker=ok "
        f"subsystems={len(subsystems)} open_items={len(items)} "
        f"ctest={ctest} docs={docs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
