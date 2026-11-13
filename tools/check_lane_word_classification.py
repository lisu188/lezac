#!/usr/bin/env python3
"""Check raw lane-word triage, separately from selected-record tags."""

from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import check_lane_div_route_sweep_summary as div_check
import check_lane_write_route_sweep_summary as write_check
import summarize_lane_div_route_sweep as div_summary
import summarize_lane_write_route_sweep as write_summary


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def original_debris_word(word: int) -> bool:
    return 0 <= word <= 0xFFFF and bool(word & 0x8000) and (word & 0x7FFF) >= 0x4000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parent.parent)
    root = parser.parse_args().root.resolve()
    prefix = bytes.fromhex("8b167420f7c20080744889d025ff7f3d00407345")
    executable = (root / "LEZAC.EXE").read_bytes()
    require(executable[0x770 + 0x3A7E:0x770 + 0x3A7E + len(prefix)] == prefix,
            "original 3A7E damage-bit/type lookup prefix changed")
    words = [0x8009, 0, 0x3FFF, 0x4000, 0x4E1F, 0x4E20, 0x7FFF,
             0x8000, 0xBFFF, 0xC000, 0xC004, 0xFFFF, 0x10000, 0x1C004, -1]
    cli_cases = 0
    with tempfile.TemporaryDirectory(prefix="lezac-lane-word-", dir=div_check.temp_root_for(root)) as tmp:
        base = Path(tmp)
        samples = base / "samples.tsv"
        for word in [*(hex(word) for word in words), "not-hex"]:
            div_check.write_route_state_samples(samples, [("raw", "0.5", "0x90", word)])
            expected = int(original_debris_word(int(word, 16))) if word != "not-hex" else 0
            for module in (div_summary, write_summary):
                stats = module.route_state_stats(samples)
                require(stats.debris_marker_samples == expected,
                        f"{module.__name__} raw_word={word} debris_samples={stats.debris_marker_samples} expected={expected}")
                require(stats.samples == 1 and stats.best_label == "raw", "raw sample metadata lost")
                require(stats.max_lane_word_global == (int(word, 16) if word != "not-hex" else None),
                        "raw sampled word was normalized")

        for positive in (False, True):
            group = [word for word in range(0x10000) if original_debris_word(word) == positive]
            div_check.write_route_state_samples(samples, [
                (f"word_{word:04x}", "0.5", "0x90", hex(word)) for word in group
            ])
            for module in (div_summary, write_summary):
                stats = module.route_state_stats(samples)
                require(stats.samples == len(group) and stats.debris_marker_samples == (len(group) if positive else 0),
                        f"{module.__name__} exhaustive raw-word group incorrect: debris={positive}")
                require(stats.max_lane_word_global == group[-1] and stats.best_label == f"word_{group[-1]:04x}",
                        "exhaustive raw metadata changed")

        for word in (0x8009, 0xBFFF, 0x4001, 0x1C004, 0xC004, 0xFFFF):
            for checker, offset in ((div_check, "3ce3"), (write_check, "3d2d")):
                case = base / f"{checker.__name__}-{word:x}"
                candidate, child, sweep = (case / n for n in ("candidate.txt", "child.txt", "sweep.txt"))
                route_samples, handoff = case / "samples.tsv", case / "handoff.txt"
                checker.write_candidate(candidate, offset, freeze=True)
                checker.write_route_state_samples(route_samples, [("raw", "0.5", "0x90", hex(word))])
                checker.write_runtime_manifest(child, candidate, route_samples)
                checker.write_route_sweep(sweep, [("raw", offset, child, candidate)], [offset])
                args = [str(sweep), "--require-route-state-debris-marker"]
                if checker is div_check:
                    args += ["--require-forward-divide", "--write-forward-debris-route-manifest", str(handoff)]
                positive = original_debris_word(word)
                output = checker.run_summary(root, args, expect_success=positive)
                if positive:
                    require("route_state_debris_marker_candidates=1" in output, "debris route lost")
                    if checker is div_check:
                        require("matching_routes=1" in handoff.read_text(encoding="ascii"), "debris handoff missing")
                else:
                    require("reason=no_route_state_debris_marker_candidates" in output, "wrong rejection gate")
                    require(not handoff.exists(), "non-debris route produced a debris handoff")
                cli_cases += 1

        # These are selected-record tags, not the raw staging word tested above.
        require(write_summary.classify_lane_write_tag("0x0009") == ("collapse", 9), "collapse tag changed")
        require(write_summary.classify_lane_write_tag("0x4e21") == ("debris", 0x4E21), "debris tag changed")
    print(f"lane_word_classification=ok boundary_cases={len(words) + 1} raw_words=65536 "
          f"summarizers=2 cli_cases={cli_cases} original_byte_binding=1 natural_capture_claim=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
