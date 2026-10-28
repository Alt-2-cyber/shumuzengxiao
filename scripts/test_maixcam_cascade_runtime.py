import importlib.util
import copy
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
from test_maixcam_lifecycle import load_node


SOURCE = Path(__file__).resolve().parents[1] / '\u786c\u4ef6\u4ee3\u7801' / 'MaixCam\u8282\u70b9' / 'launcher_app'


class Picture:
    def __init__(self, width, height, bg=None, pixels=None):
        if pixels is None:
            pixels = np.full((height, width, 3), bg or (114, 114, 114), dtype=np.uint8)
        self.pixels = pixels

    def width(self): return self.pixels.shape[1]
    def height(self): return self.pixels.shape[0]
    def to_bytes(self): return self.pixels.tobytes()
    def crop(self, x, y, width, height):
        return Picture(width, height, pixels=self.pixels[y:y + height, x:x + width].copy())
    def resize(self, width, height, method=None):
        value = np.asarray(Image.fromarray(self.pixels).resize((width, height), Image.Resampling.BILINEAR))
        return Picture(width, height, pixels=value)
    def draw_image(self, x, y, other):
        self.pixels[y:y + other.height(), x:x + other.width()] = other.pixels


class CascadeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.node = load_node()
        maix = ModuleType('maix')
        for name in ('app', 'camera', 'display', 'touchscreen'):
            setattr(maix, name, SimpleNamespace())
        maix.image = SimpleNamespace(Image=Picture, ResizeMethod=SimpleNamespace(BILINEAR=1),
                                     Color=SimpleNamespace(from_rgb=lambda r, g, b: (r, g, b)))
        sys.path.insert(0, str(SOURCE))
        self.addCleanup(lambda: sys.path.remove(str(SOURCE)))
        spec = importlib.util.spec_from_file_location('cascade_app_under_test', SOURCE / 'main.py')
        self.app = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'maix': maix, 'vision_node': self.node}):
            spec.loader.exec_module(self.app)
        values = np.indices((240, 320)).sum(0) % 2 * 180 + 35
        self.frame = Picture(320, 240, pixels=np.repeat(values[:, :, None], 3, axis=2).astype(np.uint8))
        self.raw = {'sourceLabel': 'healthy', 'score': .9, 'scores':
                    [{'sourceLabel': 'healthy', 'score': .9}, {'sourceLabel': 'lumpy', 'score': .06},
                     {'sourceLabel': 'foot-and-mouth', 'score': .04}]}
        self.cfg = {'model_type': 'classifier', 'classes': {'cattle': ['cow']}}

    def test_detects_cow_before_classifying_only_the_prepared_crop(self):
        detector = SimpleNamespace(detect=Mock(return_value=[SimpleNamespace(
            label='cow', score=.9, x=40, y=30, w=120, h=90)]))
        with patch.object(self.node, 'classifier_predict', return_value=self.raw) as predict:
            result = self.app.research_frame(detector, object(), self.frame, self.cfg)
        self.assertEqual(result['status'], 'classified')
        self.assertEqual(result['classifier_calls'], 1)
        prepared = predict.call_args.args[1]
        self.assertIsNot(prepared, self.frame)
        self.assertEqual((prepared.width(), prepared.height()), (224, 224))
        self.assertEqual(result['results'][0]['prediction']['unit'], 'detected_cow_roi_letterbox')

    def test_empty_next_frame_has_no_classification_or_previous_disease_label(self):
        detector = SimpleNamespace(detect=Mock(return_value=[]))
        with patch.object(self.node, 'classifier_predict', side_effect=AssertionError('No cow')):
            result = self.app.research_frame(detector, object(), self.frame, self.cfg)
        self.assertEqual(result['status'], 'no_cattle')
        self.assertEqual(result['classifier_calls'], 0)
        self.assertEqual(result['results'], [])

    def test_dark_cow_crop_is_rejected_before_neural_classification(self):
        detector = SimpleNamespace(detect=Mock(return_value=[SimpleNamespace(
            label='cow', score=.9, x=40, y=30, w=120, h=90)]))
        with patch.object(self.node, 'classifier_predict', side_effect=AssertionError('Bad quality')):
            result = self.app.research_frame(detector, object(), Picture(320, 240, bg=(0, 0, 0)), self.cfg)
        self.assertEqual(result['status'], 'uncertain')
        self.assertEqual(result['classifier_calls'], 0)

    def test_inference_failure_does_not_log_a_previous_frame_prediction(self):
        record = {'status': 'classified', 'classifier_calls': 1,
                  'results': [{'regionbbox': [40, 30, 160, 120],
                               'prediction': self.raw, 'detector_score': .9}]}
        records = []
        model = SimpleNamespace(input_format=lambda: 0, close=Mock())
        classifier = SimpleNamespace(close=Mock())
        cam = SimpleNamespace(read=lambda: self.frame, close=Mock())
        disp = SimpleNamespace(show=Mock(), close=Mock())
        with patch.object(self.app.app, 'need_exit', return_value=False, create=True), \
             patch.object(self.app.image, 'COLOR_BLACK', (0, 0, 0), create=True), \
             patch.object(self.app.display, 'Display', return_value=disp, create=True), \
             patch.object(self.node.nn, 'YOLOv8', return_value=model, create=True), \
             patch.object(self.node, 'load_detector', return_value=classifier), \
             patch.object(self.app.camera, 'Camera', return_value=cam, create=True), \
             patch.object(self.app, 'poll', return_value=False), \
             patch.object(self.app, 'overlay', side_effect=lambda frame, *a, **kw: frame), \
             patch.object(self.app, 'research_frame', side_effect=[record, ValueError('next-frame failure')]), \
             patch.object(self.app, 'save_record', side_effect=lambda name, value: records.append(copy.deepcopy(value))):
            with self.assertRaisesRegex(ValueError, 'next-frame failure'):
                self.app.run_mode(self.cfg, SimpleNamespace(mode='appearance_research'), None, None, 2)
        self.assertNotIn('last_prediction', records[-1])
        self.assertEqual(records[-1]['error'], 'next-frame failure')
        self.assertTrue(cam.close.called and model.close.called and classifier.close.called and disp.close.called)


if __name__ == '__main__':
    unittest.main()
