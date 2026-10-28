"""Read a MaixCAM Linux partition without mounting or modifying its filesystem."""

import argparse
from collections import OrderedDict
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import posixpath
import re
import stat
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '.run/maix-recovery-packages'))


class PartitionView(io.RawIOBase):
    def __init__(self, source, offset, length):
        self.source, self.offset, self.length, self.position = source, offset, length, 0

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def write(self, data): raise io.UnsupportedOperation('The camera partition is read-only')

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self.position + offset if whence == 1 else self.length + offset
        if not 0 <= target <= self.length:
            raise ValueError('Seek exceeds the read-only partition')
        self.position = target
        return target

    def read(self, size=-1):
        count = self.length - self.position if size < 0 else min(size, self.length - self.position)
        if count > 8_388_608:
            raise ValueError('Unbounded partition reads are forbidden')
        self.source.seek(self.offset + self.position)
        result = self.source.read(count)
        self.position += len(result)
        return result


class SectorReader(io.RawIOBase):
    def __init__(self, read_sectors, length):
        self.read_sectors, self.length, self.position = read_sectors, length, 0
        self.cache = OrderedDict()

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.position
    def write(self, data): raise io.UnsupportedOperation('The raw disk is read-only')

    def seek(self, offset, whence=0):
        target = offset if whence == 0 else self.position + offset if whence == 1 else self.length + offset
        if not 0 <= target <= self.length:
            raise ValueError('Raw disk seek out of range')
        self.position = target
        return target

    def read(self, size=-1):
        if size < 0 or size > 8_388_608:
            raise ValueError('A bounded raw read is required')
        remaining = min(size, self.length - self.position)
        result = bytearray()
        while remaining:
            page = self.position // 65536 * 65536
            if page not in self.cache:
                count = min(65536, self.length - page)
                self.cache[page] = self.read_sectors(page, count)
                if len(self.cache) > 32:
                    self.cache.popitem(last=False)
            self.cache.move_to_end(page)
            block = self.cache[page]
            start = self.position - page
            count = min(remaining, len(block) - start)
            if count <= 0:
                raise OSError('Short raw disk read')
            result.extend(block[start:start + count])
            self.position += count
            remaining -= count
        return bytes(result)


class WindowsDisk(SectorReader):
    def __init__(self, number, length):
        if os.name != 'nt' or not 0 <= number <= 99 or length % 512:
            raise ValueError('Invalid Windows disk descriptor')
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.c_void_p, wintypes.DWORD]
        kernel.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        device = chr(92) * 2 + '.' + chr(92) + 'PhysicalDrive' + str(number)
        self.handle = kernel.CreateFileW(device, 0x80000000, 3, None, 3, 0, None)
        if self.handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        self.kernel = kernel
        super().__init__(self._read_sectors, length)

    def _read_sectors(self, offset, size):
        if offset % 512 or size % 512:
            raise ValueError('Raw reads must be sector aligned')
        if not self.kernel.SetFilePointerEx(self.handle, offset, None, 0):
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size)
        count = wintypes.DWORD()
        if not self.kernel.ReadFile(self.handle, buffer, size, ctypes.byref(count), None):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer.raw[:count.value]

    def close(self):
        if getattr(self, 'handle', None) not in (None, ctypes.c_void_p(-1).value):
            self.kernel.CloseHandle(self.handle)
            self.handle = None
        super().close()


def resolve(fs, path):
    path = posixpath.normpath('/' + path.lstrip('/'))
    for _ in range(20):
        parts = path.strip('/').split('/') if path != '/' else []
        node = fs.root
        current = '/'
        for index, part in enumerate(parts):
            node = next((child for child in node.iterdir() if child.filename == part), None)
            if node is None:
                raise FileNotFoundError(path)
            if node.filetype == stat.S_IFLNK:
                path = posixpath.normpath(posixpath.join(current, node.link, *parts[index + 1:]))
                break
            current = posixpath.join(current, part)
        else:
            return node
    raise ValueError('Too many filesystem symlinks')


def write_report(path, report):
    path.write_text(json.dumps(report, indent=2, ensure_ascii=True, default=str), encoding='utf-8')


def inspect_filesystem(source, offset, length, output):
    from dissect.extfs import ExtFS
    fs = ExtFS(PartitionView(source, offset, length))
    free_blocks = (fs.sb.s_free_blocks_count_hi << 32) | fs.sb.s_free_blocks_count_lo
    report = {'read_only': True, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'filesystem': {'type': fs.type, 'uuid': str(fs.uuid), 'volume_name': fs.volume_name,
                             'block_size': fs.block_size, 'total_bytes': fs.block_count * fs.block_size,
                             'free_bytes': free_blocks * fs.block_size, 'inodes': fs.sb.s_inodes_count,
                             'free_inodes': fs.sb.s_free_inodes_count, 'state': fs.sb.s_state,
                             'feature_incompat': fs.sb.s_feature_incompat,
                             'last_mount': fs.last_mount},
              'directories': {}, 'files': [], 'errors': []}
    output.mkdir(parents=True, exist_ok=True)
    (output / 'files').mkdir(exist_ok=True)

    def capture(path):
        if any(row['path'] == path for row in report['files']):
            return
        try:
            node = resolve(fs, path)
            if node.filetype != stat.S_IFREG:
                return
            limit = min(node.size, 1_048_576)
            stream = node.open()
            start = max(0, node.size - limit)
            stream.seek(start)
            content = stream.read(limit)
            target = output / 'files' / path.lstrip('/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            report['files'].append({'path': path, 'inode': node.inum, 'mode': oct(node.inode.i_mode),
                                    'size': node.size, 'captured_bytes': len(content), 'tail_offset': start,
                                    'captured_sha256': hashlib.sha256(content).hexdigest()})
        except Exception as failure:
            report['errors'].append({'path': path, 'type': type(failure).__name__, 'error': str(failure)[:400]})

    def directory(path, capture_logs=False, capture_scripts=False):
        try:
            node = resolve(fs, path)
            children = []
            for child in node.iterdir():
                if child.filename in ('.', '..'):
                    continue
                if len(children) >= 1000:
                    raise ValueError('Directory listing bound reached')
                entry = {'name': child.filename, 'type': child.filetype, 'inode': child.inum,
                         'mode': oct(child.inode.i_mode), 'size': child.size}
                if child.filetype == stat.S_IFLNK:
                    entry['link'] = child.link
                children.append(entry)
                if child.filetype == stat.S_IFREG and (capture_scripts or capture_logs and
                        (re.search(r'log|stdout|stderr|message|dmesg|error|last_run', child.filename, re.I))):
                    capture(posixpath.join(path, child.filename))
            report['directories'][path] = children
        except Exception as failure:
            report['errors'].append({'path': path, 'type': type(failure).__name__, 'error': str(failure)[:400]})
        write_report(output / 'inspection.json', report)

    for path in ('/etc/inittab', '/etc/fstab', '/etc/os-release', '/etc/rc.local', '/etc/profile',
                 '/etc/console_handler.sh', '/etc/ttyGS0_handler.sh', '/root/maixcam.log',
                 '/maixapp/sys_conf.ini', '/maixapp/maixcam_lib.version',
                 '/maixapp/apps/launcher/launcher_daemon',
                 '/maixapp/tmp/last_run.log', '/root/cattle-vision/main.py',
                 '/root/cattle-vision/manage_node.py', '/root/cattle-vision/start.sh'):
        capture(path)
    for path in ('/', '/root', '/maixapp', '/maixapp/apps', '/maixapp/share', '/usr/lib', '/usr/local/lib'):
        directory(path)
    directory('/etc/init.d', capture_scripts=True)
    directory('/etc/profile.d', capture_scripts=True)
    for path in ('/maixapp/tmp', '/var/log', '/tmp', '/root/cattle-vision/logs'):
        directory(path, capture_logs=True)
    for parent in ('/usr/lib', '/usr/local/lib'):
        for child in report['directories'].get(parent, []):
            if child['name'].startswith('python3'):
                for suffix in ('site-packages', 'dist-packages'):
                    package_dir = posixpath.join(parent, child['name'], suffix)
                    directory(package_dir)
                    for entry in report['directories'].get(package_dir, []):
                        if entry['name'].lower().startswith('maixpy') and entry['name'].endswith('.dist-info'):
                            capture(posixpath.join(package_dir, entry['name'], 'METADATA'))
    report['completed_at_utc'] = datetime.now(timezone.utc).isoformat()
    write_report(output / 'inspection.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        if args.image and not args.descriptor:
            with args.image.open('rb') as image:
                report = inspect_filesystem(image, 0, args.image.stat().st_size, args.output)
        elif args.descriptor and not args.image:
            descriptor = json.loads(args.descriptor.read_text(encoding='utf-8-sig'))
            if descriptor['bus_type'] not in ('USB', 'SD', 'MMC') or not descriptor['maixcam_boot_verified']:
                raise ValueError('Only the verified external camera TF card is allowed')
            with WindowsDisk(int(descriptor['disk_number']), int(descriptor['disk_size'])) as disk:
                mbr = disk.read(512)
                if mbr[510:512] != b'\x55\xaa':
                    raise ValueError('Camera card MBR signature mismatch')
                entries = [struct.unpack_from('<II', mbr, 446 + 16 * i + 8) for i in range(4)]
                expected = (int(descriptor['partition_offset']), int(descriptor['partition_size']))
                if expected not in [(start * 512, count * 512) for start, count in entries]:
                    raise ValueError('Camera partition layout changed')
                report = inspect_filesystem(disk, *expected, args.output)
        else:
            parser.error('Use either --descriptor for the card or --image for a test image')
        print(json.dumps({'read_only': True, 'filesystem': report['filesystem'],
                          'captured_files': len(report['files']), 'errors': len(report['errors']),
                          'report': str((args.output / 'inspection.json').resolve())}, default=str), flush=True)
    except Exception as failure:
        error = {'read_only': True, 'type': type(failure).__name__, 'error': str(failure)}
        write_report(args.output / 'inspection-failed.json', error)
        print(json.dumps(error, ensure_ascii=True), flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
