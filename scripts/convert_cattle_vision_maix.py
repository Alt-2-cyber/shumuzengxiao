"""Convert the trained research classifier inside the isolated WSL toolchain."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'vision-training-data/maixcam-yolov8-disease-20261026'


def run_tool(name, arguments):
    log = OUTPUT / (name.replace('.py', '') + '.log')
    command = [sys.executable, str(ROOT / 'scripts/run_maix_tpu_tool.py'), name] + arguments
    print('Running', name, flush=True)
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=OUTPUT, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(errors='replace')[-5500:], flush=True)
        raise SystemExit(result.returncode)
    print(name, 'passed', flush=True)


def main():
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    OUTPUT = args.output.resolve()
    if (OUTPUT / 'conversion_result.json').exists():
        raise FileExistsError('A completed conversion already exists in this directory')
    metadata = json.loads((OUTPUT / 'conversion_inputs.json').read_text())
    assert hashlib.sha256((OUTPUT / 'classifier_logits.onnx').read_bytes()).hexdigest() == metadata['logit_onnx_sha256']
    if not metadata.get('calibration_uses_training_only') or not metadata.get('calibration_records'):
        raise ValueError('Training-only calibration provenance is required')
    for record in metadata['calibration_records']:
        if record['split'] != 'train':
            raise ValueError('Heldout images cannot be used for calibration')
        actual = hashlib.sha256((OUTPUT / 'calibration' / record['file']).read_bytes()).hexdigest()
        if actual != record['calibration_sha256']:
            raise ValueError('Calibration image hash mismatch: ' + record['file'])
    run_tool('model_transform.py', ['--model_name', 'cattle_research_classifier', '--model_def', 'classifier_logits.onnx',
             '--input_shapes', '[[1,3,224,224]]', '--mean', '0,0,0', '--scale', '0.00392156862745098,0.00392156862745098,0.00392156862745098',
             '--pixel_format', 'rgb', '--channel_format', 'nchw', '--output_names', metadata['output_name'],
             '--test_input', 'reference_input.npz', '--test_result', 'classifier_top_outputs.npz',
             '--tolerance', '0.99,0.99', '--mlir', 'classifier.mlir'])
    run_tool('run_calibration.py', ['classifier.mlir', '--dataset', 'calibration', '--input_num', str(len(metadata['calibration_records'])), '-o', 'classifier_cali_table'])
    run_tool('model_deploy.py', ['--mlir', 'classifier.mlir', '--quantize', 'INT8', '--quant_input',
             '--calibration_table', 'classifier_cali_table', '--processor', 'cv181x',
             '--test_input', 'cattle_research_classifier_in_f32.npz', '--test_reference', 'classifier_top_outputs.npz',
             '--tolerance', '0.9,0.6', '--model', 'cattle_research_int8.cvimodel'])
    mud = '[basic]\ntype = cvimodel\nmodel = cattle_research_int8.cvimodel\n\n[extra]\nmodel_type = classifier\ninput_type = rgb\nmean = 0,0,0\nscale = 0.00392156862745098,0.00392156862745098,0.00392156862745098\nlabels = ' + ','.join(metadata['labels']) + '\n'
    (OUTPUT / 'cattle_research.mud').write_text(mud)
    metadata.update(status='converted_research_only', cvimodel_sha256=hashlib.sha256((OUTPUT / 'cattle_research_int8.cvimodel').read_bytes()).hexdigest(),
                    device_execution_verified=False)
    (OUTPUT / 'conversion_result.json').write_text(json.dumps(metadata, indent=2))
    print('Converted cv181x research model; physical camera execution remains unverified.', flush=True)


if __name__ == '__main__':
    main()
