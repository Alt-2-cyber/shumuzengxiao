#!/usr/bin/env python3
"""Train and release-gate the lightweight cattle sound classifier for ESP32.

The extractor mirrors the 8 kHz, 2 s feature path in ``src/main.cpp``.
It is an acoustic-event screening model, never a veterinary diagnosis. A
generated model stays disabled unless ``--release`` succeeds against explicit
clinical-data and validation gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import wave
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


FEATURE_RATE = 8_000
FRAME_SIZE = 128
GOERTZEL_BINS = (2, 4, 8, 16, 32, 48)
FEATURE_COUNT = 10
SUPPORTED_SUFFIXES = {".wav"}
TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")
RESPIRATORY_LABELS = {"cough_suspect", "wheeze_suspect"}
VOCALIZATION_LABELS = {"abnormal_vocalization_suspect"}
RISK_LABELS = RESPIRATORY_LABELS | VOCALIZATION_LABELS


@dataclass(frozen=True)
class AudioClip:
    path: Path
    label: str
    group_id: str
    source_id: str
    clinical_verified: bool
    allow_for_disease_labels: bool
    metadata: dict[str, Any]


@dataclass(frozen=True)
class FeatureRow:
    values: np.ndarray
    label: str
    group_id: str
    source_id: str
    path: Path
    clinical_verified: bool
    allow_for_disease_labels: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--dataset", type=Path,
                        help="Legacy class-folder directory of PCM WAV files")
    source.add_argument("--manifest", type=Path,
                        help="Prepared JSONL manifest from prepare_audio_dataset.py")
    parser.add_argument("--output", type=Path,
                        default=Path("../include/cattle_audio_model.h"),
                        help="Generated ESP32 header path")
    parser.add_argument("--metadata", type=Path,
                        default=Path("audio_model_metadata.json"),
                        help="JSON training report path")
    parser.add_argument("--model-card", type=Path,
                        default=Path("audio_model_card.md"),
                        help="Markdown model card path")
    parser.add_argument("--model-name", default="cattle-audio-softmax-v2")
    parser.add_argument("--epochs", type=int, default=1_200)
    parser.add_argument("--learning-rate", type=float, default=0.06)
    parser.add_argument("--l2", type=float, default=0.001)
    parser.add_argument("--validation-ratio", type=float, default=0.2,
                        help="Only used with --dataset; manifests keep their declared split")
    parser.add_argument("--window-seconds", type=float, default=2.0,
                        help="Feature window matching SAMPLE_INTERVAL_MS in firmware")
    parser.add_argument("--window-hop-seconds", type=float, default=2.0)
    parser.add_argument("--max-windows-per-clip", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--release", action="store_true",
                        help="Enable the generated header only when every production gate passes")
    parser.add_argument("--required-clinical-labels",
                        default="cough_suspect,wheeze_suspect,abnormal_vocalization_suspect",
                        help="Comma-separated risk labels required for a release")
    parser.add_argument("--minimum-clinical-files", type=int, default=100)
    parser.add_argument("--minimum-validation-groups", type=int, default=3)
    parser.add_argument("--minimum-macro-f1", type=float, default=0.75)
    parser.add_argument("--minimum-risk-precision", type=float, default=0.80)
    parser.add_argument("--minimum-risk-recall", type=float, default=0.70)
    parser.add_argument("--clinical-api",
                        help="Clinical backend base URL used to recheck platform audio lineage before --release")
    parser.add_argument("--clinical-api-key", default=os.environ.get("CLINICAL_API_KEY", ""),
                        help="Clinical API key; defaults to CLINICAL_API_KEY")
    parser.add_argument("--lineage-timeout-seconds", type=int, default=20,
                        help="Timeout for each platform lineage recheck during --release")
    return parser.parse_args()


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        channels = source.getnchannels()
        width = source.getsampwidth()
        rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    if channels < 1 or rate <= 0:
        raise ValueError("invalid WAV stream")
    if width == 1:
        values = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
        values = (values - 128.0) / 128.0
    elif width == 2:
        values = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
    elif width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        values = (raw[:, 0].astype(np.int32) |
                  (raw[:, 1].astype(np.int32) << 8) |
                  (raw[:, 2].astype(np.int32) << 16))
        values = np.where(values & 0x800000, values - 0x1000000, values).astype(np.float32)
        values /= 8388608.0
    elif width == 4:
        values = np.frombuffer(frames, dtype="<i4").astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"unsupported sample width: {width}")
    if values.size == 0:
        raise ValueError("empty WAV stream")
    values = values.reshape(-1, channels).mean(axis=1)
    return values, rate


def resample(samples: np.ndarray, source_rate: int) -> np.ndarray:
    if source_rate == FEATURE_RATE:
        return samples.astype(np.float32, copy=False)
    target_count = max(1, round(samples.size * FEATURE_RATE / source_rate))
    source_x = np.linspace(0.0, 1.0, samples.size, endpoint=False)
    target_x = np.linspace(0.0, 1.0, target_count, endpoint=False)
    return np.interp(target_x, source_x, samples).astype(np.float32)


def goertzel_energy(frame: np.ndarray, frequency_bin: int) -> float:
    coefficient = 2.0 * math.cos(2.0 * math.pi * frequency_bin / FRAME_SIZE)
    previous = 0.0
    previous_previous = 0.0
    for sample in frame:
        current = float(sample) + coefficient * previous - previous_previous
        previous_previous = previous
        previous = current
    return max(0.0, previous_previous * previous_previous + previous * previous -
               coefficient * previous * previous_previous)


def extract_features(samples: np.ndarray, source_rate: int) -> np.ndarray:
    audio = resample(samples, source_rate)
    if audio.size < FRAME_SIZE:
        audio = np.pad(audio, (0, FRAME_SIZE - audio.size))
    audio = audio - float(np.mean(audio))
    complete = (audio.size // FRAME_SIZE) * FRAME_SIZE
    audio = audio[:complete]
    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    crossings = np.count_nonzero((audio[1:] >= 0.0) != (audio[:-1] >= 0.0))
    zcr = float(crossings / max(1, audio.size))
    difference_energy = float(np.sum(np.square(np.diff(audio))))
    energy = float(np.sum(np.square(audio)))
    bands = np.zeros(len(GOERTZEL_BINS), dtype=np.float64)
    for start in range(0, audio.size, FRAME_SIZE):
        frame = audio[start:start + FRAME_SIZE]
        for index, frequency_bin in enumerate(GOERTZEL_BINS):
            bands[index] += goertzel_energy(frame, frequency_bin)
    band_total = max(float(np.sum(bands)), 1e-9)
    features = np.empty(FEATURE_COUNT, dtype=np.float32)
    features[0] = math.log(max(rms, 1e-5))
    features[1] = zcr
    features[2] = min(10.0, peak / max(rms, 1e-5))
    features[3:9] = np.log(np.maximum(bands / band_total, 1e-6))
    features[9] = math.log(max(math.sqrt(difference_energy / max(energy, 1e-9)), 1e-6))
    return features


def window_features(samples: np.ndarray, rate: int, window_seconds: float,
                    hop_seconds: float, maximum: int) -> list[np.ndarray]:
    if window_seconds <= 0.0 or hop_seconds <= 0.0 or maximum < 1:
        raise ValueError("window seconds, hop seconds, and maximum windows must be positive")
    audio = resample(samples, rate)
    window_size = max(FRAME_SIZE, round(window_seconds * FEATURE_RATE))
    hop_size = max(1, round(hop_seconds * FEATURE_RATE))
    if audio.size <= window_size:
        starts = [0]
    else:
        starts = list(range(0, audio.size - window_size + 1, hop_size))
        final_start = audio.size - window_size
        if starts[-1] != final_start:
            starts.append(final_start)
    if len(starts) > maximum:
        positions = np.linspace(0, len(starts) - 1, num=maximum, dtype=int)
        starts = [starts[int(position)] for position in positions]
    rows: list[np.ndarray] = []
    for start in starts:
        segment = audio[start:start + window_size]
        if segment.size < window_size:
            segment = np.pad(segment, (0, window_size - segment.size))
        rows.append(extract_features(segment, FEATURE_RATE))
    return rows


def load_legacy_dataset(dataset: Path) -> list[AudioClip]:
    if not dataset.is_dir():
        raise ValueError(f"dataset directory does not exist: {dataset}")
    clips: list[AudioClip] = []
    classes = sorted(path.name for path in dataset.iterdir()
                     if path.is_dir() and not path.name.startswith("."))
    if len(classes) < 2:
        raise ValueError("at least two class folders are required")
    for label in classes:
        if not TOKEN.fullmatch(label):
            raise ValueError("class folder names must use A-Z, a-z, 0-9, _, . or -")
        for path in sorted(candidate for candidate in (dataset / label).rglob("*")
                           if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES):
            clips.append(AudioClip(
                path=path.resolve(),
                label=label,
                group_id=f"legacy:{label}:{path.stem}",
                source_id="legacy_unverified",
                clinical_verified=False,
                allow_for_disease_labels=False,
                metadata={"input": "legacy_class_folder"},
            ))
    return clips


def load_manifest(manifest_path: Path) -> tuple[list[AudioClip], dict[str, Any]]:
    if not manifest_path.is_file():
        raise ValueError(f"manifest does not exist: {manifest_path}")
    clips: list[AudioClip] = []
    fingerprints: list[str] = []
    seen_paths: set[Path] = set()
    seen_hashes: dict[str, tuple[str, str, Path]] = {}
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            label = str(record["label"])
            relative = Path(str(record["path"]))
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid manifest line {line_number}: {error}") from error
        if not TOKEN.fullmatch(label):
            raise ValueError(f"invalid label on manifest line {line_number}: {label}")
        path = relative if relative.is_absolute() else (manifest_path.parent / relative)
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"audio path is missing on manifest line {line_number}: {path}")
        if path in seen_paths:
            raise ValueError(f"same audio path appears twice in manifest: {path}")
        seen_paths.add(path)
        group_id = str(record.get("groupId") or f"manifest:{label}:{path.stem}")
        source_id = str(record.get("sourceId") or "manifest_unspecified")
        content_hash = file_sha256(path)
        for field in ("normalizedSha256", "rawSha256", "platformClipSha256"):
            declared = str(record.get(field) or "").strip().lower()
            if declared and declared != content_hash:
                raise ValueError(
                    f"audio SHA-256 mismatch for manifest line {line_number}: {field} does not match {path}")
        previous = seen_hashes.get(content_hash)
        if previous is not None:
            previous_label, previous_group, previous_path = previous
            if previous_label != label or previous_group != group_id:
                raise ValueError(
                    "identical audio crosses labels or groups: "
                    f"{previous_path} ({previous_label}, {previous_group}) vs "
                    f"{path} ({label}, {group_id})")
            continue
        seen_hashes[content_hash] = (label, group_id, path)
        clips.append(AudioClip(
            path=path,
            label=label,
            group_id=group_id,
            source_id=source_id,
            clinical_verified=bool(record.get("clinicalVerified", False)),
            allow_for_disease_labels=bool(record.get("allowForDiseaseLabels", False)),
            metadata=record,
        ))
        fingerprints.append("|".join([
            source_id, label, group_id, content_hash,
            str(bool(record.get("clinicalVerified", False))),
            str(record.get("sourceEventId") or ""),
            str(record.get("platformClipSha256") or "").lower(),
            str(record.get("animalId") or ""),
            str(record.get("recordingSessionId") or ""),
            str(record.get("veterinarian") or ""),
            str(record.get("clinicalEvidenceReference") or ""),
        ]))
    if len(clips) < 8:
        raise ValueError("manifest needs at least eight valid clips")
    digest = hashlib.sha256("\n".join(sorted(fingerprints)).encode("utf-8")).hexdigest()
    return clips, {"manifest": str(manifest_path.resolve()), "fingerprint": digest}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def required_text(record: dict[str, Any], field: str, line_number: int) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise ValueError(f"disease-label manifest line {line_number} has no {field}")
    return value


def clinical_lineage_records(manifest_path: Path) -> list[tuple[int, dict[str, Any]]]:
    """Return every clip in a disease-model release manifest.

    Normal, moo, and barn-noise rows shape the decision boundary just as much
    as cough/wheeze rows. Letting them bypass archive verification would allow
    silent data substitution and invalidate the release evidence.
    """
    records: list[tuple[int, dict[str, Any]]] = []
    for line_number, line in enumerate(manifest_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid manifest line {line_number}: {error}") from error
        records.append((line_number, record))
    return records


def fetch_json(url: str, api_key: str, timeout_seconds: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        raise ValueError(f"clinical lineage API returned HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise ValueError(f"cannot reach clinical lineage API: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("clinical lineage API returned a non-object response")
    return payload


def verify_release_lineage(args: argparse.Namespace) -> dict[str, Any]:
    """Recheck every disease-labelled WAV against the protected platform archive.

    A local JSONL file is useful for reproducibility but is not an authority for
    clinical truth. During --release, each risk-labelled row must map to the
    archived event, current WAV hash, clinical signature fields, and confirmed
    review held by the clinical API.
    """
    if not args.manifest:
        raise ValueError("--release requires --manifest; legacy class folders cannot release a disease model")
    if not args.clinical_api or not args.clinical_api_key:
        raise ValueError("--release requires --clinical-api and --clinical-api-key for platform lineage recheck")
    if args.lineage_timeout_seconds < 1 or args.lineage_timeout_seconds > 120:
        raise ValueError("lineage timeout must be between 1 and 120 seconds")

    base_url = args.clinical_api.rstrip("/")
    checked: list[dict[str, Any]] = []
    seen_events: set[str] = set()
    risk_rows = 0
    for line_number, record in clinical_lineage_records(args.manifest):
        label = required_text(record, "label", line_number)
        if label in RISK_LABELS:
            risk_rows += 1
        event_id = required_text(record, "sourceEventId", line_number)
        if event_id in seen_events:
            raise ValueError(f"disease-label manifest reuses sourceEventId {event_id}")
        seen_events.add(event_id)
        local_hash = required_text(record, "platformClipSha256", line_number).lower()
        if not re.fullmatch(r"[a-f0-9]{64}", local_hash):
            raise ValueError(f"disease-label manifest line {line_number} has invalid platformClipSha256")
        for field in ("animalId", "recordingSessionId", "veterinarian", "clinicalEvidenceReference"):
            required_text(record, field, line_number)
        if not bool(record.get("clinicalVerified", False)) or not bool(record.get("allowForDiseaseLabels", False)):
            raise ValueError(f"disease-label manifest line {line_number} is not clinically eligible")

        endpoint = urllib.parse.urljoin(base_url + "/", f"api/events/audio/{urllib.parse.quote(event_id, safe='')}/training-lineage")
        remote = fetch_json(endpoint, args.clinical_api_key, args.lineage_timeout_seconds)
        comparisons = {
            "sourceEventId": (str(remote.get("sourceEventId") or ""), event_id),
            "clipSha256": (str(remote.get("clipSha256") or "").lower(), local_hash),
            "reviewLabel": (str(remote.get("reviewLabel") or ""), label),
            "clinicalAnimalId": (str(remote.get("clinicalAnimalId") or ""), str(record.get("animalId") or "")),
            "recordingSessionId": (str(remote.get("recordingSessionId") or ""), str(record.get("recordingSessionId") or "")),
            "veterinarian": (str(remote.get("veterinarian") or ""), str(record.get("veterinarian") or "")),
            "clinicalEvidenceReference": (
                str(remote.get("clinicalEvidenceReference") or ""),
                str(record.get("clinicalEvidenceReference") or "")),
        }
        mismatched = [field for field, (actual, expected) in comparisons.items() if actual != expected]
        if remote.get("reviewStatus") not in {"confirmed", "normal"}:
            mismatched.append("reviewStatus")
        if not remote.get("clinicallyVerifiedAt"):
            mismatched.append("clinicallyVerifiedAt")
        if remote.get("clipIntegrityVerified") is not True:
            mismatched.append("clipIntegrityVerified")
        if mismatched:
            raise ValueError(
                f"platform lineage mismatch for sourceEventId {event_id} on manifest line {line_number}: "
                + ", ".join(mismatched))
        checked.append({
            "sourceEventId": event_id,
            "clipSha256": local_hash,
            "label": label,
            "reviewStatus": str(remote.get("reviewStatus") or ""),
            "clinicalAnimalId": required_text(record, "animalId", line_number),
            "recordingSessionId": required_text(record, "recordingSessionId", line_number),
            "veterinarian": required_text(record, "veterinarian", line_number),
            "clinicalEvidenceReference": required_text(record, "clinicalEvidenceReference", line_number),
            "clinicallyVerifiedAt": str(remote.get("clinicallyVerifiedAt") or ""),
            "integrityVerifiedAt": remote.get("integrityVerifiedAt"),
        })

    if not checked or risk_rows == 0:
        raise ValueError("--release needs at least one disease-labelled platform audio event")
    fingerprint_records = [
        {key: record[key] for key in (
            "sourceEventId", "clipSha256", "label", "reviewStatus", "clinicalAnimalId",
            "recordingSessionId", "veterinarian", "clinicalEvidenceReference", "clinicallyVerifiedAt")}
        for record in checked
    ]
    digest = hashlib.sha256(json.dumps(fingerprint_records, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        "checked": len(checked),
        "sourceEventIds": [item["sourceEventId"] for item in checked],
        "records": checked,
        "fingerprint": digest,
        "api": base_url,
    }


def group_split(clips: list[AudioClip], ratio: float, seed: int) -> tuple[set[str], set[str]]:
    if not 0.05 <= ratio < 0.5:
        raise ValueError("validation ratio must be between 0.05 and 0.5")
    groups: dict[str, list[AudioClip]] = defaultdict(list)
    for clip in clips:
        groups[clip.group_id].append(clip)
    labels_by_group = {group: {clip.label for clip in values} for group, values in groups.items()}
    classes = sorted({clip.label for clip in clips})
    groups_for_label = {
        label: [group for group, labels in labels_by_group.items() if label in labels]
        for label in classes
    }
    for label, identifiers in groups_for_label.items():
        if len(identifiers) < 2:
            raise ValueError(f"label {label} needs at least two independent groups")
    generator = np.random.default_rng(seed)
    ordered = list(groups)
    generator.shuffle(ordered)
    total_by_label = Counter(clip.label for clip in clips)
    target_by_label = {label: total_by_label[label] * ratio for label in classes}
    validation: set[str] = set()
    validation_count: Counter[str] = Counter()
    validation_target_groups = min(len(groups) - 1, max(1, round(len(groups) * ratio)))
    # Seed every class into validation. A group can satisfy several labels.
    for label in classes:
        if validation_count[label] > 0:
            continue
        candidates = [group for group in ordered if group not in validation and label in labels_by_group[group]]
        candidates.sort(key=lambda group: len(labels_by_group[group]))
        chosen = candidates[0]
        validation.add(chosen)
        validation_count.update(clip.label for clip in groups[chosen])
    # Fill the approximate group budget by minimizing class-count imbalance.
    while len(validation) < validation_target_groups:
        candidates = [group for group in ordered if group not in validation]
        if not candidates:
            break
        def score(group: str) -> float:
            proposed = validation_count.copy()
            proposed.update(clip.label for clip in groups[group])
            return sum(((proposed[label] - target_by_label[label]) /
                        max(target_by_label[label], 1.0)) ** 2 for label in classes)
        chosen = min(candidates, key=score)
        validation.add(chosen)
        validation_count.update(clip.label for clip in groups[chosen])
    train = set(groups) - validation
    for label in classes:
        if not any(label in labels_by_group[group] for group in train):
            raise ValueError(f"group split leaves no training samples for {label}")
        if not any(label in labels_by_group[group] for group in validation):
            raise ValueError(f"group split leaves no validation samples for {label}")
    return train, validation


def build_rows(clips: list[AudioClip], args: argparse.Namespace) -> list[FeatureRow]:
    rows: list[FeatureRow] = []
    errors: list[str] = []
    for clip in clips:
        try:
            samples, rate = read_wav(clip.path)
            features = window_features(samples, rate, args.window_seconds,
                                       args.window_hop_seconds, args.max_windows_per_clip)
            rows.extend(FeatureRow(
                values=values,
                label=clip.label,
                group_id=clip.group_id,
                source_id=clip.source_id,
                path=clip.path,
                clinical_verified=clip.clinical_verified,
                allow_for_disease_labels=clip.allow_for_disease_labels,
            ) for values in features)
        except (OSError, ValueError, wave.Error) as error:
            errors.append(f"{clip.path}: {error}")
    if errors:
        raise ValueError("unreadable audio clips:\n" + "\n".join(errors[:10]))
    return rows


def softmax(values: np.ndarray) -> np.ndarray:
    shifted = values - np.max(values, axis=1, keepdims=True)
    exponentials = np.exp(shifted)
    return exponentials / np.sum(exponentials, axis=1, keepdims=True)


def train_softmax(features: np.ndarray, labels: np.ndarray, train_indices: np.ndarray,
                  epochs: int, learning_rate: float, l2: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    train_features = features[train_indices]
    mean = train_features.mean(axis=0)
    scale = np.maximum(train_features.std(axis=0), 1e-5)
    normalized = (train_features - mean) / scale
    class_count = int(labels.max()) + 1
    weights = np.zeros((class_count, FEATURE_COUNT), dtype=np.float64)
    bias = np.zeros(class_count, dtype=np.float64)
    targets = np.eye(class_count, dtype=np.float64)[labels[train_indices]]
    for _ in range(epochs):
        probabilities = softmax(normalized @ weights.T + bias)
        delta = (probabilities - targets) / normalized.shape[0]
        weights -= learning_rate * (delta.T @ normalized + l2 * weights)
        bias -= learning_rate * delta.sum(axis=0)
    return weights.astype(np.float32), bias.astype(np.float32), mean.astype(np.float32), scale.astype(np.float32)


def prediction_probabilities(features: np.ndarray, indices: np.ndarray, weights: np.ndarray,
                             bias: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    normalized = (features[indices] - mean) / scale
    return softmax(normalized @ weights.T + bias)


def class_centroids(features: np.ndarray, labels: np.ndarray, train_indices: np.ndarray,
                    mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    normalized = (features - mean) / scale
    return np.vstack([normalized[train_indices][labels[train_indices] == category].mean(axis=0)
                      for category in range(int(labels.max()) + 1)]).astype(np.float32)


def class_distance_limits(features: np.ndarray, labels: np.ndarray, validation_indices: np.ndarray,
                          weights: np.ndarray, bias: np.ndarray, mean: np.ndarray,
                          scale: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    normalized = (features[validation_indices] - mean) / scale
    probabilities = softmax(normalized @ weights.T + bias)
    predicted = np.argmax(probabilities, axis=1)
    true = labels[validation_indices]
    limits: list[float] = []
    for category in range(centroids.shape[0]):
        mask = (true == category) & (predicted == category)
        pool = normalized[mask] if np.any(mask) else normalized[true == category]
        distances = np.sum(np.square(pool - centroids[category]), axis=1)
        limits.append(float(max(1e-4, np.quantile(distances, 0.975) * 1.05)))
    return np.asarray(limits, dtype=np.float32)


def evaluate(true: np.ndarray, predicted: np.ndarray, classes: list[str]) -> dict[str, Any]:
    class_count = len(classes)
    confusion = np.zeros((class_count, class_count + 1), dtype=np.int64)
    for observed, estimate in zip(true, predicted, strict=True):
        confusion[int(observed), int(estimate) if estimate >= 0 else class_count] += 1
    metrics: dict[str, dict[str, float | int]] = {}
    scores: list[float] = []
    for category, label in enumerate(classes):
        true_positive = int(confusion[category, category])
        false_positive = int(confusion[:, category].sum() - true_positive)
        false_negative = int(confusion[category, :].sum() - true_positive)
        precision = true_positive / max(1, true_positive + false_positive)
        recall = true_positive / max(1, true_positive + false_negative)
        f1 = 2.0 * precision * recall / max(1e-9, precision + recall)
        scores.append(f1)
        metrics[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": int(confusion[category, :].sum()),
        }
    return {
        "accuracy": float(np.mean(predicted == true)),
        "macroF1": float(np.mean(scores)),
        "classMetrics": metrics,
        "confusionMatrix": confusion.tolist(),
        "confusionLabels": [*classes, "unknown"],
        "rejectionRate": float(np.mean(predicted < 0)),
    }


def calibrate_confidence(probabilities: np.ndarray, labels: np.ndarray, classes: list[str]) -> float:
    raw = np.argmax(probabilities, axis=1)
    best_score = -1.0
    best_threshold = 0.5
    confidence = np.max(probabilities, axis=1)
    for threshold in np.linspace(0.40, 0.95, num=23):
        predicted = np.where(confidence >= threshold, raw, -1)
        value = float(evaluate(labels, predicted, classes)["macroF1"])
        if value > best_score + 1e-9 or (abs(value - best_score) <= 1e-9 and threshold > best_threshold):
            best_score = value
            best_threshold = float(threshold)
    return best_threshold


def cpp_float(value: float) -> str:
    text = f"{float(value):.8g}"
    if "e" not in text and "." not in text:
        text += ".0"
    return text + "f"


def array_literal(values: np.ndarray) -> str:
    return ", ".join(cpp_float(value) for value in values.ravel())


def export_header(output: Path, classes: list[str], weights: np.ndarray, bias: np.ndarray,
                  mean: np.ndarray, scale: np.ndarray, centroids: np.ndarray,
                  distance_limits: np.ndarray, minimum_confidence: float,
                  model_version: str, validation: dict[str, Any], enabled: bool) -> None:
    labels = ", ".join(f'"{label}"' for label in classes)
    rows = ",\n    ".join("{" + array_literal(row) + "}" for row in weights)
    centroid_rows = ",\n    ".join("{" + array_literal(row) + "}" for row in centroids)
    respiratory = [label for label in classes if label in RESPIRATORY_LABELS]
    respiratory_check = " || ".join(f'strcmp(label, "{label}") == 0' for label in respiratory) or "false"
    vocalization = [label for label in classes if label in VOCALIZATION_LABELS]
    vocalization_check = " || ".join(f'strcmp(label, "{label}") == 0' for label in vocalization) or "false"
    header = f'''#pragma once

#include <Arduino.h>
#include <math.h>
#include <string.h>

// Generated by tools/train_audio_model.py. This model is an acoustic screening
// component, not a veterinary diagnosis. Deployment status: {"approved" if enabled else "disabled"}.
namespace cattle_audio_model {{

constexpr bool kEnabled = {str(enabled).lower()};
constexpr uint8_t kFeatureCount = {FEATURE_COUNT};
constexpr uint8_t kClassCount = {len(classes)};
constexpr const char *kVersion = "{model_version}";
constexpr float kValidationAccuracy = {cpp_float(float(validation["accuracy"]))};
constexpr float kValidationMacroF1 = {cpp_float(float(validation["macroF1"]))};
constexpr float kMinimumConfidence = {cpp_float(minimum_confidence)};
static const char *const kLabels[kClassCount] = {{{labels}}};
static const float kMean[kFeatureCount] = {{{array_literal(mean)}}};
static const float kScale[kFeatureCount] = {{{array_literal(scale)}}};
static const float kWeights[kClassCount][kFeatureCount] = {{
    {rows}
}};
static const float kBias[kClassCount] = {{{array_literal(bias)}}};
static const float kCentroids[kClassCount][kFeatureCount] = {{
    {centroid_rows}
}};
static const float kDistanceLimits[kClassCount] = {{{array_literal(distance_limits)}}};

struct Prediction {{
  const char *label;
  float score;
}};

inline Prediction predict(const float *features) {{
  float scores[kClassCount];
  float highest = -INFINITY;
  for (uint8_t category = 0; category < kClassCount; category++) {{
    float score = kBias[category];
    for (uint8_t feature = 0; feature < kFeatureCount; feature++) {{
      score += ((features[feature] - kMean[feature]) / kScale[feature]) *
               kWeights[category][feature];
    }}
    scores[category] = score;
    highest = max(highest, score);
  }}
  float total = 0.0f;
  for (uint8_t category = 0; category < kClassCount; category++) {{
    scores[category] = expf(scores[category] - highest);
    total += scores[category];
  }}
  uint8_t best = 0;
  for (uint8_t category = 1; category < kClassCount; category++) {{
    if (scores[category] > scores[best]) {{
      best = category;
    }}
  }}
  const float confidence = total > 0.0f ? scores[best] / total : 0.0f;
  float distance = 0.0f;
  for (uint8_t feature = 0; feature < kFeatureCount; feature++) {{
    const float normalized = (features[feature] - kMean[feature]) / kScale[feature];
    const float delta = normalized - kCentroids[best][feature];
    distance += delta * delta;
  }}
  if (confidence < kMinimumConfidence || distance > kDistanceLimits[best]) {{
    return {{"unknown", confidence}};
  }}
  return {{kLabels[best], confidence}};
}}

inline bool isRespiratoryLabel(const char *label) {{
  return {respiratory_check};
}}

inline bool isAbnormalVocalizationLabel(const char *label) {{
  return {vocalization_check};
}}

inline bool isScreeningLabel(const char *label) {{
  return isRespiratoryLabel(label) || isAbnormalVocalizationLabel(label);
}}

}}  // namespace cattle_audio_model
'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(header, encoding="utf-8", newline="\n")


def release_gate(args: argparse.Namespace, clips: list[AudioClip], classes: list[str],
                 validation_groups: dict[str, int], validation: dict[str, Any],
                 lineage: dict[str, Any] | None) -> tuple[bool, list[str], list[str]]:
    required = [label.strip() for label in args.required_clinical_labels.split(",") if label.strip()]
    if any(label not in RISK_LABELS for label in required):
        raise ValueError(
            "required clinical labels must be cough_suspect, wheeze_suspect, "
            "and/or abnormal_vocalization_suspect")
    reasons: list[str] = []
    if not args.release:
        reasons.append("release was not requested; generated header remains disabled")
    if args.release and lineage is None:
        reasons.append("clinical platform lineage was not rechecked")
    if args.release and lineage is not None and int(lineage.get("checked", 0)) != len(clips):
        reasons.append(
            "clinical platform lineage record count does not match the unique training clip count")
    for label in required:
        label_clips = [clip for clip in clips if clip.label == label]
        if label not in classes:
            reasons.append(f"required clinical label is absent: {label}")
            continue
        if len(label_clips) < args.minimum_clinical_files:
            reasons.append(
                f"{label} has {len(label_clips)} clips; minimum is {args.minimum_clinical_files}")
        if any(not clip.clinical_verified for clip in label_clips):
            reasons.append(f"{label} contains clips without veterinary clinical verification")
        if any(not clip.allow_for_disease_labels for clip in label_clips):
            reasons.append(f"{label} contains clips from a source not approved for disease labels")
        if validation_groups.get(label, 0) < args.minimum_validation_groups:
            reasons.append(
                f"{label} has {validation_groups.get(label, 0)} validation groups; minimum is {args.minimum_validation_groups}")
        metric = validation["classMetrics"].get(label, {})
        if float(metric.get("precision", 0.0)) < args.minimum_risk_precision:
            reasons.append(
                f"{label} validation precision {float(metric.get('precision', 0.0)):.3f} is below {args.minimum_risk_precision:.3f}")
        if float(metric.get("recall", 0.0)) < args.minimum_risk_recall:
            reasons.append(
                f"{label} validation recall {float(metric.get('recall', 0.0)):.3f} is below {args.minimum_risk_recall:.3f}")
    if float(validation["macroF1"]) < args.minimum_macro_f1:
        reasons.append(
            f"validation macro F1 {float(validation['macroF1']):.3f} is below {args.minimum_macro_f1:.3f}")
    return args.release and not reasons, required, reasons


def write_model_card(path: Path, report: dict[str, Any]) -> None:
    validation = report["validation"]
    gate = report["releaseGate"]
    lines = [
        "# Cattle Audio Model Card",
        "",
        f"- Model version: `{report['modelVersion']}`",
        f"- Deployment status: `{'approved' if gate['approved'] else 'disabled'}`",
        f"- Input: {report['featureRateHz']} Hz mono audio, {report['windowSeconds']} s feature windows",
        f"- Labels: {', '.join('`' + label + '`' for label in report['classes'])}",
        f"- Dataset fingerprint: `{report['datasetFingerprint']}`",
        f"- Validation groups: {report['validationGroups']}; windows: {report['validationSamples']}",
        f"- Validation accuracy: {validation['accuracy']:.4f}; macro F1: {validation['macroF1']:.4f}",
        f"- Confidence threshold: {report['minimumConfidence']:.2f}; OOD rejection is enabled in the header.",
        "",
        "## Per-class validation",
        "",
        "| Label | Precision | Recall | F1 | Support |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for label, metrics in validation["classMetrics"].items():
        lines.append(
            f"| `{label}` | {metrics['precision']:.3f} | {metrics['recall']:.3f} | "
            f"{metrics['f1']:.3f} | {metrics['support']} |")
    lines.extend([
        "",
        "## Release gate",
        "",
        f"Required clinical labels: {', '.join(gate['requiredClinicalLabels']) or 'none'}",
    ])
    if gate["reasons"]:
        lines.extend(f"- {reason}" for reason in gate["reasons"])
    else:
        lines.append("- All release gates passed.")
    lines.extend([
        "",
        "## Scope and safety",
        "",
        "This model flags acoustic events only. It must not diagnose a disease or trigger treatment on its own. A respiratory-risk workflow requires audio playback, clinical review, temperature/behavior/environment evidence, and veterinary escalation when symptoms persist.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> None:
    args = parse_args()
    if args.epochs < 1 or args.learning_rate <= 0.0 or args.l2 < 0.0:
        raise SystemExit("epochs, learning rate, and l2 must be valid non-negative training values")
    if not 0.1 <= args.window_seconds <= 10.0 or not 0.1 <= args.window_hop_seconds <= 10.0:
        raise SystemExit("window seconds and hop seconds must be between 0.1 and 10")
    lineage: dict[str, Any] | None = None
    if args.release:
        try:
            lineage = verify_release_lineage(args)
        except ValueError as error:
            raise SystemExit(f"release lineage check failed: {error}") from error
    if args.manifest:
        clips, dataset_metadata = load_manifest(args.manifest)
        declared_split = {str(clip.metadata.get("split", "")) for clip in clips}
        if declared_split == {"train", "validation"}:
            train_groups = {clip.group_id for clip in clips if clip.metadata.get("split") == "train"}
            validation_groups_set = {clip.group_id for clip in clips if clip.metadata.get("split") == "validation"}
            if train_groups & validation_groups_set:
                raise SystemExit("manifest leaks one group into both train and validation")
        else:
            train_groups, validation_groups_set = group_split(clips, args.validation_ratio, args.seed)
    else:
        clips = load_legacy_dataset(args.dataset)
        dataset_metadata = {"dataset": str(args.dataset.resolve()), "fingerprint": "legacy-unverified"}
        train_groups, validation_groups_set = group_split(clips, args.validation_ratio, args.seed)
    if train_groups & validation_groups_set:
        raise SystemExit("group split overlap detected")
    rows = build_rows(clips, args)
    classes = sorted({row.label for row in rows})
    if len(classes) < 2:
        raise SystemExit("at least two valid classes are required")
    class_index = {label: index for index, label in enumerate(classes)}
    features = np.vstack([row.values for row in rows])
    labels = np.asarray([class_index[row.label] for row in rows], dtype=np.int64)
    train_indices = np.asarray([index for index, row in enumerate(rows) if row.group_id in train_groups], dtype=np.int64)
    validation_indices = np.asarray([index for index, row in enumerate(rows)
                                     if row.group_id in validation_groups_set], dtype=np.int64)
    if train_indices.size == 0 or validation_indices.size == 0:
        raise SystemExit("group split produced an empty train or validation partition")
    if set(labels[train_indices]) != set(range(len(classes))) or set(labels[validation_indices]) != set(range(len(classes))):
        raise SystemExit("every class must appear in both train and validation partitions")
    weights, bias, mean, scale = train_softmax(
        features, labels, train_indices, args.epochs, args.learning_rate, args.l2)
    probabilities = prediction_probabilities(features, validation_indices, weights, bias, mean, scale)
    raw_prediction = np.argmax(probabilities, axis=1)
    raw_validation = evaluate(labels[validation_indices], raw_prediction, classes)
    confidence = calibrate_confidence(probabilities, labels[validation_indices], classes)
    centroids = class_centroids(features, labels, train_indices, mean, scale)
    distance_limits = class_distance_limits(
        features, labels, validation_indices, weights, bias, mean, scale, centroids)
    normalized_validation = (features[validation_indices] - mean) / scale
    predicted_distances = np.sum(
        np.square(normalized_validation - centroids[raw_prediction]), axis=1)
    gated_prediction = np.where(
        (np.max(probabilities, axis=1) >= confidence) &
        (predicted_distances <= distance_limits[raw_prediction]), raw_prediction, -1)
    validation = evaluate(labels[validation_indices], gated_prediction, classes)
    validation_group_counts = {
        label: len({row.group_id for row in rows
                    if row.group_id in validation_groups_set and row.label == label})
        for label in classes
    }
    approved, required_labels, gate_reasons = release_gate(
        args, clips, classes, validation_group_counts, validation, lineage)
    model_version = f"{args.model_name}-{dataset_metadata['fingerprint'][:12]}"
    export_header(args.output, classes, weights, bias, mean, scale, centroids,
                  distance_limits, confidence, model_version, validation, approved)
    report = {
        "modelVersion": model_version,
        "generatedAt": datetime.now(UTC).isoformat(),
        "featureRateHz": FEATURE_RATE,
        "featureCount": FEATURE_COUNT,
        "windowSeconds": args.window_seconds,
        "windowHopSeconds": args.window_hop_seconds,
        "maxWindowsPerClip": args.max_windows_per_clip,
        "classes": classes,
        "sourceClipCount": len(clips),
        "sampleCount": int(features.shape[0]),
        "trainSamples": int(train_indices.size),
        "validationSamples": int(validation_indices.size),
        "trainGroups": len(train_groups),
        "validationGroups": len(validation_groups_set),
        "validationGroupsByClass": validation_group_counts,
        "dataset": dataset_metadata,
        "datasetFingerprint": dataset_metadata["fingerprint"],
        "sources": dict(sorted(Counter(clip.source_id for clip in clips).items())),
        "clinicalVerifiedClipCounts": dict(sorted(Counter(
            clip.label for clip in clips if clip.clinical_verified).items())),
        "clinicalPlatformLineage": lineage,
        "rawValidation": raw_validation,
        "validation": validation,
        "minimumConfidence": confidence,
        "distanceLimits": [float(value) for value in distance_limits],
        "releaseGate": {
            "approved": approved,
            "requested": args.release,
            "requiredClinicalLabels": required_labels,
            "reasons": gate_reasons,
        },
        "limitation": "Acoustic screening only. Do not use this model as a veterinary diagnosis.",
    }
    args.metadata.parent.mkdir(parents=True, exist_ok=True)
    args.metadata.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_model_card(args.model_card, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"generated {args.output}")
    print(f"model card {args.model_card}")


if __name__ == "__main__":
    main()
