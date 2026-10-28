"""Run saved 224x224 ROI inputs on the actual MaixCAM NPU."""

import argparse
import gc
import hashlib
import json
from pathlib import Path
import time

from maix import image, nn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--old-model', required=True)
    parser.add_argument('--new-model', required=True)
    args = parser.parse_args()
    rows = json.loads((args.root / 'manifest.json').read_text())
    result = {'scope': 'Public source-label cow-region images; not clinical accuracy', 'models': {}}
    for name, path in [('previous', args.old_model), ('candidate', args.new_model)]:
        model = nn.Classifier(model=path, dual_buff=False)
        predictions = []
        started = time.monotonic()
        for index, row in enumerate(rows):
            picture = image.load(str(args.root / row['file']))
            if picture.width() != 224 or picture.height() != 224:
                raise ValueError('Only the prepared ROI contract is allowed')
            ranked = model.classify(picture, softmax=True)
            probability = [0.0, 0.0, 0.0]
            for class_id, score in ranked:
                probability[int(class_id)] = float(score)
            predictions.append({'id': row['id'], 'split': row['split'], 'source_label': row['source_label'],
                                'probabilities': probability})
            if index % 100 == 0 or index + 1 == len(rows):
                print('NPU_EVAL', name, index + 1, '/', len(rows), flush=True)
        result['models'][name] = {'labels': model.labels, 'predictions': predictions,
                                  'elapsed_seconds': time.monotonic() - started,
                                  'mud_sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
        model = None
        gc.collect()
    (args.root / 'device-results.json').write_text(json.dumps(result, indent=2))
    print('NPU_EVAL_COMPLETE', flush=True)


if __name__ == '__main__':
    main()
