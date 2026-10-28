"""Exercise the exact repair against copies, including its refusal to overwrite changes."""

import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.run/maixcam-recovery-20261027/offline-inspection-20261027-204938/files/etc/init.d'


def linux_path(path):
    value = str(path.resolve()).replace('\\', '/')
    return '/mnt/' + value[0].lower() + value[2:]


class StartupRestoreTests(unittest.TestCase):
    def test_image_repair_rejects_hardlinks_without_changing_original(self):
        command = r'''
set -eu
fixture=$(mktemp -d /tmp/maixcam-image-identity-test.XXXXXX)
trap 'rm -rf "$fixture"' EXIT
original="$fixture/rootfs-original.img"
working="$fixture/rootfs-working.img"
truncate -s 8388608 "$original"
/usr/sbin/mke2fs -q -t ext4 -F "$original"
ln "$original" "$working"
before=$(sha256sum "$original" | cut -d ' ' -f 1)
uuid=$(/usr/sbin/blkid -p -s UUID -o value "$original")
if /bin/sh "$1" "$working" "$fixture/evidence" "$uuid"; then exit 99; fi
after=$(sha256sum "$original" | cut -d ' ' -f 1)
test "$before" = "$after"
test ! -e "$fixture/evidence"
'''
        result = subprocess.run(['wsl.exe', '-u', 'root', '-e', '/bin/sh', '-c', command, 'test',
                                 linux_path(ROOT / 'scripts/maixcam_repair_image.sh')],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))

    def test_trace_records_each_service_and_continues_after_failure(self):
        command = r'''
set -eu
fixture=$(mktemp -d /tmp/maixcam-startup-test.XXXXXX)
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/etc/init.d"
printf '#!/bin/sh\nprintf "sensitive-data-not-for-trace\\n"\nexit 3\n' > "$fixture/etc/init.d/S01first"
printf '#!/bin/sh\nexit 0\n' > "$fixture/etc/init.d/S02second"
chmod 755 "$fixture/etc/init.d/S01first" "$fixture/etc/init.d/S02second"
MAIX_RECOVERY_ROOT="$fixture" sh "$1"
trace="$fixture/root/maixcam-recovery-20261027/startup-trace.log"
grep -q 'S01first status=3' "$trace"
grep -q 'S02second status=0' "$trace"
if grep -q 'sensitive-data-not-for-trace' "$trace"; then exit 99; fi
'''
        result = subprocess.run(['wsl.exe', '-u', 'root', '-e', '/bin/sh', '-c', command, 'test',
                                 linux_path(ROOT / 'scripts/maixcam_rcS_trace.sh')],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))

    def test_restore_idempotency_and_tamper_rejection(self):
        command = r'''
set -eu
fixture=$(mktemp -d /tmp/maixcam-startup-test.XXXXXX)
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/etc/init.d" "$fixture/root"
cp "$1/S06maixapp" "$fixture/etc/init.d/S06maixapp"
cp "$1/S06maixapp.project-backup" "$fixture/etc/init.d/S06maixapp.project-backup"
MAIX_RECOVERY_ROOT="$fixture" sh "$2"
cmp "$fixture/etc/init.d/S06maixapp" "$1/S06maixapp.project-backup"
test ! -e "$fixture/etc/init.d/S06maixapp.project-backup"
test -f "$fixture/root/maixcam-recovery-20261027/S06maixapp.before"
MAIX_RECOVERY_ROOT="$fixture" sh "$2"
changed=$(mktemp -d /tmp/maixcam-startup-test.XXXXXX)
mkdir -p "$changed/etc/init.d" "$changed/root"
cp "$1/S06maixapp" "$changed/etc/init.d/S06maixapp"
cp "$1/S06maixapp.project-backup" "$changed/etc/init.d/S06maixapp.project-backup"
printf '\n# user change\n' >> "$changed/etc/init.d/S06maixapp"
if MAIX_RECOVERY_ROOT="$changed" sh "$2"; then exit 99; fi
test -f "$changed/etc/init.d/S06maixapp.project-backup"
test ! -d "$changed/root/maixcam-recovery-20261027"
rm -rf "$changed"
'''
        result = subprocess.run(['wsl.exe', '-e', '/bin/sh', '-c', command, 'test', linux_path(SOURCE),
                                 linux_path(ROOT / 'scripts/maixcam_restore_startup.sh')],
                                capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout.decode(errors='replace') + result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
