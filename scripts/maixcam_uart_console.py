from __future__ import annotations

import argparse
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import serial
from serial.tools import list_ports

TTL_VENDOR_IDS = {0x1A86, 0x10C4, 0x0403, 0x067B}


def select_ttl_port(ports) -> str:
    candidates = [port.device for port in ports if port.vid in TTL_VENDOR_IDS]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise RuntimeError('No independent USB-to-TTL adapter found. COM5 environment and COM9 wearable are not camera console ports.')
    raise RuntimeError('Multiple USB-to-TTL adapters found; select the camera adapter using --port: ' + ', '.join(candidates))


def usb_environment_path() -> str:
    candidates = [port for port in list_ports.comports() if port.vid == 0x303A and
                  (port.serial_number or '').replace(':', '').upper() == '2884859D78F0']
    if len(candidates) != 1:
        raise RuntimeError('Environment USB board not uniquely detected; pass --port explicitly')
    port = candidates[0]
    if port.device.upper() != 'COM5':
        return port.device
    result = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
        r"Get-PnpDevice -PresentOnly -Class Ports | Where-Object { $_.InstanceId -like 'USB\*' -and $_.FriendlyName -match '\(COM5\)$' } | Select-Object -ExpandProperty InstanceId"],
        capture_output=True, text=True, timeout=20, check=True)
    instance = result.stdout.strip()
    slash = chr(92)
    if not instance.startswith('USB' + slash) or '\n' in instance:
        raise RuntimeError('USB interface path unavailable; pass --port explicitly')
    return slash * 2 + '?' + slash + instance.replace(slash, '#') + '#{86e0d1e0-8089-11d0-9ce4-08003e301f73}'


def redact(text: str) -> str:
    return re.sub(r'(?im)((?:password|psk|wifi_pass|api_key)\s*[=:]\s*)[^\r\n]+', r'\1[redacted]', text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--port')
    parser.add_argument('--bridge', action='store_true', help='Use the environment ESP32 only after explicitly flashing the temporary UART bridge')
    parser.add_argument('--seconds', type=int, default=45)
    parser.add_argument('--login', action='store_true')
    parser.add_argument('--command', default='')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / '.run' / 'hardware-integration-20261025'
    root.mkdir(parents=True, exist_ok=True)
    output = root / ('maixcam-uart-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.log')
    port = serial.Serial(port=None, baudrate=115200, timeout=0.3, write_timeout=2)
    port.dtr = args.bridge
    port.rts = False
    ports = list(list_ports.comports())
    if args.port and not args.bridge and any(item.device.upper() == args.port.upper() and item.vid == 0x303A for item in ports):
        raise RuntimeError('Selected port is an ESP32 node, not an independent camera TTL adapter. Use --bridge only for the temporary bridge firmware.')
    port.port = args.port or (usb_environment_path() if args.bridge else select_ttl_port(ports))
    received = ''
    login_attempts = 0
    sent_command = False
    print('Opening MaixCAM console bridge, 115200 8N1; log:', output, flush=True)
    try:
        port.open()
        port.write(b'\r')
        until = time.monotonic() + args.seconds
        while time.monotonic() < until:
            data = port.read(max(1, port.in_waiting))
            if not data:
                continue
            chunk = data.decode('utf-8', errors='replace')
            received += chunk
            print(redact(chunk), end='', flush=True)
            tail = received[-300:]
            if args.login and login_attempts < 2 and re.search(r'login:\s*$', tail):
                port.write(b'root\r')
                login_attempts += 1
            elif args.login and re.search(r'Password:\s*$', tail):
                port.write(b'root\r')
            elif args.command and not sent_command and re.search(r'(?:root@[^\r\n]*|[\r\n])[^\r\n]*#\s*$', tail):
                port.write(args.command.encode('utf-8') + b'\r')
                sent_command = True
    finally:
        port.close()
        output.write_text(redact(received), 'utf-8')
    print('\nCaptured', len(received), 'characters; command sent:', sent_command, flush=True)


if __name__ == '__main__':
    main()
