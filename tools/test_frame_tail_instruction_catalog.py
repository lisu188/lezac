"""Reject drift in the tail's mechanically checked instruction catalogs."""
import unittest
import frame_tail_instruction_catalog as catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.sources={name:(catalog.ROOT/name).read_text(encoding='utf-8') for name in catalog.INPUTS}

    def changed(self,name,before,after):
        self.assertIn(before,self.sources[name])
        self.sources[name]=self.sources[name].replace(before,after,1)
        with self.assertRaises(ValueError):
            catalog.check_sources(self.sources)

    def test_current(self):
        self.assertTrue(catalog.check_sources(self.sources))
        counts=catalog.irq_progress(self.sources[catalog.INPUTS[3]])
        self.assertEqual(len(counts),110)
        self.assertEqual(min(counts[('bios',0xfeb6)]),35)

    def test_foreground_catalog(self):
        self.changed(catalog.INPUTS[0],'0x806a,0x806f','0x806b,0x806f')

    def test_timer_catalog(self):
        self.changed(catalog.INPUTS[0],'{0xfea5,0x1ull,0x0ull}','{0xfea5,0x3ull,0x0ull}')

    def test_owner_drift(self):
        self.changed(catalog.INPUTS[0],'case 0x806a:','case 0x806b:')

    def test_unknown_timer_edge(self):
        self.changed(catalog.INPUTS[3],'r.ip = 0xfea9;','r.ip = 0xfea8;')

    def test_unknown_dispatch_label(self):
        self.changed(catalog.INPUTS[0],'case 0x806a:','case kOtherInstruction:')

    def test_duplicate_markers(self):
        self.sources[catalog.INPUTS[0]]+=catalog.BEGIN
        with self.assertRaises(ValueError):
            catalog.check_sources(self.sources)


if __name__=='__main__':
    unittest.main()
