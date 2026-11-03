"""Check entry-ID layouts and read bounds without tracing a process."""
import struct
import unittest

from actor_pass_contact_operands import StoppedOperandReader
import actor_pass_entry_operands as entry


class EntryOperands(unittest.TestCase):
    def test_five_guard_layouts_use_exact_four_byte_id_fields(self):
        expected = {
            0x3184b: [('tested_snapshot', 0x400734)],
            0x3d02d: [('source_copy', 0x2022a4), ('destination_copy', 0x201ae4)],
            0x3da27: [('tested_snapshot', 0x200734), ('source_copy', 0x200ef4)],
            0x89fe3: [('tested_snapshot', 0x200734), ('source_copy', 0x200ef4)],
            0x91849: [('tested_snapshot', 0x200734), ('source_copy', 0x200ef4)],
        }
        registers = dict(rsp=0x200000, rdi=0x400000, rcx=0xcafe000000200200, eflags=0x10206)
        for guard, fields in expected.items():
            with self.subTest(guard=hex(guard)):
                calls = []
                def read(address, size):
                    calls.append((address, size))
                    return (0x200200 + len(calls)).to_bytes(4, 'little')
                result = entry.observe_entry_operands(read, registers, guard)
                self.assertEqual(calls, [(address, 4) for _, address in fields])
                self.assertEqual(result['observed_id_fields'],
                                 {name:0x200201 + i for i,(name,_) in enumerate(fields)})
                self.assertEqual(result['host_metadata_bytes_read'], 4 * len(fields))
                self.assertEqual(result['capture_phase'], 'before-exception-allocation')
                self.assertEqual(result['native_test_mask'], 0xffdfffff)
                self.assertFalse(result['native_zf_at_stop'])
                self.assertFalse(result['earlier_memory_operand_value_proven'])
                self.assertFalse(result['interpretation_claim'])
                self.assertFalse(result['state_ownership_claim'])
                if guard == 0x3d02d:
                    self.assertEqual(result['native_operand_kind'], 'register')
                    self.assertEqual(result['native_register_id_operand'], 0x200200)
                else:
                    self.assertEqual(result['native_operand_kind'], 'memory')
                    self.assertNotIn('native_register_id_operand', result)

    def test_constructor_and_unknown_layouts_do_not_read(self):
        for stop in (0x2520, 0x2330, 0x9fcbc, 0):
            with self.assertRaisesRegex(ValueError, 'Unknown native entry-ID guard layout'):
                entry.observe_entry_operands(lambda *_: self.fail('must not read'), {}, stop)

    def test_missing_live_inputs_do_not_read(self):
        for guard, profile in entry.ENTRY_PROFILES.items():
            required = {base for base,_ in profile['operands'].values()} | {'eflags'}
            if 'register_operand' in profile:
                required.add(profile['register_operand'])
            for missing in required:
                with self.subTest(guard=hex(guard), missing=missing):
                    registers = {name:0 for name in required - {missing}}
                    with self.assertRaisesRegex(ValueError, 'requires its live input registers'):
                        entry.observe_entry_operands(lambda *_: self.fail('must not read'), registers, guard)

    def test_each_short_id_field_is_rejected(self):
        registers = dict(rsp=0x200000, rdi=0x400000, rcx=0x200000, eflags=0x40)
        for guard, profile in entry.ENTRY_PROFILES.items():
            for short in range(len(profile['operands'])):
                calls = 0
                def read(*unused):
                    nonlocal calls
                    calls += 1
                    return b'\0' * (3 if calls - 1 == short else 4)
                with self.subTest(guard=hex(guard), short=short):
                    with self.assertRaisesRegex(ValueError, 'operand read was incomplete'):
                        entry.observe_entry_operands(read, registers, guard)

    def test_entry_fields_use_the_same_stopped_read_witness(self):
        for guard, profile in entry.ENTRY_PROFILES.items():
            reader = StoppedOperandReader(lambda *_: b'\xff' * 4, lambda _: -1)
            result = entry.observe_entry_operands(reader.read,
                dict(rsp=0x200000, rdi=0x400000, rcx=0x200200, eflags=0x40), guard)
            witness = reader.finish(True)
            count = len(profile['operands'])
            self.assertEqual(witness['status'], 'cross_reader_agreement')
            self.assertEqual(witness['logical_operand_bytes'], 4 * count)
            self.assertEqual(witness['host_memory_bytes_returned'], 16 * count)
            self.assertEqual(set(result['observed_id_fields'].values()), {0xffffffff})
            self.assertTrue(result['native_zf_at_stop'])

    def test_guard_banks_cover_all_five_sites_with_four_slots(self):
        banks = entry.ENTRY_GUARD_BANKS
        self.assertEqual(set(banks), {'a','b'})
        self.assertTrue(all(len(offsets) == len(set(offsets)) == 4 for offsets in banks.values()))
        self.assertEqual(set().union(*map(set, banks.values())), set(entry.ENTRY_PROFILES))
        self.assertEqual(len(entry.ENTRY_PROFILES), 5)

    def test_all_pinned_signatures_and_individual_mutations(self):
        image = bytearray(0xab400)
        message = entry.ENTRY_MESSAGE.encode('ascii') + b'\0'
        image[0xab340:0xab340 + len(message)] = message
        mutations = [0xab340]
        for guard, profile in entry.ENTRY_PROFILES.items():
            encoded = bytes.fromhex(profile['predicate_bytes'])
            at = profile['predicate']
            image[at:at + len(encoded)] = encoded
            if 'register_load' in profile:
                load, raw = profile['register_load']
                image[load:load + len(bytes.fromhex(raw))] = bytes.fromhex(raw)
                mutations.append(load)
            image[guard:guard + 6] = bytes.fromhex('bf10000000e8')
            struct.pack_into('<i', image, guard + 6, 0x2370 - (guard + 10))
            image[guard + 13:guard + 16] = bytes.fromhex('488d35')
            struct.pack_into('<i', image, guard + 16, 0xab340 - (guard + 20))
            image[guard + 20:guard + 24] = bytes.fromhex('4889c7e8')
            struct.pack_into('<i', image, guard + 24, 0x2520 - (guard + 28))
            mutations.extend((at, at + len(encoded) - 1, guard, guard + 6,
                              guard + 13, guard + 16, guard + 24))
        entry.verify_pinned_entry_sites(image)
        self.assertEqual(len(mutations), 37)
        for at in mutations:
            changed = bytearray(image)
            changed[at] ^= 1
            with self.subTest(at=hex(at)):
                with self.assertRaisesRegex(ValueError, 'Pinned entry-ID .* differs'):
                    entry.verify_pinned_entry_sites(changed)


if __name__ == '__main__':
    unittest.main()
