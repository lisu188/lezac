"""Synthetic observation binding and storage failures; no guest launch."""
import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import literal_map_buffers as literal
import literal_map_observer as observer
from test_literal_map_buffers import fixture


class LiteralMapObserverTests(unittest.TestCase):
    def setUp(self):
        self.ds, self.state, self.buffers, self.hashes = fixture()
        self.boundary = dict(tick=18100, phase='post_update', sequence=37555, level=4,
            ds_sha256=literal.digest(self.ds), original_observation=True,
            projection=dict(mapped=dict(frame=1, rng=0x1234ABCD,
                tiles_hex=self.hashes['tiles'], words_hex=self.hashes['words'])))
        self.files = {}

    def store(self, name, raw):
        self.assertNotIn(name, self.files)
        self.files[name] = raw
        return bytes(raw)

    def retain(self, boundary=None, store=None, **changed):
        return observer.retain_literal_buffers(self.boundary if boundary is None else boundary,
            self.state, self.ds, self.buffers['dac'].hex(), self.store if store is None else store,
            **changed)

    def bound(self):
        receipt = self.retain()
        return dict(copy.deepcopy(self.boundary), literal_buffers=receipt), self.files[receipt['bundle']]

    def test_complete_boundary_roundtrip_and_no_input_mutation(self):
        before = copy.deepcopy(self.boundary)
        boundary, blob = self.bound()
        metadata, buffers = observer.read_literal_buffers(boundary, self.ds, blob)
        self.assertEqual(buffers, self.buffers)
        self.assertEqual(metadata['role'], 'original_runtime')
        self.assertEqual(self.boundary, before)
        self.assertEqual(list(self.files), ['literal-18100-post_update.json.gz'])

    def test_both_declared_phases(self):
        for phase in ('present', 'post_update'):
            with self.subTest(phase=phase):
                boundary = dict(self.boundary, phase=phase)
                receipt = self.retain(boundary)
                boundary['literal_buffers'] = receipt
                self.assertEqual(observer.read_literal_buffers(boundary, self.ds, self.files[receipt['bundle']])[1], self.buffers)

    def test_storage_errors_propagate_without_attaching_receipt(self):
        def fail(name, raw):
            raise OSError('private write failed')
        with self.assertRaisesRegex(OSError, 'private write failed'):
            self.retain(store=fail)
        self.assertNotIn('literal_buffers', self.boundary)

    def test_all_incorrect_readbacks_rejected_before_receipt(self):
        for change in (lambda b: None, lambda b: bytearray(b), lambda b: b[:-1],
                       lambda b: b + b'\0', lambda b: bytes([b[0] ^ 1]) + b[1:]):
            with self.subTest(change=change), self.assertRaises(literal.EvidenceError):
                self.retain(store=lambda name, raw: change(raw))
        self.assertNotIn('literal_buffers', self.boundary)

    def test_callback_cannot_change_the_boundary_before_attachment(self):
        for change in (dict(sequence=37556), dict(literal_buffers={})):
            boundary = copy.deepcopy(self.boundary)
            def mutate(name, raw):
                boundary.update(change)
                return raw
            with self.subTest(change=change), self.assertRaises(literal.EvidenceError):
                self.retain(boundary, store=mutate)

    def test_wrong_original_role_and_identity_never_write(self):
        for change in (dict(original_observation=False), dict(original_observation=1),
                       dict(tick=True), dict(tick=0), dict(phase='input'), dict(sequence=0),
                       dict(sequence=True), dict(level=True), dict(level=5), dict(ds_sha256='0' * 64)):
            with self.subTest(change=change), self.assertRaises(literal.EvidenceError):
                self.retain(dict(self.boundary, **change))
        self.assertFalse(self.files)

    def test_stale_projection_or_unbound_plane_never_write(self):
        for key, value in (('frame', 2), ('frame', True), ('rng', 0),
                           ('tiles_hex', '0' * 64), ('words_hex', '0' * 64),
                           ('tiles_hex', self.state['tiles'])):
            boundary = copy.deepcopy(self.boundary)
            boundary['projection']['mapped'][key] = value
            with self.subTest(key=key, value=str(value)[:16]), self.assertRaises(literal.EvidenceError):
                self.retain(boundary)
        self.assertFalse(self.files)

    def test_malformed_projection_never_writes(self):
        for projection in (None, [], {}, dict(mapped=[])):
            with self.subTest(projection=projection), self.assertRaises(literal.EvidenceError):
                self.retain(dict(self.boundary, projection=projection))
        self.assertFalse(self.files)

    def test_receipt_cannot_attach_twice(self):
        boundary, _ = self.bound()
        with self.assertRaises(literal.EvidenceError):
            self.retain(boundary)

    def test_receipt_bound_to_tick_phase_sequence_and_map_receipts(self):
        boundary, blob = self.bound()
        for key, value in (('tick', 18101), ('phase', 'present'), ('sequence', 37556)):
            with self.subTest(key=key), self.assertRaises(literal.EvidenceError):
                observer.read_literal_buffers(dict(boundary, **{key: value}), self.ds, blob)
        changed = copy.deepcopy(boundary)
        changed['projection']['mapped']['words_hex'] = '0' * 64
        with self.assertRaises(literal.EvidenceError):
            observer.read_literal_buffers(changed, self.ds, blob)

    def test_receipt_extent_hash_name_and_claim_mutations_rejected(self):
        boundary, blob = self.bound()
        mutations = (dict(bundle='../escape.gz'), dict(bundle_bytes=len(blob) + 1),
            dict(bundle_sha256='0' * 64), dict(context_sha256='0' * 64),
            dict(extra=0), dict(full_frame_claim=0), dict(original_fidelity_claim=True),
            dict(full_guest_ram_export=True))
        for change in mutations:
            changed = copy.deepcopy(boundary)
            changed['literal_buffers'].update(change)
            with self.subTest(change=change), self.assertRaises(literal.EvidenceError):
                observer.read_literal_buffers(changed, self.ds, blob)

    def test_changed_bundle_and_ds_rejected(self):
        boundary, blob = self.bound()
        for value in (blob[:-1], blob + b'0', bytes([blob[0] ^ 1]) + blob[1:], bytearray(blob)):
            with self.subTest(value=type(value)), self.assertRaises(literal.EvidenceError):
                observer.read_literal_buffers(boundary, self.ds, value)
        changed = b'\1' + self.ds[1:]
        with self.assertRaises(literal.EvidenceError):
            observer.read_literal_buffers(boundary, changed, blob)

    def test_malformed_external_receipts_rejected(self):
        boundary, blob = self.bound()
        for hashes in (None, {}, [], dict(self.hashes, extra='0' * 64),
                       dict(self.hashes, dac='X' * 64), dict(self.hashes, tiles='0' * 64)):
            changed = copy.deepcopy(boundary)
            changed['literal_buffers']['plane_sha256'] = hashes
            with self.subTest(hashes=hashes), self.assertRaises(literal.EvidenceError):
                observer.read_literal_buffers(changed, self.ds, blob)

    def test_malformed_dac_never_writes(self):
        for value in ('00', 'x' * 1536, self.buffers['dac'].hex().upper(), '40' * 768):
            with self.subTest(value=value[:4]), self.assertRaises(literal.EvidenceError):
                observer.retain_literal_buffers(self.boundary, self.state, self.ds, value, self.store)
        self.assertFalse(self.files)

    def test_isolated_source_checkout_needs_no_game_or_optional_modules(self):
        with tempfile.TemporaryDirectory(prefix='lezac-literal-observer-') as folder:
            root = Path(folder)
            for name in ('level1_fidelity.py', 'literal_map_buffers.py', 'literal_map_observer.py',
                         'test_literal_map_buffers.py', 'test_literal_map_observer.py'):
                (root / name).write_bytes((Path(__file__).parent / name).read_bytes())
            script = ('import sys,unittest; sys.path.insert(0, ' + repr(str(root)) + '); '
                'import test_literal_map_observer as t; '
                'result=unittest.TextTestRunner().run(unittest.TestSuite(['
                't.LiteralMapObserverTests("test_complete_boundary_roundtrip_and_no_input_mutation")])); '
                'sys.exit(not result.wasSuccessful())')
            child = subprocess.run([sys.executable, '-S', '-B', '-c', script], cwd=root,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(child.returncode, 0, child.stderr)


if __name__ == '__main__':
    unittest.main()
