"""Pure helpers for cow detection followed by appearance classification."""

import math


def _finite_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _probability(value):
    return _finite_number(value) and 0 <= value <= 1


def cow_regions(detections, width, height, min_score=0.45, min_side=32,
                padding=0.05, max_regions=2):
    """Return clipped cow boxes and integer crops, largest unpadded box first.

    Bounding boxes use [x1, y1, x2, y2]; crops use [x, y, width, height].
    Padding is a fraction of the clipped box size on each side. Minimum
    dimensions and area ordering are evaluated before padding.
    """
    if (not _finite_number(width) or not _finite_number(height)
            or width < 1 or height < 1
            or int(width) != width or int(height) != height
            or not _probability(min_score)
            or not _finite_number(min_side) or min_side <= 0
            or not _finite_number(padding) or padding < 0
            or type(max_regions) is not int or max_regions <= 0):
        return []
    if detections is None:
        return []
    width, height = int(width), int(height)
    regions = []
    for detection in detections:
        if not isinstance(detection, dict) or detection.get('label') != 'cow':
            continue
        score = detection.get('score')
        bbox = detection.get('bbox')
        if not _probability(score) or score < min_score:
            continue
        if (not isinstance(bbox, (list, tuple)) or len(bbox) != 4
                or not all(_finite_number(value) for value in bbox)):
            continue
        x1, y1, x2, y2 = bbox
        x1, x2 = max(0, min(width, x1)), max(0, min(width, x2))
        y1, y2 = max(0, min(height, y1)), max(0, min(height, y2))
        box_width, box_height = x2 - x1, y2 - y1
        if box_width < min_side or box_height < min_side:
            continue
        pad_x, pad_y = box_width * padding, box_height * padding
        left = math.floor(max(0, x1 - pad_x))
        top = math.floor(max(0, y1 - pad_y))
        right = math.ceil(min(width, x2 + pad_x))
        bottom = math.ceil(min(height, y2 + pad_y))
        regions.append({'label': 'cow', 'score': score,
                        'bbox': [x1, y1, x2, y2],
                        'crop': [left, top, right - left, bottom - top]})
    regions.sort(key=lambda region: ((region['bbox'][2] - region['bbox'][0])
                                    * (region['bbox'][3] - region['bbox'][1])),
                 reverse=True)
    return regions[:max_regions]


def classify_regions(detections, width, height, predict_roi, **region_options):
    """Call predict_roi once per selected cow; keep caller predictions as-is."""
    regions = cow_regions(detections, width, height, **region_options)
    results = []
    for region in regions:
        bbox = list(region['bbox'])
        prediction = predict_roi(region)
        results.append({'regionbbox': bbox, 'prediction': prediction})
    if not regions:
        status = 'no_cattle'
    elif any(result['prediction'] is not None for result in results):
        status = 'classified'
    else:
        status = 'uncertain'
    return {'status': status, 'cattleCount': len(regions), 'results': results}


def accept_prediction(raw, minimum_score=0.75, minimum_margin=0.2):
    """Validate a complete three-class appearance prediction, or return None.

    scores contains three dictionaries with sourceLabel and score. Its order
    is irrelevant, but the declared top label and score must match its maximum.
    The three probabilities must sum to within 0.02 of one.
    Accepted output is a shallow copy marked clinicalDiagnosis=False.
    """
    labels = ('foot-and-mouth', 'healthy', 'lumpy')
    if (not isinstance(raw, dict) or not _probability(minimum_score)
            or not _probability(minimum_margin)
            or raw.get('sourceLabel') not in labels
            or not _probability(raw.get('score'))):
        return None
    scores = raw.get('scores')
    if not isinstance(scores, (list, tuple)) or len(scores) != len(labels):
        return None
    seen = set()
    for item in scores:
        if not isinstance(item, dict):
            return None
        label, score = item.get('sourceLabel'), item.get('score')
        if label not in labels or not _probability(score):
            return None
        if label in seen:
            return None
        seen.add(label)
    if not 0.98 <= math.fsum(item['score'] for item in scores) <= 1.02:
        return None
    ranked = sorted(scores, key=lambda item: item['score'], reverse=True)
    top = ranked[0]
    if raw['sourceLabel'] != top['sourceLabel'] or raw['score'] != top['score']:
        return None
    margin = top['score'] - ranked[1]['score']
    if top['score'] < minimum_score:
        return None
    # Subtraction can round an exact boundary such as 0.8 - 0.6 downward.
    if margin < minimum_margin and not math.isclose(
            margin, minimum_margin, rel_tol=0, abs_tol=1e-12):
        return None
    accepted = dict(raw)
    accepted['clinicalDiagnosis'] = False
    return accepted


def roi_quality(rgb):
    """Check HWC uint8 RGB image quality using fixed initial thresholds.

    Brightness and contrast are grayscale mean and standard deviation.
    Sharpness is the four-neighbor Laplacian variance on interior pixels;
    borders are excluded to avoid artificial edges. This checks image quality
    only, and makes no clinical inference. NumPy is loaded only on use.
    Invalid or undersized inputs return zero-valued metrics.
    """
    import numpy as np

    result = {'accepted': False, 'reason': 'invalid_input',
              'brightness': 0.0, 'contrast': 0.0, 'sharpness': 0.0}
    # uint8 excludes nonfinite values as well as out-of-range intensities.
    if (not isinstance(rgb, np.ndarray) or rgb.dtype != np.uint8
            or rgb.ndim != 3 or rgb.shape[2] != 3):
        return result
    if rgb.shape[0] < 16 or rgb.shape[1] < 16:
        result['reason'] = 'too_small'
        return result
    pixels = rgb.astype(np.float64)
    # BT.601 luminance in difference form preserves exact achromatic levels.
    green = pixels[:, :, 1]
    gray = (green + 0.299 * (pixels[:, :, 0] - green)
            + 0.114 * (pixels[:, :, 2] - green))
    laplacian = (gray[:-2, 1:-1] + gray[2:, 1:-1]
                 + gray[1:-1, :-2] + gray[1:-1, 2:] - 4 * gray[1:-1, 1:-1])
    result['brightness'] = float(gray.mean())
    result['contrast'] = float(gray.std())
    result['sharpness'] = float(laplacian.var())
    if result['brightness'] < 15:
        result['reason'] = 'too_dark'
    elif result['brightness'] > 245:
        result['reason'] = 'too_bright'
    elif result['contrast'] < 4:
        result['reason'] = 'low_contrast'
    elif result['sharpness'] < 3:
        result['reason'] = 'blurry'
    else:
        result['accepted'] = True
        result['reason'] = 'ok'
    return result
