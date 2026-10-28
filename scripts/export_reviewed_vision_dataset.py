#!/usr/bin/env python3
"""Export reviewed MaixCam snapshots into the gated vision manifest format."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


def clinical_fields_complete(event: dict[str, Any]) -> bool:
    return all(str(event.get(field) or "").strip() for field in (
        "clinicalAnimalId", "veterinarian", "clinicalEvidenceReference", "clinicallyVerifiedAt"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8080")
    parser.add_argument("--output", type=Path, default=Path("vision_dataset"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--source-id", default="platform-reviewed-vision")
    parser.add_argument("--statuses", default="normal,confirmed")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--api-key", default=os.environ.get("CLINICAL_API_KEY", ""))
    return parser.parse_args()


def request(url: str, api_key: str, timeout: int = 20) -> urllib.request.addinfourl:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)


def request_json(url: str, api_key: str) -> Any:
    with request(url, api_key) as response:
        return json.loads(response.read().decode("utf-8"))


def download(url: str, api_key: str) -> tuple[bytes, str]:
    with request(url, api_key, 30) as response:
        content_type = response.headers.get_content_type()
        if content_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ValueError(f"unexpected content type {content_type}")
        return response.read(), content_type


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def extension(content_type: str, snapshot_path: str) -> str:
    suffix = Path(urllib.parse.urlparse(snapshot_path).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp"}:
        return suffix
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[content_type]


def recording_id(event: dict[str, Any]) -> str:
    source_key = str(event.get("sourceKey") or "").strip()
    return source_key or f"vision-event-{event.get('id')}"


def main() -> None:
    args = parse_args()
    base_url = args.api.rstrip("/")
    accepted = {value.strip() for value in args.statuses.split(",") if value.strip()}
    manifest_path = args.manifest or args.output / "reviewed_manifest.jsonl"
    payload = request_json(f"{base_url}/api/events/vision", args.api_key)
    events = payload if isinstance(payload, list) else payload.get("value", [])
    records: list[dict[str, Any]] = []
    exported = 0
    skipped = 0
    for event in events:
        status = str(event.get("reviewStatus") or "").strip()
        label = str(event.get("reviewLabel") or "").strip().lower()
        snapshot = str(event.get("snapshotPath") or "").strip()
        event_id = event.get("id")
        if status not in accepted or not label or not TOKEN.fullmatch(label) or not snapshot or event_id is None:
            skipped += 1
            continue
        target = args.output / label / f"event-{event_id}{Path(snapshot).suffix.lower() or '.jpg'}"
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if target.exists() and not args.overwrite:
                content = target.read_bytes()
                content_type = "image/jpeg"
            else:
                content, content_type = download(
                    urllib.parse.urljoin(base_url + "/", snapshot.lstrip("/")), args.api_key)
                target.write_bytes(content)
                exported += 1
            actual_hash = digest(content)
            platform_hash = str(event.get("snapshotSha256") or "").strip().lower()
            if not SHA256.fullmatch(platform_hash) or actual_hash != platform_hash:
                raise ValueError("downloaded snapshot SHA-256 does not match platform archive")
            complete = clinical_fields_complete(event)
            animal = str(event.get("clinicalAnimalId") or "").strip()
            records.append({
                "schemaVersion": 1,
                "image": Path(os.path.relpath(target.resolve(), manifest_path.resolve().parent)).as_posix(),
                "label": label,
                "eventId": event_id,
                "recordingId": recording_id(event),
                "sourceId": args.source_id,
                "snapshotSha256": actual_hash,
                "cameraId": event.get("cameraId"),
                "barnId": event.get("barnId"),
                "animalId": animal or None,
                "recordedAt": event.get("recordedAt"),
                "reviewStatus": status,
                "reviewLabel": label,
                "reviewer": event.get("reviewer"),
                "reviewedAt": event.get("reviewedAt"),
                "veterinarian": event.get("veterinarian") if complete else None,
                "clinicalEvidenceReference": event.get("clinicalEvidenceReference") if complete else None,
                "clinicallyVerifiedAt": event.get("clinicallyVerifiedAt") if complete else None,
                "clinicallyVerified": complete,
                "allowForDiseaseLabels": complete,
                "labelProvenance": "veterinarian_verified_vision_event" if complete
                else "platform_review_not_clinically_verified",
            })
        except (OSError, ValueError, urllib.error.URLError) as error:
            skipped += 1
            print(f"skip event {event_id}: {error}")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    records.sort(key=lambda record: (str(record["label"]), str(record["eventId"])))
    with manifest_path.open("w", encoding="utf-8", newline="\n") as manifest:
        for record in records:
            manifest.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(f"manifest={manifest_path} records={len(records)}")
    print(f"exported={exported} skipped={skipped}")


if __name__ == "__main__":
    main()
