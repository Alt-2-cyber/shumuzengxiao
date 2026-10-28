"""Prepare training-only calibration and a logit ONNX for the MaixCAM NPU."""

import argparse
import hashlib
import json
import random
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from PIL import Image, ImageOps
from torchvision import transforms
from torchvision.transforms import InterpolationMode

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'vision-training-data/yolov8-disease-research-20261026'
OUTPUT = ROOT / 'vision-training-data/maixcam-yolov8-disease-20261026'


def main():
    global SOURCE, OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    SOURCE, OUTPUT = args.source.resolve(), args.output.resolve()
    if (OUTPUT / 'conversion_inputs.json').exists():
        raise FileExistsError('Conversion inputs already exist; choose a new --output directory')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    completion = json.loads((SOURCE / 'completion.json').read_text('utf-8'))
    original = SOURCE / 'best.onnx'
    assert hashlib.sha256(original.read_bytes()).hexdigest() == completion['onnx_sha256']
    graph = onnx.load(original)
    producer = next(node for node in graph.graph.node if graph.graph.output[0].name in node.output)
    assert producer.op_type == 'Softmax'
    logits_name = producer.input[0]
    exported = OUTPUT / 'classifier_logits.onnx'
    onnx.utils.extract_model(str(original), str(exported), [graph.graph.input[0].name], [logits_name])
    split = json.loads((SOURCE / 'split.json').read_text('utf-8'))
    selected = []
    generator = random.Random(20261026)
    input_contract = json.loads((SOURCE / 'input_output_contract.json').read_text('utf-8'))
    labels = input_contract['labels']
    for label in labels:
        rows = [row for row in split['images'] if row['split'] == 'train' and row['source_label'] == label]
        if not rows:
            raise ValueError('No training-only calibration images for ' + label)
        generator.shuffle(rows)
        selected.extend(rows[:40])
    calibration = OUTPUT / 'calibration'
    calibration.mkdir(exist_ok=True)
    geometry = transforms.Compose([transforms.Resize(224, interpolation=InterpolationMode.BILINEAR, antialias=True),
                                   transforms.CenterCrop((224, 224))])
    records = []
    reference = None
    for index, row in enumerate(selected):
        path = SOURCE / row['prepared_path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['prepared_sha256']
        with Image.open(path) as image:
            cropped = geometry(ImageOps.exif_transpose(image).convert('RGB'))
            target = calibration / ('image-%03d.png' % index)
            cropped.save(target)
        if reference is None:
            reference = np.asarray(cropped, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
        records.append({'file': target.name, 'calibration_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
                        'source_id': row['id'], 'group_id': row['group_id'],
                        'split': row['split'], 'source_label': row['source_label'], 'source_sha256': row['prepared_sha256']})
    assert all(record['split'] == 'train' for record in records)
    np.savez(OUTPUT / 'reference_input.npz', images=reference)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    source_session = ort.InferenceSession(str(original), options, providers=['CPUExecutionProvider'])
    logit_session = ort.InferenceSession(str(exported), options, providers=['CPUExecutionProvider'])
    expected = source_session.run(None, {'images': reference})[0]
    logits = logit_session.run(None, {'images': reference})[0]
    probability = np.exp(logits - logits.max(axis=1, keepdims=True))
    probability /= probability.sum(axis=1, keepdims=True)
    np.testing.assert_allclose(probability, expected, rtol=1e-5, atol=1e-6)
    metadata = {'status': 'prepared_for_conversion', 'scope': 'research_only', 'source_onnx_sha256': completion['onnx_sha256'],
                'logit_onnx_sha256': hashlib.sha256(exported.read_bytes()).hexdigest(), 'input_name': 'images',
                'output_name': logits_name, 'input_shape': [1, 3, 224, 224], 'labels': labels,
                'classifier_softmax': True, 'calibration_records': records,
                'calibration_uses_training_only': True, 'source_probability_max_difference': float(np.max(np.abs(expected-probability))),
                'device_execution_verified': False,
                'input_geometry': input_contract.get('input_geometry', 'full_frame_center_crop')}
    (OUTPUT / 'conversion_inputs.json').write_text(json.dumps(metadata, indent=2), 'utf-8')
    print('Prepared', len(records), 'training calibration images; logit/softmax parity passed.')


if __name__ == '__main__':
    main()
