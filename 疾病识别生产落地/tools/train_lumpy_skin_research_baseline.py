#!/usr/bin/env python3
"""Train a clearly non-production lumpy-skin image research baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps


LABEL_DIRS = {
    "lumpy skin": "lumpy_skin",
    "normal skin": "normal_skin",
    "foot-and-mouth": "foot_and_mouth",
    "healthy": "healthy",
    "lumpy": "lumpy",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
RESIZE = (24, 24)


def release_gate(
    *, has_veterinary_signoff: bool, has_animal_grouping: bool, has_external_farm_test: bool
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not has_veterinary_signoff:
        reasons.append("veterinary sign-off is missing")
    if not has_animal_grouping:
        reasons.append("animal grouping is missing")
    if not has_external_farm_test:
        reasons.append("external farm test is missing")
    return not reasons, reasons


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def image_features(path: Path) -> np.ndarray:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB").resize(RESIZE, Image.Resampling.BILINEAR)
        pixels = np.asarray(image, dtype=np.float32) / 255.0
    values: list[float] = list(pixels.reshape(-1))
    for channel in range(3):
        channel_values = pixels[:, :, channel]
        values.extend([float(channel_values.mean()), float(channel_values.std())])
        histogram, _ = np.histogram(channel_values, bins=8, range=(0.0, 1.0))
        values.extend((histogram / max(1, channel_values.size)).astype(np.float32).tolist())
    return np.asarray(values, dtype=np.float32)


def discover(root: Path) -> tuple[list[Path], np.ndarray, list[str]]:
    paths: list[Path] = []
    labels: list[str] = []
    for directory in sorted(root.rglob("*")):
        if not directory.is_dir() or directory.name.lower() not in LABEL_DIRS:
            continue
        label = LABEL_DIRS[directory.name.lower()]
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
                paths.append(path)
                labels.append(label)
    if len(set(labels)) < 2:
        raise ValueError("dataset must contain at least two recognized class folders")
    classes = sorted(set(labels))
    class_to_index = {label: index for index, label in enumerate(classes)}
    features = np.vstack([image_features(path) for path in paths])
    return paths, features, [class_to_index[label] for label in labels]


def stratified_split(labels: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train: list[int] = []
    validation: list[int] = []
    external: list[int] = []
    for label in sorted(set(labels.tolist())):
        indices = np.flatnonzero(labels == label)
        rng.shuffle(indices)
        first = max(1, int(len(indices) * 0.70))
        second = first + max(1, int(len(indices) * 0.15))
        train.extend(indices[:first].tolist())
        validation.extend(indices[first:second].tolist())
        external.extend(indices[second:].tolist())
    return np.asarray(train), np.asarray(validation), np.asarray(external)


def softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    values = np.exp(np.clip(shifted, -40.0, 40.0))
    return values / np.maximum(values.sum(axis=1, keepdims=True), 1e-9)


def fit(features: np.ndarray, labels: np.ndarray, train: np.ndarray, epochs: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mean = features[train].mean(axis=0)
    scale = np.maximum(features[train].std(axis=0), 1e-5)
    normalized = (features[train] - mean) / scale
    class_count = int(labels.max()) + 1
    weights = np.zeros((class_count, normalized.shape[1]), dtype=np.float64)
    bias = np.zeros(class_count, dtype=np.float64)
    target = np.eye(class_count)[labels[train]]
    for _ in range(epochs):
        probabilities = softmax(normalized @ weights.T + bias)
        delta = (probabilities - target) / max(1, len(train))
        weights -= 0.08 * (delta.T @ normalized + 0.001 * weights)
        bias -= 0.08 * delta.sum(axis=0)
    return weights.astype(np.float32), bias.astype(np.float32), mean.astype(np.float32), scale.astype(np.float32)


def predict(features: np.ndarray, indices: np.ndarray, weights: np.ndarray, bias: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return np.argmax(softmax(((features[indices] - mean) / scale) @ weights.T + bias), axis=1)


def metrics(labels: np.ndarray, predictions: np.ndarray, classes: list[str]) -> dict[str, Any]:
    matrix = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for actual, predicted in zip(labels, predictions, strict=True):
        matrix[int(actual), int(predicted)] += 1
    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    for index, label in enumerate(classes):
        tp = float(matrix[index, index])
        fp = float(matrix[:, index].sum() - matrix[index, index])
        fn = float(matrix[index, :].sum() - matrix[index, index])
        precision = tp / max(1.0, tp + fp)
        recall = tp / max(1.0, tp + fn)
        f1 = 2 * precision * recall / max(1e-9, precision + recall)
        f1_values.append(f1)
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": int(matrix[index].sum())}
    return {
        "accuracy": float(np.mean(predictions == labels)),
        "macroF1": float(np.mean(f1_values)),
        "classMetrics": per_class,
        "confusionMatrix": matrix.tolist(),
        "labels": classes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-prefix", default="lumpy-skin-research")
    parser.add_argument("--seed", type=int, default=20260918)
    parser.add_argument("--epochs", type=int, default=250)
    args = parser.parse_args()

    paths, features, label_values = discover(args.data_root)
    labels = np.asarray(label_values, dtype=np.int64)
    classes = sorted(set(LABEL_DIRS.values()).intersection(set(
        LABEL_DIRS[path.parent.name.lower()] for path in paths
    )))
    train, validation, external = stratified_split(labels, args.seed)
    weights, bias, mean, scale = fit(features, labels, train, args.epochs)
    validation_metrics = metrics(labels[validation], predict(features, validation, weights, bias, mean, scale), classes)
    external_metrics = metrics(labels[external], predict(features, external, weights, bias, mean, scale), classes)
    source_hash = hashlib.sha256("\n".join(sorted(sha256(path) for path in paths)).encode()).hexdigest()
    version = f"{args.model_prefix}-{source_hash[:12]}"
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output_dir / "model.npz", weights=weights, bias=bias, mean=mean, scale=scale,
                        classes=np.asarray(classes), featureSize=np.asarray([features.shape[1]]))
    metadata = {
        "modelVersion": version,
        "status": "research_only",
        "sourceRoot": str(args.data_root.resolve()),
        "sourceImageCount": len(paths),
        "sourceFingerprint": source_hash,
        "classes": classes,
        "classCounts": dict(Counter(classes[value] for value in labels)),
        "splitPolicy": "image-level stratified split; no animal/farm/date identity was supplied",
        "validation": validation_metrics,
        "externalTest": external_metrics,
        "releaseGate": {"approved": False, "reasons": [
            "veterinary sign-off is missing",
            "animal grouping is missing",
            "external farm test is missing",
            "artifact is not a MaixCAM .mud model",
        ]},
        "labelPolicy": "All labels are research image labels only; they are not a veterinary diagnosis or release authorization.",
        "generatedAt": datetime.now(UTC).isoformat(),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "model_card.md").write_text(
        "# Cattle disease image research baseline\n\n"
        f"- Version: `{version}`\n- Status: `research_only`\n"
        f"- Classes: {', '.join(classes)}\n- Images: {len(paths)}\n- External accuracy: {external_metrics['accuracy']:.3f}\n"
        f"- External macro-F1: {external_metrics['macroF1']:.3f}\n\n"
        "This artifact is not a veterinary model, not an FMD model, and not a MaixCAM deployment artifact. "
        "Its image-level split has no animal/farm grouping and cannot support production claims.\n",
        encoding="utf-8",
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
