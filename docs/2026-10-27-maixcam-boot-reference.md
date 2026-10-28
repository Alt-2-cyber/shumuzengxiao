# MaixCAM boot console reference, 2026-10-27

Read-only investigation. No serial port was opened, no card or camera file was
changed, and no existing capture or device process was started or stopped.
Only this reference document was written. No private network files were read.

## Result

For the backed-up `maixcam-2026-01-24-maixpy-v4.12.5` boot files, the compiled
U-Boot default is **`consoledev=ttyS0`**, without `/dev/`. Commenting the existing
assignment preserves that default under the official environment-import
implementation. The official UART instructions agree with this operation.
There is no evidence that adding an explicit assignment is necessary.

The Linux device path is `/dev/ttyS0`, but the matching U-Boot assignment would
be `consoledev=ttyS0`, not `consoledev=/dev/ttyS0`. These are different uses of
the name: U-Boot inserts the value directly into the kernel `console=` argument.

This establishes the static configuration and intended fallback. It does not
establish the live `/proc/cmdline`, successful import on the last boot, working
camera-side electrical contact, or availability of a login process.

## Evidence from this card's actual boot binaries

Input directory:
`.run/maixcam-recovery-20261027/boot-before-console-20261027-201634`.

| File | SHA256 |
| --- | --- |
| `fip.bin` (440832 bytes) | `d85e68836f57a9fcb1bbfba3c1ccf93d1b062ac168305d7f0cc83a72a796c6b9` |
| `boot.sd` | `1acecfd0e005b9d4fd52a0d6fa9451b8c5925f9b78b929b59da17238a49e0880` |

The FIP contains a second-stage loader at byte 164352. Its magic at byte
164356 is `B3MA`, which the official FIP tool identifies as LZMA. The loader
header is 32 bytes, its stored size is 276480 bytes, and the LZMA stream begins
at byte 164384. Standard-library `lzma.LZMADecompressor(FORMAT_ALONE)` completed
with `eof=True`, yielding 595086 bytes and 207 unused padding bytes. Extraction
was entirely in memory; no decompressed binary was written.

Decompressed payload SHA256:
`856e50c3cd1f9a6c67cd4441695e44ca48b9d4c821ee4eec0b94a74319f9e8c9`.

Actual compiled version string:

```text
U-Boot 2021.10 (Jan 22 2026 - 14:08:22 +0800) soph
```

The following strings are contiguous members of the NUL-separated default
environment, starting at decompressed offset 363384 and ending at 364722.
They are not guesses based on the current upstream build configuration.
Offsets below are decimal offsets in the decompressed payload.

| Offset | Exact string |
| --- | --- |
| 363384 | `bootcmd=run loadenvcmd ; run showlogo;run sdboot || run sdbootauto` |
| 363630 | `bootdelay=0` |
| 363642 | `baudrate=115200` |
| 363822 | `consoledev=ttyS0` |
| 363839 | `baudrate=115200` |
| 363919 | `root=root=/dev/mmcblk0p2 rootwait rw` |
| 363956 | `sddev=0` |
| 364543 | `othbootargs=earlycon=sbi riscv.fwsz=0x80000  release  loglevel=0` |
| 364608 | `loadenvcmd=mmc info;load mmc 0:1 ${uImage_addr} uEnv.txt; if test $? -eq 0; then env import ${uImage_addr} - ; fi;` |

The exact SD boot command at offset 363964 is:

```text
sdboot=setenv bootargs ${reserved_mem} ${root} ${mtdparts} console=$consoledev,$baudrate $othbootargs;echo Boot from SD dev ${sddev} ...;mmc dev ${sddev} && fatload mmc ${sddev} ${uImage_addr} boot.sd;if test $? -eq 0; then bootm ${uImage_addr}#config-sg2002_licheervnano_sd;fi;
```

`sdbootauto` likewise uses `console=$consoledev,$baudrate`. Consequently, the
compiled defaults yield `console=ttyS0,115200`. The `loglevel=0` argument
suppresses ordinary kernel printk output; it does not itself disable a getty
or explain all silence from Boot ROM, FSBL, U-Boot and userspace.

The actual FIT image in `boot.sd` selects
`config-sg2002_licheervnano_sd`, whose FDT is
`fdt-sg2002_licheervnano_sd`. The embedded DTB is 22206 bytes and contains:

```text
/aliases: serial0 = /serial@04140000
/aliases: serial1 = /serial@04150000
/chosen: stdout-path = serial0
/serial@04140000: compatible = snps,dw-apb-uart; status = okay
/serial@04150000: compatible = snps,dw-apb-uart; status = okay
```

The original backup `uEnv.txt` contains `consoledev=/dev/tty3` with CRLF.
The recovery status documents that it was changed to `# consoledev=/dev/tty3`.
The live card was not inspected in this investigation.

## Official references and what they establish

The source links below are pinned to official Sipeed repository commit
`d4003f15b35d43ad4842f427050ab2bba0114fa5` (2026-01-14). They describe public
source behavior; a source-to-binary reproducible-build match for this card
has not been established.

- [Official MaixPy UART manual](https://wiki.sipeed.com/maixpy/doc/zh/peripheral/uart.html):
  MaixCAM/MaixCAM-Pro UART0 is A16/TX and A17/RX, using `/dev/ttyS0`.
  UART1 uses A19/TX and A18/RX, using `/dev/ttyS1`. Its terminal instructions
  explicitly say to comment or remove the `consoledev` line in `/boot/uEnv.txt`
  and reboot. This is a current how-to, not a version-pinned image manifest.
- [FIP loader format and compression](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/fsbl/plat/cv181x/fiptool.py#L35):
  `B3MA` denotes LZMA; lines 220-230 define the 32-byte loader header;
  lines 568-593 describe compression of the body after that header.
- [U-Boot environment import](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/u-boot-2021.10/cmd/nvedit.c#L1087):
  default import format is newline-separated text. `del` defaults to zero;
  line 1192 passes `H_NOCLEAR` unless `-d` is supplied. The card's compiled
  import command does not supply `-d`.
- [U-Boot comment handling](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/u-boot-2021.10/lib/hashtable.c#L770):
  existing variables are retained with `H_NOCLEAR`; `#` comment lines are
  ignored (lines 897-901). CRLF in the commented line does not expose its
  assignment, because the entire line is skipped up to LF.
- [Kernel console argument parsing](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/linux_5.10/kernel/printk/printk.c#L2186):
  `console_setup()` copies the console name and separates its numeric index.
  This implementation does not strip a `/dev/` prefix. Use the actual compiled
  default as the reference spelling, rather than inventing an absolute path
  for `consoledev`.

The similarly named `include/configs/sipeed-maix.h` in U-Boot is for K210
(`k210_bootcmd`, 8 MiB SDRAM), and is not a MaixCAM SG2002 console reference.

One import limitation remains: the compiled command uses `-` for automatic
input size, not `${filesize}`, and does not pass `-r` for CRLF normalization.
The source scans for LF followed by NUL. A commented CRLF line remains a
comment, but the full runtime import and buffer termination cannot be proved
from the file alone. No import failure was observed or established.

## USB maintenance and startup references

Actual backed-up files: `usb.dev`, `usb.rndis` and `usb.ncm` all exist and are
zero-length. `usb.product` is `maixcam`. The backup does not contain `usb.host`,
`usb.GS0` or `usb.adbd`. These observations cover the boot partition only.

- [Official S08usbdev](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/buildroot/board/cvitek/SG200X/overlay/etc/init.d/S08usbdev#L7):
  `usb.host` takes precedence; otherwise `usb.dev` enables gadget setup.
  Default VID/PID are `0x359F`/`0x2120`, matching the reported device.
  `usb.rndis` creates `rndis.usb0` (line 119), and `usb.ncm` creates `ncm.usb0`
  (line 129). `usb.GS0` gates ACM serial (line 86); `usb.adbd` gates ADB
  (line 172). File existence, not nonempty contents, controls these branches.
- [Official S30gadget_nic](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/buildroot/board/cvitek/SG200X/overlay/etc/init.d/S30gadget_nic#L29):
  a separate stage brings RNDIS `usb0` up (line 45), then NCM `usb1` up when
  both functions are enabled (line 91). It configures addresses and DHCP.
  Thus successful enumeration does not establish that this later stage ran.
- [Official inittab](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/buildroot/board/cvitek/SG200X/overlay/etc/inittab#L18):
  runs `/etc/init.d/rcS`, then respawns getty on `console` and `ttyGS0`, using
  `/etc/console_handler.sh` and `/etc/ttyGS0_handler.sh`. The published handlers
  call `login` when the respective device exists.
- [Official S99local](https://github.com/sipeed/LicheeRV-Nano-Build/blob/d4003f15b35d43ad4842f427050ab2bba0114fa5/buildroot/board/cvitek/SG200X/overlay/etc/init.d/S99local#L3):
  runs `/etc/rc.local` unless `/boot/rclocal.disable` exists. This is a concrete
  startup hook to inspect, not evidence that this card's custom startup is bad.

These startup scripts have not been read from this card's ext4 partition.
They must not be presented as verified MaixPy 4.12.5 installed contents.
The backup flags and reported enumeration do not support claiming USB device,
RNDIS or NCM mode was simply disabled. Missing ACM/ADB flags are consistent
with no such maintenance interface under the published script, but do not
prove the live script is identical.

## Remaining checks for the independent offline rootfs investigation

Compare actual `/etc/inittab`, `/etc/init.d/rcS`, `S08usbdev`, `S30gadget_nic`,
console handlers, `/etc/rc.local`, and any Maix startup overrides with the
references above, including executable modes and symlink targets. Check the
already identified `/maixapp/tmp/last_run.log` with credential redaction.
Inspect kernel/userspace logging and any UART0 pin remapping before drawing
electrical conclusions from zero received bytes.

The black WiFi/camera apps and media-disconnected USB links remain unexplained
by the boot-partition evidence. This investigation does not justify a reflash,
another console edit, or enabling an extra maintenance service.
