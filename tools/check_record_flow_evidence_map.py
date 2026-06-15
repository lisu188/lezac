#!/usr/bin/env python3
"""Check high-score/name-entry/end-flow evidence coverage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


CTESTS = (
    "autoplayer_records_flow_dummy",
    "records_update_temp",
    "records_name_entry_temp",
    "records_save_failure_temp",
    "end_flow_records_temp",
)

COMMANDS = (
    "--debug-autoplayer records_flow",
    "--debug-record-update",
    "--debug-record-name-entry",
    "--debug-record-save-failure",
    "--debug-end-flow-records",
)

SOURCE_ANCHORS = (
    "debugRecordUpdate",
    "debugRecordNameEntry",
    "debugRecordSaveFailure",
    "debugEndFlowRecords",
    "handleNameEntryKey",
    "recordCharForKey",
    "beginEndRun",
    "startNextPendingRecord",
)


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def require_test(cmake: str, name: str) -> None:
    require(cmake, f"add_test(NAME {name}", f"cmake:{name}")
    require(cmake, f"set_tests_properties({name}", f"cmake:{name}")


def check_cmake(root: Path) -> tuple[int, int]:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_record_flow_evidence_map.py", "cmake:checker")
    require_test(cmake, "record_flow_evidence_map")
    for test_name in CTESTS:
        require_test(cmake, test_name)
    for command in COMMANDS:
        require(cmake, command, f"cmake:{command}")
    for output in (
        "record_update=ok top=999999 level=9 name=TEST",
        "record_name_entry=ok top=999999 name=test",
        "record_save_failure=ok pending=999999",
        "end_flow_records=ok completion_level=2",
        "autoplayer=ok scenario=records_flow",
    ):
        require(cmake, output, f"cmake:{output}")
    return len(CTESTS), len(COMMANDS)


def check_source(root: Path) -> int:
    source = (root / "src" / "main.cpp").read_text(encoding="utf-8")
    for snippet in SOURCE_ANCHORS:
        require(source, snippet, "source")
    for snippet in (
        "records_.size() < 7",
        "pendingRecordQueue_",
        "pendingRecordName_.size() < 8",
        "SDLK_BACKSPACE",
        "SDLK_RETURN",
        "SDLK_SPACE",
        "cancelPendingRecord",
        "scoreQualifies",
        "record_update=ok",
        "record_name_entry=ok",
        "record_save_failure=ok",
        "end_flow_records=ok",
    ):
        require(source, snippet, "source")
    return len(SOURCE_ANCHORS)


def check_docs(root: Path) -> int:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    ghidra = (root / "docs" / "GHIDRA_NOTES.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")

    for snippet in (
        "`RECS.DAT` high-score parsing",
        "record-entry",
        "--debug-record-update",
        "--debug-record-name-entry",
        "--debug-record-save-failure",
        "--debug-end-flow-records",
    ):
        require(readme, snippet, "README_RECONSTRUCTION.md")

    for snippet in (
        "1000:1845..1ad4",
        "`A..Z` plus space",
        "or 0x20",
        "Backspace as `0x08`",
        "Enter `0x0d`",
        "colon padding",
        "1000:1b14..1d42",
        "1000:1d18..1d24",
        "1000:1d38",
        "DS:1af7 + 7 * 0x0d",
        "beginEndRun",
        "startNextPendingRecord",
        "finalizePendingRecord",
    ):
        require(ghidra, snippet, "docs/GHIDRA_NOTES.md")

    for snippet in (
        "records_flow",
        "record-entry",
        "--debug-autoplayer records_flow",
    ):
        require(status, snippet, "RECOVERY_STATUS.md")
    return 3


def check_resource(root: Path) -> int:
    path = root / "src" / "RECS.DAT.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("file") != "RECS.DAT" or data.get("type") != "high_scores":
        raise RuntimeError("RECS.DAT.json metadata mismatch")
    records = data.get("records")
    if not isinstance(records, list) or data.get("record_count") != len(records):
        raise RuntimeError("RECS.DAT.json record count mismatch")
    if len(records) != 7:
        raise RuntimeError(f"RECS.DAT.json expected 7 records, found {len(records)}")

    previous_score = None
    for index, record in enumerate(records):
        if record.get("index") != index:
            raise RuntimeError(f"RECS.DAT.json index mismatch at {index}")
        encoded = record.get("encoded_name")
        decoded = record.get("decoded_name")
        score = record.get("score")
        if not isinstance(encoded, str) or len(encoded) != 8:
            raise RuntimeError(f"bad encoded name at record {index}")
        if not isinstance(decoded, str) or not isinstance(score, int):
            raise RuntimeError(f"bad record fields at record {index}")
        if encoded.rstrip(":") != decoded:
            raise RuntimeError(f"colon padding mismatch at record {index}")
        if previous_score is not None and score > previous_score:
            raise RuntimeError("records are not sorted by descending score")
        previous_score = score
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check high-score record-flow evidence handoff."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    ctests, commands = check_cmake(root)
    source_anchors = check_source(root)
    docs = check_docs(root)
    resource_records = check_resource(root)
    print(
        "record_flow_evidence_map=ok "
        f"ctests={ctests} commands={commands} "
        f"source_anchors={source_anchors} docs={docs} "
        f"resource_records={resource_records}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
