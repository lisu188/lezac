"""Read bounded ownership metadata from pinned historical native guard sites."""
import struct

CONTACT_RETURNS = (0x3ac10, 0x3b353, 0x8ad15, 0x8c5f8,
                   0x91b78, 0x960e4, 0x9fcd8, 0xa21c9)
PROFILES = {
    0x3abf4: dict(name='ActorUpdate.interruptInProgress', return_offset=0x3ac10,
        parent=0x17a0, prefix_child=0x1770, contact_child=0xfd0,
        source_parent=0x1fc0, variant_tag=0x1fb8, tag_location='source'),
    0x3b337: dict(name='ActorUpdate.validate', return_offset=0x3b353,
        parent=0x7f0, prefix_child=0x7c0, contact_child=0x20,
        source_parent=0x1010, variant_tag=0x7e8, tag_location='destination'),
    0x8acf9: dict(name='ActorUpdate.registers', return_offset=0x8ad15,
        parent=0x17b0, prefix_child=0x1780, contact_child=0xfe0,
        source_parent=0x1fd0, variant_tag=0x1fc8, tag_location='source'),
    0x8c5dc: dict(name='ActorUpdate.register-input', return_offset=0x8c5f8,
        kind='register-input', prefix_child=0xfe0, contact_child=0x840),
    0x91b5c: dict(name='ActorUpdate.deliverTimerInterrupt', return_offset=0x91b78,
        parent=0x1890, prefix_child=0x1860, contact_child=0x10c0,
        source_parent=0x20b0, variant_tag=0x20a8, tag_location='source'),
    0x960c8: dict(name='ActorUpdate.advance', return_offset=0x960e4,
        parent=0x930, prefix_child=0x900, contact_child=0x160,
        source_parent=0x1150, variant_tag=0x928, tag_location='destination'),
    0x9fcbc: dict(name='ActorUpdate.transition', return_offset=0x9fcd8,
        parent=0x800, prefix_child=0x7d0, contact_child=0x30,
        source_parent=0x1020, variant_tag=0x1018, tag_location='source'),
    0xa21ad: dict(name='FrameActorPass.advance.ActorUpdate.registers', return_offset=0xa21c9,
        parent=0x17d0, prefix_child=0x17a0, contact_child=0x1000,
        source_parent=0x2840, variant_tag=0x2838, tag_location='source'),
}
GUARD_BANKS = {
    'queries': (0x3abf4, 0x3b337, 0x8acf9, 0x91b5c),
    'updates': (0x8c5dc, 0x960c8, 0x9fcbc, 0xa21ad),
}


class StoppedOperandReader:
    """Compare bounded stopped-child reads through two kernel interfaces."""

    def __init__(self, read, peek_word):
        self.read_memory, self.peek_word = read, peek_word
        self.report = dict(status='collecting', samples=[], logical_operand_bytes=0,
            proc_bytes_returned=0, ptrace_word_bytes=0, earlier_load_values_proven=False,
            independent_hardware_observation=False)

    def read(self, address, size):
        if size not in (1, 8):
            raise ValueError('Stopped operand witness only accepts one byte or one native word')
        first = self.read_memory(address, size)
        self.report['proc_bytes_returned'] += len(first)
        word = self.peek_word(address)
        self.report['ptrace_word_bytes'] += 8
        if not isinstance(word, int) or not -(1 << 63) <= word < 1 << 64:
            raise ValueError('Stopped operand witness received an invalid native word')
        other = (word & ((1 << 64) - 1)).to_bytes(8, 'little')[:size]
        second = self.read_memory(address, size)
        self.report['proc_bytes_returned'] += len(second)
        self.report['logical_operand_bytes'] += size
        self.report['samples'].append(dict(requested_bytes=size, proc_first_hex=first.hex(),
            ptrace_hex=other.hex(), proc_second_hex=second.hex(),
            equal=len(first) == size and first == other == second))
        return first

    def finish(self, registers_unchanged):
        if not self.report['samples']:
            raise ValueError('Stopped operand witness has no completed samples')
        self.report['register_samples_equal'] = registers_unchanged
        self.report['status'] = ('cross_reader_agreement' if registers_unchanged and
            all(sample['equal'] for sample in self.report['samples']) else 'contradiction')
        self.report['host_memory_bytes_returned'] = (self.report['proc_bytes_returned'] +
                                                    self.report['ptrace_word_bytes'])
        return self.report


def verify_pinned_contact_sites(image):
    for offset in CONTACT_RETURNS:
        if (image[offset - 15:offset - 12] != bytes.fromhex('488d35') or
                image[offset - 8:offset - 5] != bytes.fromhex('4889c7') or
                image[offset - 5:offset - 4] != b'\xe8' or
                offset - 8 + struct.unpack_from('<i', image, offset - 12)[0] != 0xab658 or
                offset + struct.unpack_from('<i', image, offset - 4)[0] != 0x2520):
            raise ValueError('Pinned contact constructor site differs: ' + hex(offset))
    for offset in PROFILES:
        if (image[offset:offset + 5] != bytes.fromhex('bf10000000') or
                image[offset + 5:offset + 6] != b'\xe8' or
                offset + 10 + struct.unpack_from('<i', image, offset + 6)[0] != 0x2370):
            raise ValueError('Pinned contact allocation site differs: ' + hex(offset))


def observe_contact_operands(read, stack_pointer, image_base, stop_offset, registers=None):
    consumed = 0

    def take(address, size):
        nonlocal consumed
        raw = read(address, size)
        if len(raw) != size:
            raise ValueError('Native contact operand read was incomplete')
        consumed += size
        return int.from_bytes(raw, 'little')

    result = dict(interpretation_claim=False, constructor_sites_catalogued=len(CONTACT_RETURNS),
                  constructor_layouts_supported=len(PROFILES))
    if stop_offset == 0x2520:
        returned = take(stack_pointer, 8) - image_base
        result.update(constructor_return_offset=returned,
                      capture_phase='after-allocation-at-constructor-entry')
        if returned not in CONTACT_RETURNS:
            raise ValueError('Contact throw caller is outside the pinned constructor catalog')
        matched = [(offset, profile) for offset, profile in PROFILES.items()
                   if profile['return_offset'] == returned]
        if not matched:
            return dict(result, status='unsupported_constructor_layout', host_metadata_bytes_read=consumed)
        guard_offset, profile = matched[0]
        stack_pointer += 8
    else:
        if stop_offset not in PROFILES:
            raise ValueError('Unknown native contact validation layout')
        guard_offset, profile = stop_offset, PROFILES[stop_offset]
        result['capture_phase'] = 'before-exception-allocation'
    if profile.get('kind') == 'register-input':
        # This guard can be reached before the parent fields or variant tag are stored.
        if registers is None or any(name not in registers for name in ('rbp', 'r12', 'r14')):
            raise ValueError('Register-input contact layout requires its live input registers')
        selected = 'contact_child' if registers['r14'] & 0xffff == 0x654e else 'prefix_child'
        child = take(stack_pointer + profile[selected], 8)
        result.update(status='ownership_fields_captured',
            ownership={'parent': dict(gameSegment=registers['rbp'] & 0xffff,
                idToggleMask=registers['r12'] & 0xffffffff),
                selected: dict(gameSegment=child & 0xffff, idToggleMask=child >> 32)},
            selected_child=selected, entry_ip=registers['r14'] & 0xffff,
            variant_tag=None, variant_tag_location='not-initialized-at-guard',
            parent_source='callee-saved-input-registers', parent_memory_read=False,
            inactive_overlap_is_not_ownership=True, profile=profile['name'], guard_offset=guard_offset,
            host_metadata_bytes_read=consumed, source='pinned-ELF-register-input-and-child-offset')
        return result
    pairs = {}
    for name in ('parent', 'prefix_child', 'contact_child', 'source_parent'):
        value = take(stack_pointer + profile[name], 8)
        pairs[name] = dict(gameSegment=value & 0xffff, idToggleMask=value >> 32)
    tag = take(stack_pointer + profile['variant_tag'], 1)
    result.update(status='ownership_fields_captured', ownership=pairs, variant_tag=tag,
        selected_child={0: 'prefix_child', 1: 'contact_child'}.get(tag),
        inactive_overlap_is_not_ownership=True,
        variant_tag_location=profile['tag_location'], profile=profile['name'],
        guard_offset=guard_offset, host_metadata_bytes_read=consumed,
        source='pinned-ELF-stack-offsets')
    return result
