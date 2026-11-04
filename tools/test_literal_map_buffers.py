"""Synthetic transport controls only; no original snapshots or guest execution."""
import copy
import gzip
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

import literal_map_buffers as literal


def fixture(width=100, height=58):
    data = bytearray(65536)
    struct.pack_into('<H', data, 0xC204, width)
    struct.pack_into('<H', data, 0x2096, (height - 21) * 8)
    struct.pack_into('<HH', data, 0xC1E0, 19, 0x2000)
    struct.pack_into('<HH', data, 0x6612, 37, 0x3000)
    struct.pack_into('<H', data, 0x78C2, 1)
    struct.pack_into('<I', data, 0x1AFE, 0x1234ABCD)
    data[0x79B7] = 4
    cells = width * height
    buffers = dict(tiles=bytes((i * 71) & 255 for i in range(cells)),
        words=bytes((i * 53 + (i >> 8)) & 255 for i in range(cells * 2)), dac=bytes(i & 63 for i in range(768)))
    state = dict(frame=1, rng=0x1234ABCD, **{name: buffers[name].hex() for name in ('tiles', 'words')})
    return bytes(data), state, buffers, {name: literal.digest(value) for name, value in buffers.items()}


class LiteralMapBufferTests(unittest.TestCase):
    def setUp(self):
        self.ds, self.state, self.buffers, self.hashes = fixture()
        self.args = dict(ds=self.ds, tick=18100, phase='post_update', role='synthetic_control', plane_sha256=self.hashes)
        self.blob = self.pack()

    def pack(self, state=None, **changed):
        args = {key: value for key, value in self.args.items() if key != 'ds'}
        return literal.pack_literal_map_buffers(self.state if state is None else state, self.ds,
            self.buffers['dac'].hex(), **{**args, **changed})

    def read(self, blob=None, **changed):
        blob = self.blob if blob is None else blob
        return literal.unpack_literal_map_buffers(blob, blob_sha256=literal.digest(blob), **{**self.args, **changed})

    def rewrite(self, mutate):
        document = json.loads(gzip.decompress(self.blob))
        mutate(document)
        return literal._compress(literal._json(document))

    def test_complete_roundtrip_and_determinism(self):
        metadata, buffers = self.read()
        self.assertEqual(buffers, self.buffers)
        self.assertEqual(metadata['dimensions'], [100, 58])
        for key in ('full_guest_ram_export', 'original_fidelity_claim', 'full_frame_claim'):
            self.assertFalse(metadata[key])
        self.assertEqual(self.pack(), self.blob)

    def test_dimensions_already_observed_in_campaign(self):
        for width, height in ((60, 33), (100, 53), (150, 60), (100, 58)):
            with self.subTest(width=width, height=height):
                ds, state, buffers, hashes = fixture(width, height)
                args = dict(ds=ds, tick=1, phase='present', role='synthetic_control', plane_sha256=hashes)
                blob = literal.pack_literal_map_buffers(state, ds, buffers['dac'].hex(),
                    **{key: value for key, value in args.items() if key != 'ds'})
                self.assertEqual(literal.unpack_literal_map_buffers(blob, blob_sha256=literal.digest(blob), **args)[1], buffers)

    def test_external_bundle_receipt_rejects_changed_bytes(self):
        changed = bytes([self.blob[0] ^ 1]) + self.blob[1:]
        with self.assertRaises(literal.EvidenceError):
            literal.unpack_literal_map_buffers(changed, blob_sha256=literal.digest(self.blob), **self.args)

    def test_maximum_word_span_is_supported_without_truncation(self):
        ds, state, buffers, hashes = fixture(1024, 32)
        data = bytearray(ds)
        struct.pack_into('<HH', data, 0x6612, 0, 0x3000)
        args = dict(ds=bytes(data), tick=1, phase='present', role='synthetic_control', plane_sha256=hashes)
        blob = literal.pack_literal_map_buffers(state, bytes(data), buffers['dac'].hex(),
            **{key: value for key, value in args.items() if key != 'ds'})
        self.assertEqual(len(literal.unpack_literal_map_buffers(blob, blob_sha256=literal.digest(blob), **args)[1]['words']), 65536)

    def test_each_plane_rejects_mutation_with_fresh_bundle_receipt(self):
        for name in literal.BUFFER_NAMES:
            def change(document):
                data = bytes.fromhex(document['data_hex'][name])
                document['data_hex'][name] = (bytes([data[0] ^ 1]) + data[1:]).hex()
            with self.subTest(name=name), self.assertRaises(literal.EvidenceError):
                self.read(self.rewrite(change))

    def test_coherent_plane_metadata_mutation_rejected_by_external_receipts(self):
        def change(document):
            value = b'\x80' + bytes.fromhex(document['data_hex']['words'])[1:]
            document['data_hex']['words'] = value.hex()
            document['metadata']['buffers']['words']['sha256'] = literal.digest(value)
        with self.assertRaises(literal.EvidenceError):
            self.read(self.rewrite(change))

    def test_complete_ds_is_bound(self):
        for at in (0, 0x1AFE, 0x2096, 0x6612, 0x78C2, 0x79B7, 0xC1E0, 0xC204, 65535):
            data = bytearray(self.ds)
            data[at] ^= 1
            with self.subTest(at=at), self.assertRaises(literal.EvidenceError):
                self.read(ds=bytes(data))

    def test_tick_phase_and_role_cannot_be_rebound(self):
        for changed in (dict(tick=18101), dict(phase='present'), dict(role='original_runtime'),
                        dict(tick=True), dict(tick=0), dict(tick=2**32), dict(phase='input'), dict(role='cpp')):
            with self.subTest(changed=changed), self.assertRaises(literal.EvidenceError):
                self.read(**changed)

    def test_metadata_keys_types_and_values_are_exact(self):
        mutations = (lambda m: m.__setitem__('native_frame', True), lambda m: m.__setitem__('extra', 0),
            lambda m: m.__setitem__('full_frame_claim', True), lambda m: m['dimensions'].__setitem__(0, 101),
            lambda m: m['pointers']['words'].__setitem__('segment', 0x3001))
        for mutate in mutations:
            with self.subTest(mutate=mutate), self.assertRaises(literal.EvidenceError):
                self.read(self.rewrite(lambda d: mutate(d['metadata'])))

    def test_json_shape_duplicates_nonfinite_and_encoding_rejected(self):
        for raw in (b'{"metadata":1,"metadata":2}', b'NaN', b'[]', b'\xff', b'{}' * 9000):
            with self.subTest(raw=raw[:20]), self.assertRaises(literal.EvidenceError):
                self.read(literal._compress(raw))
        for mutate in (lambda d: d.__setitem__('extra', 0), lambda d: d.__setitem__('data_hex', []),
                       lambda d: d['data_hex'].__setitem__('extra', ''), lambda d: d.pop('metadata')):
            with self.subTest(mutate=mutate), self.assertRaises(literal.EvidenceError):
                self.read(self.rewrite(mutate))

    def test_canonical_json_and_hex_are_required(self):
        raw = json.dumps(json.loads(gzip.decompress(self.blob)), indent=2).encode('ascii')
        with self.assertRaises(literal.EvidenceError):
            self.read(literal._compress(raw))
        for value in ('00 ', self.state['tiles'].upper(), self.state['tiles'] + '00'):
            with self.subTest(value=value[:12]), self.assertRaises(literal.EvidenceError):
                self.read(self.rewrite(lambda d: d['data_hex'].__setitem__('tiles', value)))

    def test_plane_and_ds_extents_are_exact(self):
        for name in literal.BUFFER_NAMES:
            for delta in (-1, 1):
                def change(document):
                    value = document['data_hex'][name]
                    document['data_hex'][name] = value[:-2] if delta < 0 else value + '00'
                with self.subTest(name=name, delta=delta), self.assertRaises(literal.EvidenceError):
                    self.read(self.rewrite(change))
        for data in (self.ds[:-1], self.ds + b'\0', bytearray(self.ds)):
            with self.subTest(length=len(data)), self.assertRaises(literal.EvidenceError):
                self.read(ds=data)

    def test_far_pointer_and_size_guards(self):
        changes = ((0xC204, '<H', 0), (0xC204, '<H', 65535),
            (0xC1E0, '<HH', 65535, 0x2000), (0x6612, '<HH', 65535, 0x3000),
            (0xC1E0, '<HH', 0, 0), (0x6612, '<HH', 0, 0xA000), (0x6612, '<HH', 0, 0x9FFF))
        for at, fmt, *values in changes:
            data = bytearray(self.ds)
            struct.pack_into(fmt, data, at, *values)
            with self.subTest(at=at, values=values), self.assertRaises(literal.EvidenceError):
                self.read(ds=bytes(data))

    def test_packer_requires_same_instant_and_receipts(self):
        for mutate in (lambda s: s.__setitem__('frame', 2), lambda s: s.__setitem__('frame', True),
                       lambda s: s.__setitem__('rng', 0), lambda s: s.__setitem__('tiles', s['tiles'].upper()),
                       lambda s: s.__setitem__('words', s['words'][:-2])):
            state = copy.deepcopy(self.state)
            mutate(state)
            with self.subTest(mutate=mutate), self.assertRaises(literal.EvidenceError):
                self.pack(state)
        with self.assertRaises(literal.EvidenceError):
            self.pack(plane_sha256=dict(self.hashes, words='0' * 64))

    def test_invalid_receipt_sets(self):
        for hashes in ({}, dict(self.hashes, extra='0' * 64), dict(self.hashes, words='x' * 64),
                       dict(self.hashes, words=self.hashes['words'].upper())):
            with self.subTest(hashes=hashes), self.assertRaises(literal.EvidenceError):
                self.read(plane_sha256=hashes)

    def test_dac_range_not_normalized(self):
        value = b'\x40' + self.buffers['dac'][1:]
        hashes = dict(self.hashes, dac=literal.digest(value))
        with self.assertRaises(literal.EvidenceError):
            literal.pack_literal_map_buffers(self.state, self.ds, value.hex(), tick=1,
                phase='present', role='synthetic_control', plane_sha256=hashes)
        def change(document):
            document['data_hex']['dac'] = value.hex()
            document['metadata']['buffers']['dac']['sha256'] = hashes['dac']
        with self.assertRaises(literal.EvidenceError):
            self.read(self.rewrite(change), plane_sha256=hashes)

    def test_gzip_framing_and_crc_are_exact(self):
        changed_header = bytes([self.blob[0] ^ 1]) + self.blob[1:]
        changed_crc = self.blob[:-8] + bytes([self.blob[-8] ^ 1]) + self.blob[-7:]
        for blob in (changed_header, changed_crc, self.blob[:-1], self.blob + b'junk',
                     self.blob + literal._compress(b''), self.blob + self.blob):
            with self.subTest(length=len(blob)), self.assertRaises(literal.EvidenceError):
                self.read(blob)

    def test_compressed_and_decoded_size_limits(self):
        for data in (b'', b'x' * (literal.MAX_BLOB_BYTES + 1), bytearray(self.blob)):
            with self.subTest(size=len(data)), self.assertRaises(literal.EvidenceError):
                self.read(data)
        too_big = gzip.compress(b'0' * (literal.MAX_DOCUMENT_BYTES + 1), compresslevel=9, mtime=0)
        with self.assertRaises(literal.EvidenceError):
            self.read(literal.GZIP_HEADER + too_big[10:])

    def test_frozen_source_checkout_without_game_assets(self):
        with tempfile.TemporaryDirectory(prefix='lezac-literal-map-') as folder:
            root = Path(folder)
            for name in ('literal_map_buffers.py', 'level1_fidelity.py', 'test_literal_map_buffers.py'):
                (root / name).write_bytes((Path(__file__).parent / name).read_bytes())
            test = 'test_literal_map_buffers.LiteralMapBufferTests.test_complete_roundtrip_and_determinism'
            child = subprocess.run([sys.executable, '-S', '-B', '-m', 'unittest', test], cwd=root,
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(child.returncode, 0, child.stderr)


if __name__ == '__main__':
    unittest.main()
