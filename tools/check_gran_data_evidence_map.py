#!/usr/bin/env python3
"""Check GRAN.MST opaque data preservation and evidence coverage."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_RECORD_SIZE = 57
EXPECTED_RECORDS = 7
EXPECTED_RAW_SIZE = EXPECTED_RECORD_SIZE * EXPECTED_RECORDS
EXPECTED_SHA256 = "3f0cf17706d557ca863d6e39bfa6641fba777a88815ba3f0a22e5ac89e0e39e2"


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def require(text: str, snippet: str, case: str) -> None:
    if snippet not in text:
        raise RuntimeError(f"{case} missing snippet {snippet!r}")


def parse_bytes_hex(value: str, record_index: int) -> bytes:
    tokens = value.split()
    try:
        return bytes(int(token, 16) for token in tokens)
    except ValueError as exc:
        raise RuntimeError(f"bad bytes_hex in GRAN record {record_index}") from exc


def check_resource(root: Path) -> tuple[int, int, int, str]:
    raw = (root / "GRAN.MST").read_bytes()
    if len(raw) != EXPECTED_RAW_SIZE:
        raise RuntimeError(f"GRAN.MST raw size mismatch: {len(raw)}")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError(f"GRAN.MST sha256 mismatch: {digest}")

    data = json.loads((root / "src" / "GRAN.MST.json").read_text(encoding="utf-8"))
    if data.get("file") != "GRAN.MST" or data.get("type") != "gran_records":
        raise RuntimeError("GRAN.MST.json metadata mismatch")
    if data.get("record_size") != EXPECTED_RECORD_SIZE:
        raise RuntimeError("GRAN.MST.json record_size mismatch")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_RECORDS:
        raise RuntimeError("GRAN.MST.json records count mismatch")

    payload = bytearray()
    for index, record in enumerate(records):
        if record.get("index") != index:
            raise RuntimeError(f"GRAN.MST.json index mismatch at {index}")
        chunk = parse_bytes_hex(record.get("bytes_hex", ""), index)
        if len(chunk) != EXPECTED_RECORD_SIZE:
            raise RuntimeError(f"GRAN.MST.json record length mismatch at {index}")
        payload.extend(chunk)
    if bytes(payload) != raw:
        raise RuntimeError("GRAN.MST raw/json payload mismatch")
    return len(raw), EXPECTED_RECORD_SIZE, EXPECTED_RECORDS, digest


def check_cmake(root: Path) -> int:
    cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
    require(cmake, "check_gran_data_evidence_map.py", "cmake:checker")
    for test_name in (
        "gran_data_evidence_map",
        "gran_raw_roundtrip",
        "gran_summary",
        "gran_static_consumer_model",
    ):
        require(cmake, f"add_test(NAME {test_name}", f"cmake:{test_name}")
        require(cmake, f"set_tests_properties({test_name}", f"cmake:{test_name}")
    require(cmake, "--debug-gran-raw-roundtrip", "cmake:roundtrip-command")
    require(cmake, "--debug-gran", "cmake:summary-command")
    require(cmake, "--debug-gran-static-consumer-model", "cmake:consumer-command")
    require(cmake, "gran_raw_roundtrip=ok raw_size=399", "cmake:roundtrip-output")
    require(cmake, "gran_record_profile=summary record_size=57 records=7",
            "cmake:summary-output")
    require(cmake, "gran_static_consumer_model=ok", "cmake:consumer-output")
    return 3


def check_source(root: Path) -> int:
    source = (root / "src" / "main.cpp").read_text(encoding="utf-8")
    for snippet in (
        "constexpr size_t kGranRecordSize = 57",
        "GranBank loadGran",
        "record_size does not match GRAN.MST fixed record size",
        "records array does not contain seven records",
        "GRAN.MST raw/json payload mismatch",
    ):
        require(source, snippet, "source")
    return 5


def check_docs(root: Path) -> tuple[int, int]:
    readme = (root / "README_RECONSTRUCTION.md").read_text(encoding="utf-8")
    ghidra = (root / "docs" / "GHIDRA_NOTES.md").read_text(encoding="utf-8")
    status = (root / "RECOVERY_STATUS.md").read_text(encoding="utf-8")

    for snippet in (
        "`GRAN.MST`",
        "seven fixed-size opaque records",
        "--debug-gran",
        "--debug-gran-raw-roundtrip",
    ):
        require(readme, snippet, "README_RECONSTRUCTION.md")

    for snippet in (
        "`GRAN.MST` is the level-7 boss actor file",
        "1000:08A5",
        "stride `0x26`",
        "`7 * 57`",
        "399-byte file",
        "original_runtime_claim=0",
    ):
        require(ghidra, snippet, "docs/GHIDRA_NOTES.md")

    for snippet in (
        "`GRAN.MST` loader and field layout are now statically recovered",
        "--debug-gran-static-consumer-model",
        "frame/debugger evidence",
    ):
        require(status, snippet, "RECOVERY_STATUS.md")
    return 3, 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check GRAN.MST opaque-data evidence handoff."
    )
    parser.add_argument("root", nargs="?", type=Path, default=default_repo_root())
    args = parser.parse_args()

    root = args.root.resolve()
    raw_size, record_size, records, digest = check_resource(root)
    ctests = check_cmake(root)
    source_guards = check_source(root)
    docs, opaque_claim = check_docs(root)
    raw = (root / "GRAN.MST").read_bytes()
    zero_bytes = raw.count(0)

    print(
        "gran_data_evidence_map=ok "
        f"raw_size={raw_size} record_size={record_size} records={records} "
        f"sha256={digest} zero_bytes={zero_bytes} ctests={ctests} "
        f"docs={docs} source_guards={source_guards} opaque_claim={opaque_claim}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
