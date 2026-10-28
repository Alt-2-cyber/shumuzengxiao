import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

import maixcam_boot_capture as capture


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class BootCaptureTests(unittest.TestCase):
    def test_native_usb_selection_does_not_open_ttl_or_esp32(self):
        ports = [SimpleNamespace(device='COM11', vid=0x1A86, pid=0x7523),
                 SimpleNamespace(device='COM9', vid=0x303A, pid=0x1001),
                 SimpleNamespace(device='COM25', vid=0x359F, pid=0x2120)]
        self.assertEqual(capture.select_maix_usb_port(ports), 'COM25')
        with self.assertRaises(RuntimeError):
            capture.select_maix_usb_port(ports[:-1])

    def test_persistent_status_lock_is_reported_without_raising(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'capture-status.json'
            with patch.object(Path, 'replace', side_effect=PermissionError('held open')), \
                 patch.object(capture.time, 'sleep'):
                self.assertFalse(capture.save_json(target, {'phase': 'listening'}))
            self.assertTrue(capture.save_json(target, {'phase': 'receiving'}))
            self.assertIn('receiving', target.read_text(encoding='utf-8'))

    def test_transient_windows_reader_lock_does_not_end_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'capture-status.json'
            original_replace = Path.replace
            attempts = []

            def locked_once(source, destination):
                attempts.append(str(destination))
                if len(attempts) == 1:
                    raise PermissionError('Windows status reader still has the destination open')
                return original_replace(source, destination)

            with patch.object(Path, 'replace', locked_once):
                capture.save_json(target, {'phase': 'listening'})
            self.assertEqual(len(attempts), 2)
            self.assertIn('listening', target.read_text(encoding='utf-8'))

    def test_waits_for_actual_ttl_without_opening_esp32_or_bluetooth(self):
        clock = FakeClock()
        opened = []
        with tempfile.TemporaryDirectory() as directory:
            result = capture.watch(Path(directory), seconds=1, clock=clock, sleep=clock.sleep,
                                   enumerate_ports=lambda: [SimpleNamespace(device='COM5', vid=0x303A),
                                                            SimpleNamespace(device='COM3', vid=None)],
                                   serial_factory=lambda **kwargs: opened.append(kwargs))
        self.assertEqual(opened, [])
        self.assertEqual(result['rx_bytes'], 0)
        self.assertEqual(result['connections'], 0)

    def test_receives_without_transmitting_and_redacts_split_credentials(self):
        clock = FakeClock()
        instances = []

        class Port:
            in_waiting = 0

            def __init__(self, **kwargs):
                self.kwargs = kwargs
                self.chunks = [b'Linux boot\nwifi_pa', b'ss=do-not-publish\nlogin: ']
                self.closed = False
                instances.append(self)

            def open(self):
                pass

            def read(self, count):
                clock.sleep(0.2)
                return self.chunks.pop(0) if self.chunks else b''

            def write(self, data):
                raise AssertionError('Boot capture must never transmit into the camera')

            def close(self):
                self.closed = True

        with tempfile.TemporaryDirectory() as directory:
            result = capture.watch(Path(directory), seconds=1, clock=clock, sleep=clock.sleep,
                                   enumerate_ports=lambda: [SimpleNamespace(device='COM22', vid=0x1A86)],
                                   serial_factory=Port)
            log = (Path(directory) / 'boot-console.log').read_text(encoding='utf-8')
            self.assertIn('Linux boot', log)
            self.assertIn('wifi_pass=[redacted]', log)
            self.assertNotIn('do-not-publish', log)
        self.assertGreater(result['rx_bytes'], 0)
        self.assertEqual(result['connections'], 1)
        self.assertFalse(instances[0].dtr)
        self.assertFalse(instances[0].rts)
        self.assertTrue(instances[0].closed)

    def test_reconnects_after_adapter_disconnect(self):
        clock = FakeClock()
        instances = []

        class Port:
            in_waiting = 0

            def __init__(self, **kwargs):
                instances.append(self)
                self.number = len(instances)

            def open(self):
                pass

            def read(self, count):
                clock.sleep(0.2)
                if self.number == 1:
                    raise capture.serial.SerialException('adapter unplugged')
                return b'login: '

            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            result = capture.watch(Path(directory), seconds=2, clock=clock, sleep=clock.sleep,
                                   enumerate_ports=lambda: [SimpleNamespace(device='COM22', vid=0x1A86)],
                                   serial_factory=Port)
        self.assertEqual(result['connections'], 2)
        self.assertGreater(result['rx_bytes'], 0)


if __name__ == '__main__':
    unittest.main()
