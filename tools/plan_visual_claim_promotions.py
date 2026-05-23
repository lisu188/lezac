#!/usr/bin/env python3
"""Validate a batch of visual-claim promotion candidates."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

from summarize_frame_compare_bundle import read_key_values, summarize
from validate_visual_claim_promotion_candidate import (
    fixture_visual_claim,
    resolve_arg,
    validate_generated_entry,
)
from write_visual_claim_promotion_entry import make_entry


PROMOTION_KIND = "visual_claim_candidates"
CANDIDATE_FIELD_RE = re.compile(r"^candidate_(?P<index>[0-9]+)_(?P<field>.+)$")


@dataclass(frozen=True)
class Candidate:
    index: int
    fixture: str
    bundle: Path
    docs: Path
    label: str | None


@dataclass(frozen=True)
class CandidateResult:
    candidate: Candidate
    status: str
    label: str
    current_claim: str
    compared: int
    exact_matches: int
    entry: str
    reason: str


def default_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def token(value: object) -> str:
    return re.sub(r"\s+", "_", str(value))


def display_path(root: Path, path: Path) -> str:
    resolved_root = root.resolve()
    resolved = path.resolve()
    try:
        return resolved.relative_to(resolved_root).as_posix()
    except ValueError:
        return token(resolved)


def require(values: dict[str, str], key: str) -> str:
    value = values.get(key)
    if value is None or value == "":
        raise RuntimeError(f"missing_{key}")
    return value


def parse_count(raw: str) -> int:
    try:
        count = int(raw, 10)
    except ValueError as exc:
        raise RuntimeError(f"bad_candidates={raw}") from exc
    if count < 0:
        raise RuntimeError(f"bad_candidates={raw}")
    return count


def candidate_indices(values: dict[str, str]) -> set[int]:
    indices: set[int] = set()
    for key in values:
        match = CANDIDATE_FIELD_RE.match(key)
        if match:
            indices.add(int(match.group("index")))
    return indices


def parse_candidates(values: dict[str, str]) -> list[Candidate]:
    promotion = require(values, "promotion")
    if promotion != PROMOTION_KIND:
        raise RuntimeError(f"bad_promotion={promotion}")
    count = parse_count(require(values, "candidates"))

    extras = sorted(index for index in candidate_indices(values) if index >= count)
    if extras:
        raise RuntimeError(
            "candidate_index_outside_count="
            + ",".join(str(index) for index in extras)
            + f" candidates={count}"
        )

    candidates: list[Candidate] = []
    for index in range(count):
        prefix = f"candidate_{index}"
        label = values.get(f"{prefix}_label")
        candidates.append(
            Candidate(
                index=index,
                fixture=require(values, f"{prefix}_fixture"),
                bundle=Path(require(values, f"{prefix}_frame_compare_bundle")),
                docs=Path(require(values, f"{prefix}_docs")),
                label=None if label in (None, "", "none") else label,
            )
        )
    return candidates


def validate_candidate(root: Path, candidate: Candidate) -> CandidateResult:
    try:
        current_claim = fixture_visual_claim(root, candidate.fixture)
        summary = summarize(resolve_arg(root, candidate.bundle).resolve())
        if not summary.promotion_ready:
            raise RuntimeError(
                f"frame_compare_bundle_not_ready={summary.bundle} reason={summary.reason}"
            )
        label, entry = make_entry(
            root,
            candidate.fixture,
            candidate.bundle,
            candidate.docs,
            candidate.label,
        )
        validate_generated_entry(root, candidate.fixture, entry)
    except Exception as exc:
        return CandidateResult(
            candidate=candidate,
            status="blocked",
            label=candidate.label or "none",
            current_claim="unknown",
            compared=0,
            exact_matches=0,
            entry="",
            reason=token(exc),
        )

    return CandidateResult(
        candidate=candidate,
        status="ready",
        label=label,
        current_claim=current_claim,
        compared=summary.compared,
        exact_matches=summary.exact_matches,
        entry=entry,
        reason="none",
    )


def print_results(root: Path, manifest: Path, results: list[CandidateResult]) -> tuple[int, int]:
    ready = sum(1 for result in results if result.status == "ready")
    blocked = len(results) - ready
    print(
        "visual_claim_promotion_plan=ok "
        f"manifest={display_path(root, manifest)} "
        f"candidates={len(results)} "
        f"ready={ready} "
        f"blocked={blocked}"
    )
    for result in results:
        candidate = result.candidate
        print(
            "visual_claim_promotion_candidate "
            f"index={candidate.index} "
            f"status={result.status} "
            f"fixture={candidate.fixture} "
            f"label={result.label} "
            f"fixture_current_visual_claim={result.current_claim} "
            f"compared={result.compared} "
            f"exact_matches={result.exact_matches} "
            f"reason={result.reason}"
        )
        if result.entry:
            print(result.entry)
    return ready, blocked


def write_ready_entries(path: Path, results: list[CandidateResult]) -> int:
    ready_entries = [result.entry for result in results if result.status == "ready"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(ready_entries) + ("\n" if ready_entries else ""), encoding="ascii")
    return len(ready_entries)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dry-run a key/value manifest of visual-claim promotion candidates."
    )
    parser.add_argument("manifest", type=Path, help="candidate manifest")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument(
        "--require-all-ready",
        action="store_true",
        help="exit nonzero if any candidate is blocked",
    )
    parser.add_argument(
        "--write-ready-entries",
        type=Path,
        help="write ready ledger entries to this review file without editing the real ledger",
    )
    args = parser.parse_args()

    root = args.repo_root.resolve()
    try:
        manifest_path = resolve_arg(root, args.manifest).resolve()
        manifest = read_key_values(manifest_path)
        candidates = parse_candidates(manifest.values)
    except Exception as exc:
        print(f"visual_claim_promotion_plan=error reason={token(exc)}", file=sys.stderr)
        return 2

    results = [validate_candidate(root, candidate) for candidate in candidates]
    ready, blocked = print_results(root, manifest_path, results)
    if args.write_ready_entries is not None:
        try:
            entries_path = resolve_arg(root, args.write_ready_entries).resolve()
            written = write_ready_entries(entries_path, results)
        except Exception as exc:
            print(f"visual_claim_ready_entries=error reason={token(exc)}", file=sys.stderr)
            return 4
        print(
            "visual_claim_ready_entries=ok "
            f"path={display_path(root, entries_path)} "
            f"entries={written}"
        )
    if args.require_all_ready and blocked:
        print(
            "visual_claim_promotion_plan=error "
            f"reason=blocked_candidates ready={ready} blocked={blocked}",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
