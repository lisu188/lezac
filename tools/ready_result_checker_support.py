#!/usr/bin/env python3
"""Shared helpers for ready-result summary checker tests."""

from __future__ import annotations

from pathlib import Path


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def write_original_fixture_tree(
    root: Path,
    fixture_name: str,
    *,
    runtime_ds: str,
    include_ledger_entry: bool = True,
    note_names_fixture: bool = True,
) -> Path:
    fixture = root / "tests" / "fixtures" / "dosbox" / fixture_name
    write_text(
        fixture,
        f"temp_copy=1\nvisual_claim=0\nruntime_cs=01ED\nruntime_ds={runtime_ds}\n",
    )
    docs = root / "docs" / "recovery" / "original_runtime_fixture_notes.md"
    note_text = (
        f"# Runtime Notes\n\n{fixture_name} is named here as runtime evidence.\n"
        if note_names_fixture
        else "# Runtime Notes\n\nThis note intentionally omits the fixture name.\n"
    )
    write_text(docs, note_text)
    entry = (
        "- fixture="
        f"{fixture_name} visual_claim=0 "
        "evidence=runtime_cs_runtime_ds_temp_copy "
        "docs=docs/recovery/original_runtime_fixture_notes.md"
    )
    ledger_lines = [
        "# Runtime Evidence Ledger",
        "",
        "runtime_evidence_ledger=non_visual",
        "original_runtime_fixture_count=1",
        "",
        "```text",
        "- fixture=<name>.txt visual_claim=0 evidence=runtime_cs_runtime_ds_temp_copy docs=<path>",
        "```",
        "",
        "Current original-runtime fixtures:",
        "",
    ]
    if include_ledger_entry:
        ledger_lines.append(entry)
    ledger_lines.append("")
    write_text(
        root / "docs" / "recovery" / "runtime_evidence_ledger.md",
        "\n".join(ledger_lines),
    )
    return fixture
