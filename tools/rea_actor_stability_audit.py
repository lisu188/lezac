"""Observe the original instruction at the historical actor-pass mismatch."""
import argparse
import hashlib
import json
from pathlib import Path

import rea_prefix_audit as audit

HELPER_SHA = 'acf74525b08220c0d976d10509c9d6592c772437628bc8990841356746924096'
OFFSETS = (0x752d, 0x7530, 0x7533, 0x7535, 0x7537, 0x753a, 0x753e, 0x7541)
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    helper = Path(audit.__file__)
    source = Path(__file__)
    source_sha = sha(source)
    if sha(helper) != HELPER_SHA:
        raise ValueError('Frozen REA transport helper changed')
    old_offsets, old_calls = audit.INSTRUCTIONS, audit.CALLS
    audit.INSTRUCTIONS, audit.CALLS = OFFSETS, {}
    try:
        audit.run(args.repo.resolve(), args.out, args.rea_script.resolve(), args.ghidra.resolve(), args.java_home.resolve())
        result = json.loads((args.out / 'instruction-753a.json').read_bytes())['result']['structuredContent']
        instruction = result['normalized_result']
        expected = (args.repo / 'LEZAC.EXE').read_bytes()[0x770 + 0x753a:0x770 + 0x753e]
        if (instruction['bytes'], instruction['mnemonic'], instruction['operands'][0]['raw']) != (expected.hex(), 'ADD', 'DI'):
            raise ValueError('Original 753A instruction differs')
        if sha(source) != source_sha or sha(helper) != HELPER_SHA:
            raise ValueError('REA adapter input changed')
        compact = dict(schema='lezac-actor-stability-instruction-v1', status='observed',
            adapter_sha256=source_sha, helper_sha256=HELPER_SHA, instruction_offsets=list(OFFSETS),
            inherited_advisory_decompilation_offsets=[0x2f9f, 0x6ab], direct_call_queries=[],
            evidence_id=result['evidence_id'], target_sha256=result['subject']['digest']['sha256'],
            provider=result['provider'], instruction=instruction,
            historical_host_failure_reproduced=False, intermittent_hold_cleared=False,
            limitation='Original instruction evidence does not diagnose a C++ host-memory fault')
        (args.out / 'stability-instruction.json').write_text(json.dumps(compact, indent=2) + '\n')
        print(json.dumps(dict(status='observed', instruction=instruction['raw_disassembly'], evidence_id=result['evidence_id'])), flush=True)
    finally:
        audit.INSTRUCTIONS, audit.CALLS = old_offsets, old_calls


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'out', 'rea-script', 'ghidra', 'java-home'):
        parser.add_argument('--' + name, type=Path, required=True)
    run(parser.parse_args())
