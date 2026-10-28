"""Copy the verified camera Linux partition to a host image, with a read-only source handle."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import time

from maixcam_boot_capture import save_json
from maixcam_offline_inspect import PartitionView, WindowsDisk


def verify_prefix(read_at, stream, offset, length):
    positions = {0, max(0, length - 65536), *range(0, length, 134_217_728)} if length else set()
    for position in sorted(positions):
        count = min(65536, length - position)
        stream.seek(position)
        if stream.read(count) != read_at(offset + position, count):
            raise ValueError('Partial backup differs from the camera card; refusing resume')
    digest = hashlib.sha256()
    stream.seek(0)
    remaining = length
    while remaining:
        data = stream.read(min(4_194_304, remaining))
        if not data:
            raise OSError('Partial backup was truncated')
        digest.update(data)
        remaining -= len(data)
    return digest


def copy_exact(read_at, target, offset, length, progress=lambda count: None, initial_count=0, initial_digest=None):
    digest = initial_digest if initial_digest is not None else hashlib.sha256()
    copied = initial_count
    while copied < length:
        count = min(4_194_304, length - copied)
        content = read_at(offset + copied, count)
        if len(content) != count:
            raise OSError(f'Short card read at partition byte {copied}')
        target.write(content)
        digest.update(content)
        copied += count
        progress(copied)
    return digest.hexdigest(), copied


def main():
    from dissect.extfs import ExtFS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    descriptor = json.loads(args.descriptor.read_text(encoding='utf-8-sig'))
    if descriptor['bus_type'] not in ('USB', 'SD', 'MMC') or not descriptor['maixcam_boot_verified']:
        raise ValueError('Only the verified removable camera card is allowed')
    length, offset = int(descriptor['partition_size']), int(descriptor['partition_offset'])
    if offset % 512 or length % 512 or offset + length > int(descriptor['disk_size']):
        raise ValueError('Invalid camera partition boundaries')
    if shutil.disk_usage(args.output).free < length * 2 + 1_073_741_824:
        raise OSError('Insufficient host space for original and working filesystem images')
    target = args.output / 'rootfs-original.img'
    temporary = args.output / 'rootfs-original.img.part'
    if target.exists():
        raise FileExistsError('A completed backup already exists and will not be overwritten')
    resume_bytes = temporary.stat().st_size if temporary.exists() else 0
    if resume_bytes % 512 or resume_bytes > length:
        raise ValueError('Invalid partial backup length')
    started = time.monotonic()
    last_reported = -10.0
    state = {'phase': 'validating', 'source_read_only': True, 'partition_bytes': length,
             'copied_bytes': resume_bytes, 'resumed_bytes': resume_bytes, 'image': str(target.resolve()),
             'started_at_utc': datetime.now(timezone.utc).isoformat()}
    save_json(args.output / 'backup-progress.json', state)

    def progress(copied):
        nonlocal last_reported
        elapsed = time.monotonic() - started
        if elapsed - last_reported >= 2 or copied == length:
            state.update(phase='copying', copied_bytes=copied, percent=round(copied / length * 100, 2),
                         elapsed_seconds=round(elapsed, 1), mib_per_second=round((copied - resume_bytes) / 1_048_576 / max(elapsed, 0.01), 2),
                         updated_at_utc=datetime.now(timezone.utc).isoformat())
            save_json(args.output / 'backup-progress.json', state)
            last_reported = elapsed
    try:
        with WindowsDisk(int(descriptor['disk_number']), int(descriptor['disk_size'])) as source:
            mbr = source.read(512)
            expected = (offset // 512, length // 512)
            if mbr[510:512] != b'\x55\xaa' or expected not in [struct.unpack_from('<II', mbr, 454 + 16 * i) for i in range(4)]:
                raise ValueError('Camera MBR/partition differs from the verified descriptor')
            fs = ExtFS(PartitionView(source, offset, length))
            if str(fs.uuid) != '22a051af-0675-4d62-bed7-98e0dde8dfc0':
                raise ValueError('This is not the verified camera filesystem UUID')
            state['filesystem_uuid'] = str(fs.uuid)
            with temporary.open('r+b' if resume_bytes else 'xb') as stream:
                digest_state = verify_prefix(source._read_sectors, stream, offset, resume_bytes)
                stream.seek(resume_bytes)
                state['resume_prefix_sampled_and_hashed'] = True
                digest, copied = copy_exact(source._read_sectors, stream, offset, length, progress,
                                            initial_count=resume_bytes, initial_digest=digest_state)
                stream.flush()
                os.fsync(stream.fileno())
        temporary.rename(target)
        state.update(phase='complete', copied_bytes=copied, percent=100.0, sha256=digest,
                     completed_at_utc=datetime.now(timezone.utc).isoformat())
        save_json(args.output / 'backup-progress.json', state)
        save_json(args.output / 'backup-summary.json', {'descriptor': descriptor, **state})
        print(json.dumps(state, indent=2), flush=True)
    except Exception as failure:
        state.update(phase='failed', error_type=type(failure).__name__, error=str(failure))
        save_json(args.output / 'backup-progress.json', state)
        raise


if __name__ == '__main__':
    main()
