"""Manage this project process without stopping MaixCAM system applications."""

import argparse
import json
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(ROOT, 'main.py')
PID_FILE = os.path.join(ROOT, 'node.pid')


def owns_process(pid):
    try:
        with open('/proc/%s/cmdline' % int(pid), 'rb') as stream:
            arguments = stream.read().split(b'\0')
        return MAIN.encode('utf-8') in arguments
    except (OSError, ValueError):
        return False


def running_pid():
    try:
        with open(PID_FILE, 'r') as stream:
            pid = int(stream.read().strip())
        if owns_process(pid):
            return pid
    except (OSError, ValueError):
        pass
    for name in os.listdir('/proc'):
        if name.isdigit() and owns_process(int(name)):
            return int(name)
    return None


def prepare_config(backend_url=None):
    config_path = os.path.join(ROOT, 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as stream:
            config = json.load(stream)
        with open(config_path + '.backup-' + str(int(time.time())), 'w') as stream:
            json.dump(config, stream)
    else:
        with open(os.path.join(ROOT, 'config.default.json'), 'r') as stream:
            config = json.load(stream)
    config['model_path'] = os.path.join(ROOT, 'models', 'cattle_yolov8.mud')
    if backend_url:
        config['backend_url'] = backend_url
    with open(config_path + '.new', 'w') as stream:
        json.dump(config, stream, indent=2)
    os.replace(config_path + '.new', config_path)
    return {'status': 'configured', 'modelPath': config['model_path']}


def stop():
    pid = running_pid()
    if pid is None:
        return {'status': 'not_running'}
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        if not owns_process(pid):
            return {'status': 'stopped', 'pid': pid}
        time.sleep(0.1)
    raise RuntimeError('Project process did not stop; inspect its log before retrying')


def start():
    pid = running_pid()
    if pid is not None:
        return {'status': 'already_running', 'pid': pid}
    log_dir = os.path.join(ROOT, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, 'vision.log'), 'ab') as log:
        process = subprocess.Popen([sys.executable, '-u', MAIN], cwd=ROOT, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    with open(PID_FILE, 'w') as stream:
        stream.write(str(process.pid))
    time.sleep(2)
    if process.poll() is not None:
        raise RuntimeError('Project exited; inspect logs/vision.log')
    return {'status': 'started_waiting_for_runtime_validation', 'pid': process.pid}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['configure', 'start', 'stop', 'status'])
    parser.add_argument('--backend-url')
    args = parser.parse_args()
    if args.action == 'configure':
        result = prepare_config(args.backend_url)
    elif args.action == 'start':
        result = start()
    elif args.action == 'stop':
        result = stop()
    else:
        result = {'status': 'running' if running_pid() else 'not_running', 'pid': running_pid()}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
