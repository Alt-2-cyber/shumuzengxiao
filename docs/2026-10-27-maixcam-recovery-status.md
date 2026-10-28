# MaixCAM application recovery status

Checked 2026-10-28. The user booted the repaired card and confirmed that system
applications open and WiFi connects. USB-network SSH is also restored. Offline
repair passed readback/startup-file verification; a complete original backup
and separate repaired working image are retained.

## Observations

- User identifies COM42 as the camera UART adapter, with RXD to A16/TX,
  TXD to A17/RX, shared ground and separate camera USB power.
- Present USB adapter is CH340 VID1A86/PID7523, driver problem code0,
  WCH version3.9.2024.9. COM42 maps to the actual `\Device\Serial2`.
- Console reads at115200, with DTR off/on, and bounded9600/57600/921600
  probes returned zero bytes. No command was executed on the camera shell.
- Read-only official Maix protocol current-app and app-list requests also
  returned zero bytes. This cannot distinguish a disabled service from a
  wiring/electrical problem.
- Camera USB composite VID359F/PID2120 and RNDIS/NCM interfaces are present
  without Windows driver error. Both network links report disconnected.
  IPv4 binding is enabled. The known USB SSH addresses timed out.
- Earlier probes had no removable/USB TF volume, and the user initially had
  no card reader. They subsequently supplied one; see the TF section below.
- The user subsequently corrected the TX/RX loopback connection. Five fresh
  loopback checks passed: 1347 bytes sent and 1347 received, zero mismatches,
  including ASCII, all256 byte values, repeated bit patterns, 115200/9600 baud
  and DTR off/on. The CH340 host/adapter loopback is now verified. This does
  not establish camera-side wiring, console enablement or application health.
- After a transient USB configuration error on COM42, the user reassigned the
  same CH340 instance to COM11. COM11 now opens and configures correctly at
  1152008N1, but a24-second read and two official read-only protocol queries
  still returned zero bytes. The user then confirmed a camera-only power
  cycle. A fresh28-second COM11 read after that confirmation received zero
  bytes and sent no shell command. RNDIS/NCM remained media-disconnected,
  with only tentative APIPA addresses. The confirmed loopback excludes an
  unverified adapter failure as the default assumption, but camera-side
  contacts/ground/voltage and UART console enablement remain unverified.
  Those initial listeners were closed. No camera shell command has run.

## Wiring photographs supplied later

The CH340 connector photo clearly establishes white=GND, purple=RXD,
blue=TXD; the3V3/VCC/5V header pins are unconnected. The camera photo shows
purple, blue, white on the first three adjacent positions at the lens end.
Compared with the official ordinary MaixCAM/LicheeRV Nano layout, these
positions appear to be A17/RX, A16/TX, GND respectively. Camera silkscreen
is covered by the plugs, so the signal swap remains a testable hypothesis,
not an electrically verified fault.

Official reference images are cached under `.run/hardware-integration-20261025`:
`maixcam-rv-nano-pinout.jpg` and `maixcam-board-overview.png`. The separate
MaixCAM-Pro picture has a different connector layout and is not used to
assign the ordinary board's physical pins.

A receive-only check was requested: power off the camera, keep white
ground, disconnect blue from the camera, move purple to blue's former
A16/TX position, then power on. The user confirmed this adjustment and power
cycle. The only enumerated CH340 subsequently appeared on COM22, USB instance
`USB\VID_1A86&PID_7523\5&4D3B25D&0&9`; COM11 was absent. A fresh30-second
1152008N1 receive-only capture on COM22 sent no bytes and received zero bytes.
RNDIS and NCM remained media-disconnected. This checks output after the user
reported power-on; it does not establish that the full boot interval was
captured. No camera repair or UART terminal enablement is claimed.

Evidence: `.run/hardware-integration-20261025/maixcam-rx-only-20261027-175737.log`
(empty). The remaining practical path is direct TF boot configuration access
to verify/enable the official console, unless a separate camera maintenance
connection becomes available. No more camera-side wiring fault is inferred
from the zero-byte capture alone.

## Official console requirement

[Sipeed UART manual](https://wiki.sipeed.com/maixpy/doc/zh/peripheral/uart.html)
states that MaixCAM/MaixCAM-Pro UART0 needs the `consoledev` line in
`/boot/uEnv.txt` commented or removed before UART terminal/boot logging is
available. A16/TX and A17/RX are the correct pins. Thus zero bytes alone do
not establish bad wiring or a faulty adapter, and terminal enablement on
this particular card is still unknown.

The main image/launcher is booting according to the user's screen report,
but WiFi and camera system applications black out. Without device logs,
disk usage, process list or filesystem inspection, the cause remains
unconfirmed. No driver reinstall or blind system reflash was attempted.

## Prepared recovery path

Borrow a USB reader that accepts TF/microSD. Power off MaixCAM before removing
the card. Connect the card to Windows; ignore any request to format a Linux
partition. Inspect the readable boot volume and its actual `uEnv.txt` first.

`scripts/enable-maixcam-console.ps1 -DriveRoot E:\` inspects only, using the
actual TF boot letter in place of E. Add `-Apply` to back up and comment only
active `consoledev` assignments. The helper rejects internal disks, linked
files and binary content. It stores byte-identical backups on both the card
and host, preserves UTF-8 BOM/newlines, and verifies the change.

After safe card ejection and reinstallation, enumerate the current CH340 port
(latest COM22) and capture at1152008N1.
Read boot output, `/maixapp/tmp/last_run.log`, `df -h`, memory and process
state. Fix the observed cause while preserving project models/configuration.
Do not replace the image until storage evidence and backups justify it.

`scripts/test_enable_maixcam_console.ps1` verifies six transformation cases
without opening or modifying the camera/card. This preparation is not proof
that the application failure is fixed.

## TF Card Connected And Console Enabled

The user connected the camera TF card as E. Verified hardware identity:
Generic STORAGE DEVICE, USB/removable, disk2,31,273,779,200 bytes, MBR.
E is the FAT boot partition, about16MiB; the separate Linux partition is
not mounted by Windows. `E:\ver` is `maixcam-2026-01-24-maixpy-v4.12.5`;
the selected board is ordinary `maixcam`, not `maixcam_pro`.

The actual original `E:\uEnv.txt` was `consoledev=/dev/tty3` with CRLF.
This directly explains why a Linux UART terminal was not configured; it
does not identify the cause of the system-app black screen.

All25 readable boot files were copied to the host and verified by SHA256,
12,261,334 bytes in total. Backup:
`.run/maixcam-recovery-20261027/boot-before-console-20261027-201634`.
This backup includes private network configuration and must not be published.

The tested helper commented only the console assignment, preserving CRLF:
`# consoledev=/dev/tty3`. A22-byte original and24-byte result were verified,
with byte-identical backups on host and card before writing.

- Original SHA256: `6f5cc47bd2253e5e60ba28c30316c46783d1a419346dc5b541ad0ed0f8554029`.
- Updated SHA256: `478cd09e99d4dc3ef1e495d98cf57543a3c8fdbf8fe8234c501bb1d2da9883`.
- Host original: `.run/maixcam-recovery-20261027/uEnv-20261027-201636-841.txt`.
- Card original: `uEnv.txt.before-console-20261027-201636-841`.

CH340 was not enumerated while the card reader was connected. A passive
background watcher, `scripts/maixcam_boot_capture.py`, now waits for a real
USB TTL adapter, automatically selects its current COM number and reconnects
after disconnects. It never transmits bytes or logs in. Captured console
text is credential-redacted and continuously saved to `boot-console.log`,
with `capture-status.json` beside it. Creating `stop-capture` in that capture
directory stops it cleanly. Three watcher tests cover no ESP32/Bluetooth
selection, no transmission, reconnects and split-key credential redaction.

The current watcher was started at20:21 local time, PID29444, with a2-hour
limit. Evidence directory:
`.run/maixcam-recovery-20261027/capture-20261027-202110`.
Its initial state is `waiting_adapter`. The Windows shell safely ejected
E after configuration verification; `E:\uEnv.txt` became inaccessible.

Next physical step: safely remove the card reader, reinstall TF with the
camera powered off, reconnect CH340 to the PC first, retain white ground
and purple RXD at camera A16/TX with blue TXD disconnected, then power the
camera. Read the resulting boot log before any further camera change.

## First Boot After The Change

The user confirmed card reinstallation and power-on. CH340 now enumerates
as COM11. The watcher received only3 bytes (not readable boot output).
At20:26 local time a Windows status-file reader prevented `Path.replace`,
and this unhandled sharing violation ended the first watcher.

The failure was reproduced with a locked-destination test, then fixed:
status/log writes retry transient sharing violations; persistent locks
do not terminate capture, and unsaved console text remains in memory for
later retry. All5 watcher tests pass. A new passive watcher is running,
PID41468, for2 hours in
`.run/maixcam-recovery-20261027/capture-retry-20261027-202754`.
It successfully opened COM11 and reports `listening`. A camera-only reboot
was requested to obtain an uninterrupted startup capture. No readable
Linux prompt or app error has been obtained yet.

## Offline Linux Filesystem Inspection

After the next complete power cycle still produced zero UART bytes, the
user put the TF card back into the reader as E. The commented console line
persisted. Normal Windows raw read access was denied with error5; the
prepared read-only inspector was then launched through Windows UAC.

The inspector opens the verified USB disk with GENERIC_READ only, validates
the MBR partition offset/size against Windows, and parses ext4 using
`dissect.extfs`, without mounting or replaying the journal. Its partition
and sector-bound tests passed. An8MiB synthetic ext4 fixture was parsed and
the source-image SHA256 stayed unchanged. Reports and source file copies
remain private under `.run/maixcam-recovery-20261027/offline-inspection-20261027-204938`.

Actual rootfs UUID: `22a051af-0675-4d62-bed7-98e0dde8dfc0`, block size4096,
31,256,997,888 bytes total,29,582,053,376 bytes free, clean state1. Seventy-three
configuration/log files were captured. `/maixapp/tmp` was empty; installed
S06 scripts erase it at every startup. The retained project logs show
successful GC4653/ISP initialization but no captured fatal application error.

Confirmed startup defects:

- `/etc/init.d/rcS` runs every regular `S??*` file. It includes executable
  `S06maixapp` and executable `S06maixapp.project-backup`; both repeat the
  launcher initialization and erase `/maixapp/tmp`. Multiple successful live
  daemon instances or a causal link to black screens are not yet proven.
- Main S06 has literal `#\1` instead of the MaixVision launch line. The
  backup retains `(/usr/bin/maixvision_server &)`, so the full current boot
  configuration does still attempt MaixVision startup through the backup.
- `scripts/maixcam_restore_startup.sh` prepares a guarded, reversible repair:
  verify exact preimage hashes, copy both originals outside init.d, restore
  the original S06, and archive the executable backup outside `S??*`.
  A host test verifies the repair, repeat execution and rejection of changed
  source scripts. This repair has not yet run on the actual card/device.

To obtain a direct USB terminal, the installed S08usbdev and inittab were
read and verified: presence of `/boot/usb.GS0` creates ACM, and ttyGS0 has a
login handler. The marker was added on E, while kernel/app/model/rootfs
content stayed untouched. Native-console capture now waits for VID359F /
PID2120 in the Windows Ports class and ignores CH340/ESP32 adapters.
It will capture the next camera USB boot for2 hours. The TF card was safely
ejected after readback. Next step is to reinstall it, connect camera Type-C
directly to the PC, and inspect the new native USB terminal before applying
the guarded startup repair and validating WiFi/camera applications.

## Complete Backup And Verified Working Image, 2026-10-28

The user confirmed that the earlier reader interruption followed physically
moving or reconnecting the reader. The stopped backup was resumed only after
matching samples from its existing prefix to the verified card and hashing the
entire saved prefix. This interruption is not evidence of failed TF media.

The Linux partition backup completed at10:14 local time on2026-10-28:

- Size:31,257,001,472 bytes.
- Source:disk2, partition2, offset16,777,728; source handle was read-only.
- UUID:`22a051af-0675-4d62-bed7-98e0dde8dfc0`.
- Image:`.run/maixcam-recovery-20261027/partition-backup-20261027-214947/rootfs-original.img`.
- SHA256:`03ec29009c5f7e1074fb91bdc95329502c9b01f5e4f247415efbf23f2b8ceddd`.

The original image is marked read-only. An independent filesystem copy named
`rootfs-working.img` was used for all Linux repair operations. The image helper
rejects a symbolic link, a hardlink alias of the original, multiple hardlinks
on the working image, or a size/UUID mismatch before any image write.

The working image restored the original S06 launcher/MaixVision script, moved
the executable backup outside `S??*`, and installed the reviewed startup trace
in rcS. Original scripts are archived within the image under
`/root/maixcam-recovery-20261027`. The trace records service names and exit
statuses without copying service stdout or credentials.

After journal recovery, a forced check found two residual orphan-list inodes,
35158 and39442. Read-only inspection of the original showed both had zero
links, zero size and no data blocks. An explicit forced repair was performed
on the working image only. A subsequent `e2fsck -f -n` completed all five
passes with exit0. The initial failed check and subsequent repair/check logs
are retained in `.run/maixcam-recovery-20261027/image-repair-20261028`.

A full before/after image comparison revalidated the original SHA256 and
generated48 sector-aligned ranges totaling3,604,480 bytes. Working SHA256:
`8d97e683100163eab34baad1c7d0b5d618c7255dcc50937c30b98ce07c6423ef`.
Plan and rollback bytes:
`.run/maixcam-recovery-20261027/card-patch-plan-20261028`.

Recursive content/link inventories of `/root/cattle-vision`, `/maixapp/apps`
and `/maixapp/share` matched exactly:811 files and symbolic links in total.
The regular diagnostic captures changed only the two intended startup files.
The payload comparison report contains counts and paths, not file contents.

The physical adapter validates the card layout/UUID, complete backup hash,
all range preimages and virtual repaired-image hash before writing. It denies
concurrent write handles, writes only inside the Linux partition, flushes and
reads back every changed range, and verifies both repaired startup files
within the rollback transaction. The normal offline-disk path retains the
disk offline on failure; successful restoration to online rechecks identity
and preserves an originally offline state. No claim about live WiFi/camera
behavior follows from image checks alone.

### Removable Reader Access

On this reader, Windows rejected `Set-Disk -IsOffline` with `Not Supported:
Removable media cannot be set to offline`. The rejection happened before any
raw write handle was opened. The card was still online and no patch was
applied by that attempt.

The explicit `-UseVolumeLock` path obtains partition1's actual volume GUID
from Windows. The adapter checks its single physical extent with
`IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS`, verifies the disk number and that the
extent ends before the Linux partition, then holds `FSCTL_LOCK_VOLUME` and
`FSCTL_DISMOUNT_VOLUME` for the transaction. The extent must also match an
MBR entry before partition verification. Windows exposes no volume/access
path for Linux partition2. The raw physical handle still denies concurrent
writers. Locks are released only after the raw handle is closed.

This mode does not mark removable media offline. A failed operation must be
assessed using its rollback result before the card is booted. Both access
modes retain the original backup and before/after patch blobs on the host.

The real card volume lock succeeded at10:48 local time on2026-10-28; the
adapter then began the complete source SHA256 scan with zero bytes written.
Evidence directory:
`.run/maixcam-recovery-20261027/card-volume-apply-20261028`.

### Card Patch Completed

At11:13 local time on2026-10-28, the full31,257,001,472-byte source scan
matched the original backup SHA256 and the virtual patched-image SHA256.
The adapter then wrote all48 planned ranges,3,604,480 bytes in total,
flushed and read back each range, and verified S06 and rcS by content hash.
The executable S06 backup was absent from the startup directory. The final
result is `phase=complete`, `status=applied`, `startup_files_verified=true`;
stderr is empty and the applying processes have exited.

The `boot_volume_locked` field in the result records the access protection
used during the transaction; the volume handle has been closed after the
completed process. It does not indicate a continuing lock.

Evidence is `apply-result.json` in the directory above. The original image,
working image, before/after blobs, original startup archive and filesystem
repair logs are retained. Host checks passed:30 patch tests,9 Windows-adapter
tests,20 wrapper tests and3 startup/identity tests. These checks establish
the offline repair outcome and do not substitute for the next live boot test.

## Live Recovery Confirmed And Model App Installed

The user subsequently confirmed that applications can open and WiFi connects.
Read-only SSH checks at `10.139.183.1` found exactly one launcher daemon and
one MaixVision service. The persistent startup trace contains completed,
successful entries for all services, including S06, USB gadget, WiFi and SSH.
This confirms the next boot completed; the prior uncertainty about the live
black screen is resolved by the user's report.

At the user's request, a separate launcher application named
`杨文昊-数牧增效` was installed at `/maixapp/apps/shumu_ywh`. It contains the
existing cow detector and the expanded2026-10-26 appearance classifier.
Both models were run through the actual launcher using the documented
`/tmp/run_app.txt` three-line handoff, and each completed three live-camera
frames. Both screenshot artifacts are nonblank and show readable controls.
The classifier remains research-only and does not establish a diagnosis.
The application returned to the launcher between mode checks.

Installation, model hashes, live results and screenshots are retained under
`.run/maixcam-app-install-20261028`. The installer only adds its own app entry
and backs up the prior registry/application. The earlier executable-backup
startup defect is not reintroduced.
