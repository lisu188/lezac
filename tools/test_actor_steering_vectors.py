"""Authenticate derived original vectors and preserve failed exports/reports."""
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest

import export_actor_steering_vectors as exporter


class VectorTests(unittest.TestCase):
    def inputs(self):
        return [*exporter.original.INPUTS,'tools/export_actor_steering_vectors.py',
            'tests/fixtures/actor_steering/manifest.json','tests/fixtures/actor_steering/oracle.bin.gz']

    def copy(self,root):
        for name in self.inputs():
            path=root/name;path.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(exporter.ROOT/name,path)

    def test_original_extraction_and_retention(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.copy(root);out,report=root/'vectors.bin',root/'report.json'
            result=exporter.run(root,out,report)
            self.assertEqual((result['cases'],result['app_homing_cases'],result['app_gate_excluded']),(2136,2097,39))
            self.assertEqual(result['sha256'],exporter.VECTORS_SHA)
            self.assertEqual(result['excluded'],dict(square_root=1536,runtime_error=10,alias=54))
            before=out.stat().st_mtime_ns;exporter.run(root,out,report);self.assertEqual(before,out.stat().st_mtime_ns)
            out.write_bytes(b'preserve vector evidence')
            with self.assertRaises(ValueError): exporter.run(root,out,report)
            self.assertEqual(out.read_bytes(),b'preserve vector evidence')
            self.assertEqual(json.loads(report.read_bytes())['status'],'failed')

    def test_unavailable_changed_and_alias_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.copy(root);out,report=root/'vectors.bin',root/'report.json'
            out.write_bytes(b'preserve vector evidence')
            for name in self.inputs():
                path=root/name;raw=path.read_bytes()
                for mutation in ('changed','missing','directory'):
                    with self.subTest(path=name,mutation=mutation):
                        if mutation=='changed':
                            changed=bytearray(raw);changed[len(changed)//2]^=1;path.write_bytes(changed)
                        else:
                            path.unlink()
                            if mutation=='directory': path.mkdir()
                        try:
                            for target in (out,root/'absent.bin'):
                                with self.assertRaises((ValueError,OSError)): exporter.run(root,target,report)
                                self.assertEqual(json.loads(report.read_bytes())['status'],'failed')
                            self.assertFalse((root/'absent.bin').exists());self.assertEqual(out.read_bytes(),b'preserve vector evidence')
                        finally:
                            if path.is_dir(): path.rmdir()
                            path.write_bytes(raw)
                for target,receipt in ((out,path),(path,report)):
                    with self.assertRaises(ValueError): exporter.run(root,target,receipt)
                    self.assertEqual(path.read_bytes(),raw)
            with self.assertRaises(ValueError): exporter.run(root,out,out)
            self.assertEqual(out.read_bytes(),b'preserve vector evidence')

    def test_delta_parser_controls(self):
        raw=exporter.original.read_fixture(exporter.ROOT,exporter.ROOT/'tests/fixtures/actor_steering')
        # Case header: three dwords and two complete 30-byte register records.
        at=12+72;seeds=struct.unpack_from('<I',raw,at)[0];at+=4
        for unused in range(seeds):
            size=struct.unpack_from('<I',raw,at+4)[0];at+=8+size
        mask=at+4
        variants=[raw[:10],raw[:8]+struct.pack('<I',3735)+raw[12:],
            raw[:12]+struct.pack('<I',1)+raw[16:],
            raw[:mask]+struct.pack('<H',0x4000)+raw[mask+2:],
            raw[:mask]+struct.pack('<H',0x1fff)+raw[mask+2:],raw[:-1],raw+b'\0']
        for changed in variants:
            with self.assertRaises(ValueError): exporter.derive(changed)


if __name__=='__main__':
    unittest.main()
