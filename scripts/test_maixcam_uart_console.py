import unittest
from types import SimpleNamespace

from maixcam_uart_console import redact, select_ttl_port


class CameraConsolePortTests(unittest.TestCase):
    def test_does_not_select_environment_wearable_or_bluetooth(self):
        nodes = [SimpleNamespace(device='COM5', vid=0x303A),
                 SimpleNamespace(device='COM9', vid=0x303A),
                 SimpleNamespace(device='COM3', vid=None)]
        with self.assertRaisesRegex(RuntimeError, 'No independent USB-to-TTL'):
            select_ttl_port(nodes)

    def test_selects_usb_ttl_by_vendor_identity(self):
        nodes = [SimpleNamespace(device='COM5', vid=0x303A),
                 SimpleNamespace(device='COM11', vid=0x10C4)]
        self.assertEqual(select_ttl_port(nodes), 'COM11')

    def test_requires_explicit_choice_for_multiple_ttl_adapters(self):
        nodes = [SimpleNamespace(device='COM11', vid=0x10C4),
                 SimpleNamespace(device='COM12', vid=0x1A86)]
        with self.assertRaisesRegex(RuntimeError, 'Multiple USB-to-TTL'):
            select_ttl_port(nodes)

    def test_redacts_credentials_in_system_logs(self):
        self.assertEqual(redact('wifi_pass=secret\npsk="password"\nready'),
                         'wifi_pass=[redacted]\npsk=[redacted]\nready')


if __name__ == '__main__':
    unittest.main()
