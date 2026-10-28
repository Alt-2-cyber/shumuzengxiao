"""Apply a validated image difference only to the verified camera Linux partition."""

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import time

from maixcam_boot_capture import save_json
from maixcam_image_patch import PatchApplyError, apply_ranges
from maixcam_offline_inspect import PartitionView, SectorReader, resolve


class BootVolumeLock:
    def __init__(self, path, descriptor):
        if os.name != 'nt' or not re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}', path):
            raise ValueError('Only a verified Windows volume GUID is allowed')
        self.handle = None
        self.locked = False
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                                                wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                                ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateFileW(path, 0xC0000000, 3, None, 3, 0, None)
        if self.handle == ctypes.c_void_p(-1).value:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            # VOLUME_DISK_EXTENTS on Win64: count, padding, DISK_EXTENT.
            content = self.control(0x00560000, 1024)
            if len(content) < 32 or struct.unpack_from('<I', content)[0] != 1:
                raise ValueError('The boot volume must have exactly one physical extent')
            number, offset, length = struct.unpack_from('<I4xqq', content, 8)
            if (number != int(descriptor['disk_number']) or offset < 512 or length <= 0
                    or offset + length > int(descriptor['partition_offset'])):
                raise ValueError('The boot volume does not belong to the verified camera boot partition')
            self.extent = (offset, length)
            self.control(0x00090018)
            self.locked = True
            self.control(0x00090020)
        except BaseException:
            self.close()
            raise

    def control(self, code, size=0):
        output = ctypes.create_string_buffer(size) if size else None
        actual = wintypes.DWORD()
        if not self.kernel.DeviceIoControl(self.handle, code, None, 0, output, size,
                                          ctypes.byref(actual), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return output.raw[:actual.value] if output is not None else b''

    def close(self):
        if self.handle is not None:
            try:
                if self.locked:
                    self.control(0x0009001C)
            finally:
                self.kernel.CloseHandle(self.handle)
                self.handle = None
                self.locked = False


class CardPatchIO:
    def __init__(self, descriptor, report):
        if os.name != 'nt':
            raise RuntimeError('The physical camera card adapter is Windows-only')
        self.length = int(descriptor['disk_size'])
        self.first = int(descriptor['partition_offset'])
        self.end = self.first + int(descriptor['partition_size'])
        self.report = report
        self.bytes_read = self.bytes_written = 0
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                           ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        self.kernel.CreateFileW.restype = wintypes.HANDLE
        self.kernel.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
        for name in ('ReadFile', 'WriteFile'):
            getattr(self.kernel, name).argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                                  ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        self.kernel.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        device = chr(92) * 2 + '.' + chr(92) + 'PhysicalDrive' + str(int(descriptor['disk_number']))
        # A second writer must fail to open while this transaction owns the disk.
        self.handle = self.kernel.CreateFileW(device, 0xC0000000, 1, None, 3, 0x80000000, None)
        if self.handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

    def _seek(self, offset, count):
        if offset < 0 or count < 0 or offset + count > self.length or offset % 512 or count % 512:
            raise ValueError('Raw camera I/O exceeds verified sector bounds')
        if not self.kernel.SetFilePointerEx(self.handle, offset, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def read_at(self, offset, count):
        self._seek(offset, count)
        buffer = ctypes.create_string_buffer(count)
        actual = wintypes.DWORD()
        if not self.kernel.ReadFile(self.handle, buffer, count, ctypes.byref(actual), None):
            raise ctypes.WinError(ctypes.get_last_error())
        if actual.value != count:
            raise OSError('Short camera card read')
        self.bytes_read += count
        self.report('verifying_writeback' if self.bytes_written else 'verifying_original', self.bytes_read, self.bytes_written)
        return buffer.raw[:count]

    def write_at(self, offset, content):
        if not self.first <= offset or offset + len(content) > self.end:
            raise ValueError('A patch cannot write the MBR, boot partition or any other disk area')
        self._seek(offset, len(content))
        buffer = ctypes.create_string_buffer(content)
        actual = wintypes.DWORD()
        if not self.kernel.WriteFile(self.handle, buffer, len(content), ctypes.byref(actual), None):
            raise ctypes.WinError(ctypes.get_last_error())
        self.bytes_written += actual.value
        self.report('writing', self.bytes_read, self.bytes_written)
        if actual.value != len(content):
            raise OSError('Short camera card patch write')
        return actual.value

    def flush(self):
        if not self.kernel.FlushFileBuffers(self.handle):
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle is not None:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def main():
    from dissect.extfs import ExtFS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--backup-summary', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--boot-volume', help='Lock and dismount this verified boot volume while patching removable media')
    parser.add_argument('--apply', action='store_true', required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    descriptor = json.loads(args.descriptor.read_text(encoding='utf-8-sig'))
    backup = json.loads(args.backup_summary.read_text(encoding='utf-8-sig'))
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    if (descriptor['bus_type'] not in ('USB', 'SD', 'MMC') or not descriptor['maixcam_boot_verified']
            or backup['phase'] != 'complete' or backup['copied_bytes'] != descriptor['partition_size']
            or plan['originalSha256'] != backup['sha256'] or plan['imageBytes'] != descriptor['partition_size']
            or backup['filesystem_uuid'] != '22a051af-0675-4d62-bed7-98e0dde8dfc0'):
        raise ValueError('Backup, plan and verified camera identity do not match')
    state = {'phase': 'opening_verified_card', 'partition_bytes': descriptor['partition_size'],
             'changed_bytes': plan['changedBytes'], 'bytes_read': 0, 'bytes_written': 0,
             'started_at_utc': datetime.now(timezone.utc).isoformat()}
    save_json(args.output / 'apply-progress.json', state)
    last_report = 0.0

    def report(phase, read_bytes, written_bytes):
        nonlocal last_report
        now = time.monotonic()
        if now - last_report >= 2 or phase == 'writing':
            state.update(phase=phase, bytes_read=read_bytes, bytes_written=written_bytes,
                         verify_percent=round(min(read_bytes / descriptor['partition_size'], 1) * 100, 2),
                         checked_at_utc=datetime.now(timezone.utc).isoformat())
            save_json(args.output / 'apply-progress.json', state)
            last_report = now

    card = None
    volume = None
    try:
        if args.boot_volume:
            volume = BootVolumeLock(args.boot_volume, descriptor)
            state['boot_volume_locked'] = True
        card = CardPatchIO(descriptor, report)
        mbr = card.read_at(0, 512)
        layout = [(start * 512, count * 512) for start, count in
                  (struct.unpack_from('<II', mbr, 454 + 16 * index) for index in range(4))]
        if mbr[510:512] != b'\x55\xaa' or (descriptor['partition_offset'], descriptor['partition_size']) not in layout:
            raise ValueError('Camera MBR partition layout changed')
        if volume is not None and volume.extent not in layout:
            raise ValueError('Locked boot volume does not match the camera MBR')
        fs = ExtFS(PartitionView(SectorReader(card.read_at, descriptor['disk_size']),
                                 descriptor['partition_offset'], descriptor['partition_size']))
        if str(fs.uuid) != backup['filesystem_uuid']:
            raise ValueError('Camera filesystem UUID changed')
        card.bytes_read = 0
        def verify_startup():
            repaired = ExtFS(PartitionView(SectorReader(card.read_at, descriptor['disk_size']),
                                           descriptor['partition_offset'], descriptor['partition_size']))
            expected = {'/etc/init.d/S06maixapp': 'fbe527eb6d8a8766ec440173ef8c5d012daed8cd21e55f763ddf2a60dd62c784',
                        '/etc/init.d/rcS': 'd9e244549fd6aa82a9d4d38ae676c5aa8ff1a9f0a34405fcad9fa10e873f8a1a'}
            for path, expected_hash in expected.items():
                node = resolve(repaired, path)
                content = node.open().read(node.size)
                if hashlib.sha256(content).hexdigest() != expected_hash:
                    raise ValueError('Repaired startup file verification failed: ' + path)
            if any(node.filename == 'S06maixapp.project-backup'
                   for node in resolve(repaired, '/etc/init.d').iterdir()):
                raise ValueError('Executable backup still appears in the startup directory')

        result = apply_ranges(card.read_at, card.write_at, card.flush, plan, args.plan.parent,
                              int(descriptor['partition_offset']), int(descriptor['partition_size']),
                              verify_after=verify_startup)
        state.update(phase='complete', result=result, startup_files_verified=True,
                     completed_at_utc=datetime.now(timezone.utc).isoformat())
        save_json(args.output / 'apply-result.json', state)
        save_json(args.output / 'apply-progress.json', state)
        print(json.dumps(state, indent=2), flush=True)
    except BaseException as failure:
        state.update(phase='failed', error_type=type(failure).__name__, error=str(failure))
        if isinstance(failure, PatchApplyError):
            state.update(rollback_verified=failure.rollback_ok, rollback_errors=failure.rollback_errors)
        save_json(args.output / 'apply-result.json', state)
        save_json(args.output / 'apply-progress.json', state)
        raise
    finally:
        if card is not None:
            card.close()
        if volume is not None:
            volume.close()


if __name__ == '__main__':
    main()
