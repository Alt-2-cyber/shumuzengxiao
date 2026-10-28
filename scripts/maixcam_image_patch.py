"""Build host-image patch plans and apply them through caller-owned byte I/O.

There is no device adapter or device-write CLI. The caller must verify disk
identity, MBR, filesystem UUID and exclusive access before calling apply_ranges.
All callback offsets are absolute bytes; all plan offsets are image-relative.
"""

import argparse
from contextlib import ExitStack
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat


FORMAT = 'maixcam-image-patch-v1'
SECTOR_BYTES = 512
CHUNK_BYTES = 65_536
MAX_RANGE_BYTES = 4_194_304
MAX_CHANGED_BYTES = 134_217_728
MAX_ADDRESS = 2**63 - 1


class PlanError(ValueError):
    """Invalid plan, blob or source preimage; no patch write has occurred."""


class PatchApplyError(RuntimeError):
    """A mutation failed; rollback_ok reports verified restoration and flush."""

    def __init__(self, message, *, rollback_ok, rollback_errors, touched_ranges):
        super().__init__(message)
        self.rollback_ok = rollback_ok
        self.rollback_errors = tuple(rollback_errors)
        self.touched_ranges = touched_ranges


@dataclass(frozen=True)
class _Range:
    image_offset: int
    length: int
    before_sha256: str
    after_sha256: str
    before_blob_offset: int
    after_blob_offset: int


def _integer(value, label, minimum=0, maximum=MAX_ADDRESS):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PlanError(f'Invalid {label}')
    return value


def _sha256(value, label):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
        raise PlanError(f'Invalid {label} SHA256')
    return value


def _field(mapping, name):
    if not isinstance(mapping, dict) or name not in mapping:
        raise PlanError(f'Missing or invalid plan field: {name}')
    return mapping[name]


def _regular_file(path):
    path = Path(path)
    spelling = str(path).replace('\\', '/')
    if spelling.startswith(('//./', '//?/', '/dev/')):
        raise PlanError('Only regular host files are allowed')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & 0x400):
        raise PlanError('Only regular files without symlinks/reparse points are allowed')
    return path, info


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def create_plan(original_image, working_image, output_dir):
    """Read two regular image files once; exclusively create a new plan directory.

    Changed 64 KiB pages (including a sector-aligned final partial page) are
    saved. Adjacent changed pages merge up to 4 MiB; changedBytes is page-rounded.
    Inputs are never opened for writing. Returns the JSON-compatible plan dict.
    """
    original_path, original_info = _regular_file(original_image)
    working_path, working_info = _regular_file(working_image)
    image_bytes = original_info.st_size
    if (image_bytes != working_info.st_size or image_bytes <= 0
            or image_bytes % SECTOR_BYTES or image_bytes > MAX_ADDRESS):
        raise PlanError('Image sizes must be equal, positive and multiples of 512')
    output_dir = Path(output_dir)
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    created = []
    try:
        with ExitStack() as stack:
            original = stack.enter_context(original_path.open('rb'))
            working = stack.enter_context(working_path.open('rb'))
            original_start = os.fstat(original.fileno())
            working_start = os.fstat(working.fileno())
            # Windows path/handle ctime semantics differ; compare ctime within each API only.
            if (_identity(original_start) != _identity(original_info)
                    or _identity(working_start) != _identity(working_info)):
                raise PlanError('Source images changed before reading')
            streams = []
            for name in ('before.bin', 'after.bin'):
                path = output_dir / name
                streams.append(stack.enter_context(path.open('xb')))
                created.append(path)
            before_stream, after_stream = streams
            original_hash, working_hash = hashlib.sha256(), hashlib.sha256()
            before_hash, after_hash = hashlib.sha256(), hashlib.sha256()
            ranges, changed_bytes = [], 0
            range_before_hash = range_after_hash = None
            for offset in range(0, image_bytes, CHUNK_BYTES):
                length = min(CHUNK_BYTES, image_bytes - offset)
                before, after = original.read(length), working.read(length)
                if len(before) != length or len(after) != length:
                    raise PlanError('Short source image read')
                original_hash.update(before)
                working_hash.update(after)
                if before == after:
                    continue
                if changed_bytes + length > MAX_CHANGED_BYTES:
                    raise PlanError('Changed pages exceed the 128 MiB limit')
                if (before_stream.write(before) != length
                        or after_stream.write(after) != length):
                    raise OSError('Short host blob write')
                before_hash.update(before)
                after_hash.update(after)
                if (ranges and ranges[-1]['imageOffset'] + ranges[-1]['length'] == offset
                        and ranges[-1]['length'] + length <= MAX_RANGE_BYTES):
                    ranges[-1]['length'] += length
                    range_before_hash.update(before)
                    range_after_hash.update(after)
                else:
                    range_before_hash = hashlib.sha256(before)
                    range_after_hash = hashlib.sha256(after)
                    ranges.append({'imageOffset': offset, 'length': length,
                                   'beforeBlobOffset': changed_bytes,
                                   'afterBlobOffset': changed_bytes})
                ranges[-1]['beforeSha256'] = range_before_hash.hexdigest()
                ranges[-1]['afterSha256'] = range_after_hash.hexdigest()
                changed_bytes += length
            original_end = os.fstat(original.fileno())
            working_end = os.fstat(working.fileno())
            if (original.read(1) or working.read(1)
                    or _identity(original_end) != _identity(original_start)
                    or _identity(working_end) != _identity(working_start)
                    or original_end.st_ctime_ns != original_start.st_ctime_ns
                    or working_end.st_ctime_ns != working_start.st_ctime_ns):
                raise PlanError('Source images changed during planning')
            for stream in streams:
                stream.flush()
                os.fsync(stream.fileno())
            plan = {
                'format': FORMAT, 'sectorBytes': SECTOR_BYTES, 'chunkBytes': CHUNK_BYTES,
                'imageBytes': image_bytes, 'changedBytes': changed_bytes,
                'originalSha256': original_hash.hexdigest(),
                'workingSha256': working_hash.hexdigest(),
                'beforeBlob': {'path': 'before.bin', 'bytes': changed_bytes,
                               'sha256': before_hash.hexdigest()},
                'afterBlob': {'path': 'after.bin', 'bytes': changed_bytes,
                              'sha256': after_hash.hexdigest()},
                'ranges': ranges,
            }
            plan_path = output_dir / 'plan.json'
            with plan_path.open('x', encoding='utf-8', newline='\n') as stream:
                created.append(plan_path)
                json.dump(plan, stream, indent=2, sort_keys=True)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
        return plan
    except BaseException:
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                pass
        try:
            output_dir.rmdir()
        except OSError:
            pass
        raise


def _validate_ranges(plan, image_bytes, changed_bytes):
    records = _field(plan, 'ranges')
    if not isinstance(records, list) or len(records) > MAX_CHANGED_BYTES // SECTOR_BYTES:
        raise PlanError('Invalid range list')
    ranges, previous_end, blob_offset = [], 0, 0
    for record in records:
        item = _Range(
            _integer(_field(record, 'imageOffset'), 'imageOffset'),
            _integer(_field(record, 'length'), 'range length', 1, MAX_RANGE_BYTES),
            _sha256(_field(record, 'beforeSha256'), 'range before'),
            _sha256(_field(record, 'afterSha256'), 'range after'),
            _integer(_field(record, 'beforeBlobOffset'), 'beforeBlobOffset'),
            _integer(_field(record, 'afterBlobOffset'), 'afterBlobOffset'),
        )
        if (item.image_offset % SECTOR_BYTES or item.length % SECTOR_BYTES
                or item.image_offset < previous_end
                or item.image_offset + item.length > image_bytes
                or item.before_blob_offset != blob_offset
                or item.after_blob_offset != blob_offset):
            raise PlanError('Ranges must be sorted, disjoint, sector aligned and within the image; '
                            'blob ranges must be packed in the same order')
        previous_end = item.image_offset + item.length
        blob_offset += item.length
        if blob_offset > MAX_CHANGED_BYTES:
            raise PlanError('Changed ranges exceed the 128 MiB limit')
        ranges.append(item)
    if blob_offset != changed_bytes:
        raise PlanError('Range lengths do not match changedBytes')
    return tuple(ranges)


def _load_blob(description, plan_dir, expected_name, changed_bytes):
    if _field(description, 'path') != expected_name:
        raise PlanError('Blob path must be the expected single filename within plan_dir')
    size = _integer(_field(description, 'bytes'), 'blob bytes', maximum=MAX_CHANGED_BYTES)
    digest = _sha256(_field(description, 'sha256'), 'blob')
    if size != changed_bytes:
        raise PlanError('Blob size does not match changedBytes')
    try:
        root = Path(plan_dir).resolve(strict=True)
        path, info = _regular_file(root / expected_name)
        if not root.is_dir() or path.resolve(strict=True).parent != root or info.st_size != size:
            raise PlanError('Blob must be a regular file of the declared size within plan_dir')
        with path.open('rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise PlanError('Blob is not a regular file')
            content = stream.read(size + 1)
    except OSError as error:
        raise PlanError(f'Cannot read {expected_name}: {error}') from error
    if len(content) != size or hashlib.sha256(content).hexdigest() != digest:
        raise PlanError(f'{expected_name} size or SHA256 mismatch')
    return content


def _read_exact(read_at, offset, length):
    content = read_at(offset, length)
    if not isinstance(content, (bytes, bytearray, memoryview)) or len(content) != length:
        raise OSError(f'Short or invalid read at absolute byte {offset}, expected {length}')
    return bytes(content)


def _write_exact(write_at, offset, content):
    written = write_at(offset, content)
    if written is not None and (type(written) is not int or written != len(content)):
        raise OSError(f'Short or invalid write at absolute byte {offset}, expected {len(content)}')


def _hash_gap(read_at, offset, length, original_hash, working_hash):
    while length:
        count = min(CHUNK_BYTES, length)
        content = _read_exact(read_at, offset, count)
        original_hash.update(content)
        working_hash.update(content)
        offset += count
        length -= count


def _verify_source(read_at, ranges, before, after, partition_offset, image_bytes,
                   original_sha256, working_sha256):
    original_hash, working_hash = hashlib.sha256(), hashlib.sha256()
    cursor = 0
    try:
        for item in ranges:
            _hash_gap(read_at, partition_offset + cursor, item.image_offset - cursor,
                      original_hash, working_hash)
            content = _read_exact(read_at, partition_offset + item.image_offset, item.length)
            expected = before[item.before_blob_offset:item.before_blob_offset + item.length]
            if content != expected:
                raise PlanError(f'Preimage mismatch at image byte {item.image_offset}')
            original_hash.update(content)
            working_hash.update(after[item.after_blob_offset:item.after_blob_offset + item.length])
            cursor = item.image_offset + item.length
        _hash_gap(read_at, partition_offset + cursor, image_bytes - cursor,
                  original_hash, working_hash)
    except PlanError:
        raise
    except Exception as error:
        raise PlanError(f'Source preflight read failed: {error}') from error
    if original_hash.hexdigest() != original_sha256:
        raise PlanError('Original full-image SHA256 mismatch')
    if working_hash.hexdigest() != working_sha256:
        raise PlanError('Expected working full-image SHA256 mismatch')


def _rollback(read_at, write_at, flush, touched, before, partition_offset):
    errors = []
    for item in reversed(touched):
        try:
            content = before[item.before_blob_offset:item.before_blob_offset + item.length]
            _write_exact(write_at, partition_offset + item.image_offset, content)
        except BaseException as error:
            errors.append(f'Rollback write at image byte {item.image_offset}: {error}')
    try:
        flush()
    except BaseException as error:
        errors.append(f'Rollback flush: {error}')
    for item in touched:
        try:
            content = _read_exact(read_at, partition_offset + item.image_offset, item.length)
            expected = before[item.before_blob_offset:item.before_blob_offset + item.length]
            if content != expected:
                raise OSError('Restored preimage readback mismatch')
        except BaseException as error:
            errors.append(f'Rollback readback at image byte {item.image_offset}: {error}')
    return tuple(errors)


def apply_ranges(read_at, write_at, flush, plan, plan_dir, partition_offset, partition_size,
                 *, verify_after=None):
    """Validate everything before writing; flush and verify, or attempt full rollback.

    read_at(absolute_offset, length) must return exactly length bytes.
    write_at(absolute_offset, data) returns its exact byte count or None for an
    adapter that guarantees full writes. flush() must raise on failure.
    A complete partition scan verifies originalSha256 and the virtual patched
    workingSha256 before any write. Validated blobs are frozen in memory, at
    most 128 MiB each, so later plan/blob edits cannot change pending writes.
    PlanError means no patch writes; PatchApplyError carries rollback status.
    An optional verify_after callback runs after flush/readback within the same
    rollback transaction, for filesystem-level checks on the patched data.
    """
    if _field(plan, 'format') != FORMAT:
        raise PlanError('Unsupported patch plan format')
    if (_field(plan, 'sectorBytes') != SECTOR_BYTES
            or _field(plan, 'chunkBytes') != CHUNK_BYTES):
        raise PlanError('Unsupported sector or chunk size')
    image_bytes = _integer(_field(plan, 'imageBytes'), 'imageBytes', 1)
    changed_bytes = _integer(_field(plan, 'changedBytes'), 'changedBytes',
                             maximum=MAX_CHANGED_BYTES)
    original_sha256 = _sha256(_field(plan, 'originalSha256'), 'original image')
    working_sha256 = _sha256(_field(plan, 'workingSha256'), 'working image')
    partition_offset = _integer(partition_offset, 'partition_offset')
    partition_size = _integer(partition_size, 'partition_size', 1)
    if (image_bytes != partition_size or image_bytes % SECTOR_BYTES
            or partition_offset % SECTOR_BYTES
            or partition_offset + partition_size > MAX_ADDRESS):
        raise PlanError('Invalid or mismatched verified partition boundaries')
    if not all(callable(callback) for callback in (read_at, write_at, flush)):
        raise PlanError('read_at, write_at and flush must be callable')
    if verify_after is not None and not callable(verify_after):
        raise PlanError('verify_after must be callable')
    ranges = _validate_ranges(plan, image_bytes, changed_bytes)
    before = _load_blob(_field(plan, 'beforeBlob'), plan_dir, 'before.bin', changed_bytes)
    after = _load_blob(_field(plan, 'afterBlob'), plan_dir, 'after.bin', changed_bytes)
    for item in ranges:
        old = before[item.before_blob_offset:item.before_blob_offset + item.length]
        new = after[item.after_blob_offset:item.after_blob_offset + item.length]
        if (hashlib.sha256(old).hexdigest() != item.before_sha256
                or hashlib.sha256(new).hexdigest() != item.after_sha256 or old == new):
            raise PlanError(f'Invalid before/after range data at image byte {item.image_offset}')
    _verify_source(read_at, ranges, before, after, partition_offset, image_bytes,
                   original_sha256, working_sha256)
    touched = []
    try:
        for item in ranges:
            content = after[item.after_blob_offset:item.after_blob_offset + item.length]
            # A failing callback can already have changed part of this range.
            touched.append(item)
            _write_exact(write_at, partition_offset + item.image_offset, content)
        if touched:
            flush()
            for item in touched:
                content = _read_exact(read_at, partition_offset + item.image_offset, item.length)
                expected = after[item.after_blob_offset:item.after_blob_offset + item.length]
                if content != expected:
                    raise OSError(f'Patch readback mismatch at image byte {item.image_offset}')
        if verify_after is not None:
            verify_after()
    except BaseException as error:
        rollback_errors = _rollback(read_at, write_at, flush, touched, before, partition_offset)
        restored = not rollback_errors
        raise PatchApplyError(
            f'Patch failed: {error}; rollback {"verified" if restored else "FAILED"}',
            rollback_ok=restored, rollback_errors=rollback_errors,
            touched_ranges=len(touched),
        ) from error
    return {'status': 'applied', 'rangesWritten': len(touched), 'changedBytes': changed_bytes,
            'originalSha256': original_sha256, 'workingSha256': working_sha256}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    build = commands.add_parser('build-plan', help='Compare two regular host image files')
    build.add_argument('--original', type=Path, required=True)
    build.add_argument('--working', type=Path, required=True)
    build.add_argument('--output', type=Path, required=True,
                       help='New directory for plan.json, before.bin and after.bin')
    args = parser.parse_args(argv)
    try:
        plan = create_plan(args.original, args.working, args.output)
    except (OSError, PlanError) as error:
        parser.exit(2, f'error: {error}\n')
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
