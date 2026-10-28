import io
import unittest

import maixcam_offline_inspect as inspect_card


class OfflineInspectionTests(unittest.TestCase):
    def test_partition_reader_cannot_escape_its_range_or_write(self):
        source = io.BytesIO(b'outside' + b'filesystem' + b'outside')
        view = inspect_card.PartitionView(source, 7, 10)
        self.assertEqual(view.read(4), b'file')
        self.assertEqual(view.seek(-3, 2), 7)
        self.assertEqual(view.read(50), b'tem')
        with self.assertRaises(ValueError):
            view.seek(-1)
        with self.assertRaises(io.UnsupportedOperation):
            view.write(b'changed')
        self.assertEqual(source.getvalue(), b'outsidefilesystemoutside')

    def test_raw_disk_reads_are_sector_aligned_and_bounded(self):
        raw = inspect_card.SectorReader(lambda start, size: bytes((i % 256 for i in range(start, start + size))), 4096)
        raw.seek(513)
        self.assertEqual(raw.read(7), bytes(range(1, 8)))
        raw.seek(4094)
        self.assertEqual(raw.read(20), bytes([254, 255]))
        self.assertEqual(raw.read(10), b'')


if __name__ == '__main__':
    unittest.main()
