#!/usr/bin/env python3
"""Validate the scope and provenance of original main-menu character observations."""

import copy
import gzip
import json

from check_main_menu_fixture import ROOT, require, sha

EVIDENCE = ROOT / "docs/recovery/evidence/main_menu_characters_20261001"
MANIFEST_SHA = "e027ea831d019a186c3432162b0adafdaf959d93d7fb4adc88c8719f84ea35d1"
MENU_SHA = "a6e2f9867be3fac329c8862529e751aedffd76f84d846c1c70700eb42bb3a914"
OLD_EXE = "57da6e289bb8f02b3944b25910ac7ef3edc215b18a37569cb5fef6d7edad2a7a"
XOR_EXE = "9a37e3a064f6e9dc947c18ce2a085132551f1f1438e95f325b4f528ec4caf92d"
FIXED_EXE = "4dc99d5089fce42f3899fbbc3b97c01202776530620c2a2ea591f5075ce934f3"
ORIGINAL_CASES = {
    "shift_l": (76, 0, "ignored"), "caps_l": (None, 0, "ignored"),
    "shift_one": (33, 0, "ignored"), "ctrl_l": (12, 0, "ignored"),
    "caps_shift_l": (108, 0, "language"), "alt_f5": (108, 0, "language"),
    "kp1_off": (79, 0, "ignored"), "kp2_off": (80, 0, "ignored"),
    "kp1_num": (49, 1, "intro"), "kp1_shift": (49, 1, "intro"),
    "kp1_num_shift": (49, 1, "intro"), "kp2_num": (50, 2, "intro"),
    "kp2_shift": (50, 2, "intro"), "kp2_num_shift": (50, 2, "intro"),
    "alt_f2": (105, 0, "page"), "alt_three": (122, 0, "page"),
}


def load_records():
    raw = (EVIDENCE / "manifest.json").read_bytes()
    require(sha(raw) == MANIFEST_SHA, "character evidence manifest changed")
    manifest = json.loads(raw)
    require(manifest["schema"] == 1 and manifest["whole_game_parity"] is False, "evidence scope")
    require(sha((ROOT / "LEZAC.EXE").read_bytes()) == manifest["original_exe_sha256"], "original executable changed")
    records, sources = {}, set()
    for name, digest in manifest["files"].items():
        require("/" not in name and "\\" not in name, "evidence path escaped")
        data = (EVIDENCE / name).read_bytes()
        require(sha(data) == digest, "character evidence changed: " + name)
        if name.endswith(".json"):
            records[name[:-5]] = json.loads(data)
        elif name.endswith(".py.gz"):
            sources.add(sha(gzip.decompress(data)))
    require(len(records) == 23 and len(sources) == 9, "character evidence inventory")
    for name, record in records.items():
        field = "harness_sha256" if name.startswith("matrix_") else "observer_sha256"
        require(record[field] in sources, "missing exact executed source: " + name)
    return records


def validate(records):
    for name, (character, players, outcome) in ORIGINAL_CASES.items():
        record = records[name + "_original"]
        require(record["status"] == "observed" and record["version"] == "original", "original observation: " + name)
        require(record["audio"] == "dummy" and record["gameplay_seeded"] is False and
                record["delay_gates"] is False and record["physical_keys"] is True and
                record["manual_input"] is False, "original scope: " + name)
        require(record["hooks_restored"] == 1 and record["child_exit_code"] == 0, "original cleanup: " + name)
        require(record["captures"][0]["pixel_sha256"] == MENU_SHA, "ready original menu: " + name)
        choices = [row for row in record["captures"] if row["name"].startswith("after-choice-")]
        require(len(choices) == 5, "post-key observations: " + name)
        if character is not None:
            state = record["after_input_bytes"]
            require((state["last_menu_character_2058"], state["player_count_79b8"]) ==
                    (character, players), "original character/players: " + name)
        if outcome == "ignored":
            require(all(row["full_menu"] and row["pixel_sha256"] == MENU_SHA for row in choices),
                    "ignored original frames: " + name)
        elif outcome == "language":
            require(any(row["name"] == "english-ready-control" and row["english_full"]
                        for row in record["captures"]), "language control: " + name)
        elif outcome == "intro":
            require(choices[-1]["intro"] and not choices[-1]["full_menu"], "intro selection: " + name)
        else:
            require(not any(choices[-1][field] for field in ("intro", "full_menu", "english_full")) and
                    record["positive_selection_control"] is False and record["page_navigation_observed"] is False,
                    "page observation scope: " + name)
        if outcome != "page":
            require(record["positive_selection_control"] is True, "selection control: " + name)
        if name in {"kp1_shift", "kp1_num_shift", "kp2_shift", "kp2_num_shift"}:
            code = "raw:87" if name.startswith("kp1") else "raw:88"
            event = next(row for row in record["events"] if row["key"] == code)
            flags = 34 if "num_shift" in name else 2
            require(event["after_input_bytes"]["bios_flags_417"] == flags, "held keypad modifiers: " + name)

    wrong = records["kp1_shift_original_wrong_expectation"]
    require(wrong["status"] == "failed" and wrong["error"] == "probe keys changed the ready main menu" and
            wrong["after_input_bytes"]["last_menu_character_2058"] == 49 and wrong["captures"][-1]["intro"],
            "wrong original expectation was relabeled")
    startup = records["kp2_num_shift_original_startup_failure"]
    require(startup["status"] == "failed" and startup["error"] == "original overlaps resident allocation" and
            startup["events"] == [] and startup["captures"] == [] and startup["hooks_restored"] == 0,
            "startup failure was promoted")
    old = records["shift_l_cpp_negative"]
    require(old["status"] == "failed" and old["exe_sha256"] == OLD_EXE and not old["captures"][-1]["full_menu"],
            "uppercase negative evidence changed")
    negative = records["kp1_num_shift_cpp_negative"]
    require(negative["status"] == "failed" and negative["exe_sha256"] == XOR_EXE and
            all(row["full_menu"] for row in negative["captures"]), "keypad XOR negative evidence changed")
    fixed = records["kp1_num_shift_cpp_fixed"]
    require(fixed["status"] == "observed" and fixed["exe_sha256"] == FIXED_EXE and
            fixed["captures"][-1]["intro"] and fixed["child_exit_code"] == 0, "corrected physical keypad evidence")
    matrix = records["matrix_cpp_fixed"]
    require(matrix["status"] == "observed" and matrix["exe_sha256"] == FIXED_EXE and
            matrix["audio"] == "dummy" and matrix["gameplay_seeded"] is False and
            matrix["whole_game_parity"] is False and matrix["child_exit_code"] == 0 and
            len(matrix["captures"]) == 14 and matrix["ignored_choices"] == 25 and matrix["held_return_cases"] == 2,
            "physical matrix scope")
    for field in ("caps_shift_selected", "alt_f5_selected", "keypad_off_ignored", "keypad_on_selected",
                  "keypad_num_shift_selected", "keypad_shift_selected"):
        require(matrix[field] is True, "physical matrix missing " + field)
    matrix_negative = records["matrix_cpp_xor_negative"]
    require(matrix_negative["status"] == "failed" and matrix_negative["exe_sha256"] == XOR_EXE and
            matrix_negative["error"] == "fresh keypad selection did not leave the menu: num-shift",
            "physical matrix lost its negative control")


def main():
    records = load_records()
    validate(records)
    mutations = [
        lambda rows: rows["shift_l_original"]["after_input_bytes"].__setitem__("last_menu_character_2058", 108),
        lambda rows: rows["shift_l_original"].__setitem__("gameplay_seeded", True),
        lambda rows: rows["kp1_num_shift_original"]["events"][2]["after_input_bytes"].__setitem__("bios_flags_417", 32),
        lambda rows: rows["kp1_shift_original_wrong_expectation"].__setitem__("status", "observed"),
        lambda rows: rows["kp1_num_shift_cpp_negative"].__setitem__("status", "observed"),
        lambda rows: rows["shift_l_original"]["captures"][0].__setitem__("pixel_sha256", "0" * 64),
    ]
    for mutate in mutations:
        changed = copy.deepcopy(records)
        mutate(changed)
        try:
            validate(changed)
        except RuntimeError:
            continue
        raise RuntimeError("character evidence mutation accepted")
    print("main_menu_character_evidence=ok original_cases=16 failed_records=5 mutations=6 whole_game_parity=0")


if __name__ == "__main__":
    main()
