import unittest

from PIL import Image
from train_cattle_roi_20261028 import letterbox, validate_groups


class RoiTrainingTests(unittest.TestCase):
    def test_letterbox_preserves_full_cow_shape_and_adds_neutral_padding(self):
        original = Image.new('RGB', (80, 40), (200, 0, 0))
        result = letterbox(original, 224, 224)
        self.assertEqual(result.size, (224, 224))
        self.assertEqual(result.getpixel((112, 0)), (114, 114, 114))
        self.assertEqual(result.getpixel((112, 56)), (200, 0, 0))
        self.assertEqual(result.getpixel((112, 167)), (200, 0, 0))
        self.assertEqual(result.getpixel((112, 168)), (114, 114, 114))

    def test_original_duplicate_group_cannot_cross_into_training(self):
        rows = [{'group_id': 'same-cow-image', 'split': 'test', 'source_label': 'healthy'},
                {'group_id': 'same-cow-image', 'split': 'train', 'source_label': 'healthy'}]
        with self.assertRaisesRegex(ValueError, 'crosses'):
            validate_groups(rows)

    def test_unknown_labels_cannot_be_invented_from_parent_directory_names(self):
        with self.assertRaises(ValueError):
            validate_groups([{'group_id': 'x', 'split': 'train', 'source_label': 'unhealthy'}])


if __name__ == '__main__':
    unittest.main()
