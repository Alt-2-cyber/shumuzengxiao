"""Regression checks for cross-source connected components and frozen splits."""

import tempfile
import unittest
import zipfile
from pathlib import Path

import vision_expand_retrain_20261026 as pipeline


def record(identifier, label='lumpy', prior_split=None, source='new', **changes):
    value = dict(id=identifier, source_label=label, prior_split=prior_split,
                 prior_group_id=None, source_dataset=source,
                 decode_status='ok', file_sha256='file-' + identifier,
                 pixel_sha256='pixel-' + identifier, source_name_key=None,
                 phash='aaaaaaaaaaaaaaaa', dhash='aaaaaaaaaaaaaaaa',
                 phash_mirror='5555555555555555', dhash_mirror='5555555555555555',
                 width=224, height=224, source_path=identifier,
                 prior_role='representative' if prior_split else None)
    value.update(changes)
    return value


class LeakageTests(unittest.TestCase):
    def test_new_bridge_to_test_blocks_prior_training_and_all_variants(self):
        rows = [record('test', prior_split='test', source='prior'),
                record('bridge', pixel_sha256='pixel-test'),
                record('train', prior_split='train', source='prior',
                       file_sha256='file-bridge')]
        groups, edges = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertEqual(len(groups), 1)
        self.assertTrue(edges)
        self.assertEqual(rows[0]['role'], 'frozen_test')
        self.assertFalse(any(r['role'] == 'train' for r in rows))

    def test_cross_class_components_are_quarantined_without_relabeling(self):
        rows = [record('a'), record('b', label='healthy')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertTrue(all(r['role'] == 'quarantine_cross_label' for r in rows))
        self.assertEqual({r['source_label'] for r in rows}, {'lumpy', 'healthy'})

    def test_frozen_validation_cannot_be_added_to_training(self):
        rows = [record('v', prior_split='val', source='prior'), record('n')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertEqual(rows[0]['role'], 'val')
        self.assertFalse(any(r['role'] == 'train' for r in rows))

    def test_unlabeled_detection_is_not_a_disease_and_can_bridge_duplicates(self):
        rows = [record('a', label=None, source='cow-detection'), record('b')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertEqual(rows[0]['role'], 'duplicate_excluded')
        self.assertEqual(rows[1]['role'], 'train')

    def test_holdout_source_component_is_excluded_from_training(self):
        rows = [record('a', source='holdout'), record('b')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertEqual(sum(r['role'] == 'source_holdout' for r in rows), 1)
        self.assertFalse(any(r['role'] == 'train' for r in rows))

    def test_mirror_is_matched_but_aspect_mismatch_is_not(self):
        rows = [record('a'), record('b', phash='5555555555555555',
                                  dhash='5555555555555555',
                                  phash_mirror='aaaaaaaaaaaaaaaa',
                                  dhash_mirror='aaaaaaaaaaaaaaaa'),
                record('c', width=450)]
        groups, edges = pipeline.build_groups(rows)
        self.assertEqual(len(groups), 2)
        self.assertTrue(any(e['reason'] == 'perceptual_near_duplicate' for e in edges))

    def test_descriptive_source_names_are_global_numeric_names_are_namespaced(self):
        left = pipeline.source_name_key('cow-lesion_jpg.rf.123.jpg', 'one')
        right = pipeline.source_name_key('cow-lesion.png', 'two')
        self.assertEqual(left, right)
        self.assertNotEqual(pipeline.source_name_key('123.jpg', 'one'),
                            pipeline.source_name_key('123.png', 'two'))

    def test_archive_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'bad.zip'
            with zipfile.ZipFile(archive, 'w') as output:
                output.writestr('../escape.txt', 'bad')
            with self.assertRaises(ValueError):
                pipeline.safe_extract(archive, Path(folder) / 'raw')
            self.assertFalse((Path(folder) / 'escape.txt').exists())

    def test_unspecified_unhealthy_and_cow_detection_are_not_disease_labels(self):
        self.assertIsNone(pipeline.normalize_label('unhealthy'))
        self.assertIsNone(pipeline.normalize_label('cow-and-cattle'))
        self.assertEqual(pipeline.normalize_label('foot and mougth'), 'foot-and-mouth')
        self.assertEqual(pipeline.normalize_label('Healthycows 2'), 'healthy')

    def test_generic_class_sequence_names_do_not_cross_sources(self):
        self.assertNotEqual(pipeline.source_name_key('Normal_Skin_10.jpg', 'a'),
                            pipeline.source_name_key('Normal_Skin_10.jpg', 'b'))

    def test_prior_groups_stay_joined_even_if_new_hashes_differ(self):
        rows = [record('test', prior_split='test', prior_group_id='old'),
                record('variant', prior_group_id='old', phash='0000000000000000',
                       dhash='0000000000000000')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertEqual(len(groups), 1)
        self.assertEqual(rows[1]['role'], 'excluded_frozen_test_component')

    def test_no_unmapped_holdout_image_is_relabelled_from_other_source(self):
        rows = [record('a', label=None, source='holdout'), record('b')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertEqual(rows[0]['source_label'], None)
        self.assertFalse(any(r['role'] == 'train' for r in rows))

    def test_non_bovine_filename_exclusion_propagates_to_duplicate_component(self):
        rows = [record('goat-mouth.jpg', label=None), record('cow-labeled-copy')]
        groups, _ = pipeline.build_groups(rows)
        pipeline.assign_roles(rows, groups, 'holdout')
        self.assertTrue(all(r['role'] == 'excluded_non_bovine_subject' for r in rows))

    def test_dataset_root_acronym_cannot_relabel_unhealthy_class(self):
        self.assertEqual(pipeline.public_directory_label(Path('LSD/unhealthy/a.jpg')),
                         ('unhealthy', None))
        self.assertEqual(pipeline.public_directory_label(Path('LSD/healthy/a.jpg')),
                         ('healthy', 'healthy'))


if __name__ == '__main__':
    unittest.main()
