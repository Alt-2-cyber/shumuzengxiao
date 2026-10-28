import base64
import json
import os
from pathlib import Path
import time
from typing import Any

import requests
from PIL import Image


API_URL = "https://www.easynet.cc/v1/responses"
MODEL = "gpt-5.2"
SIZE = os.environ.get("IMAGE_SIZE", "2048x1152")
QUALITY = os.environ.get("IMAGE_QUALITY", "high")


def die(message: str) -> None:
    raise SystemExit(message)


def load_jobs(path: Path) -> list[dict[str, str]]:
    jobs: list[dict[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.strip():
            jobs.append(json.loads(raw))
    return jobs


def extract_image_b64(value: Any) -> str | None:
    if isinstance(value, dict):
        if value.get("type") == "image_generation_call" and value.get("result"):
            return str(value["result"])
        for item in value.values():
            found = extract_image_b64(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = extract_image_b64(item)
            if found:
                return found
    return None


def request_image(prompt: str, api_key: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "model": MODEL,
        "input": prompt,
        "tools": [{"type": "image_generation", "size": SIZE, "quality": QUALITY}],
        "tool_choice": {"type": "image_generation"},
    }
    last_error = None
    for attempt in range(1, 4):
        try:
            response = requests.post(API_URL, headers=headers, json=payload, timeout=600)
            if response.ok:
                body = response.json()
                encoded = extract_image_b64(body)
                if encoded:
                    return base64.b64decode(encoded)
                last_error = f"No image result in response: {response.text[:500]}"
            else:
                last_error = f"HTTP {response.status_code}: {response.text[:500]}"
        except Exception as exc:
            last_error = repr(exc)
        if attempt < 3:
            wait_s = 10 * attempt
            print(f"Retrying after failure ({last_error}); waiting {wait_s}s", flush=True)
            time.sleep(wait_s)
    die(f"Responses image request failed: {last_error}")


def verify_image(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        image.load()
        return image.size


def main() -> int:
    api_key = os.environ.get("EASYNET_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        die("Set EASYNET_API_KEY or OPENAI_API_KEY before running.")

    out_dir = Path("outputs/imagegen")
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = load_jobs(Path(os.environ.get("IMAGE_JOBS", "tmp_image_prompts.jsonl")))
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
        print(f"[{index}/{len(jobs)}] Generating {out_path.name} via Responses image tool", flush=True)
        started = time.time()
        out_path.write_bytes(request_image(job["prompt"], api_key))
        width, height = verify_image(out_path)
        elapsed = time.time() - started
        print(f"[{index}/{len(jobs)}] Wrote {out_path} ({width}x{height}) in {elapsed:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
