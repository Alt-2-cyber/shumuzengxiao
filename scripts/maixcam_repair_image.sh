#!/bin/sh
set -eu

image=$1
evidence=$2
expected_uuid=${3:-22a051af-0675-4d62-bed7-98e0dde8dfc0}
original=${4:-"${image%/*}/rootfs-original.img"}
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
case "$image" in */rootfs-working.img) ;; *) echo 'Refusing an original image or physical device.' >&2; exit 2 ;; esac
test -f "$image"
test ! -L "$image"
test -f "$original"
test ! -L "$original"
test ! "$image" -ef "$original"
test "$(stat -c %h "$image")" = 1
test "$(stat -c %s "$image")" = "$(stat -c %s "$original")"
test "$(/usr/sbin/blkid -p -s UUID -o value "$image")" = "$expected_uuid"
mkdir -p "$evidence"

# Replay/repair only the working copy; the original backup remains immutable.
set +e
/usr/sbin/e2fsck -p "$image" > "$evidence/fsck-before.log" 2>&1
check_status=$?
set -e
case "$check_status" in 0|1|2) ;; *) cat "$evidence/fsck-before.log" >&2; exit "$check_status" ;; esac

mount_dir=$(mktemp -d /mnt/maixcam-image-repair.XXXXXX)
mounted=0
cleanup() {
    if [ "$mounted" = 1 ]; then /bin/umount "$mount_dir"; fi
    rmdir "$mount_dir"
}
trap cleanup EXIT
/bin/mount -t ext4 -o loop,rw,noinit_itable,nodiscard "$image" "$mount_dir"
mounted=1
tar -C "$mount_dir" -cpf "$evidence/startup-before.tar" \
    etc/init.d/S06maixapp etc/init.d/S06maixapp.project-backup etc/init.d/rcS etc/inittab
printf '%s  %s\n' dc1615df9f2012b20b81ffad8e07e16293039ba7fd897854ca3646d6cfea0c0f \
    "$mount_dir/etc/init.d/rcS" | sha256sum -c -
MAIX_RECOVERY_ROOT="$mount_dir" /bin/sh "$script_dir/maixcam_restore_startup.sh" > "$evidence/startup-repair.log" 2>&1
archive="$mount_dir/root/maixcam-recovery-20261027"
cp -p "$mount_dir/etc/init.d/rcS" "$archive/rcS.before"
cp "$script_dir/maixcam_rcS_trace.sh" "$archive/rcS.restored"
chmod 755 "$archive/rcS.restored"
mv "$archive/rcS.restored" "$mount_dir/etc/init.d/rcS"
/bin/sh -n "$mount_dir/etc/init.d/rcS"
test ! -e "$mount_dir/etc/init.d/S06maixapp.project-backup"
sha256sum "$mount_dir/etc/init.d/S06maixapp" "$mount_dir/etc/init.d/rcS" > "$evidence/repaired-files.sha256"
sync
/bin/umount "$mount_dir"
mounted=0
/usr/sbin/e2fsck -f -n "$image" > "$evidence/fsck-after.log" 2>&1
printf 'Working image repaired and filesystem verification passed.\n'
