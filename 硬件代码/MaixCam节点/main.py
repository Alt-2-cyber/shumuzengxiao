import base64
import json
import math
import os
import sys
import time

try:
    import urequests as http_requests
except Exception:
    try:
        import requests as http_requests
    except Exception:
        http_requests = None

try:
    from maix import app, camera, display, image, nn, pinmap, time as maix_time
except Exception as exc:
    print("MaixPy import failed:", exc)
    raise

try:
    import serial
except Exception:
    serial = None

try:
    import paho.mqtt.client as mqtt
except Exception:
    mqtt = None


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def now_epoch():
    return int(time.time())


def ensure_dir(path):
    if path and not os.path.exists(path):
        os.makedirs(path)


def configured_cattle_id(cfg):
    value = str(cfg.get("cattle_id", "")).strip()
    return value or None


def classifier_mode(cfg):
    return str(cfg.get("model_type", "")).lower() in ("classifier", "yolov8-cls")


def model_metadata(cfg, loaded):
    default_name = "maixcam-appearance-research" if classifier_mode(cfg) else "maixcam-cattle-detector"
    name = str(cfg.get("model_name", default_name)).strip()
    version = str(cfg.get("model_version", "unversioned")).strip()
    configured_status = str(cfg.get("model_status", "deployed")).strip() or "feature_only"
    scope = str(cfg.get("model_scope", "cow_detection_only")).strip() or "cow_detection_only"
    if classifier_mode(cfg):
        configured_status = "research_only"
        scope = "public_source_appearance_research"
    status = configured_status if loaded else "unavailable"
    return {
        "name": name or default_name,
        "version": version or "unversioned",
        "status": status,
        "scope": scope,
    }


class BackendLink:
    """Small HTTP bridge for a backend that does not subscribe to MQTT.

    The response is intentionally ignored: edge operation and recording should
    continue if the LAN/backend is temporarily unavailable.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.url = str(cfg.get("backend_url", "")).rstrip("/")
        self.api_key = str(cfg.get("backend_api_key", "")).strip()
        self.last_error = None

    def publish_event(self, payload):
        if not self.url or http_requests is None:
            return False
        try:
            headers = {"Content-Type": "application/json"}
            if self.api_key:
                headers["Authorization"] = "Bearer " + self.api_key
            response = http_requests.post(
                self.url + "/api/events/vision",
                data=json.dumps(payload),
                headers=headers,
                timeout=float(self.cfg.get("backend_timeout_seconds", 3)),
            )
            status = getattr(response, "status_code", 200)
            try:
                response.close()
            except Exception:
                pass
            if status < 200 or status >= 300:
                self.last_error = "HTTP %s" % status
                print("backend event rejected:", self.last_error)
                return False
            self.last_error = None
            return True
        except Exception as exc:
            self.last_error = str(exc)
            print("backend event failed:", exc)
            return False


class UartLink:
    def __init__(self, cfg):
        self.cfg = cfg
        self.port = None

    def begin(self):
        if serial is None:
            print("python serial module missing, UART disabled")
            return

        tx_pin = self.cfg.get("uart_tx_pin", "")
        rx_pin = self.cfg.get("uart_rx_pin", "")
        try:
            if tx_pin:
                pinmap.set_pin_function(tx_pin, "UART1_TX")
            if rx_pin:
                pinmap.set_pin_function(rx_pin, "UART1_RX")
        except Exception as exc:
            print("UART pinmap warning:", exc)

        try:
            self.port = serial.Serial(
                self.cfg.get("uart_device", "/dev/ttyS1"),
                self.cfg.get("uart_baud", 115200),
                timeout=0,
            )
            print("UART opened:", self.port.port)
        except Exception as exc:
            print("UART open failed:", exc)
            self.port = None

    def send_json(self, payload):
        if not self.port:
            return
        try:
            line = json.dumps(payload, separators=(",", ":")) + "\n"
            self.port.write(line.encode("utf-8"))
        except Exception as exc:
            print("UART send failed:", exc)

    def read_lines(self):
        if not self.port:
            return []
        lines = []
        try:
            while self.port.in_waiting:
                raw = self.port.readline()
                if raw:
                    lines.append(raw.decode("utf-8", errors="ignore").strip())
        except Exception as exc:
            print("UART read failed:", exc)
        return lines


class MqttLink:
    def __init__(self, cfg):
        self.cfg = cfg
        self.client = None
        self.connected = False
        self.last_try = 0

    def begin(self):
        if mqtt is None:
            print("paho-mqtt missing, MQTT disabled")
            return
        if not self.cfg.get("mqtt_host"):
            print("mqtt_host empty, MQTT disabled")
            return
        self.client = mqtt.Client(client_id=self.cfg.get("camera_id", "cam_01"))
        user = self.cfg.get("mqtt_user", "")
        if user:
            self.client.username_pw_set(user, self.cfg.get("mqtt_pass", ""))
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        self.connected = rc == 0
        print("MQTT connected" if self.connected else "MQTT connect rc=%s" % rc)

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        print("MQTT disconnected rc=%s" % rc)

    def loop(self):
        if not self.client:
            return
        if not self.connected and time.time() - self.last_try > 5:
            self.last_try = time.time()
            try:
                self.client.connect(
                    self.cfg.get("mqtt_host"),
                    int(self.cfg.get("mqtt_port", 1883)),
                    keepalive=30,
                )
            except Exception as exc:
                print("MQTT connect failed:", exc)
        try:
            self.client.loop(0.01)
        except Exception as exc:
            print("MQTT loop failed:", exc)
            self.connected = False

    def publish(self, topic, payload, retain=False):
        if not self.client or not self.connected:
            return
        try:
            self.client.publish(
                topic,
                json.dumps(payload, separators=(",", ":")),
                qos=0,
                retain=retain,
            )
        except Exception as exc:
            print("MQTT publish failed:", exc)
            self.connected = False


def load_detector(cfg):
    model_path = cfg.get("model_path", "")
    if not model_path or not os.path.exists(model_path):
        print("Model missing:", model_path)
        return None
    model_type = cfg.get("model_type", "yolov5").lower()
    try:
        if classifier_mode(cfg):
            return nn.Classifier(model=model_path, dual_buff=False)
        if model_type == "yolov8":
            return nn.YOLOv8(model=model_path)
        return nn.YOLOv5(model=model_path)
    except TypeError:
        if classifier_mode(cfg):
            return nn.Classifier(model_path, dual_buff=False)
        if model_type == "yolov8":
            return nn.YOLOv8(model_path)
        return nn.YOLOv5(model_path)


def classifier_input(img, size):
    size = int(size)
    width, height = int(img.width()), int(img.height())
    if size <= 0 or width <= 0 or height <= 0:
        raise ValueError("Classifier image dimensions must be positive")
    if width <= height:
        resized_width, resized_height = size, int(size * height / width)
    else:
        resized_width, resized_height = int(size * width / height), size
    resized = img if (width, height) == (resized_width, resized_height) else img.resize(
        resized_width, resized_height, method=image.ResizeMethod.BILINEAR)
    # Match torchvision's resize-short-edge and rounded center crop geometry.
    x = int(round((resized_width - size) / 2.0))
    y = int(round((resized_height - size) / 2.0))
    return resized.crop(x, y, size, size)


def classifier_predict(classifier, img, cfg):
    if classifier is None or not classifier_mode(cfg):
        return None
    prepared = classifier_input(img, int(cfg.get("classifier_image_size", 224)))
    raw = classifier.classify(prepared, softmax=bool(cfg.get("classifier_softmax", True)))
    labels = getattr(classifier, "labels", [])
    predictions = []
    for index, value in raw:
        class_id, score = int(index), float(value)
        if class_id < 0 or class_id >= len(labels) or not math.isfinite(score) or not 0.0 <= score <= 1.0:
            return None
        predictions.append({"sourceLabel": str(labels[class_id]), "score": score})
    if not predictions:
        return None
    best = max(predictions, key=lambda item: item["score"])
    return {
        "sourceLabel": best["sourceLabel"],
        "score": best["score"],
        "scores": predictions,
        "unit": "full_frame_center_crop",
        "scope": "public_source_appearance_research",
        "clinicalDiagnosis": False,
    }


def object_label(obj, detector):
    for attr in ("class_name", "label", "name"):
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    class_id = getattr(obj, "class_id", None)
    if class_id is None:
        class_id = getattr(obj, "id", None)
    labels = getattr(detector, "labels", None)
    if labels and class_id is not None and int(class_id) < len(labels):
        return labels[int(class_id)]
    return str(class_id if class_id is not None else "unknown")


def object_score(obj):
    for attr in ("score", "prob", "confidence"):
        value = getattr(obj, attr, None)
        if value is not None:
            return float(value)
    return 0.0


def object_bbox(obj):
    x = int(getattr(obj, "x", 0))
    y = int(getattr(obj, "y", 0))
    w = int(getattr(obj, "w", 0))
    h = int(getattr(obj, "h", 0))
    return [x, y, x + w, y + h]


def in_group(label, group):
    return label in group


def cattle_detections(detections, cfg):
    names = cfg.get("classes", {}).get("cattle", ["cow", "cattle"])
    return [d for d in detections if in_group(d["label"], names)]


class VisionState:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lie_started = None
        self.last_event_ts = {}
        self.frame_count = 0
        self.fps_started = time.time()

    def fps(self):
        elapsed = max(0.001, time.time() - self.fps_started)
        return self.frame_count / elapsed

    def can_emit(self, event_type):
        now = time.time()
        cooldown = float(self.cfg.get("event_cooldown_seconds", 30))
        if now - self.last_event_ts.get(event_type, 0) < cooldown:
            return False
        self.last_event_ts[event_type] = now
        return True

    def update(self, detections):
        classes = self.cfg.get("classes", {})
        lie_names = classes.get("lie", [])
        stand_names = classes.get("stand", [])
        person_names = classes.get("person", [])
        gait_names = classes.get("gait_abnormal", [])
        hoof_lesion_names = classes.get("hoof_lesion", [])
        oral_lesion_names = classes.get("oral_lesion", [])
        nasal_discharge_names = classes.get("nasal_discharge", [])
        has_lie = any(in_group(d["label"], lie_names) for d in detections)
        has_stand = any(in_group(d["label"], stand_names) for d in detections)
        has_person = any(in_group(d["label"], person_names) for d in detections)
        has_gait_abnormal = any(in_group(d["label"], gait_names) for d in detections)
        has_hoof_lesion = any(in_group(d["label"], hoof_lesion_names) for d in detections)
        has_oral_lesion = any(in_group(d["label"], oral_lesion_names) for d in detections)
        has_nasal_discharge = any(in_group(d["label"], nasal_discharge_names) for d in detections)

        events = []
        now = time.time()
        if has_lie:
            if self.lie_started is None:
                self.lie_started = now
            duration = now - self.lie_started
            if duration >= float(self.cfg.get("fall_seconds", 180)) and self.can_emit("fall_suspect"):
                events.append(("fall_suspect", "warning", duration))
        elif has_stand:
            self.lie_started = None

        if has_person and self.can_emit("person_enter"):
            events.append(("person_enter", "observe", 0))

        # These classes are optional. They produce review evidence only after a
        # locally validated model has been installed and class names configured.
        if has_gait_abnormal and self.can_emit("gait_abnormal_suspect"):
            events.append(("gait_abnormal_suspect", "observe", 0))
        if has_hoof_lesion and self.can_emit("hoof_lesion_suspect"):
            events.append(("hoof_lesion_suspect", "warning", 0))
        if has_oral_lesion and self.can_emit("oral_lesion_suspect"):
            events.append(("oral_lesion_suspect", "warning", 0))
        if has_nasal_discharge and self.can_emit("nasal_discharge_suspect"):
            events.append(("nasal_discharge_suspect", "observe", 0))

        return events


def save_snapshot(img, cfg, event_type):
    directory = cfg.get("snapshot_dir", "/root/snapshots")
    ensure_dir(directory)
    filename = "%s_%s.jpg" % (event_type, time.strftime("%Y%m%d_%H%M%S"))
    path = os.path.join(directory, filename)
    try:
        img.save(path)
        return path
    except Exception as exc:
        print("snapshot save failed:", exc)
        return ""


def snapshot_upload_payload(path, cfg):
    """Read a local JPEG only for the HTTP bridge; MQTT stays metadata-only."""
    if not path or not cfg.get("snapshot_upload_enabled", True):
        return {}
    maximum = max(32_768, int(cfg.get("snapshot_upload_max_bytes", 1_500_000)))
    try:
        with open(path, "rb") as source:
            content = source.read(maximum + 1)
        if len(content) > maximum:
            print("snapshot upload skipped: %d bytes exceeds %d" % (len(content), maximum))
            return {}
        return {
            "snapshotBase64": base64.b64encode(content).decode("ascii"),
            "snapshotContentType": "image/jpeg",
        }
    except Exception as exc:
        print("snapshot upload read failed:", exc)
        return {}


def publish_event_links(mqtt_link, backend_link, topic, payload, snapshot_path, cfg):
    mqtt_link.publish(topic, payload)
    backend_payload = dict(payload)
    backend_payload.update(snapshot_upload_payload(snapshot_path, cfg))
    return backend_link.publish_event(backend_payload)


def detector_detect(detector, img, cfg):
    if detector is None or classifier_mode(cfg):
        return []
    try:
        return detector.detect(
            img,
            conf_th=float(cfg.get("score_threshold", 0.55)),
            iou_th=float(cfg.get("iou_threshold", 0.45)),
        )
    except TypeError:
        try:
            return detector.detect(
                img,
                float(cfg.get("score_threshold", 0.55)),
                float(cfg.get("iou_threshold", 0.45)),
            )
        except TypeError:
            return detector.detect(img)


def draw_detection(img, det):
    try:
        x1, y1, x2, y2 = det["bbox"]
        img.draw_rect(x1, y1, x2 - x1, y2 - y1, color=image.COLOR_RED, thickness=2)
        img.draw_string(x1, max(0, y1 - 16), "%s %.2f" % (det["label"], det["score"]), color=image.COLOR_RED)
    except Exception:
        pass


def handle_uart_commands(lines, cfg):
    for line in lines:
        if not line:
            continue
        print("UART <-", line)
        try:
            cmd = json.loads(line)
        except Exception:
            continue
        if cmd.get("type") == "capture_request":
            # Main loop handles capture through returned reason marker.
            return cmd.get("reason", "manual")
    return None


def open_camera_with_retry(cfg):
    width = int(cfg.get("image_width", 640))
    height = int(cfg.get("image_height", 480))
    retry_seconds = max(1.0, float(cfg.get("camera_retry_seconds", 5)))
    while not app.need_exit():
        try:
            cam = camera.Camera(width, height)
            print("Camera opened: %sx%s" % (width, height), flush=True)
            return cam
        except Exception as exc:
            print("Camera open failed; retrying in %.1fs: %s" % (retry_seconds, exc), flush=True)
            time.sleep(retry_seconds)
    raise KeyboardInterrupt()


def run_camera_loop(cfg, uart, mqtt_link, backend_link, detector, state, cam, disp):
    status_topic = "cattle/%s/%s/vision/status" % (cfg.get("barn_id"), cfg.get("camera_id"))
    event_topic = "cattle/%s/%s/vision/event" % (cfg.get("barn_id"), cfg.get("camera_id"))
    last_status = 0
    last_classification = 0
    appearance = None

    print("MaixCam vision node started")
    print("model:", cfg.get("model_path"), "loaded:", detector is not None)

    while not app.need_exit():
        mqtt_link.loop()
        capture_reason = handle_uart_commands(uart.read_lines(), cfg)

        img = cam.read()
        if classifier_mode(cfg) and time.time() - last_classification >= max(0.1, float(cfg.get("classifier_interval_seconds", 1))):
            last_classification = time.time()
            appearance = classifier_predict(detector, img, cfg)
            if appearance and state.can_emit("appearance_research"):
                snapshot = save_snapshot(img, cfg, "appearance_research")
                model = model_metadata(cfg, detector is not None)
                payload = {
                    "cameraId": cfg.get("camera_id"),
                    "barnId": cfg.get("barn_id"),
                    "ts": now_epoch(),
                    "eventType": "snapshot_event",
                    "level": "observe",
                    "score": appearance["score"],
                    "snapshotPath": snapshot,
                    "targetId": configured_cattle_id(cfg),
                    "edgeEventId": "appearance-%s-%s" % (now_epoch(), state.frame_count),
                    "bootId": cfg.get("source_boot_id", ""),
                    "screeningOnly": True,
                    "modelName": model["name"],
                    "modelVersion": model["version"],
                    "modelStatus": model["status"],
                    "modelScope": model["scope"],
                    "evidence": "Public source-label appearance research: %s (%.4f); full-frame center crop, no clinical or lesion-localization validation."
                                % (appearance["sourceLabel"], appearance["score"]),
                }
                publish_event_links(mqtt_link, backend_link, event_topic, payload, snapshot, cfg)
                print("appearance research:", appearance)
        raw_objects = detector_detect(detector, img, cfg)
        detections = []
        for obj in raw_objects:
            det = {
                "label": object_label(obj, detector),
                "score": object_score(obj),
                "bbox": object_bbox(obj),
            }
            detections.append(det)
            draw_detection(img, det)

        state.frame_count += 1
        events = state.update(detections)

        if capture_reason:
            snapshot = save_snapshot(img, cfg, "capture_" + capture_reason)
            model = model_metadata(cfg, detector is not None)
            payload = {
                "cameraId": cfg.get("camera_id"),
                "barnId": cfg.get("barn_id"),
                "ts": now_epoch(),
                "eventType": "snapshot_event",
                "level": "observe",
                "reason": capture_reason,
                "snapshotPath": snapshot,
                "targetId": configured_cattle_id(cfg),
                "edgeEventId": "capture-%s-%s" % (capture_reason, now_epoch()),
                "bootId": cfg.get("source_boot_id", ""),
                "screeningOnly": True,
                "modelName": model["name"],
                "modelVersion": model["version"],
                "modelStatus": model["status"],
                "modelScope": model["scope"],
            }
            publish_event_links(mqtt_link, backend_link, event_topic, payload, snapshot, cfg)
            print("capture_request handled:", payload)

        for event_type, level, duration in events:
            snapshot = save_snapshot(img, cfg, event_type)
            best = detections[0] if detections else {"score": 0, "bbox": []}
            model = model_metadata(cfg, detector is not None)
            payload = {
                "cameraId": cfg.get("camera_id"),
                "barnId": cfg.get("barn_id"),
                "ts": now_epoch(),
                "eventType": event_type,
                "level": level,
                "score": best.get("score", 0),
                "bbox": best.get("bbox", []),
                "durationSec": int(duration),
                "snapshotPath": snapshot,
                # The backend ignores a missing targetId for individual risk
                # screening. Never substitute a vision tracking number here.
                "targetId": configured_cattle_id(cfg),
                "edgeEventId": "%s-%s-%s" % (event_type, now_epoch(), state.frame_count),
                "bootId": cfg.get("source_boot_id", ""),
                "modelName": model["name"],
                "modelVersion": model["version"],
                "modelStatus": model["status"],
                "modelScope": model["scope"],
                "screeningOnly": event_type in (
                    "gait_abnormal_suspect",
                    "hoof_lesion_suspect",
                    "oral_lesion_suspect",
                    "nasal_discharge_suspect",
                ),
            }
            uart.send_json({
                "type": "vision_event",
                "cameraId": cfg.get("camera_id"),
                "event": event_type,
                "level": level,
                "score": payload["score"],
                "durationSec": int(duration),
            })
            publish_event_links(mqtt_link, backend_link, event_topic, payload, snapshot, cfg)
            print("event:", payload)

        if time.time() - last_status > 10:
            last_status = time.time()
            cattle = cattle_detections(detections, cfg)
            model = model_metadata(cfg, detector is not None)
            status = {
                "cameraId": cfg.get("camera_id"),
                "barnId": cfg.get("barn_id"),
                "ts": now_epoch(),
                "fps": round(state.fps(), 2),
                "modelLoaded": detector is not None,
                "modelName": model["name"],
                "modelVersion": model["version"],
                "modelStatus": model["status"],
                "modelScope": model["scope"],
                "detections": len(detections),
                "cattleDetected": len(cattle),
                "cattleScores": [round(d["score"], 3) for d in cattle[:8]],
                "mqtt": mqtt_link.connected,
                "backend": bool(backend_link.url and backend_link.last_error is None),
            }
            if classifier_mode(cfg):
                status["appearanceResearch"] = appearance
            mqtt_link.publish(status_topic, status, retain=True)
            uart.send_json({"type": "status", **status})
            print("status:", status)

        if disp is not None:
            try:
                disp.show(img)
            except Exception:
                pass
        maix_time.sleep_ms(10)


def close_resource(resource):
    if resource is not None and hasattr(resource, "close"):
        try:
            resource.close()
        except Exception as exc:
            print("Resource close failed:", exc)


def main():
    cfg = load_config()
    ensure_dir(cfg.get("snapshot_dir", "/root/snapshots"))
    uart = UartLink(cfg)
    mqtt_link = MqttLink(cfg)
    cam = None
    disp = None
    detector = None
    try:
        uart.begin()
        mqtt_link.begin()
        backend_link = BackendLink(cfg)
        detector = load_detector(cfg)
        state = VisionState(cfg)
        cam = open_camera_with_retry(cfg)
        disp = display.Display() if cfg.get("display_enabled", False) else None
        run_camera_loop(cfg, uart, mqtt_link, backend_link, detector, state, cam, disp)
    finally:
        close_resource(detector)
        close_resource(disp)
        close_resource(cam)
        close_resource(uart.port)
        if mqtt_link.client is not None:
            try:
                mqtt_link.client.disconnect()
            except Exception as exc:
                print("MQTT disconnect failed:", exc)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
