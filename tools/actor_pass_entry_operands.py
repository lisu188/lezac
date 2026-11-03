"""Read only qualified entry-ID operands from the pinned historical ELF."""
import struct

ENTRY_MESSAGE = 'Frame actor entry ID-toggle profile differs'
ENTRY_PROFILES = {
    0x3184b: dict(name='FrameActorEntry.validate', predicate=0x317f6,
        predicate_bytes='f78734070000ffffdfff7549',
        operands={'tested_snapshot': ('rdi', 0x734)}),
    0x3d02d: dict(name='FrameActorPass.registers.entry', predicate=0x3cfce,
        predicate_bytes='f7c1ffffdfff7557', register_operand='rcx',
        register_load=(0x3cf29, '8b8c24a4220000'),
        operands={'source_copy': ('rsp', 0x22a4), 'destination_copy': ('rsp', 0x1ae4)}),
    0x3da27: dict(name='FrameActorPass.interruptInProgress.entry', predicate=0x3d9c1,
        predicate_bytes='f7842434070000ffffdfff7559',
        operands={'tested_snapshot': ('rsp', 0x734), 'source_copy': ('rsp', 0xef4)}),
    0x89fe3: dict(name='FrameActorPass.advance.entry', predicate=0x89f7b,
        predicate_bytes='f7842434070000ffffdfff755b',
        operands={'tested_snapshot': ('rsp', 0x734), 'source_copy': ('rsp', 0xef4)}),
    0x91849: dict(name='FrameActorPass.deliverTimerInterrupt.entry', predicate=0x917e3,
        predicate_bytes='f7842434070000ffffdfff7559',
        operands={'tested_snapshot': ('rsp', 0x734), 'source_copy': ('rsp', 0xef4)}),
}
ENTRY_GUARD_BANKS = {
    'a': (0x3184b, 0x3d02d, 0x3da27, 0x89fe3),
    'b': (0x3184b, 0x3d02d, 0x89fe3, 0x91849),
}


def verify_pinned_entry_sites(image):
    message = ENTRY_MESSAGE.encode('ascii') + b'\0'
    if image[0xab340:0xab340 + len(message)] != message:
        raise ValueError('Pinned entry-ID exception string differs')
    for guard, profile in ENTRY_PROFILES.items():
        predicate = bytes.fromhex(profile['predicate_bytes'])
        start = profile['predicate']
        if (image[start:start + len(predicate)] != predicate or
                start + len(predicate) + struct.unpack('b', predicate[-1:])[0] != guard):
            raise ValueError('Pinned entry-ID predicate site differs: ' + hex(guard))
        if 'register_load' in profile:
            offset, encoded = profile['register_load']
            expected = bytes.fromhex(encoded)
            if image[offset:offset + len(expected)] != expected:
                raise ValueError('Pinned entry-ID register load differs: ' + hex(guard))
        if (image[guard:guard + 6] != bytes.fromhex('bf10000000e8') or
                guard + 10 + struct.unpack_from('<i', image, guard + 6)[0] != 0x2370):
            raise ValueError('Pinned entry-ID allocation site differs: ' + hex(guard))
        if (image[guard + 13:guard + 16] != bytes.fromhex('488d35') or
                guard + 20 + struct.unpack_from('<i', image, guard + 16)[0] != 0xab340 or
                image[guard + 20:guard + 24] != bytes.fromhex('4889c7e8') or
                guard + 28 + struct.unpack_from('<i', image, guard + 24)[0] != 0x2520):
            raise ValueError('Pinned entry-ID constructor site differs: ' + hex(guard))


def observe_entry_operands(read, registers, stop_offset):
    if stop_offset not in ENTRY_PROFILES:
        raise ValueError('Unknown native entry-ID guard layout')
    profile = ENTRY_PROFILES[stop_offset]
    required = {base for base, _ in profile['operands'].values()} | {'eflags'}
    if 'register_operand' in profile:
        required.add(profile['register_operand'])
    if not required <= registers.keys():
        raise ValueError('Entry-ID layout requires its live input registers')
    fields = {}
    for name, (base, offset) in profile['operands'].items():
        raw = read(registers[base] + offset, 4)
        if len(raw) != 4:
            raise ValueError('Native entry-ID operand read was incomplete')
        fields[name] = int.from_bytes(raw, 'little')
    result = dict(status='entry_id_fields_captured', family='entry-id', profile=profile['name'],
        guard_offset=stop_offset, capture_phase='before-exception-allocation',
        host_metadata_bytes_read=4 * len(fields), observed_id_fields=fields,
        native_test_mask=0xffdfffff, native_zf_at_stop=bool(registers['eflags'] & 0x40),
        native_operand_kind='register' if 'register_operand' in profile else 'memory',
        earlier_memory_operand_value_proven=False, state_ownership_claim=False,
        interpretation_claim=False, source='pinned-ELF-entry-ID-layouts')
    if 'register_operand' in profile:
        result['native_register_id_operand'] = registers[profile['register_operand']] & 0xffffffff
    return result
