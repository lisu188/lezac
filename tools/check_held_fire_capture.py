#!/usr/bin/env python3
"""Validate a completed physical-input observation without claiming C++ parity."""

import argparse
import hashlib
from pathlib import Path
import re

import capture_original_held_fire as capture


FIELDS = {
    "capture": "schema mode level physical_keys gameplay_seeded main_loop_wait irq_masked_during_record exe_sha256 hooks slots stride resident mcb source_sha256 irq_sha256 frame_sha256 dosbox_sha256",
    "sample": "seq frame makes breaks hardware ammo selected p1 visual flags gate fallback count level regs",
    "event": "after_seq kind key reason",
    "ack": "seq after_seq kind reason makes breaks",
    "screenshot": "after_seq label frame_alignment normalized_palette indexed_sha256",
    "observed": "samples dying_seq waiting_seq resumed_seq makes breaks",
    "restored": "hook bytes",
    "complete": "samples dying_seq waiting_seq resumed_seq makes breaks hooks_restored game_process_exited whole_game_parity",
}


def parse(text):
    records = []
    objective_context = False
    for line in text.splitlines():
        parts = line.split()
        if not parts or parts[0] not in FIELDS:
            raise RuntimeError("unknown or empty capture record")
        tag, values = parts[0], {}
        for field in parts[1:]:
            key, separator, value = field.partition("=")
            if not separator or not value or key in values:
                raise RuntimeError("invalid or duplicate capture field")
            values[key] = value
        if not records and tag == "capture":
            objective_context = values.get("schema") == "held_fire_irq_v4"
        expected_fields = set(FIELDS[tag].split())
        if objective_context and tag == "capture":
            expected_fields.add("death_sha256")
        if objective_context and tag == "sample":
            expected_fields.update(capture.CONTEXT_FIELDS)
        if set(values) != expected_fields:
            raise RuntimeError(f"invalid {tag} fields")
        records.append((tag, values))
    return records


def validate_text(text):
    records = parse(text)
    if not records or records[0][0] != "capture" or records[-1][0] != "complete":
        raise RuntimeError("capture is incomplete")
    header = records[0][1]
    objective_context = header["schema"] == "held_fire_irq_v4"
    expected = dict(schema="held_fire_irq_v4" if objective_context else "held_fire_irq_v3", level="1", physical_keys="1", gameplay_seeded="0",
                    main_loop_wait="0", irq_masked_during_record="1", exe_sha256=capture.EXE_SHA256,
                    hooks="10a1,7a57,30f6" if objective_context else "10a1,7a57", slots="16", stride="128")
    if any(header[key] != value for key, value in expected.items()):
        raise RuntimeError("capture provenance contract mismatch")
    image = (capture.ROOT / "LEZAC.EXE").read_bytes()[0x770:]
    stubs = [("irq", capture.irq_stub(image)), ("frame", capture.frame_stub(image, objective_context))]
    if objective_context:
        stubs.append(("death", capture.death_stub(image)))
    for name, stub in stubs:
        if header[name + "_sha256"] != hashlib.sha256(stub).hexdigest():
            raise RuntimeError("instrumentation stub identity mismatch")
    for key in ("source_sha256", "dosbox_sha256"):
        if not re.fullmatch("[0-9a-f]{64}", header[key]):
            raise RuntimeError("missing capture source identity")
    mcb = bytes.fromhex(header["mcb"])
    if len(mcb) != 16 or mcb[0] not in (ord("M"), ord("Z")) or int.from_bytes(mcb[1:3], "little") != int(header["resident"], 16):
        raise RuntimeError("resident ownership mismatch")
    if int.from_bytes(mcb[3:5], "little") < capture.RESIDENT_PARAGRAPHS:
        raise RuntimeError("undersized resident allocation")
    samples, events, screenshots, restored = [], [], [], []
    pending = observed = None
    for tag, fields in records[1:-1]:
        if observed is not None and tag != "restored":
            raise RuntimeError("observation continued after its summary")
        if tag == "sample":
            row = {}
            for key, value in fields.items():
                row[key] = bytes.fromhex(value) if key in ("hardware", "ammo", "selected", "p1", "visual", "flags", "regs") else int(value)
            if len(row["ammo"]) != 8 or len(row["selected"]) != 2 or len(row["visual"]) != 8 or not 0 <= row["count"] <= 30:
                raise RuntimeError("invalid original table projection")
            samples.append(row)
        elif tag == "event":
            if pending is not None or int(fields["after_seq"]) != len(samples) or fields["key"] != "n":
                raise RuntimeError("input command ordering mismatch")
            pending = dict(fields, after_seq=int(fields["after_seq"]), ack_seq=0)
            events.append(pending)
        elif tag == "ack":
            if pending is None or not samples or int(fields["seq"]) != len(samples):
                raise RuntimeError("unexpected input acknowledgement")
            if any(str(pending[key]) != fields[key] for key in ("after_seq", "kind", "reason")):
                raise RuntimeError("input acknowledgement identity mismatch")
            if any(int(fields[key]) != samples[-1][key] for key in ("makes", "breaks")):
                raise RuntimeError("input acknowledgement counter mismatch")
            pending["ack_seq"] = int(fields["seq"])
            pending = None
        elif tag == "screenshot":
            if fields["frame_alignment"] != "0" or fields["normalized_palette"] != "1" or not re.fullmatch("[0-9a-f]{64}", fields["indexed_sha256"]):
                raise RuntimeError("preview overstates capture scope")
            if int(fields["after_seq"]) != len(samples):
                raise RuntimeError("preview observation sequence mismatch")
            screenshots.append(fields["label"])
        elif tag == "observed":
            if pending is not None:
                raise RuntimeError("unacknowledged input at observation end")
            observed = {key: int(value) for key, value in fields.items()}
        elif tag == "restored":
            if observed is None:
                raise RuntimeError("hooks removed before observation ended")
            restored.append(fields)
        else:
            raise RuntimeError("duplicate header or completion")
    result = capture.validate_lifecycle(samples, events, header["mode"])
    if objective_context:
        capture.validate_objective_context(samples)
    if observed != result or screenshots != ["dying", "resumed", "final"]:
        raise RuntimeError("observation summary or preview set mismatch")
    hooks = capture.HOOKS + ((capture.CONTEXT_HOOK,) if objective_context else ())
    expected_restored = [dict(hook=f"{entry:04x}", bytes=image[entry:entry + length].hex())
                         for entry, length, _ in hooks]
    if restored != expected_restored:
        raise RuntimeError("missing or incorrect original hook restoration")
    complete = records[-1][1]
    expected_complete = dict(result, hooks_restored=len(hooks), game_process_exited=1, whole_game_parity=0)
    if complete != {key: str(value) for key, value in expected_complete.items()}:
        raise RuntimeError("completion summary mismatch")
    return dict(result, mode=header["mode"], input_events=len(events), previews=len(screenshots),
                objective_context=int(objective_context), hooks_restored=len(hooks))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    result = validate_text(args.capture.read_text(encoding="ascii"))
    print("held_fire_observation=ok " + " ".join(f"{key}={value}" for key, value in result.items()) +
          " game_process_exited=1 cpp_parity=0")


if __name__ == "__main__":
    main()
