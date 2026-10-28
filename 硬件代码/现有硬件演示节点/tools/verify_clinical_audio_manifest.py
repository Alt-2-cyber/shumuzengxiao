#!/usr/bin/env python3
"""Merge veterinarian-signed annotations into a platform audio manifest.

The script is intentionally separate from ordinary UI review. A reviewer can
label an audio event, but only a complete clinical annotation can mark an event
as eligible for respiratory-risk model release.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


REQUIRED_COLUMNS = {
    "sourceEventId",
    "label",
    "animalId",
    "recordingSessionId",
    "veterinarian",
    "evidenceReference",
    "verifiedAt",
}

RISK_LABELS = {"cough_suspect", "wheeze_suspect"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True,
                        help="Reviewed audio JSONL manifest")
    parser.add_argument("--annotations", type=Path, required=True,
                        help="CSV with veterinary clinical verification")
    parser.add_argument("--output", type=Path, required=True,
                        help="New JSONL manifest with verification fields")
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"invalid JSON at {path}:{number}: {error}") from error
        if row.get("sourceEventId") is None:
            raise SystemExit(f"manifest row {number} has no sourceEventId")
        rows.append(row)
    return rows


def read_annotations(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        columns = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - columns
        if missing:
            raise SystemExit(f"annotation CSV is missing columns: {', '.join(sorted(missing))}")
        annotations: dict[str, dict[str, str]] = {}
        for number, row in enumerate(reader, start=2):
            event_id = str(row.get("sourceEventId") or "").strip()
            if not event_id:
                raise SystemExit(f"annotation CSV row {number} has no sourceEventId")
            if event_id in annotations:
                raise SystemExit(f"duplicate annotation for sourceEventId {event_id}")
            missing_values = [column for column in REQUIRED_COLUMNS if not str(row.get(column) or "").strip()]
            if missing_values:
                raise SystemExit(
                    f"annotation CSV row {number} has empty required values: {', '.join(sorted(missing_values))}")
            annotations[event_id] = {key: str(value or "").strip() for key, value in row.items()}
            if annotations[event_id]["label"] not in RISK_LABELS | {"normal", "moo", "barn_noise"}:
                raise SystemExit(f"annotation CSV row {number} has unsupported label")
    return annotations


def main() -> None:
    args = parse_args()
    if not args.manifest.is_file() or not args.annotations.is_file():
        raise SystemExit("manifest and annotation CSV must exist")
    if args.output.exists():
        raise SystemExit(f"output already exists: {args.output}")
    rows = read_manifest(args.manifest)
    annotations = read_annotations(args.annotations)
    event_ids = {str(row["sourceEventId"]) for row in rows}
    unknown = set(annotations) - event_ids
    if unknown:
        raise SystemExit(f"annotations reference events not in manifest: {', '.join(sorted(unknown))}")
    verified = 0
    for row in rows:
        annotation = annotations.get(str(row["sourceEventId"]))
        if not annotation:
            continue
        if annotation["label"] != str(row.get("label") or ""):
            raise SystemExit(
                f"event {row['sourceEventId']} label mismatch: manifest={row.get('label')} annotation={annotation['label']}")
        if not row.get("path") or not row.get("rawSha256") or not row.get("normalizedSha256"):
            raise SystemExit(f"event {row['sourceEventId']} has no auditable local WAV path/hash")
        row.update({
            "animalId": annotation["animalId"],
            "recordingSessionId": annotation["recordingSessionId"],
            "groupId": f"animal:{annotation['animalId']}",
            "veterinarian": annotation["veterinarian"],
            "clinicalEvidenceReference": annotation["evidenceReference"],
            "clinicalVerifiedAt": annotation["verifiedAt"],
            "clinicalVerified": True,
            "allowForDiseaseLabels": True,
            "labelProvenance": "veterinarian_verified_audio_event",
        })
        verified += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"wrote {args.output}; clinically verified records={verified}; unverified records={len(rows) - verified}")


if __name__ == "__main__":
    main()
