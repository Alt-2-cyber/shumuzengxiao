import hashlib
import io
import unittest

from maixcam_partition_backup import copy_exact, verify_prefix


class PartitionBackupTests(unittest.TestCase):
    def test_resume_validates_prefix_and_produces_complete_hash(self):
        source = bytes(range(256)) * 64
        target = io.BytesIO(source[:4096])
        state = verify_prefix(lambda start, count: source[start:start + count], target, 0, 4096)
        target.seek(4096)
        digest, copied = copy_exact(lambda start, count: source[start:start + count], target, 0, len(source),
                                    initial_count=4096, initial_digest=state)
        self.assertEqual(target.getvalue(), source)
        self.assertEqual(copied, len(source))
        self.assertEqual(digest, hashlib.sha256(source).hexdigest())

    def test_resume_refuses_a_prefix_from_a_different_card(self):
        with self.assertRaisesRegex(ValueError, 'refusing resume'):
            verify_prefix(lambda start, count: b'A' * count, io.BytesIO(b'B' * 512), 0, 512)

    def test_exact_range_is_copied_and_hashed_without_touching_source(self):
        original = b'outside' + bytes(range(256)) * 64 + b'outside'
        target = io.BytesIO()
        digest, copied = copy_exact(lambda start, size: original[start:start + size], target, 7, 16384)
        self.assertEqual(target.getvalue(), original[7:-7])
        self.assertEqual(digest, hashlib.sha256(original[7:-7]).hexdigest())
        self.assertEqual(copied, 16384)
        self.assertEqual(original[:7], b'outside')

    def test_short_card_read_is_rejected_before_claiming_a_backup(self):
        with self.assertRaisesRegex(OSError, 'Short card read'):
            copy_exact(lambda start, size: b'not enough', io.BytesIO(), 512, 4096)


if __name__ == '__main__':
    unittest.main()
