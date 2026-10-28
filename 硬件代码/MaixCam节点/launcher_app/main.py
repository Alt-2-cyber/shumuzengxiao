"""Foreground MaixCAM app; each mode owns and releases its camera/model."""

import gc
import json
import os
import time
import traceback

from maix import app, camera, display, image, touchscreen
import vision_node as node
from ui_logic import MODES, TouchState, mode_config
from cascade_logic import accept_prediction, classify_regions, roi_quality


ROOT = os.path.dirname(os.path.abspath(__file__))
TITLE = '\u6768\u6587\u660a-\u6570\u7267\u589e\u6548'
LABELS = {'foot-and-mouth': '\u53e3\u8e44\u75ab\u6837\u672c\u7c7b',
          'healthy': '\u5065\u5eb7\u6837\u672c\u7c7b', 'lumpy': '\u7ed3\u8282\u6837\u76ae\u80a4\u6837\u672c\u7c7b'}


def save_record(name, record):
    directory = os.path.join(ROOT, 'logs')
    os.makedirs(directory, exist_ok=True)
    target = os.path.join(directory, name + '.json')
    with open(target + '.new', 'w', encoding='utf-8') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
    os.replace(target + '.new', target)


def text(img, x, y, value, color=None):
    img.draw_string(x, y, value, color=color or image.COLOR_WHITE, font='shumu', wrap=False)


def prepare_roi(roi, size=224):
    scale = min(size / roi.width(), size / roi.height())
    width = max(1, int(round(roi.width() * scale)))
    height = max(1, int(round(roi.height() * scale)))
    resized = roi.resize(width, height, method=image.ResizeMethod.BILINEAR)
    canvas = image.Image(size, size, bg=image.Color.from_rgb(114, 114, 114))
    canvas.draw_image((size - width) // 2, (size - height) // 2, resized)
    return canvas


def research_frame(detector, classifier, frame, cfg):
    import numpy as np
    detector_cfg = dict(cfg, model_type='yolov8')
    detections = [{'label': node.object_label(obj, detector), 'score': node.object_score(obj),
                   'bbox': node.object_bbox(obj)} for obj in node.detector_detect(detector, frame, detector_cfg)]
    qualities = {}
    detector_scores = {}
    calls = 0

    def predict(region):
        nonlocal calls
        detector_scores[tuple(region['bbox'])] = region['score']
        x, y, width, height = region['crop']
        roi = frame.crop(x, y, width, height)
        pixels = np.frombuffer(roi.to_bytes(), dtype=np.uint8).reshape(height, width, 3)
        quality = roi_quality(pixels)
        qualities[tuple(region['bbox'])] = quality
        if not quality['accepted']:
            return None
        prepared = prepare_roi(roi)
        calls += 1
        raw = node.classifier_predict(classifier, prepared, cfg)
        accepted = accept_prediction(raw, float(cfg.get('cascade_minimum_score', .8)),
                                      float(cfg.get('cascade_minimum_margin', .2)))
        if accepted is not None:
            accepted['unit'] = 'detected_cow_roi_letterbox'
        return accepted

    result = classify_regions(detections, frame.width(), frame.height(), predict,
                              min_score=float(cfg.get('score_threshold', .45)),
                              min_side=int(cfg.get('cascade_minimum_side', 32)), padding=.05,
                              max_regions=int(cfg.get('cascade_max_regions', 2)))
    result['classifier_calls'] = calls
    result['detectedCattle'] = len(node.cattle_detections(detections, cfg))
    result['clinicalDiagnosis'] = False
    if result['status'] == 'no_cattle' and result['detectedCattle']:
        result['status'] = 'cow_too_small'
    for item in result['results']:
        item['quality'] = qualities.get(tuple(item['regionbbox']))
        item['detector_score'] = detector_scores[tuple(item['regionbbox'])]
    return result


def overlay(img, mode, back, result=None, message=None, fps=0):
    width, height = img.width(), img.height()
    img.draw_rect(0, 0, width, 34, color=image.COLOR_BLACK, thickness=-1)
    img.draw_image(4, 5, back)
    text(img, 34, 9, TITLE)
    text(img, width - 44, 9, '\u5207\u6362')
    img.draw_rect(0, height - 58, width, 58, color=image.COLOR_BLACK, thickness=-1)
    research = mode == 'appearance_research'
    text(img, 6, height - 54, '\u5916\u89c2\u7814\u7a76 / \u975e\u8bca\u65ad' if research else '\u725b\u53ea\u68c0\u6d4b')
    if message:
        summary = message
    elif research and result:
        accepted = [item['prediction'] for item in result['results'] if item['prediction'] is not None]
        if result['status'] == 'no_cattle':
            summary = '\u672a\u68c0\u6d4b\u5230\u725b\u53ea'
        elif result['status'] == 'cow_too_small':
            summary = '\u725b\u53ea\u592a\u5c0f\uff0c\u8bf7\u9760\u8fd1'
        elif not accepted:
            summary = '\u753b\u8d28\u6216\u7f6e\u4fe1\u5ea6\u4e0d\u8db3'
        else:
            best = accepted[0]
            summary = '%s %.1f%%' % (LABELS.get(best['sourceLabel'], best['sourceLabel']), best['score'] * 100)
    elif not research and result is not None:
        summary = '\u725b\u53ea\u6570\u91cf %d' % len(result)
    else:
        summary = '\u7b49\u5f85\u63a8\u7406'
    text(img, 6, height - 29, summary)
    if not research:
        text(img, width - 92, height - 29, '%.1f FPS' % fps)
    return img


def poll(touch, state, disp):
    x, y, pressed = touch.read()
    changed = state.update(x, y, pressed, disp.width(), disp.height())
    if state.exit:
        app.set_exit_flag(True)
    return changed


def run_mode(base, state, touch, back, test_frames):
    mode = state.mode
    cfg = mode_config(base, mode, ROOT)
    disp = cam = model = detector = None
    frames = 0
    started = time.monotonic()
    record = {'mode': mode, 'model_loaded': False, 'frames': 0,
              'model_scope': cfg['model_scope'], 'clinicalDiagnosis': False}
    try:
        disp = display.Display()
        loading = image.Image(320, 240, bg=image.COLOR_BLACK)
        disp.show(overlay(loading, mode, back, message='\u6b63\u5728\u52a0\u8f7d\u6a21\u578b'))
        cow_cfg = mode_config(base, 'cow_detection', ROOT)
        detector = node.nn.YOLOv8(model=cow_cfg['model_path'], dual_buff=False)
        if mode == 'appearance_research':
            model = node.load_detector(cfg)
        if detector is None or (mode == 'appearance_research' and model is None):
            raise RuntimeError('The model could not be loaded')
        record['model_loaded'] = True
        record['cow_detector_loaded'] = True
        record['classifier_loaded'] = model is not None
        cam = camera.Camera(320, 240, detector.input_format(), fps=15)
        started = time.monotonic()
        while not app.need_exit() and state.mode == mode:
            if poll(touch, state, disp):
                break
            record.pop('last_prediction', None)
            record.pop('detections', None)
            frame = cam.read()
            if mode == 'appearance_research':
                result = research_frame(detector, model, frame, cfg)
                record['last_prediction'] = result
                record['classifier_calls'] = record.get('classifier_calls', 0) + result['classifier_calls']
                for item in result['results']:
                    prediction = item['prediction']
                    node.draw_detection(frame, {'bbox': item['regionbbox'],
                        'label': prediction['sourceLabel'] if prediction else 'cow',
                        'score': prediction['score'] if prediction else item['detector_score']})
            else:
                detections = [{'label': node.object_label(obj, detector), 'score': node.object_score(obj),
                               'bbox': node.object_bbox(obj)} for obj in node.detector_detect(detector, frame, cfg)]
                result = node.cattle_detections(detections, cfg)
                for detection in result:
                    node.draw_detection(frame, detection)
                record['detections'] = result
            frames += 1
            record.update(frames=frames, fps=round(frames / max(time.monotonic() - started, 0.01), 2))
            overlay(frame, mode, back, result, fps=record['fps'])
            disp.show(frame)
            if frames == 1 or frames % 30 == 0:
                save_record('runtime', record)
            if test_frames and frames >= test_frames:
                os.makedirs(os.path.join(ROOT, 'logs'), exist_ok=True)
                frame.save(os.path.join(ROOT, 'logs', 'qa-' + mode + '.jpg'))
                save_record('qa-' + mode, record)
                return
        save_record('runtime', record)
    except Exception as failure:
        record.update(error=str(failure), traceback=traceback.format_exc(), frames=frames)
        save_record('qa-' + mode if test_frames else 'runtime', record)
        print(record['traceback'], flush=True)
        if test_frames:
            raise
        if disp is not None:
            error_frame = image.Image(320, 240, bg=image.COLOR_BLACK)
            overlay(error_frame, mode, back, message='\u8fd0\u884c\u5f02\u5e38\uff0c\u53ef\u8fd4\u56de')
            text(error_frame, 8, 80, 'Model/camera error')
            disp.show(error_frame)
            while not app.need_exit() and state.mode == mode:
                if poll(touch, state, disp):
                    break
                time.sleep(0.05)
    finally:
        node.close_resource(cam)
        node.close_resource(model)
        node.close_resource(detector)
        node.close_resource(disp)
        cam = model = detector = disp = None
        gc.collect()


def main():
    with open(os.path.join(ROOT, 'config.json'), encoding='utf-8') as stream:
        base = json.load(stream)
    params = {}
    try:
        value = app.get_start_param()
        if value:
            params = json.loads(value)
    except (ValueError, TypeError):
        pass
    mode = os.environ.get('SHUMU_TEST_MODE') or params.get('mode') or base.get('default_mode', 'cow_detection')
    if mode not in MODES:
        raise ValueError('Unsupported mode')
    test_frames = min(120, max(0, int(os.environ.get('SHUMU_TEST_FRAMES') or params.get('test_frames', 0))))
    image.load_font('shumu', '/maixapp/share/font/SourceHanSansCN-Regular.otf', size=16)
    back = image.load('/maixapp/share/icon/ret.png').resize(24, 24)
    touch = touchscreen.TouchScreen()
    state = TouchState(mode)
    try:
        while not app.need_exit():
            run_mode(base, state, touch, back, test_frames)
            if test_frames or state.exit:
                break
    finally:
        node.close_resource(touch)


if __name__ == '__main__':
    main()
