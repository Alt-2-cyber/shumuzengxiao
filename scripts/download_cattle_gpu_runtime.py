from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

import requests

ROOT = Path(__file__).resolve().parents[1] / '.run' / 'cattle-ml-wheels'
PACKAGES = [('torch', 'torch-2.5.1%2Bcu121-cp311-cp311-win_amd64.whl'),
            ('torchvision', 'torchvision-0.20.1%2Bcu121-cp311-cp311-win_amd64.whl')]


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for package, filename in PACKAGES:
        url = 'https://download.pytorch.org/whl/cu121/' + filename
        index = requests.get('https://download.pytorch.org/whl/cu121/' + package + '/', timeout=30)
        index.raise_for_status()
        expected = next((digest for link, digest in re.findall(r'href="([^"]+)#sha256=([a-f0-9]{64})"', index.text)
                         if unquote(filename) in unquote(link)), None)
        if expected is None:
            raise RuntimeError('Official wheel SHA256 missing: ' + filename)
        target = ROOT / unquote(filename)
        if target.exists() and hashlib.file_digest(target.open('rb'), 'sha256').hexdigest() == expected:
            print('Verified cached', target.name, flush=True)
            continue
        partial = target.with_suffix('.part')
        digest = hashlib.sha256()
        received = partial.stat().st_size if partial.exists() else 0
        if received:
            with partial.open('rb') as previous:
                for chunk in iter(lambda: previous.read(4 * 1024 * 1024), b''):
                    digest.update(chunk)
            print('Resuming', target.name, received // (1024 * 1024), 'MiB', flush=True)
        next_report = received + 256 * 1024 * 1024
        headers = {'Range': f'bytes={received}-'} if received else {}
        with requests.get(url, headers=headers, stream=True, timeout=(20, 90)) as response:
            response.raise_for_status()
            if received and response.status_code != 206:
                received = 0
                digest = hashlib.sha256()
            with partial.open('ab' if received else 'wb') as stream:
                for chunk in response.iter_content(4 * 1024 * 1024):
                    stream.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    if received >= next_report:
                        print(target.name, received // (1024 * 1024), 'MiB', flush=True)
                        next_report += 256 * 1024 * 1024
        if digest.hexdigest() != expected:
            raise RuntimeError('Wheel hash mismatch: ' + filename)
        partial.replace(target)
        print('SHA256 verified', target.name, received, flush=True)


if __name__ == '__main__':
    main()
