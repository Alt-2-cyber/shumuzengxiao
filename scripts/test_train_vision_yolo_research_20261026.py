import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

import train_vision_yolo_research_20261026 as pipeline


class VisionResearchDataTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def image(self, label, name, seed=1):
        path = self.root / label / name
        path.parent.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(seed)
        small = Image.fromarray(rng.integers(0, 256, (16, 16, 3), dtype=np.uint8))
        small.resize((256, 256), Image.Resampling.BILINEAR).save(path, quality=96)
        return path

    def records(self):
        return [pipeline.inspect_image(path, self.root) for path in sorted(self.root.glob('*/*'))]

    def test_roboflow_variants_stay_in_one_group(self):
        self.image('lumpy', 'lesion-source_jpg.rf.' + 'a' * 32 + '.jpg', 1)
        self.image('lumpy', 'lesion-source_png.rf.' + 'b' * 32 + '.jpg', 2)
        groups, edges = pipeline.group_records(self.records())
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]['members']), 2)
        self.assertIn('roboflow_source_name', {edge['reason'] for edge in edges})

    def test_cross_class_duplicate_quarantines_transitive_source_group(self):
        original = self.image('healthy', 'a.jpg', 3)
        duplicate = self.root / 'lumpy' / ('origin_jpg.rf.' + 'c' * 32 + '.jpg')
        duplicate.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, duplicate)
        self.image('lumpy', 'origin_jpg.rf.' + 'd' * 32 + '.jpg', 4)
        groups, _ = pipeline.group_records(self.records())
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['status'], 'quarantine_cross_class')
        self.assertEqual(len(groups[0]['members']), 3)
        self.assertEqual(groups[0]['labels'], ['healthy', 'lumpy'])

    def test_reencoded_near_duplicate_is_grouped_without_matching_filename(self):
        original = self.image('healthy', 'first.jpg', 5)
        recoded = self.root / 'healthy' / 'unrelated-name.jpg'
        with Image.open(original) as image:
            image.resize((240, 240), Image.Resampling.BILINEAR).save(recoded, quality=85)
        records = self.records()
        self.assertNotEqual(records[0]['file_sha256'], records[1]['file_sha256'])
        self.assertNotEqual(records[0]['pixel_sha256'], records[1]['pixel_sha256'])
        groups, edges = pipeline.group_records(records)
        self.assertEqual(len(groups), 1)
        self.assertIn('perceptual_near_duplicate', {edge['reason'] for edge in edges})

    def test_group_split_is_stratified_reproducible_and_disjoint(self):
        groups = [
            {'group_id': f'{label}-{index}', 'labels': [label], 'status': 'eligible',
             'members': [f'{label}-{index}-a', f'{label}-{index}-b']}
            for label in pipeline.LABELS for index in range(20)
        ]
        assigned = pipeline.assign_group_splits(groups, seed=20261026)
        self.assertEqual(assigned, pipeline.assign_group_splits(groups, seed=20261026))
        for label in pipeline.LABELS:
            counts = {split: sum(assigned[g['group_id']] == split for g in groups
                                 if g['labels'] == [label]) for split in ('train', 'val', 'test')}
            self.assertEqual(counts, {'train': 14, 'val': 3, 'test': 3})
        self.assertEqual(len(assigned), 60)


if __name__ == '__main__':
    unittest.main()
