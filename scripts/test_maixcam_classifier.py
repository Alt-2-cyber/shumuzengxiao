import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from test_maixcam_lifecycle import load_node


class ImageFixture:
    def __init__(self, width, height, calls=None):
        self._width = width
        self._height = height
        self.calls = calls if calls is not None else []

    def width(self):
        return self._width

    def height(self):
        return self._height

    def resize(self, width, height, method=None):
        self.resize_method = method
        self.calls.append(('resize', width, height))
        return ImageFixture(width, height, self.calls)

    def crop(self, x, y, width, height):
        self.calls.append(('crop', x, y, width, height))
        return ImageFixture(width, height, self.calls)


class ClassifierTests(unittest.TestCase):
    def test_camera_resize_explicitly_uses_training_bilinear_method(self):
        node = load_node()
        picture = ImageFixture(640, 480)
        node.classifier_input(picture, 224)
        self.assertEqual(picture.resize_method, node.image.ResizeMethod.BILINEAR)

    def test_live_loop_archives_classification_without_health_events(self):
        node = load_node()
        cfg = {'model_type': 'classifier', 'camera_id': 'camera-test', 'barn_id': 'barn-test',
               'model_version': 'test-candidate', 'model_status': 'deployed'}
        picture = ImageFixture(640, 480)
        classifier = types.SimpleNamespace(labels=['foot-and-mouth'],
                                            classify=Mock(return_value=[(0, 0.82)]))
        uart = types.SimpleNamespace(read_lines=lambda: [], send_json=Mock())
        mqtt = types.SimpleNamespace(loop=lambda: None, publish=Mock(), connected=False)
        backend = types.SimpleNamespace(url='', last_error=None)
        state = node.VisionState(cfg)
        with patch.object(node.app, 'need_exit', side_effect=[False, True]), \
             patch.object(node, 'save_snapshot', return_value='/tmp/test.jpg'), \
             patch.object(node, 'publish_event_links') as publish:
            node.run_camera_loop(cfg, uart, mqtt, backend, classifier, state,
                                 types.SimpleNamespace(read=lambda: picture), None)
        self.assertEqual(publish.call_count, 1)
        payload = publish.call_args.args[3]
        self.assertEqual(payload['eventType'], 'snapshot_event')
        self.assertEqual(payload['level'], 'observe')
        self.assertEqual(payload['modelStatus'], 'research_only')
        self.assertIn('foot-and-mouth', payload['evidence'])
        self.assertEqual(payload['score'], 0.82)
        status = mqtt.publish.call_args.args[1]
        self.assertEqual(status['cattleDetected'], 0)
        self.assertFalse(status['appearanceResearch']['clinicalDiagnosis'])

    def test_classifier_model_loads_with_classifier_api(self):
        node = load_node()
        classifier = Mock()
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'candidate.mud'
            model.touch()
            with patch.object(node.nn, 'Classifier', return_value=classifier, create=True) as factory:
                loaded = node.load_detector({'model_type': 'classifier', 'model_path': str(model)})
        self.assertIs(loaded, classifier)
        factory.assert_called_once_with(model=str(model), dual_buff=False)

    def test_landscape_preprocessing_preserves_aspect_and_center_crop(self):
        node = load_node()
        picture = ImageFixture(640, 480)
        result = node.classifier_input(picture, 224)
        self.assertEqual(picture.calls, [('resize', 298, 224), ('crop', 37, 0, 224, 224)])
        self.assertEqual((result.width(), result.height()), (224, 224))

    def test_portrait_preprocessing_and_torchvision_rounding(self):
        node = load_node()
        picture = ImageFixture(480, 642)
        node.classifier_input(picture, 224)
        self.assertEqual(picture.calls, [('resize', 224, 299), ('crop', 0, 38, 224, 224)])

    def test_logit_output_applies_softmax_once(self):
        node = load_node()
        classifier = types.SimpleNamespace(
            labels=['foot-and-mouth', 'healthy', 'lumpy'],
            classify=Mock(return_value=[(1, 0.8), (0, 0.15), (2, 0.05)]),
        )
        result = node.classifier_predict(classifier, ImageFixture(224, 224), {'model_type': 'classifier'})
        self.assertEqual(result['sourceLabel'], 'healthy')
        self.assertEqual(result['score'], 0.8)
        self.assertTrue(classifier.classify.call_args.kwargs['softmax'])
        self.assertFalse(result['clinicalDiagnosis'])

    def test_probability_output_does_not_apply_softmax_again(self):
        node = load_node()
        classifier = types.SimpleNamespace(labels=['healthy'], classify=Mock(return_value=[(0, 0.9)]))
        node.classifier_predict(classifier, ImageFixture(224, 224),
                                {'model_type': 'classifier', 'classifier_softmax': False})
        self.assertFalse(classifier.classify.call_args.kwargs['softmax'])

    def test_nonfinite_scores_and_unrecognized_ids_fail_closed(self):
        node = load_node()
        for raw in [[(0, float('nan'))], [(2, 0.9)], [(0, 1.1)], []]:
            with self.subTest(raw=raw):
                classifier = types.SimpleNamespace(labels=['healthy'], classify=Mock(return_value=raw))
                self.assertIsNone(node.classifier_predict(classifier, ImageFixture(224, 224),
                                                          {'model_type': 'classifier'}))

    def test_classifier_results_never_become_detection_boxes(self):
        node = load_node()
        classifier = types.SimpleNamespace(detect=Mock(side_effect=AssertionError('wrong model API')))
        self.assertEqual(node.detector_detect(classifier, object(), {'model_type': 'classifier'}), [])

    def test_classifier_metadata_stays_research_only_even_if_misconfigured(self):
        node = load_node()
        metadata = node.model_metadata({'model_type': 'classifier', 'model_status': 'deployed'}, True)
        self.assertEqual(metadata['status'], 'research_only')
        self.assertEqual(metadata['scope'], 'public_source_appearance_research')


if __name__ == '__main__':
    unittest.main()
