"""Exercise image patch planning and callback I/O using host fixtures only."""

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

try:
    import maixcam_image_patch as patcher
except ModuleNotFoundError:
    patcher = None


PAGE = 65_536
MIB = 1_048_576


class MemoryPartition:
    def __init__(self, image):
        self.offset = 1024
        self.prefix = b'P' * self.offset
        self.suffix = b'S' * 1536
        self.initial = self.prefix + image + self.suffix
        self.stream = io.BytesIO(self.initial)
        self.writes = []
        self.reads = []
        self.flush_count = 0

    def read_at(self, offset, length):
        self.reads.append((offset, length))
        self.stream.seek(offset)
        return self.stream.read(length)

    def write_at(self, offset, data):
        self.writes.append((offset, len(data)))
        self.stream.seek(offset)
        return self.stream.write(data)

    def flush(self):
        self.flush_count += 1
        self.stream.flush()


class ImagePatchTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(patcher, 'maixcam_image_patch has not been implemented')
        temporary = tempfile.TemporaryDirectory(prefix='maixcam-image-patch-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.original = b'A' * (4 * PAGE + 512)
        working = bytearray(self.original)
        for offset, value in ((0, 66), (2 * PAGE + 7, 67),
                              (3 * PAGE + 9, 68), (4 * PAGE + 1, 69)):
            working[offset] = value
        self.working = bytes(working)
        self.original_path = self.root / 'original.img'
        self.working_path = self.root / 'working.img'
        self.original_path.write_bytes(self.original)
        self.working_path.write_bytes(self.working)
        self.plan_dir = self.root / 'plan'

    def build(self):
        return patcher.create_plan(self.original_path, self.working_path, self.plan_dir)

    def apply(self, plan, target, **callbacks):
        return patcher.apply_ranges(
            callbacks.get('read_at', target.read_at),
            callbacks.get('write_at', target.write_at),
            callbacks.get('flush', target.flush),
            plan, self.plan_dir, target.offset, len(self.original),
            verify_after=callbacks.get('verify_after'),
        )

    def assert_no_write(self, target):
        self.assertEqual(target.writes, [])
        self.assertEqual(target.flush_count, 0)
        self.assertEqual(target.stream.getvalue(), target.initial)

    def test_plan_contains_only_changed_pages_and_full_image_hashes(self):
        plan = self.build()
        self.assertEqual(plan['imageBytes'], 4 * PAGE + 512)
        self.assertEqual(plan['originalSha256'], hashlib.sha256(self.original).hexdigest())
        self.assertEqual(plan['workingSha256'], hashlib.sha256(self.working).hexdigest())
        self.assertEqual([(r['imageOffset'], r['length']) for r in plan['ranges']],
                         [(0, PAGE), (2 * PAGE, 2 * PAGE + 512)])
        self.assertEqual(plan['changedBytes'], 3 * PAGE + 512)
        self.assertEqual((self.plan_dir / 'before.bin').read_bytes(),
                         self.original[:PAGE] + self.original[2 * PAGE:])
        self.assertEqual((self.plan_dir / 'after.bin').read_bytes(),
                         self.working[:PAGE] + self.working[2 * PAGE:])
        self.assertEqual(json.loads((self.plan_dir / 'plan.json').read_text()), plan)
        self.assertEqual(self.original_path.read_bytes(), self.original)
        self.assertEqual(self.working_path.read_bytes(), self.working)

    def test_adjacent_changes_split_at_four_mib_including_partial_last_page(self):
        self.original_path.write_bytes(b'A' * (5 * MIB + 512))
        self.working_path.write_bytes(b'B' * (5 * MIB + 512))
        plan = self.build()
        self.assertEqual([(r['imageOffset'], r['length']) for r in plan['ranges']],
                         [(0, 4 * MIB), (4 * MIB, MIB + 512)])

    def test_rejects_unequal_and_non_sector_sized_images_without_output(self):
        for content in (self.working[:-512], self.working + b'X'):
            with self.subTest(size=len(content)):
                self.working_path.write_bytes(content)
                with self.assertRaises(patcher.PlanError):
                    self.build()
                self.assertFalse(self.plan_dir.exists())
        self.original_path.write_bytes(b'X' * 513)
        self.working_path.write_bytes(b'Y' * 513)
        with self.assertRaises(patcher.PlanError):
            self.build()
        self.assertFalse(self.plan_dir.exists())

    def test_rejects_empty_images(self):
        self.original_path.write_bytes(b'')
        self.working_path.write_bytes(b'')
        with self.assertRaises(patcher.PlanError):
            self.build()

    def test_existing_plan_is_never_overwritten(self):
        self.build()
        saved = {p.name: p.read_bytes() for p in self.plan_dir.iterdir()}
        with self.assertRaises(FileExistsError):
            self.build()
        self.assertEqual({p.name: p.read_bytes() for p in self.plan_dir.iterdir()}, saved)

    def test_windows_path_and_handle_ctime_difference_does_not_reject_stable_images(self):
        real_lstat = Path.lstat

        def windows_path_stat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            fields = {name: getattr(info, name) for name in dir(info) if name.startswith('st_')}
            fields['st_ctime_ns'] -= 1_000_000_000
            return SimpleNamespace(**fields)

        with mock.patch.object(Path, 'lstat', windows_path_stat):
            plan = self.build()
        self.assertEqual(plan['originalSha256'], hashlib.sha256(self.original).hexdigest())

    def test_change_limit_failure_removes_only_new_incomplete_plan(self):
        with mock.patch.object(patcher, 'MAX_CHANGED_BYTES', PAGE):
            with self.assertRaises(patcher.PlanError):
                self.build()
        self.assertFalse(self.plan_dir.exists())
        self.assertEqual(self.original_path.read_bytes(), self.original)
        self.assertEqual(self.working_path.read_bytes(), self.working)

    def test_exact_patch_preserves_every_byte_outside_changed_ranges(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        result = self.apply(plan, target)
        self.assertEqual(target.stream.getvalue(), target.prefix + self.working + target.suffix)
        self.assertEqual(target.writes, [(1024, PAGE), (1024 + 2 * PAGE, 2 * PAGE + 512)])
        self.assertEqual(target.flush_count, 1)
        self.assertEqual(result['rangesWritten'], 2)
        self.assertEqual(result['changedBytes'], 3 * PAGE + 512)
        for offset, length in target.reads + target.writes:
            self.assertGreaterEqual(offset, target.offset)
            self.assertLessEqual(offset + length, target.offset + len(self.original))

    def test_noop_plan_performs_no_writes_or_flush(self):
        self.working_path.write_bytes(self.original)
        plan = self.build()
        target = MemoryPartition(self.original)
        result = self.apply(plan, target)
        self.assertEqual(plan['ranges'], [])
        self.assertEqual(result['rangesWritten'], 0)
        self.assert_no_write(target)

    def test_post_verification_failure_restores_all_original_bytes(self):
        plan = self.build()
        target = MemoryPartition(self.original)

        def reject_startup():
            self.assertEqual(target.stream.getvalue(), target.prefix + self.working + target.suffix)
            self.assertEqual(target.flush_count, 1)
            raise ValueError('Startup files could not be verified')

        with self.assertRaises(patcher.PatchApplyError) as failure:
            self.apply(plan, target, verify_after=reject_startup)
        self.assertTrue(failure.exception.rollback_ok)
        self.assertEqual(target.stream.getvalue(), target.initial)
        self.assertEqual(target.flush_count, 2)

    def test_post_verification_runs_on_flushed_verified_data(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        observed = []

        def verify_startup():
            observed.append((target.stream.getvalue(), target.flush_count))

        result = self.apply(plan, target, verify_after=verify_startup)
        self.assertEqual(observed, [(target.prefix + self.working + target.suffix, 1)])
        self.assertEqual(result['status'], 'applied')

    def test_invalid_post_verifier_is_rejected_without_writes(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target, verify_after='invalid')
        self.assert_no_write(target)

    def test_later_preimage_mismatch_prevents_even_first_write(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        target.stream.seek(target.offset + 2 * PAGE)
        target.stream.write(b'Z')
        target.initial = target.stream.getvalue()
        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target)
        self.assert_no_write(target)

    def test_change_in_unpatched_page_fails_full_source_hash_before_writes(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        target.stream.seek(target.offset + PAGE)
        target.stream.write(b'Z')
        target.initial = target.stream.getvalue()
        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target)
        self.assert_no_write(target)

    def test_tampered_before_or_after_blob_is_rejected_without_writes(self):
        plan = self.build()
        for filename in ('before.bin', 'after.bin'):
            with self.subTest(blob=filename):
                path = self.plan_dir / filename
                original = path.read_bytes()
                path.write_bytes(b'Z' + original[1:])
                target = MemoryPartition(self.original)
                with self.assertRaises(patcher.PlanError):
                    self.apply(plan, target)
                self.assert_no_write(target)
                path.write_bytes(original)

    def test_rehashed_blob_tamper_still_fails_expected_working_image_hash(self):
        plan = self.build()
        path = self.plan_dir / 'after.bin'
        changed = b'Z' + path.read_bytes()[1:]
        path.write_bytes(changed)
        plan['afterBlob']['sha256'] = hashlib.sha256(changed).hexdigest()
        plan['ranges'][0]['afterSha256'] = hashlib.sha256(changed[:PAGE]).hexdigest()
        target = MemoryPartition(self.original)
        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target)
        self.assert_no_write(target)

    def test_blob_path_traversal_and_absolute_paths_are_rejected(self):
        plan = self.build()
        for path in ('../after.bin', '..\\after.bin', '/after.bin',
                     'C:\\outside\\after.bin', 'sub/after.bin', 'before.bin'):
            with self.subTest(path=path):
                invalid = copy.deepcopy(plan)
                invalid['afterBlob']['path'] = path
                target = MemoryPartition(self.original)
                with self.assertRaises(patcher.PlanError):
                    self.apply(invalid, target)
                self.assert_no_write(target)

    def test_blob_symlink_is_rejected(self):
        plan = self.build()
        path = self.plan_dir / 'after.bin'
        outside = self.root / 'outside.bin'
        path.rename(outside)
        try:
            path.symlink_to(outside)
        except OSError as error:
            self.skipTest(f'Host does not permit symlink fixtures: {error}')
        target = MemoryPartition(self.original)
        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target)
        self.assert_no_write(target)

    def test_malformed_ranges_or_metadata_are_rejected_before_writes(self):
        plan = self.build()
        mutations = [
            ('negative', lambda p: p['ranges'][0].update(imageOffset=-512)),
            ('unaligned offset', lambda p: p['ranges'][0].update(imageOffset=1)),
            ('unaligned length', lambda p: p['ranges'][0].update(length=513)),
            ('empty range', lambda p: p['ranges'][0].update(length=0)),
            ('beyond partition', lambda p: p['ranges'][1].update(imageOffset=len(self.original))),
            ('overlap', lambda p: p['ranges'][1].update(imageOffset=0)),
            ('unordered', lambda p: p['ranges'].reverse()),
            ('boolean offset', lambda p: p['ranges'][0].update(imageOffset=True)),
            ('blob offset', lambda p: p['ranges'][0].update(beforeBlobOffset=512)),
            ('range hash', lambda p: p['ranges'][-1].update(afterSha256='0' * 64)),
            ('before hash', lambda p: p['ranges'][-1].update(beforeSha256='0' * 64)),
            ('source hash', lambda p: p.update(originalSha256='0' * 64)),
            ('working hash', lambda p: p.update(workingSha256='0' * 64)),
            ('image size', lambda p: p.update(imageBytes=len(self.original) + 512)),
            ('blob size', lambda p: p['afterBlob'].update(bytes=p['changedBytes'] + 512)),
            ('change size', lambda p: p.update(changedBytes=128 * MIB + 512)),
            ('format', lambda p: p.update(format='unknown')),
        ]
        for label, mutate in mutations:
            with self.subTest(case=label):
                invalid = copy.deepcopy(plan)
                mutate(invalid)
                target = MemoryPartition(self.original)
                with self.assertRaises(patcher.PlanError):
                    self.apply(invalid, target)
                self.assert_no_write(target)

    def test_invalid_partition_boundaries_are_rejected_before_writes(self):
        plan = self.build()
        for offset, size in ((-512, len(self.original)), (1, len(self.original)),
                             (1024, len(self.original) - 512),
                             (True, len(self.original)), (2**63 - 512, len(self.original))):
            with self.subTest(offset=offset, size=size):
                target = MemoryPartition(self.original)
                with self.assertRaises(patcher.PlanError):
                    patcher.apply_ranges(target.read_at, target.write_at, target.flush,
                                         plan, self.plan_dir, offset, size)
                self.assert_no_write(target)

    def test_short_preflight_read_causes_no_write(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target, read_at=lambda offset, length: b'X' * (length - 1))
        self.assert_no_write(target)

    def test_adapter_preflight_exception_is_reported_as_plan_error_without_writes(self):
        plan = self.build()
        target = MemoryPartition(self.original)

        def failed_read(offset, length):
            raise RuntimeError('Injected adapter read failure')

        with self.assertRaises(patcher.PlanError):
            self.apply(plan, target, read_at=failed_read)
        self.assert_no_write(target)

    def test_adapter_can_return_none_after_a_complete_write(self):
        plan = self.build()
        target = MemoryPartition(self.original)

        def complete_write(offset, data):
            target.write_at(offset, data)

        self.apply(plan, target, write_at=complete_write)
        self.assertEqual(target.stream.getvalue(), target.prefix + self.working + target.suffix)

    def test_callback_cannot_replace_validated_offsets_or_pending_blob_bytes(self):
        plan = self.build()
        target = MemoryPartition(self.original)

        def change_plan_after_validation(offset, data):
            if not target.writes:
                plan['ranges'][1]['imageOffset'] = 0
                (self.plan_dir / 'after.bin').write_bytes(b'Z' * plan['changedBytes'])
            return target.write_at(offset, data)

        self.apply(plan, target, write_at=change_plan_after_validation)
        self.assertEqual(target.stream.getvalue(), target.prefix + self.working + target.suffix)

    def test_partial_current_write_rolls_back_it_and_previously_written_ranges(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        calls = 0

        def partial_write(offset, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                target.write_at(offset, data[:512])
                raise OSError('Injected partial write failure')
            return target.write_at(offset, data)

        with self.assertRaises(patcher.PatchApplyError) as caught:
            self.apply(plan, target, write_at=partial_write)
        self.assertTrue(caught.exception.rollback_ok)
        self.assertEqual(caught.exception.rollback_errors, ())
        self.assertEqual(caught.exception.touched_ranges, 2)
        self.assertEqual(target.stream.getvalue(), target.initial)
        self.assertEqual([offset for offset, _ in target.writes],
                         [1024, 1024 + 2 * PAGE, 1024 + 2 * PAGE, 1024])

    def test_short_write_return_triggers_rollback(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        calls = 0

        def short_write(offset, data):
            nonlocal calls
            calls += 1
            return target.write_at(offset, data[:512] if calls == 1 else data)

        with self.assertRaises(patcher.PatchApplyError) as caught:
            self.apply(plan, target, write_at=short_write)
        self.assertTrue(caught.exception.rollback_ok)
        self.assertEqual(target.stream.getvalue(), target.initial)

    def test_readback_mismatch_restores_all_written_ranges(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        injected = False

        def bad_readback(offset, length):
            nonlocal injected
            data = target.read_at(offset, length)
            if target.flush_count == 1 and not injected:
                injected = True
                return b'Z' + data[1:]
            return data

        with self.assertRaises(patcher.PatchApplyError) as caught:
            self.apply(plan, target, read_at=bad_readback)
        self.assertTrue(caught.exception.rollback_ok)
        self.assertEqual(caught.exception.touched_ranges, 2)
        self.assertEqual(target.stream.getvalue(), target.initial)

    def test_flush_failure_triggers_rollback_and_second_flush(self):
        plan = self.build()
        target = MemoryPartition(self.original)

        def fail_first_flush():
            target.flush()
            if target.flush_count == 1:
                raise OSError('Injected flush failure')

        with self.assertRaises(patcher.PatchApplyError) as caught:
            self.apply(plan, target, flush=fail_first_flush)
        self.assertTrue(caught.exception.rollback_ok)
        self.assertEqual(target.flush_count, 2)
        self.assertEqual(target.stream.getvalue(), target.initial)

    def test_rollback_failure_is_reported_and_other_ranges_still_restore(self):
        plan = self.build()
        target = MemoryPartition(self.original)
        calls = 0

        def fail_write_and_first_rollback(offset, data):
            nonlocal calls
            calls += 1
            if calls == 2:
                target.write_at(offset, data[:512])
                raise OSError('Injected partial write')
            if calls == 3:
                raise OSError('Injected rollback failure')
            return target.write_at(offset, data)

        with self.assertRaises(patcher.PatchApplyError) as caught:
            self.apply(plan, target, write_at=fail_write_and_first_rollback)
        self.assertFalse(caught.exception.rollback_ok)
        self.assertTrue(caught.exception.rollback_errors)
        self.assertEqual(calls, 4)
        self.assertEqual(target.read_at(1024, PAGE), self.original[:PAGE])
        self.assertEqual(target.stream.getvalue()[:1024], target.prefix)
        self.assertEqual(target.stream.getvalue()[-1536:], target.suffix)

    def test_cli_build_plan_only_uses_fixture_images(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = patcher.main(['build-plan', '--original', str(self.original_path),
                                   '--working', str(self.working_path),
                                   '--output', str(self.plan_dir)])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())['imageBytes'], len(self.original))


if __name__ == '__main__':
    unittest.main()
