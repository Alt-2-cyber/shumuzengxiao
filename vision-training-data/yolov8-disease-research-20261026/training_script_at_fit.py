#!/usr/bin/env python3
"""Train an auditable source-label image-group heldout YOLOv8n classifier.

Public folder labels are not clinical diagnoses. This script never connects to
devices, registers a production model, or changes the existing cow detector.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import json
import os
import platform
import random
import re
import shutil
import sys
import time
import traceback
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np
from PIL import Image, ImageOps
from scipy.fft import dctn


ROOT = Path(__file__).resolve().parents[1]
LABELS = ['foot-and-mouth', 'healthy', 'lumpy']
SOURCE_RELATIVE = ('\u75be\u75c5\u8bc6\u522b\u751f\u4ea7\u843d\u5730/'
                   '\u5916\u90e8\u89c6\u89c9\u6570\u636e/Kaggle_CattleDiseases_2025')
OUTPUT_RELATIVE = 'vision-training-data/yolov8-disease-research-20261026'
EVALUATION_SCOPE = 'source-label image-group heldout; NOT independent farm disease accuracy'
WEIGHTS_URL = 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n-cls.pt'
DATASET_URL = 'https://www.kaggle.com/datasets/devang03mgr/cattle-diseases-datasets'
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tif', '.tiff'}
SEED = 20261026
PHASH_DISTANCE = 6
DHASH_DISTANCE = 10


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_csv(path, rows):
    if not rows:
        return
    with Path(path).open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def pack_hash(bits):
    return int.from_bytes(np.packbits(bits.flatten()).tobytes(), 'big')


def perceptual_hashes(image):
    gray = image.convert('L')
    resized = np.asarray(gray.resize((32, 32), Image.Resampling.LANCZOS), dtype=np.float64)
    low = dctn(resized, type=2, norm='ortho')[:8, :8]
    phash = pack_hash(low > np.median(low.flatten()[1:]))
    difference = np.asarray(gray.resize((9, 8), Image.Resampling.LANCZOS), dtype=np.int16)
    dhash = pack_hash(difference[:, 1:] > difference[:, :-1])
    return f'{phash:016x}', f'{dhash:016x}'


def roboflow_source_key(path, label):
    name = Path(path).name.lower()
    if '.rf.' not in name:
        return None
    base = name.split('.rf.', 1)[0]
    base = re.sub(r'(?:(?:_|\.)(?:jpe?g|png|webp|bmp))+$', '', base)
    # Numeric names are ambiguous across independently assembled class folders.
    namespace = label if not re.search(r'[a-z]{3}', base) else 'descriptive-global'
    return f'{namespace}:{base}'


def inspect_image(path, source_root):
    relative = Path(path).relative_to(source_root).as_posix()
    label = Path(relative).parts[0]
    record = {
        'id': hashlib.sha256(relative.encode('utf-8')).hexdigest()[:20],
        'relative_path': relative,
        'source_path': str(Path(path).resolve()),
        'source_label': label,
        'label_source': 'public_source_directory_name_only',
        'source_dataset': 'devang03mgr/cattle-diseases-datasets',
        'source_url': DATASET_URL,
        'animal_id': None, 'farm_id': None, 'veterinarian': None,
        'clinical_reference': None, 'clinically_verified': False,
        'file_sha256': sha256(path),
        'roboflow_source_key': roboflow_source_key(path, label),
    }
    try:
        with Image.open(path) as opened:
            image = ImageOps.exif_transpose(opened).convert('RGB')
            image.load()
        width, height = image.size
        digest = hashlib.sha256(f'RGB:{width}x{height}\0'.encode('ascii') + image.tobytes()).hexdigest()
        phash, dhash = perceptual_hashes(image)
        phash_mirror, dhash_mirror = perceptual_hashes(ImageOps.mirror(image))
        record.update(width=width, height=height, pixel_sha256=digest,
                      phash=phash, dhash=dhash, phash_mirror=phash_mirror,
                      dhash_mirror=dhash_mirror, decode_status='ok')
    except Exception as error:
        record.update(decode_status='invalid', decode_error=repr(error))
    return record


def group_records(records):
    valid = [record for record in records if record['decode_status'] == 'ok']
    parent = list(range(len(valid)))
    edges = []

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def join(left, right, reason, **details):
        a, b = find(left), find(right)
        if a != b:
            parent[max(a, b)] = min(a, b)
        edges.append({'left_id': valid[left]['id'], 'right_id': valid[right]['id'],
                      'reason': reason, **details})

    for key, reason in [('file_sha256', 'exact_file_sha256'),
                        ('pixel_sha256', 'exact_rgb_pixel_sha256'),
                        ('roboflow_source_key', 'roboflow_source_name')]:
        first = {}
        for index, record in enumerate(valid):
            value = record.get(key)
            if not value:
                continue
            if value in first:
                join(first[value], index, reason)
            else:
                first[value] = index

    hashes = [(int(r['phash'], 16), int(r['dhash'], 16),
               int(r['phash_mirror'], 16), int(r['dhash_mirror'], 16),
               r['width'] / r['height']) for r in valid]
    for left, (phash, dhash, _, _, aspect) in enumerate(hashes):
        for right in range(left + 1, len(valid)):
            if valid[left]['pixel_sha256'] == valid[right]['pixel_sha256']:
                continue
            other_p, other_d, mirror_p, mirror_d, other_aspect = hashes[right]
            if max(aspect / other_aspect, other_aspect / aspect) > 1.10:
                continue
            for orientation, target_p, target_d in [('original', other_p, other_d),
                                                    ('horizontal_mirror', mirror_p, mirror_d)]:
                pdistance = (phash ^ target_p).bit_count()
                if pdistance > PHASH_DISTANCE:
                    continue
                ddistance = (dhash ^ target_d).bit_count()
                if ddistance <= DHASH_DISTANCE:
                    join(left, right, 'perceptual_near_duplicate',
                         phash_distance=pdistance, dhash_distance=ddistance,
                         orientation=orientation)
                    break

    components = defaultdict(list)
    for index, record in enumerate(valid):
        components[find(index)].append(record)
    groups = []
    for members in components.values():
        member_ids = sorted(record['id'] for record in members)
        group_id = 'g-' + hashlib.sha256('\n'.join(member_ids).encode('ascii')).hexdigest()[:20]
        labels = sorted({record['source_label'] for record in members})
        representative = min(members, key=lambda r: (-r['width'] * r['height'],
                                                     r['file_sha256'], r['relative_path']))
        groups.append({'group_id': group_id, 'members': member_ids, 'labels': labels,
                       'status': 'eligible' if len(labels) == 1 else 'quarantine_cross_class',
                       'representative_id': representative['id'] if len(labels) == 1 else None})
    return sorted(groups, key=lambda g: g['group_id']), edges


def assign_group_splits(groups, seed=SEED):
    assignments = {}
    rng = random.Random(seed)
    for label in LABELS:
        eligible = sorted(g['group_id'] for g in groups
                          if g['status'] == 'eligible' and g['labels'] == [label])
        if len(eligible) < 7:
            raise ValueError(f'Insufficient independent image groups for {label}: {len(eligible)}')
        rng.shuffle(eligible)
        heldout = max(1, round(len(eligible) * 0.15))
        for index, group_id in enumerate(eligible):
            assignments[group_id] = ('test' if index < heldout else
                                     'val' if index < 2 * heldout else 'train')
    return assignments


def prepare_dataset(source_root, output, seed=SEED):
    if (output / 'manifest.jsonl').exists():
        raise FileExistsError('Preparation is immutable; use --stage train or --stage finalize for this prepared run.')
    paths = sorted(path for path in source_root.rglob('*')
                   if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    if len(paths) != 3244:
        raise ValueError(f'Expected the authorized 3244 source images, found {len(paths)}')
    records = []
    for index, path in enumerate(paths, start=1):
        if path.relative_to(source_root).parts[0] not in LABELS:
            raise ValueError(f'Unexpected source class: {path}')
        records.append(inspect_image(path, source_root))
        if index % 250 == 0 or index == len(paths):
            print(f'Inventoried {index}/{len(paths)} images', flush=True)
    groups, edges = group_records(records)
    assignments = assign_group_splits(groups, seed)
    by_id = {record['id']: record for record in records}
    for split in ('train', 'val'):
        for label in LABELS:
            (output / 'dataset' / split / label).mkdir(parents=True, exist_ok=True)
    for label in LABELS:
        (output / 'heldout_test' / label).mkdir(parents=True, exist_ok=True)
    split_rows = []
    for group in groups:
        quarantined = group['status'] == 'quarantine_cross_class'
        split = 'quarantine' if quarantined else assignments[group['group_id']]
        group['split'] = split
        for member_id in group['members']:
            record = by_id[member_id]
            record.update(group_id=group['group_id'], split=split,
                          role='quarantine_cross_class' if quarantined else
                          'representative' if member_id == group['representative_id'] else 'duplicate_excluded')
            if quarantined:
                target = output / 'quarantine' / record['source_label'] / (member_id + Path(record['source_path']).suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(record['source_path'], target)
                record['quarantine_path'] = target.relative_to(output).as_posix()
            elif record['role'] == 'representative':
                parent_dir = output / 'heldout_test' if split == 'test' else output / 'dataset' / split
                target = parent_dir / record['source_label'] / (group['group_id'] + '.png')
                with Image.open(record['source_path']) as opened:
                    ImageOps.exif_transpose(opened).convert('RGB').save(target, compress_level=3)
                record['prepared_path'] = target.relative_to(output).as_posix()
                record['prepared_sha256'] = sha256(target)
                split_rows.append({key: record[key] for key in
                                   ('id', 'group_id', 'source_label', 'split', 'relative_path',
                                    'prepared_path', 'file_sha256', 'pixel_sha256', 'prepared_sha256')})
    for record in records:
        if record['decode_status'] != 'ok':
            record.update(group_id=None, split='quarantine', role='quarantine_invalid_image')
            target = output / 'quarantine' / 'invalid' / (record['id'] + Path(record['source_path']).suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(record['source_path'], target)
            record['quarantine_path'] = target.relative_to(output).as_posix()
    with (output / 'manifest.jsonl').open('w', encoding='utf-8') as stream:
        for record in records:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')
    split_rows.sort(key=lambda row: (row['split'], row['source_label'], row['group_id']))
    write_csv(output / 'split.csv', split_rows)
    write_json(output / 'split.json', {'seed': seed, 'ratios': [0.70, 0.15, 0.15],
               'unit': 'connected_image_group_one_representative', 'scope': EVALUATION_SCOPE,
               'test_hidden_from_trainer': True, 'assignments': assignments, 'images': split_rows})
    write_json(output / 'groups.json', groups)
    write_json(output / 'duplicate_edges.json', edges)
    report = {
        'created_utc': utc_now(), 'source_images': len(records),
        'source_class_counts': dict(Counter(r['source_label'] for r in records)),
        'valid_images': sum(r['decode_status'] == 'ok' for r in records),
        'invalid_images': sum(r['decode_status'] != 'ok' for r in records),
        'connected_groups': len(groups),
        'eligible_groups': sum(g['status'] == 'eligible' for g in groups),
        'quarantine_cross_class_groups': sum(g['status'] == 'quarantine_cross_class' for g in groups),
        'quarantine_cross_class_images': sum(r['role'] == 'quarantine_cross_class' for r in records),
        'duplicate_images_excluded': sum(r['role'] == 'duplicate_excluded' for r in records),
        'duplicate_edge_counts': dict(Counter(edge['reason'] for edge in edges)),
        'split_class_counts': {split: dict(Counter(row['source_label'] for row in split_rows
                                                 if row['split'] == split))
                               for split in ('train', 'val', 'test')},
        'split_counts': dict(Counter(row['split'] for row in split_rows)),
        'largest_groups': sorted([{'group_id': g['group_id'], 'images': len(g['members']),
                                  'labels': g['labels'], 'status': g['status']} for g in groups],
                                 key=lambda g: -g['images'])[:20],
        'algorithm': {
            'file_hash': 'SHA256 of source bytes',
            'pixel_hash': 'SHA256 of RGB:WIDTHxHEIGHT + NUL + EXIF-transposed decoded RGB bytes',
            'near_duplicate': '64-bit DCT pHash <=6 AND 64-bit dHash <=10; aspect ratio within 10%; original or horizontal mirror',
            'rf_names': 'strip .rf.* and trailing _jpg/_png/etc; descriptive names global, ambiguous numeric names class-namespaced',
            'components': 'transitive union of exact, pixel, filename and perceptual edges',
            'representative': 'largest decoded pixel area; ties by file SHA256 then source path',
            'quarantine': 'all members of any mixed-source-label component; original raw files left untouched',
            'limits': 'heuristic image grouping cannot infer animal/farm identity or catch every crop, rotation or montage',
        },
    }
    write_json(output / 'deduplication_report.json', report)
    for card in [ROOT / SOURCE_RELATIVE / 'DATASET_CARD.md',
                 ROOT / '\u75be\u75c5\u8bc6\u522b\u751f\u4ea7\u843d\u5730/\u7814\u7a76\u6a21\u578b/cattle-disease-multiclass-baseline/model_card.md']:
        shutil.copyfile(card, output / ('source_' + card.name))
    zip_path = ROOT / '\u75be\u75c5\u8bc6\u522b\u751f\u4ea7\u843d\u5730/\u5916\u90e8\u89c6\u89c9\u6570\u636e/cattle-diseases-datasets.zip'
    write_json(output / 'source_provenance.json', {
        'dataset_url': DATASET_URL, 'source_root': str(source_root),
        'label_origin': 'public folder names; no clinical or animal identity verification',
        'license_reported_by_existing_card': 'Database: Open Database, Contents: Database Contents',
        'license_scope': 'recorded from local source card; not independently audited per-image rights',
        'archive_path': str(zip_path), 'archive_sha256': sha256(zip_path),
        'source_card_sha256': sha256(ROOT / SOURCE_RELATIVE / 'DATASET_CARD.md'),
    })
    print(json.dumps(report, indent=2), flush=True)
    return report


def load_records(output):
    return [json.loads(line) for line in (output / 'manifest.jsonl').read_text(encoding='utf-8').splitlines()]


def verify_prepared_data(output, check_source=False):
    records = load_records(output)
    splits = read_json(output / 'split.json')
    by_group = defaultdict(set)
    for record in records:
        if check_source and sha256(record['source_path']) != record['file_sha256']:
            raise ValueError(f'Source file changed: {record["relative_path"]}')
        if record['role'] == 'representative':
            path = output / record['prepared_path']
            if sha256(path) != record['prepared_sha256']:
                raise ValueError(f'Prepared image changed: {path}')
            by_group[record['group_id']].add(record['split'])
        elif record['role'].startswith('quarantine'):
            if sha256(output / record['quarantine_path']) != record['file_sha256']:
                raise ValueError('Quarantine copy changed')
    assert all(len(parts) == 1 for parts in by_group.values())
    assert set(by_group) == set(splits['assignments'])
    assert not (output / 'dataset' / 'test').exists()
    assert len(splits['images']) == len(by_group)
    by_id = {record['id']: record for record in records}
    edges = read_json(output / 'duplicate_edges.json')
    for edge in edges:
        assert by_id[edge['left_id']]['group_id'] == by_id[edge['right_id']]['group_id']
    for key in ('file_sha256', 'pixel_sha256', 'roboflow_source_key'):
        hash_splits = defaultdict(set)
        for record in records:
            if record.get(key) and record['split'] != 'quarantine':
                hash_splits[record[key]].add(record['split'])
        assert all(len(parts) == 1 for parts in hash_splits.values()), f'{key} crossed splits'
    return {'passed': True, 'source_files_verified': len(records) if check_source else 0,
            'prepared_images_verified': len(by_group), 'group_split_overlap': 0,
            'file_pixel_name_split_overlap': 0, 'duplicate_edges_verified': len(edges),
            'near_duplicate_edge_split_overlap': 0, 'test_visible_to_trainer': False}


def download_pretrained(output):
    import requests
    path = output / 'pretrained' / 'yolov8n-cls.pt'
    receipt = output / 'pretrained' / 'source.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        provenance = read_json(receipt)
        if sha256(path) != provenance['sha256'] or provenance['requested_url'] != WEIGHTS_URL:
            raise ValueError('Existing pretrained weights do not match their receipt')
        return path
    print(f'Downloading official pretrained weights: {WEIGHTS_URL}', flush=True)
    with requests.get(WEIGHTS_URL, stream=True, timeout=(30, 180)) as response:
        response.raise_for_status()
        with path.with_suffix('.part').open('wb') as stream:
            for chunk in response.iter_content(1024 * 1024):
                stream.write(chunk)
        path.with_suffix('.part').replace(path)
        final = urlsplit(response.url)
        provenance = {'requested_url': WEIGHTS_URL, 'official_repository': 'ultralytics/assets',
                      'release': 'v8.3.0', 'retrieved_utc': utc_now(),
                      'final_host': final.netloc, 'final_path': final.path,
                      'http_status': response.status_code, 'etag': response.headers.get('ETag'),
                      'content_length': response.headers.get('Content-Length'),
                      'bytes': path.stat().st_size, 'sha256': sha256(path),
                      'hash_scope': 'locally observed downloaded bytes; not an independently signed attestation'}
        write_json(receipt, provenance)
    return path


def train(output, epochs=30, batch=16, workers=0, patience=8):
    import torch
    from ultralytics import YOLO
    if (output / 'training_summary.json').exists():
        raise FileExistsError('Training already completed; use --stage finalize')
    if not torch.cuda.is_available():
        raise RuntimeError('This authorized experiment requires CUDA, not a silent CPU fallback')
    verified = verify_prepared_data(output)
    write_csv(output / 'quarantine_records.csv', [
        {key: record.get(key) for key in ('id', 'group_id', 'source_label', 'relative_path',
                                         'quarantine_path', 'file_sha256', 'pixel_sha256', 'role')}
        for record in load_records(output) if record['role'].startswith('quarantine')])
    pretrained = download_pretrained(output)
    config = {
        'data': str((output / 'dataset').resolve()), 'epochs': epochs, 'patience': patience,
        'batch': batch, 'imgsz': 224, 'workers': workers, 'device': 0,
        'seed': SEED, 'deterministic': True, 'optimizer': 'AdamW',
        'lr0': 0.001, 'lrf': 0.01, 'weight_decay': 0.0005, 'warmup_epochs': 3,
        'amp': False, 'cache': False, 'plots': True, 'save': True,
        'project': str(output / 'runs'), 'name': 'train', 'exist_ok': False,
        'auto_augment': None, 'erasing': 0.0, 'scale': 0.3,
        'hsv_h': 0.015, 'hsv_s': 0.3, 'hsv_v': 0.2, 'fliplr': 0.5,
        'flipud': 0.0, 'dropout': 0.1, 'verbose': True,
    }
    write_json(output / 'training_protocol.json', {
        'locked_before_training_utc': utc_now(), 'config': config,
        'scope': EVALUATION_SCOPE, 'data_verification': verified,
        'split_sha256': sha256(output / 'split.json'),
        'manifest_sha256': sha256(output / 'manifest.jsonl'),
        'script_sha256_at_train': sha256(Path(__file__)),
        'pretrained_sha256': sha256(pretrained),
        'selection': 'single run; validation top1 checkpoint; test never loaded by trainer',
        'native_fitness': '(top1 + top5) / 2; top5 is always 1 for three classes, so ranking equals top1',
        'amp_note': 'FP32 selected in advance to avoid auxiliary AMP-check detector downloads and simplify ONNX parity',
    })
    torch.set_num_threads(4)
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    model = YOLO(str(pretrained), task='classify')
    checkpoint_events = []

    def record_checkpoint(trainer):
        if trainer.best_fitness == trainer.fitness:
            checkpoint_events.append({'epoch_1based': trainer.epoch + 1,
                                      'fitness': float(trainer.fitness),
                                      'validation_top1': float(trainer.metrics['metrics/accuracy_top1'])})
            write_json(output / 'best_checkpoint_events.json', checkpoint_events)

    model.add_callback('on_model_save', record_checkpoint)
    model.train(**config)
    elapsed = time.perf_counter() - start
    run_dir = Path(model.trainer.save_dir)
    best = run_dir / 'weights' / 'best.pt'
    shutil.copyfile(best, output / 'best.pt')
    shutil.copyfile(run_dir / 'results.csv', output / 'training_history.csv')
    with (output / 'training_history.csv').open(encoding='utf-8-sig', newline='') as stream:
        history = [{key.strip(): value.strip() for key, value in row.items()} for row in csv.DictReader(stream)]
    best_row = max(history, key=lambda row: float(row['metrics/accuracy_top1']))
    summary = {
        'completed_utc': utc_now(), 'elapsed_seconds': elapsed,
        'epochs_completed': len(history), 'epochs_requested': epochs, 'patience': patience,
        'selection_metric': 'validation accuracy_top1',
        'maximum_validation_top1': float(best_row['metrics/accuracy_top1']),
        'first_epoch_with_maximum_validation_top1': int(float(best_row['epoch'])),
        'selected_checkpoint_epoch': checkpoint_events[-1]['epoch_1based'],
        'best_checkpoint_sha256': sha256(output / 'best.pt'),
        'peak_cuda_memory_allocated_bytes': torch.cuda.max_memory_allocated(),
        'run_directory': str(run_dir), 'gpu': torch.cuda.get_device_name(0),
        'train_images': read_json(output / 'deduplication_report.json')['split_counts']['train'],
    }
    write_json(output / 'training_summary.json', summary)
    write_json(output / 'heldout_lock.json', {
        'locked_utc': utc_now(), 'checkpoint_sha256': summary['best_checkpoint_sha256'],
        'split_sha256': sha256(output / 'split.json'), 'protocol_sha256': sha256(output / 'training_protocol.json'),
        'statement': 'Checkpoint fixed before first heldout inference; no test-based hyperparameter selection',
    })
    print(json.dumps(summary, indent=2), flush=True)


def plot_confusion(matrix, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axis = plt.subplots(figsize=(7.8, 6.2), constrained_layout=True)
    axis.imshow(matrix, cmap='Blues')
    axis.set(xticks=range(3), yticks=range(3), xticklabels=LABELS,
             yticklabels=LABELS, xlabel='Predicted source label', ylabel='Source directory label',
             title='Source-label image-group heldout (one image per group)')
    for row in range(3):
        for col in range(3):
            axis.text(col, row, str(matrix[row][col]), ha='center', va='center',
                      color='white' if matrix[row][col] > np.max(matrix) / 2 else 'black')
    figure.savefig(output / 'heldout_confusion_matrix.png', dpi=180)
    plt.close(figure)


def freeze_environment(output):
    packages = sorted((distribution.metadata['Name'], distribution.version)
                      for distribution in importlib.metadata.distributions())
    write_json(output / 'environment.json', {
        'python': sys.version, 'executable': sys.executable,
        'platform': platform.platform(), 'packages': dict(packages), 'recorded_utc': utc_now(),
    })


def finalize(output):
    import onnx
    import onnxruntime as ort
    import torch
    from sklearn.metrics import (accuracy_score, balanced_accuracy_score, classification_report,
                                 confusion_matrix, f1_score, log_loss)
    from ultralytics import YOLO
    from ultralytics.data.augment import classify_transforms

    lock = read_json(output / 'heldout_lock.json')
    if lock['checkpoint_sha256'] != sha256(output / 'best.pt'):
        raise ValueError('Best checkpoint changed after heldout lock')
    if lock['split_sha256'] != sha256(output / 'split.json'):
        raise ValueError('Split changed after heldout lock')
    verification = verify_prepared_data(output, check_source=True)
    torch.set_num_threads(4)
    model = YOLO(str(output / 'best.pt'), task='classify')
    names = [model.names[index] for index in range(3)]
    assert names == LABELS, (names, LABELS)
    exported = model.export(format='onnx', imgsz=224, batch=1, dynamic=False,
                            opset=13, simplify=False, half=False, device='cpu')
    exported = Path(exported)
    graph = onnx.load(str(exported))
    onnx.checker.check_model(graph)
    session = ort.InferenceSession(str(exported), providers=['CPUExecutionProvider'])
    input_info, output_info = session.get_inputs()[0], session.get_outputs()[0]
    assert input_info.shape == [1, 3, 224, 224], input_info.shape
    assert output_info.shape == [1, 3], output_info.shape
    assert input_info.type == 'tensor(float)'
    assert any(node.op_type == 'Softmax' for node in graph.graph.node)
    transform = classify_transforms(size=224)
    model = YOLO(str(output / 'best.pt'), task='classify')
    network = model.model.float().to('cuda:0').eval()
    records = [record for record in load_records(output)
               if record['role'] == 'representative' and record['split'] == 'test']
    records.sort(key=lambda record: (record['source_label'], record['group_id']))
    rows, true, probabilities, ort_probabilities, differences = [], [], [], [], []
    preprocess_samples = []
    prediction_started = utc_now()
    for index, record in enumerate(records):
        with Image.open(output / record['prepared_path']) as opened:
            image = opened.convert('RGB')
        tensor = transform(image).unsqueeze(0).float()
        with torch.inference_mode():
            torch_result = network(tensor.to('cuda:0'))
            pytorch_probability = torch_result[0].cpu().numpy()[0]
            logits = torch_result[1].cpu().numpy()[0]
        ort_probability = session.run(None, {input_info.name: tensor.numpy()})[0][0]
        np.testing.assert_allclose(ort_probability, pytorch_probability, rtol=1e-4, atol=1e-5)
        assert np.isfinite(ort_probability).all()
        assert abs(float(ort_probability.sum()) - 1) < 1e-5
        difference = float(np.max(np.abs(ort_probability - pytorch_probability)))
        differences.append(difference)
        target = LABELS.index(record['source_label'])
        prediction = int(pytorch_probability.argmax())
        true.append(target)
        probabilities.append(pytorch_probability)
        ort_probabilities.append(ort_probability)
        rows.append({
            'id': record['id'], 'group_id': record['group_id'], 'source_path': record['source_path'],
            'prepared_path': record['prepared_path'], 'source_label': record['source_label'],
            'predicted_source_label': LABELS[prediction], 'correct': prediction == target,
            'confidence': float(pytorch_probability[prediction]),
            **{f'pytorch_probability_{label}': float(pytorch_probability[i]) for i, label in enumerate(LABELS)},
            **{f'onnx_probability_{label}': float(ort_probability[i]) for i, label in enumerate(LABELS)},
            **{f'pytorch_logit_{label}': float(logits[i]) for i, label in enumerate(LABELS)},
            'max_abs_pt_onnx_difference': difference,
        })
        if index < 3:
            preprocess_samples.append(tensor.numpy())
        if (index + 1) % 50 == 0 or index + 1 == len(records):
            print(f'Heldout inference and ONNX parity {index + 1}/{len(records)}', flush=True)
    probabilities = np.asarray(probabilities)
    ort_probabilities = np.asarray(ort_probabilities)
    predicted = probabilities.argmax(axis=1)
    matrix = confusion_matrix(true, predicted, labels=range(3))
    report = classification_report(true, predicted, labels=range(3), target_names=LABELS,
                                    output_dict=True, zero_division=0)
    correct = int(np.sum(np.asarray(true) == predicted))
    count = len(true)
    proportion = correct / count
    z = 1.959963984540054
    center = (proportion + z * z / (2 * count)) / (1 + z * z / count)
    radius = z * np.sqrt(proportion * (1 - proportion) / count + z * z / (4 * count * count)) / (1 + z * z / count)
    metrics = {
        'scope': EVALUATION_SCOPE, 'unit': 'one deterministic representative per deduplicated image group',
        'heldout_prediction_started_utc': prediction_started,
        'checkpoint_frozen_utc': lock['locked_utc'], 'test_used_for_selection': False,
        'n_images': count, 'n_image_groups': count, 'correct': correct,
        'accuracy': float(accuracy_score(true, predicted)),
        'balanced_accuracy': float(balanced_accuracy_score(true, predicted)),
        'macro_f1': float(f1_score(true, predicted, average='macro')),
        'weighted_f1': float(f1_score(true, predicted, average='weighted')),
        'log_loss': float(log_loss(true, probabilities, labels=range(3))),
        'accuracy_wilson95': [float(center - radius), float(center + radius)],
        'interval_limit': 'image-group binomial approximation; not animal/farm-clustered uncertainty',
        'classification_report': report, 'label_order': LABELS,
        'confusion_matrix_rows_true_columns_predicted': matrix.tolist(),
        'onnx_accuracy': float(accuracy_score(true, ort_probabilities.argmax(axis=1))),
    }
    parity = {
        'passed': True, 'pytorch_device': 'cuda:0', 'onnx_provider': session.get_providers(),
        'tested_images': count, 'input_shape': input_info.shape, 'output_shape': output_info.shape,
        'input_dtype': input_info.type, 'output_semantics': 'softmax probabilities, not logits',
        'maximum_absolute_difference': max(differences),
        'mean_per_image_maximum_difference': float(np.mean(differences)),
        'argmax_agreement': float(np.mean(predicted == ort_probabilities.argmax(axis=1))),
        'rtol': 1e-4, 'atol': 1e-5, 'onnx_checker_passed': True,
        'static_batch_1': True, 'opset': 13,
    }
    write_json(output / 'heldout_metrics.json', metrics)
    write_json(output / 'onnx_parity.json', parity)
    write_json(output / 'data_integrity_verification.json', verification)
    write_csv(output / 'heldout_predictions.csv', rows)
    write_csv(output / 'heldout_confusion_matrix.csv', [
        {'true_source_label': label, **{name: int(matrix[i, j]) for j, name in enumerate(LABELS)}}
        for i, label in enumerate(LABELS)])
    plot_confusion(matrix, output)
    contract = {
        'input_name': input_info.name, 'input_shape': [1, 3, 224, 224],
        'input_dtype': 'float32', 'color_order': 'RGB', 'layout': 'NCHW',
        'pixel_formula': '(raw_rgb_uint8 - mean) * scale',
        'mean': [0.0, 0.0, 0.0], 'scale': [1 / 255, 1 / 255, 1 / 255],
        'torchvision_mean': [0.0, 0.0, 0.0], 'torchvision_std': [1.0, 1.0, 1.0],
        'geometry': 'EXIF transpose; bilinear resize shorter edge to 224 preserving aspect ratio; center crop 224x224',
        'pillow_torchvision_transform': str(transform),
        'output_name': output_info.name, 'output_shape': [1, 3],
        'labels': LABELS, 'output': 'softmax probabilities',
        'softmax_in_graph': True, 'apply_softmax_again': False,
        'pytorch_eval_return': '(softmax_probabilities, pre_softmax_logits)',
        'maixcam_classifier_handoff': {
            'model_type': 'classifier', 'input_type': 'rgb',
            'mean': [0.0, 0.0, 0.0], 'scale': [1 / 255, 1 / 255, 1 / 255],
            'labels': LABELS,
            'conversion_status': 'ONNX handoff only; no cvimodel/mud conversion or deployment performed',
            'requirements': 'Implement identical resize/center-crop; avoid double /255 or double softmax; verify converted outputs and nn.Classifier behavior on-device before any use',
            'warning': 'Classifier ranks public image source labels; scores are not calibrated disease probabilities',
        },
    }
    write_json(output / 'input_output_contract.json', contract)
    (output / 'labels.txt').write_text('\n'.join(LABELS) + '\n', encoding='utf-8')
    np.save(output / 'reference_inputs_nchw_float32.npy', np.concatenate(preprocess_samples, axis=0))
    write_json(output / 'reference_input_records.json', rows[:3])
    freeze_environment(output)
    shutil.copyfile(Path(__file__), output / 'training_script_snapshot.py')
    generate_documents(output, metrics, parity, contract)
    write_hashes(output)
    write_json(output / 'completion.json', {
        'completed_utc': utc_now(), 'status': 'research_only_completed',
        'scope': EVALUATION_SCOPE, 'best_pt_sha256': sha256(output / 'best.pt'),
        'onnx_sha256': sha256(exported), 'metrics': metrics,
        'pt_onnx_parity': parity, 'hardware_deployment': False,
    })
    write_hashes(output)
    print(json.dumps({'metrics': metrics, 'parity': parity}, indent=2), flush=True)


def generate_documents(output, metrics, parity, contract):
    data = read_json(output / 'deduplication_report.json')
    training = read_json(output / 'training_summary.json')
    source = read_json(output / 'pretrained/source.json')
    split_lines = '\n'.join(
        f'| {split} | ' + ' | '.join(str(data['split_class_counts'][split].get(label, 0)) for label in LABELS)
        + f" | {data['split_counts'][split]} |" for split in ('train', 'val', 'test'))
    class_lines = '\n'.join(
        f"| {label} | {metrics['classification_report'][label]['precision']:.6f} | "
        f"{metrics['classification_report'][label]['recall']:.6f} | "
        f"{metrics['classification_report'][label]['f1-score']:.6f} | "
        f"{int(metrics['classification_report'][label]['support'])} |" for label in LABELS)
    matrix_text = '\n'.join(' '.join(f'{value:4d}' for value in row)
                            for row in metrics['confusion_matrix_rows_true_columns_predicted'])
    text = f'''# YOLOv8n-cls source-label image-group heldout research

Completed UTC: {utc_now()}. Status: `research_only`.

This is **source-label image-group heldout**, not independent farm disease
accuracy, external clinical validation, or a veterinary diagnostic model.
The three outputs rank appearance associated with public source-directory
labels, including `foot-and-mouth`; that label is not proof of FMD. Scores
are not calibrated clinical disease probabilities. No animal ID, farm ID,
veterinarian, laboratory result, or clinical reference standard was supplied.

## Existing Project Restrictions

Read the local source dataset card, both existing vision baseline model cards,
the model release manual, the hardware integration plan, and MaixCAM README.
The existing deployed YOLO model is a COCO cow detector. Its cow detections
cannot establish lesions, behavior, or diseases. Existing baseline metrics
were image-level source-label results and cannot establish independent farm
accuracy. This classifier is a separate research artifact. No hardware or
backend files were edited, no serial port was opened, and no MaixCAM files
were converted, installed, or registered for production by this script.

## Source and Deduplication

- Source: {DATASET_URL}
- Local source: `{ROOT / SOURCE_RELATIVE / 'raw/Cows datasets'}`.
- Original images: {data['source_images']}; counts: `{data['source_class_counts']}`.
- Decodable images: {data['valid_images']}; invalid images: {data['invalid_images']}.
- Connected image groups: {data['connected_groups']}; eligible groups: {data['eligible_groups']}.
- Cross-class groups quarantined: {data['quarantine_cross_class_groups']}, containing
  {data['quarantine_cross_class_images']} source images. Entire components were copied
  to `quarantine/` and excluded. Raw source files were not modified.
- Same-class redundant variants excluded: {data['duplicate_images_excluded']}.

Every file has SHA-256 of original bytes and EXIF-transposed decoded RGB pixels
(with width/height header), plus 64-bit DCT pHash and dHash for original and
mirrored images. Connected components merge exact file/pixel matches,
Roboflow names stripped of `.rf.*` and `_jpg`/`_png` variants, and near matches
with pHash Hamming distance <=6 AND dHash <=10, aspect ratio within 10%.
Descriptive Roboflow names are global; ambiguous numeric stems are namespaced
by source folder because numeric equality alone does not establish provenance.
Content matching remains global across all labels. Every mixed-label component
is quarantined. Edge reasons and members are recorded in `duplicate_edges.json`
and `groups.json`; no clinical relabeling was attempted.

One representative per eligible component is chosen by largest pixel area,
then file SHA-256 and path. All other members remain inventoried but are
excluded from model inputs. The heuristic cannot detect all crops, rotations,
montages, or repeated views of the same animal; it is not animal/farm grouping.

## Fixed Group Split

Seed {SEED}; stratified at group level, approximately 70/15/15. Split assignment
was frozen before training. Test representatives are in `heldout_test/`, outside
the `dataset/` root read by Ultralytics. Test was not used for early stopping,
hyperparameter selection, threshold selection, or checkpoint selection.

| Split | foot-and-mouth | healthy | lumpy | Total |
|---|---:|---:|---:|---:|
{split_lines}

All retained inputs are EXIF-corrected, lossless RGB PNGs. `manifest.jsonl`
preserves every original source path, label origin, hashes, group, split and
role. `split.csv`/`split.json` enumerate the representative inputs. Final
integrity checks rehashed all original files, materialized inputs and
quarantine copies and confirmed no exact/pixel/source-name group overlap.

## Actual Training

- Architecture: official pretrained YOLOv8n-cls, adapted to three classes.
- Weights: {source['requested_url']}
- Downloaded weight SHA-256: `{source['sha256']}`.
- GPU: {training['gpu']}.
- Input 224, batch 16, workers 0, FP32, AdamW lr0=0.001/lrf=0.01,
  weight decay 0.0005, warmup 3, dropout 0.1.
- 30 epoch cap, patience 8; actual epochs: {training['epochs_completed']}.
- Wall training time: {training['elapsed_seconds']:.2f} seconds.
- Peak allocated CUDA memory: {training['peak_cuda_memory_allocated_bytes'] / (1024 ** 3):.3f} GiB.
- Maximum validation top-1: {training['maximum_validation_top1']:.6f}, first reached
  at epoch {training['first_epoch_with_maximum_validation_top1']} (CSV is 1-based).
- Selected checkpoint epoch: {training['selected_checkpoint_epoch']}; equal-fitness
  checkpoints use the trainer's latest tie. Native fitness is (top1+top5)/2;
  top5=1 for three classes, so its ranking equals validation top1.
- Selection: a single prespecified run, validation top-1 fitness only. Best
  checkpoint copied to `best.pt` and SHA-locked before heldout inference.
- Augmentation: random resized crop with area range [0.7,1.0] (scale=0.3 argument), horizontal
  flip 0.5, HSV h/s/v=0.015/0.3/0.2; no auto augment or erasing.

Full arguments, epoch history, environment/package versions, and timing are
in `training_protocol.json`, `training_history.csv`, `environment.json`, and
`training_summary.json`. A reproducible script snapshot is included.

## Heldout Results

Each evaluated image is the single representative of a distinct heldout image
group. There are {metrics['n_images']} images/groups and {metrics['correct']} correct source-label
predictions. Accuracy: **{metrics['accuracy']:.6f}**; balanced accuracy:
**{metrics['balanced_accuracy']:.6f}**; macro-F1: **{metrics['macro_f1']:.6f}**;
weighted-F1: {metrics['weighted_f1']:.6f}; log loss: {metrics['log_loss']:.6f}.
Accuracy Wilson 95% interval: [{metrics['accuracy_wilson95'][0]:.6f},
{metrics['accuracy_wilson95'][1]:.6f}], an image-group binomial approximation,
not uncertainty across independent farms or animals.

| Public source label | Precision | Recall | F1 | Groups/images |
|---|---:|---:|---:|---:|
{class_lines}

Confusion matrix: rows are source labels and columns predicted labels, both
in order `foot-and-mouth`, `healthy`, `lumpy`.

```text
{matrix_text}
```

`heldout_predictions.csv` includes source/group paths, all PyTorch logits,
PyTorch/ONNX probabilities, correctness, and per-image numerical differences.
Confusion matrices are supplied as CSV and PNG. No test-driven retraining or
claim of independent external validation was performed.

## ONNX and MaixCAM Handoff

`best.onnx` is float32, opset 13, fixed batch 1, static input `[1,3,224,224]`
and output `[1,3]`; ONNX checker and ONNX Runtime CPU execution passed.
All {parity['tested_images']} heldout inputs were compared with PyTorch CUDA:
maximum absolute probability difference {parity['maximum_absolute_difference']:.10g},
argmax agreement {parity['argmax_agreement']:.6f}; tolerance atol=1e-5, rtol=1e-4.

The later `nn.Classifier` conversion needs this contract:

- RGB, NCHW, 224x224, float32. EXIF transpose, bilinear resize shorter edge to
  224 while preserving aspect ratio, then center crop 224x224. Directly
  stretching a non-square image is not the evaluated preprocessing.
- For raw RGB 0..255, `mean=[0,0,0]`,
  `scale=[0.00392156862745098,0.00392156862745098,0.00392156862745098]`.
  Formula: `(pixel - mean) * scale`. Do not divide by 255 twice. Torchvision
  mean/std after ToTensor are `[0,0,0]` and `[1,1,1]`.
- Labels in exact index order: `0=foot-and-mouth`, `1=healthy`, `2=lumpy`.
- Exported ONNX output is **softmax probabilities**, with Softmax already in
  the graph. Do not apply softmax again. Native PyTorch evaluation returns
  `(probabilities, logits)`; training consumes logits. A converter that removes
  Softmax would need to declare a different output contract and revalidate it.
- `input_output_contract.json`, `labels.txt`, and three float32 reference
  tensors (`reference_inputs_nchw_float32.npy`) accompany per-image reference
  logits/probabilities. Feed each reference tensor individually for batch 1.
- The main agent must convert with the correct MaixCAM toolchain, preserve
  geometry/normalization, and verify `nn.Classifier` decoding and converted
  numeric outputs. No `.mud`/`.cvimodel` or hardware execution is claimed here.

## Limitations and Reproduction

Source-label bias can include breed, background, image framing, web source,
watermarks and augmentation style. Healthy folder membership does not prove
clinical health. Image grouping reduces known duplication leakage but does
not establish animal, farm or date independence. Pretrained data overlap is
unknown. There are no clinical calibration, prospective, multi-farm, lesion
localization or diagnostic performance claims. Full images were used; this
run did not train or evaluate cow-detector crops or a cascade.

Original source data rights are reported by the existing card as
`Database: Open Database, Contents: Database Contents`; individual image
rights were not independently audited. Ultralytics code/weights licensing
must be reviewed before redistribution or commercial use.

```powershell
& .\\.run\\cattle-ml-venv\\Scripts\\python.exe scripts/train_vision_yolo_research_20261026.py --stage all
```

Preparation is immutable and will refuse an existing manifest. To inspect
or regenerate export/metrics from the frozen run, use `--stage finalize`.
`SHA256SUMS.txt` and `artifact_hashes.json` cover the run artifacts (excluding
the hashes index itself and the actively written console log). The Python
script does not access a serial port, SSH, camera, backend, or deployment API.
'''
    (output / 'model_card.md').write_text(text, encoding='utf-8')
    (ROOT / 'docs/2026-10-26-vision-yolo-training.md').write_text(text, encoding='utf-8')


def write_hashes(output):
    excluded = {'SHA256SUMS.txt', 'artifact_hashes.json', 'console.log'}
    values = {path.relative_to(output).as_posix(): sha256(path)
              for path in sorted(output.rglob('*'))
              if path.is_file() and path.name not in excluded}
    write_json(output / 'artifact_hashes.json', values)
    (output / 'SHA256SUMS.txt').write_text(
        '\n'.join(f'{digest}  {path}' for path, digest in values.items()) + '\n', encoding='utf-8')


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, value):
        for stream in self.streams:
            stream.write(value)
            stream.flush()
        return len(value)

    def flush(self):
        for stream in self.streams:
            stream.flush()

    def isatty(self):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['all', 'prepare', 'train', 'finalize'], default='all')
    parser.add_argument('--source', type=Path, default=ROOT / SOURCE_RELATIVE / 'raw/Cows datasets')
    parser.add_argument('--output', type=Path, default=ROOT / OUTPUT_RELATIVE)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    # Keep optional integrations and any new Ultralytics settings inside this run.
    os.environ['YOLO_CONFIG_DIR'] = str(output / 'ultralytics_config')
    os.environ['WANDB_MODE'] = 'disabled'
    os.environ['MPLCONFIGDIR'] = str(output / 'matplotlib_config')
    with (output / 'console.log').open('a', encoding='utf-8') as log:
        with contextlib.redirect_stdout(Tee(sys.stdout, log)), contextlib.redirect_stderr(Tee(sys.stderr, log)):
            print(f'Run stage={args.stage}; started={utc_now()}; scope={EVALUATION_SCOPE}', flush=True)
            try:
                if args.stage in {'all', 'prepare'}:
                    prepare_dataset(args.source.resolve(), output)
                if args.stage in {'all', 'train'}:
                    train(output)
                if args.stage in {'all', 'finalize'}:
                    finalize(output)
            except Exception as error:
                write_json(output / 'failure.json', {'utc': utc_now(), 'stage': args.stage,
                           'error': repr(error), 'traceback': traceback.format_exc()})
                raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
