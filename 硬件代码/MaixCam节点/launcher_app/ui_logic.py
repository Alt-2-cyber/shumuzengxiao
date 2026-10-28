"""Configuration and touch handling shared by the camera app and host checks."""

import os


MODES = ('cow_detection', 'appearance_research')


def mode_config(base, mode, root):
    if mode not in MODES:
        raise ValueError('Unknown camera mode')
    result = dict(base)
    research = mode == 'appearance_research'
    key = 'research_model_path' if research else 'cow_model_path'
    default = 'models/cattle_research.mud' if research else 'models/cattle_yolov8.mud'
    result['model_path'] = os.path.join(root, base.get(key, default))
    result['model_type'] = 'classifier' if research else 'yolov8'
    result['model_status'] = 'research_only' if research else 'deployed'
    result['model_scope'] = 'public_source_appearance_research' if research else 'cow_detection_only'
    result['classifier_softmax'] = True
    return result


class TouchState:
    def __init__(self, mode):
        self.mode = mode
        self.exit = False
        self.pressed = False

    def update(self, x, y, pressed, screen_width, screen_height, width=320, height=240):
        fresh = bool(pressed) and not self.pressed
        self.pressed = bool(pressed)
        if not fresh:
            return False
        scale = min(screen_width / width, screen_height / height)
        px = (x - (screen_width - width * scale) / 2) / scale
        py = (y - (screen_height - height * scale) / 2) / scale
        if 0 <= px < 34 and 0 <= py < 34:
            self.exit = True
            return True
        if width - 54 <= px < width and 0 <= py < 34:
            self.mode = MODES[1 - MODES.index(self.mode)]
            return True
        return False
