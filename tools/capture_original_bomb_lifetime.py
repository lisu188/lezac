"""Trace preserved bomb-slot bytes through complete original lifetimes and expiry."""
from collections import defaultdict
from datetime import datetime, timezone
import argparse
import itertools
import json
from pathlib import Path
import sys
import traceback

def validate_lifetime_result(report):
    """Reject a lifetime result that contradicts preserved-byte independence."""
    assert not report['preserved_offsets_read'], 'preserved constructor bytes were read'
    assert not report['differential_groups_with_outside_preserved_differences'], \
        'stale slot pattern changed state outside preserved bytes'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-report', type=Path, required=True)
    parser.add_argument('--unicorn-path', type=Path)
    args = parser.parse_args()
    ROOT = args.root.resolve()
    if args.unicorn_path:
        sys.path.insert(0, str(args.unicorn_path.resolve()))
    sys.path.insert(0, str(ROOT / 'tools'))
    from original_bomb_cpu import BombCPU, sha, unicorn
    from unicorn.x86_const import UC_X86_REG_IP, UC_X86_REG_CS, UC_X86_REG_SP, UC_X86_REG_BP, UC_X86_REG_EFLAGS
    from scan_livels_debris_sites import load_levels
    OUT = args.out.resolve()
    assert not OUT.exists()
    report = dict(passed=False, cases=[], original_instructions_patched=False,
        original_calls_stubbed=False, hardware_io_permitted=False, new_native_capture=False,
        natural_stale_slot_reachability_proven=False, compiled_cpp_comparison=False,
        visual_parity_claim=False, sound_parity_claim=False, whole_game_complete=False)

    try:
        native_path = args.native_report.resolve()
        native = json.loads(native_path.read_text())
        assert native['passed'] and native['native_updates'] == 2304
        assert native['native_traces'] == 16 and native['compared_bytes'] == 106720
        assert native['helper_sha256'] == sha(Path(__file__).with_name('original_bomb_cpu.py').read_bytes())
        report['independent_native_crosscheck'] = dict(path=str(native_path), sha256=sha(native_path.read_bytes()),
            native_traces=16, native_updates=2304, compared_bytes=106720, differing_bytes=0)
        shipped = load_levels(ROOT / 'LIVELS.SCH')[0]
        empty = dict(shipped, tiles=[0] * 1980, words=[0] * 1980)
        levels = {'shipped_level1': shipped, 'controlled_empty': empty}
        original = BombCPU(ROOT)
        cpu, data = original.cpu, original.DATA
        slot = data + 0x1bae + 38
        preserved = sorted(set(range(38)) - {0, 1, 2, *range(6, 14), 20, 21, *range(22, 29)})
        reads = defaultdict(set)
        writes = set()
        early_reads = defaultdict(set)

        def observe(uc, access, address, size, value, user):
            for physical in range(max(address, slot), min(address + size, slot + 38)):
                offset = physical - slot
                if access == unicorn.UC_MEM_WRITE:
                    writes.add(offset)
                else:
                    ip = uc.reg_read(UC_X86_REG_IP)
                    reads[offset].add(ip)
                    if offset not in writes:
                        early_reads[offset].add(ip)

        def execute(level, weapon, parity, velocities, stale, traced):
            original.reset(level, weapon, 104, 168, *velocities, visual_cursor=2, stale=stale)
            reads.clear()
            writes.clear()
            early_reads.clear()
            hook = cpu.hook_add(unicorn.UC_HOOK_MEM_READ | unicorn.UC_HOOK_MEM_WRITE,
                                observe, None, slot, slot + 37) if traced else None
            timeline = bytearray()
            instruction_count = 0
            try:
                for step in range(401):
                    actor, visual = original.update(parity + step)
                    timeline.extend(actor + visual)
                    instruction_count += original.instructions
                    if actor[2] == 0:
                        assert '0x175cb' in original.boundaries
                        break
                else:
                    raise AssertionError('bomb failed to expire within its original bounded lifetime')
            finally:
                if hook is not None:
                    cpu.hook_del(hook)
            boundary = [cpu.reg_read(register) for register in (
                UC_X86_REG_CS, UC_X86_REG_IP, UC_X86_REG_SP, UC_X86_REG_BP, UC_X86_REG_EFLAGS)]
            return dict(memory=bytes(cpu.mem_read(0, 1024**2)), timeline=bytes(timeline),
                        instructions=instruction_count, updates=step + 1, boundary=boundary,
                        reads={key: sorted(value) for key, value in reads.items()},
                        early_reads={key: sorted(value) for key, value in early_reads.items()})

        groups = defaultdict(list)
        for weapon, parity, scene, velocities, pattern in itertools.product(
                range(1, 5), (0, 1), levels, ((0, 0), (448, -464)), range(3)):
            report['active_case'] = dict(weapon=weapon, parity=parity, scene=scene,
                                        velocities=velocities, stale_pattern=pattern)
            stale = (bytes(38) if pattern == 0 else bytes([255] * 38) if pattern == 1
                     else bytes((17 + offset * 29) & 255 for offset in range(38)))
            traced = execute(levels[scene], weapon, parity, velocities, stale, True)
            observed = {key: value for key, value in traced['reads'].items() if key in preserved}
            early = {key: value for key, value in traced['early_reads'].items() if key in preserved}
            assert {0, 1, 2, 6, 7, 8, 9, 10, 12, 20, 21, 22, 27} <= set(traced['reads'])
            untraced = execute(levels[scene], weapon, parity, velocities, stale, False)
            for field in ('memory', 'timeline', 'instructions', 'updates', 'boundary'):
                assert traced[field] == untraced[field], ('observer changed execution', field)
            masked_timeline = bytearray(traced['timeline'])
            for base in range(0, len(masked_timeline), 46):
                for offset in preserved:
                    masked_timeline[base + offset] = 0
            memory = traced['memory']
            masked_data = bytearray(memory[data:data + 65536])
            for offset in preserved:
                masked_data[0x1bae + 38 + offset] = 0
            projection = sha(masked_data + memory[0x40000:0x60000])
            row = dict(weapon=weapon, parity=parity, scene=scene, velocities=velocities, stale_pattern=pattern,
                complete_updates=traced['updates'], complete_expiry_executed=True,
                instructions=traced['instructions'], observer_neutrality_verified=True,
                compared_mapped_memory_bytes=1024**2, masked_final_state_sha256=projection,
                masked_timeline_sha256=sha(masked_timeline), preserved_reads=observed,
                preserved_read_before_write=early, helpers_entered=dict(original.entries))
            report['cases'].append(row)
            groups[(weapon, parity, scene, velocities)].append(row)
        assert len(report['cases']) == 96 and len(groups) == 32
        assert sum(row['complete_updates'] for row in report['cases']) == 13872
        differences = []
        for key, rows in groups.items():
            for field in ('masked_final_state_sha256', 'masked_timeline_sha256', 'complete_updates'):
                if len({row[field] for row in rows}) != 1:
                    differences.append(dict(group=key, field=field))
        report.update(total_cases=96, differential_groups=32,
            complete_updates=13872, complete_expiry_paths=96,
            traced_and_untraced_updates=27744, observer_neutrality_cases=96,
            positive_read_controls_verified=True, preserved_offsets=preserved,
            preserved_offsets_read=sorted({int(key) for row in report['cases'] for key in row['preserved_reads']}),
            differential_groups_with_outside_preserved_differences=differences,
            helper_sha256=sha(Path(__file__).with_name('original_bomb_cpu.py').read_bytes()),
            generator_sha256=sha(Path(__file__).read_bytes()),
            limitation='Controlled one-bomb lifetimes on shipped Level1 and a zero-filled map; native crosscheck covers ordinary trajectories, not these poisoned slots, mixed pools or all callers.')
        validate_lifetime_result(report)
        report['passed'] = True
        print(json.dumps(dict(passed=True, cases=96, updates=13872, expiry_paths=96,
            differing_groups=len(differences), preserved_offsets_read=report['preserved_offsets_read'],
            report=str(OUT))), flush=True)
    except BaseException:
        report['failure'] = traceback.format_exc()
        raise
    finally:
        report['recorded_utc'] = datetime.now(timezone.utc).isoformat()
        OUT.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
