#!/usr/bin/env python3
"""Verify clinical lameness annotations before model training.

The tool creates an auditable manifest for a future synchronized neck/body/leg
model. It deliberately does not train or publish a model: labels must come
from a trained gait scorer and hoof/clinical examination, and train/validation
splits must be performed by animal or recording session.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request


MINIMUM_COMPLETENESS_RATIO = 0.95


REQUIRED_COLUMNS = {
    "recordingId",
    "animalId",
    "recordingSessionId",
    "startedAt",
    "lamenessScore",
    "gaitReviewer",
    "hoofExaminer",
    "veterinarian",
    "hoofFinding",
    "videoReference",
    "imuReference",
    "clinicalEvidenceReference",
    "verifiedAt",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--minimum-score", type=int, default=0)
    parser.add_argument("--maximum-score", type=int, default=3)
    parser.add_argument("--api", default=os.environ.get("SMART_CATTLE_API", ""),
                        help="Backend URL for accepted-session verification; defaults to SMART_CATTLE_API")
    parser.add_argument("--api-key", default=os.environ.get("CLINICAL_API_KEY", ""),
                        help="Clinical API key; defaults to CLINICAL_API_KEY")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.annotations.is_file():
        raise SystemExit(f"annotations do not exist: {args.annotations}")
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    if args.minimum_score < 0 or args.maximum_score < args.minimum_score:
        raise SystemExit("invalid lameness score range")

    rows: list[dict[str, object]] = []
    recording_ids: set[str] = set()
    session_ids: set[str] = set()
    with args.annotations.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"CSV is missing columns: {', '.join(sorted(missing))}")
        for line, raw in enumerate(reader, start=2):
            row = {key: str(value or "").strip() for key, value in raw.items()}
            empty = [key for key in REQUIRED_COLUMNS if not row[key]]
            if empty:
                raise SystemExit(f"row {line} has empty required fields: {', '.join(sorted(empty))}")
            if row["recordingId"] in recording_ids:
                raise SystemExit(f"duplicate recordingId in row {line}: {row['recordingId']}")
            recording_ids.add(row["recordingId"])
            if row["recordingSessionId"] in session_ids:
                raise SystemExit(
                    f"duplicate recordingSessionId in row {line}: {row['recordingSessionId']}")
            session_ids.add(row["recordingSessionId"])
            try:
                score = int(row["lamenessScore"])
            except ValueError as error:
                raise SystemExit(f"row {line} has invalid lamenessScore") from error
            if score < args.minimum_score or score > args.maximum_score:
                raise SystemExit(
                    f"row {line} lamenessScore must be {args.minimum_score}..{args.maximum_score}")
            quality = verify_capture_quality(row["imuReference"], args.annotations)
            if args.api:
                quality["platformSession"] = verify_platform_session(
                    args.api, args.api_key, row["animalId"], row["recordingSessionId"],
                    row["videoReference"], quality["sha256"], score,
                    row["gaitReviewer"], row["hoofExaminer"], row["veterinarian"],
                    row["hoofFinding"], row["clinicalEvidenceReference"], row["verifiedAt"])
            rows.append({
                "schemaVersion": 2,
                "recordingId": row["recordingId"],
                "animalId": row["animalId"],
                "recordingSessionId": row["recordingSessionId"],
                "groupId": f"animal:{row['animalId']}",
                "startedAt": row["startedAt"],
                "lamenessScore": score,
                "targetLabel": "lameness_suspect" if score >= 2 else "normal_gait",
                "gaitReviewer": row["gaitReviewer"],
                "hoofExaminer": row["hoofExaminer"],
                "veterinarian": row["veterinarian"],
                "hoofFinding": row["hoofFinding"],
                "videoReference": row["videoReference"],
                "imuReference": row["imuReference"],
                "imuQuality": quality,
                "clinicalEvidenceReference": row["clinicalEvidenceReference"],
                "verifiedAt": row["verifiedAt"],
                "clinicalVerified": True,
                "allowForDiseaseLabels": True,
                "labelProvenance": "gait_score_and_hoof_exam_verified",
            })

    if len({str(row["animalId"]) for row in rows}) < 2:
        raise SystemExit("need at least two independent animals before a split can be created")
    fingerprint = hashlib.sha256(
        "\n".join(json.dumps(row, sort_keys=True) for row in sorted(rows, key=lambda item: str(item["recordingId"]))).encode("utf-8")
    ).hexdigest()
    payload = {
        "schemaVersion": 2,
        "recordCount": len(rows),
        "animalCount": len({str(row["animalId"]) for row in rows}),
        "datasetFingerprint": fingerprint,
        "records": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: payload[key] for key in ("recordCount", "animalCount", "datasetFingerprint")}, ensure_ascii=False))


def verify_capture_quality(reference: str, annotations_path: Path | None = None) -> dict[str, object]:
    path = Path(reference)
    if not path.is_absolute() and annotations_path is not None:
        path = annotations_path.parent / path
    if not path.is_file():
        raise SystemExit(f"raw IMU file does not exist: {path}")
    sample_indexes: list[int] = []
    sample_rate: int | None = None
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            sample = json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"invalid IMU JSON at {path}:{number}: {error}") from error
        if sample.get("type") != "motion_capture_sample":
            continue
        index = sample.get("sampleIndex")
        if not isinstance(index, int) or index < 0:
            raise SystemExit(f"invalid sampleIndex at {path}:{number}")
        sample_indexes.append(index)
        rate = sample.get("sampleRateHz")
        if not isinstance(rate, int) or rate < 1 or rate > 100:
            raise SystemExit(f"invalid sampleRateHz at {path}:{number}")
        if sample_rate is None:
            sample_rate = rate
        elif sample_rate != rate:
            raise SystemExit(f"raw IMU file has inconsistent sampleRateHz values: {path}")
    if not sample_indexes:
        raise SystemExit(f"raw IMU file has no motion_capture_sample rows: {path}")
    if len(sample_indexes) != len(set(sample_indexes)):
        raise SystemExit(f"raw IMU file has duplicate sampleIndex values: {path}")
    expected = max(sample_indexes) + 1
    completeness = len(sample_indexes) / expected
    missing = sorted(set(range(expected)) - set(sample_indexes))
    if completeness < MINIMUM_COMPLETENESS_RATIO:
        raise SystemExit(
            f"raw IMU capture completeness {completeness:.3f} is below {MINIMUM_COMPLETENESS_RATIO:.2f}: {path}")
    return {
        "rowCount": len(sample_indexes),
        "sampleRateHz": sample_rate,
        "expectedByIndex": expected,
        "missingSamples": len(missing),
        "completenessRatio": round(completeness, 6),
        "minimumCompletenessRatio": MINIMUM_COMPLETENESS_RATIO,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def verify_platform_session(
        api: str,
        api_key: str,
        animal_id: str,
        recording_session_id: str,
        video_reference: str,
        file_sha256: str,
        lameness_score: int,
        gait_reviewer: str,
        hoof_examiner: str,
        veterinarian: str,
        hoof_finding: str,
        clinical_evidence_reference: str,
        verified_at: str,
) -> dict[str, object]:
    base_url = api.rstrip("/")
    url = f"{base_url}/api/motion-captures/{urllib.parse.quote(recording_session_id, safe='')}/training-lineage"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot verify motion capture session from platform: {error}") from error
    if not isinstance(payload, dict):
        raise SystemExit("platform motion-capture lineage API returned a non-object response")
    session = payload
    if str(session.get("sessionId") or "") != recording_session_id:
        raise SystemExit(f"platform resolved the wrong capture session for {recording_session_id}")
    if str(session.get("cattleId") or "") != animal_id:
        raise SystemExit(f"platform session cattle identity does not match for {recording_session_id}")
    if session.get("status") != "completed" or session.get("qualityStatus") != "accepted":
        raise SystemExit(f"platform session {recording_session_id} is not accepted")
    if session.get("archiveIntegrityVerified") is not True:
        raise SystemExit(f"platform archive integrity failed for {recording_session_id}")
    if str(session.get("rawDataSha256") or "").lower() != file_sha256.lower():
        raise SystemExit(f"platform hash does not match local IMU archive for {recording_session_id}")
    if str(session.get("videoReference") or "") != video_reference:
        raise SystemExit(f"platform video reference does not match the annotation for {recording_session_id}")
    if session.get("sampleRateHz") != 20:
        raise SystemExit(f"platform sample rate is not 20 Hz for {recording_session_id}")
    received = session.get("receivedSamples")
    expected = session.get("expectedSamples")
    attempted = session.get("attemptedSamples")
    if not all(isinstance(value, int) for value in (received, expected, attempted)) or expected <= 0:
        raise SystemExit(f"platform sample counts are incomplete for {recording_session_id}")
    if received / expected < MINIMUM_COMPLETENESS_RATIO or attempted != expected:
        raise SystemExit(f"platform capture completeness is insufficient for {recording_session_id}")
    if session.get("droppedBackpressureSamples") not in (0, None) \
            or session.get("droppedSensorSamples") not in (0, None):
        raise SystemExit(f"platform capture has dropped samples for {recording_session_id}")
    comparisons = {
        "clinicalReviewStatus": (str(session.get("clinicalReviewStatus") or ""), "verified"),
        "lamenessScore": (session.get("lamenessScore"), lameness_score),
        "gaitReviewer": (str(session.get("gaitReviewer") or ""), gait_reviewer),
        "hoofExaminer": (str(session.get("hoofExaminer") or ""), hoof_examiner),
        "veterinarian": (str(session.get("veterinarian") or ""), veterinarian),
        "hoofFinding": (str(session.get("hoofFinding") or ""), hoof_finding),
        "clinicalEvidenceReference": (
            str(session.get("clinicalEvidenceReference") or ""), clinical_evidence_reference),
        "clinicallyVerifiedAt": (str(session.get("clinicallyVerifiedAt") or ""), verified_at),
    }
    mismatched = [field for field, (actual, expected_value) in comparisons.items() if actual != expected_value]
    if mismatched:
        raise SystemExit(
            f"platform clinical sign-off does not match annotation for {recording_session_id}: "
            + ", ".join(mismatched))
    # Keep the exported manifest reproducible. The server's recheck timestamp
    # is deliberately omitted; train/release perform a fresh recheck later.
    return {
        "api": base_url,
        "sessionId": recording_session_id,
        "cattleId": animal_id,
        "status": session.get("status"),
        "qualityStatus": session.get("qualityStatus"),
        "rawDataSha256": session.get("rawDataSha256"),
        "archiveIntegrityVerified": True,
        "sampleRateHz": session.get("sampleRateHz"),
        "receivedSamples": received,
        "expectedSamples": expected,
        "attemptedSamples": attempted,
        "droppedBackpressureSamples": session.get("droppedBackpressureSamples"),
        "droppedSensorSamples": session.get("droppedSensorSamples"),
        "completenessRatio": session.get("completenessRatio"),
        "videoReference": video_reference,
        "clinicalReviewStatus": session.get("clinicalReviewStatus"),
        "lamenessScore": session.get("lamenessScore"),
        "gaitReviewer": session.get("gaitReviewer"),
        "hoofExaminer": session.get("hoofExaminer"),
        "veterinarian": session.get("veterinarian"),
        "hoofFinding": session.get("hoofFinding"),
        "clinicalEvidenceReference": session.get("clinicalEvidenceReference"),
        "clinicallyVerifiedAt": session.get("clinicallyVerifiedAt"),
    }


if __name__ == "__main__":
    main()
