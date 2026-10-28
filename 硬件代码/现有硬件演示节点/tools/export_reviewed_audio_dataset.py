#!/usr/bin/env python3
"""Export reviewed audio events from the platform into class folders."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path


TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8080",
                        help="Smart cattle backend base URL")
    parser.add_argument("--output", type=Path, default=Path("audio_dataset"),
                        help="Class-folder dataset output")
    parser.add_argument("--manifest", type=Path,
                        help="JSONL output manifest; defaults to reviewed_manifest.jsonl under --output")
    parser.add_argument("--source-id", default="platform-reviewed-audio",
                        help="Stable source id written into the training manifest")
    parser.add_argument("--statuses", default="normal,confirmed",
                        help="Comma-separated accepted review states")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace an already exported clip")
    parser.add_argument("--api-key", default=os.environ.get("CLINICAL_API_KEY", ""),
                        help="Clinical API key; defaults to CLINICAL_API_KEY")
    return parser.parse_args()


def request(url: str, api_key: str, timeout: int) -> object:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def request_json(url: str, api_key: str) -> object:
    with request(url, api_key, 15) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, api_key: str) -> bytes:
    with request(url, api_key, 30) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"audio/wav", "application/octet-stream"}:
            raise ValueError(f"unexpected content type {content_type}")
        return response.read()


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def recording_group(event: dict[str, object]) -> str:
    cattle = str(event.get("cattleId") or event.get("deviceId") or "unknown-cattle")
    return f"animal:{cattle}"


def main() -> None:
    args = parse_args()
    base_url = args.api.rstrip("/")
    accepted = {value.strip() for value in args.statuses.split(",") if value.strip()}
    manifest_path = args.manifest or args.output / "reviewed_manifest.jsonl"
    payload = request_json(f"{base_url}/api/events/audio", args.api_key)
    events = payload if isinstance(payload, list) else payload.get("value", [])
    exported = 0
    skipped = 0
    records: list[dict[str, object]] = []
    for event in events:
        label = str(event.get("reviewLabel") or "").strip()
        status = str(event.get("reviewStatus") or "").strip()
        path = str(event.get("audioClipPath") or "").strip()
        if status not in accepted or not label or not TOKEN.fullmatch(label) or not path:
            skipped += 1
            continue
        event_id = event.get("id")
        if event_id is None:
            skipped += 1
            continue
        target = args.output / label / f"event-{event_id}.wav"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target.exists() and not args.overwrite:
                audio = target.read_bytes()
            else:
                audio = download(urllib.parse.urljoin(base_url + "/", path.lstrip("/")), args.api_key)
                target.write_bytes(audio)
                exported += 1
                print(f"exported {target}")
            platform_hash = str(event.get("clipSha256") or "").strip().lower()
            actual_hash = digest(audio)
            if not platform_hash or not re.fullmatch(r"[a-f0-9]{64}", platform_hash):
                raise ValueError("platform event has no valid archived WAV SHA-256")
            if actual_hash != platform_hash:
                raise ValueError("downloaded WAV SHA-256 does not match platform archive")
            clinically_verified = bool(event.get("clinicallyVerifiedAt"))
            clinical_animal = str(event.get("clinicalAnimalId") or "").strip()
            clinical_session = str(event.get("recordingSessionId") or "").strip()
            veterinarian = str(event.get("veterinarian") or "").strip()
            evidence_reference = str(event.get("clinicalEvidenceReference") or "").strip()
            complete_clinical_review = clinically_verified and all(
                (clinical_animal, clinical_session, veterinarian, evidence_reference))
            records.append({
                "schemaVersion": 1,
                "path": Path(os.path.relpath(target.resolve(), manifest_path.resolve().parent)).as_posix(),
                "label": label,
                "groupId": f"animal:{clinical_animal}" if complete_clinical_review else recording_group(event),
                "sourceId": args.source_id,
                "sourceEventId": event_id,
                "deviceId": event.get("deviceId"),
                "barnId": event.get("barnId"),
                "cattleId": event.get("cattleId"),
                "recordedAt": event.get("recordedAt"),
                "reviewStatus": status,
                "reviewLabel": label,
                "reviewer": event.get("reviewer"),
                "reviewedAt": event.get("reviewedAt"),
                "reviewNote": event.get("reviewNote"),
                "rawSha256": actual_hash,
                "normalizedSha256": actual_hash,
                "platformClipSha256": platform_hash,
                "animalId": clinical_animal or None,
                "recordingSessionId": clinical_session or None,
                "veterinarian": veterinarian or None,
                "clinicalEvidenceReference": evidence_reference or None,
                "clinicalVerifiedAt": event.get("clinicallyVerifiedAt"),
                "labelProvenance": (
                    "veterinarian_verified_audio_event" if complete_clinical_review
                    else "platform_review_not_clinically_verified"),
                "clinicalVerified": complete_clinical_review,
                "allowForDiseaseLabels": complete_clinical_review,
                "clinicalReviewRequired": not complete_clinical_review,
            })
        except (OSError, ValueError, urllib.error.URLError) as error:
            skipped += 1
            print(f"skip event {event_id}: {error}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda record: (str(record["label"]), str(record["sourceEventId"])))
    with manifest_path.open("w", encoding="utf-8", newline="\n") as manifest:
        for record in records:
            manifest.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"manifest={manifest_path} records={len(records)}")
    print(f"exported={exported} skipped={skipped}")


if __name__ == "__main__":
    main()
