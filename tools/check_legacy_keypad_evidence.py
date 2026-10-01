#!/usr/bin/env python3
"""Validate the sealed legacy-reader keypad observations and their boundaries."""

import copy
import gzip
import json

from check_main_menu_fixture import ROOT, require, sha

EVIDENCE = ROOT / "docs/recovery/evidence/legacy_keypad_20261001"
MANIFEST_SHA = "131f0215e2e85e8a27ee451f4dd0dbfc114950930ddb083e09ff3ba9274e2e4e"
BASELINE_EXE = "7e83d43c39db5d06c9888361a7ba8d0f825e57253a87569ff5f6a0e8a7a746ac"
FIXED_EXE = "f7ecfa1eefb12dba4fe11dfc480696d4cd0552fe554f0e77a09c753207f02c3f"
LIVE_SOURCE = "d34e6329a5dd8b0f795018811598c2d64854b155a0960da4d967640be744ab58"
ENGLISH_SHA = "1ba172f477005a57a01132e42042e54a5d1454f5b7361ceba9cab8b36a715b58"
ITALIAN_SHA = "a6e2f9867be3fac329c8862529e751aedffd76f84d846c1c70700eb42bb3a914"
ORIGINAL = ("original_alt_four", "original_alt_six", "original_control_five", "original_control_enter",
            "original_decimal", "original_control_alt_decimal", "original_unmodified_plus", "original_control_alt_priority")
FAILURES = {
    "original_queue_guard_failure": "probe changed the original BIOS character queue",
    "original_clock_boundary_failure": "unexpected original clock boundary",
    "original_decimal_expectation_failure": "probe keys did not reach the completed English menu",
    "original_allocation_failure": "original overlaps resident allocation",
    "cpp_alt_negative": "probe key skipped menu typing",
    "cpp_decimal_negative": "probe keys did not reach the completed English menu",
    "cpp_initial_composition": "ambiguous physical key mapping: KP_Decimal",
}


def load_records():
    data = (EVIDENCE / "manifest.json").read_bytes()
    require(sha(data) == MANIFEST_SHA, "keypad manifest changed")
    manifest = json.loads(data)
    require(manifest["schema"] == 1 and manifest["whole_game_parity"] is False and
            manifest["manual_input"] is False, "keypad scope changed")
    require(len(manifest["cases"]) == 23 and len(manifest["images"]) == 8 and len(manifest["files"]) == 36,
            "keypad evidence inventory")
    require(sha((ROOT / "LEZAC.EXE").read_bytes()) == manifest["original_exe_sha256"], "original executable changed")
    for name, digest in manifest["files"].items():
        require("/" not in name and "\\" not in name, "keypad evidence path escaped")
        require(sha((EVIDENCE / name).read_bytes()) == digest, "keypad evidence changed: " + name)
    records = {}
    for name, item in manifest["cases"].items():
        require(item["record"] in manifest["files"] and item["source"] in manifest["files"], "missing executed source")
        row = json.loads((EVIDENCE / item["record"]).read_bytes())
        field = "harness_sha256" if "scenario" in row else "observer_sha256"
        require(sha(gzip.decompress((EVIDENCE / item["source"]).read_bytes())) == row[field], "observer changed")
        require(row["status"] == item["status"], "raw status changed")
        records[name] = row
    for item in manifest["images"].values():
        require(item["file"] in manifest["files"] and any(x["name"] == item["capture"] and
                x["pixel_sha256"] == item["pixel_sha256"] for x in records[item["case"]]["captures"]),
                "image not bound to executed capture")
    require(manifest["images"]["original_decimal"]["pixel_sha256"] == ENGLISH_SHA and
            manifest["images"]["cpp_decimal"]["pixel_sha256"] == ENGLISH_SHA, "completed English pair changed")
    require(sha(gzip.decompress((EVIDENCE / "producer.py.gz").read_bytes())) == manifest["producer_sha256"],
            "packaging source changed")
    return records


def states(row):
    return [x["after_input_bytes"] for x in row["events"] if "after_input_bytes" in x]


def post_frames(row):
    return [x for x in row["captures"] if x["name"].startswith("after-choice-")]


def validate(records):
    for name in ORIGINAL:
        row = records[name]
        require(row["status"] == "observed" and row["version"] == "original" and row["audio"] == "dummy" and
                row["gameplay_seeded"] is False and row["delay_gates"] is False and row["physical_keys"] is True and
                row["manual_input"] is False and row["hooks_restored"] == 1 and row["child_exit_code"] == 0,
                "original scope or cleanup: " + name)
        require(row["positive_selection_control"] is True and row["selection_control_bytes"]["player_count_79b8"] == 1 and
                len(post_frames(row)) == 5, "original fresh-key control missing: " + name)
    for name, advances in (("original_alt_four", [0, 2, 4, 4, 6, 6]),
                           ("original_alt_six", [0, 2, 4, 4, 6, 8, 10, 10]),
                           ("original_control_five", [0, 2, 4, 6, 8, 10, 10])):
        row = records[name]
        require(row["stage"] == "typing" and row["queue_change_allowed"] is True and
                all(not x["full_menu"] for x in post_frames(row)), "filtered word skipped typing")
        initial = row["before_input_bytes"]["bios_buffer_head_41a"]
        require([x["bios_buffer_head_41a"] - initial for x in states(row)] == advances and
                all(x["bios_buffer_head_41a"] == x["bios_buffer_tail_41c"] and
                    x["last_menu_character_2058"] == 48 for x in states(row)), "BIOS/CRT distinction changed")
    for name, character in (("original_control_enter", 10), ("original_unmodified_plus", 43),
                            ("original_control_alt_priority", 120)):
        row = records[name]
        require(row["after_input_bytes"]["last_menu_character_2058"] == character and
                all(x["full_menu"] for x in post_frames(row) if x["name"] != "after-choice-0.05"),
                "valid keypad or Alt character was suppressed")
    for name, digits in (("original_decimal", [0, 1, 1, 1, 1, 1, 1, 10, 108, 0]),
                         ("original_control_alt_decimal", [0, 1, 1, 1, 1, 10, 10, 10, 10, 10, 108, 0])):
        row = records[name]
        require([x["bios_alt_accumulator_419"] for x in states(row)] == digits and
                all(x["last_menu_character_2058"] == 48 for x in states(row)[:-1]) and
                states(row)[-1]["last_menu_character_2058"] == 108 and states(row)[-1]["language_79cc"] == 1,
                "decimal zero, pending digits or release changed")
        require(any(x["english_full"] and x["pixel_sha256"] == ENGLISH_SHA for x in row["captures"]),
                "original completed English menu missing")
    for name, error in FAILURES.items():
        require(records[name]["status"] == "failed" and records[name]["error"] == error,
                "failed attempt was promoted: " + name)
    require(records["original_allocation_failure"]["hooks_restored"] == 0 and
            not records["original_clock_boundary_failure"]["events"], "startup failure boundary lost")
    require(records["original_decimal_expectation_failure"]["after_input_bytes"]["last_menu_character_2058"] == 240,
            "incorrect decimal expectation concealed")
    for name in ("cpp_alt_negative", "cpp_decimal_negative"):
        require(records[name]["exe_sha256"] == BASELINE_EXE and
                all(x["full_menu"] and not x["english_full"] for x in post_frames(records[name])),
                "baseline mismatch evidence changed")
    for name in ("cpp_alt_fixed", "cpp_decimal_fixed", "cpp_initial_noncharacters", "cpp_initial_intro",
                 "cpp_live_noncharacters", "cpp_live_intro", "cpp_live_composition", "cpp_live_keypad"):
        row = records[name]
        require(row["status"] == "observed" and row["exe_sha256"] == FIXED_EXE and row["child_exit_code"] == 0 and
                row["audio"] == "dummy" and row["normal_entry_point"] is True and row["gameplay_seeded"] is False and
                row["whole_game_parity"] is False and row["manual_input"] is False, "normal C++ scope: " + name)
        if name.startswith("cpp_live_"):
            require(row["harness_sha256"] == LIVE_SOURCE and row["startup_timing_gated"] is False,
                    "corrected physical harness missing")
    require(all(not x["full_menu"] for x in post_frames(records["cpp_alt_fixed"])), "fixed Alt word skipped typing")
    require(any(x["english_full"] and x["pixel_sha256"] == ENGLISH_SHA for x in records["cpp_decimal_fixed"]["captures"]),
            "fixed decimal input did not reach English menu")
    composition = records["cpp_live_composition"]
    require(any(x["name"] == "alt-decimal-released-italian" and x["pixel_sha256"] == ITALIAN_SHA for x in composition["captures"]),
            "normal-app decimal language change missing")
    for name in ("cpp_live_composition", "cpp_live_keypad"):
        decimal = [x for x in records[name]["events"] if x.get("key") == "KP_Decimal"]
        require(decimal and all(x["code"] == 91 and x["lookup_keysym"] == "KP_Delete" for x in decimal),
                "legacy decimal position was not resolved")
    keypad = records["cpp_live_keypad"]
    names = {x["name"] for x in keypad["captures"]}
    require(sum(x.startswith(("menu-", "intro-Alt_L-", "intro-Control_L-", "intro-wait-")) for x in names) == 33 and
            {"unmodified-plus-consumed-skip", "control-keypad-enter-consumed-skip", "fresh-control-keypad-enter-gameplay"} <= names,
            "menu/intro/wait keypad matrix or fresh character controls missing")


def main():
    records = load_records()
    validate(records)
    mutations = [
        lambda r: r["original_control_enter"]["after_input_bytes"].__setitem__("last_menu_character_2058", 48),
        lambda r: r["original_decimal"]["events"][7]["after_input_bytes"].__setitem__("bios_alt_accumulator_419", 1),
        lambda r: r["original_alt_six"]["events"][1]["after_input_bytes"].__setitem__("last_menu_character_2058", 43),
        lambda r: r["original_queue_guard_failure"].__setitem__("status", "observed"),
        lambda r: r["cpp_alt_negative"].__setitem__("exe_sha256", FIXED_EXE),
        lambda r: r["cpp_live_keypad"].__setitem__("normal_entry_point", False),
        lambda r: next(x for x in r["cpp_live_composition"]["events"] if x.get("key") == "KP_Decimal").__setitem__("lookup_keysym", "KP_Decimal"),
        lambda r: r["original_allocation_failure"].__setitem__("status", "observed"),
        lambda r: r["original_control_alt_decimal"]["events"][-3]["after_input_bytes"].__setitem__("last_menu_character_2058", 240),
        lambda r: next(x for x in r["cpp_decimal_fixed"]["captures"] if x["name"] == "english-ready-control").__setitem__("pixel_sha256", ITALIAN_SHA),
    ]
    for mutate in mutations:
        changed = copy.deepcopy(records)
        mutate(changed)
        try:
            validate(changed)
        except RuntimeError:
            continue
        raise RuntimeError("keypad evidence mutation was accepted")
    print("legacy_keypad_evidence=ok originals=8 failed_records=7 cpp_live_cases=4 sources=4 images=8"
          " rejection_mutations=10 whole_game_parity=0 manual_input=0")


if __name__ == "__main__":
    main()
