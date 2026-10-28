#!/bin/sh
set -eu

# MAIX_RECOVERY_ROOT is used only by the isolated host filesystem test.
prefix=${MAIX_RECOVERY_ROOT:-}
init_dir="$prefix/etc/init.d"
current="$init_dir/S06maixapp"
legacy_backup="$init_dir/S06maixapp.project-backup"
archive="$prefix/root/maixcam-recovery-20261027"
before_hash=b8801523f25496e107d0cfb51c110980a711a886fd3cae8dd283f6160bbf004d
original_hash=fbe527eb6d8a8766ec440173ef8c5d012daed8cd21e55f763ddf2a60dd62c784

check_hash() {
    printf '%s  %s\n' "$1" "$2" | sha256sum -c -
}

if [ -f "$archive/restore.complete" ]; then
    check_hash "$original_hash" "$current"
    test ! -e "$legacy_backup"
    echo 'Startup repair already applied and verified.'
    exit 0
fi

check_hash "$before_hash" "$current"
check_hash "$original_hash" "$legacy_backup"
test ! -e "$archive"
mkdir -p "$archive"
cp -p "$current" "$archive/S06maixapp.before"
cp -p "$legacy_backup" "$archive/S06maixapp.original"
cp -p "$legacy_backup" "$archive/S06maixapp.restored"
chmod 755 "$archive/S06maixapp.restored"
check_hash "$before_hash" "$archive/S06maixapp.before"
check_hash "$original_hash" "$archive/S06maixapp.restored"

# Backups in S??* are executed by rcS; keep them outside the startup directory.
mv "$legacy_backup" "$archive/S06maixapp.executed-backup"
mv "$archive/S06maixapp.restored" "$current"
check_hash "$original_hash" "$current"
test ! -e "$legacy_backup"
printf '%s\n' 'Original launcher/MaixVision startup restored; executable backup archived.' > "$archive/restore.complete"
sync
printf 'Recovery files: %s\n' "$archive"
