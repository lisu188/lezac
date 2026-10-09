"""Adapt the legacy debris contract without changing pinned fixture dependencies."""
import sys

import check_original_debris_update as legacy
from source_guardrails import function_ranges, source_files

ORIGINAL_CONTRACT = legacy.contract
PHYSICS = ('                if (physicsDispatch) {\n'
    '                    if (!debrisQueue_.empty()) updateDebrisRecords();\n'
    '                    if (!collapseQueue_.empty()) updateCollapseRecords();\n'
    '                }')


def contract(source):
    first, last = function_ranges(source, ['debugOriginalDebrisUpdate'])['debugOriginalDebrisUpdate']
    body = '\n'.join(source.splitlines()[first - 1:last])
    if body.count(PHYSICS) != 1 or legacy.compact(body).count(legacy.compact(PHYSICS)) != 1:
        raise ValueError('coupled physics diagnostic consumer differs')
    normalized = body.replace(PHYSICS, '                if (physicsDispatch) {}')
    ORIGINAL_CONTRACT(source.replace(body, normalized))


def self_check():
    source = '\n'.join(item.text for item in source_files(legacy.ROOT, 'app', 'runtime'))
    contract(source)
    changes = (
        (PHYSICS, ''),
        ('if (!debrisQueue_.empty()) updateDebrisRecords();\n                    if (!collapseQueue_.empty()) updateCollapseRecords();',
         'if (!collapseQueue_.empty()) updateCollapseRecords();\n                    if (!debrisQueue_.empty()) updateDebrisRecords();'),
        ('if (!debrisQueue_.empty()) updateDebrisRecords();', 'updateDebrisRecords();'),
        ('if (!collapseQueue_.empty()) updateCollapseRecords();', 'updateCollapseRecords();'),
        (PHYSICS, PHYSICS + '\n' + PHYSICS),
        ('if (physicalDebrisUpdate || !collapseUpdate) updateDebrisRecords();',
         'if (physicalDebrisUpdate || !collapseUpdate) { updateDebrisRecords(); updateDebrisRecords(); }'))
    for old, new in changes:
        changed = source.replace(old, new)
        if changed == source:
            raise ValueError('debris dispatch source mutation did not apply')
        try:
            contract(changed)
        except ValueError:
            continue
        raise ValueError('debris dispatch accepted a source mutation')


def main():
    if '--self-check' in sys.argv:
        self_check()
    legacy.contract = contract
    legacy.main()
    if '--self-check' in sys.argv:
        print('original_debris_dispatch_contract=ok coupled_mutants=6 legacy_source_mutants=6 production_app=0')


if __name__ == '__main__':
    main()
