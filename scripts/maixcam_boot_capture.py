"""Passively capture a camera console, waiting for a real USB TTL adapter."""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import serial
from serial.tools import list_ports

from maixcam_uart_console import redact, select_ttl_port


def select_maix_usb_port(ports):
    candidates = [port.device for port in ports if port.vid == 0x359F and port.pid == 0x2120]
    if len(candidates) != 1:
        raise RuntimeError('Expected exactly one native MaixCAM USB console')
    return candidates[0]


def replace_text(path, content):
    temporary = path.with_suffix('.new')
    for attempt in range(6):
        try:
            temporary.write_text(content, encoding='utf-8')
            temporary.replace(path)
            return True
        except PermissionError:
            if attempt == 5:
                return False
            time.sleep(0.05)


def save_json(path, value):
    return replace_text(path, json.dumps(value, indent=2))


def watch(output, seconds=3600, max_bytes=4_194_304, clock=time.monotonic,
          sleep=time.sleep, enumerate_ports=list_ports.comports, serial_factory=serial.Serial,
          port_selector=select_ttl_port):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / 'capture-status.json'
    log_path = output / 'boot-console.log'
    stop_path = output / 'stop-capture'
    if log_path.exists():
        raise FileExistsError('Use a new capture output directory to preserve earlier evidence')
    log_path.write_text('', encoding='utf-8')
    state = {'phase': 'waiting_adapter', 'rx_bytes': 0, 'connections': 0,
             'port': None, 'baud': 115200, 'receive_only': True, 'log': str(log_path.resolve())}
    started = clock()
    port = None
    received = bytearray()
    saved_bytes = 0
    try:
        while clock() - started < seconds and not stop_path.exists() and len(received) < max_bytes:
            if port is None:
                try:
                    name = port_selector(list(enumerate_ports()))
                    port = serial_factory(port=None, baudrate=115200, bytesize=8, parity='N', stopbits=1,
                                          timeout=0.25, write_timeout=1, xonxoff=False,
                                          rtscts=False, dsrdtr=False)
                    port.dtr = False
                    port.rts = False
                    port.port = name
                    port.open()
                    state.update(phase='listening', port=name, connections=state['connections'] + 1)
                    state.pop('last_error', None)
                except (RuntimeError, OSError, serial.SerialException) as failure:
                    if port is not None:
                        port.close()
                    port = None
                    state.update(phase='waiting_adapter', last_error=type(failure).__name__)
                    state['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
                    save_json(status_path, state)
                    sleep(0.5)
                    continue
            try:
                data = port.read(min(max_bytes - len(received), max(1, port.in_waiting)))
                if data:
                    received.extend(data)
                    state.update(rx_bytes=len(received), phase='receiving',
                                 last_data_at_utc=datetime.now(timezone.utc).isoformat())
            except (OSError, serial.SerialException) as failure:
                port.close()
                port = None
                state.update(phase='waiting_adapter', last_error=type(failure).__name__)
            if len(received) != saved_bytes:
                # Retry on subsequent reads if a Windows reader temporarily holds the file.
                text = redact(received.decode('utf-8', errors='replace'))
                if replace_text(log_path, text):
                    saved_bytes = len(received)
            state['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
            save_json(status_path, state)
    finally:
        if port is not None:
            port.close()
        if len(received) != saved_bytes:
            replace_text(log_path, redact(received.decode('utf-8', errors='replace')))
        state.update(phase='stopped', stopped_at_utc=datetime.now(timezone.utc).isoformat())
        save_json(status_path, state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=3600)
    parser.add_argument('--maix-usb', action='store_true', help='Wait for the native MaixCAM USB ACM console')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 14_400:
        parser.error('--seconds must be between 1 and 14400')
    selector = select_maix_usb_port if args.maix_usb else select_ttl_port
    print(json.dumps(watch(args.output, args.seconds, port_selector=selector), indent=2), flush=True)


if __name__ == '__main__':
    main()
