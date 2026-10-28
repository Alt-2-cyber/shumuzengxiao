#!/usr/bin/env python3
"""Host-side regression checks for MaixCam event mapping.

The device-only ``maix`` package is stubbed so this test can run on the
development computer. It verifies that the default cow detector cannot emit
disease-like events, while an explicitly configured reviewed class can emit a
screening evidence event.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "main.py"
CONFIG = ROOT / "config.json"


def install_device_stubs() -> None:
    maix = types.ModuleType("maix")
    for name in ("camera", "display", "image", "nn", "pinmap", "time"):
        setattr(maix, name, types.SimpleNamespace())
    sys.modules["maix"] = maix

    paho = types.ModuleType("paho")
    paho.__path__ = []
    mqtt_package = types.ModuleType("paho.mqtt")
    mqtt_package.__path__ = []
    mqtt_client = types.ModuleType("paho.mqtt.client")
    sys.modules["paho"] = paho
    sys.modules["paho.mqtt"] = mqtt_package
    sys.modules["paho.mqtt.client"] = mqtt_client


def load_main():
    install_device_stubs()
    spec = importlib.util.spec_from_file_location("maixcam_main", MAIN)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load MaixCam main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    module = load_main()
    default_config = json.loads(CONFIG.read_text(encoding="utf-8"))
    detection = {"label": "nasal_discharge", "score": 0.92, "bbox": [1, 2, 3, 4]}

    default_state = module.VisionState(default_config)
    assert default_state.update([detection]) == [], (
        "default COCO cow detector must not emit disease-like events"
    )

    reviewed_config = copy.deepcopy(default_config)
    reviewed_config["classes"]["nasal_discharge"] = ["nasal_discharge"]
    reviewed_state = module.VisionState(reviewed_config)
    events = reviewed_state.update([detection])
    assert events == [("nasal_discharge_suspect", "observe", 0)]
    assert reviewed_state.update([detection]) == [], "cooldown must deduplicate events"

    print("MaixCam vision logic checks passed")


if __name__ == "__main__":
    main()
