#!/usr/bin/env python3
"""Register an already gate-approved disease-screening model with the backend.

This is deliberately an administrator action. It refuses metadata whose local
release gate is not approved, rechecks every source archive, and sends the
source list and canonical fingerprint for a second server-side recheck. It
does not set the server's version whitelist; that change is a separate
deployment approval after the signed release record exists.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=os.environ.get("SMART_CATTLE_API", "http://localhost:8080"))
    parser.add_argument("--api-key", default=os.environ.get("ADMIN_API_KEY", ""),
                        help="Admin API key; defaults to ADMIN_API_KEY")
    parser.add_argument("--family", choices=("audio", "lameness", "vision"), required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--model-card", type=Path, required=True)
    parser.add_argument("--firmware", type=Path, required=True)
    parser.add_argument("--evidence-reference", required=True)
    parser.add_argument("--approved-by", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--confirm-production-release", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"file not found: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def request_json(url: str, api_key: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(
            f"clinical lineage recheck failed: HTTP {error.code} {error.read().decode('utf-8', 'replace')}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"cannot reach clinical lineage API: {error}") from error
    if not isinstance(payload, dict):
        raise SystemExit("clinical lineage API returned a non-object response")
    return payload


def required_text(payload: dict[str, object], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise SystemExit(f"audio model metadata has no clinicalPlatformLineage.{field}")
    return value


def required_lameness_text(payload: dict[str, object], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise SystemExit(f"lameness model metadata has no motionPlatformLineage.{field}")
    return value


def required_lameness_integer(payload: dict[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int):
        raise SystemExit(f"lameness model metadata has no integer motionPlatformLineage.{field}")
    return value


def required_vision_text(payload: dict[str, object], field: str) -> str:
    value = str(payload.get(field) or "").strip()
    if not value:
        raise SystemExit(f"vision model metadata has no visionPlatformLineage.{field}")
    return value


def recheck_audio_lineage(metadata: dict[str, object], api: str, api_key: str) -> dict[str, object]:
    """Repeat archive and clinical-signature validation at release registration."""
    lineage = metadata.get("clinicalPlatformLineage")
    if not isinstance(lineage, dict):
        raise SystemExit("audio model metadata has no platform-verified clinical lineage")
    source_api = str(lineage.get("api") or "").rstrip("/")
    target_api = api.rstrip("/")
    if source_api != target_api:
        raise SystemExit("audio lineage was trained against a different backend; retrain against the target production API")
    records = lineage.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit("audio model metadata has no lineage records")
    expected_count = metadata.get("sourceClipCount")
    if not isinstance(expected_count, int) or expected_count != len(records):
        raise SystemExit("audio model metadata lineage count does not match sourceClipCount")
    if lineage.get("checked") != len(records):
        raise SystemExit("audio model metadata lineage checked count is inconsistent")

    seen: set[str] = set()
    verified: list[dict[str, str]] = []
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit("audio model metadata has an invalid lineage record")
        event_id = required_text(record, "sourceEventId")
        if event_id in seen:
            raise SystemExit(f"audio model metadata reuses sourceEventId {event_id}")
        seen.add(event_id)
        expected_hash = required_text(record, "clipSha256").lower()
        expected_label = required_text(record, "label")
        endpoint = urllib.parse.urljoin(
            target_api + "/", f"api/events/audio/{urllib.parse.quote(event_id, safe='')}/training-lineage")
        remote = request_json(endpoint, api_key)
        if str(remote.get("sourceEventId") or "") != event_id:
            raise SystemExit(f"audio lineage event {event_id} resolved to the wrong source event")
        if str(remote.get("clipSha256") or "").lower() != expected_hash:
            raise SystemExit(f"audio lineage hash changed for source event {event_id}")
        for field, remote_field in (
            ("label", "reviewLabel"),
            ("reviewStatus", "reviewStatus"),
            ("clinicalAnimalId", "clinicalAnimalId"),
            ("recordingSessionId", "recordingSessionId"),
            ("veterinarian", "veterinarian"),
            ("clinicalEvidenceReference", "clinicalEvidenceReference"),
            ("clinicallyVerifiedAt", "clinicallyVerifiedAt"),
        ):
            expected = required_text(record, field)
            if str(remote.get(remote_field) or "") != expected:
                raise SystemExit(f"audio lineage {remote_field} changed for source event {event_id}")
        if str(remote.get("reviewStatus") or "") not in {"confirmed", "normal"}:
            raise SystemExit(f"audio lineage clinical review is no longer valid for source event {event_id}")
        if remote.get("clipIntegrityVerified") is not True:
            raise SystemExit(f"audio archive integrity failed for source event {event_id}")
        verified.append({
            key: required_text(record, key)
            for key in (
                "sourceEventId", "clipSha256", "label", "reviewStatus", "clinicalAnimalId",
                "recordingSessionId", "veterinarian", "clinicalEvidenceReference", "clinicallyVerifiedAt")
        })

    canonical = json.dumps(verified, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if fingerprint != str(lineage.get("fingerprint") or ""):
        raise SystemExit("audio lineage fingerprint is inconsistent")
    return {"checked": len(verified), "fingerprint": fingerprint}


def recheck_vision_lineage(metadata: dict[str, object], api: str, api_key: str) -> dict[str, object]:
    """Repeat visual archive, clinical review, and snapshot integrity validation."""
    lineage = metadata.get("visionPlatformLineage")
    if not isinstance(lineage, dict):
        raise SystemExit("vision model metadata has no platform-verified visual lineage")
    source_api = str(lineage.get("api") or "").rstrip("/")
    target_api = api.rstrip("/")
    if source_api != target_api:
        raise SystemExit(
            "vision lineage was trained against a different backend; retrain against the target production API")
    records = lineage.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit("vision model metadata has no lineage records")
    if lineage.get("checked") != len(records):
        raise SystemExit("vision model metadata lineage checked count is inconsistent")

    seen_events: set[str] = set()
    seen_recordings: set[str] = set()
    verified: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit("vision model metadata has an invalid lineage record")
        event_id = required_vision_text(record, "sourceEventId")
        recording_id = required_vision_text(record, "recordingId")
        if event_id in seen_events:
            raise SystemExit(f"vision model metadata reuses sourceEventId {event_id}")
        if recording_id in seen_recordings:
            raise SystemExit(f"vision model metadata reuses recordingId {recording_id}")
        seen_events.add(event_id)
        seen_recordings.add(recording_id)
        endpoint = urllib.parse.urljoin(
            target_api + "/", f"api/events/vision/{urllib.parse.quote(event_id, safe='')}/training-lineage")
        remote = request_json(endpoint, api_key)
        comparisons = {
            "sourceEventId": (str(remote.get("sourceEventId") or ""), event_id),
            "cameraId": (str(remote.get("cameraId") or ""), required_vision_text(record, "cameraId")),
            "barnId": (str(remote.get("barnId") or ""), required_vision_text(record, "barnId")),
            "snapshotSha256": (
                str(remote.get("snapshotSha256") or "").lower(),
                required_vision_text(record, "snapshotSha256").lower()),
            "reviewLabel": (str(remote.get("reviewLabel") or ""), required_vision_text(record, "reviewLabel")),
            "reviewStatus": (str(remote.get("reviewStatus") or ""), required_vision_text(record, "reviewStatus")),
            "clinicalAnimalId": (
                str(remote.get("clinicalAnimalId") or ""),
                required_vision_text(record, "clinicalAnimalId")),
            "veterinarian": (
                str(remote.get("veterinarian") or ""),
                required_vision_text(record, "veterinarian")),
            "clinicalEvidenceReference": (
                str(remote.get("clinicalEvidenceReference") or ""),
                required_vision_text(record, "clinicalEvidenceReference")),
            "clinicallyVerifiedAt": (
                str(remote.get("clinicallyVerifiedAt") or ""),
                required_vision_text(record, "clinicallyVerifiedAt")),
            "recordedAt": (
                str(remote.get("recordedAt") or ""),
                required_vision_text(record, "recordedAt")),
        }
        mismatched = [field for field, (actual, expected) in comparisons.items() if actual != expected]
        if remote.get("snapshotIntegrityVerified") is not True:
            mismatched.append("snapshotIntegrityVerified")
        if str(remote.get("reviewStatus") or "") not in {"confirmed", "normal"}:
            mismatched.append("reviewStatus")
        if mismatched:
            raise SystemExit(f"vision lineage changed for source event {event_id}: {', '.join(mismatched)}")
        verified.append({
            "sourceEventId": event_id,
            "recordingId": recording_id,
            "cameraId": required_vision_text(record, "cameraId"),
            "barnId": required_vision_text(record, "barnId"),
            "snapshotSha256": required_vision_text(record, "snapshotSha256").lower(),
            "reviewLabel": required_vision_text(record, "reviewLabel"),
            "reviewStatus": required_vision_text(record, "reviewStatus"),
            "clinicalAnimalId": required_vision_text(record, "clinicalAnimalId"),
            "veterinarian": required_vision_text(record, "veterinarian"),
            "clinicalEvidenceReference": required_vision_text(record, "clinicalEvidenceReference"),
            "clinicallyVerifiedAt": required_vision_text(record, "clinicallyVerifiedAt"),
            "recordedAt": required_vision_text(record, "recordedAt"),
        })

    canonical = json.dumps(verified, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if fingerprint != str(lineage.get("fingerprint") or ""):
        raise SystemExit("vision lineage fingerprint is inconsistent")
    return {"checked": len(verified), "fingerprint": fingerprint}


def recheck_lameness_lineage(
        metadata: dict[str, object], api: str, api_key: str, manifest_path: Path
) -> dict[str, object]:
    """Repeat IMU archive identity and integrity validation before registration."""
    lineage = metadata.get("motionPlatformLineage")
    if not isinstance(lineage, dict):
        raise SystemExit("lameness model metadata has no platform-verified motion lineage")
    source_api = str(lineage.get("api") or "").rstrip("/")
    target_api = api.rstrip("/")
    if source_api != target_api:
        raise SystemExit(
            "motion lineage was trained against a different backend; retrain against the target production API")
    metadata_manifest_hash = str(metadata.get("manifestFingerprint") or "").lower()
    if len(metadata_manifest_hash) != 64 or sha256(manifest_path) != metadata_manifest_hash:
        raise SystemExit("lameness dataset manifest differs from the manifest used for training")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read lameness dataset manifest: {error}") from error
    manifest_records = manifest.get("records") if isinstance(manifest, dict) else None
    if not isinstance(manifest_records, list) or not manifest_records:
        raise SystemExit("lameness dataset manifest has no records")
    records = lineage.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit("lameness model metadata has no motion lineage records")
    if lineage.get("checked") != len(records) or len(records) != len(manifest_records):
        raise SystemExit("lameness model metadata lineage count does not match the training manifest")

    manifest_by_recording: dict[str, dict[str, object]] = {}
    for manifest_record in manifest_records:
        if not isinstance(manifest_record, dict):
            raise SystemExit("lameness dataset manifest has an invalid record")
        recording_id = str(manifest_record.get("recordingId") or "").strip()
        if not recording_id or recording_id in manifest_by_recording:
            raise SystemExit("lameness dataset manifest has a missing or duplicate recordingId")
        manifest_by_recording[recording_id] = manifest_record

    seen_sessions: set[str] = set()
    verified: list[dict[str, object]] = []
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit("lameness model metadata has an invalid motion lineage record")
        recording_id = required_lameness_text(record, "recordingId")
        manifest_record = manifest_by_recording.pop(recording_id, None)
        if manifest_record is None:
            raise SystemExit(f"lameness lineage recording {recording_id} is absent from the dataset manifest")
        session_id = required_lameness_text(record, "recordingSessionId")
        if session_id in seen_sessions:
            raise SystemExit(f"lameness model metadata reuses recordingSessionId {session_id}")
        seen_sessions.add(session_id)
        quality = manifest_record.get("imuQuality")
        if not isinstance(quality, dict):
            raise SystemExit(f"lameness dataset manifest record {recording_id} has no IMU quality block")
        comparisons = {
            "recordingSessionId": (str(manifest_record.get("recordingSessionId") or ""), session_id),
            "animalId": (str(manifest_record.get("animalId") or ""), required_lameness_text(record, "animalId")),
            "rawDataSha256": (
                str(quality.get("sha256") or "").lower(),
                required_lameness_text(record, "rawDataSha256").lower()),
            "videoReference": (
                str(manifest_record.get("videoReference") or ""), required_lameness_text(record, "videoReference")),
            "gaitReviewer": (
                str(manifest_record.get("gaitReviewer") or ""), required_lameness_text(record, "gaitReviewer")),
            "hoofExaminer": (
                str(manifest_record.get("hoofExaminer") or ""), required_lameness_text(record, "hoofExaminer")),
            "veterinarian": (
                str(manifest_record.get("veterinarian") or ""), required_lameness_text(record, "veterinarian")),
            "hoofFinding": (
                str(manifest_record.get("hoofFinding") or ""), required_lameness_text(record, "hoofFinding")),
            "clinicalEvidenceReference": (
                str(manifest_record.get("clinicalEvidenceReference") or ""),
                required_lameness_text(record, "clinicalEvidenceReference")),
            "verifiedAt": (
                str(manifest_record.get("verifiedAt") or ""), required_lameness_text(record, "verifiedAt")),
        }
        if any(actual != expected for actual, expected in comparisons.values()):
            mismatched = [field for field, (actual, expected) in comparisons.items() if actual != expected]
            raise SystemExit(f"lameness dataset manifest changed for {recording_id}: {', '.join(mismatched)}")
        try:
            manifest_score = int(manifest_record.get("lamenessScore"))
        except (TypeError, ValueError) as error:
            raise SystemExit(f"lameness dataset manifest has invalid lamenessScore for {recording_id}") from error
        if manifest_score != required_lameness_integer(record, "lamenessScore"):
            raise SystemExit(f"lameness score changed for {recording_id}")
        if not bool(manifest_record.get("clinicalVerified")) \
                or not bool(manifest_record.get("allowForDiseaseLabels")):
            raise SystemExit(f"lameness dataset manifest record {recording_id} is no longer clinically eligible")

        endpoint = urllib.parse.urljoin(
            target_api + "/", f"api/motion-captures/{urllib.parse.quote(session_id, safe='')}/training-lineage")
        remote = request_json(endpoint, api_key)
        remote_comparisons = {
            "sessionId": (str(remote.get("sessionId") or ""), session_id),
            "cattleId": (str(remote.get("cattleId") or ""), required_lameness_text(record, "animalId")),
            "rawDataSha256": (
                str(remote.get("rawDataSha256") or "").lower(),
                required_lameness_text(record, "rawDataSha256").lower()),
            "videoReference": (
                str(remote.get("videoReference") or ""), required_lameness_text(record, "videoReference")),
        }
        mismatched = [field for field, (actual, expected) in remote_comparisons.items() if actual != expected]
        if remote.get("status") != "completed":
            mismatched.append("status")
        if remote.get("qualityStatus") != "accepted":
            mismatched.append("qualityStatus")
        if remote.get("archiveIntegrityVerified") is not True:
            mismatched.append("archiveIntegrityVerified")
        if remote.get("clinicalReviewStatus") != "verified":
            mismatched.append("clinicalReviewStatus")
        clinical_comparisons = {
            "lamenessScore": (remote.get("lamenessScore"), required_lameness_integer(record, "lamenessScore")),
            "gaitReviewer": (str(remote.get("gaitReviewer") or ""), required_lameness_text(record, "gaitReviewer")),
            "hoofExaminer": (str(remote.get("hoofExaminer") or ""), required_lameness_text(record, "hoofExaminer")),
            "veterinarian": (str(remote.get("veterinarian") or ""), required_lameness_text(record, "veterinarian")),
            "hoofFinding": (str(remote.get("hoofFinding") or ""), required_lameness_text(record, "hoofFinding")),
            "clinicalEvidenceReference": (
                str(remote.get("clinicalEvidenceReference") or ""),
                required_lameness_text(record, "clinicalEvidenceReference")),
            "clinicallyVerifiedAt": (str(remote.get("clinicallyVerifiedAt") or ""), required_lameness_text(record, "verifiedAt")),
        }
        mismatched.extend(
            field for field, (actual, expected_value) in clinical_comparisons.items() if actual != expected_value)
        if remote.get("sampleRateHz") != 20:
            mismatched.append("sampleRateHz")
        received = remote.get("receivedSamples")
        expected = remote.get("expectedSamples")
        attempted = remote.get("attemptedSamples")
        if not all(isinstance(value, int) for value in (received, expected, attempted)) \
                or expected <= 0 or received / expected < 0.95 or attempted != expected:
            mismatched.append("sampleCounts")
        if remote.get("droppedBackpressureSamples") not in (0, None) \
                or remote.get("droppedSensorSamples") not in (0, None):
            mismatched.append("droppedSamples")
        if mismatched:
            raise SystemExit(f"motion lineage changed for recording {recording_id}: {', '.join(mismatched)}")
        verified.append({
            "recordingId": recording_id,
            "recordingSessionId": session_id,
            "animalId": required_lameness_text(record, "animalId"),
            "rawDataSha256": required_lameness_text(record, "rawDataSha256").lower(),
            "videoReference": required_lameness_text(record, "videoReference"),
            "sampleRateHz": 20,
            "receivedSamples": received,
            "expectedSamples": expected,
            "attemptedSamples": attempted,
            "completenessRatio": remote.get("completenessRatio"),
            "gaitReviewer": required_lameness_text(record, "gaitReviewer"),
            "hoofExaminer": required_lameness_text(record, "hoofExaminer"),
            "veterinarian": required_lameness_text(record, "veterinarian"),
            "hoofFinding": required_lameness_text(record, "hoofFinding"),
            "clinicalEvidenceReference": required_lameness_text(record, "clinicalEvidenceReference"),
            "verifiedAt": required_lameness_text(record, "verifiedAt"),
            "lamenessScore": required_lameness_integer(record, "lamenessScore"),
        })

    if manifest_by_recording:
        raise SystemExit("lameness model metadata did not cover every training-manifest record")
    canonical = json.dumps(verified, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if fingerprint != str(lineage.get("fingerprint") or ""):
        raise SystemExit("lameness motion lineage fingerprint is inconsistent")
    return {"checked": len(verified), "fingerprint": fingerprint}


def server_lineage_sources(family: str, metadata: dict[str, object]) -> list[dict[str, str]]:
    """Build the exact archive identifiers the backend must re-verify.

    The backend independently reconstructs the trainer fingerprint from these
    records. Sending only a successful local recheck would leave a direct
    administrator API call able to skip the server-side archive verification.
    """
    lineage_key = {
        "audio": "clinicalPlatformLineage",
        "lameness": "motionPlatformLineage",
        "vision": "visionPlatformLineage",
    }[family]
    lineage = metadata.get(lineage_key)
    if not isinstance(lineage, dict):
        raise SystemExit(f"{family} model metadata has no {lineage_key}")
    records = lineage.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit(f"{family} model metadata has no release lineage records")

    sources: list[dict[str, str]] = []
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise SystemExit(f"{family} model metadata has an invalid release lineage record")
        source_id = required_text(record, "sourceEventId") if family in {"audio", "vision"} \
            else required_lameness_text(record, "recordingSessionId")
        if source_id in seen:
            raise SystemExit(f"{family} model metadata reuses release lineage source {source_id}")
        seen.add(source_id)
        source: dict[str, str] = {"sourceId": source_id}
        if family == "lameness":
            source["recordingId"] = required_lameness_text(record, "recordingId")
        elif family == "vision":
            source["recordingId"] = required_vision_text(record, "recordingId")
        sources.append(source)
    return sources


def main() -> None:
    args = parse_args()
    if not args.api_key:
        raise SystemExit("an administrator API key is required")
    if not args.confirm_production_release:
        raise SystemExit("pass --confirm-production-release after clinical release approval")
    try:
        metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read metadata: {error}") from error
    gate = metadata.get("releaseGate")
    if not isinstance(gate, dict) or gate.get("approved") is not True:
        raise SystemExit("local model metadata has not passed its release gate")
    version = str(metadata.get("modelVersion") or "").strip()
    if not version:
        raise SystemExit("model metadata has no modelVersion")
    lineage_summary = None
    if args.family == "audio":
        lineage_summary = recheck_audio_lineage(metadata, args.api, args.api_key)
    elif args.family == "lameness":
        lineage_summary = recheck_lameness_lineage(metadata, args.api, args.api_key, args.dataset_manifest)
    else:
        lineage_summary = recheck_vision_lineage(metadata, args.api, args.api_key)
    source_lineage = server_lineage_sources(args.family, metadata)
    summary = {
        "modelVersion": version,
        "releaseGate": gate,
        "validation": metadata.get("validation") or metadata.get("externalTest"),
        "datasetFingerprint": metadata.get("datasetFingerprint") or metadata.get("manifestFingerprint"),
    }
    if args.family == "audio":
        summary["clinicalPlatformLineage"] = lineage_summary
    elif args.family == "lameness":
        summary["motionPlatformLineage"] = lineage_summary
    else:
        summary["visionPlatformLineage"] = lineage_summary
    payload = {
        "modelFamily": args.family,
        "modelVersion": version,
        "datasetManifestSha256": sha256(args.dataset_manifest),
        "modelCardSha256": sha256(args.model_card),
        "firmwareSha256": sha256(args.firmware),
        "evidenceReference": args.evidence_reference,
        "approvedBy": args.approved_by,
        "validationSummary": json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        "notes": args.notes or None,
        "sourceLineageSha256": lineage_summary["fingerprint"],
        "sourceLineage": source_lineage,
    }
    request = urllib.request.Request(
        args.api.rstrip("/") + "/api/model-releases",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {args.api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            print(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise SystemExit(f"backend rejected release: HTTP {error.code} {error.read().decode('utf-8', 'replace')}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"cannot reach backend: {error}") from error


if __name__ == "__main__":
    main()
