import copy
import importlib.util
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = (Path(__file__).resolve().parents[1] / '\u786c\u4ef6\u4ee3\u7801' /
               'MaixCam\u8282\u70b9' / 'launcher_app' / 'cascade_logic.py')
if MODULE_PATH.exists():
    SPEC = importlib.util.spec_from_file_location('cascade_logic', MODULE_PATH)
    LOGIC = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(LOGIC)
else:
    LOGIC = None


def cow(bbox=None, score=0.9, label='cow'):
    return {'label': label, 'score': score,
            'bbox': [10, 20, 90, 80] if bbox is None else bbox}


def prediction():
    return {'sourceLabel': 'healthy', 'score': 0.8, 'extra': 'preserved',
            'scores': [{'sourceLabel': 'lumpy', 'score': 0.05},
                       {'sourceLabel': 'healthy', 'score': 0.8},
                       {'sourceLabel': 'foot-and-mouth', 'score': 0.15}]}


class CascadeLogicTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(LOGIC, 'cascade_logic.py must implement the cascade API')

    def test_only_exact_cow_label_is_allowed(self):
        detections = [cow(label=label) for label in
                      ('person', 'sheep', 'background', 'Cow', 'cattle', None)]
        detections += [{'score': 0.99, 'bbox': [0, 0, 100, 100]}]
        self.assertEqual(LOGIC.cow_regions(detections, 200, 100), [])

    def test_invalid_detections_and_boxes_are_ignored(self):
        bad_boxes = [[], [1, 2, 3], [1, 2, 3, 4, 5], '1234',
                     [0, 0, float('nan'), 80], [0, 0, 80, float('inf')],
                     [0, float('-inf'), 80, 80], [0, 0, '80', 80],
                     [0, 0, None, 80], [90, 0, 10, 80], [0, 0, 0, 80],
                     [201, 0, 300, 80], [-100, 0, -1, 80]]
        detections = [cow(box) for box in bad_boxes]
        detections += [None, 1, [], {}, {'label': 'cow', 'score': 0.9}]
        self.assertEqual(LOGIC.cow_regions(detections, 200, 100), [])

    def test_low_missing_and_nonfinite_detection_scores_are_rejected(self):
        for score in (0.449, None, '0.9', float('nan'), float('inf'),
                      float('-inf'), True, -0.1):
            with self.subTest(score=score):
                self.assertEqual(LOGIC.cow_regions([cow(score=score)], 200, 100), [])
        item = cow()
        del item['score']
        self.assertEqual(LOGIC.cow_regions([item], 200, 100), [])
        self.assertEqual(len(LOGIC.cow_regions([cow(score=0.45)], 200, 100)), 1)

    def test_bbox_is_clamped_before_size_check(self):
        self.assertEqual(LOGIC.cow_regions([cow([-100, 0, 20, 100])], 100, 100), [])
        result = LOGIC.cow_regions([cow([-10, -20, 110, 120])], 100, 100)
        self.assertEqual(result, [{'label': 'cow', 'score': 0.9,
                                   'bbox': [0, 0, 100, 100], 'crop': [0, 0, 100, 100]}])

    def test_padding_uses_each_side_and_rounds_outward(self):
        result = LOGIC.cow_regions([cow([10.2, 20.4, 50.6, 60.8])], 100, 100,
                                   padding=0.1)
        self.assertEqual(result[0]['crop'], [6, 16, 49, 49])
        self.assertTrue(all(type(value) is int for value in result[0]['crop']))

    def test_default_padding_and_boundary_clipping(self):
        result = LOGIC.cow_regions([cow([10, 20, 90, 80])], 100, 100)
        self.assertEqual(result[0]['crop'], [6, 17, 88, 66])
        result = LOGIC.cow_regions([cow([0, 0, 40, 40])], 100, 100, padding=0.5)
        self.assertEqual(result[0]['crop'], [0, 0, 60, 60])

    def test_minimum_side_is_checked_before_padding(self):
        self.assertEqual(LOGIC.cow_regions([cow([0, 0, 31, 90])], 100, 100,
                                           padding=1), [])
        self.assertEqual(len(LOGIC.cow_regions([cow([0, 0, 32, 32])], 100, 100)), 1)
        result = LOGIC.cow_regions([cow([0, 0, 20, 20])], 100, 100,
                                   min_side=20, padding=0)
        self.assertEqual(result[0]['crop'], [0, 0, 20, 20])

    def test_original_area_orders_regions_before_limit(self):
        items = [cow([0, 0, 40, 40], 0.99), cow([0, 0, 80, 80], 0.5),
                 cow([20, 20, 80, 80], 0.8)]
        original = copy.deepcopy(items)
        regions = LOGIC.cow_regions(items, 100, 100, padding=0.5)
        self.assertEqual([r['score'] for r in regions], [0.5, 0.8])
        self.assertEqual(items, original)
        self.assertEqual(len(LOGIC.cow_regions(items, 100, 100, max_regions=1)), 1)
        self.assertEqual(LOGIC.cow_regions(items, 100, 100, max_regions=0), [])

    def test_invalid_image_dimensions_fail_closed(self):
        for width, height in ((0, 100), (100, 0), (-1, 100),
                              (float('nan'), 100), (100, float('inf'))):
            with self.subTest(width=width, height=height):
                self.assertEqual(LOGIC.cow_regions([cow()], width, height), [])

    def test_zero_cattle_never_calls_callback(self):
        def forbidden(region):
            self.fail('prediction must not run without a valid cow')
        for detections in ([], None, [cow(label='person')], [cow(score=0.1)],
                           [cow([0, 0, 1, 1])]):
            with self.subTest(detections=detections):
                self.assertEqual(LOGIC.classify_regions(detections, 100, 100, forbidden),
                                 {'status': 'no_cattle', 'cattleCount': 0, 'results': []})

    def test_callback_receives_only_selected_cow_regions(self):
        calls = []
        accepted = prediction()
        def predict(region):
            calls.append(region)
            return accepted
        result = LOGIC.classify_regions(
            [cow(label='sheep'), cow(), cow([0, 0, 40, 40])], 100, 100,
            predict, max_regions=1, padding=0)
        self.assertEqual(calls, [{'label': 'cow', 'score': 0.9,
                                  'bbox': [10, 20, 90, 80], 'crop': [10, 20, 80, 60]}])
        self.assertEqual(result, {'status': 'classified', 'cattleCount': 1,
                                  'results': [{'regionbbox': [10, 20, 90, 80],
                                               'prediction': accepted}]})
        self.assertIs(result['results'][0]['prediction'], accepted)

    def test_all_none_is_uncertain_and_mixed_results_are_preserved(self):
        items = [cow(), cow([0, 0, 40, 40])]
        result = LOGIC.classify_regions(items, 100, 100, lambda region: None)
        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(result['cattleCount'], 2)
        self.assertEqual([r['prediction'] for r in result['results']], [None, None])
        values = iter([None, prediction()])
        result = LOGIC.classify_regions(items, 100, 100, lambda region: next(values))
        self.assertEqual(result['status'], 'classified')
        self.assertIsNone(result['results'][0]['prediction'])
        self.assertEqual(result['results'][1]['prediction']['sourceLabel'], 'healthy')

    def test_no_cattle_and_rejection_never_reuse_previous_frame(self):
        first = LOGIC.classify_regions([cow()], 100, 100, lambda region: prediction())
        empty = LOGIC.classify_regions([], 100, 100, lambda region: self.fail('callback'))
        rejected = LOGIC.classify_regions(
            [cow()], 100, 100, lambda region: LOGIC.accept_prediction(None))
        self.assertEqual(empty, {'status': 'no_cattle', 'cattleCount': 0, 'results': []})
        self.assertEqual(rejected, {'status': 'uncertain', 'cattleCount': 1,
                                    'results': [{'regionbbox': [10, 20, 90, 80],
                                                 'prediction': None}]})
        self.assertEqual(first['results'][0]['prediction']['sourceLabel'], 'healthy')

    def test_prediction_accepts_unsorted_scores_without_mutating_input(self):
        raw = prediction()
        raw['clinicalDiagnosis'] = True
        original = copy.deepcopy(raw)
        result = LOGIC.accept_prediction(raw)
        self.assertEqual(result, dict(original, clinicalDiagnosis=False))
        self.assertEqual(raw, original)
        self.assertIsNot(result, raw)

    def test_every_allowed_label_can_be_the_top_class(self):
        for label in ('healthy', 'foot-and-mouth', 'lumpy'):
            raw = prediction()
            for item in raw['scores']:
                item['score'] = 0.8 if item['sourceLabel'] == label else 0.1
            raw['sourceLabel'] = label
            self.assertIsNotNone(LOGIC.accept_prediction(raw))

    def test_low_score_and_small_margin_are_rejected(self):
        self.assertIsNone(LOGIC.accept_prediction(prediction(), minimum_score=0.81))
        self.assertIsNone(LOGIC.accept_prediction(prediction(), minimum_margin=0.66))
        self.assertIsNotNone(LOGIC.accept_prediction(prediction(), minimum_score=0.8,
                                                     minimum_margin=0.65))
        raw = prediction()
        raw['score'] = raw['scores'][1]['score'] = 0.74
        raw['scores'][2]['score'] = 0.21
        self.assertIsNone(LOGIC.accept_prediction(raw))
        raw['score'] = raw['scores'][1]['score'] = 0.55
        raw['scores'][0]['score'] = 0.4
        raw['scores'][2]['score'] = 0.05
        self.assertIsNone(LOGIC.accept_prediction(raw, minimum_score=0.5))

    def test_non_normalized_probabilities_are_rejected(self):
        for other_score in (0.01, 0.129999, 0.170001, 0.2, 0.8):
            raw = prediction()
            raw['scores'][2]['score'] = other_score
            with self.subTest(other_score=other_score):
                self.assertIsNone(LOGIC.accept_prediction(raw))

    def test_probability_sum_tolerance_includes_both_boundaries(self):
        for other_score in (0.13, 0.15, 0.17):
            raw = prediction()
            raw['scores'][2]['score'] = other_score
            with self.subTest(other_score=other_score):
                self.assertIsNotNone(LOGIC.accept_prediction(raw))

    def test_missing_unknown_duplicate_and_malformed_predictions_are_rejected(self):
        cases = [None, [], {}, {'sourceLabel': 'healthy', 'score': 0.9}]
        for key in ('sourceLabel', 'score', 'scores'):
            raw = prediction()
            del raw[key]
            cases.append(raw)
        for scores in ([], prediction()['scores'][:2], {}, 'invalid',
                       prediction()['scores'] + [prediction()['scores'][0]],
                       [{'sourceLabel': 'healthy', 'score': 0.8}] * 3,
                       [None, {}, {'sourceLabel': 'healthy', 'score': 0.8}]):
            raw = prediction()
            raw['scores'] = scores
            cases.append(raw)
        for key in ('sourceLabel', 'score'):
            raw = prediction()
            del raw['scores'][0][key]
            cases.append(raw)
        for label in ('cow', 'background', '', None, ['healthy']):
            raw = prediction()
            raw['sourceLabel'] = label
            cases.append(raw)
            raw = prediction()
            raw['scores'][0]['sourceLabel'] = label
            cases.append(raw)
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertIsNone(LOGIC.accept_prediction(raw))

    def test_every_probability_must_be_finite_numeric_and_in_range(self):
        for invalid in (float('nan'), float('inf'), float('-inf'), -0.01,
                        1.01, '0.8', None, True):
            for index in (None, 0, 1, 2):
                raw = prediction()
                if index is None:
                    raw['score'] = invalid
                else:
                    raw['scores'][index]['score'] = invalid
                with self.subTest(invalid=invalid, index=index):
                    self.assertIsNone(LOGIC.accept_prediction(raw))

    def test_declared_top_label_and_score_must_match_actual_maximum(self):
        raw = prediction()
        raw['sourceLabel'] = 'lumpy'
        self.assertIsNone(LOGIC.accept_prediction(raw))
        raw = prediction()
        raw['score'] = 0.99
        self.assertIsNone(LOGIC.accept_prediction(raw))
        raw = prediction()
        raw['scores'][0]['score'] = 0.9
        self.assertIsNone(LOGIC.accept_prediction(raw))

    def test_invalid_acceptance_thresholds_fail_closed(self):
        for invalid in (float('nan'), float('inf'), -0.1, 1.1, None, '0.5', True):
            with self.subTest(invalid=invalid):
                self.assertIsNone(LOGIC.accept_prediction(prediction(), minimum_score=invalid))
                self.assertIsNone(LOGIC.accept_prediction(prediction(), minimum_margin=invalid))


class RoiQualityTests(unittest.TestCase):
    def quality(self, rgb):
        self.assertTrue(callable(getattr(LOGIC, 'roi_quality', None)),
                        'roi_quality must implement image quality rejection')
        result = LOGIC.roi_quality(rgb)
        self.assertEqual(set(result), {'accepted', 'reason', 'brightness',
                                       'contrast', 'sharpness'})
        self.assertIs(type(result['accepted']), bool)
        for metric in ('brightness', 'contrast', 'sharpness'):
            self.assertIs(type(result[metric]), float)
            self.assertTrue(np.isfinite(result[metric]))
        return result

    def test_invalid_shapes_types_and_nonfinite_images_are_rejected(self):
        fixtures = [None, [], [[[0, 0, 0]]], 'rgb',
                    np.zeros((32, 32), dtype=np.uint8),
                    np.zeros((32, 32, 1), dtype=np.uint8),
                    np.zeros((32, 32, 4), dtype=np.uint8),
                    np.zeros((1, 32, 32, 3), dtype=np.uint8),
                    np.zeros((32, 32, 3), dtype=np.int16),
                    np.zeros((32, 32, 3), dtype=np.float32)]
        fixtures += [np.full((32, 32, 3), value) for value in
                     (float('nan'), float('inf'), float('-inf'))]
        for rgb in fixtures:
            with self.subTest(shape=getattr(rgb, 'shape', None),
                              dtype=getattr(rgb, 'dtype', None)):
                result = self.quality(rgb)
                self.assertFalse(result['accepted'])
                self.assertEqual(result['reason'], 'invalid_input')

    def test_each_dimension_must_be_at_least_sixteen(self):
        for shape in ((0, 32, 3), (32, 0, 3), (15, 32, 3), (32, 15, 3)):
            with self.subTest(shape=shape):
                result = self.quality(np.full(shape, 128, dtype=np.uint8))
                self.assertFalse(result['accepted'])
                self.assertEqual(result['reason'], 'too_small')

    def test_black_and_white_are_rejected_for_exposure(self):
        for level, reason in ((0, 'too_dark'), (14, 'too_dark'),
                              (246, 'too_bright'), (255, 'too_bright')):
            with self.subTest(level=level):
                result = self.quality(np.full((32, 32, 3), level, dtype=np.uint8))
                self.assertFalse(result['accepted'])
                self.assertEqual(result['reason'], reason)
                self.assertAlmostEqual(result['brightness'], level)
                self.assertAlmostEqual(result['contrast'], 0)
                self.assertAlmostEqual(result['sharpness'], 0)

    def test_flat_gray_and_low_contrast_stripes_are_rejected(self):
        for low, high in ((128, 128), (125, 131)):
            rgb = np.full((32, 32, 3), low, dtype=np.uint8)
            rgb[:, 1::2, :] = high
            result = self.quality(rgb)
            self.assertFalse(result['accepted'])
            self.assertEqual(result['reason'], 'low_contrast')
            self.assertAlmostEqual(result['brightness'], 128)
            self.assertAlmostEqual(result['contrast'], (high - low) / 2)

    def test_linear_ramp_is_rejected_for_low_sharpness(self):
        rgb = np.repeat(np.tile(np.arange(32, dtype=np.uint8) * 4 + 64,
                                (32, 1))[:, :, None], 3, axis=2)
        result = self.quality(rgb)
        self.assertFalse(result['accepted'])
        self.assertEqual(result['reason'], 'blurry')
        self.assertGreater(result['contrast'], 4)
        self.assertAlmostEqual(result['sharpness'], 0)

    def test_normal_stripes_are_accepted_without_mutating_input(self):
        rgb = np.full((32, 32, 3), 64, dtype=np.uint8)
        rgb[:, 1::2, :] = 192
        original = rgb.copy()
        result = self.quality(rgb)
        self.assertTrue(result['accepted'])
        self.assertEqual(result['reason'], 'ok')
        self.assertAlmostEqual(result['brightness'], 128)
        self.assertAlmostEqual(result['contrast'], 64)
        self.assertAlmostEqual(result['sharpness'], 65536)
        np.testing.assert_array_equal(rgb, original)

    def test_minimum_size_and_contrast_boundary_are_accepted(self):
        rgb = np.full((16, 16, 3), 124, dtype=np.uint8)
        rgb[:, 1::2, :] = 132
        result = self.quality(rgb)
        self.assertTrue(result['accepted'])
        self.assertAlmostEqual(result['contrast'], 4)
        self.assertAlmostEqual(result['sharpness'], 256)

    def test_rgb_channels_use_grayscale_luminance(self):
        rgb = np.zeros((32, 32, 3), dtype=np.uint8)
        rgb[:, :, 0] = 100
        rgb[:, 1::2, 0] = 200
        result = self.quality(rgb)
        self.assertTrue(result['accepted'])
        self.assertAlmostEqual(result['brightness'], 44.85)
        self.assertAlmostEqual(result['contrast'], 14.95)

    def test_noncontiguous_roi_is_supported(self):
        rgb = np.full((32, 64, 3), 64, dtype=np.uint8)
        rgb[:, 2::4, :] = 192
        result = self.quality(rgb[:, ::2, :])
        self.assertTrue(result['accepted'])
        self.assertAlmostEqual(result['sharpness'], 65536)


if __name__ == '__main__':
    unittest.main()
