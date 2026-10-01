#!/usr/bin/env python3
"""Check full-health controlled boss defeat and continuous production replay."""

import argparse
import ast
import gzip
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from check_boss_active_combat_evidence import decode_view, fields, require, sha

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "docs/recovery/evidence/boss_extended_combat_20261001"
MANIFEST_SHA = "40c67746a7c341548a1c4c491472996bb13d681b9a51e89ff65b7b1b523c51f8"
TRACE_SHA = "1e5425c095ac833b577647d63b6aebd3a8803fbc6eef348ac7903f951ee27ce9"
VIEWS = (0, 1, 15, 16, 20, 39, 59, 99, 199, 399, 599, 799, 1599, 2399, 3199)


def actors(tick):
    return [] if tick["actors"] == "-" else [bytes.fromhex(record.split(":")[0])
                                             for record in tick["actors"].split(",")]


def validate_observer_variant(original):
    template = original["sources"]["tools/capture_original_boss_defeat.py"]
    generated = original["sources"]["generated/extended_boss_observer.py"]
    template_tree = ast.parse(gzip.decompress((EVIDENCE / template["file"]).read_bytes()))
    proof = json.loads(gzip.decompress((EVIDENCE / "observer_ast.json.gz").read_bytes()))
    require(proof["schema"] == 1 and proof["source_sha256"] == generated["sha256"] and
            proof["python_version"][:2] == [3, 12], "observer AST provenance")

    def decode(node):
        if isinstance(node, list):
            return [decode(value) for value in node]
        if not isinstance(node, dict):
            require(node is None or isinstance(node, (str, int, float, bool)), "invalid AST value")
            return node
        if set(node) == {"bytes"}:
            return bytes.fromhex(node["bytes"])
        require(set(node) == {"type", "fields"}, "invalid AST node")
        kind = getattr(ast, node["type"], None)
        require(isinstance(kind, type) and issubclass(kind, ast.AST), "unknown AST node")
        arguments = dict(node["fields"])
        # Python 3.12 adds empty type-parameter fields; no captured function uses them.
        if "type_params" not in kind._fields and arguments.get("type_params") == []:
            del arguments["type_params"]
        require(set(arguments) == set(kind._fields), "AST field mismatch")
        return kind(**{key: decode(value) for key, value in arguments.items()})

    generated_tree = decode(proof["tree"])
    if sys.version_info >= (3, 12):
        require(ast.dump(generated_tree) == ast.dump(ast.parse(gzip.decompress((EVIDENCE / generated["file"]).read_bytes()))),
                "observer AST not bound to source")
    changes = dict(root=0, views=0, samples=0, summary=0, header=0)

    class Restore(ast.NodeTransformer):
        def visit_Assign(self, node):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if names == ["ROOT"]:
                replacement = next(item.value for item in template_tree.body if isinstance(item, ast.Assign)
                                   and [getattr(target, "id", None) for target in item.targets] == ["ROOT"])
                node.value = replacement
                changes["root"] += 1
            elif names == ["COMBAT_VIEWS"]:
                require(ast.literal_eval(node.value) == VIEWS, "generated views")
                node.value = next(item.value for item in template_tree.body if isinstance(item, ast.Assign)
                                  and [getattr(target, "id", None) for target in item.targets] == ["COMBAT_VIEWS"])
                changes["views"] += 1
            elif len(node.targets) == 1 and isinstance(node.targets[0], ast.Tuple) and \
                    [getattr(value, "id", None) for value in node.targets[0].elts] == ["cases", "samples", "views"] and \
                    isinstance(node.value, ast.Tuple) and isinstance(node.value.elts[1], ast.Constant) and \
                    node.value.elts[1].value == 3200:
                node.value.elts[1] = ast.Constant(800)
                changes["samples"] += 1
            return self.generic_visit(node)

        def visit_IfExp(self, node):
            if isinstance(node.test, ast.Attribute) and isinstance(node.test.value, ast.Name) and \
                    node.test.value.id == "args" and node.test.attr == "active_combat" and \
                    isinstance(node.body, ast.Constant) and node.body.value == 3200:
                node.body = ast.Constant(800)
                changes["summary"] += 1
            return self.generic_visit(node)

        def visit_Constant(self, node):
            header = ("capture=boss_extended_combat_candidate_v1 level=7 temp_copy=1 seeded_case_boundary=1"
                      " head_health_modified=0 seeded_bomb=0 latched_input=1 physical_keyboard=0"
                      " per_tick_actor_seed=0 natural_campaign=0")
            if node.value == header:
                node.value = header.replace("boss_extended_combat_candidate_v1", "boss_active_combat_original_v1")
                changes["header"] += 1
            return node

    restored = Restore().visit(generated_tree)
    require(changes == dict(root=1, views=1, samples=1, summary=1, header=1) and
            ast.dump(restored) == ast.dump(template_tree), "observer changes exceed five parameters")


def validate_trace(raw):
    rows = [row for row in raw.decode("ascii").splitlines() if row and not row.startswith("#")]
    require(fields(rows[0]) == dict(capture="boss_extended_combat_candidate_v1", level="7", temp_copy="1",
            seeded_case_boundary="1", head_health_modified="0", seeded_bomb="0", latched_input="1",
            physical_keyboard="0", per_tick_actor_seed="0", natural_campaign="0"), "extended scope")
    require(rows[-2:] == ["end samples=3200", "complete cases=1 samples=3200 views=15"], "incomplete extended combat")
    cases = [fields(row) for row in rows if row.startswith("case ")]
    require(len(cases) == 1 and cases[0]["name"] == "latched_fire_even" and cases[0]["frame"] == "100", "case")
    initial = cases[0]
    head = actors(initial)[0]
    require(len(head) == 38 and head[0] == 30 and head[2] == 1 and head[36] == 10 and
            initial["count"] == "7" and initial["ammo"] == "c8140600c8140600", "full-health seed")
    ticks = [fields(row) for row in rows if row.startswith("tick ")]
    require(len(ticks) == 3200, "tick count")
    for sample, tick in enumerate(ticks):
        require(int(tick["sample"]) == sample and int(tick["frame"]) == 101 + sample, "tick continuity")
        require(len(tick["ammo"]) == 16 and tick["weapons"] == "0101" and len(tick["latches"]) == 4 and
                tick["resets"] == "0" and tick["active_players"] == "1", "inventory/lifecycle")
        require(tick["control"] in ("idle", "fire"), "control")
        if tick["input_regs"] != "-":
            require(tick["normalized"] == ("0000000100" if tick["control"] == "fire" else "0000000000"), "normalized input")
    keys = [fields(row) for row in rows if row.startswith("key ")]
    expected = [(sample - 1, sample, value) for shot in range(133)
                for sample, value in ((16 + 24 * shot, "01"), (17 + 24 * shot, "00"))]
    require(len(keys) == len(expected), "key count")
    for key, (previous, sample, value) in zip(keys, expected):
        require(int(key["sample"]) == previous and int(key["next_sample"]) == sample and
                key["address"] == "1b7b" and key["value"] == value and key["after_render"] == "1" and
                key["before"] == ticks[previous]["latches"][:2], "key boundary")
    views = [fields(row) for row in rows if row.startswith("view ")]
    require(tuple(int(view["sample"]) for view in views) == VIEWS, "view coverage")
    for view in views:
        require(sha(decode_view(view["pixels"])) == view["indexed_sha256"], "indexed view hash")
    boundaries = [fields(row) for row in rows if row.startswith("boundary ")]
    require(len(boundaries) == 140 and all(row["stage"] == "fallback_increment" for row in boundaries), "wait coverage")
    require(sum(ticks[i - 1]["player_state"] == "2" and ticks[i]["player_state"] == "1" for i in range(1, 3200)) == 10
            and ticks[-1]["lives"] == "89" and ticks[-1]["ammo"] == "68140600c8140600"
            and sum(tick["control"] == "fire" for tick in ticks) == 96, "combat coverage")
    require(all([actor[0] for actor in actors(tick)[:7]] == [30, 31, 31, 31, 31, 31, 31]
                for tick in ticks[:1714]), "premature conversion")
    converted = actors(ticks[1714])[:7]
    require([actor[0] for actor in converted] == [14] * 7 and converted[0][2] == 60 and converted[0][36] == 255
            and [actor[2] for actor in converted[1:]] == [43, 44, 41, 41, 40, 43], "fatal conversion")
    require(all(actor[0] not in (14, 30, 31) for tick in ticks[1833:] for actor in actors(tick)), "boss cleanup")
    return {int(view["sample"]): view for view in views}


def load_evidence():
    manifest_raw = (EVIDENCE / "manifest.json").read_bytes()
    require(sha(manifest_raw) == MANIFEST_SHA, "extended manifest changed")
    manifest = json.loads(manifest_raw)
    require(manifest["schema"] == 1 and all(manifest[key] is False for key in
            ("whole_game_parity", "natural_campaign", "physical_keyboard")), "manifest scope")
    require(sha((ROOT / "LEZAC.EXE").read_bytes()) == manifest["original_exe_sha256"], "original executable changed")
    for name, digest in manifest["files"].items():
        require(Path(name).name == name and "/" not in name and "\\" not in name, "evidence path")
        require(sha((EVIDENCE / name).read_bytes()) == digest, "evidence changed: " + name)
    fixture = ROOT / "tests/fixtures/boss_extended_combat_original_level7.txt.gz"
    require(manifest["fixture"] == fixture.relative_to(ROOT).as_posix(), "fixture path")
    packed = fixture.read_bytes()
    raw = gzip.decompress(packed)
    require(sha(packed) == manifest["fixture_sha256"] and sha(raw) == manifest["trace_sha256"] == TRACE_SHA, "fixture changed")
    original = json.loads((EVIDENCE / "original.json").read_bytes())
    require(original["status"] == "captured_candidate" and original["observer_exit_code"] == 0 and
            original["hooks_restored"] is True and original["audio"] == "dummy" and
            original["observed_samples"] == 3200 and original["head_before_warmup"]["hp"] == 10 and
            original["head_before_warmup"]["lives"] == 1 and len(original["owned_dosbox"]) == 1 and
            all(child["returncode"] == 0 for child in original["owned_dosbox"]), "original outcome")
    require(all(original[key] is False for key in ("production_replay", "whole_game_parity", "natural_campaign",
                "physical_keyboard", "head_health_modified", "seeded_bomb")), "capture-time scope changed")
    require(original["transformations"] == dict(root=1, views=1, samples=1, summary=1, header=1)
            and len(original["sources"]) == 10, "observer parameter/source coverage")
    for name, item in original["sources"].items():
        source = gzip.decompress((EVIDENCE / item["file"]).read_bytes())
        require(sha(source) == item["sha256"], "executed source changed")
        if name.startswith("tools/"):
            require(sha((ROOT / name).read_bytes().replace(b"\r\n", b"\n")) == manifest["sources_lf"][name], "capture source drift")
    validate_observer_variant(original)
    failed = json.loads((EVIDENCE / "failed-replay.json").read_bytes())
    require(failed["status"] == "failed" and failed["exit_code"] == 1 and failed["audio"] == "dummy" and
            "sample=1793: route effect mismatch" in failed["stderr"] and
            sha(gzip.decompress((EVIDENCE / "failed_source.cpp.gz").read_bytes())) == failed["source_sha256"], "failed diagnostic provenance")
    cpp = json.loads((EVIDENCE / "cpp.json").read_bytes())
    require(cpp["status"] == "passed" and cpp["exit_code"] == 0 and cpp["audio"] == "dummy" and
            cpp["production_replay"] is True and cpp["whole_game_parity"] is False and
            sha(gzip.decompress((EVIDENCE / "cpp_source.cpp.gz").read_bytes())) == cpp["source_sha256"], "archived replay outcome/source")
    require(sha(gzip.decompress((EVIDENCE / "producer.py.gz").read_bytes())) == manifest["producer_sha256"], "producer changed")
    require(sha(gzip.decompress((EVIDENCE / "observer_ast_producer.py.gz").read_bytes())) ==
            manifest["observer_ast_producer_sha256"], "AST producer changed")
    views = validate_trace(raw)
    palette = (ROOT / "BOMPAL.PAL").read_bytes()
    for sample in (1599, 2399, 3199):
        rgb = bytearray()
        for value in decode_view(views[sample]["pixels"]):
            j = value - 176
            color = (j * 43 // 38, j * 23 // 38, 14 - j * 12 // 38) if 176 <= value <= 214 else palette[3 * value:3 * value + 3]
            rgb.extend(((v << 2) | (v >> 4)) & 255 for v in color)
        for version in ("original", "cpp"):
            name = f"{version}_{sample}"
            ppm = gzip.decompress((EVIDENCE / (name + ".ppm.gz")).read_bytes())
            require(ppm == b"P6\n312 152\n255\n" + rgb and sha(rgb) == manifest["images"][name], "preview not bound to indexed view")
    return raw


def mutations(raw):
    text = raw.decode("ascii")
    yield text.rsplit("complete ", 1)[0], "missing completion"
    for old, new in (("head_health_modified=0", "head_health_modified=1"),
                     ("physical_keyboard=0", "physical_keyboard=1"),
                     ("boss_extended_combat_candidate_v1", "boss_active_combat_original_v1"),
                     ("key sample=15 next_sample=16", "key sample=15 next_sample=17"),
                     ("end samples=3200", "end samples=800")):
        require(old in text, "mutation target missing")
        yield text.replace(old, new, 1), ""
    rows = text.splitlines()
    for sample, key, value in ((1714, "rng", "00000000"), (2399, "map", "-"),
                                (3199, "ammo", "69140600c8140600"), (1714, "count", "13")):
        index = next(i for i, row in enumerate(rows) if row.startswith(f"tick sample={sample} "))
        changed = list(rows)
        old = key + "=" + fields(rows[index])[key]
        changed[index] = rows[index].replace(old, key + "=" + value)
        yield "\n".join(changed) + "\n", ""
    # The retained visual slot is deliberately not actor_index + 2 after conversion.
    for prefix, actor_index, offset, value, expected in (("case ", 0, 2, 0, "sample=0: head health seed"),
                ("case ", 0, 36, 0, "sample=0: head health seed"),
                ("tick sample=1714 ", 0, 0, 30, "sample=1714: actor constructor mismatch"),
                ("tick sample=1714 ", 0, 2, 59, "sample=1714: defeat conversion/countdown mismatch"),
                ("tick sample=1793 ", 5, 1, 7, "sample=1793: visual slot/order mismatch"),
                ("tick sample=1793 ", 5, 2, 17, "sample=1793: route effect mismatch")):
        index = next(i for i, row in enumerate(rows) if row.startswith(prefix))
        original = fields(rows[index])["actors"]
        records = original.split(",")
        actor, visual = records[actor_index].split(":")
        actor = bytearray.fromhex(actor)
        require(actor[offset] != value, "mutation unchanged")
        actor[offset] = value
        records[actor_index] = actor.hex() + ":" + visual
        changed = list(rows)
        changed[index] = rows[index].replace("actors=" + original, "actors=" + ",".join(records))
        yield "\n".join(changed) + "\n", expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path)
    args = parser.parse_args()
    raw = load_evidence()
    if not args.exe:
        print("boss_extended_combat_evidence=ok samples=3200 views=15 shots=96 reentries=10 keys=266 defeat=1714 cleanup=1833 sealed_replay=1 live_replay=0 whole_game_parity=0")
        return
    environment = os.environ.copy()
    environment.update(SDL_AUDIODRIVER="dummy", SDL_VIDEODRIVER="dummy")
    with tempfile.TemporaryDirectory(prefix="lezac-boss-extended-combat-") as directory:
        path = Path(directory) / "trace.txt"

        def run(data):
            path.write_bytes(data)
            return subprocess.run([str(args.exe.resolve()), "--debug-boss-extended-combat-original", str(path)],
                                  cwd=ROOT, env=environment, capture_output=True, text=True, timeout=90)

        for data in (raw, raw.replace(b"\n", b"\r\n")):
            result = run(data)
            require(result.returncode == 0 and "views=15 compared_pixels=711360 different_pixels=0" in result.stdout and
                    "shots=96 reentries=10" in result.stdout and "defeat_sample=1714 cleanup_sample=1833" in result.stdout and
                    "whole_game_parity=0" in result.stdout, "production replay failed: " + result.stderr)
        count = 0
        for data, expected in mutations(raw):
            result = run(data.encode("ascii"))
            require(result.returncode != 0 and "boss-continuous" in result.stderr and expected in result.stderr,
                    "mutation accepted or unrelated failure: " + result.stderr)
            count += 1
    print(f"boss_extended_combat_fixture=ok samples=3200 views=15 shots=96 reentries=10 keys=266 newline_variants=2 mutations_rejected={count} silent_children=1 whole_game_parity=0")


if __name__ == "__main__":
    main()
