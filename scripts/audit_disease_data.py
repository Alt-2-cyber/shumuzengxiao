#!/usr/bin/env python3
"""Audit real clinical inputs before any disease-model release.

This is a report-only gate. It never labels public data as veterinary truth and
never enables an edge model. Use --strict in CI or a release script to fail
when a disease family is not ready.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PLACEHOLDER_MARKERS = (
    "yyyy",
    "placeholder",
    "example",
    "file-or-url",
    "case-00",
    "0000000000000000000000000000000000000000000000000000000000000000",
)
RISK_AUDIO_LABELS = {"cough_suspect", "wheeze_suspect"}
RISK_VISION_LABELS = {
    "gait_abnormal_suspect",
    "hoof_lesion_suspect",
    "oral_lesion_suspect",
    "nasal_discharge_suspect",
}


def is_placeholder(value: object) -> bool:
    text = str(value or "").strip().lower()
    return not text or any(marker in text for marker in PLACEHOLDER_MARKERS)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            records.append(value)
    return records


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        return [dict(row) for row in csv.DictReader(source)]


def vision_summary(root: Path) -> dict[str, Any]:
    data_dir = root / "疾病识别生产落地" / "数据采集"
    manifest_candidates = (
        data_dir / "vision_annotations.jsonl",
        root / "vision-training-data" / "reviewed" / "reviewed_manifest.jsonl",
        root / "vision_dataset" / "reviewed_manifest.jsonl",
    )
    manifest = next((candidate for candidate in manifest_candidates if candidate.is_file()), manifest_candidates[0])
    records = read_jsonl(manifest)
    usable = 0
    clinical = 0
    risk_counts: Counter[str] = Counter()
    animals: set[str] = set()
    reasons: list[str] = []
    for record in records:
        label = str(record.get("label") or "").strip().lower()
        image_value = str(record.get("image") or record.get("path") or "").strip()
        image = Path(image_value)
        if not image.is_absolute():
            image = (manifest.parent / image).resolve()
        declared = str(record.get("snapshotSha256") or "").lower()
        valid = (
            not is_placeholder(record.get("eventId"))
            and not is_placeholder(record.get("recordingId"))
            and image.is_file()
            and len(declared) == 64
            and sha256(image) == declared
        )
        if not valid:
            continue
        usable += 1
        animals.add(str(record.get("animalId") or ""))
        if label in RISK_VISION_LABELS:
            risk_counts[label] += 1
        if bool(record.get("clinicallyVerified")) and bool(record.get("allowForDiseaseLabels")):
            clinical += 1

    if not records:
        reasons.append("vision_annotations.jsonl is missing; only the example template exists")
    if usable == 0:
        reasons.append("no image has a real file and matching SHA-256")
    if len(animals) < 9:
        reasons.append(f"usable vision animals={len(animals)}; requires at least 9")
    for label in sorted(RISK_VISION_LABELS):
        if risk_counts[label] < 50:
            reasons.append(f"{label} usable images={risk_counts[label]}; requires at least 50")
    return {
        "ready": not reasons,
        "manifest": str(manifest),
        "records": len(records),
        "usableAnnotations": usable,
        "clinicalVerified": clinical,
        "animals": len(animals),
        "riskLabelCounts": dict(risk_counts),
        "reasons": reasons,
    }


def audio_summary(root: Path) -> dict[str, Any]:
    reviewed = root / "audio-training-data" / "reviewed"
    manifests = sorted(reviewed.rglob("clinical_manifest.jsonl")) if reviewed.is_dir() else []
    records = [record for path in manifests for record in read_jsonl(path)]
    usable = 0
    clinical = 0
    labels: Counter[str] = Counter()
    animals: set[str] = set()
    reasons: list[str] = []
    for record in records:
        path_value = str(record.get("path") or "")
        audio = Path(path_value)
        if not audio.is_absolute():
            audio = (root / "audio-training-data" / "reviewed" / path_value).resolve()
        if not audio.is_file() or is_placeholder(record.get("sourceEventId")):
            continue
        usable += 1
        label = str(record.get("label") or "").strip().lower()
        labels[label] += 1
        animals.add(str(record.get("animalId") or ""))
        if bool(record.get("clinicalVerified")) and bool(record.get("allowForDiseaseLabels")):
            clinical += 1

    if not manifests:
        reasons.append("no veterinarian-verified clinical_manifest.jsonl exists")
    if usable == 0:
        reasons.append("no usable archived clinical WAV is available")
    if len(animals) < 9:
        reasons.append(f"usable audio animals={len(animals)}; requires at least 9")
    for label in sorted(RISK_AUDIO_LABELS):
        if labels[label] < 100:
            reasons.append(f"{label} records={labels[label]}; production minimum is 100")
    return {
        "ready": not reasons,
        "manifests": [str(path) for path in manifests],
        "records": len(records),
        "usableAnnotations": usable,
        "clinicalVerified": clinical,
        "animals": len(animals),
        "labelCounts": dict(labels),
        "reasons": reasons,
    }


def lameness_summary(root: Path) -> dict[str, Any]:
    data_dir = root / "疾病识别生产落地" / "数据采集"
    annotations_path = data_dir / "lameness_annotations.csv"
    manifest_path = data_dir / "lameness_manifest.json"
    rows = read_csv(annotations_path)
    usable = [
        row for row in rows
        if not any(is_placeholder(row.get(field)) for field in (
            "recordingId", "animalId", "recordingSessionId", "startedAt",
            "videoReference", "imuReference", "clinicalEvidenceReference", "verifiedAt"))
    ]
    captures = sorted((root / "motion-captures").rglob("*.ndjson")) if (root / "motion-captures").is_dir() else []
    animals = {row.get("animalId", "") for row in usable if row.get("animalId")}
    positive = {row.get("animalId", "") for row in usable if str(row.get("lamenessScore", "0")) not in {"0", ""}}
    reasons: list[str] = []
    if not manifest_path.is_file():
        reasons.append("lameness_manifest.json is missing")
    if not usable:
        reasons.append("lameness_annotations.csv contains only the placeholder row")
    if not captures:
        reasons.append("no archived three-position IMU NDJSON exists")
    if len(animals) < 9:
        reasons.append(f"usable lameness animals={len(animals)}; requires at least 9")
    if len(positive) < 3:
        reasons.append(f"external/positive animal evidence={len(positive)}; requires at least 3")
    return {
        "ready": not reasons,
        "annotations": str(annotations_path),
        "manifest": str(manifest_path),
        "records": len(rows),
        "usableAnnotations": len(usable),
        "imuArchives": len(captures),
        "animals": len(animals),
        "positiveAnimals": len(positive),
        "reasons": reasons,
    }


def build_report(root: Path, family: str | None = None) -> dict[str, Any]:
    families = {
        "vision": vision_summary(root),
        "audio": audio_summary(root),
        "lameness": lameness_summary(root),
    }
    if family is not None and family not in families:
        raise ValueError(f"unsupported family: {family}")
    checked = families if family is None else {family: families[family]}
    return {
        "generatedAt": datetime.now(UTC).isoformat(),
        "root": str(root.resolve()),
        "scope": family or "all",
        "checkedFamilies": sorted(checked),
        "overallReady": all(item["ready"] for item in checked.values()),
        "families": families,
        "policy": "Public data may support non-diagnostic baselines; clinical disease release requires local veterinary evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--family", choices=("vision", "audio", "lameness"))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = build_report(args.root, args.family)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overallReady"] or not args.strict else 2


if __name__ == "__main__":
    sys.exit(main())
