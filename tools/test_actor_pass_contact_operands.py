"""Check pinned contact layouts without launching a replay or reading host memory."""
import struct
import unittest
from unittest import mock

import actor_pass_contact_operands as operands


class ContactOperands(unittest.TestCase):
    def stack_profiles(self):
        return {key: value for key, value in operands.PROFILES.items() if value.get('kind') != 'register-input'}

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

    def test_seven_stack_guard_layouts_read_only_33_typed_bytes(self):
        self.assertEqual(len(self.stack_profiles()), 7)
        for offset, profile in self.stack_profiles().items():
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
        for profile in self.stack_profiles().values():
            with self.subTest(profile=profile['name']):
                base, stack, read, calls = self.make_reader(profile, constructor=True)
                result = operands.observe_contact_operands(read, stack, base, 0x2520)
                self.assertEqual(result['host_metadata_bytes_read'], 41)
                self.assertEqual(calls[0], (stack, 8))
                self.assertEqual(result['constructor_return_offset'], profile['return_offset'])
                self.assertEqual(result['capture_phase'], 'after-allocation-at-constructor-entry')

    def test_missing_layout_remains_explicitly_unsupported(self):
        for omitted, profile in operands.PROFILES.items():
            offset = profile['return_offset']
            calls = []
            def read(address, size):
                calls.append((address, size))
                return (0x100000 + offset).to_bytes(8, 'little')
            with mock.patch.dict(operands.PROFILES, {}, clear=True):
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
            for profile in self.stack_profiles().values():
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

    def test_register_input_never_reads_parent_or_uninitialized_tag(self):
        profile = operands.PROFILES[0x8c5dc]
        for constructor in (False, True):
            for ip, selected in ((0x6053, 'prefix_child'), (0x654e, 'contact_child')):
                with self.subTest(constructor=constructor, entry=hex(ip)):
                    base, stack = 0x100000, 0x200000
                    offset = 8 if constructor else 0
                    calls = []
                    def read(address, size):
                        calls.append((address, size))
                        if constructor and address == stack:
                            return (base + profile['return_offset']).to_bytes(8, 'little')
                        self.assertEqual((address, size), (stack + offset + profile[selected], 8))
                        return (0x200000a55a1000).to_bytes(8, 'little')
                    registers = dict(rbp=0xbeef00001000, r12=0xabcd000000200000, r14=0xbeef00000000 | ip)
                    result = operands.observe_contact_operands(read, stack, base,
                        0x2520 if constructor else 0x8c5dc, registers)
                    self.assertEqual(result['ownership']['parent'], dict(gameSegment=0x1000, idToggleMask=0x200000))
                    self.assertEqual(result['selected_child'], selected)
                    self.assertIsNone(result['variant_tag'])
                    self.assertFalse(result['parent_memory_read'])
                    self.assertEqual(result['variant_tag_location'], 'not-initialized-at-guard')
                    self.assertEqual(result['host_metadata_bytes_read'], 16 if constructor else 8)
                    self.assertEqual(sum(size for _, size in calls), result['host_metadata_bytes_read'])

    def test_register_input_requires_registers_and_rejects_short_child(self):
        for registers in (None, {}, dict(rbp=0x1000, r12=0x200000)):
            with self.assertRaisesRegex(ValueError, 'requires its live input registers'):
                operands.observe_contact_operands(lambda *_: self.fail('must not read'), 0, 0, 0x8c5dc, registers)
        with self.assertRaisesRegex(ValueError, 'operand read was incomplete'):
            operands.observe_contact_operands(lambda *_: b'\0' * 7, 0, 0, 0x8c5dc,
                dict(rbp=0x1000, r12=0x200000, r14=0x6053))

    def test_register_input_preserves_bad_game_and_id_bits(self):
        result = operands.observe_contact_operands(lambda *_: (0x20000000001000).to_bytes(8, 'little'),
            0, 0, 0x8c5dc, dict(rbp=0x1200, r12=0x200200, r14=0x6053))
        self.assertEqual(result['ownership']['parent'], dict(gameSegment=0x1200, idToggleMask=0x200200))
        self.assertEqual(result['ownership']['prefix_child'], dict(gameSegment=0x1000, idToggleMask=0x200000))
        self.assertFalse(result['interpretation_claim'])

    def test_guard_banks_cover_every_constructor_layout_once(self):
        entries = [offset for bank in operands.GUARD_BANKS.values() for offset in bank]
        self.assertEqual(len(entries), 8)
        self.assertEqual(len(set(entries)), 8)
        self.assertEqual(set(entries), set(operands.PROFILES))
        self.assertEqual({profile['return_offset'] for profile in operands.PROFILES.values()},
                         set(operands.CONTACT_RETURNS))

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


class StoppedReads(unittest.TestCase):
    def test_native_words_and_tags_use_proc_peek_proc_order(self):
        for size, word in ((1, 0x10203040506070ff), (4, -1), (8, -1), (8, 0x200000a55a1000)):
            with self.subTest(size=size, word=word):
                raw = (word & ((1 << 64) - 1)).to_bytes(8, 'little')[:size]
                calls = []
                def read(address, length):
                    calls.append(('proc', address, length))
                    return raw
                def peek(address):
                    calls.append(('peek', address, 8))
                    return word
                reader = operands.StoppedOperandReader(read, peek)
                self.assertEqual(reader.read(0x200001, size), raw)
                report = reader.finish(True)
                self.assertEqual(calls, [('proc', 0x200001, size), ('peek', 0x200001, 8),
                                         ('proc', 0x200001, size)])
                self.assertEqual(report['status'], 'cross_reader_agreement')
                self.assertEqual(report['host_memory_bytes_returned'], size * 2 + 8)
                self.assertEqual(report['logical_operand_bytes'], size)
                self.assertFalse(report['earlier_load_values_proven'])
                self.assertFalse(report['independent_hardware_observation'])

    def test_mismatched_or_short_samples_are_not_agreement(self):
        for first, word, last in ((b'\x01' * 8, 0, b'\x01' * 8),
                                  (b'\0' * 8, 0, b'\x01' * 8),
                                  (b'\0' * 7, 0, b'\0' * 8),
                                  (b'\0' * 8, 0, b'\0' * 7)):
            with self.subTest(first=first, word=word, last=last):
                reads = iter((first, last))
                reader = operands.StoppedOperandReader(lambda *_: next(reads), lambda _: word)
                self.assertEqual(reader.read(0, 8), first)
                report = reader.finish(True)
                self.assertEqual(report['status'], 'contradiction')
                self.assertFalse(report['samples'][0]['equal'])
                self.assertEqual(report['host_memory_bytes_returned'], len(first) + len(last) + 8)

    def test_changed_registers_are_not_agreement(self):
        reader = operands.StoppedOperandReader(lambda *_: b'\0' * 8, lambda _: 0)
        reader.read(0, 8)
        report = reader.finish(False)
        self.assertTrue(report['samples'][0]['equal'])
        self.assertEqual(report['status'], 'contradiction')
        self.assertFalse(report['register_samples_equal'])

    def test_empty_or_unsupported_witness_cannot_claim_agreement(self):
        reader = operands.StoppedOperandReader(lambda *_: self.fail('must not read'),
                                                lambda _: self.fail('must not peek'))
        with self.assertRaisesRegex(ValueError, 'no completed samples'):
            reader.finish(True)
        for size in (0, 2, 7, 9):
            with self.assertRaisesRegex(ValueError, 'one byte, a 32-bit operand or one native word'):
                reader.read(0, size)
        self.assertEqual(reader.report['status'], 'collecting')

    def test_invalid_native_word_is_rejected(self):
        for word in (None, 1.5, -(1 << 63) - 1, 1 << 64):
            reader = operands.StoppedOperandReader(lambda *_: b'\0' * 8, lambda _: word)
            with self.assertRaisesRegex(ValueError, 'invalid native word'):
                reader.read(0, 8)

    def test_each_failed_read_stage_retains_available_operand_bytes(self):
        for failed in ('proc_first', 'ptrace', 'proc_second'):
            with self.subTest(failed=failed):
                calls = 0
                def read(*unused):
                    nonlocal calls
                    calls += 1
                    if failed == ('proc_first' if calls == 1 else 'proc_second'):
                        raise OSError('test-only failed proc read')
                    return b'\x01' * 8
                def peek(*unused):
                    if failed == 'ptrace':
                        raise OSError('test-only failed peek')
                    return 0x0101010101010101
                reader = operands.StoppedOperandReader(read, peek)
                with self.assertRaises(OSError):
                    reader.read(0, 8)
                sample, = reader.report['samples']
                self.assertEqual((sample['status'], sample['stage']), ('incomplete', failed))
                self.assertEqual(reader.report['status'], 'incomplete')
                self.assertEqual(reader.report['logical_operand_bytes'], 8)
                self.assertEqual(reader.report['host_memory_bytes_returned'],
                                 {'proc_first': 0, 'ptrace': 8, 'proc_second': 16}[failed])
                self.assertEqual('proc_first_hex' in sample, failed != 'proc_first')
                self.assertEqual('ptrace_hex' in sample, failed == 'proc_second')
                self.assertNotIn('proc_second_hex', sample)
                if failed != 'proc_first':
                    self.assertEqual(sample['proc_first_hex'], '01' * 8)
                if failed == 'proc_second':
                    self.assertEqual(sample['ptrace_hex'], '01' * 8)
                with self.assertRaisesRegex(ValueError, 'incomplete samples'):
                    reader.finish(True)


if __name__ == '__main__':
    unittest.main()
