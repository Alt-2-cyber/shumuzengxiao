import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

ROOT = Path(__file__).resolve().parents[1] / '硬件代码' / 'MaixCam节点'


def load_node():
    maix = types.ModuleType('maix')
    for name in ['camera', 'display', 'image', 'nn', 'pinmap']:
        setattr(maix, name, types.SimpleNamespace())
    maix.image.ResizeMethod = types.SimpleNamespace(BILINEAR=1)
    maix.app = types.SimpleNamespace(need_exit=lambda: False)
    maix.time = types.SimpleNamespace(sleep_ms=lambda value: None)
    spec = importlib.util.spec_from_file_location('cattle_camera_node_under_test', ROOT / 'main.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'maix': maix}):
        spec.loader.exec_module(module)
    return module


class LifecycleTests(unittest.TestCase):
    def test_camera_retry_honors_system_exit(self):
        node = load_node()
        with patch.object(node.app, 'need_exit', return_value=True):
            with self.assertRaises(KeyboardInterrupt):
                node.open_camera_with_retry({})

    def test_main_releases_camera_and_serial_after_inference_failure(self):
        node = load_node()
        camera = types.SimpleNamespace(close=unittest.mock.Mock())
        uart_port = types.SimpleNamespace(close=unittest.mock.Mock())
        mqtt_client = types.SimpleNamespace(disconnect=unittest.mock.Mock())
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(node, 'load_config', return_value={'snapshot_dir': directory}), \
                 patch.object(node, 'UartLink', return_value=types.SimpleNamespace(port=uart_port, begin=lambda: None)), \
                 patch.object(node, 'MqttLink', return_value=types.SimpleNamespace(client=mqtt_client, begin=lambda: None)), \
                 patch.object(node, 'load_detector', return_value=None), \
                 patch.object(node, 'open_camera_with_retry', return_value=camera), \
                 patch.object(node, 'run_camera_loop', side_effect=ValueError('inference failed')):
                with self.assertRaisesRegex(ValueError, 'inference failed'):
                    node.main()
        camera.close.assert_called_once()
        uart_port.close.assert_called_once()
        mqtt_client.disconnect.assert_called_once()

    def test_process_manager_accepts_only_exact_project_entrypoint(self):
        spec = importlib.util.spec_from_file_location('manager_under_test', ROOT / 'manage_node.py')
        manager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manager)
        with patch('builtins.open', mock_open(read_data=b'python3\0' + manager.MAIN.encode() + b'\0')):
            self.assertTrue(manager.owns_process(42))
        with patch('builtins.open', mock_open(read_data=b'python3\0/maixapp/apps/settings/main.py\0')):
            self.assertFalse(manager.owns_process(42))

    def test_config_update_preserves_existing_credentials(self):
        spec = importlib.util.spec_from_file_location('manager_config_under_test', ROOT / 'manage_node.py')
        manager = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(manager)
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps({'backend_api_key': 'unit-test-value', 'backend_url': 'http://old:8080'}))
            with patch.object(manager, 'ROOT', directory):
                manager.prepare_config('http://new:8080')
            updated = json.loads(config.read_text())
            self.assertEqual(updated['backend_api_key'], 'unit-test-value')
            self.assertEqual(updated['backend_url'], 'http://new:8080')
            self.assertEqual(updated['model_path'], str(Path(directory) / 'models' / 'cattle_yolov8.mud'))


if __name__ == '__main__':
    unittest.main()
