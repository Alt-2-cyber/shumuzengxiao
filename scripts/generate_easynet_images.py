import base64
import json
import os
from pathlib import Path
import time

import requests
from PIL import Image


API_URL = "https://www.easynet.cc/v1/images/generations"
MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-2")
SIZE = os.environ.get("IMAGE_SIZE", "2048x1152")
QUALITY = os.environ.get("IMAGE_QUALITY", "high")


def die(message: str) -> None:
    raise SystemExit(message)


def load_jobs(path: Path) -> list[dict]:
    jobs: list[dict] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            job = json.loads(raw)
        except json.JSONDecodeError as exc:
            die(f"Invalid JSON on line {line_no}: {exc}")
        if not job.get("prompt") or not job.get("out"):
            die(f"Line {line_no} must include prompt and out.")
        jobs.append(job)
    if not jobs:
        die("No jobs found.")
    return jobs


def request_image(prompt: str, api_key: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "n": 1,
        "size": SIZE,
        "quality": QUALITY,
    }
    last_error = None
    for attempt in range(1, 6):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=420)
            if response.ok:
                body = response.json()
                encoded = body["data"][0]["b64_json"]
                return base64.b64decode(encoded)
            last_error = f"HTTP {response.status_code}: {response.text[:500]}"
        except Exception as exc:
            last_error = repr(exc)
        if attempt < 5:
            wait_s = 12 * attempt
            print(f"Retrying after failure ({last_error}); waiting {wait_s}s", flush=True)
            time.sleep(wait_s)
    die(f"Image request failed: {last_error}")


def verify_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        return image.size


def main() -> int:
    api_key = os.environ.get("EASYNET_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        die("Set EASYNET_API_KEY or OPENAI_API_KEY before running.")

    jobs_path = Path(os.environ.get("IMAGE_JOBS", "tmp_image_prompts.jsonl"))
    out_dir = Path("outputs/imagegen")
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = load_jobs(jobs_path)
    overwrite = os.environ.get("IMAGE_OVERWRITE") == "1"

    for index, job in enumerate(jobs, start=1):
        out_path = out_dir / Path(job["out"]).name
        if out_path.exists() and not overwrite:
            try:
                width, height = verify_image(out_path)
                if abs((width / height) - (16 / 9)) < 0.02:
                    print(f"[{index}/{len(jobs)}] Skipping existing {out_path.name} ({width}x{height})", flush=True)
                    continue
            except Exception:
                pass
        print(f"[{index}/{len(jobs)}] Generating {out_path.name}", flush=True)
        started = time.time()
        image_bytes = request_image(job["prompt"], api_key)
        out_path.write_bytes(image_bytes)
        width, height = verify_image(out_path)
        elapsed = time.time() - started
        print(f"[{index}/{len(jobs)}] Wrote {out_path} ({width}x{height}) in {elapsed:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
