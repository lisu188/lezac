#!/usr/bin/env python3
"""Pin BIOS-menu observations, their executed sources and their bounded claims."""

import copy
import gzip
import json

from check_main_menu_fixture import ROOT, require, sha

EVIDENCE = ROOT / "docs/recovery/evidence/bios_menu_input_20261001"
MANIFEST_SHA = "e6a24eb10bf390418242db1e924c1d8f61ca41cfe90574b4a1b5a82e1d879468"
FIXED_EXE = "7e83d43c39db5d06c9888361a7ba8d0f825e57253a87569ff5f6a0e8a7a746ac"
OLD_EXE = "4dc99d5089fce42f3899fbbc3b97c01202776530620c2a2ea591f5075ce934f3"
TYPING_SHA = "262a264357582a0f87f81e27e2751990890d1c24f36fea2fe018a2198e05a621"
ENGLISH_SHA = "1ba172f477005a57a01132e42042e54a5d1454f5b7361ceba9cab8b36a715b58"
ORIGINAL = ("control_one", "control_two", "control_noncharacters", "enhanced_functions",
            "alt_one", "alt_language", "alt_zero", "alt_modulo", "alt_release", "alt_overlap",
            "alt_interruption", "alt_tab", "control_valid")


def load_records():
    raw = (EVIDENCE / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA, "BIOS menu evidence manifest changed")
    manifest = json.loads(raw)
    require(manifest["schema"] == 1 and manifest["whole_game_parity"] is False and
            manifest["manual_input"] is False, "BIOS menu evidence scope")
    require(sha((ROOT / "LEZAC.EXE").read_bytes()) == manifest["original_exe_sha256"], "original executable changed")
    for name, digest in manifest["files"].items():
        require("/" not in name and "\\" not in name, "evidence path escaped")
        require(sha((EVIDENCE / name).read_bytes()) == digest, "evidence changed: " + name)
    records = {}
    require(len(manifest["cases"]) == 20 and len(manifest["images"]) == 6 and
            len(manifest["files"]) == 33, "BIOS evidence inventory")
    for name, item in manifest["cases"].items():
        require(item["record"] in manifest["files"] and item["source"] in manifest["files"], "missing pinned source")
        record = json.loads((EVIDENCE / item["record"]).read_bytes())
        field = "harness_sha256" if "scenario" in record else "observer_sha256"
        require(sha(gzip.decompress((EVIDENCE / item["source"]).read_bytes())) == record[field],
                "executed observer missing: " + name)
        require(record["status"] == item["status"], "raw status changed: " + name)
        records[name] = record
    for item in manifest["images"].values():
        require(item["file"] in manifest["files"] and any(row["name"] == item["capture"] and
                row["pixel_sha256"] == item["pixel_sha256"] for row in records[item["case"]]["captures"]),
                "image not bound to executed record")
    require(manifest["images"]["original_english"]["pixel_sha256"] == ENGLISH_SHA and
            manifest["images"]["cpp_english"]["pixel_sha256"] == ENGLISH_SHA, "paired completed English pixels")
    require(sha(gzip.decompress((EVIDENCE / "producer.py.gz").read_bytes())) == manifest["producer_sha256"],
            "packaging source changed")
    return records


def queue(state):
    return state["bios_buffer_head_41a"], state["bios_buffer_tail_41c"]


def events(record):
    return [row["after_input_bytes"] for row in record["events"] if "after_input_bytes" in row]


def validate(records):
    for name in ORIGINAL:
        row = records[name]
        require(row["status"] == "observed" and row["version"] == "original" and row["audio"] == "dummy" and
                row["gameplay_seeded"] is False and row["delay_gates"] is False and row["physical_keys"] is True and
                row["manual_input"] is False, "original scope: " + name)
        require(row["hooks_restored"] == 1 and row["child_exit_code"] == 0 and
                row["positive_selection_control"] is True and row["selection_control_bytes"]["player_count_79b8"] == 1,
                "original cleanup or fresh selection control: " + name)
        require(len([x for x in row["captures"] if x["name"].startswith("after-choice-")]) == 5,
                "missing post-input observations: " + name)
    for name in ("control_one", "control_noncharacters", "alt_zero", "alt_tab", "enhanced_functions"):
        row = records[name]
        require(row["stage"] == "typing" and row["captures"][0]["pixel_sha256"] == TYPING_SHA and
                all(not x["full_menu"] for x in row["captures"] if x["name"].startswith("after-choice-")),
                "noncharacter skipped original typing: " + name)
        require(row["after_input_bytes"]["last_menu_character_2058"] == 48, "noncharacter reached CRT")
        if name != "enhanced_functions":
            require(queue(row["before_input_bytes"]) == queue(row["after_input_bytes"]), "unbuffered queue changed")
    require(len(events(records["control_noncharacters"])) == 15, "Control noncharacter inventory")
    require(len(events(records["enhanced_functions"])) == 8 and
            records["enhanced_functions"]["queue_change_allowed"] is True and
            queue(records["enhanced_functions"]["after_input_bytes"]) !=
            queue(records["enhanced_functions"]["before_input_bytes"]), "enhanced BIOS/CRT distinction lost")
    for name, character in (("control_two", 3), ("control_valid", 31), ("alt_one", 1)):
        row = records[name]
        require(row["after_input_bytes"]["last_menu_character_2058"] == character and
                all(x["full_menu"] for x in row["captures"] if x["name"].startswith("after-choice-") and
                    x["name"] != "after-choice-0.05"), "valid character did not skip typing: " + name)
    require([x["last_menu_character_2058"] for x in events(records["control_valid"])] == [30, 31],
            "Ctrl+6/minus characters changed")
    require([x["bios_alt_accumulator_419"] for x in events(records["alt_zero"])] == [0, 0, 0, 0, 2, 25, 0, 0],
            "zero or modulo-256 accumulation changed")
    for name, digits in (("alt_language", [0, 1, 10, 108]), ("alt_modulo", [0, 3, 36, 108])):
        row = records[name]
        states = events(row)
        require([x["bios_alt_accumulator_419"] for x in states[:-1]] == digits and
                all(queue(x) == queue(row["before_input_bytes"]) for x in states[:-1]), "digits buffered before release")
        require(states[-1]["bios_alt_accumulator_419"] == 0 and states[-1]["last_menu_character_2058"] == 108 and
                states[-1]["language_79cc"] == 1 and any(x["english_full"] for x in row["captures"]),
                "Alt release failed to expose lowercase language command")
    states = events(records["alt_release"])
    require(states[4]["bios_alt_accumulator_419"] == 108 and states[5]["bios_flags_417"] == 0 and
            states[5]["last_menu_character_2058"] == 108 and queue(states[5]) == queue(states[6]),
            "first Alt release or duplicate suppression changed")
    states = events(records["alt_overlap"])
    require(all(x["bios_flags_417"] == 0 and x["bios_alt_accumulator_419"] == 0 for x in states[5:]) and
            records["alt_overlap"]["after_input_bytes"]["language_79cc"] == 1, "overlapping Alt flag was retained")
    states = events(records["alt_interruption"])
    require(states[2]["bios_alt_accumulator_419"] == 1 and states[2]["last_menu_character_2058"] == 30 and
            states[-1]["last_menu_character_2058"] == 108, "ordinary Alt character cleared decimal accumulator")
    for name in ("control_two_transitional_failure", "alt_chord_failure", "cpp_control_one_negative", "cpp_cleanup_failure"):
        require(records[name]["status"] == "failed", "failed attempt was promoted: " + name)
    require(records["control_two_transitional_failure"]["captures"][1]["full_menu"] is False and
            records["control_two_transitional_failure"]["after_input_bytes"]["last_menu_character_2058"] == 3,
            "transitional failure evidence lost")
    require(events(records["alt_chord_failure"])[2]["bios_flags_417"] == 0, "synthetic Alt break was concealed")
    require(records["cpp_control_one_negative"]["exe_sha256"] == OLD_EXE and
            records["cpp_control_one_negative"]["error"] == "probe key skipped menu typing", "negative control changed")
    for name in ("cpp_noncharacters", "cpp_intro", "cpp_composition"):
        row = records[name]
        require(row["status"] == "observed" and row["exe_sha256"] == FIXED_EXE and row["child_exit_code"] == 0 and
                row["audio"] == "dummy" and row["normal_entry_point"] is True and row["gameplay_seeded"] is False and
                row["startup_timing_gated"] is False and row["whole_game_parity"] is False and
                row["physical_keys"] is True and row["manual_input"] is False, "normal C++ physical scope: " + name)


def main():
    records = load_records()
    validate(records)
    mutations = [
        lambda r: r["control_one"]["after_input_bytes"].__setitem__("bios_buffer_tail_41c", 32),
        lambda r: r["alt_language"]["events"][2]["after_input_bytes"].__setitem__("bios_alt_accumulator_419", 0),
        lambda r: r["alt_release"]["events"][5]["after_input_bytes"].__setitem__("bios_flags_417", 8),
        lambda r: r["control_two_transitional_failure"].__setitem__("status", "observed"),
        lambda r: r["alt_chord_failure"].__setitem__("status", "observed"),
        lambda r: r["cpp_cleanup_failure"].__setitem__("status", "observed"),
        lambda r: r["cpp_composition"].__setitem__("whole_game_parity", True),
    ]
    for mutate in mutations:
        changed = copy.deepcopy(records)
        mutate(changed)
        try:
            validate(changed)
        except RuntimeError:
            continue
        raise RuntimeError("BIOS menu evidence mutation was accepted")
    print("bios_menu_evidence=ok originals=13 failed_records=4 cpp_physical_cases=3 sources=6 images=6"
          " rejection_mutations=7 whole_game_parity=0 manual_input=0")


if __name__ == "__main__":
    main()
