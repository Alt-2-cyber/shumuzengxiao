"""Train and evaluate cow-region appearance classification on fixed source splits."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import sys
import time

import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'vision-training-data/expanded-yolo-20261026'
OUTPUT = ROOT / 'vision-training-data/cascade-20261028'
LABELS = ['foot-and-mouth', 'healthy', 'lumpy']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def letterbox(img, width, height):
    scale = min(width / img.width, height / img.height)
    size = (max(1, int(round(img.width * scale))), max(1, int(round(img.height * scale))))
    resized = img.resize(size, Image.Resampling.BILINEAR)
    canvas = Image.new('RGB', (width, height), (114, 114, 114))
    canvas.paste(resized, ((width - size[0]) // 2, (height - size[1]) // 2))
    return canvas


def validate_groups(rows):
    groups = {}
    for row in rows:
        if row['source_label'] not in LABELS or row['split'] not in ('train', 'val', 'test', 'source_holdout'):
            raise ValueError('Unexpected original label or split')
        previous = groups.setdefault(row['group_id'], row['split'])
        if previous != row['split']:
            raise ValueError('An image group crosses fixed splits')


def prepare():
    from ultralytics import YOLO
    if (OUTPUT / 'split.json').exists():
        raise FileExistsError('A prepared ROI split already exists')
    rows = json.loads((SOURCE / 'split.json').read_text(encoding='utf-8'))['images']
    validate_groups(rows)
    detector = YOLO(str(OUTPUT / 'yolov8n.pt'))
    kept, excluded = [], []
    for start in range(0, len(rows), 24):
        batch = rows[start:start + 24]
        frames = []
        for row in batch:
            path = SOURCE / row['prepared_path']
            if sha(path) != row['prepared_sha256']:
                raise ValueError('Original image hash changed: ' + row['id'])
            with Image.open(path) as im:
                frames.append(letterbox(ImageOps.exif_transpose(im).convert('RGB'), 320, 240))
        predictions = detector.predict(frames, imgsz=(224, 320), conf=0.45, iou=0.45,
                                       classes=[19], device=0, batch=24, rect=False, verbose=False)
        for row, frame, detection in zip(batch, frames, predictions):
            boxes = []
            for box in detection.boxes:
                x1, y1, x2, y2 = box.xyxy.cpu().numpy()[0].tolist()
                if x2 - x1 >= 32 and y2 - y1 >= 32:
                    boxes.append((x1, y1, x2, y2, float(box.conf.cpu()[0])))
            # Image-level labels cannot identify the affected cow in a group.
            if len(boxes) != 1:
                excluded.append({'id': row['id'], 'split': row['split'], 'source_label': row['source_label'],
                                 'reason': 'no_qualified_cow' if not boxes else 'multiple_cows_ambiguous_image_label'})
                continue
            x1, y1, x2, y2, confidence = boxes[0]
            pad_x, pad_y = (x2 - x1) * .05, (y2 - y1) * .05
            left, top = max(0, math.floor(x1 - pad_x)), max(0, math.floor(y1 - pad_y))
            right, bottom = min(320, math.ceil(x2 + pad_x)), min(240, math.ceil(y2 + pad_y))
            cropped = letterbox(frame.crop((left, top, right, bottom)), 224, 224)
            prepared = 'dataset/' + row['split'] + '/' + row['source_label'] + '/' + row['id'] + '.png'
            target = OUTPUT / prepared
            target.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(target)
            kept.append({**row, 'original_prepared_path': row['prepared_path'],
                         'original_prepared_sha256': row['prepared_sha256'],
                         'prepared_path': prepared, 'prepared_sha256': sha(target),
                         'cow_bbox': [x1, y1, x2, y2], 'crop': [left, top, right - left, bottom - top],
                         'detector_score': confidence, 'pixel_sha256': hashlib.sha256(cropped.tobytes()).hexdigest()})
        if start % 240 == 0 or start + 24 >= len(rows):
            print('COW_CROPS', min(start + 24, len(rows)), '/', len(rows), 'retained', len(kept), flush=True)
    protected = {r['pixel_sha256'] for r in kept if r['split'] != 'train'}
    retained = []
    for row in kept:
        if row['split'] == 'train' and row['pixel_sha256'] in protected:
            (OUTPUT / row['prepared_path']).unlink()
            excluded.append({'id': row['id'], 'split': row['split'], 'source_label': row['source_label'],
                             'reason': 'roi_pixel_duplicate_of_validation_or_heldout'})
        else:
            retained.append(row)
    validate_groups(retained)
    counts = {split: dict(Counter(r['source_label'] for r in retained if r['split'] == split))
              for split in ('train', 'val', 'test', 'source_holdout')}
    write_json(OUTPUT / 'split.json', {'source_split_sha256': sha(SOURCE / 'split.json'), 'images': retained})
    write_json(OUTPUT / 'excluded.json', excluded)
    report = {'retained_counts': counts, 'original_images': len(rows), 'retained_images': len(retained),
              'excluded_reasons': dict(Counter(r['reason'] for r in excluded)),
              'detector_sha256': sha(OUTPUT / 'yolov8n.pt'),
              'detector_source': 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolov8n.pt',
              'scope': 'Cow-detected public source-label image groups; no animal/farm or clinical reference',
              'geometry': 'RGB 320x240 letterbox, single cow, 5% padding, RGB 224 letterbox with 114 fill',
              'split_groups_preserved': True, 'test_not_used_for_parameter_selection': True}
    write_json(OUTPUT / 'preparation.json', report)
    print(json.dumps(report, indent=2), flush=True)


def train():
    import torch
    from torch.utils.data import WeightedRandomSampler
    from torchvision import transforms
    from torchvision.transforms import InterpolationMode
    from ultralytics import YOLO
    from ultralytics.data.build import InfiniteDataLoader
    from ultralytics.models.yolo.classify.train import ClassificationTrainer
    from sklearn.metrics import f1_score
    if (OUTPUT / 'training_summary.json').exists():
        raise FileExistsError('This candidate has already been trained')
    split = json.loads((OUTPUT / 'split.json').read_text(encoding='utf-8'))
    validate_groups(split['images'])
    # Keep all heldout images outside the directory passed to the optimizer.
    for row in split['images']:
        if row['split'] not in ('train', 'val') and row['prepared_path'].startswith('dataset/'):
            old = OUTPUT / row['prepared_path']
            row['prepared_path'] = 'heldout/' + row['prepared_path'].split('/', 1)[1]
            new = OUTPUT / row['prepared_path']
            new.parent.mkdir(parents=True, exist_ok=True)
            old.rename(new)
    for name in ('test', 'source_holdout'):
        parent = OUTPUT / 'dataset' / name
        if parent.exists():
            for child in parent.iterdir():
                child.rmdir()
            parent.rmdir()
    write_json(OUTPUT / 'split.json', split)
    for row in split['images']:
        if sha(OUTPUT / row['prepared_path']) != row['prepared_sha256']:
            raise ValueError('ROI image hash changed')
    counts = Counter(r['source_label'] for r in split['images'] if r['split'] == 'train')
    if any(counts[label] < 15 for label in LABELS):
        raise ValueError('Insufficient cow-region training examples for one of the original labels')

    class ROITrainer(ClassificationTrainer):
        def build_dataset(self, img_path, mode='train', batch=None):
            dataset = super().build_dataset(img_path, mode, batch)
            operations = []
            if mode == 'train':
                operations = [transforms.RandomHorizontalFlip(.5),
                              transforms.RandomAffine(6, translate=(.03, .03), scale=(.9, 1.05),
                                                      interpolation=InterpolationMode.BILINEAR, fill=114),
                              transforms.ColorJitter(.18, .18, .12, .025),
                              transforms.RandomApply([transforms.GaussianBlur(3, (.1, .6))], p=.1)]
            dataset.torch_transforms = transforms.Compose(operations + [transforms.ToTensor()])
            return dataset

        def get_dataloader(self, dataset_path, batch_size=16, rank=0, mode='train'):
            if mode != 'train':
                return super().get_dataloader(dataset_path, batch_size, rank, mode)
            dataset = self.build_dataset(dataset_path, mode)
            class_counts = Counter(item[1] for item in dataset.samples)
            weights = [1 / math.sqrt(class_counts[item[1]]) for item in dataset.samples]
            generator = torch.Generator().manual_seed(20261028)
            sampler = WeightedRandomSampler(weights, len(weights), replacement=True, generator=generator)
            return InfiniteDataLoader(dataset, batch_size=batch_size, sampler=sampler,
                                      num_workers=0, pin_memory=True)

        def validate(self):
            metrics, _ = super().validate()
            network = self.ema.ema if self.ema else self.model
            network.float().eval()
            targets, predicted = [], []
            with torch.inference_mode():
                for batch in self.test_loader:
                    value = network(batch['img'].to(self.device).float())
                    probability = value[0] if isinstance(value, tuple) else value
                    predicted.extend(probability.argmax(1).cpu().tolist())
                    targets.extend(batch['cls'].tolist())
            score = float(f1_score(targets, predicted, labels=range(3), average='macro', zero_division=0))
            metrics['metrics/macro_f1'] = score
            return metrics, score

    config = dict(data=str(OUTPUT / 'dataset'), epochs=30, patience=7, batch=32,
                  imgsz=224, workers=0, device=0, seed=20261028, deterministic=True,
                  optimizer='AdamW', lr0=.0003, lrf=.05, weight_decay=.0005,
                  warmup_epochs=2, amp=False, cache=False, plots=True, save=True,
                  project=str(OUTPUT / 'runs'), name='roi_candidate', exist_ok=False,
                  auto_augment=None, erasing=0, dropout=.1, verbose=True)
    protocol = {'locked_utc': datetime.now(timezone.utc).isoformat(), 'config': config,
                'source_model_sha256': sha(SOURCE / 'best.pt'), 'split_sha256': sha(OUTPUT / 'split.json'),
                'selection': 'Validation macro-F1 only, one predetermined candidate run',
                'sampling': 'Training-only inverse-square-root class-frequency replacement sampling',
                'geometry': 'Fixed 224 letterbox ROI; no random resized crop',
                'augmentation': 'Flip, bounded affine/color, occasional mild Gaussian blur; not new independent images',
                'scope': 'Public source-label appearance research, not clinical diagnosis'}
    write_json(OUTPUT / 'training_protocol.json', protocol)
    shutil.copyfile(__file__, OUTPUT / 'training_script_at_fit.py')
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    model = YOLO(str(SOURCE / 'best.pt'), task='classify')
    started = time.monotonic()
    model.train(trainer=ROITrainer, **config)
    run = Path(model.trainer.save_dir)
    shutil.copyfile(run / 'weights/best.pt', OUTPUT / 'best.pt')
    shutil.copyfile(run / 'results.csv', OUTPUT / 'training_history.csv')
    write_json(OUTPUT / 'training_summary.json', {'elapsed_seconds': time.monotonic() - started,
               'gpu': torch.cuda.get_device_name(0), 'best_pt_sha256': sha(OUTPUT / 'best.pt'),
               'selection': protocol['selection'], 'test_consulted': False,
               'best_fitness': float(model.trainer.best_fitness)})


def evaluate():
    import onnx
    import onnxruntime as ort
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, classification_report, log_loss
    from ultralytics import YOLO
    if (OUTPUT / 'evaluation.json').exists():
        raise FileExistsError('Fixed evaluation already exists; no test-driven reruns')
    model = YOLO(str(OUTPUT / 'best.pt'), task='classify')
    assert [model.names[i] for i in range(3)] == LABELS
    exported = model.export(format='onnx', imgsz=224, batch=1, dynamic=False,
                            opset=13, simplify=False, half=False, device='cpu')
    onnx.checker.check_model(onnx.load(exported))
    options = ort.SessionOptions(); options.intra_op_num_threads = 4
    candidate = ort.InferenceSession(str(exported), options, providers=['CPUExecutionProvider'])
    baseline = ort.InferenceSession(str(SOURCE / 'best.onnx'), options, providers=['CPUExecutionProvider'])
    rows = json.loads((OUTPUT / 'split.json').read_text(encoding='utf-8'))['images']
    write_json(OUTPUT / 'heldout_lock.json', {'utc': datetime.now(timezone.utc).isoformat(),
                'checkpoint_sha256': sha(OUTPUT / 'best.pt'), 'onnx_sha256': sha(exported),
                'protocol_sha256': sha(OUTPUT / 'training_protocol.json')})
    summary, all_predictions = {}, {}
    for subset in ('val', 'test', 'source_holdout'):
        selected = [r for r in rows if r['split'] == subset]
        actual, old = [], []
        for row in selected:
            with Image.open(OUTPUT / row['prepared_path']) as im:
                array = np.asarray(im.convert('RGB'), dtype=np.float32).transpose(2, 0, 1)[None] / 255
            actual.append(candidate.run(None, {candidate.get_inputs()[0].name: array})[0][0])
            old.append(baseline.run(None, {baseline.get_inputs()[0].name: array})[0][0])
        actual, old = np.asarray(actual), np.asarray(old)
        target = np.array([LABELS.index(r['source_label']) for r in selected])
        result = {}
        for name, values in [('candidate', actual), ('previous_on_same_rois', old)]:
            pred = values.argmax(1)
            result[name] = {'n': len(selected), 'accuracy': float(accuracy_score(target, pred)),
                            'macro_f1': float(f1_score(target, pred, labels=range(3), average='macro', zero_division=0)),
                            'confusion_matrix': confusion_matrix(target, pred, labels=range(3)).tolist(),
                            'classification_report': classification_report(target, pred, labels=range(3),
                                    target_names=LABELS, output_dict=True, zero_division=0)}
        if subset == 'val':
            # Fix rejection thresholds before either heldout split is interpreted.
            choices = []
            ranked = np.sort(actual, axis=1)
            for score in (.7, .75, .8, .85, .9, .95):
                for margin in (.1, .15, .2, .25, .3):
                    accepted = (ranked[:, -1] >= score) & ((ranked[:, -1] - ranked[:, -2]) >= margin)
                    n = int(accepted.sum())
                    precision = float((actual.argmax(1)[accepted] == target[accepted]).mean()) if n else 0
                    if n and precision >= .9:
                        choices.append((n, precision, score, margin))
            choice = max(choices) if choices else (0, 0, .95, .3)
            thresholds = {'minimum_score': choice[2], 'minimum_margin': choice[3],
                          'validation_accepted': choice[0], 'validation_accuracy_among_accepted': choice[1],
                          'selection': 'Validation only; widest coverage at >=90% source-label correctness',
                          'clinical_validation': False}
            write_json(OUTPUT / 'rejection_thresholds.json', thresholds)
            promote = result['candidate']['macro_f1'] >= result['previous_on_same_rois']['macro_f1']
            write_json(OUTPUT / 'selection.json', {'promote_candidate': promote, 'validation': result,
                       'scope': 'Selection uses validation only; heldout scores do not trigger retuning'})
        ranked = np.sort(actual, axis=1)
        accepted = (ranked[:, -1] >= thresholds['minimum_score']) & ((ranked[:, -1] - ranked[:, -2]) >= thresholds['minimum_margin'])
        result['rejection'] = {'accepted': int(accepted.sum()), 'total': len(selected),
                              'accuracy_among_accepted': float((actual.argmax(1)[accepted] == target[accepted]).mean()) if accepted.any() else None}
        summary[subset] = result
        all_predictions[subset] = [{'id': r['id'], 'group_id': r['group_id'], 'source_label': r['source_label'],
                                    'probabilities': p.tolist(), 'accepted': bool(a)} for r, p, a in zip(selected, actual, accepted)]
        print('EVALUATION', subset, json.dumps(result), flush=True)
    write_json(OUTPUT / 'predictions.json', all_predictions)
    write_json(OUTPUT / 'evaluation.json', summary)
    write_json(OUTPUT / 'input_output_contract.json', {'labels': LABELS, 'input_shape': [1,3,224,224],
               'geometry': 'Bilinear letterbox cow ROI, gray114 padding, RGB /255', 'softmax_in_graph': True})
    write_json(OUTPUT / 'completion.json', {'onnx_sha256': sha(exported), 'scope': 'research_only',
               'status': 'trained_and_evaluated_cow_roi_candidate'})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'train', 'evaluate'])
    args = parser.parse_args()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    {'prepare': prepare, 'train': train, 'evaluate': evaluate}[args.stage]()


if __name__ == '__main__':
    main()
