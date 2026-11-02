"""Read bounded ownership metadata from three pinned historical native layouts."""
import struct

CONTACT_RETURNS = (0x3ac10, 0x3b353, 0x8ad15, 0x8c5f8,
                   0x91b78, 0x960e4, 0x9fcd8, 0xa21c9)
PROFILES = {
    0x3abf4: dict(name='ActorUpdate.interruptInProgress', return_offset=0x3ac10,
        parent=0x17a0, prefix_child=0x1770, contact_child=0xfd0,
        source_parent=0x1fc0, variant_tag=0x1fb8, tag_location='source'),
    0x8acf9: dict(name='ActorUpdate.registers', return_offset=0x8ad15,
        parent=0x17b0, prefix_child=0x1780, contact_child=0xfe0,
        source_parent=0x1fd0, variant_tag=0x1fc8, tag_location='source'),
    0x960c8: dict(name='ActorUpdate.advance', return_offset=0x960e4,
        parent=0x930, prefix_child=0x900, contact_child=0x160,
        source_parent=0x1150, variant_tag=0x928, tag_location='destination'),
}


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


def observe_contact_operands(read, stack_pointer, image_base, stop_offset):
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
