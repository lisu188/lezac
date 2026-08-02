#!/usr/bin/env python3
"""Cross-check the inventory of port values the original has NOT established.

This repo's recurring failure mode has been a green suite that verifies the
port agrees with itself: a pin echoing a port constant back, with no captured
or byte-cited datum behind it. Several wrong models survived that way -- a
"measured" bomb fuse that was really a spawner cooldown, and a debris
retirement that the original never performs.

This checker makes the set of unevidenced values explicit and machine-checked.
Every site in src/app/app.cpp carrying an UNEVIDENCED / UNRECOVERED / INFERRED
marker must appear in docs/recovery/unevidenced_constants.md, and every entry
in that doc must still exist in the source. Neither side can drift.
"""
import argparse
import re
import sys
from pathlib import Path

MARKERS = ("UNEVIDENCED", "UNRECOVERED", "INFERRED")


def scan_source(path: Path):
    """Return {tag: line_number} for each marked site, keyed by its doc tag."""
    found = {}
    for number, line in enumerate(path.read_text().split("\n"), start=1):
        if not any(marker in line for marker in MARKERS):
            continue
        tag = re.search(r"@unevidenced:([a-z0-9_]+)", line)
        if not tag:
            raise SystemExit(
                f"{path}:{number}: carries an uncertainty marker but no "
                f"@unevidenced:<tag> so the inventory cannot track it:\n  {line.strip()}"
            )
        key = tag.group(1)
        if key in found:
            raise SystemExit(f"{path}:{number}: duplicate @unevidenced tag '{key}'")
        found[key] = number
    return found


def scan_doc(path: Path):
    entries = {}
    for number, line in enumerate(path.read_text().split("\n"), start=1):
        match = re.match(r"^- `([a-z0-9_]+)`\s*—\s*(.+)$", line)
        if match:
            entries[match.group(1)] = (number, match.group(2))
    return entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="src/app/app.cpp")
    parser.add_argument("--doc", default="docs/recovery/unevidenced_constants.md")
    args = parser.parse_args()

    source = Path(args.source)
    doc = Path(args.doc)
    for path in (source, doc):
        if not path.is_file():
            raise SystemExit(f"missing {path}")

    in_source = scan_source(source)
    in_doc = scan_doc(doc)

    missing_from_doc = sorted(set(in_source) - set(in_doc))
    missing_from_source = sorted(set(in_doc) - set(in_source))
    if missing_from_doc:
        raise SystemExit(
            "these marked sites are not in the inventory: "
            + ", ".join(missing_from_doc)
        )
    if missing_from_source:
        raise SystemExit(
            "the inventory lists entries with no marked site left in the source "
            "(recovered? then remove the entry and the marker together): "
            + ", ".join(missing_from_source)
        )

    print(
        "unevidenced_constants=ok"
        f" tracked={len(in_source)}"
        f" source={source.name}"
        f" doc={doc.name}"
        " drift=0"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
