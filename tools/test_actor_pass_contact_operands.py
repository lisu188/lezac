"""Check pinned contact layouts without launching a replay or reading host memory."""
import struct
import unittest

import actor_pass_contact_operands as operands


class ContactOperands(unittest.TestCase):
    def make_reader(self, profile, constructor=False, tag=0):
        base, stack = 0x100000, 0x200000
        at = stack + (8 if constructor else 0)
        data = {at + profile[name]: (0x200000a55a1000).to_bytes(8, 'little')
                for name in ('parent', 'prefix_child', 'contact_child', 'source_parent')}
        data[at + profile['variant_tag']] = bytes([tag])
        if constructor:
            data[stack] = (base + profile['return_offset']).to_bytes(8, 'little')
        calls = []

        def read(address, size):
            calls.append((address, size))
            return data[address]
        return base, stack, read, calls

    def test_three_guard_layouts_read_only_33_typed_bytes(self):
        for offset, profile in operands.PROFILES.items():
            with self.subTest(profile=profile['name']):
                base, stack, read, calls = self.make_reader(profile)
                result = operands.observe_contact_operands(read, stack, base, offset)
                self.assertEqual(result['profile'], profile['name'])
                self.assertEqual(result['host_metadata_bytes_read'], 33)
                self.assertEqual(sum(size for _, size in calls), 33)
                self.assertEqual(result['capture_phase'], 'before-exception-allocation')
                self.assertEqual(result['ownership']['parent'], dict(gameSegment=0x1000, idToggleMask=0x200000))
                self.assertFalse(result['interpretation_claim'])

    def test_constructor_caller_adds_exactly_eight_bytes_and_stack_adjustment(self):
        for profile in operands.PROFILES.values():
            with self.subTest(profile=profile['name']):
                base, stack, read, calls = self.make_reader(profile, constructor=True)
                result = operands.observe_contact_operands(read, stack, base, 0x2520)
                self.assertEqual(result['host_metadata_bytes_read'], 41)
                self.assertEqual(calls[0], (stack, 8))
                self.assertEqual(result['constructor_return_offset'], profile['return_offset'])
                self.assertEqual(result['capture_phase'], 'after-allocation-at-constructor-entry')

    def test_five_other_known_sites_remain_explicitly_unsupported(self):
        supported = {profile['return_offset'] for profile in operands.PROFILES.values()}
        other = set(operands.CONTACT_RETURNS) - supported
        self.assertEqual(len(other), 5)
        for offset in other:
            calls = []
            def read(address, size):
                calls.append((address, size))
                return (0x100000 + offset).to_bytes(8, 'little')
            result = operands.observe_contact_operands(read, 0x200000, 0x100000, 0x2520)
            self.assertEqual(result['status'], 'unsupported_constructor_layout')
            self.assertEqual(result['host_metadata_bytes_read'], 8)
            self.assertEqual(calls, [(0x200000, 8)])
            self.assertNotIn('ownership', result)

    def test_unknown_caller_and_layout_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'outside the pinned constructor catalog'):
            operands.observe_contact_operands(lambda *_: (0xdeadbeef).to_bytes(8, 'little'), 0, 0, 0x2520)
        with self.assertRaisesRegex(ValueError, 'Unknown native contact validation layout'):
            operands.observe_contact_operands(lambda *_: self.fail('must not read'), 0, 0, 0x1234)

    def test_every_incomplete_read_is_rejected(self):
        for constructor in (False, True):
            for profile in operands.PROFILES.values():
                for short_at in range(6 if constructor else 5):
                    with self.subTest(constructor=constructor, profile=profile['name'], read=short_at):
                        base, stack, read, calls = self.make_reader(profile, constructor=constructor)
                        def short(address, size):
                            raw = read(address, size)
                            return raw[:-1] if len(calls) - 1 == short_at else raw
                        with self.assertRaisesRegex(ValueError, 'operand read was incomplete'):
                            operands.observe_contact_operands(short, stack, base, 0x2520 if constructor else
                                next(key for key, value in operands.PROFILES.items() if value == profile))

    def test_variant_selection_is_explicit_and_invalid_tag_is_retained(self):
        offset, profile = next(iter(operands.PROFILES.items()))
        for tag, selected in ((0, 'prefix_child'), (1, 'contact_child'), (255, None)):
            base, stack, read, unused = self.make_reader(profile, tag=tag)
            result = operands.observe_contact_operands(read, stack, base, offset)
            self.assertEqual(result['variant_tag'], tag)
            self.assertEqual(result['selected_child'], selected)
            self.assertTrue(result['inactive_overlap_is_not_ownership'])
            self.assertFalse(result['interpretation_claim'])

    def test_site_signatures_and_each_mutated_signature(self):
        image = bytearray(0xa3000)
        for offset in operands.CONTACT_RETURNS:
            image[offset - 15:offset - 12] = bytes.fromhex('488d35')
            struct.pack_into('<i', image, offset - 12, 0xab658 - (offset - 8))
            image[offset - 8:offset - 4] = bytes.fromhex('4889c7e8')
            struct.pack_into('<i', image, offset - 4, 0x2520 - offset)
        for offset in operands.PROFILES:
            image[offset:offset + 6] = bytes.fromhex('bf10000000e8')
            struct.pack_into('<i', image, offset + 6, 0x2370 - (offset + 10))
        operands.verify_pinned_contact_sites(image)
        for offset in [value - 15 for value in operands.CONTACT_RETURNS] + list(operands.PROFILES):
            changed = bytearray(image)
            changed[offset] ^= 1
            with self.subTest(offset=hex(offset)):
                with self.assertRaisesRegex(ValueError, 'Pinned contact .* site differs'):
                    operands.verify_pinned_contact_sites(changed)


if __name__ == '__main__':
    unittest.main()
