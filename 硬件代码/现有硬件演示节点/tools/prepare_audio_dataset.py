#!/usr/bin/env python3
"""Prepare a versioned, audited PCM dataset from an approved audio archive.

The prepared data is deliberately separated from source code. Every normalized
clip gets a content hash, source metadata, quality measurements, and a
group-safe train/validation split. This prevents public non-clinical audio from
being silently relabeled as a disease sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import wave
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


TARGET_RATE = 8_000
TARGET_CHANNELS = 1
TARGET_WIDTH_BYTES = 2
TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9_.-]+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path,
                        default=Path("tools/audio_dataset_sources.json"),
                        help="JSON source registry")
    parser.add_argument("--source-id", required=True,
                        help="Approved source id from the source registry")
    parser.add_argument("--archive", type=Path, required=True,
                        help="Downloaded source archive")
    parser.add_argument("--output", type=Path, required=True,
                        help="New, empty directory for normalized audio and manifest")
    parser.add_argument("--ffmpeg", default=os.environ.get("AUDIO_FFMPEG", "ffmpeg"),
                        help="ffmpeg executable; AUDIO_FFMPEG is honored")
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--min-duration-seconds", type=float, default=0.5)
    parser.add_argument("--max-duration-seconds", type=float, default=10.0)
    parser.add_argument("--min-rms-dbfs", type=float, default=-60.0)
    parser.add_argument("--max-saturation-ratio", type=float, default=0.02)
    return parser.parse_args()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_source(registry_path: Path, source_id: str) -> dict[str, Any]:
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read source registry {registry_path}: {error}") from error
    for source in payload.get("sources", []):
        if source.get("id") == source_id:
            return source
    raise SystemExit(f"source id not found in registry: {source_id}")


def require_empty_output(output: Path) -> None:
    if output.exists() and any(output.iterdir()):
        raise SystemExit(
            f"output directory is not empty: {output}. Choose a new versioned output directory.")
    output.mkdir(parents=True, exist_ok=True)


def resolve_ffmpeg(value: str) -> str:
    candidate = Path(value).expanduser()
    if candidate.is_file():
        return str(candidate)
    found = shutil.which(value)
    if found:
        return found
    raise SystemExit(
        "ffmpeg was not found. Install ffmpeg, add it to PATH, or pass --ffmpeg /path/to/ffmpeg.exe")


def source_class(entry_name: str, source: dict[str, Any]) -> str:
    parts = PurePosixPath(entry_name).parts
    index = int(source.get("classPathIndex", 1))
    if len(parts) <= index:
        raise ValueError(f"cannot read source class from {entry_name}")
    return parts[index]


def output_name(source_id: str, entry_name: str) -> str:
    stem = PurePosixPath(entry_name).with_suffix("").as_posix().replace("/", "__")
    return f"{source_id}__{SAFE_FILENAME.sub('_', stem)}.wav"


def group_id(source_id: str, original_class: str, entry_name: str) -> str:
    stem = PurePosixPath(entry_name).stem
    stem = re.sub(r"-[A-Za-z]$", "", stem)
    return f"{source_id}:{original_class}:{stem}"


def run_ffmpeg(ffmpeg: str, source: Path, target: Path) -> None:
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel", "error",
        "-nostdin",
        "-y",
        "-i", str(source),
        "-ac", str(TARGET_CHANNELS),
        "-ar", str(TARGET_RATE),
        "-sample_fmt", "s16",
        "-c:a", "pcm_s16le",
        str(target),
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0 or not target.is_file():
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed for {source.name}: {detail or completed.returncode}")


def inspect_pcm_wav(path: Path) -> dict[str, float | int]:
    with wave.open(str(path), "rb") as audio:
        channels = audio.getnchannels()
        sample_width = audio.getsampwidth()
        sample_rate = audio.getframerate()
        frame_count = audio.getnframes()
        raw = audio.readframes(frame_count)
    if channels != TARGET_CHANNELS or sample_width != TARGET_WIDTH_BYTES or sample_rate != TARGET_RATE:
        raise ValueError(
            f"normalized format mismatch: {channels} channel(s), {sample_rate} Hz, {sample_width * 8}-bit")
    values = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if values.size == 0:
        raise ValueError("empty audio")
    rms = float(np.sqrt(np.mean(np.square(values))))
    return {
        "sampleRate": sample_rate,
        "channels": channels,
        "bitDepth": sample_width * 8,
        "frameCount": frame_count,
        "durationSeconds": frame_count / sample_rate,
        "rmsDbfs": 20.0 * math.log10(max(rms, 1e-9)),
        "peak": float(np.max(np.abs(values))),
        "saturationRatio": float(np.mean(np.abs(values) >= 0.999)),
    }


def quality_reason(measurements: dict[str, float | int], args: argparse.Namespace) -> str | None:
    duration = float(measurements["durationSeconds"])
    if duration < args.min_duration_seconds:
        return f"duration_lt_{args.min_duration_seconds}"
    if duration > args.max_duration_seconds:
        return f"duration_gt_{args.max_duration_seconds}"
    if float(measurements["rmsDbfs"]) < args.min_rms_dbfs:
        return f"rms_lt_{args.min_rms_dbfs}"
    if float(measurements["saturationRatio"]) > args.max_saturation_ratio:
        return f"saturation_gt_{args.max_saturation_ratio}"
    return None


def assign_group_splits(records: list[dict[str, Any]], ratio: float, seed: int) -> None:
    if not 0.05 <= ratio < 0.5:
        raise ValueError("validation ratio must be between 0.05 and 0.5")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        groups[str(record["groupId"])].append(record)
    group_label: dict[str, str] = {}
    for identifier, rows in groups.items():
        labels = {str(row["label"]) for row in rows}
        if len(labels) != 1:
            raise ValueError(
                f"group {identifier} contains more than one class; source grouping must be corrected before training")
        group_label[identifier] = labels.pop()
    by_label: dict[str, list[str]] = defaultdict(list)
    for identifier, label in group_label.items():
        by_label[label].append(identifier)
    generator = random.Random(seed)
    validation_groups: set[str] = set()
    for label, identifiers in sorted(by_label.items()):
        if len(identifiers) < 2:
            raise ValueError(f"label {label} has fewer than two independent groups")
        generator.shuffle(identifiers)
        validation_count = min(len(identifiers) - 1, max(1, round(len(identifiers) * ratio)))
        validation_groups.update(identifiers[:validation_count])
    for record in records:
        record["split"] = "validation" if record["groupId"] in validation_groups else "train"


def main() -> None:
    args = parse_args()
    source = load_source(args.registry, args.source_id)
    if source.get("status") != "approved_for_baseline_only":
        raise SystemExit(f"source {args.source_id} is not approved for preparation: {source.get('status')}")
    if not args.archive.is_file():
        raise SystemExit(f"archive does not exist: {args.archive}")
    require_empty_output(args.output)
    archive_hash = sha256_file(args.archive)
    expected_hash = str(source.get("expectedArchiveSha256", "")).lower()
    if expected_hash and archive_hash.lower() != expected_hash:
        raise SystemExit(
            f"archive SHA-256 mismatch: expected {expected_hash}, received {archive_hash}. Refusing to prepare.")
    ffmpeg = resolve_ffmpeg(args.ffmpeg)
    mapping = source.get("classMapping", {})
    if not isinstance(mapping, dict) or not mapping:
        raise SystemExit("source registry requires a non-empty classMapping")
    records: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    observed_classes: Counter[str] = Counter()
    normalized_hashes: dict[str, tuple[str, str]] = {}
    with zipfile.ZipFile(args.archive) as archive, tempfile.TemporaryDirectory(prefix="cattle-audio-") as temporary:
        temp_root = Path(temporary)
        entries = sorted(
            (entry for entry in archive.infolist()
             if not entry.is_dir() and PurePosixPath(entry.filename).suffix.lower() == ".wav"),
            key=lambda entry: entry.filename.lower())
        if not entries:
            raise SystemExit("archive has no .wav files")
        for entry in entries:
            try:
                original_label = source_class(entry.filename, source)
                observed_classes[original_label] += 1
                mapped_label = str(mapping[original_label])
                if not TOKEN.fullmatch(mapped_label):
                    raise ValueError(f"mapped class is unsafe: {mapped_label}")
            except (KeyError, ValueError) as error:
                skipped[f"mapping:{error}"] += 1
                continue
            raw = archive.read(entry)
            raw_path = temp_root / "raw" / output_name(args.source_id, entry.filename)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(raw)
            pcm_path = temp_root / "pcm" / output_name(args.source_id, entry.filename)
            pcm_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                run_ffmpeg(ffmpeg, raw_path, pcm_path)
                measurements = inspect_pcm_wav(pcm_path)
                reason = quality_reason(measurements, args)
                if reason:
                    skipped[reason] += 1
                    continue
            except (OSError, RuntimeError, ValueError, wave.Error) as error:
                skipped[f"conversion:{type(error).__name__}"] += 1
                print(f"skip {entry.filename}: {error}", file=sys.stderr)
                continue
            normalized_hash = sha256_file(pcm_path)
            duplicate = normalized_hashes.get(normalized_hash)
            if duplicate is not None:
                existing_label, existing_path = duplicate
                if existing_label != mapped_label:
                    raise SystemExit(
                        "same normalized audio appears under different labels: "
                        f"{existing_path} ({existing_label}) vs {entry.filename} ({mapped_label})")
                skipped["duplicate_exact"] += 1
                continue
            normalized_hashes[normalized_hash] = (mapped_label, entry.filename)
            target = args.output / "audio" / mapped_label / output_name(args.source_id, entry.filename)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pcm_path, target)
            records.append({
                "schemaVersion": 1,
                "path": target.relative_to(args.output).as_posix(),
                "label": mapped_label,
                "groupId": group_id(args.source_id, original_label, entry.filename),
                "sourceId": args.source_id,
                "sourcePage": source.get("sourcePage"),
                "sourceVersion": source.get("version"),
                "license": source.get("license"),
                "originalLabel": original_label,
                "originalPath": entry.filename,
                "rawSha256": sha256_bytes(raw),
                "normalizedSha256": normalized_hash,
                "labelProvenance": source.get("labelProvenance"),
                "clinicalVerified": bool(source.get("clinicalVerified", False)),
                "allowForDiseaseLabels": bool(source.get("allowForDiseaseLabels", False)),
                "quality": measurements,
            })
    expected_counts = source.get("expectedSourceClassCounts", {})
    if expected_counts and dict(observed_classes) != expected_counts:
        raise SystemExit(
            f"unexpected source class counts: expected {expected_counts}, observed {dict(observed_classes)}")
    if len(records) < 8:
        raise SystemExit(f"only {len(records)} clips passed quality checks")
    hashes: dict[str, str] = {}
    for record in records:
        digest = str(record["normalizedSha256"])
        existing = hashes.get(digest)
        if existing and existing != record["label"]:
            raise SystemExit(f"same normalized audio appears under different labels: {existing} and {record['label']}")
        hashes[digest] = str(record["label"])
    assign_group_splits(records, args.validation_ratio, args.seed)
    records.sort(key=lambda row: (row["split"], row["label"], row["path"]))
    manifest_path = args.output / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as manifest:
        for record in records:
            manifest.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    report = {
        "schemaVersion": 1,
        "sourceId": args.source_id,
        "sourceStatus": source.get("status"),
        "sourcePage": source.get("sourcePage"),
        "license": source.get("license"),
        "archive": str(args.archive.resolve()),
        "archiveSha256": archive_hash,
        "ffmpeg": ffmpeg,
        "targetFormat": {"sampleRate": TARGET_RATE, "channels": TARGET_CHANNELS, "bitDepth": 16},
        "inputSourceClassCounts": dict(sorted(observed_classes.items())),
        "acceptedCount": len(records),
        "skipped": dict(sorted(skipped.items())),
        "labels": dict(sorted(Counter(record["label"] for record in records).items())),
        "groupCount": len({record["groupId"] for record in records}),
        "groupsByLabel": {
            label: len({record["groupId"] for record in records if record["label"] == label})
            for label in sorted({record["label"] for record in records})
        },
        "splits": dict(sorted(Counter(record["split"] for record in records).items())),
        "manifest": manifest_path.name,
        "allowedUse": source.get("allowedUse"),
    }
    (args.output / "dataset_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"prepared {len(records)} clips in {args.output}")


if __name__ == "__main__":
    main()
