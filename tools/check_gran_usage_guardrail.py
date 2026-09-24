#!/usr/bin/env python3
"""Check that GRAN.MST remains opaque outside debug/resource preservation paths."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
import tempfile

from source_guardrails import source_files, mask_cpp, DEFINITION, function_ranges as cpp_function_ranges


DEBUG_FUNCTIONS = (
    "validate",
    "debugShippedFileManifest",
    "debugPortCompletionStatus",
    "debugGranStaticConsumerModel",
    "debugGranBossModel",
    "debugGranRawRoundtrip",
    "debugGran",
    "debugOriginalAssetLoad",
)

# Live consumers must be backed by recovered-consumer evidence before being
# added here. spawnLevel7Boss implements the level-7 boss decoded by the
# static consumer model (--debug-gran-static-consumer-model /
# --debug-gran-boss-model) from the shipped executable's reader at
# 1000:08A5 behind the DS:0x79B7 == 7 level gate.
LIVE_FUNCTIONS = ("spawnLevel7Boss",)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def function_ranges(lines: list[str],
                    names: tuple[str, ...] = DEBUG_FUNCTIONS) -> dict[str, tuple[int, int]]:
    return cpp_function_ranges("\n".join(lines), names)


def in_range(line_number: int, ranges: dict[str, tuple[int, int]]) -> bool:
    return any(start <= line_number <= end for start, end in ranges.values())


def direct_class_lines(text: str, class_name: str) -> set[int]:
    """Lines at class member depth, excluding function/local declaration bodies."""
    masked = mask_cpp(text)
    match = re.search(r"\bclass\s+" + re.escape(class_name) + r"\s*\{", masked)
    if not match:
        return set()
    depth = 1
    lines = set()
    start = match.end()
    number = masked.count("\n", 0, start) + 1
    for line in masked[start:].splitlines(keepends=True):
        if depth == 1:
            lines.add(number)
        depth += line.count("{") - line.count("}")
        if depth <= 0:
            break
        number += 1
    return lines


def session_initializer_lines(text: str) -> set[int]:
    """Only the borrowed bank initializer in the actual GameSession constructor."""
    masked = mask_cpp(text)
    constructors = list(re.finditer(
        r"(?m)^GameSession::GameSession\(const AssetCatalog& assets,\s*"
        r"sound::SoundEngine& sound,\s*core::TurboRandom& random\)\s*:\s*"
        r"(?P<initializers>[^;{}]*)\{", masked))
    if len(constructors) != 1:
        raise RuntimeError("expected one GameSession asset constructor")
    constructor = constructors[0]
    initializers = constructor.group("initializers")
    aliases = list(re.finditer(r"\bgran_\(assets\.gran\(\)\)", initializers))
    if len(aliases) != 1:
        raise RuntimeError("expected one GameSession GRAN catalog initializer")
    alias = aliases[0]
    start = constructor.start("initializers") + alias.start()
    number = masked.count("\n", 0, start) + 1
    line = masked.splitlines()[number - 1]
    remainder = line.replace(alias.group(), "", 1)
    if "gran_" in remainder or re.search(r"(?:\.|->|::)\s*gran\b", remainder):
        raise RuntimeError("unexpected GameSession GRAN constructor reference")
    return {number}


def live_consumer_ranges(source, composed: bool) -> dict[str, tuple[int, int]]:
    if "runtime" not in source.roles:
        return {}
    ranges = cpp_function_ranges(source.text, LIVE_FUNCTIONS)
    if not composed or not ranges:
        return ranges
    definitions = [match for match in DEFINITION.finditer(mask_cpp(source.text))
                   if match.group("name").rsplit("::", 1)[-1] in LIVE_FUNCTIONS]
    if (source.relative == "src/gameplay/game_session_boss.cpp"
            and len(definitions) == 1
            and definitions[0].group("name") == "GameSession::spawnLevel7Boss"):
        return ranges
    # This transitional diagnostic adapter forwards to the owning session. It
    # grants no permission to read GRAN here or to add another implementation.
    if source.relative == "src/app/app.cpp" and "diagnostics" in source.roles:
        start, end = ranges["spawnLevel7Boss"]
        body = "\n".join(source.text.splitlines()[start - 1:end]).strip()
        if body == "void spawnLevel7Boss() { gameplayReplay_.spawnLevel7Boss(); }":
            return {}
    raise RuntimeError(f"{source.relative}: unexpected live GRAN consumer owner")


def check_source(root: Path) -> tuple[int, int, int, int, int, int, int, int, int]:
    sources = source_files(root, roles=("runtime", "diagnostics", "dispatch"))
    composed = any(source.relative == "src/gameplay/game_session.hpp" for source in sources)
    session_member_refs = session_init_refs = 0
    found_debug = set()
    found_live = set()
    source_refs = load_refs = debug_refs = member_refs = live_consumer_refs = 0
    accessor_refs = alias_refs = json_load_refs = original_load_refs = 0
    live_refs: list[str] = []
    for source in sources:
        lines = source.text.splitlines()
        ranges = function_ranges(lines) if "diagnostics" in source.roles else {}
        live_ranges = live_consumer_ranges(source, composed)
        if found_debug.intersection(ranges) or found_live.intersection(live_ranges):
            raise RuntimeError(f"{source.relative}: duplicate GRAN consumer definition")
        found_debug.update(ranges)
        found_live.update(live_ranges)
        runtime = "runtime" in source.roles
        catalog_header = runtime and source.relative == "src/resources/asset_catalog.hpp"
        app_source = runtime and source.relative == "src/app/app.cpp"
        session_header = composed and runtime and source.relative == "src/gameplay/game_session.hpp"
        members = direct_class_lines(source.text, "AssetCatalog" if catalog_header else "GameSession" if session_header else "App")
        initializers = session_initializer_lines(source.text) if composed and runtime and source.relative == "src/gameplay/game_session.cpp" else set()
        catalog_load = {}
        if runtime and source.relative == "src/resources/asset_catalog.cpp":
            require(source.text, "AssetCatalog AssetCatalog::load(AssetFormat format)", "catalog:loader")
            catalog_load = cpp_function_ranges(source.text, ("load",))
        for line_number, line in enumerate(lines, start=1):
            if "gran_" not in line and not re.search(r"(?:\.|->|::)\s*gran\b", line):
                continue
            source_refs += 1
            declaration = line.strip()
            if in_range(line_number, catalog_load) and declaration == 'catalog.gran_ = loadGran("GRAN.MST.json");':
                load_refs += 1
                json_load_refs += 1
            elif in_range(line_number, catalog_load) and declaration == 'catalog.gran_ = loadRawGran("GRAN.MST");':
                load_refs += 1
                original_load_refs += 1
            elif catalog_header and line_number in members and declaration == "GranBank gran_;":
                member_refs += 1
            elif catalog_header and line_number in members and declaration == "const GranBank& gran() const { return gran_; }":
                accessor_refs += 1
            elif app_source and line_number in members and declaration == "const GranBank& gran_ = assets_.gran();":
                alias_refs += 1
            elif session_header and line_number in members and declaration == "const GranBank& gran_;":
                session_member_refs += 1
            elif line_number in initializers:
                session_init_refs += 1
            elif in_range(line_number, ranges):
                debug_refs += 1
            elif in_range(line_number, live_ranges):
                live_consumer_refs += 1
            else:
                live_refs.append(f"{source.relative}:{line_number}:{line.strip()}")

    missing = [name for name in DEBUG_FUNCTIONS if name not in found_debug]
    if missing:
        raise RuntimeError("missing debug function range(s): " + ",".join(missing))
    missing_live = [name for name in LIVE_FUNCTIONS if name not in found_live]
    if missing_live:
        raise RuntimeError("missing live consumer function range(s): " + ",".join(missing_live))

    if live_refs:
        raise RuntimeError("unexpected live GRAN references: " + "; ".join(live_refs))
    if (json_load_refs, original_load_refs, member_refs, accessor_refs, alias_refs) != (1, 1, 1, 1, 1):
        raise RuntimeError(
            f"unexpected GRAN catalog ownership counts: json_load={json_load_refs} "
            f"original_load={original_load_refs} member={member_refs} "
            f"accessor={accessor_refs} alias={alias_refs}"
        )
    expected_session = (1, 1) if composed else (0, 0)
    if (session_member_refs, session_init_refs) != expected_session:
        raise RuntimeError(f"unexpected GameSession GRAN ownership counts: member={session_member_refs} initializer={session_init_refs}")
    return source_refs, load_refs, debug_refs, member_refs, live_consumer_refs, accessor_refs, alias_refs, session_member_refs, session_init_refs


def check_cmake(root: Path) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_gran_usage_guardrail.py", "cmake:script")
    require(cmake, "add_test(NAME gran_usage_guardrail", "cmake:test")
    require(cmake, "gran_usage_guardrail=ok", "cmake:output")
    require(cmake, "add_test(NAME gran_raw_roundtrip", "cmake:raw_roundtrip_test")
    require(cmake, "raw_json_match=1", "cmake:raw_roundtrip_output")
    require(cmake, "add_test(NAME gran_profile", "cmake:profile_test")
    return 3


def check_docs(root: Path) -> int:
    docs = (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    )
    for relative in docs:
        text = (root / relative).read_text(encoding="utf-8")
        require(text, "check_gran_usage_guardrail.py", relative)
        require(text, "`GRAN.MST`", relative)
    return len(docs)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_contract_files(root: Path) -> None:
    write_text(root / "tools/source_ownership.json", json.dumps({
        "version": 1,
        "owners": {
            "app": {"runtime": ["src/app/app.cpp"], "dispatch": ["src/app/app.cpp"]},
            "diagnostics": {"diagnostics": ["src/app/app.cpp"]},
            "resources": {"runtime": ["src/resources/asset_catalog.hpp", "src/resources/asset_catalog.cpp"]},
        },
    }))
    write_text(
        root / "CMakeLists.txt",
        "\n".join(
            (
                "add_test(NAME gran_usage_guardrail",
                "  COMMAND python tools/check_gran_usage_guardrail.py)",
                "set_tests_properties(gran_usage_guardrail PROPERTIES",
                '  PASS_REGULAR_EXPRESSION "gran_usage_guardrail=ok")',
                "add_test(NAME gran_raw_roundtrip",
                "  COMMAND lezac_cpp --debug-gran-raw-roundtrip)",
                "set_tests_properties(gran_raw_roundtrip PROPERTIES",
                '  PASS_REGULAR_EXPRESSION "raw_json_match=1")',
                "add_test(NAME gran_profile",
                "  COMMAND lezac_cpp --debug-gran)",
                "",
            )
        ),
    )
    for relative in (
        "README_RECONSTRUCTION.md",
        "docs/GHIDRA_NOTES.md",
        "RECOVERY_STATUS.md",
    ):
        write_text(
            root / relative,
            "`GRAN.MST` remains opaque; see tools/check_gran_usage_guardrail.py.\n",
        )


def write_source(root: Path, live_line: str = "", include_debug: bool = True) -> None:
    debug_functions = (
        "\n".join(
            (
                "    void validate() {",
                "        if (gran_.records.empty()) {",
                "            throw Error();",
                "        }",
                "    }",
                "",
                "    void debugShippedFileManifest() {",
                '        dump("exe_gran_anchor");',
                "    }",
                "",
                "    void debugPortCompletionStatus() {",
                '        dump("gran_mst_preservation");',
                "    }",
                "",
                "    void debugGranStaticConsumerModel() {",
                '        dump("gran_static_consumer_model=ok");',
                "    }",
                "",
                "    void debugGranBossModel() {",
                '        dump("gran_boss_model=ok");',
                "    }",
                "",
                "    void spawnLevel7Boss() {",
                "        auto records = gran_.records;",
                "    }",
                "",
                "    void debugGranRawRoundtrip() {",
                "        dump(gran_.records);",
                "    }",
                "",
                "    void debugGran() {",
                "        dump(gran_.recordSize);",
                "    }",
                "",
                "    void debugOriginalAssetLoad() {",
                "        auto jsonGran = gran_;",
                "        dump(gran_.records.size());",
                "    }",
                "",
            )
        )
        if include_debug
        else ""
    )
    write_text(
        root / "src" / "app" / "app.cpp",
        "\n".join(
            (
                "class App {",
                "",
                debug_functions,
                "    void updateLive() {",
                f"        {live_line}",
                "    }",
                "",
                "    const GranBank& gran_ = assets_.gran();",
                "};",
                "",
            )
        ),
    )
    write_text(root / "src/resources/asset_catalog.hpp", "\n".join((
        "class AssetCatalog {", "public:",
        "    const GranBank& gran() const { return gran_; }", "private:",
        "    GranBank gran_;", "};", "",
    )))
    write_text(root / "src/resources/asset_catalog.cpp", "\n".join((
        "AssetCatalog AssetCatalog::load(AssetFormat format) {",
        '    catalog.gran_ = loadGran("GRAN.MST.json");',
        '    catalog.gran_ = loadRawGran("GRAN.MST");', "}", "",
    )))


def write_composed_source(root: Path) -> None:
    write_source(root)
    app = root / "src/app/app.cpp"
    app.write_text(app.read_text().replace(
        "    void spawnLevel7Boss() {\n        auto records = gran_.records;\n    }",
        "    void spawnLevel7Boss() { gameplayReplay_.spawnLevel7Boss(); }"))
    manifest = root / "tools/source_ownership.json"
    data = json.loads(manifest.read_text())
    data["owners"]["gameplay"] = {"runtime": [
        "src/gameplay/game_session.hpp", "src/gameplay/game_session.cpp",
        "src/gameplay/game_session_boss.cpp", "src/gameplay/extra.cpp"]}
    manifest.write_text(json.dumps(data))
    write_text(root / "src/gameplay/game_session.hpp",
               "class GameSession {\n    const GranBank& gran_;\n};\n")
    write_text(root / "src/gameplay/game_session.cpp",
               "GameSession::GameSession(const AssetCatalog& assets, sound::SoundEngine& sound, core::TurboRandom& random)\n"
               "    : gran_(assets.gran()) {}\n")
    write_text(root / "src/gameplay/game_session_boss.cpp",
               "void GameSession::spawnLevel7Boss() {\n    auto records = gran_.records;\n}\n")
    write_text(root / "src/gameplay/extra.cpp", "")


def self_test() -> int:
    with tempfile.TemporaryDirectory(prefix="lezac-gran-guardrail-") as tmp:
        root = Path(tmp)
        write_contract_files(root)
        write_source(root)
        source_refs, load_refs, debug_refs, member_refs, live_consumer_refs, accessor_refs, alias_refs, session_member_refs, session_init_refs = \
            check_source(root)
        if (source_refs, load_refs, debug_refs, member_refs,
                live_consumer_refs, accessor_refs, alias_refs) != (15, 2, 9, 1, 1, 1, 1):
            raise RuntimeError("selftest positive source counts mismatch")
        check_cmake(root)
        check_docs(root)

        write_source(root, "auto live_count = gran_.records.size();")
        try:
            check_source(root)
        except RuntimeError as exc:
            if "unexpected live GRAN references" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest live GRAN reference was not rejected")

        write_source(root, include_debug=False)
        try:
            check_source(root)
        except RuntimeError as exc:
            if "missing debug function range" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing debug function was not rejected")

        write_source(root)
        write_text(root / "README_RECONSTRUCTION.md", "`GRAN.MST` remains opaque.\n")
        try:
            check_docs(root)
        except RuntimeError as exc:
            if "check_gran_usage_guardrail.py" not in str(exc):
                raise
        else:
            raise RuntimeError("selftest missing docs guardrail reference was not rejected")

        write_composed_source(root)
        result = check_source(root)
        if result != (17, 2, 9, 1, 1, 1, 1, 1, 1):
            raise RuntimeError(f"selftest composed source counts mismatch: {result}")
        mutations = (
            ("src/gameplay/extra.cpp", "void extra() { auto n = assets.gran().records.size(); }\n"),
            ("src/gameplay/extra.cpp", "void extra() { const GranBank& gran_ = assets_.gran(); }\n"),
            ("src/gameplay/extra.cpp", "void GameSession::spawnLevel7Boss() { auto n = gran_.records.size(); }\n"),
            ("src/gameplay/game_session_boss.cpp", "void ForgedSession::spawnLevel7Boss() { auto records = gran_.records; }\n"),
            ("src/gameplay/game_session.hpp", "class GameSession {\n    void extra() { const GranBank& gran_; }\n};\n"),
            ("src/gameplay/game_session.cpp", "GameSession::GameSession(const AssetCatalog& assets, sound::SoundEngine& sound, core::TurboRandom& random)\n"
             "    : gran_(assets.gran()) {}\nvoid extra() { gran_(assets.gran()); }\n"),
        )
        for relative, mutation in mutations:
            write_composed_source(root)
            write_text(root / relative, mutation)
            try:
                check_source(root)
            except RuntimeError:
                pass
            else:
                raise RuntimeError(f"selftest composed GRAN mutation was not rejected: {relative}")

    print(
        "gran_usage_guardrail_selftest=ok "
        "positive=1 live_ref=1 missing_debug=1 docs=1 composed=1 composed_mutations=6"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check GRAN.MST usage stays limited to opaque preservation paths."
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
    source_refs, load_refs, debug_refs, member_refs, live_consumer_refs, accessor_refs, alias_refs, session_member_refs, session_init_refs = \
        check_source(root)
    ctest = check_cmake(root)
    docs = check_docs(root)
    print(
        "gran_usage_guardrail=ok "
        f"source_refs={source_refs} load_refs={load_refs} "
        f"debug_refs={debug_refs} member_refs={member_refs} "
        f"live_consumer_refs={live_consumer_refs} "
        f"live_refs=0 ctest={ctest} docs={docs} "
        f"accessor_refs={accessor_refs} alias_refs={alias_refs} "
        f"session_member_refs={session_member_refs} session_init_refs={session_init_refs}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
