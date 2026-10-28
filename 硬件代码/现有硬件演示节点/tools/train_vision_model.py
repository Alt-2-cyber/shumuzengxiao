#!/usr/bin/env python3
"""Train and release-gate a visual screening baseline.

This trainer is intentionally conservative. It accepts only image-level
screening labels that can be clinically reviewed; it never accepts FMD
positive/negative labels and it never treats a generic cow detector as a
disease model. The generated NumPy baseline is useful for data and pipeline
validation, but MaixCAM production deployment still requires an independently
trained and converted YOLO/MUD artifact supplied with ``--edge-model``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


ALLOWED_LABELS = {
    "normal",
    "gait_abnormal_suspect",
    "hoof_lesion_suspect",
    "oral_lesion_suspect",
    "nasal_discharge_suspect",
}
VISUAL_RISK_LABELS = ALLOWED_LABELS - {"normal"}
FORBIDDEN_DISEASE_LABELS = {
    "fmd_positive", "fmd_negative", "foot_and_mouth_disease",
    "fmd", "hoof_rot", "digital_dermatitis", "sole_ulcer",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
RESIZE = (16, 12)


@dataclass(frozen=True)
class ImageRecord:
    path: Path
    label: str
    animal_id: str
    barn_id: str
    camera_id: str
    recorded_at: str
    event_id: str
    recording_id: str
    snapshot_sha256: str
    veterinarian: str
    clinical_evidence_reference: str
    clinically_verified: bool
    allow_for_disease_labels: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="JSONL manifest of archived, reviewed visual events")
    parser.add_argument("--images-root", type=Path,
                        help="Root used for relative image paths; defaults to manifest directory")
    parser.add_argument("--output", type=Path, default=Path("vision_model_baseline.npz"),
                        help="NumPy baseline artifact; this is not a MaixCAM MUD file")
    parser.add_argument("--metadata", type=Path, default=Path("vision_model_metadata.json"))
    parser.add_argument("--model-card", type=Path, default=Path("vision_model_card.md"))
    parser.add_argument("--model-name", default="cattle-vision-screening-baseline")
    parser.add_argument("--epochs", type=int, default=700)
    parser.add_argument("--learning-rate", type=float, default=0.08)
    parser.add_argument("--l2", type=float, default=0.001)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260917)
    parser.add_argument("--release", action="store_true",
                        help="Run the production release gates")
    parser.add_argument("--clinical-api",
                        help="Backend base URL used for per-event lineage rechecks")
    parser.add_argument("--clinical-api-key", default=os.environ.get("CLINICAL_API_KEY", ""))
    parser.add_argument("--lineage-timeout-seconds", type=int, default=20)
    parser.add_argument("--edge-model", type=Path,
                        help="Converted MaixCAM .mud artifact (required for release approval)")
    parser.add_argument("--minimum-animals", type=int, default=9)
    parser.add_argument("--minimum-external-animals", type=int, default=3)
    parser.add_argument("--minimum-risk-images", type=int, default=50)
    parser.add_argument("--minimum-risk-animals", type=int, default=3)
    parser.add_argument("--minimum-macro-f1", type=float, default=0.75)
    parser.add_argument("--minimum-risk-precision", type=float, default=0.80)
    parser.add_argument("--minimum-risk-recall", type=float, default=0.70)
    parser.add_argument("--maximum-reject-rate", type=float, default=0.25)
    return parser.parse_args()


def fail(message: str) -> None:
    raise SystemExit(message)


def sha256_file(path: Path) -> str:
    if not path.is_file():
        fail(f"file not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_text(value: Any, field: str, line_number: int) -> str:
    text = str(value or "").strip()
    if not text:
        fail(f"manifest line {line_number} requires {field}")
    return text


def load_manifest(path: Path, images_root: Path | None) -> list[ImageRecord]:
    if not path.is_file():
        fail(f"manifest not found: {path}")
    root = (images_root or path.parent).resolve()
    records: list[ImageRecord] = []
    seen_paths: set[Path] = set()
    seen_events: set[str] = set()
    seen_hashes: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as error:
            fail(f"invalid JSON on manifest line {line_number}: {error}")
        if not isinstance(raw, dict):
            fail(f"manifest line {line_number} is not an object")

        label = required_text(raw.get("label"), "label", line_number).lower()
        if label in FORBIDDEN_DISEASE_LABELS or label not in ALLOWED_LABELS:
            fail(f"manifest line {line_number} has unsupported or forbidden label: {label}")
        relative = Path(required_text(raw.get("image") or raw.get("path"), "image", line_number))
        image_path = relative if relative.is_absolute() else root / relative
        image_path = image_path.resolve()
        if image_path.suffix.lower() not in IMAGE_SUFFIXES or not image_path.is_file():
            fail(f"manifest line {line_number} image is missing or unsupported: {image_path}")
        if image_path in seen_paths:
            fail(f"manifest line {line_number} repeats image path: {image_path}")
        seen_paths.add(image_path)

        event_id = required_text(raw.get("eventId") or raw.get("sourceEventId"), "eventId", line_number)
        recording_id = required_text(raw.get("recordingId"), "recordingId", line_number)
        if event_id in seen_events:
            fail(f"manifest repeats eventId: {event_id}")
        seen_events.add(event_id)
        animal_id = required_text(raw.get("animalId"), "animalId", line_number)
        barn_id = required_text(raw.get("barnId"), "barnId", line_number)
        camera_id = required_text(raw.get("cameraId"), "cameraId", line_number)
        recorded_at = required_text(raw.get("recordedAt"), "recordedAt", line_number)
        declared_hash = required_text(raw.get("snapshotSha256"), "snapshotSha256", line_number).lower()
        if len(declared_hash) != 64 or any(character not in "0123456789abcdef" for character in declared_hash):
            fail(f"manifest line {line_number} has invalid snapshotSha256")
        actual_hash = sha256_file(image_path)
        if actual_hash != declared_hash:
            fail(f"manifest line {line_number} image SHA-256 does not match {image_path}")
        if actual_hash in seen_hashes:
            fail(f"manifest reuses the same image bytes: {image_path}")
        seen_hashes.add(actual_hash)

        clinically_verified = bool(raw.get("clinicallyVerified", False))
        allow_for_disease_labels = bool(raw.get("allowForDiseaseLabels", False))
        veterinarian = str(raw.get("veterinarian") or "").strip()
        evidence = str(raw.get("clinicalEvidenceReference") or "").strip()
        if clinically_verified != allow_for_disease_labels:
            fail(f"manifest line {line_number} must keep clinicalVerified and allowForDiseaseLabels consistent")
        if (label in VISUAL_RISK_LABELS or clinically_verified) and (not veterinarian or not evidence):
            fail(f"manifest line {line_number} requires veterinarian and clinicalEvidenceReference")
        records.append(ImageRecord(
            image_path, label, animal_id, barn_id, camera_id, recorded_at, event_id, recording_id,
            declared_hash, veterinarian, evidence, clinically_verified, allow_for_disease_labels,
        ))
    if len(records) < 2:
        fail("manifest must contain at least two distinct images")
    if {record.label for record in records} != set(ALLOWED_LABELS):
        missing = sorted(ALLOWED_LABELS - {record.label for record in records})
        fail("manifest must include normal and every visual screening label; missing: " + ", ".join(missing))
    return records


def image_features(path: Path) -> np.ndarray:
    try:
        with Image.open(path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image = image.resize(RESIZE, Image.Resampling.BILINEAR)
            pixels = np.asarray(image, dtype=np.float32) / 255.0
    except Exception as error:
        fail(f"cannot read image {path}: {error}")
    spatial = pixels.reshape(-1)
    features: list[float] = list(spatial)
    for channel in range(3):
        values = pixels[:, :, channel]
        features.extend([float(values.mean()), float(values.std())])
        histogram, _ = np.histogram(values, bins=8, range=(0.0, 1.0))
        features.extend((histogram / max(1, values.size)).astype(np.float32).tolist())
    return np.asarray(features, dtype=np.float32)


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - np.max(logits, axis=1, keepdims=True)
    exponential = np.exp(np.clip(shifted, -40.0, 40.0))
    return exponential / np.maximum(exponential.sum(axis=1, keepdims=True), 1e-9)


def fit_softmax(features: np.ndarray, labels: np.ndarray, train_indices: np.ndarray,
                epochs: int, learning_rate: float, l2: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    train = features[train_indices]
    mean = train.mean(axis=0)
    scale = np.maximum(train.std(axis=0), 1e-5)
    normalized = (train - mean) / scale
    class_count = int(labels.max()) + 1
    weights = np.zeros((class_count, normalized.shape[1]), dtype=np.float64)
    bias = np.zeros(class_count, dtype=np.float64)
    target = np.eye(class_count, dtype=np.float64)[labels[train_indices]]
    for _ in range(max(1, epochs)):
        probabilities = softmax(normalized @ weights.T + bias)
        delta = (probabilities - target) / max(1, normalized.shape[0])
        weights -= learning_rate * (delta.T @ normalized + l2 * weights)
        bias -= learning_rate * delta.sum(axis=0)
    return weights.astype(np.float32), bias.astype(np.float32), mean.astype(np.float32), scale.astype(np.float32)


def probabilities(features: np.ndarray, indices: np.ndarray, weights: np.ndarray, bias: np.ndarray,
                  mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return softmax(((features[indices] - mean) / scale) @ weights.T + bias)


def metrics(true: np.ndarray, predicted: np.ndarray, classes: list[str]) -> dict[str, Any]:
    matrix = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for observed, estimate in zip(true, predicted, strict=True):
        matrix[int(observed), int(estimate)] += 1
    class_metrics: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for index, label in enumerate(classes):
        tp = int(matrix[index, index])
        fp = int(matrix[:, index].sum() - tp)
        fn = int(matrix[index, :].sum() - tp)
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2.0 * precision * recall / max(1e-9, precision + recall)
        f1_values.append(f1)
        class_metrics[label] = {"precision": precision, "recall": recall, "f1": f1,
                                "support": int(matrix[index, :].sum())}
    return {
        "accuracy": float(np.mean(predicted == true)) if len(true) else 0.0,
        "macroF1": float(np.mean(f1_values)) if f1_values else 0.0,
        "classMetrics": class_metrics,
        "confusionMatrix": matrix.tolist(),
        "confusionLabels": classes,
    }


def grouped_split(records: list[ImageRecord], validation_ratio: float, seed: int) -> tuple[set[str], set[str], set[str]]:
    if not 0.05 <= validation_ratio < 0.5:
        fail("validation ratio must be between 0.05 and 0.5")
    by_animal: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        by_animal[record.animal_id].append(record)
    animals = list(by_animal)
    if len(animals) < 3:
        fail("at least 3 independent animals are required for a non-release baseline")
    rng = np.random.default_rng(seed)
    rng.shuffle(animals)
    external_count = max(1, round(len(animals) * 0.2))
    validation_count = max(1, round(len(animals) * validation_ratio))
    external = set(animals[:external_count])
    validation = set(animals[external_count:external_count + validation_count])
    train = set(animals[external_count + validation_count:])
    if not train or not validation or not external:
        fail("animal-group split produced an empty partition")
    return train, validation, external


def index_rows(records: list[ImageRecord], groups: tuple[set[str], set[str], set[str]]) -> dict[str, np.ndarray]:
    by_name = {name: group for name, group in zip(("train", "validation", "external"), groups, strict=True)}
    return {name: np.asarray([index for index, record in enumerate(records) if record.animal_id in group], dtype=np.int64)
            for name, group in by_name.items()}


def request_json(url: str, api_key: str, timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "Authorization": f"Bearer {api_key}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as error:
        fail(f"clinical lineage recheck failed for {url}: {error}")
    if not isinstance(value, dict):
        fail(f"clinical lineage endpoint returned a non-object: {url}")
    return value


def recheck_platform_lineage(records: list[ImageRecord], api: str, api_key: str, timeout: int) -> dict[str, Any]:
    if not api or not api_key:
        fail("--release requires --clinical-api and --clinical-api-key")
    base = api.rstrip("/")
    verified: list[dict[str, Any]] = []
    for record in records:
        endpoint = urllib.parse.urljoin(base + "/", f"api/events/vision/{urllib.parse.quote(record.event_id, safe='')}/training-lineage")
        remote = request_json(endpoint, api_key, timeout)
        comparisons = {
            "eventId": (str(remote.get("eventId") or remote.get("id") or ""), record.event_id),
            "cameraId": (str(remote.get("cameraId") or ""), record.camera_id),
            "barnId": (str(remote.get("barnId") or ""), record.barn_id),
            "clinicalAnimalId": (str(remote.get("clinicalAnimalId") or ""), record.animal_id),
            "snapshotSha256": (str(remote.get("snapshotSha256") or "").lower(), record.snapshot_sha256),
            "reviewLabel": (str(remote.get("reviewLabel") or ""), record.label),
            "veterinarian": (str(remote.get("veterinarian") or ""), record.veterinarian),
            "clinicalEvidenceReference": (str(remote.get("clinicalEvidenceReference") or ""), record.clinical_evidence_reference),
            "recordedAt": (str(remote.get("recordedAt") or ""), record.recorded_at),
        }
        mismatched = [field for field, (actual, expected) in comparisons.items() if actual != expected]
        if remote.get("snapshotIntegrityVerified") is not True:
            mismatched.append("snapshotIntegrityVerified")
        if remote.get("reviewStatus") not in {"confirmed", "normal"}:
            mismatched.append("reviewStatus")
        if not remote.get("clinicallyVerifiedAt"):
            mismatched.append("clinicallyVerifiedAt")
        if mismatched:
            fail(f"vision lineage mismatch for event {record.event_id}: {', '.join(mismatched)}")
        verified.append({
            "sourceEventId": record.event_id,
            "recordingId": record.recording_id,
            "cameraId": record.camera_id,
            "barnId": record.barn_id,
            "snapshotSha256": record.snapshot_sha256,
            "reviewLabel": record.label,
            "reviewStatus": str(remote.get("reviewStatus") or ""),
            "clinicalAnimalId": record.animal_id,
            "veterinarian": record.veterinarian,
            "clinicalEvidenceReference": record.clinical_evidence_reference,
            "clinicallyVerifiedAt": str(remote.get("clinicallyVerifiedAt") or ""),
            "recordedAt": str(remote.get("recordedAt") or record.recorded_at),
        })
    canonical = json.dumps(verified, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"api": base, "checked": len(verified), "records": verified,
            "fingerprint": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def release_gate(args: argparse.Namespace, records: list[ImageRecord], external_animals: set[str], external_metrics: dict[str, Any],
                 lineage: dict[str, Any] | None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not args.release:
        reasons.append("release was not requested; production approval remains disabled")
    if args.release and lineage is None:
        reasons.append("platform visual lineage was not rechecked")
    if args.edge_model is None:
        reasons.append("a converted MaixCAM .mud artifact was not supplied")
    elif args.edge_model.suffix.lower() != ".mud" or not args.edge_model.is_file():
        reasons.append("--edge-model must point to an existing .mud file")
    animals = {record.animal_id for record in records}
    if len(animals) < args.minimum_animals:
        reasons.append(f"dataset has {len(animals)} animals; requires {args.minimum_animals}")
    if len(external_animals) < args.minimum_external_animals:
        reasons.append(f"external test has {len(external_animals)} animals; requires {args.minimum_external_animals}")
    for label in sorted(VISUAL_RISK_LABELS):
        label_records = [record for record in records if record.label == label]
        label_animals = {record.animal_id for record in label_records}
        if len(label_records) < args.minimum_risk_images:
            reasons.append(f"{label} has {len(label_records)} images; requires {args.minimum_risk_images}")
        if len(label_animals) < args.minimum_risk_animals:
            reasons.append(f"{label} has {len(label_animals)} animals; requires {args.minimum_risk_animals}")
        if any(not record.clinically_verified or not record.allow_for_disease_labels for record in label_records):
            reasons.append(f"{label} contains an image without clinical disease-label eligibility")
        metric = external_metrics["classMetrics"].get(label, {})
        if float(metric.get("precision", 0.0)) < args.minimum_risk_precision:
            reasons.append(f"external {label} precision is below {args.minimum_risk_precision:.2f}")
        if float(metric.get("recall", 0.0)) < args.minimum_risk_recall:
            reasons.append(f"external {label} recall is below {args.minimum_risk_recall:.2f}")
    if float(external_metrics.get("macroF1", 0.0)) < args.minimum_macro_f1:
        reasons.append(f"external macro-F1 is below {args.minimum_macro_f1:.2f}")
    return args.release and not reasons, reasons


def write_model_card(path: Path, metadata: dict[str, Any]) -> None:
    gate = metadata["releaseGate"]
    lines = [
        "# Visual cattle health screening model card", "",
        f"- Version: `{metadata['modelVersion']}`",
        f"- Production approval: `{'approved' if gate['approved'] else 'disabled'}`",
        "- Labels: `normal`, `gait_abnormal_suspect`, `hoof_lesion_suspect`, `oral_lesion_suspect`, `nasal_discharge_suspect`.",
        "- The NumPy artifact is a data/pipeline baseline. It is not a MaixCAM detector and must not be copied to the edge as a `.mud` file.",
        "- A MaixCAM deployment must provide an independently trained, converted and hashed `.mud` artifact.",
        "- A positive label is a screening candidate requiring veterinary review; it is not a disease diagnosis.",
        "", "## External metrics", "",
        f"- Accuracy: {metadata['externalTest']['accuracy']:.3f}",
        f"- Macro-F1: {metadata['externalTest']['macroF1']:.3f}",
        "", "## Gate decisions", "",
    ]
    lines.extend(f"- {reason}" for reason in gate["reasons"] or ["All visual release gates passed."])
    lines.extend([
        "", "## Medical and deployment boundary", "",
        "This model cannot output FMD positive/negative, foot rot, digital dermatitis, sole ulcer, or any other disease diagnosis.",
        "FMD triage requires approved oral/hoof evidence, approved lameness evidence, and a recent manually measured core-temperature alert.",
        "", "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.learning_rate <= 0.0 or args.l2 < 0.0:
        fail("epochs, learning-rate and l2 are invalid")
    records = load_manifest(args.manifest, args.images_root)
    classes = sorted(ALLOWED_LABELS)
    class_to_index = {label: index for index, label in enumerate(classes)}
    features = np.vstack([image_features(record.path) for record in records]).astype(np.float32)
    labels = np.asarray([class_to_index[record.label] for record in records], dtype=np.int64)
    groups = grouped_split(records, args.validation_ratio, args.seed)
    indices = index_rows(records, groups)
    weights, bias, mean, scale = fit_softmax(features, labels, indices["train"], args.epochs, args.learning_rate, args.l2)
    validation_probabilities = probabilities(features, indices["validation"], weights, bias, mean, scale)
    external_probabilities = probabilities(features, indices["external"], weights, bias, mean, scale)
    validation_predictions = np.argmax(validation_probabilities, axis=1)
    external_predictions = np.argmax(external_probabilities, axis=1)
    validation_metrics = metrics(labels[indices["validation"]], validation_predictions, classes)
    external_metrics = metrics(labels[indices["external"]], external_predictions, classes)
    lineage = recheck_platform_lineage(records, args.clinical_api, args.clinical_api_key, args.lineage_timeout_seconds) if args.release else None
    approved, gate_reasons = release_gate(args, records, groups[2], external_metrics, lineage)
    manifest_fingerprint = sha256_file(args.manifest)
    version = f"vision-baseline-{manifest_fingerprint[:12]}"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, weights=weights, bias=bias, mean=mean, scale=scale,
                        classes=np.asarray(classes), featureSize=np.asarray([features.shape[1]]))
    edge_artifact = None
    if args.edge_model is not None and args.edge_model.is_file():
        edge_artifact = {"path": str(args.edge_model.resolve()), "sha256": sha256_file(args.edge_model)}
    metadata: dict[str, Any] = {
        "schemaVersion": 1,
        "modelFamily": "vision",
        "modelName": args.model_name,
        "modelVersion": version,
        "generatedAt": datetime.now(UTC).isoformat(),
        "datasetManifest": str(args.manifest.resolve()),
        "datasetManifestSha256": manifest_fingerprint,
        "classes": classes,
        "featureExtractor": {"type": "rgb_spatial_histogram_baseline", "resize": list(RESIZE), "featureCount": int(features.shape[1])},
        "trainAnimals": sorted(groups[0]),
        "validationAnimals": sorted(groups[1]),
        "externalAnimals": sorted(groups[2]),
        "validation": validation_metrics,
        "externalTest": external_metrics,
        "edgeArtifact": edge_artifact,
        "visionPlatformLineage": lineage,
        "releaseGate": {"approved": approved, "reasons": gate_reasons},
        "labelPolicy": {
            "screeningLabelsOnly": True,
            "forbiddenLabels": sorted(FORBIDDEN_DISEASE_LABELS),
            "fmdOutput": "fmd_suspect_triage only after independent clinical fusion; never FMD positive/negative",
        },
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    write_model_card(args.model_card, metadata)
    print(json.dumps({
        "modelVersion": version,
        "output": str(args.output.resolve()),
        "metadata": str(args.metadata.resolve()),
        "releaseApproved": approved,
        "releaseReasons": gate_reasons,
        "externalTest": external_metrics,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
