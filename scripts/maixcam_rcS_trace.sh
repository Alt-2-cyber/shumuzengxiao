#!/bin/sh

# This prefix is empty on the camera and set only by the isolated host test.
recovery_root=${MAIX_RECOVERY_ROOT:-}
recovery_trace="$recovery_root/root/maixcam-recovery-20261027/startup-trace.log"
mkdir -p "${recovery_trace%/*}"
printf 'BOOT startup trace\n' > "$recovery_trace"
recovery_status=0

for i in "$recovery_root"/etc/init.d/S??* ;do
    [ ! -f "$i" ] && continue
    printf 'BEGIN %s\n' "$i" >> "$recovery_trace"
    sync
    case "$i" in
        *.sh)
            (
                trap - INT QUIT TSTP
                set start
                . "$i"
            )
            ;;
        *)
            "$i" start
            ;;
    esac
    recovery_status=$?
    printf 'END %s status=%s\n' "$i" "$recovery_status" >> "$recovery_trace"
    sync
done
exit "$recovery_status"
