import ctypes
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from unittest.mock import patch

import maixcam_apply_card_patch as adapter
from maixcam_apply_card_patch import CardPatchIO


class CardAdapterTests(unittest.TestCase):
    def volume_kernel(self, disk_number=2, start=512, length=16777216, fail_control=None):
        controls = []

        def control(handle, code, source, source_size, output, output_size, actual, overlapped):
            controls.append(code)
            if code == fail_control:
                return 0
            if code == 0x00560000:
                content = struct.pack('<I4xI4xqq', 1, disk_number, start, length)
                ctypes.memmove(output, content, len(content))
                actual._obj.value = len(content)
            return 1

        kernel = SimpleNamespace(CreateFileW=Mock(return_value=7),
                                 DeviceIoControl=Mock(side_effect=control), CloseHandle=Mock(return_value=1))
        return kernel, controls

    def open_volume(self, kernel):
        descriptor = {'disk_number': 2, 'partition_offset': 16777728}
        with patch.object(adapter.ctypes, 'WinDLL', return_value=kernel):
            return adapter.BootVolumeLock(r'\\?\Volume{50693c9c-d1f8-11f1-8cd8-1091d109ad84}', descriptor)

    def test_volume_is_identified_locked_and_dismounted_before_returning(self):
        kernel, controls = self.volume_kernel()
        volume = self.open_volume(kernel)
        self.assertEqual(controls, [0x00560000, 0x00090018, 0x00090020])
        self.assertEqual(volume.extent, (512, 16777216))
        volume.close()
        self.assertEqual(controls[-1], 0x0009001C)
        kernel.CloseHandle.assert_called_once_with(7)

    def test_volume_of_another_disk_is_rejected_before_locking(self):
        kernel, controls = self.volume_kernel(disk_number=0)
        with self.assertRaises(ValueError):
            self.open_volume(kernel)
        self.assertEqual(controls, [0x00560000])
        kernel.CloseHandle.assert_called_once_with(7)

    def test_volume_overlapping_linux_partition_is_rejected(self):
        kernel, controls = self.volume_kernel(length=31257001472)
        with self.assertRaises(ValueError):
            self.open_volume(kernel)
        self.assertEqual(controls, [0x00560000])

    def test_lock_failure_closes_volume_without_dismount(self):
        kernel, controls = self.volume_kernel(fail_control=0x00090018)
        with self.assertRaises(OSError):
            self.open_volume(kernel)
        self.assertEqual(controls, [0x00560000, 0x00090018])
        kernel.CloseHandle.assert_called_once_with(7)

    def test_dismount_failure_unlocks_and_closes_volume(self):
        kernel, controls = self.volume_kernel(fail_control=0x00090020)
        with self.assertRaises(OSError):
            self.open_volume(kernel)
        self.assertEqual(controls, [0x00560000, 0x00090018, 0x00090020, 0x0009001C])
        kernel.CloseHandle.assert_called_once_with(7)

    def test_open_refuses_concurrent_writers(self):
        kernel = SimpleNamespace(**{name: Mock() for name in
                                 ('CreateFileW', 'SetFilePointerEx', 'ReadFile', 'WriteFile',
                                  'FlushFileBuffers', 'CloseHandle')})
        kernel.CreateFileW.return_value = 7
        descriptor = {'disk_size': 16384, 'partition_offset': 4096,
                      'partition_size': 4096, 'disk_number': 2}
        with patch.object(adapter.ctypes, 'WinDLL', return_value=kernel):
            card = CardPatchIO(descriptor, Mock())
            self.addCleanup(card.close)
        self.assertEqual(kernel.CreateFileW.call_args.args[2], 1)

    def adapter(self, short=False):
        card = object.__new__(CardPatchIO)
        card.first, card.end, card.length = 4096, 8192, 16384
        card.handle = 1
        card.bytes_read = card.bytes_written = 0
        card.report = Mock()

        def write(handle, buffer, size, actual, overlapped):
            actual._obj.value = size // 2 if short else size
            return 1

        def read(handle, buffer, size, actual, overlapped):
            ctypes.memmove(buffer, b'A' * size, size)
            actual._obj.value = size
            return 1

        card.kernel = SimpleNamespace(SetFilePointerEx=Mock(return_value=1),
                                      WriteFile=Mock(side_effect=write), ReadFile=Mock(side_effect=read),
                                      FlushFileBuffers=Mock(return_value=1))
        return card

    def test_mbr_boot_partition_and_outside_writes_never_reach_driver(self):
        for offset, length in [(0, 512), (3584, 1024), (8192, 512), (4609, 512), (4096, 511)]:
            with self.subTest(offset=offset, length=length):
                card = self.adapter()
                with self.assertRaises(ValueError):
                    card.write_at(offset, b'B' * length)
                card.kernel.WriteFile.assert_not_called()

    def test_exact_write_and_uncached_readback_use_absolute_sector_offsets(self):
        card = self.adapter()
        self.assertEqual(card.write_at(4096, b'B' * 512), 512)
        self.assertEqual(card.read_at(4096, 512), b'A' * 512)
        self.assertEqual(card.bytes_written, 512)
        self.assertEqual(card.bytes_read, 512)
        card.kernel.SetFilePointerEx.assert_called_with(1, 4096, None, 0)
        card.flush()
        card.kernel.FlushFileBuffers.assert_called_once_with(1)

    def test_short_write_raises_so_the_transaction_can_roll_back(self):
        card = self.adapter(short=True)
        with self.assertRaisesRegex(OSError, 'Short camera card patch write'):
            card.write_at(4096, b'B' * 512)
        self.assertEqual(card.bytes_written, 256)


if __name__ == '__main__':
    unittest.main()
