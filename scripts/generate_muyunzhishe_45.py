import base64
import json
import os
from pathlib import Path
import time

import requests
from PIL import Image


API_URL = "https://www.easynet.cc/v1/images/generations"
MODEL = "gpt-image-2"
SIZE = "1536x864"
QUALITY = "low"
JOBS_FILE = Path("tmp_muyunzhishe_45_prompts.jsonl")
OUT_DIR = Path("outputs/muyunzhishe_45_posters")


def load_jobs() -> list[dict]:
    jobs = []
    for line_no, raw in enumerate(JOBS_FILE.read_text(encoding="utf-8").splitlines(), start=1):
        raw = raw.strip()
        if not raw:
            continue
        job = json.loads(raw)
        if not job.get("out") or not job.get("prompt"):
            raise SystemExit(f"Line {line_no} must include out and prompt")
        jobs.append(job)
    return jobs


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        with Image.open(path) as image:
            image.load()
            return image.size
    except Exception:
        return None


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
                return base64.b64decode(body["data"][0]["b64_json"])
            last_error = f"HTTP {response.status_code}: {response.text[:320]}"
        except Exception as exc:
            last_error = repr(exc)
        if attempt < 5:
            wait_s = 15 * attempt
            print(f"Retrying after failure ({last_error}); waiting {wait_s}s", flush=True)
            time.sleep(wait_s)
    raise RuntimeError(last_error)


def main() -> int:
    api_key = os.environ.get("EASYNET_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set EASYNET_API_KEY or OPENAI_API_KEY before running.")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jobs = load_jobs()
    failures = []

    for index, job in enumerate(jobs, start=1):
        out_path = OUT_DIR / Path(job["out"]).name
        existing = image_size(out_path)
        if existing:
            print(f"[{index:02d}/{len(jobs)}] Skip existing {out_path.name} ({existing[0]}x{existing[1]})", flush=True)
            continue

        print(f"[{index:02d}/{len(jobs)}] Generating {out_path.name}", flush=True)
        started = time.time()
        try:
            out_path.write_bytes(request_image(job["prompt"], api_key))
            size = image_size(out_path)
            elapsed = time.time() - started
            if size:
                print(f"[{index:02d}/{len(jobs)}] Wrote {out_path} ({size[0]}x{size[1]}) in {elapsed:.1f}s", flush=True)
            else:
                failures.append((out_path.name, "written file could not be opened"))
                print(f"[{index:02d}/{len(jobs)}] Wrote unreadable file: {out_path}", flush=True)
        except Exception as exc:
            failures.append((out_path.name, str(exc)))
            print(f"[{index:02d}/{len(jobs)}] FAILED {out_path.name}: {exc}", flush=True)
            time.sleep(10)

    if failures:
        fail_path = OUT_DIR / "failures.json"
        fail_path.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Failures: {len(failures)} written to {fail_path}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
