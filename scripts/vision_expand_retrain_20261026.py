#!/usr/bin/env python3
"""Expand public cattle appearance research data without borrowing frozen tests."""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import numpy as np
import requests
from PIL import Image, ImageOps

import train_vision_yolo_research_20261026 as prior

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'vision-training-data/expanded-yolo-20261026'
EXTERNAL = ROOT / prior.SOURCE_RELATIVE
EXTERNAL = EXTERNAL.parent
PRIOR = ROOT / prior.OUTPUT_RELATIVE
LABELS = prior.LABELS
SOURCES = [
    ('shivamagarwal29/cow-lumpy-disease-dataset', 'Kaggle_CowLumpy_Shivam_expanded-20261026'),
    ('drtawfikrrahman/cowhealth-6k-cow-disease-detection', 'Kaggle_CowHealth6K_expanded-20261026'),
    ('magantirajasri/cattle-diseases-dataset', 'Kaggle_CattleDiseases_Maganti_expanded-20261026'),
    ('tanushtambea/calf-lumpy-skin-disease', 'Kaggle_CalfLumpy_expanded-20261026'),
    ('wasimfaraz/fmd-cattle-dataset', 'Kaggle_FMD_Additional_expanded-20261026'),
]
HOLDOUT_SOURCE = 'tanushtambea/calf-lumpy-skin-disease'
write_json = prior.write_json
read_json = prior.read_json
sha256 = prior.sha256
utc_now = prior.utc_now


def http_session():
    session = requests.Session()
    session.proxies.update({k: v for k, v in urllib.request.getproxies().items()
                            if k in {'http', 'https'}})
    session.headers['User-Agent'] = 'cattle-appearance-research/20261026 (public-data-only)'
    return session


def safe_extract(archive, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            name = entry.filename.replace('\\', '/')
            parts = PurePosixPath(name).parts
            target = (destination / name).resolve()
            if ('..' in parts or PurePosixPath(name).is_absolute() or ':' in name
                    or not target.is_relative_to(destination)
                    or (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError(f'Unsafe archive member: {name}')
        destination.mkdir(parents=True, exist_ok=True)
        bundle.extractall(destination)


def acquire(only_ref=None):
    session = http_session()
    search_dir = EXTERNAL / 'PublicSearch_expanded-20261026'
    search_dir.mkdir(parents=True, exist_ok=True)
    queries = [
        ('kaggle-cattle', 'https://www.kaggle.com/api/v1/datasets/list',
         {'search': 'cattle disease', 'page': 1, 'pageSize': 20}),
        ('kaggle-lumpy', 'https://www.kaggle.com/api/v1/datasets/list',
         {'search': 'lumpy skin', 'page': 1, 'pageSize': 20}),
        ('kaggle-fmd', 'https://www.kaggle.com/api/v1/datasets/list',
         {'search': 'foot and mouth', 'page': 1, 'pageSize': 20}),
        ('hf-cattle', 'https://huggingface.co/api/datasets', {'search': 'cattle', 'limit': 15}),
        ('hf-lumpy', 'https://huggingface.co/api/datasets', {'search': 'lumpy', 'limit': 15}),
        ('github', 'https://api.github.com/search/repositories',
         {'q': 'cattle disease dataset', 'per_page': 8}),
        ('zenodo', 'https://zenodo.org/api/records',
         {'q': '"lumpy skin" AND images', 'size': 5}),
    ]
    for key, url, params in queries:
        receipt_path = search_dir / f'{key}.json'
        if receipt_path.exists():
            continue
        try:
            response = session.get(url, params=params, timeout=(15, 35))
            receipt = {'url': url, 'params': params, 'utc': utc_now(),
                       'status': response.status_code}
            if response.ok:
                receipt['response'] = response.json()
            else:
                receipt['reason'] = response.reason
        except (requests.RequestException, ValueError) as error:
            receipt = {'url': url, 'params': params, 'utc': utc_now(),
                       'failure_type': type(error).__name__,
                       'reason': 'Public endpoint unavailable via configured system proxy; no bypass attempted'}
        write_json(receipt_path, receipt)
        print(f'Public search {key}: {receipt.get("status", receipt.get("failure_type"))}', flush=True)

    total_budget = 800 * 1024 * 1024
    # Fetch small sources first so a slow large archive cannot block all progress.
    for ref, folder in sorted(SOURCES, key=lambda s: (s[0].startswith('drtawfik'), s[0].startswith('maganti'))):
        if only_ref and only_ref != ref:
            continue
        directory = EXTERNAL / folder
        directory.mkdir(parents=True, exist_ok=True)
        if (directory / 'provenance.json').exists():
            receipt = read_json(directory / 'provenance.json')
            assert sha256(directory / 'archive.zip') == receipt['archive_sha256']
            continue
        metadata_url = 'https://www.kaggle.com/api/v1/datasets/view/' + ref
        metadata_response = session.get(metadata_url, timeout=(20, 50))
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        write_json(directory / 'kaggle_metadata.json', metadata)
        if metadata.get('isPrivate'):
            raise ValueError('Private dataset is outside authorized public acquisition')
        size = int(metadata.get('totalBytes', 0))
        if size > total_budget:
            raise ValueError('Bounded acquisition size budget exceeded')
        total_budget -= size
        version = metadata.get('currentVersionNumber', 1)
        url = f'https://www.kaggle.com/api/v1/datasets/download/{ref}'
        archive = directory / 'archive.zip'
        partial = directory / 'archive.zip.part'
        print(f'Downloading public {ref} version={version}, reported bytes={size}', flush=True)
        response = session.get(url, params={'datasetVersionNumber': version},
                               allow_redirects=False, timeout=(15, 30))
        response.raise_for_status()
        location = response.headers.get('Location')
        if response.status_code not in {301, 302, 303, 307, 308} or not location:
            write_json(directory / 'acquisition_failure.json',
                       dict(utc=utc_now(), reason='Expected public download redirect', status=response.status_code))
            continue
        environment = os.environ.copy()
        environment.update({key.upper() + '_PROXY': value for key, value in urllib.request.getproxies().items()
                            if key in {'http', 'https'}})
        command = ['curl.exe', '--silent', '--show-error', '--fail', '--location',
                   '--connect-timeout', '15', '--max-time', '360', '--continue-at', '-',
                   '--speed-limit', '4096', '--speed-time', '30',
                   '--output', str(partial), location]
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        last_progress = time.monotonic()
        while process.poll() is None:
            time.sleep(0.2)
            if time.monotonic() - last_progress >= 20:
                count = partial.stat().st_size if partial.exists() else 0
                print(f'{ref}: {count / (1024 * 1024):.1f} MiB transferred', flush=True)
                last_progress = time.monotonic()
        _, errors = process.communicate()
        if process.returncode != 0 or not zipfile.is_zipfile(partial):
            write_json(directory / 'acquisition_failure.json',
                       dict(utc=utc_now(), reason='Bounded public transfer failed',
                            curl_exit_code=process.returncode, stderr=errors.decode(errors='replace')[:500]))
            print(f'Bounded transfer failed for {ref}: curl exit={process.returncode}', flush=True)
            continue
        downloaded = partial.stat().st_size
        partial.replace(archive)
        final_url = urlsplit(location)
        receipt = {
                'source_dataset': ref, 'source_url': 'https://www.kaggle.com/datasets/' + ref,
                'api_url': url, 'metadata_api_url': metadata_url, 'version': version,
                'retrieved_utc': utc_now(), 'http_status': 200, 'api_redirect_status': response.status_code,
                'final_host': final_url.netloc, 'final_path': final_url.path,
                'etag': response.headers.get('ETag'), 'archive_bytes': downloaded,
                'archive_sha256': sha256(archive),
                'license_reported': metadata.get('licenseName'),
                'license_scope': 'Uploader/platform statement, not independent per-image rights verification',
                'animal_id': None, 'farm_id': None, 'capture_date': None,
                'veterinarian': None, 'laboratory_reference': None,
                'clinical_reference': None, 'clinically_verified': False,
                'label_policy': 'Only original explicit disease/healthy directory or annotation labels; no inferred clinical labels',
                'access': 'Unauthenticated official HTTP API; system proxy; no credentials or restriction bypass',
        }
        safe_extract(archive, directory / 'raw')
        # Some public datasets package their original class directories in nested ZIPs.
        for nested in sorted((directory / 'raw').rglob('*.zip')):
            safe_extract(nested, nested.with_suffix(''))
        write_json(directory / 'provenance.json', receipt)
        (directory / 'DATASET_CARD.md').write_text(
            '# Public cattle appearance research source\n\n'
            + f'- Source: {receipt["source_url"]}\n- Version: {version}\n'
            + f'- Platform license: {receipt["license_reported"]}\n'
            + f'- ZIP SHA-256: `{receipt["archive_sha256"]}`\n'
            + '- Clinical identity/reference fields: missing; uploader claims are not verification.\n'
            + '- Original labels and all cross-source duplicate components are audited before use.\n'
            + '- Disease-directory membership is a public appearance label, not a diagnosis.\n',
            encoding='utf-8')
        with zipfile.ZipFile(archive) as bundle:
            tops = Counter('/'.join(PurePosixPath(n).parts[:-1]) for n in bundle.namelist()
                           if Path(n).suffix.lower() in prior.IMAGE_EXTENSIONS)
            print(json.dumps({'downloaded': ref, 'image_directories': tops}, indent=2), flush=True)


def build_groups(records):
    valid = [r for r in records if r['decode_status'] == 'ok']
    parent = list(range(len(valid)))
    edges = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def join(a, b, reason, **extra):
        left, right = find(a), find(b)
        if left != right:
            parent[max(left, right)] = min(left, right)
        edges.append(dict(left_id=valid[a]['id'], right_id=valid[b]['id'], reason=reason, **extra))

    for field in ['prior_group_id', 'file_sha256', 'pixel_sha256', 'source_name_key']:
        first = {}
        for index, row in enumerate(valid):
            key = row.get(field)
            if not key:
                continue
            if key in first:
                join(first[key], index, field)
            else:
                first[key] = index
    values = {key: np.asarray([int(r[key], 16) for r in valid], dtype=np.uint64)
              for key in ['phash', 'dhash', 'phash_mirror', 'dhash_mirror']}
    aspects = np.asarray([r['width'] / r['height'] for r in valid])
    counts = np.asarray([int(i).bit_count() for i in range(256)], dtype=np.uint8)

    def distance(x, y):
        return counts[np.bitwise_xor(x, y).view(np.uint8).reshape(-1, 8)].sum(axis=1)

    for i in range(len(valid)):
        remaining = np.arange(i + 1, len(valid))
        if not len(remaining):
            continue
        mask = np.maximum(aspects[i] / aspects[remaining], aspects[remaining] / aspects[i]) <= 1.10
        targets = remaining[mask]
        for orientation, suffix in [('original', ''), ('horizontal_mirror', '_mirror')]:
            pd = distance(values['phash'][i], values['phash' + suffix][targets])
            selected = targets[pd <= 6]
            dd = distance(values['dhash'][i], values['dhash' + suffix][selected])
            for other, delta in zip(selected[dd <= 10], dd[dd <= 10]):
                j = int(other)
                if valid[i]['pixel_sha256'] != valid[j]['pixel_sha256']:
                    join(i, j, 'perceptual_near_duplicate', orientation=orientation,
                         phash_distance=(int(values['phash'][i]) ^ int(values['phash' + suffix][j])).bit_count(),
                         dhash_distance=int(delta))
        if (i + 1) % 1000 == 0:
            print(f'Global duplicate scan {i + 1}/{len(valid)}', flush=True)
    members = defaultdict(list)
    for i, row in enumerate(valid):
        members[find(i)].append(row)
    groups = []
    for component in members.values():
        identifiers = sorted(r['id'] for r in component)
        gid = 'xg-' + hashlib.sha256('\n'.join(identifiers).encode()).hexdigest()[:20]
        for row in component:
            row['global_group_id'] = gid
        groups.append(dict(group_id=gid, members=identifiers,
                           labels=sorted({r['source_label'] for r in component if r['source_label']}),
                           sources=sorted({r['source_dataset'] for r in component})))
    return sorted(groups, key=lambda g: g['group_id']), edges


def assign_roles(records, groups, holdout_source):
    by_id = {r['id']: r for r in records}
    for row in records:
        row['role'] = 'invalid' if row['decode_status'] != 'ok' else 'duplicate_excluded'
    for group in groups:
        members = [by_id[i] for i in group['members']]
        prior_test = [r for r in members if r.get('prior_split') == 'test']
        prior_val = [r for r in members if r.get('prior_split') == 'val']
        prior_quarantine = any(r.get('prior_split') == 'quarantine' for r in members)
        holdout = [r for r in members if r['source_dataset'] == holdout_source]
        if prior_test:
            group['partition'] = 'frozen_test_protected'
            for row in members:
                row['role'] = ('frozen_test' if row.get('prior_split') == 'test'
                               and row.get('prior_role') == 'representative'
                               else 'excluded_frozen_test_component')
            continue
        if any(r.get('label_origin') == 'catalog_only_filename_identifies_non_bovine_subject'
               or re.search(r'\b(?:goat|sheep|pig|swine|human|buffalo)\b', Path(r['source_path']).stem, re.IGNORECASE)
               for r in members):
            group['partition'] = 'excluded_non_bovine_subject'
            for row in members:
                row['role'] = group['partition']
            continue
        if len(group['labels']) > 1 or prior_quarantine:
            group['partition'] = 'quarantine_cross_label'
            for row in members:
                row['role'] = 'quarantine_cross_label'
            continue
        if not group['labels'] or group['labels'][0] not in LABELS:
            group['partition'] = 'catalog_only'
            for row in members:
                row['role'] = 'catalog_only'
            continue
        eligible = [r for r in members if r['source_label'] == group['labels'][0]]
        if prior_val:
            group['partition'] = 'val'
            for row in prior_val:
                if row.get('prior_role') == 'representative':
                    row['role'] = 'val'
            continue
        if holdout:
            group['partition'] = 'source_holdout'
            # Only genuinely new groups can support a novel-source holdout claim.
            prior_members = [r for r in members if r.get('prior_split') is not None]
            if prior_members:
                group['partition'] = 'excluded_holdout_overlap_with_prior'
                for row in members:
                    row['role'] = group['partition']
                continue
            eligible = [r for r in eligible if r['source_dataset'] == holdout_source]
            if not eligible:
                group['partition'] = 'excluded_holdout_unmapped_label'
                for row in members:
                    row['role'] = group['partition']
                continue
        else:
            group['partition'] = 'train'
            old_reps = [r for r in eligible if r.get('prior_split') == 'train'
                        and r.get('prior_role') == 'representative']
            if old_reps:
                eligible = old_reps
        representative = min(eligible, key=lambda r: (-r['width'] * r['height'], r['file_sha256'], r['id']))
        representative['role'] = group['partition']
        group['representative_id'] = representative['id']


def source_name_key(name, dataset):
    stem = Path(name).name.lower()
    stem = stem.split('.rf.', 1)[0] if '.rf.' in stem else Path(stem).stem
    stem = re.sub(r'(?:(?:_|\.)(?:jpe?g|png|webp|bmp))+$', '', stem)
    # Descriptive web/Roboflow identifiers are global; numeric stems are ambiguous.
    generic = re.fullmatch(r'(?:imgs?|images?|pics?|photos?|cows?|healthy|normal|lumpy|normalskin|lumpyskin)\d+',
                           re.sub(r'[\s_\-]', '', stem))
    if re.search(r'[a-z]{3}', stem) and len(stem) >= 8 and not generic:
        return 'global:' + stem
    return dataset + ':' + stem


def normalize_label(value):
    key = re.sub(r'[^a-z0-9]', '', str(value).lower())
    key = re.sub(r'(?<=[a-z])[12]$', '', key)
    return {
        'healthy': 'healthy', 'healthycow': 'healthy', 'healthycows': 'healthy',
        'normal': 'healthy', 'normalskin': 'healthy', 'normalcow': 'healthy',
        'normalcows': 'healthy', 'lumpy': 'lumpy', 'lumpycow': 'lumpy',
        'lumpycows': 'lumpy', 'lumpyskin': 'lumpy', 'lumpyskindisease': 'lumpy',
        'lumpydisease': 'lumpy', 'lsd': 'lumpy', 'fmd': 'foot-and-mouth',
        'footandmouth': 'foot-and-mouth', 'footandmouthdisease': 'foot-and-mouth',
        'footandmougth': 'foot-and-mouth',
        'mastitis': 'mastitis',
    }.get(key)


def public_directory_label(path):
    label = Path(path).parent.name
    return label, normalize_label(label)


def annotation_index(raw):
    """Read explicit public labels; detection-only cattle names are left unmapped."""
    import yaml
    annotations = {}
    for coco in sorted(raw.rglob('*annotations*.json')):
        document = read_json(coco)
        if not all(key in document for key in ['images', 'categories', 'annotations']):
            continue
        categories = {row['id']: row['name'] for row in document['categories']}
        labels = defaultdict(set)
        for row in document['annotations']:
            labels[row['image_id']].add(categories[row['category_id']])
        for row in document['images']:
            annotations[str((coco.parent / row['file_name']).resolve())] = {
                'original_annotation_labels': sorted(labels[row['id']]),
                'label_origin': str(coco), 'format': 'COCO',
            }
    yaml_files = sorted([*raw.rglob('*.yaml'), *raw.rglob('*.yml')])
    for data_file in yaml_files:
        document = yaml.safe_load(data_file.read_text(encoding='utf-8-sig'))
        if not isinstance(document, dict) or 'names' not in document:
            continue
        names = document['names']
        if isinstance(names, list):
            names = dict(enumerate(names))
        else:
            names = {int(key): value for key, value in names.items()}
        for labels_dir in data_file.parent.rglob('labels'):
            images_dir = labels_dir.parent / 'images'
            if not images_dir.exists():
                continue
            for path in images_dir.iterdir():
                if path.suffix.lower() not in prior.IMAGE_EXTENSIONS:
                    continue
                annotation_file = labels_dir / (path.stem + '.txt')
                if not annotation_file.exists():
                    continue
                classes = {int(line.split()[0]) for line in annotation_file.read_text().splitlines() if line.strip()}
                annotations[str(path.resolve())] = {
                    'original_annotation_labels': sorted(str(names[k]) for k in classes),
                    'label_origin': str(annotation_file), 'format': 'YOLO',
                    'class_names_file': str(data_file),
                }
    return annotations


def inventory():
    if (OUTPUT / 'inventory.jsonl').exists():
        raise FileExistsError('Inventory already frozen')
    old_records = prior.load_records(PRIOR)
    for row in old_records:
        row['prior_group_id'] = row['group_id']
        row['prior_split'] = row['split']
        row['prior_role'] = row['role']
        row['source_name_key'] = source_name_key(Path(row['source_path']).name,
                                                row['source_dataset'] + ':' + row['source_label'])
        row['acquisition'] = 'prior_original_dataset'
        row['license_reported'] = 'Database: Open Database, Contents: Database Contents'
        row['original_source_label'] = row['source_label']
    records = old_records[:]
    descriptors = [
        ('warcoder/lumpy-skin-images-dataset', 'Kaggle_LumpySkin_2023', 'existing_unused_source'),
        ('wasimfaraz/cattle-foot-and-mouth-disease-fmd', 'Kaggle_FMD_2025', 'existing_detection_only_source'),
        *[(ref, folder, 'new_public_download') for ref, folder in SOURCES],
    ]
    source_summary = []
    for ref, folder, acquisition in descriptors:
        directory = EXTERNAL / folder
        raw = directory / 'raw'
        if not raw.exists():
            source_summary.append(dict(source=ref, images=0, acquisition=acquisition,
                                       status='bounded_transfer_unavailable', raw_path=str(raw)))
            continue
        annotation_map = annotation_index(raw)
        receipt_file = directory / 'provenance.json'
        receipt = read_json(receipt_file) if receipt_file.exists() else {}
        license_name = receipt.get('license_reported', 'CC BY 4.0 (existing local dataset card)')
        paths = sorted(p for p in raw.rglob('*') if p.suffix.lower() in prior.IMAGE_EXTENSIONS and p.is_file())
        summary = Counter()
        for index, path in enumerate(paths):
            relative = path.relative_to(raw).as_posix()
            ann = annotation_map.get(str(path.resolve()))
            original_label, label, label_origin = None, None, 'unmapped_no_disease_label'
            if ann:
                originals = ann['original_annotation_labels']
                mapped = {normalize_label(value) for value in originals}
                if len(mapped) == 1 and None not in mapped:
                    label = next(iter(mapped))
                original_label = '|'.join(originals)
                label_origin = ann['format'] + '_public_annotation_only'
            else:
                original_label, label = public_directory_label(path)
                label_origin = ('public_source_directory_name_only' if label
                                else 'unmapped_public_directory_name_only')
            # The original FMD dataset has cow/source identifiers, not disease labels.
            if acquisition == 'existing_detection_only_source':
                label = None
                label_origin = 'cattle_detection_only_no_disease_label'
            row = {
                'id': hashlib.sha256((ref + '/' + relative).encode()).hexdigest()[:24],
                'source_path': str(path.resolve()), 'relative_path': relative,
                'source_dataset': ref, 'source_url': 'https://www.kaggle.com/datasets/' + ref,
                'source_label': label, 'original_source_label': original_label,
                'label_origin': label_origin, 'public_annotation': ann,
                'license_reported': license_name, 'acquisition': acquisition,
                'animal_id': None, 'farm_id': None, 'capture_date': None,
                'veterinarian': None, 'clinical_reference': None,
                'laboratory_reference': None, 'clinically_verified': False,
                'prior_split': None, 'prior_group_id': None, 'prior_role': None,
                'file_sha256': sha256(path),
                'source_name_key': source_name_key(path.name, ref + ':' + str(label)),
            }
            if re.search(r'\b(?:goat|sheep|pig|swine|human|buffalo)\b', path.stem, re.IGNORECASE):
                row['source_label'] = None
                row['label_origin'] = 'catalog_only_filename_identifies_non_bovine_subject'
            if any(re.sub(r'[^a-z]', '', part.lower()) == 'normalteats' for part in path.parts):
                row['source_label'] = None
                row['label_origin'] = 'catalog_only_normal_teats_not_mastitis_disease_label'
            try:
                with Image.open(path) as opened:
                    image = ImageOps.exif_transpose(opened).convert('RGB')
                    image.load()
                width, height = image.size
                phash, dhash = prior.perceptual_hashes(image)
                mp, md = prior.perceptual_hashes(ImageOps.mirror(image))
                row.update(width=width, height=height, phash=phash, dhash=dhash,
                           phash_mirror=mp, dhash_mirror=md, decode_status='ok',
                           pixel_sha256=hashlib.sha256(f'RGB:{width}x{height}\0'.encode('ascii') + image.tobytes()).hexdigest())
            except Exception as error:
                row.update(decode_status='invalid', decode_error=type(error).__name__)
            records.append(row)
            summary[str(row['source_label'])] += 1
            if (index + 1) % 500 == 0:
                print(f'Inventory {ref}: {index + 1}/{len(paths)}', flush=True)
        source_summary.append(dict(source=ref, images=len(paths), source_label_counts=dict(summary),
                                   acquisition=acquisition, license_reported=license_name))
        print(json.dumps(source_summary[-1]), flush=True)
    with (OUTPUT / 'inventory.jsonl').open('w', encoding='utf-8') as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    write_json(OUTPUT / 'source_inventory.json', source_summary)
    write_json(OUTPUT / 'prior_frozen_inputs.json', {
        'created_utc': utc_now(),
        'prior_manifest_sha256': sha256(PRIOR / 'manifest.jsonl'),
        'prior_split_sha256': sha256(PRIOR / 'split.json'),
        'prior_best_pt_sha256': sha256(PRIOR / 'best.pt'),
        'test_representatives': [r['id'] for r in old_records if r['prior_split'] == 'test' and r['prior_role'] == 'representative'],
        'validation_representatives': [r['id'] for r in old_records if r['prior_split'] == 'val' and r['prior_role'] == 'representative'],
        'prior_prepared_test_sha256': {r['prepared_path']: r['prepared_sha256'] for r in old_records
                                       if r['prior_split'] == 'test' and r['prior_role'] == 'representative'},
    })


def load_jsonl(name):
    return [json.loads(line) for line in (OUTPUT / name).read_text(encoding='utf-8').splitlines() if line]


def prepare():
    global HOLDOUT_SOURCE
    if (OUTPUT / 'split.json').exists():
        raise FileExistsError('Prepared split is immutable')
    records = load_jsonl('inventory.jsonl')
    groups, edges = build_groups(records)
    by_id = {r['id']: r for r in records}
    holdout_candidates = []
    for ref, _ in SOURCES:
        novel = [g for g in groups if ref in g['sources'] and len(g['labels']) == 1
                 and g['labels'][0] in LABELS
                 and not any(by_id[i].get('prior_split') is not None for i in g['members'])
                 and any(by_id[i]['source_dataset'] == ref and by_id[i]['source_label'] in LABELS
                         for i in g['members'])]
        source_groups = [g for g in groups if ref in g['sources']]
        overlap = sum(any(by_id[i].get('prior_split') is not None for i in g['members']) for g in source_groups)
        holdout_candidates.append(dict(source=ref, novel_eligible_groups=len(novel),
                                       prior_overlap_fraction=overlap / max(1, len(source_groups)),
                                       classes=sorted({g['labels'][0] for g in novel})))
    candidates = [r for r in holdout_candidates if r['novel_eligible_groups'] >= 30
                  and len(r['classes']) >= 2 and r['prior_overlap_fraction'] <= 0.5]
    if candidates:
        selected = min(candidates, key=lambda r: (r['novel_eligible_groups'], r['source']))
        HOLDOUT_SOURCE = selected['source']
    write_json(OUTPUT / 'source_holdout_selection.json', {
        'locked_utc': utc_now(), 'selected': HOLDOUT_SOURCE, 'candidates': holdout_candidates,
        'policy': 'Before training/any inference: smallest entire new source with >=30 novel groups, >=2 explicit mapped classes and <=50% groups overlapping prior originals; fallback to calf source if none',
        'test_predictions_consulted': False,
    })
    assign_roles(records, groups, HOLDOUT_SOURCE)
    rows = []
    for split in ['train', 'val']:
        for label in LABELS:
            (OUTPUT / 'dataset' / split / label).mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(records):
        role = row['role']
        if role not in {'train', 'val', 'frozen_test', 'source_holdout'}:
            continue
        folder = ('dataset/' + role if role in {'train', 'val'} else
                  'heldout_test' if role == 'frozen_test' else 'independent_source_holdout')
        relative = Path(folder) / row['source_label'] / (row['id'] + '.png')
        target = OUTPUT / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if row.get('prior_role') == 'representative':
            old_path = PRIOR / row['prepared_path']
            assert sha256(old_path) == row['prepared_sha256']
            shutil.copyfile(old_path, target)
        else:
            with Image.open(row['source_path']) as opened:
                ImageOps.exif_transpose(opened).convert('RGB').save(target, compress_level=3)
        row['expanded_prepared_path'] = relative.as_posix()
        row['expanded_prepared_sha256'] = sha256(target)
        rows.append({
            'id': row['id'], 'group_id': row['global_group_id'],
            'source_label': row['source_label'],
            'split': 'test' if role == 'frozen_test' else role,
            'prepared_path': relative.as_posix(), 'prepared_sha256': row['expanded_prepared_sha256'],
            'source_dataset': row['source_dataset'], 'source_path': row['source_path'],
            'file_sha256': row['file_sha256'], 'pixel_sha256': row['pixel_sha256'],
            'prior_group_id': row.get('prior_group_id'), 'prior_split': row.get('prior_split'),
        })
        if len(rows) % 500 == 0:
            print(f'Materialized {len(rows)} protected/split inputs', flush=True)
    with (OUTPUT / 'manifest.jsonl').open('w', encoding='utf-8') as stream:
        for row in records:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
    write_json(OUTPUT / 'groups.json', groups)
    write_json(OUTPUT / 'duplicate_edges.json', edges)
    split_document = {
        'frozen_utc': utc_now(), 'seed': prior.SEED, 'images': rows,
        'validation_policy': 'Original prior validation representatives, unchanged unless globally conflicting/protected; no newly drawn validation',
        'test_policy': 'All original 413 test representatives preserved; any connected component is excluded from training',
        'source_holdout': HOLDOUT_SOURCE,
        'source_holdout_policy': 'Whole source excluded from training, only no-prior-overlap labeled groups evaluated',
    }
    write_json(OUTPUT / 'split.json', split_document)
    prior.write_csv(OUTPUT / 'split.csv', rows)
    write_json(OUTPUT / 'training_calibration_manifest.json', {
        'status': 'research_only', 'scope': 'training_images_only',
        'images': [row for row in rows if row['split'] == 'train'],
        'forbidden': ['val', 'test', 'source_holdout'],
    })
    source_overlap = []
    for source in sorted({r['source_dataset'] for r in records}):
        items = [r for r in records if r['source_dataset'] == source]
        matching = [g for g in groups if source in g['sources']]
        prior_connected = [g for g in matching if any(by_id[i].get('prior_split') is not None for i in g['members'])]
        source_overlap.append({
            'source': source, 'raw_images': len(items), 'connected_groups': len(matching),
            'groups_overlapping_prior_originals': len(prior_connected),
            'groups_overlapping_prior_test': sum(g['partition'] == 'frozen_test_protected' for g in matching),
            'groups_without_prior_overlap': len(matching) - len(prior_connected),
            'retained_train_representatives': sum(r['role'] == 'train' for r in items),
            'retained_holdout_representatives': sum(r['role'] == 'source_holdout' for r in items),
            'role_counts': dict(Counter(r['role'] for r in items)),
        })
    novel = [g for g in groups if not any(by_id[i].get('prior_split') is not None for i in g['members'])]
    new_download = [g for g in novel if any(by_id[i]['acquisition'] == 'new_public_download' for i in g['members'])]
    report = {
        'created_utc': utc_now(), 'original_prior_images': 3244, 'all_inventoried_images': len(records),
        'new_downloaded_images': sum(r['acquisition'] == 'new_public_download' for r in records),
        'valid_images': sum(r['decode_status'] == 'ok' for r in records),
        'invalid_images': sum(r['decode_status'] != 'ok' for r in records),
        'all_connected_groups': len(groups), 'role_counts': dict(Counter(r['role'] for r in records)),
        'partition_group_counts': dict(Counter(g['partition'] for g in groups)),
        'novel_groups_no_prior_original_overlap': len(novel),
        'novel_download_groups_no_prior_original_overlap': len(new_download),
        'novel_retained_training_groups': sum(g['partition'] == 'train' for g in novel),
        'novel_download_retained_training_groups': sum(g['partition'] == 'train' for g in new_download),
        'split_counts': dict(Counter(r['split'] for r in rows)),
        'split_class_counts': {split: dict(Counter(r['source_label'] for r in rows if r['split'] == split))
                               for split in ['train', 'val', 'test', 'source_holdout']},
        'edge_counts': dict(Counter(e['reason'] for e in edges)),
        'source_overlap': source_overlap,
        'fixed_holdout_source': HOLDOUT_SOURCE,
        'clinical_grouping_available': False,
        'grouping': {'pixel_sha256': True, 'file_sha256': True, 'source_names_global_when_descriptive': True,
                     'original_prior_components_preserved': True, 'phash_hamming_max': 6,
                     'dhash_hamming_max': 10, 'aspect_ratio_relative_max': 1.10,
                     'mirror_matching': True, 'transitive_connected_components': True,
                     'numeric_names': 'Namespaced by source and original label; equality alone is not cross-source evidence'},
    }
    write_json(OUTPUT / 'deduplication_report.json', report)
    write_json(OUTPUT / 'data_integrity_verification.json', verify_data(check_source=True))
    print(json.dumps(report, indent=2), flush=True)


def verify_data(check_source=False):
    records = load_jsonl('manifest.jsonl')
    by_id = {r['id']: r for r in records}
    split = read_json(OUTPUT / 'split.json')
    lock = read_json(OUTPUT / 'prior_frozen_inputs.json')
    assert sha256(PRIOR / 'manifest.jsonl') == lock['prior_manifest_sha256']
    assert sha256(PRIOR / 'split.json') == lock['prior_split_sha256']
    expected_test = set(lock['test_representatives'])
    actual_test = {r['id'] for r in split['images'] if r['split'] == 'test'}
    assert actual_test == expected_test and len(actual_test) == 413
    groups = read_json(OUTPUT / 'groups.json')
    for group in groups:
        component = [by_id[i] for i in group['members']]
        roles = {r['role'] for r in component}
        if 'train' in roles:
            assert not any(r.get('prior_split') in {'test', 'val', 'quarantine'} for r in component)
            assert split['source_holdout'] not in {r['source_dataset'] for r in component}
            assert roles.isdisjoint({'val', 'frozen_test', 'source_holdout', 'quarantine_cross_label'})
    for edge in read_json(OUTPUT / 'duplicate_edges.json'):
        assert by_id[edge['left_id']]['global_group_id'] == by_id[edge['right_id']]['global_group_id']
    for key in ['file_sha256', 'pixel_sha256', 'source_name_key', 'prior_group_id']:
        values = defaultdict(set)
        for record in records:
            if record.get(key) and record.get('global_group_id'):
                values[record[key]].add(record['global_group_id'])
        assert all(len(components) == 1 for components in values.values()), key
    for row in split['images']:
        assert sha256(OUTPUT / row['prepared_path']) == row['prepared_sha256']
        assert row['split'] not in {'test', 'source_holdout'} or not row['prepared_path'].startswith('dataset/')
    if check_source:
        for row in records:
            assert sha256(row['source_path']) == row['file_sha256'], row['id']
    assert not (OUTPUT / 'dataset/test').exists()
    assert not (OUTPUT / 'dataset/source_holdout').exists()
    for name, digest in lock['prior_prepared_test_sha256'].items():
        assert sha256(PRIOR / name) == digest
    return dict(passed=True, checked_utc=utc_now(), frozen_test_images=413,
                all_source_files_verified=len(records) if check_source else 0,
                prepared_images_verified=len(split['images']),
                global_train_test_component_overlap=0, global_train_val_component_overlap=0,
                global_train_source_holdout_overlap=0, original_prior_files_unchanged=True,
                trainer_has_test_directory=False)


def train():
    import torch
    from ultralytics import YOLO
    if (OUTPUT / 'training_summary.json').exists():
        raise FileExistsError('Candidate already trained; no test-driven rerun')
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is required; no silent CPU fallback')
    verified = verify_data()
    pretrained = PRIOR / 'pretrained/yolov8n-cls.pt'
    assert sha256(pretrained) == read_json(PRIOR / 'pretrained/source.json')['sha256']
    config = dict(
        data=str((OUTPUT / 'dataset').resolve()), epochs=30, patience=8,
        batch=16, imgsz=224, workers=0, device=0, seed=prior.SEED,
        deterministic=True, optimizer='AdamW', lr0=0.001, lrf=0.01,
        weight_decay=0.0005, warmup_epochs=3, amp=False, cache=False,
        plots=True, save=True, project=str(OUTPUT / 'runs'), name='candidate',
        exist_ok=False, auto_augment=None, erasing=0.0, scale=0.3,
        hsv_h=0.015, hsv_s=0.3, hsv_v=0.2, fliplr=0.5, flipud=0.0,
        dropout=0.1, verbose=True,
    )
    protocol = dict(
        locked_before_training_utc=utc_now(), config=config,
        split_sha256=sha256(OUTPUT / 'split.json'),
        manifest_sha256=sha256(OUTPUT / 'manifest.jsonl'),
        script_sha256=sha256(Path(__file__)), pretrained_sha256=sha256(pretrained),
        data_integrity=verified, candidate_runs_planned=1,
        initialization='Original official ImageNet pretrained YOLOv8n-cls, not prior disease-finetuned weights; avoids inheriting any globally newly discovered legacy leakage',
        selection='Fixed original validation only; native (top1+top5)/2 ranks top1 for 3 classes; latest equal-fitness checkpoint',
        test_use='No test loading for optimizer, early stopping, hyperparameter or checkpoint selection',
        dataset_scope='Public source-label appearance classification; no clinical diagnosis',
    )
    write_json(OUTPUT / 'training_protocol.json', protocol)
    shutil.copyfile(Path(__file__), OUTPUT / 'training_script_at_fit.py')
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    model = YOLO(str(pretrained), task='classify')
    events = []

    def record_checkpoint(trainer):
        if trainer.best_fitness == trainer.fitness:
            events.append(dict(epoch_1based=trainer.epoch + 1, fitness=float(trainer.fitness),
                               validation_top1=float(trainer.metrics['metrics/accuracy_top1'])))
            write_json(OUTPUT / 'best_checkpoint_events.json', events)

    model.add_callback('on_model_save', record_checkpoint)
    start = time.perf_counter()
    model.train(**config)
    elapsed = time.perf_counter() - start
    run = Path(model.trainer.save_dir)
    shutil.copyfile(run / 'weights/best.pt', OUTPUT / 'best.pt')
    shutil.copyfile(run / 'results.csv', OUTPUT / 'training_history.csv')
    with (OUTPUT / 'training_history.csv').open(encoding='utf-8-sig', newline='') as stream:
        history = [{key.strip(): value.strip() for key, value in row.items()} for row in csv.DictReader(stream)]
    best_row = max(history, key=lambda r: float(r['metrics/accuracy_top1']))
    summary = dict(
        completed_utc=utc_now(), elapsed_seconds=elapsed, epochs_completed=len(history),
        epochs_requested=30, patience=8, selected_checkpoint_epoch=events[-1]['epoch_1based'],
        maximum_validation_top1=float(best_row['metrics/accuracy_top1']),
        best_checkpoint_sha256=sha256(OUTPUT / 'best.pt'),
        gpu=torch.cuda.get_device_name(0), peak_cuda_memory_allocated_bytes=torch.cuda.max_memory_allocated(),
        train_images=read_json(OUTPUT / 'deduplication_report.json')['split_counts']['train'],
        checkpoint_selection='Validation only; single predetermined run; latest validation fitness tie',
    )
    write_json(OUTPUT / 'training_summary.json', summary)
    write_json(OUTPUT / 'heldout_lock.json', dict(
        locked_utc=utc_now(), checkpoint_sha256=summary['best_checkpoint_sha256'],
        split_sha256=sha256(OUTPUT / 'split.json'),
        protocol_sha256=sha256(OUTPUT / 'training_protocol.json'),
        statement='Weights selected/frozen before any frozen-test or source-holdout inference; no test-driven retraining',
    ))
    print(json.dumps(summary, indent=2), flush=True)


def metrics_for(rows, probabilities):
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, classification_report, confusion_matrix, f1_score, log_loss
    target = np.asarray([LABELS.index(r['source_label']) for r in rows])
    predicted = np.argmax(probabilities, axis=1)
    count = len(rows)
    accuracy = float(accuracy_score(target, predicted))
    z = 1.959963984540054
    center = (accuracy + z * z / (2 * count)) / (1 + z * z / count)
    radius = z * np.sqrt(accuracy * (1 - accuracy) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    present = sorted(set(target.tolist()))
    return dict(
        scope='Public source-label image groups, not animal/farm-independent clinical accuracy',
        n_images=count, n_global_image_groups=len({r['group_id'] for r in rows}),
        correct=int(np.sum(target == predicted)), accuracy=accuracy,
        balanced_accuracy=float(balanced_accuracy_score(target, predicted)),
        macro_f1=float(f1_score(target, predicted, labels=range(3), average='macro', zero_division=0)),
        macro_f1_present_classes=float(f1_score(target, predicted, labels=present, average='macro', zero_division=0)),
        weighted_f1=float(f1_score(target, predicted, average='weighted', zero_division=0)),
        log_loss=float(log_loss(target, probabilities, labels=range(3))),
        accuracy_wilson95=[float(center - radius), float(center + radius)],
        interval_limit='Image-binomial approximation; repeated global groups and unobserved animals/farms are not independent',
        label_order=LABELS, classes_present=[LABELS[i] for i in present],
        classification_report=classification_report(target, predicted, labels=range(3), target_names=LABELS,
                                                    output_dict=True, zero_division=0),
        confusion_matrix_rows_true_columns_predicted=confusion_matrix(target, predicted, labels=range(3)).tolist(),
        test_used_for_selection=False,
    )


def finalize():
    import onnx
    import onnxruntime as ort
    import torch
    from ultralytics import YOLO
    from ultralytics.data.augment import classify_transforms
    lock = read_json(OUTPUT / 'heldout_lock.json')
    assert lock['checkpoint_sha256'] == sha256(OUTPUT / 'best.pt')
    assert lock['split_sha256'] == sha256(OUTPUT / 'split.json')
    write_json(OUTPUT / 'data_integrity_verification.json', verify_data(check_source=True))
    torch.set_num_threads(4)
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cuda.matmul.allow_tf32 = False
    model = YOLO(str(OUTPUT / 'best.pt'), task='classify')
    assert [model.names[i] for i in range(3)] == LABELS
    exported = Path(model.export(format='onnx', imgsz=224, batch=1, dynamic=False,
                                 opset=13, simplify=False, half=False, device='cpu'))
    graph = onnx.load(str(exported))
    onnx.checker.check_model(graph)
    producer = next(n for n in graph.graph.node if graph.graph.output[0].name in n.output)
    assert producer.op_type == 'Softmax'
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(exported), options, providers=['CPUExecutionProvider'])
    baseline_session = ort.InferenceSession(str(PRIOR / 'best.onnx'), options, providers=['CPUExecutionProvider'])
    input_info, output_info = session.get_inputs()[0], session.get_outputs()[0]
    assert input_info.shape == [1, 3, 224, 224] and output_info.shape == [1, 3]
    assert input_info.type == 'tensor(float)'
    contract = read_json(PRIOR / 'input_output_contract.json')
    contract.update(input_name=input_info.name, output_name=output_info.name,
                    onnx_sha256=sha256(exported), checkpoint_sha256=sha256(OUTPUT / 'best.pt'),
                    source_scope='Expanded public appearance source labels, research_only',
                    labels=LABELS, output='softmax probabilities', softmax_in_graph=True,
                    apply_softmax_again=False, opset=13, static_batch_1=True)
    write_json(OUTPUT / 'input_output_contract.json', contract)
    (OUTPUT / 'labels.txt').write_text('\n'.join(LABELS) + '\n', encoding='utf-8')
    write_json(OUTPUT / 'completion.json', dict(
        status='export_ready_evaluation_pending', onnx_sha256=sha256(exported),
        best_pt_sha256=sha256(OUTPUT / 'best.pt'), contract=contract,
        selected_before_test=True, model_use='research_only', hardware_deployment=False,
    ))
    print('EXPORT_READY ' + json.dumps(dict(path=str(exported), sha256=sha256(exported),
                                           input='RGB float32 NCHW [1,3,224,224] /255, aspect resize + center crop',
                                           output='[1,3] softmax probabilities, softmax=False', labels=LABELS)), flush=True)
    transform = classify_transforms(size=224)
    split = read_json(OUTPUT / 'split.json')
    training_rows = [r for r in split['images'] if r['split'] == 'train']
    reference_rows = [next(r for r in training_rows if r['source_label'] == label) for label in LABELS]
    references = []
    for row in reference_rows:
        with Image.open(OUTPUT / row['prepared_path']) as opened:
            references.append(transform(opened.convert('RGB')).unsqueeze(0).numpy())
    np.save(OUTPUT / 'reference_inputs_nchw_float32.npy', np.concatenate(references))
    write_json(OUTPUT / 'reference_input_records.json', reference_rows)
    network = YOLO(str(OUTPUT / 'best.pt'), task='classify').model.float().to('cuda:0').eval()
    all_differences, all_argmax, combined_metrics = [], [], {}
    prediction_started = utc_now()
    for subset, filename in [('test', 'frozen_test'), ('source_holdout', 'independent_source_holdout')]:
        rows = sorted([r for r in split['images'] if r['split'] == subset],
                      key=lambda r: (r['source_label'], r['id']))
        if not rows:
            combined_metrics[filename] = {'status': 'unavailable_no_eligible_novel_labeled_groups'}
            continue
        predictions, candidate_prob, baseline_prob = [], [], []
        for index, row in enumerate(rows):
            with Image.open(OUTPUT / row['prepared_path']) as opened:
                tensor = transform(opened.convert('RGB')).unsqueeze(0).float()
            with torch.inference_mode():
                probability, logits = network(tensor.to('cuda:0'))
            probability, logits = probability.cpu().numpy()[0], logits.cpu().numpy()[0]
            actual = session.run(None, {input_info.name: tensor.numpy()})[0][0]
            baseline = baseline_session.run(None, {baseline_session.get_inputs()[0].name: tensor.numpy()})[0][0]
            np.testing.assert_allclose(actual, probability, atol=1e-5, rtol=1e-4)
            assert np.isfinite(actual).all() and abs(float(actual.sum()) - 1) < 1e-5
            delta = float(np.max(np.abs(actual - probability)))
            all_differences.append(delta)
            all_argmax.append(int(actual.argmax()) == int(probability.argmax()))
            candidate_prob.append(actual)
            baseline_prob.append(baseline)
            predictions.append({**row,
                'candidate_label': LABELS[int(actual.argmax())],
                'baseline_label': LABELS[int(baseline.argmax())],
                'candidate_correct': LABELS[int(actual.argmax())] == row['source_label'],
                'baseline_correct': LABELS[int(baseline.argmax())] == row['source_label'],
                'pt_onnx_max_abs_difference': delta,
                **{f'candidate_probability_{label}': float(actual[i]) for i, label in enumerate(LABELS)},
                **{f'pytorch_probability_{label}': float(probability[i]) for i, label in enumerate(LABELS)},
                **{f'pytorch_logit_{label}': float(logits[i]) for i, label in enumerate(LABELS)},
                **{f'baseline_probability_{label}': float(baseline[i]) for i, label in enumerate(LABELS)},
            })
            if (index + 1) % 100 == 0 or index + 1 == len(rows):
                print(f'{filename} PT/ONNX and baseline predictions {index + 1}/{len(rows)}', flush=True)
        candidate_metric = metrics_for(rows, np.asarray(candidate_prob))
        baseline_metric = metrics_for(rows, np.asarray(baseline_prob))
        comparison = dict(
            candidate=candidate_metric, prior_baseline=baseline_metric,
            accuracy_change=candidate_metric['accuracy'] - baseline_metric['accuracy'],
            macro_f1_change=candidate_metric['macro_f1'] - baseline_metric['macro_f1'],
            candidate_only_correct=sum(r['candidate_correct'] and not r['baseline_correct'] for r in predictions),
            baseline_only_correct=sum(r['baseline_correct'] and not r['candidate_correct'] for r in predictions),
            checkpoint_locked_utc=lock['locked_utc'], prediction_started_utc=prediction_started,
            source_independence_limit='Disjoint observed pixel/perceptual/source-name components only; no animal/farm identity or verified clinical reference',
        )
        write_json(OUTPUT / f'{filename}_metrics.json', comparison)
        prior.write_csv(OUTPUT / f'{filename}_predictions.csv', predictions)
        combined_metrics[filename] = comparison
    parity = dict(passed=True, tested_images=len(all_differences),
                  maximum_absolute_difference=max(all_differences),
                  mean_image_maximum_absolute_difference=float(np.mean(all_differences)),
                  argmax_agreement=float(np.mean(all_argmax)), atol=1e-5, rtol=1e-4,
                  pytorch_device='cuda:0 strict FP32, TF32 disabled',
                  onnx_provider='CPUExecutionProvider', onnx_checker_passed=True,
                  input_shape=input_info.shape, output_shape=output_info.shape,
                  softmax_in_graph=True)
    write_json(OUTPUT / 'onnx_parity.json', parity)
    prior.freeze_environment(OUTPUT)
    shutil.copyfile(Path(__file__), OUTPUT / 'training_script_snapshot.py')
    write_json(OUTPUT / 'completion.json', dict(
        completed_utc=utc_now(), status='research_only_completed',
        onnx_sha256=sha256(exported), best_pt_sha256=sha256(OUTPUT / 'best.pt'),
        selected_before_test=True, test_driven_retraining=False, pt_onnx_parity=parity,
        metrics=combined_metrics, model_use='research_only', hardware_deployment=False,
    ))
    catalog_audit()
    generate_documents()
    prior.write_hashes(OUTPUT)
    print(json.dumps({'metrics': combined_metrics, 'parity': parity}, indent=2), flush=True)


def catalog_audit():
    records = load_jsonl('manifest.jsonl')
    groups = read_json(OUTPUT / 'groups.json')
    by_id = {r['id']: r for r in records}
    sources = sorted({r['source_dataset'] for r in records})
    matrix = []
    for source in sources:
        matrix.append({'source': source, **{other: sum(source in g['sources'] and other in g['sources']
                                                    for g in groups) for other in sources}})
    prior.write_csv(OUTPUT / 'source_pair_global_group_overlap.csv', matrix)
    write_json(OUTPUT / 'source_pair_global_group_overlap.json', matrix)
    source_receipts = []
    for ref, folder in SOURCES:
        directory = EXTERNAL / folder
        receipt_path = directory / 'provenance.json'
        if receipt_path.exists():
            receipt = read_json(receipt_path)
            assert sha256(directory / 'archive.zip') == receipt['archive_sha256']
            source_receipts.append({**receipt, 'local_source_folder': str(directory),
                                    'source_card_sha256': sha256(directory / 'DATASET_CARD.md'),
                                    'metadata_sha256': sha256(directory / 'kaggle_metadata.json')})
    write_json(OUTPUT / 'source_acquisition_receipts.json', source_receipts)
    old_validation = [r for r in records if r.get('prior_split') == 'val' and r.get('prior_role') == 'representative']
    old_training = [r for r in records if r.get('prior_split') == 'train' and r.get('prior_role') == 'representative']
    removed = [{k: r.get(k) for k in ['id', 'prior_group_id', 'global_group_id', 'source_label', 'role', 'source_path']}
               for r in old_validation if r['role'] != 'val']
    write_json(OUTPUT / 'split_exclusion_audit.json', dict(
        prior_train_representatives=len(old_training),
        prior_train_retained=sum(r['role'] == 'train' for r in old_training),
        prior_train_removed_role_counts=dict(Counter(r['role'] for r in old_training if r['role'] != 'train')),
        prior_validation_representatives=len(old_validation),
        prior_validation_retained=sum(r['role'] == 'val' for r in old_validation),
        removed_prior_validation=removed,
        legacy_train_now_connected_to_frozen_test=[
            {k: r.get(k) for k in ['id', 'prior_group_id', 'global_group_id', 'source_label', 'source_path']}
            for r in old_training if r['role'] == 'excluded_frozen_test_component'],
        frozen_test_conflicting_external_label_groups=[g['group_id'] for g in groups
            if g['partition'] == 'frozen_test_protected' and len(g['labels']) > 1],
        test_images_preserved_even_with_external_label_conflict=True,
        clinical_label_overrides_performed=False,
    ))
    source = EXTERNAL / 'PublicSearch_expanded-20261026'
    searches = []
    for path in sorted(source.glob('*.json')):
        receipt = read_json(path)
        searches.append({k: receipt[k] for k in ['url', 'params', 'utc', 'status', 'failure_type', 'reason'] if k in receipt})
    write_json(OUTPUT / 'public_search_receipts_summary.json', searches)
    rejected = OUTPUT / 'rejected_preparation_01'
    assert not list(rejected.rglob('*.pt'))
    assert not list(rejected.rglob('results.csv'))
    write_json(OUTPUT / 'preparation_correction_audit.json', dict(
        rejected_preparation='rejected_preparation_01',
        reason='Detected ancestor-directory disease-label fallback and unsuitable high-overlap whole-source holdout before optimizer training',
        correction='Only direct class-directory labels accepted; whole-source holdout requires <=50% prior overlap',
        rejected_preparation_has_model_checkpoint=False,
        corrected_run_test_driven_changes=False,
        source_holdout_selection_before_inference=True,
        source_labels_not_manufactured=True,
    ))


def verify_handoff():
    """Verify prepared host conversion inputs without training or device access."""
    import onnx
    import onnxruntime as ort
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode

    conversion = ROOT / 'vision-training-data/maixcam-expanded-yolo-20261026'
    metadata = read_json(conversion / 'conversion_inputs.json')
    completion = read_json(OUTPUT / 'completion.json')
    contract = read_json(OUTPUT / 'input_output_contract.json')
    assert sha256(OUTPUT / 'best.onnx') == completion['onnx_sha256'] == metadata['source_onnx_sha256']
    assert sha256(OUTPUT / 'best.pt') == completion['best_pt_sha256']
    assert sha256(conversion / 'classifier_logits.onnx') == metadata['logit_onnx_sha256']
    assert metadata['scope'] == 'research_only' and metadata['classifier_softmax'] is True
    assert metadata['labels'] == contract['labels'] == LABELS
    assert metadata['input_shape'] == contract['input_shape'] == [1, 3, 224, 224]
    assert contract['softmax_in_graph'] is True and contract['apply_softmax_again'] is False
    split = read_json(OUTPUT / 'split.json')
    by_id = {row['id']: row for row in split['images']}
    calibration = metadata['calibration_records']
    assert len(calibration) == 120
    assert len({row['source_id'] for row in calibration}) == 120
    assert len({row['group_id'] for row in calibration}) == 120
    assert Counter(row['source_label'] for row in calibration) == {label: 40 for label in LABELS}
    evaluation_groups = {row['group_id'] for row in split['images'] if row['split'] != 'train'}
    geometry = transforms.Compose([
        transforms.Resize(224, interpolation=InterpolationMode.BILINEAR, antialias=True),
        transforms.CenterCrop((224, 224)),
    ])
    for row in calibration:
        original = by_id[row['source_id']]
        assert row['split'] == original['split'] == 'train'
        assert row['group_id'] == original['group_id'] and row['group_id'] not in evaluation_groups
        assert row['source_label'] == original['source_label']
        assert row['source_sha256'] == original['prepared_sha256']
        assert sha256(OUTPUT / original['prepared_path']) == row['source_sha256']
        prepared = conversion / 'calibration' / row['file']
        assert sha256(prepared) == row['calibration_sha256']
        with Image.open(OUTPUT / original['prepared_path']) as image:
            expected = np.asarray(geometry(image.convert('RGB')))
        with Image.open(prepared) as image:
            actual = np.asarray(image.convert('RGB'))
        np.testing.assert_array_equal(actual, expected)
        assert actual.shape == (224, 224, 3)
    source_graph = onnx.load(str(OUTPUT / 'best.onnx'))
    logit_graph = onnx.load(str(conversion / 'classifier_logits.onnx'))
    onnx.checker.check_model(source_graph)
    onnx.checker.check_model(logit_graph)
    producer = next(n for n in logit_graph.graph.node if logit_graph.graph.output[0].name in n.output)
    assert producer.op_type == 'Gemm'
    assert not any(n.op_type == 'Softmax' for n in logit_graph.graph.node)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    source_session = ort.InferenceSession(str(OUTPUT / 'best.onnx'), options, providers=['CPUExecutionProvider'])
    logit_session = ort.InferenceSession(str(conversion / 'classifier_logits.onnx'), options, providers=['CPUExecutionProvider'])
    differences = []
    references = np.load(OUTPUT / 'reference_inputs_nchw_float32.npy')
    reference_rows = read_json(OUTPUT / 'reference_input_records.json')
    assert len(references) == len(reference_rows) == 3
    assert all(row['split'] == 'train' for row in reference_rows)
    for array in references:
        tensor = array[None].astype(np.float32)
        probability = source_session.run(None, {source_session.get_inputs()[0].name: tensor})[0]
        logits = logit_session.run(None, {logit_session.get_inputs()[0].name: tensor})[0]
        restored = np.exp(logits - logits.max(axis=1, keepdims=True))
        restored /= restored.sum(axis=1, keepdims=True)
        np.testing.assert_allclose(restored, probability, atol=1e-6, rtol=1e-5)
        differences.append(float(np.max(np.abs(restored - probability))))
    report = dict(
        checked_utc=utc_now(), status='host_handoff_verified', source_onnx_sha256=completion['onnx_sha256'],
        logit_onnx_sha256=metadata['logit_onnx_sha256'], best_pt_sha256=completion['best_pt_sha256'],
        calibration_files_and_source_hashes_verified=120, calibration_geometry_pixel_exact=True,
        calibration_unique_training_groups=120, calibration_per_class={label: 40 for label in LABELS},
        calibration_evaluation_group_overlap=0, logits_softmax_reference_tensors_tested=3,
        logits_softmax_max_abs_difference=max(differences), output_labels=LABELS,
        source_probability_graph_classifier_softmax=False, extracted_logit_graph_classifier_softmax=True,
        training_rerun=False, heldout_inference_rerun=False, model_weights_changed=False,
        conversion_job_owner='main agent; existing WSL process left untouched',
        device_execution_verified=False, physical_deployment_verified=False,
        device_limit='Camera USB/network unavailable as reported by user; no device connection attempted',
        ui_validation='Static source inspection only; generic feature/archive badge for research_only; existing vision screenshot predates this work',
    )
    write_json(OUTPUT / 'handoff_final_verification.json', report)
    generate_documents()
    prior.write_hashes(OUTPUT)
    print(json.dumps(report, indent=2), flush=True)


def verify_conversion_files():
    """Inspect main-agent conversion outputs; never execute or deploy a device."""
    import configparser

    conversion = ROOT / 'vision-training-data/maixcam-expanded-yolo-20261026'
    result = read_json(conversion / 'conversion_result.json')
    completion = read_json(OUTPUT / 'completion.json')
    report = read_json(OUTPUT / 'handoff_final_verification.json')
    assert result['status'] == 'converted_research_only' and result['scope'] == 'research_only'
    assert result['source_onnx_sha256'] == completion['onnx_sha256'] == sha256(OUTPUT / 'best.onnx')
    assert result['logit_onnx_sha256'] == report['logit_onnx_sha256'] == sha256(conversion / 'classifier_logits.onnx')
    assert result['classifier_softmax'] is True and result['device_execution_verified'] is False
    assert sha256(conversion / 'cattle_research_int8.cvimodel') == result['cvimodel_sha256']
    settings = configparser.ConfigParser()
    settings.read(conversion / 'cattle_research.mud', encoding='utf-8')
    assert settings['basic']['type'] == 'cvimodel'
    assert settings['basic']['model'] == 'cattle_research_int8.cvimodel'
    assert settings['extra']['model_type'] == 'classifier' and settings['extra']['input_type'] == 'rgb'
    assert settings['extra']['labels'].split(',') == LABELS
    assert [float(v) for v in settings['extra']['mean'].split(',')] == [0, 0, 0]
    np.testing.assert_allclose([float(v) for v in settings['extra']['scale'].split(',')], [1 / 255] * 3,
                               atol=0, rtol=1e-15)
    deployment_log = (conversion / 'model_deploy.log').read_text(encoding='utf-8')
    report.update(
        converted_host_files_checked_utc=utc_now(), converted_host_file_status='hashes_and_metadata_verified',
        cvimodel_sha256=result['cvimodel_sha256'], mud_sha256=sha256(conversion / 'cattle_research.mud'),
        mud_same_directory_model_reference_verified=True, mud_color_normalization_labels_verified=True,
        host_simulator_compare_success_observed='[Success]: npz_tool.py compare' in deployment_log,
        int8_heldout_accuracy_evaluated_here=False,
        physical_deployment_verified=False, device_execution_verified=False,
    )
    write_json(OUTPUT / 'handoff_final_verification.json', report)
    generate_documents()
    prior.write_hashes(OUTPUT)
    print(json.dumps(report, indent=2), flush=True)


def generate_documents():
    report = read_json(OUTPUT / 'deduplication_report.json')
    training = read_json(OUTPUT / 'training_summary.json')
    completion = read_json(OUTPUT / 'completion.json')
    lines = ['# Expanded cattle appearance YOLO research, 2026-10-26', '',
             'Status: research_only. Public source-directory/annotation appearance labels are not clinical diagnoses.', '',
             '## Actual Data', '',
             'Global components use file/pixel hashes, original prior groups, normalized descriptive source names,',
             '64-bit pHash <=6 AND dHash <=10, aspect ratio within 10%, including horizontal mirrors.',
             'Numeric/generic names are source-and-label namespaced. Transitive components are kept intact.', '',
             f'- Inventoried images: {report["all_inventoried_images"]}; new public downloaded images: {report["new_downloaded_images"]}.',
             f'- Global groups: {report["all_connected_groups"]}; novel groups with no prior-original overlap: {report["novel_groups_no_prior_original_overlap"]}.',
             f'- Genuinely new retained training groups: {report["novel_retained_training_groups"]}; of these connected to new downloads: {report["novel_download_retained_training_groups"]}.',
             f'- Actual input counts: {report["split_counts"]}.', '',
             '| Split | foot-and-mouth | healthy | lumpy |', '|---|---:|---:|---:|']
    for split, counts in report['split_class_counts'].items():
        lines.append(f'| {split} | ' + ' | '.join(str(counts.get(label, 0)) for label in LABELS) + ' |')
    lines += ['', '## Public Sources And Overlap', '',
              '| Source | Raw Images | Groups | Overlap Prior | Overlap Prior Test | Retained Train | Source Holdout |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for source in report['source_overlap']:
        lines.append('| ' + source['source'] + ' | ' + ' | '.join(str(source[k]) for k in [
            'raw_images', 'connected_groups', 'groups_overlapping_prior_originals',
            'groups_overlapping_prior_test', 'retained_train_representatives', 'retained_holdout_representatives']) + ' |')
    lines += ['', 'Exact official URLs, version metadata, uploader licenses and archive SHA-256 are preserved in',
              'each new external-data source folder ending expanded-20261026. Search receipts are in',
              'PublicSearch_expanded-20261026. GitHub/Zenodo search results were catalogued; HF public API TLS failed.',
              'Search was bounded to first pages and five Kaggle acquisitions, with bounded/resumable transfers.', '',
              'The old 125-image FMD package has only cow/source annotation categories and supplied no FMD labels.',
              'The new 80-image FMD package explicitly annotates the source spelling "foot and mougth".',
              'Calf "unhealthy" is deliberately left unmapped; no disease label is synthesized.',
              'Mastitis and filename-identified non-bovine subjects are not added to the three classifier labels.', '',
              '## Frozen Selection And Training', '',
              'All prior 413 test representatives are copied byte-for-byte and retained, outside the trainer root.',
              'Any global component touching any prior test member is excluded from training, even through new-source bridges.',
              'Original validation representatives are fixed, with components that become protected or label-conflicting removed.',
              f'Source holdout chosen before model inference: {report["fixed_holdout_source"]}. Selection evidence is in source_holdout_selection.json.',
              'The entire source is excluded from training; evaluated source groups have no overlap with any prior original.', '',
              'One fixed run initialized from original official YOLOv8n-cls ImageNet weights, without inheriting prior disease-fit weights.',
              'AdamW, 224, batch16, workers0, FP32, lr0=.001/lrf=.01, weight_decay=.0005, dropout=.1, seed20261026,',
              '30 epoch cap, patience8; crop area .7-1, horizontal flip .5, HSV .015/.3/.2, no auto augment/erasing.',
              f'Actual GPU: {training["gpu"]}; epochs {training["epochs_completed"]}; elapsed {training["elapsed_seconds"]:.2f}s;',
              f'maximum fixed-validation top1 {training["maximum_validation_top1"]:.6f}; selected epoch {training["selected_checkpoint_epoch"]}.',
              'Checkpoint fitness uses validation only; latest equal-fitness tie, then SHA-locked before heldout inference.', '',
              'Global cross-source bridges exposed 3 original training representatives connected to frozen test components.',
              'They are excluded here. The prior model may inherit that historical duplication; it is a historical baseline,',
              'and the current candidate deliberately starts from the original official pretrained weights instead.', '',
              '## Comparable Results', '',
              '| Evaluation | Images | Prior Accuracy | Candidate Accuracy | Prior Macro-F1 | Candidate Macro-F1 |',
              '|---|---:|---:|---:|---:|---:|']
    for key, value in completion['metrics'].items():
        if 'candidate' in value:
            old, new = value['prior_baseline'], value['candidate']
            lines.append(f'| {key} | {new["n_images"]} | {old["accuracy"]:.6f} | {new["accuracy"]:.6f} | {old["macro_f1"]:.6f} | {new["macro_f1"]:.6f} |')
            lines += []
    lines += ['', 'Per-class metrics, confusion matrices, probabilities/logits, paired correctness and Wilson intervals are',
              'in the corresponding metrics JSON and predictions CSV files. Tests were evaluated only after weights were fixed.',
              'A lower candidate score is reported as such; no additional test-driven run or automatic production promotion occurs.', '',
              '## ONNX And Conversion Handoff', '',
              f'- best.onnx SHA-256: `{completion["onnx_sha256"]}`.',
              f'- best.pt SHA-256: `{completion["best_pt_sha256"]}`.',
              '- Static float32 input images [1,3,224,224], RGB NCHW, pixels /255.',
              '- EXIF transpose, bilinear resize shorter edge to224 with aspect preserved, center crop224.',
              '- Output [1,3], labels 0 foot-and-mouth, 1 healthy, 2 lumpy; Softmax is already in graph.',
              '- nn.Classifier must use softmax=False for best.onnx. A separately extracted logits graph must use True and revalidate.',
              '- mean=[0,0,0], scale=[1/255,1/255,1/255], formula (pixel-mean)*scale; avoid double normalization.',
              '- split.json images and training_calibration_manifest.json are converter-compatible; calibration uses train only.',
              '- Three train-only float32 reference tensors and exact input records accompany input_output_contract.json.',
              f'- PT CUDA/ONNX CPU parity: {completion["pt_onnx_parity"]}.', '',
              'No cvimodel/mud conversion, device execution, hardware/backend changes or production registration was performed here.', '',
              '## Limits', '',
              'All sources lack verified animal IDs, farm IDs, recording dates, veterinarian labels and clinical reference standards.',
              'Uploader licenses/collection claims do not establish individual image rights or clinical correctness.',
              'Image components reduce known duplicate leakage but cannot prove distinct animals/farms or detect every crop, montage,',
              'rotation, repeated animal view, web repost or pretraining overlap. Source holdout is a public-source stress test.',
              'Directory labels can encode background/breed/watermark/source bias; healthy is not verified clinical health.',
              'No clinical diagnosis, calibration, sensitivity in farms, lesion localization or risk-fusion claim is made.',
              'Ultralytics code/weights licensing remains applicable.', '',
              'Before training, a preparation attempt was rejected because ancestor-directory parsing could map "unhealthy"',
              'from an LSD dataset root and a highly overlapping whole-source holdout discarded nearly all old training data.',
              'That attempt, which has no model checkpoint or epoch results, is retained under rejected_preparation_01.',
              'The corrected run uses only direct class-directory labels and source-overlap criteria; no test predictions',
              'were used for these corrections. split_exclusion_audit.json documents every removed prior validation image.',
              'source_acquisition_receipts.json and source_pair_global_group_overlap.csv preserve hashes/licenses and source intersections.', '',
              '## Commands', '', '```powershell',
              '& .run/cattle-ml-venv/Scripts/python.exe -m unittest discover -s scripts -p test_vision_expand_retrain_20261026.py',
              '& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage acquire',
              '& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage inventory',
              '& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage prepare',
              '& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage train',
              '& .run/cattle-ml-venv/Scripts/python.exe scripts/vision_expand_retrain_20261026.py --stage finalize',
              '```', '', 'Inventory, split preparation and training refuse an existing completed stage. No old run is overwritten.',
              'SHA256SUMS.txt/artifact_hashes.json cover artifacts except their own indexes and active console.log.', '']
    handoff = OUTPUT / 'handoff_final_verification.json'
    if handoff.exists():
        verification = read_json(handoff)
        lines += ['## Host Conversion Handoff Verification', '',
                  'The main agent prepared classifier_logits.onnx and 120 calibration files in maixcam-expanded-yolo-20261026.',
                  f'Extracted logits SHA-256: `{verification["logit_onnx_sha256"]}`.',
                  'All 120 files have verified hashes, pixel-exact bilinear resize/center crop, and distinct train-only groups (40 per class).',
                  'No validation, frozen-test or source-holdout group was used for calibration.',
                  f'On three train-only reference tensors, softmax(logits) matches the original probability graph; max absolute difference {verification["logits_softmax_max_abs_difference"]:.10g}.',
                  'The logits graph requires classifier_softmax=True; best.onnx retains Softmax and requires False.',
                  'This verification did not rerun training or heldout inference and did not change model weights.',
                  'The main agent owns the separate WSL conversion process; this check does not execute or deploy the camera.',
                  'Physical deployment/device inference remain unverified because the camera USB/network is unavailable.',
                  'UI checks were static: research snapshots remain unapproved, with a generic feature/archive badge.',
                  'The existing vision screenshot predates this work and is not evidence of the new classifier path.',
                  'Run the host check with --stage verify-handoff. Detailed evidence: handoff_final_verification.json.', '']
        if verification.get('converted_host_file_status') == 'hashes_and_metadata_verified':
            lines += [f'The main agent\'s converted CVIMODEL SHA-256 is `{verification["cvimodel_sha256"]}`.',
                      'The CVIMODEL hash, MUD same-directory model reference, RGB input, normalization and label order passed read-only checks.',
                      'The host deployment log records a successful TPU simulator comparison. This is not physical camera execution.',
                      'The reported 413/621-image metrics apply to the FP32 research model; INT8 heldout accuracy was not evaluated here.',
                      'Run converted-file checks with --stage verify-conversion-files.', '']
    text = '\n'.join(lines)
    (OUTPUT / 'model_card.md').write_text(text, encoding='utf-8')
    (ROOT / 'docs/2026-10-26-vision-expanded-training.md').write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['acquire', 'inventory', 'prepare', 'train', 'finalize', 'verify-handoff', 'verify-conversion-files', 'all'], default='all')
    parser.add_argument('--acquire-ref', default=None)
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    os.environ['YOLO_CONFIG_DIR'] = str(OUTPUT / 'ultralytics_config')
    os.environ['WANDB_MODE'] = 'disabled'
    os.environ['MPLCONFIGDIR'] = str(OUTPUT / 'matplotlib_config')
    with (OUTPUT / 'console.log').open('a', encoding='utf-8') as log:
        with contextlib.redirect_stdout(prior.Tee(sys.stdout, log)), contextlib.redirect_stderr(prior.Tee(sys.stderr, log)):
            try:
                stages = ['acquire', 'inventory', 'prepare', 'train', 'finalize'] if args.stage == 'all' else [args.stage]
                for stage in stages:
                    if stage == 'acquire':
                        acquire(args.acquire_ref)
                    else:
                        globals()[stage.replace('-', '_')]()
            except Exception as error:
                write_json(OUTPUT / f'failure_{args.stage}.json',
                           dict(utc=utc_now(), error=repr(error), traceback=traceback.format_exc()))
                raise


if __name__ == '__main__':
    main()
