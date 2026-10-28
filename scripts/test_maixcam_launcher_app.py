import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / '\u786c\u4ef6\u4ee3\u7801' / 'MaixCam\u8282\u70b9' / 'launcher_app/ui_logic.py'
spec = importlib.util.spec_from_file_location('launcher_ui_logic', SOURCE)
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class CameraAppTests(unittest.TestCase):
    def test_research_mode_cannot_claim_a_clinical_or_detection_scope(self):
        config = ui.mode_config({'model_status': 'deployed', 'model_scope': 'disease_diagnosis'},
                                'appearance_research', '/test/app')
        self.assertEqual(config['model_type'], 'classifier')
        self.assertEqual(config['model_status'], 'research_only')
        self.assertEqual(config['model_scope'], 'public_source_appearance_research')
        self.assertTrue(config['model_path'].endswith('models/cattle_research.mud'))
        self.assertTrue(config['classifier_softmax'])

    def test_model_switch_keeps_the_original_configuration_unchanged(self):
        original = {'camera_id': 'cam_01'}
        ui.mode_config(original, 'cow_detection', '/test/app')
        self.assertEqual(original, {'camera_id': 'cam_01'})
        with self.assertRaises(ValueError):
            ui.mode_config(original, 'disease_diagnosis', '/test/app')

    def test_letterbox_margin_is_not_a_return_button(self):
        state = ui.TouchState('cow_detection')
        self.assertFalse(state.update(2, 2, True, 552, 368))
        self.assertFalse(state.exit)

    def test_scaled_back_button_exits(self):
        state = ui.TouchState('cow_detection')
        self.assertTrue(state.update(46, 15, True, 552, 368))
        self.assertTrue(state.exit)

    def test_held_mode_button_switches_only_once_until_release(self):
        state = ui.TouchState('cow_detection')
        self.assertTrue(state.update(300, 10, True, 320, 240))
        self.assertEqual(state.mode, 'appearance_research')
        self.assertFalse(state.update(300, 10, True, 320, 240))
        state.update(300, 10, False, 320, 240)
        state.update(300, 10, True, 320, 240)
        self.assertEqual(state.mode, 'cow_detection')


if __name__ == '__main__':
    unittest.main()
