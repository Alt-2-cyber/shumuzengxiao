#!/usr/bin/env python3
"""Isolated CPU calf-cough acquisition, nested research training and JSON inference."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[variable] = "1"
sys.dont_write_bytecode = True

import numpy as np
import scipy
from scipy.fft import dct
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "audio-training-data/external/calf-cough-expanded-20261026"
ARTIFACTS = ROOT / "audio-training-data/artifacts/calf-cough-expanded-20261026"
REPORT = ROOT / "docs/2026-10-26-audio-expanded-training.md"
TESTS = ROOT / "tests/test_audio_expand_retrain_20261026.py"
LEGACY_SCRIPT = ROOT / "scripts/train_calf_cough_research_20261026.py"
specification = importlib.util.spec_from_file_location("calf_cough_legacy_readonly", LEGACY_SCRIPT)
legacy = importlib.util.module_from_spec(specification)
specification.loader.exec_module(legacy)
RATE = WINDOW = 8000
SEED = 20261026
CLASSES = ["non_cough", "cough"]
POLICY = {
    "research_only": True, "production_approved": False,
    "allow_for_disease_labels": False, "non_cough_means_healthy": False,
    "animal_independent_validation": False, "scores_calibrated_on_external_data": False,
}
FEATURE_ID = "calf-cough-shape14-logmel40-mfcc13-delta-8khz-v1"
FEATURE_NAMES = [
    *legacy.FEATURE_NAMES,
    *[f"logmel_mean_{i:02d}" for i in range(40)],
    *[f"logmel_std_{i:02d}" for i in range(40)],
    *[f"mfcc_mean_{i:02d}" for i in range(1, 14)],
    *[f"mfcc_std_{i:02d}" for i in range(1, 14)],
    *[f"mfcc_delta_std_{i:02d}" for i in range(1, 14)],
]
CANDIDATES = [
    *[{"kind": "logistic", "C": value} for value in (0.001, 0.01, 0.1, 1.0)],
    *[{"kind": "rbf_svc", "C": value, "gamma": "scale"} for value in (0.1, 1.0, 10.0)],
]
FEATURE_DEFINITION = {
    "id": FEATURE_ID, "feature_count": 133, "feature_names": FEATURE_NAMES,
    "sample_rate_hz": RATE, "window_samples": WINDOW, "hop_samples": WINDOW,
    "observed_prefix_policy": "Never trim zeros; explicit prefix count is at native WAV rate.",
    "normalization": "Subtract mean, divide by AC RMS over observed window samples only.",
    "legacy_shape14": legacy.FEATURE_DEFINITION,
    "zcr_numeric_zero_tolerance_unit_rms": 1e-12,
    "spectral_frames": {"samples": 200, "hop_samples": 80, "fft_samples": 512,
                        "window": "periodic Hann", "tail": "complete frames only"},
    "mel": {"bands": 40, "minimum_hz": 80.0, "maximum_hz": 3800.0,
            "scale": "HTK: 2595*log10(1+f/700)", "triangles": "evaluated at FFT-bin frequencies",
            "normalization": "each triangle sums to one", "log": "natural log(max(mel_power,1e-10))",
            "statistics": ["mean", "population std"]},
    "mfcc": {"transform": "scipy.fft.dct(type=2, norm=ortho)", "coefficients": "1..13 (exclude 0)",
             "statistics": ["mean", "population std", "population std of adjacent frame differences"]},
    "minimum_observed_samples_for_scoring": 800, "silence_ac_rms_full_scale": 1e-8,
    "excluded_from_classifier": ["duration", "padding", "amplitude", "file/source/animal IDs", "quality flags"],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path):
    return legacy.sha256(path)


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def write_json(path, value, compact=False):
    path = Path(path).resolve()
    if not any(path.is_relative_to(base.resolve()) for base in (DATA, ARTIFACTS)):
        raise ValueError("Writes must stay in this experiment's new data/artifact directories")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=None if compact else 2, separators=(",", ":") if compact else None,
                               ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path = Path(path).resolve()
    if not any(path.is_relative_to(base.resolve()) for base in (DATA, ARTIFACTS)):
        raise ValueError("JSONL destination is outside the isolated experiment")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n" for row in rows), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def safe_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ""
    if parsed.port:
        host += f":{parsed.port}"
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
    query = [(key, "REDACTED" if any(word in key.lower() for word in ("token", "signature", "credential", "secret", "key")) else val)
             for key, val in query]
    return urllib.parse.urlunsplit((parsed.scheme, host, parsed.path, urllib.parse.urlencode(query), ""))


def _fetch_public_inline(url, destination, max_bytes=4 * 1024 * 1024, timeout_seconds=18,
                         route="direct", total_seconds=45, request_headers=None):
    """Bounded unauthenticated GET; failure bodies and incomplete state are evidence."""
    if max_bytes < 1 or timeout_seconds <= 0 or total_seconds <= 0:
        raise ValueError("HTTP bounds must be positive")
    if route not in ("direct", "system_proxy"):
        raise ValueError("Unknown local network route")
    if urllib.parse.urlsplit(url).username is not None:
        raise ValueError("Credential-bearing source URLs are not allowed")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    proxies = {} if route == "direct" else urllib.request.getproxies()
    redirects = []

    class Redirects(urllib.request.HTTPRedirectHandler):
        max_redirections = 5

        def redirect_request(self, request, fp, code, message, headers, newurl):
            if urllib.parse.urlsplit(newurl).username is not None:
                raise ValueError("Credential-bearing redirect refused")
            redirects.append({"status": code, "url": safe_url(newurl)})
            return super().redirect_request(request, fp, code, message, headers, newurl)

    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies), Redirects())
    request = urllib.request.Request(url, headers={"User-Agent": "CattleAudioResearch/1.0",
                                                "Accept": "application/json, application/zip, */*",
                                                **(request_headers or {})})
    start = time.monotonic()
    record = {"requested_at_utc": now(), "method": "GET", "url": safe_url(url),
              "route": route, "status": None, "max_bytes": max_bytes,
              "socket_timeout_seconds": timeout_seconds, "total_budget_seconds": total_seconds,
              "bytes": 0, "truncated": False, "complete": False, "redirects": redirects,
              "response_path": str(destination.resolve())}
    response = None
    try:
        try:
            response = opener.open(request, timeout=timeout_seconds)
        except urllib.error.HTTPError as error:
            response = error
        record.update(status=response.status, final_url=safe_url(response.geturl()),
                      content_type=response.headers.get("Content-Type"),
                      content_length=response.headers.get("Content-Length"),
                      content_disposition=response.headers.get("Content-Disposition"),
                      retry_after=response.headers.get("Retry-After"),
                      waf_action=response.headers.get("x-amzn-waf-action"),
                      accept_ranges=response.headers.get("Accept-Ranges"),
                      content_range=response.headers.get("Content-Range"),
                      etag=response.headers.get("ETag"), last_modified=response.headers.get("Last-Modified"),
                      content_md5=response.headers.get("Content-MD5"),
                      location=safe_url(response.headers["Location"]) if response.headers.get("Location") else None)
        with destination.open("wb") as stream:
            while True:
                if time.monotonic() - start > total_seconds:
                    record["error_type"] = "TotalTimeBudgetExceeded"
                    break
                block = response.read(min(65536, max_bytes - record["bytes"] + 1))
                if not block:
                    expected = record.get("content_length")
                    record["complete"] = expected is None or int(expected) == record["bytes"]
                    if not record["complete"]:
                        record["error_type"] = "ContentLengthMismatch"
                    break
                remaining = max_bytes - record["bytes"]
                stream.write(block[:remaining])
                record["bytes"] += min(remaining, len(block))
                if len(block) > remaining:
                    record["truncated"] = True
                    break
    except Exception as error:
        record["error_type"] = type(error).__name__
        if not destination.exists():
            destination.write_bytes(b"")
    finally:
        if response is not None:
            response.close()
    record["elapsed_seconds"] = round(time.monotonic() - start, 3)
    record["sha256"] = sha256(destination)
    return record


def fetch_public(url, destination, max_bytes=4 * 1024 * 1024, timeout_seconds=18,
                 route="direct", total_seconds=45, request_headers=None):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {"url": url, "destination": str(destination.resolve()), "max_bytes": max_bytes,
               "timeout_seconds": timeout_seconds, "route": route, "total_seconds": total_seconds,
               "request_headers": request_headers}
    started = time.monotonic()
    try:
        process = subprocess.run([sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()), "_fetch-worker"],
                                 input=json.dumps(payload), capture_output=True, text=True,
                                 timeout=total_seconds, check=False)
        if process.returncode == 0:
            return json.loads(process.stdout)
        failure = "HTTPWorkerFailed"
    except subprocess.TimeoutExpired:
        failure = "HardTotalTimeBudgetExceeded"
    if not destination.exists():
        destination.write_bytes(b"")
    return {"requested_at_utc": now(), "method": "GET", "url": safe_url(url), "route": route,
            "status": None, "max_bytes": max_bytes, "total_budget_seconds": total_seconds,
            "bytes": destination.stat().st_size, "truncated": False, "complete": False,
            "response_path": str(destination.resolve()), "sha256": sha256(destination),
            "error_type": failure, "elapsed_seconds": round(time.monotonic() - started, 3), "redirects": []}


def resume_figshare():
    """Retrieve standard byte ranges only when the public server explicitly honors Range."""
    url = "https://ndownloader.figshare.com/articles/31979640/versions/1"
    path = DATA / "raw/figshare-31979640/article-31979640.zip"
    partial = DATA / "evidence/figshare-ndownloader-direct.response"
    expected = 133088009
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() and partial.exists():
        with partial.open("rb") as source, path.open("wb") as target:
            for block in iter(lambda: source.read(1024 * 1024), b""):
                target.write(block)
    attempts_path = DATA / "figshare_range_checks.jsonl"
    attempts = read_jsonl(attempts_path) if attempts_path.exists() else []
    for attempt in range(40):
        start = path.stat().st_size if path.exists() else 0
        if start >= expected:
            break
        end = min(start + 4 * 1024**2, expected) - 1
        segment = DATA / "raw/figshare-31979640" / f"range-{start}-{end}.part"
        headers = {"Range": f"bytes={start}-{end}"}
        record = fetch_public(url, segment, max_bytes=5 * 1024**2, timeout_seconds=15,
                              total_seconds=45, request_headers=headers)
        record.update(requested_range=headers["Range"], response_path=relative(segment), expected_total_bytes=expected)
        expected_range = f"bytes {start}-{end}/{expected}"
        accepted = (record["status"] == 206 and record["complete"] and not record["truncated"]
                    and record.get("content_range") == expected_range and record["bytes"] == end - start + 1)
        record["accepted_for_append"] = accepted
        attempts.append(record)
        write_jsonl(attempts_path, attempts)
        print(json.dumps({"range": headers["Range"], "http": record["status"], "bytes": record["bytes"],
                          "content_range": record.get("content_range"), "accepted": accepted}), flush=True)
        if accepted:
            with path.open("ab") as target, segment.open("rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(block)
        elif record["status"] == 200:
            break
        elif attempt >= 2 and not any(row["accepted_for_append"] for row in attempts[-3:]):
            break
    actual = path.stat().st_size if path.exists() else 0
    result = {"url": url, "archive_path": relative(path), "expected_bytes": expected,
              "actual_bytes": actual, "length_matches": actual == expected,
              "sha256": sha256(path) if path.exists() else None, "zip_all_member_crc_passed": False,
              "original_partial_was_complete": False}
    if actual == expected and zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            result["zip_all_member_crc_passed"] = archive.testzip() is None
        if result["zip_all_member_crc_passed"]:
            audit_zip(path, "figshare-complete")
    write_json(DATA / "figshare-download-integrity.json", result)
    return result


def acquire():
    """Query only official public endpoints, keeping raw responses and zero-access evidence."""
    endpoints = [
        ("figshare-article", "https://api.figshare.com/v2/articles/31979640", 4 * 1024**2),
        ("figshare-files", "https://api.figshare.com/v2/articles/31979640/files", 4 * 1024**2),
        ("figshare-version", "https://api.figshare.com/v2/articles/31979640/versions/1", 4 * 1024**2),
        ("figshare-downloader", "https://figshare.com/ndownloader/articles/31979640/versions/1", 160 * 1024**2),
        ("figshare-ndownloader", "https://ndownloader.figshare.com/articles/31979640/versions/1", 160 * 1024**2),
        ("figshare-download-metadata", "https://api.figshare.com/v2/articles/31979640/versions", 4 * 1024**2),
        ("datacite-figshare", "https://api.datacite.org/dois/10.6084/m9.figshare.31979640", 4 * 1024**2),
        ("datacite-calf-cough", "https://api.datacite.org/dois?" + urllib.parse.urlencode({
            "query": "(cattle OR bovine OR calf) AND (cough OR coughing) AND (audio OR sound OR dataset)", "page[size]": 20}), 8 * 1024**2),
        ("zenodo-known", "https://zenodo.org/api/records/17764250", 4 * 1024**2),
        ("zenodo-search", "https://zenodo.org/api/records?" + urllib.parse.urlencode({
            "q": '(cattle OR calf OR bovine) AND (cough OR coughing)', "size": 15}), 8 * 1024**2),
        ("github-calf-cough", "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": "calf cough", "per_page": 10}), 4 * 1024**2),
        ("github-cattle-cough", "https://api.github.com/search/repositories?" + urllib.parse.urlencode({"q": "cattle cough audio", "per_page": 10}), 4 * 1024**2),
        ("huggingface-calf-cough", "https://huggingface.co/api/datasets?search=calf%20cough&limit=10", 4 * 1024**2),
        ("kaggle-calf-cough", "https://www.kaggle.com/api/v1/datasets/list?search=calf%20cough", 4 * 1024**2),
        ("inrae-metadata", "https://entrepot.recherche.data.gouv.fr/api/datasets/:persistentId/?persistentId=doi:10.57745/FP5LA9", 4 * 1024**2),
        ("github-calf-cough-tree", "https://api.github.com/repos/Goosefeatherr/calf-cough-array/git/trees/main?recursive=1", 4 * 1024**2),
    ]
    log_path = DATA / "http_checks.jsonl"
    checks = read_jsonl(log_path) if log_path.exists() else []
    for name, url, cap in endpoints:
        if any(row["name"] == name and row["route"] == "direct" for row in checks):
            continue
        destination = DATA / "evidence" / f"{name}-direct.response"
        record = fetch_public(url, destination, max_bytes=cap, timeout_seconds=15,
                              total_seconds=180 if cap > 10 * 1024**2 else 30)
        record.update(name=name, response_path=relative(destination))
        checks.append(record)
        write_jsonl(log_path, checks)
        print(json.dumps({"source": name, "http": record["status"], "bytes": record["bytes"],
                          "complete": record["complete"], "error_type": record.get("error_type")}), flush=True)
        if record["status"] == 200 and record["complete"] and not record["truncated"]:
            if zipfile.is_zipfile(destination):
                audit_zip(destination, name)
            if name in ("figshare-article", "figshare-version", "figshare-files"):
                try:
                    metadata = read_json(destination)
                except (ValueError, UnicodeError):
                    continue
                files = metadata if isinstance(metadata, list) else metadata.get("files", [])
                for file in files:
                    file_url = file.get("download_url")
                    if not file_url:
                        continue
                    file_id = file["id"]
                    for variant, file_endpoint in (("metadata-url", file_url),
                        ("api-download", f"https://api.figshare.com/v2/file/download/{file_id}")):
                        file_name = f"figshare-file-{file_id}-{variant}"
                        if any(r["name"] == file_name for r in checks):
                            continue
                        target = DATA / "raw" / "figshare-31979640" / f"{file_id}-{variant}.download"
                        row = fetch_public(file_endpoint, target, max_bytes=160 * 1024**2,
                                           timeout_seconds=15, total_seconds=180)
                        row.update(name=file_name, response_path=relative(target), repository_file_metadata=file)
                        checks.append(row)
                        write_jsonl(log_path, checks)
                        if row["status"] == 200 and row["complete"] and zipfile.is_zipfile(target):
                            audit_zip(target, file_name)
    return {"http_checks": len(checks), "data_directory": str(DATA),
            "note": "Downloaded bytes become training audio only after label/license/group audit."}


def audit_zip(path, name):
    with zipfile.ZipFile(path) as archive:
        members = [{"name": item.filename, "bytes": item.file_size, "compressed_bytes": item.compress_size,
                    "crc32": format(item.CRC, "08x"), "directory": item.is_dir()} for item in archive.infolist()]
    write_json(DATA / "evidence" / f"{name}-archive-members.json", {
        "archive": relative(path), "sha256": sha256(path), "members": members,
        "audio_members": sum(Path(item["name"]).suffix.lower() in (".wav", ".flac", ".mp3") for item in members),
        "label_audit_required_before_training": True})


def safe_extract_zip(path, destination):
    destination = Path(destination).resolve()
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 20000 or sum(item.file_size for item in members) > 2 * 1024**3:
            raise ValueError("Archive exceeds extraction file/byte bounds")
        targets = []
        for item in members:
            name = item.filename.replace("\\", "/")
            target = (destination / name).resolve()
            if not target.is_relative_to(destination) or ":" in name or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Unsafe archive member path or symbolic link")
            targets.append(target)
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC mismatch: {bad}")
        for item, target in zip(members, targets, strict=True):
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
    return {"members": len(members), "uncompressed_bytes": sum(item.file_size for item in members),
            "all_member_crc_passed": True}


def inspect_figshare():
    outer = DATA / "raw/figshare-31979640/full-curl.zip"
    if outer.stat().st_size != 133088009:
        raise ValueError("Figshare article package length differs from official HTTP response")
    target = DATA / "raw/figshare-31979640/unpacked"
    outer_result = safe_extract_zip(outer, target)
    audit_zip(outer, "figshare-complete-outer")
    nested = target / "Calf dataset.zip"
    if nested.stat().st_size != 133087841:
        raise ValueError("Nested dataset length differs from DataCite size metadata")
    nested_result = safe_extract_zip(nested, target / "dataset")
    audit_zip(nested, "figshare-complete-nested")
    files = list((target / "dataset").rglob("*"))
    audio_files = [path for path in files if path.is_file() and path.suffix.lower() == ".wav"]
    result = {"checked_at_utc": now(), "source_doi": "10.6084/m9.figshare.31979640",
              "official_download_url": "https://ndownloader.figshare.com/articles/31979640/versions/1",
              "outer": {"path": relative(outer), "bytes": outer.stat().st_size, "sha256": sha256(outer), **outer_result},
              "nested": {"path": relative(nested), "bytes": nested.stat().st_size, "sha256": sha256(nested), **nested_result},
              "wav_files": len(audio_files),
              "directories": dict(Counter(str(path.parent.relative_to(target / "dataset")) for path in audio_files)),
              "other_files": [relative(path) for path in files if path.is_file() and path.suffix.lower() != ".wav"],
              "first_audio_paths": [relative(path) for path in audio_files[:20]],
              "label_and_group_audit_required_before_training": True}
    write_json(DATA / "figshare-complete-integrity.json", result)
    write_json(DATA / "figshare-download-record.json", {
        "method": "curl HTTPS GET, direct local route, no credentials", "url": result["official_download_url"],
        "http_status": 200, "curl_bytes_downloaded": 133088009, "curl_elapsed_seconds": 307.010194,
        "response_header_snapshot": relative(DATA / "evidence/figshare-full-curl.headers"),
        "header_sha256": sha256(DATA / "evidence/figshare-full-curl.headers"),
        "outer_sha256": result["outer"]["sha256"], "nested_sha256": result["nested"]["sha256"],
        "declared_and_actual_lengths_match": True, "both_archives_all_member_crc_passed": True,
        "repository_file_md5": None, "repository_file_md5_note": "Article/file metadata APIs return 403; no upstream MD5 obtained",
        "earlier_partial_response_complete_flag_was_invalid": True,
        "earlier_partial_actual_bytes": 34819511, "standard_range_supported": False,
        "range_note": "Range request returned 200 without Content-Range; partial ranges were never appended"})
    return result


def spectral_features(observed):
    observed = legacy.finite_mono(observed)
    centered = observed - np.mean(observed)
    rms = np.sqrt(np.mean(centered**2))
    if len(observed) < 800 or rms <= 1e-8:
        raise ValueError("Spectral input must be a scoreable observed window")
    normalized = centered / rms
    frames = np.lib.stride_tricks.sliding_window_view(normalized, 200)[::80]
    hann = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(200) / 200)
    power = np.abs(np.fft.rfft(frames * hann, n=512, axis=1))**2
    frequencies = np.fft.rfftfreq(512, 1 / RATE)
    mel_limits = 2595 * np.log10(1 + np.array([80.0, 3800.0]) / 700)
    mel_points = np.linspace(*mel_limits, 42)
    hz = 700 * (10**(mel_points / 2595) - 1)
    rising = (frequencies[None, :] - hz[:-2, None]) / (hz[1:-1, None] - hz[:-2, None])
    falling = (hz[2:, None] - frequencies[None, :]) / (hz[2:, None] - hz[1:-1, None])
    filters = np.maximum(0, np.minimum(rising, falling))
    filters /= filters.sum(axis=1, keepdims=True)
    logmel = np.log(np.maximum(power @ filters.T, 1e-10))
    cepstra = dct(logmel, type=2, norm="ortho", axis=1)[:, 1:14]
    delta_std = np.std(np.diff(cepstra, axis=0), axis=0) if len(cepstra) > 1 else np.zeros(13)
    result = np.r_[legacy.shape_features(observed), logmel.mean(axis=0), logmel.std(axis=0),
                   cepstra.mean(axis=0), cepstra.std(axis=0), delta_std]
    stable_zero = np.where(np.abs(normalized) <= 1e-12, 0.0, normalized)
    result[0] = np.mean(np.signbit(stable_zero[1:]) != np.signbit(stable_zero[:-1]))
    if result.shape != (133,) or not np.isfinite(result).all():
        raise ValueError("Nonfinite/malformed spectral feature vector")
    return result


def make_windows(samples, valid_samples=None):
    windows = legacy.make_windows(samples, valid_samples=valid_samples)
    for window in windows:
        if window["features"] is not None:
            start = window["window_index"] * WINDOW
            count = window["quality"]["observed_samples"]
            window["features"] = spectral_features(np.asarray(samples)[start:start + count])
    return windows


def analyze_wav(source, valid_input_samples=None):
    rate, native = scipy.io.wavfile.read(str(source) if isinstance(source, (str, Path)) else source)
    if native.ndim not in (1, 2) or not native.size:
        raise ValueError("WAV needs at least one sample and channel")
    if native.dtype == np.uint8:
        full_scale = (native.astype(np.float64) - 128) / 128
        rails = (native == 0) | (native == 255)
    elif native.dtype.kind == "i":
        limits = np.iinfo(native.dtype)
        full_scale = native.astype(np.float64) / 2.0**(limits.bits - 1)
        rails = (native == limits.min) | (native == limits.max)
    elif native.dtype.kind == "f":
        full_scale = native.astype(np.float64)
        rails = np.abs(native) >= 1.0
    else:
        raise ValueError("Unsupported WAV sample dtype")
    if not np.isfinite(full_scale).all():
        raise ValueError("Nonfinite WAV input")
    samples = np.mean(full_scale, axis=1) if full_scale.ndim == 2 else full_scale
    native_rails = np.any(rails, axis=1) if rails.ndim == 2 else rails
    metadata = {"source_rate_hz": int(rate), "input_dtype": str(native.dtype),
                "input_channels": int(native.shape[1]) if native.ndim == 2 else 1,
                "input_frames": len(samples), "pcm_full_scale_conversion": "uint8:(value-128)/128; signed:int/2^(bits-1); float:unchanged",
                "native_saturation_fraction_before_downmix": float(np.mean(native_rails)),
                "channel_policy": "arithmetic mean in float before resampling"}
    observed_count = len(samples) if valid_input_samples is None else valid_input_samples
    if isinstance(observed_count, (bool, np.bool_)) or not isinstance(observed_count, (int, np.integer)):
        raise ValueError("Observed prefix must be an integer count at native WAV rate")
    if not 0 <= observed_count <= len(samples) or np.any(samples[observed_count:] != 0):
        raise ValueError("Invalid observed prefix or nonzero declared padding")
    if rate < RATE:
        raise ValueError("Input rate must be >= 8000 Hz")
    container_count = (len(samples) * RATE + rate - 1) // rate
    converted = legacy.resample_audio(samples[:observed_count], rate) if observed_count else np.array([])
    valid_count = len(converted)
    converted = np.pad(converted, (0, container_count - valid_count))
    metadata.update(valid_input_samples=int(observed_count), resampled_observed_samples=valid_count,
                    resampled_container_samples=container_count,
                    coverage_provenance="all_wav_samples_assumed_observed" if valid_input_samples is None else "explicit_valid_prefix",
                    observed_duration_seconds=observed_count / rate,
                    container_duration_seconds=len(samples) / rate,
                    resampling_duration_rounding_seconds=valid_count / RATE - observed_count / rate)
    windows = make_windows(converted, valid_samples=valid_count)
    for window in windows:
        start = int(round(window["start_seconds"] * rate))
        end = min(observed_count, int(round(window["nominal_end_seconds"] * rate)))
        fraction = float(np.mean(native_rails[start:end])) if end > start else 0.0
        window["quality"]["native_clipped_fraction"] = fraction
        if fraction >= 0.01 and window["status"] == "research_score":
            window.update(status="abstain_clipped", features=None)
            window["quality_flags"].append("native_pcm_saturation")
    return windows, metadata


def effective_groups(rows):
    """Union files sharing a declared parent, exact WAV bytes or decoded PCM."""
    parents = list(range(len(rows)))

    def find(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    seen = {}
    for i, row in enumerate(rows):
        keys = [(field, row.get(field)) for field in ("file_unit_id", "raw_sha256", "pcm_sha256", "parent_recording_id", "animal_id", "split_group_id", "content_linked_split_group_id")]
        for field, value in keys:
            if value is None:
                continue
            key = (field, value)
            if key in seen:
                parents[find(i)] = find(seen[key])
            else:
                seen[key] = i
    return np.array([f"content-parent-component-{find(i):05d}" for i in range(len(rows))])


def new_pipeline(candidate):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    if candidate.get("kind", "logistic") == "logistic":
        classifier = LogisticRegression(C=candidate["C"], solver="lbfgs", max_iter=3000, tol=1e-9,
                                        class_weight="balanced", random_state=SEED)
    elif candidate["kind"] == "rbf_svc":
        classifier = SVC(C=candidate["C"], gamma=candidate["gamma"], kernel="rbf", class_weight="balanced",
                         probability=False, tol=1e-7, random_state=SEED)
    else:
        raise ValueError("Unknown compact model kind")
    return Pipeline([("scaler", StandardScaler()), ("classifier", classifier)])


def decision_score(pipeline, features):
    return expit(pipeline.decision_function(features))


def select_nested(features, labels, groups, candidates=None, seed=SEED):
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import StratifiedGroupKFold

    candidates = CANDIDATES if candidates is None else candidates
    folds = list(StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=seed).split(features, labels, groups))
    fold_audit, candidate_audit = [], []
    for train, test in folds:
        if set(groups[train]) & set(groups[test]) or set(labels[train]) != {0, 1} or set(labels[test]) != {0, 1}:
            raise ValueError("Nested fold overlaps groups or lacks an acoustic class")
        fold_audit.append({"train_indices": train.tolist(), "test_indices": test.tolist(),
                           "scaler_mean": np.mean(features[train], axis=0).tolist(),
                           "training_group_count": len(set(groups[train])), "heldout_group_count": len(set(groups[test]))})
    for candidate in candidates:
        scores = []
        for train, test in folds:
            pipeline = new_pipeline(candidate).fit(features[train], labels[train])
            scores.append(float(balanced_accuracy_score(labels[test], decision_score(pipeline, features[test]) >= 0.5)))
        candidate_audit.append({"candidate": candidate, "inner_balanced_accuracy": scores, "mean": float(np.mean(scores))})
    best = max(range(len(candidates)), key=lambda i: candidate_audit[i]["mean"])
    return dict(candidates[best]), {"selection_metric": "mean_inner_balanced_accuracy", "tie_break": "first_predeclared_candidate",
                                    "seed": seed, "folds": fold_audit, "candidates": candidate_audit, "selected_index": best}


def portable_probability(model, features):
    features = np.atleast_2d(np.asarray(features, dtype=np.float64))
    mean = np.asarray(model["scaler_mean"], dtype=np.float64)
    scale = np.asarray(model["scaler_scale"], dtype=np.float64)
    if features.ndim != 2 or mean.ndim != 1 or features.shape[1] != len(mean) or scale.shape != mean.shape:
        raise ValueError("Portable model feature dimensions differ")
    if not all(np.isfinite(array).all() for array in (features, mean, scale)) or np.any(scale <= 0):
        raise ValueError("Portable features/scaler must be finite with positive scales")
    standardized = (features - mean) / scale
    if model["model_type"] == "standardized_binary_logistic_regression":
        coefficients = np.asarray(model["coefficients"], dtype=np.float64)
        intercept = float(model["intercept"])
        if coefficients.shape != mean.shape or not np.isfinite(coefficients).all() or not np.isfinite(intercept):
            raise ValueError("Invalid logistic coefficients")
        margin = standardized @ coefficients + intercept
    elif model["model_type"] == "standardized_binary_rbf_svc":
        support = np.asarray(model["support_vectors"], dtype=np.float64)
        dual = np.asarray(model["dual_coefficients"], dtype=np.float64)
        gamma, intercept = float(model["gamma"]), float(model["intercept"])
        if support.ndim != 2 or support.shape[1] != len(mean) or dual.shape != (len(support),):
            raise ValueError("Invalid RBF support dimensions")
        if not all(np.isfinite(a).all() for a in (support, dual)) or not np.isfinite([gamma, intercept]).all() or gamma <= 0:
            raise ValueError("Invalid RBF coefficients")
        # Direct subtraction avoids cancellation for nearly equal support vectors.
        distance = np.sum((standardized[:, None, :] - support[None, :, :])**2, axis=2)
        margin = np.exp(-gamma * distance) @ dual + intercept
    else:
        raise ValueError("Unsupported portable model type")
    return expit(margin)


def export_model(pipeline, rows, indices, candidate):
    scaler, classifier = pipeline.named_steps["scaler"], pipeline.named_steps["classifier"]
    model = {"schema_version": 1, "model_version": "audio-calf-cough-expanded-20261026-v1", **POLICY,
             "clinicalDiagnosis": False, "clinical_diagnosis": False,
             "task": "author_reported_calf_cough_acoustic_event",
             "classes": CLASSES, "threshold": 0.5, "feature_id": FEATURE_ID, "feature_names": FEATURE_NAMES,
             "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
             "intercept": float(classifier.intercept_[0]), "fit_candidate": candidate,
             "training_file_count": len(indices), "training_file_ids": [rows[int(i)]["file_unit_id"] for i in indices],
             "training_raw_sha256": [rows[int(i)]["raw_sha256"] for i in indices],
             "training_script_sha256": sha256(Path(__file__)), "legacy_dependency_sha256": sha256(LEGACY_SCRIPT),
             "score_interpretation": "Uncalibrated sigmoid of signed acoustic event margin; not a clinical probability."}
    if classifier.classes_.tolist() != [0, 1]:
        raise ValueError("Unexpected classifier event order")
    if candidate.get("kind", "logistic") == "logistic":
        if np.any(classifier.n_iter_ >= 3000):
            raise ValueError("Logistic model did not converge")
        model.update(model_type="standardized_binary_logistic_regression", coefficients=classifier.coef_[0].tolist())
    else:
        model.update(model_type="standardized_binary_rbf_svc", support_vectors=classifier.support_vectors_.tolist(),
                     dual_coefficients=classifier.dual_coef_[0].tolist(), gamma=float(classifier._gamma))
    return model


def load_model(path):
    model = read_json(path)
    if model.get("schema_version") != 1 or model.get("feature_id") != FEATURE_ID:
        raise ValueError("Incompatible model schema or feature extractor")
    if model.get("feature_names") != FEATURE_NAMES or model.get("classes") != CLASSES or model.get("threshold") != 0.5:
        raise ValueError("Incompatible model feature/class order or threshold")
    if any(model.get(key) != value for key, value in POLICY.items()):
        raise ValueError("Portable model lacks required research scope")
    if model.get("clinical_diagnosis") is not False or model.get("clinicalDiagnosis") is not False:
        raise ValueError("Clinical diagnosis is forbidden for this event model")
    if not isinstance(model.get("model_version"), str) or not model["model_version"]:
        raise ValueError("Missing model version")
    if len(model.get("scaler_mean", [])) != len(FEATURE_NAMES):
        raise ValueError("Incorrect model feature count")
    portable_probability(model, np.zeros((1, len(FEATURE_NAMES))))
    return model


def input_contract():
    result = {"schema_version": 1, **POLICY, "clinical_diagnosis": False, "clinicalDiagnosis": False,
              "python_api": "predict(wav_path, model_path=ARTIFACTS/'model.json', valid_input_samples=None) -> dict",
              "script_path": str(Path(__file__).resolve()), "default_model_path": str(ARTIFACTS / "model.json"),
              "cli": "python -B -X utf8 scripts/audio_expand_retrain_20261026.py predict WAV --model MODEL_JSON",
              "sample_rate_hz": RATE, "window_samples": WINDOW, "hop_samples": WINDOW,
              "minimum_input_rate_hz": RATE, "minimum_observed_window_samples": 800,
              "wav_decode": "uint8: (value-128)/128; signed PCM: value/2^(bits-1); float PCM: unchanged",
              "channels": "Arithmetic mean in float; per-frame saturation checks precede downmix",
              "resampler": "scipy.signal.resample_poly; gcd ratio; Kaiser beta 5; constant boundary padding",
              "coverage": "All WAV samples are observed unless a native-rate contiguous prefix count is explicit. Never trim zeros.",
              "normalization": "Per-window DC removal and AC-RMS normalization; amplitude is not a model input",
              "score_semantics": "score/cough_score is uncalibrated sigmoid signed margin for author cough event labels",
              "decision_threshold": 0.5, "aggregate_event": None,
              "window_fields": {"start_seconds": "Nominal original offset", "end_seconds": "Nominal end offset",
                  "observed_end_seconds": "Offset of last observed sample boundary",
                  "status": ["scored", "abstain_silence", "abstain_too_short", "abstain_no_observed_samples", "abstain_clipped"],
                  "label": ["cough", "non_cough", None], "score": "number in [0,1] or null",
                  "abstention_reason": "status suffix, or null when scored"},
              "fixed_engineering_abstentions": {"silence": "AC RMS <= 1e-8 full scale", "too_short": "<800 observed 8k samples",
                  "clipped": ">=1% native sample frames at integer PCM rail or abs(float)>=1; any channel"},
              "dependencies_prediction": ["Python", "NumPy", "SciPy", str(LEGACY_SCRIPT)],
              "negative_label_interpretation": "non_cough is an acoustic label; never a healthy diagnosis"}
    write_json(ARTIFACTS / "input_contract.json", result)
    return result


def predict(wav_path, model_path=ARTIFACTS / "model.json", valid_input_samples=None):
    """Return research acoustic events only; safe to import without training dependencies."""
    model_path = Path(model_path)
    model = load_model(model_path)
    windows, metadata = analyze_wav(wav_path, valid_input_samples)
    output = []
    for window in windows:
        vector = window.pop("features")
        score = float(portable_probability(model, vector)[0]) if vector is not None else None
        label = CLASSES[int(score >= 0.5)] if score is not None else None
        window.update(end_seconds=window["nominal_end_seconds"],
                      observed_end_seconds=window["start_seconds"] + window["quality"]["observed_samples"] / RATE,
                      label=label, score=score, cough_score=score, predicted_event=label,
                      source_label_scores={"non_cough": 1 - score, "cough": score} if score is not None else None,
                      abstention_reason=window["status"].removeprefix("abstain_") if score is None else None)
        if score is not None:
            window["status"] = "scored"
        output.append(window)
    return {"schema_version": 1, **POLICY, "clinical_diagnosis": False, "clinicalDiagnosis": False,
            "model_version": model["model_version"], "model_sha256": sha256(model_path),
            "model_path": str(model_path.resolve()), "input_path": str(Path(wav_path).resolve()),
            "input_duration_seconds": metadata["container_duration_seconds"], "input": metadata,
            "sample_rate_hz": RATE, "window_samples": WINDOW, "windows": output,
            "aggregate_event": None, "aggregation_note": "No validated aggregation of 1s windows into a clip event.",
            "score_interpretation": model["score_interpretation"], "source_label_order": CLASSES}


def self_test():
    import unittest

    test_spec = importlib.util.spec_from_file_location("audio_expanded_tests", TESTS)
    test_module = importlib.util.module_from_spec(test_spec)
    test_spec.loader.exec_module(test_module)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_module))
    return {"passed": result.wasSuccessful(), "tests_run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors), "details": output.getvalue()}


def clip_features(path):
    samples, rate, metadata = legacy.decode_wav(str(path))
    converted = legacy.resample_audio(samples, rate)
    quality = legacy.signal_quality(converted)
    reason = None
    if len(converted) < 800:
        reason = "abstain_too_short"
    elif quality["rms_ac_full_scale"] <= 1e-8:
        reason = "abstain_silence"
    elif metadata["source_saturation_fraction_before_downmix"] >= 0.01:
        reason = "abstain_clipped"
    pcm = hashlib.sha256(int(rate).to_bytes(4, "little") + np.asarray(samples, dtype="<f8").tobytes()).hexdigest()
    info = {**metadata, "duration_seconds": len(samples) / rate,
            "resampled_samples": len(converted), "resampled_quality": quality,
            "pcm_sha256": pcm, "exclusion_reason": reason}
    if reason:
        return None, None, info
    return spectral_features(converted), legacy.shape_features(converted), info


def audit_data():
    """Audit source event labels only; never upgrade inferred filename families to animal IDs."""
    original_rows, _, _, original_evidence = legacy.load_dataset()
    rows, excluded, vectors, old_vectors = [], [], [], []
    for original in original_rows:
        row = dict(original)
        x, old, info = clip_features(ROOT / row["path"])
        if x is None:
            raise ValueError("An original 40-file input unexpectedly fails the fixed quality policy")
        row.update(source_id="inrae-FP5LA9", is_additional_recording=False, pcm_sha256=info["pcm_sha256"],
                   parent_recording_id=None, split_group_id=legacy.UNKNOWN_GROUP,
                   split_group_basis="All original animal/session/parent mappings unknown; one conservative development group",
                   clip_metadata=info, observation_unit="one complete original source clip; no slices or augmentation")
        rows.append(row)
        vectors.append(x)
        old_vectors.append(old)
    integrity_path = DATA / "figshare-complete-integrity.json"
    inventory = None
    if integrity_path.exists():
        inventory = read_json(integrity_path)
        for field in ("outer", "nested"):
            source = ROOT / inventory[field]["path"]
            if source.stat().st_size != inventory[field]["bytes"] or sha256(source) != inventory[field]["sha256"]:
                raise ValueError("Downloaded Figshare archive changed since CRC audit")
        base = DATA / "raw/figshare-31979640/unpacked/dataset/Calf dataset/test"
        for path in sorted(base.rglob("*.wav"), key=lambda p: p.as_posix().lower()):
            author_label = path.parent.name.lower()
            if author_label not in {"ab", "cough", "excretion", "metal"}:
                raise ValueError("Unreviewed Figshare source class")
            match = re.fullmatch(r"[^_]+_\d+(.*)", path.stem)
            token = re.sub(r"\d+$", "", match.group(1).lower()) if match else ""
            family = token or "unmapped"
            x, old, info = clip_features(path)
            row = {"row_index": None, "file_unit_id": "figshare-31979640:" + path.relative_to(base).as_posix(),
                   "path": relative(path), "raw_sha256": sha256(path), "raw_bytes": path.stat().st_size,
                   "pcm_sha256": info["pcm_sha256"], "source_id": "figshare-31979640", "source_doi": "10.6084/m9.figshare.31979640",
                   "is_additional_recording": True, "original_label": author_label,
                   "target": 1 if author_label == "cough" else 0 if author_label in {"excretion", "metal"} else None,
                   "label_provenance": "Author archive directory; DataCite explicitly describes a calf dataset",
                   "source_group_id": "figshare-31979640:animals-sessions-unknown", "source_group_status": "source group unknown",
                   "animal_id": None, "recording_session_id": None, "parent_recording_id": None,
                   "split_group_id": f"figshare-31979640:unverified-filename-family:{family}",
                   "split_group_basis": "Casefold filename suffix after initial event number, then strip trailing digits; grouping heuristic only",
                   "source_partition": "test (only author partition supplied); local research repartition explicitly declared",
                   "clinical_verified": False, "allow_for_disease_labels": False,
                   "license": {"id": "CC-BY-4.0", "url": "https://creativecommons.org/licenses/by/4.0/legalcode",
                               "evidence": relative(DATA / "evidence/datacite-figshare-direct.response")},
                   "attribution": "Ma, Juncheng (2026), Dataset for Boosting cough recognition of livestock animals...; doi:10.6084/m9.figshare.31979640",
                   "clip_metadata": info, "observation_unit": "one complete original source clip; no slices or augmentation"}
            if author_label == "ab":
                row["exclusion_reason"] = "Unexplained author label ab; no inferred cough/noncough mapping"
            elif info["exclusion_reason"]:
                row["exclusion_reason"] = info["exclusion_reason"]
            else:
                row["row_index"] = len(rows)
                rows.append(row)
                vectors.append(x)
                old_vectors.append(old)
                continue
            excluded.append(row)
    initial_groups = effective_groups(rows)
    seen_pcm, kept_rows, kept_vectors, kept_old_vectors = {}, [], [], []
    for row, vector, old, group in zip(rows, vectors, old_vectors, initial_groups, strict=True):
        row["content_linked_split_group_id"] = str(group)
        if row["pcm_sha256"] in seen_pcm:
            prior = seen_pcm[row["pcm_sha256"]]
            if row["target"] != prior["target"]:
                raise ValueError("Duplicate audio has contradictory author event labels")
            excluded.append({**row, "row_index": None, "exclusion_reason": "duplicate_decoded_pcm", "duplicate_of": prior["file_unit_id"]})
        else:
            seen_pcm[row["pcm_sha256"]] = row
            kept_rows.append(row)
            kept_vectors.append(vector)
            kept_old_vectors.append(old)
    rows, vectors, old_vectors = kept_rows, kept_vectors, kept_old_vectors
    for i, row in enumerate(rows):
        row["row_index"] = i
    groups = effective_groups(rows)
    for row, group in zip(rows, groups, strict=True):
        row["effective_split_group"] = str(group)
    hashes = [{"path": row["path"], "sha256": row["raw_sha256"], "role": "included_original_wav"} for row in rows]
    hashes.extend({"path": row["path"], "sha256": row["raw_sha256"], "role": "excluded_original_wav"} for row in excluded)
    hashes.extend(original_evidence)
    for path in sorted(DATA.rglob("*")):
        if path.is_file() and path.suffix in {".response", ".headers"}:
            hashes.append({"path": relative(path), "sha256": sha256(path), "role": "public_source_snapshot"})
    if inventory:
        hashes.extend({"path": inventory[key]["path"], "sha256": inventory[key]["sha256"], "role": "complete_source_zip"} for key in ("outer", "nested"))
    source_counts = {"original_inrae_wavs": 40, "additional_figshare_wavs_downloaded": len(excluded) + len(rows) - 40,
                     "additional_author_cough": sum(r["source_id"] == "figshare-31979640" and r["original_label"] == "cough" for r in rows + excluded),
                     "additional_author_class_counts": dict(Counter(r["original_label"] for r in rows[40:] + excluded)),
                     "included_files": len(rows), "included_target_counts": dict(Counter(CLASSES[r["target"]] for r in rows)),
                     "included_additional_files": len(rows) - 40, "excluded_additional_files": len(excluded),
                     "unique_included_pcm_recordings": len({r["pcm_sha256"] for r in rows}),
                     "exclusion_counts": dict(Counter(r["exclusion_reason"] for r in excluded)),
                     "actual_originals_not_augmentations": True, "clinical_verified_files": 0,
                     "verified_animal_groups": 0, "verified_recording_sessions": 0,
                     "effective_split_groups": len(set(groups)), "unverified_filename_families": len({r["split_group_id"] for r in rows[40:]}),
                     "source_formats": dict(Counter(f'{r["clip_metadata"]["source_rate_hz"]}Hz/{r["clip_metadata"]["input_dtype"]}/{r["clip_metadata"]["input_channels"]}ch' for r in rows + excluded))}
    write_jsonl(DATA / "included_manifest.jsonl", rows)
    write_jsonl(DATA / "excluded_manifest.jsonl", excluded)
    write_json(DATA / "source_audit.json", {"checked_at_utc": now(), **POLICY, **source_counts,
        "figshare_integrity": inventory, "source_snapshots": hashes,
        "unknowns": ["animal, session, parent recording and clinical diagnosis mappings", "author ab class semantics"],
        "inrae_license_scope": "Etalab 2.0 repository; research/education preprint scope conflict; research only",
        "figshare_license": "CC BY 4.0; attribution and changes recorded; no clinical records supplied"})
    return rows, np.asarray(vectors), np.asarray(old_vectors), np.array([row["target"] for row in rows]), groups, hashes, source_counts


def make_split_plan(rows, labels, groups):
    from sklearn.model_selection import StratifiedGroupKFold

    original = np.array([i for i, row in enumerate(rows) if not row["is_additional_recording"]], dtype=int)
    additional = np.array([i for i, row in enumerate(rows) if row["is_additional_recording"]], dtype=int)
    original_groups = set(groups[original])
    candidates = np.array([i for i in additional if groups[i] not in original_groups], dtype=int)
    if len(set(groups[candidates])) < 5:
        raise ValueError("At least five additional content/filename groups are required for a reserved holdout")
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    _, relative_holdout = next(iter(splitter.split(np.zeros((len(candidates), 1)), labels[candidates], groups[candidates])))
    holdout = candidates[relative_holdout]
    development = np.array(sorted(set(range(len(rows))) - set(holdout)), dtype=int)
    if set(groups[development]) & set(groups[holdout]) or set(labels[holdout]) != {0, 1}:
        raise ValueError("The fixed holdout overlaps groups or lacks an event class")
    folds = []
    for number, (train, test) in enumerate(splitter.split(np.zeros((len(development), 1)), labels[development], groups[development]), 1):
        train, test = development[train], development[test]
        if set(groups[train]) & set(groups[test]) or set(labels[train]) != {0, 1} or set(labels[test]) != {0, 1}:
            raise ValueError("Expanded outer fold overlaps groups or lacks an event class")
        folds.append({"fold": number, "train_indices": train.tolist(), "test_indices": test.tolist()})
    return {"seed": SEED, "selection_before_any_model_outcome": True,
            "final_holdout_rule": "First StratifiedGroupKFold(5, shuffle=True, seed=20261026) split of new groups; originals stay development",
            "group_basis": "Unknown source group for all original INRAE files; broad unverified filename suffix families, merged by duplicate PCM, for Figshare",
            "animal_or_session_independence_established": False,
            "development_indices": development.tolist(), "final_holdout_indices": holdout.tolist(),
            "development_groups": sorted(set(groups[development])), "final_holdout_groups": sorted(set(groups[holdout])),
            "development_outer_folds": folds}


def export_baseline(pipeline, rows, indices):
    scaler, classifier = pipeline.named_steps["scaler"], pipeline.named_steps["classifier"]
    return {"schema_version": 1, **POLICY, "clinical_diagnosis": False,
            "model_type": "standardized_binary_logistic_regression", "feature_id": legacy.FEATURE_DEFINITION["id"],
            "feature_names": legacy.FEATURE_NAMES, "classes": CLASSES, "threshold": 0.5,
            "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
            "coefficients": classifier.coef_[0].tolist(), "intercept": float(classifier.intercept_[0]),
            "fit_parameters": {"C": 0.1, "class_weight": None, "solver": "lbfgs", "max_iter": 2000, "tol": 1e-8},
            "training_file_ids": [rows[int(i)]["file_unit_id"] for i in indices],
            "training_raw_sha256": [rows[int(i)]["raw_sha256"] for i in indices]}


def predictions(rows, indices, scores, fold, model_name):
    return [{"row_index": int(i), "file_unit_id": rows[int(i)]["file_unit_id"],
             "raw_sha256": rows[int(i)]["raw_sha256"], "target": int(rows[int(i)]["target"]),
             "source_author_label": rows[int(i)]["original_label"], "fold": fold,
             "model": model_name, "cough_score": float(score), "predicted_event": CLASSES[int(score >= 0.5)],
             "true_event": CLASSES[rows[int(i)]["target"]], "research_only": True}
            for i, score in zip(indices, scores, strict=True)]


def evaluate_cv(name, rows, x, baseline_x, labels, groups, folds):
    baseline_scores, spectral_scores = {}, {}
    audits, outputs, parity = [], [], []
    for fold in folds:
        number = fold["fold"]
        train, test = np.array(fold["train_indices"]), np.array(fold["test_indices"])
        candidate, inner = select_nested(x[train], labels[train], groups[train], seed=SEED + number)
        for inner_fold in inner["folds"]:
            inner_fold["train_global_indices"] = train[inner_fold["train_indices"]].tolist()
            inner_fold["test_global_indices"] = train[inner_fold["test_indices"]].tolist()
        fitted = new_pipeline(candidate).fit(x[train], labels[train])
        baseline = legacy.new_pipeline().fit(baseline_x[train], labels[train])
        model, old_model = export_model(fitted, rows, train, candidate), export_baseline(baseline, rows, train)
        model_path = ARTIFACTS / "fold_models" / name / f"fold_{number}.json"
        baseline_path = ARTIFACTS / "fold_models" / name / f"baseline_{number}.json"
        write_json(model_path, model)
        write_json(baseline_path, old_model)
        new_score = portable_probability(read_json(model_path), x[test])
        old_score = portable_probability(read_json(baseline_path), baseline_x[test])
        parity.append(float(np.max(np.abs(new_score - decision_score(fitted, x[test])))))
        parity.append(float(np.max(np.abs(old_score - baseline.predict_proba(baseline_x[test])[:, 1]))))
        for index, old, new in zip(test, old_score, new_score, strict=True):
            baseline_scores[int(index)], spectral_scores[int(index)] = float(old), float(new)
        outputs.extend(predictions(rows, test, old_score, number, "fixed_baseline"))
        outputs.extend(predictions(rows, test, new_score, number, "nested_spectral"))
        group_overlap = sorted(set(groups[train]) & set(groups[test]))
        raw_overlap = sorted({rows[i]["raw_sha256"] for i in train} & {rows[i]["raw_sha256"] for i in test})
        if group_overlap or raw_overlap:
            raise ValueError("Outer group/content leakage")
        audits.append({**fold, "train_file_ids": [rows[i]["file_unit_id"] for i in train],
                       "test_file_ids": [rows[i]["file_unit_id"] for i in test],
                       "group_overlap": group_overlap, "raw_sha256_overlap": raw_overlap,
                       "candidate": candidate, "inner_selection": inner,
                       "model_path": relative(model_path), "baseline_model_path": relative(baseline_path),
                       "fixed_baseline_metrics": legacy.metrics_for(labels[test], old_score),
                       "nested_spectral_metrics": legacy.metrics_for(labels[test], new_score)})
        print(json.dumps({"experiment": name, "fold": number, "train": len(train), "test": len(test),
                          "candidate": candidate, "baseline_accuracy": audits[-1]["fixed_baseline_metrics"]["accuracy"],
                          "spectral_accuracy": audits[-1]["nested_spectral_metrics"]["accuracy"]}), flush=True)
    indices = np.array(sorted(spectral_scores))
    old = np.array([baseline_scores[int(i)] for i in indices])
    new = np.array([spectral_scores[int(i)] for i in indices])
    write_jsonl(ARTIFACTS / f"{name}_oof_predictions.jsonl", sorted(outputs, key=lambda item: (item["row_index"], item["model"])))
    result = {"file_count": len(indices), "indices": indices.tolist(), "folds": audits,
              "fixed_baseline_metrics": legacy.metrics_for(labels[indices], old),
              "nested_spectral_metrics": legacy.metrics_for(labels[indices], new),
              "portable_sklearn_max_absolute_error": max(parity),
              "group_basis": "file IDs for original comparison; unverified filename/duplicate groups for expanded development",
              "animal_independent_validation": False}
    write_json(ARTIFACTS / f"{name}_report.json", result)
    return result


def train():
    import sklearn
    from threadpoolctl import threadpool_limits

    start = time.monotonic()
    checks = self_test()
    if not checks["passed"]:
        raise ValueError(checks["details"])
    rows, x, old_x, labels, groups, provenance, counts = audit_data()
    split_plan = make_split_plan(rows, labels, groups)
    write_json(ARTIFACTS / "split_plan.json", split_plan)
    protocol = {"frozen_at_utc": now(), "script_sha256": sha256(Path(__file__)),
                "legacy_script_sha256": sha256(LEGACY_SCRIPT), "input_manifest_sha256": sha256(DATA / "included_manifest.jsonl"),
                "candidates": CANDIDATES, "selection_metric": "mean inner 3-fold balanced accuracy; first candidate wins ties",
                "threshold": 0.5, "outer_development_folds": 5,
                "holdout_policy": "No held-out group used for training, standardization, feature fitting, selection or threshold tuning",
                "source_author_partition": "Only Figshare test/ exists; local development/holdout split is a new research experiment",
                "observation_unit": "One complete original event clip; variable length, no copied interval labels and no augmentations",
                "feature_definition": FEATURE_DEFINITION, "split_plan": split_plan}
    write_json(ARTIFACTS / "protocol.json", protocol)
    input_contract()
    write_json(ARTIFACTS / "feature_definition.json", FEATURE_DEFINITION)
    write_json(ARTIFACTS / "provenance.json", {"files": provenance, "source_counts": counts, **POLICY})
    write_jsonl(ARTIFACTS / "input_manifest.jsonl", rows)
    original_labels = labels[:40]
    original_ids = np.array([row["file_unit_id"] for row in rows[:40]])
    original_folds = [{"fold": number, "train_indices": train.tolist(), "test_indices": test.tolist()}
                      for number, (train, test) in enumerate(legacy.build_folds(original_labels, original_ids), 1)]
    prior_folds = read_json(legacy.ARTIFACTS / "fold_assignments.json")["folds"]
    for current, prior in zip(original_folds, prior_folds, strict=True):
        if current["train_indices"] != prior["train_indices"] or current["test_indices"] != prior["test_indices"]:
            raise ValueError("Original paired comparison no longer matches legacy folds")
    with threadpool_limits(limits=1):
        original = evaluate_cv("original40_comparison", rows[:40], x[:40], old_x[:40], original_labels,
                               original_ids, original_folds)
        expanded = evaluate_cv("expanded_development", rows, x, old_x, labels, groups, split_plan["development_outer_folds"])
        dev, holdout = np.array(split_plan["development_indices"]), np.array(split_plan["final_holdout_indices"])
        candidate, final_inner = select_nested(x[dev], labels[dev], groups[dev], seed=SEED)
        for fold in final_inner["folds"]:
            fold["train_global_indices"] = dev[fold["train_indices"]].tolist()
            fold["test_global_indices"] = dev[fold["test_indices"]].tolist()
        write_json(ARTIFACTS / "final_development_selection.json", final_inner)
        fitted = new_pipeline(candidate).fit(x[dev], labels[dev])
        baseline = legacy.new_pipeline().fit(old_x[dev], labels[dev])
        model, old_model = export_model(fitted, rows, dev, candidate), export_baseline(baseline, rows, dev)
        model.update(source_counts=counts, training_source_file_counts=dict(Counter(rows[i]["source_id"] for i in dev)),
                     split_manifest_sha256=sha256(ARTIFACTS / "split_plan.json"),
                     attribution="INRAE/ENVT Mach et al. (2026) doi:10.57745/FP5LA9; Ma, Juncheng (2026) doi:10.6084/m9.figshare.31979640",
                     license_scope="Research only: INRAE Etalab/preprint scope conflict; Figshare CC BY 4.0 attribution retained")
        write_json(ARTIFACTS / "model.json", model, compact=True)
        write_json(ARTIFACTS / "baseline_model.json", old_model)
        write_json(ARTIFACTS / "holdout_unseal_record.json", {
            "models_frozen_before_holdout_scoring_at_utc": now(), "model_sha256": sha256(ARTIFACTS / "model.json"),
            "baseline_model_sha256": sha256(ARTIFACTS / "baseline_model.json"),
            "development_selection_sha256": sha256(ARTIFACTS / "final_development_selection.json"),
            "split_plan_sha256": sha256(ARTIFACTS / "split_plan.json"), "threshold": 0.5, "candidate": candidate})
        score = portable_probability(load_model(ARTIFACTS / "model.json"), x[holdout])
        old_score = portable_probability(read_json(ARTIFACTS / "baseline_model.json"), old_x[holdout])
        holdout_predictions = predictions(rows, holdout, score, "final_reserved_holdout", "nested_spectral")
        holdout_predictions += predictions(rows, holdout, old_score, "final_reserved_holdout", "fixed_baseline")
        write_jsonl(ARTIFACTS / "final_holdout_predictions.jsonl", holdout_predictions)
        final_parity = float(np.max(np.abs(score - decision_score(fitted, x[holdout]))))
    final = {"indices": holdout.tolist(), "group_count": len(set(groups[holdout])),
             "file_count": len(holdout), "target_counts": dict(Counter(CLASSES[labels[i]] for i in holdout)),
             "source_author_class_counts": dict(Counter(rows[i]["original_label"] for i in holdout)),
             "fixed_baseline_metrics": legacy.metrics_for(labels[holdout], old_score),
             "nested_spectral_metrics": legacy.metrics_for(labels[holdout], score),
             "portable_sklearn_max_absolute_error": final_parity, "threshold_tuned_on_holdout": False,
             "animal_independent_validation": False, "unknown_source_groups_shared_with_development": True}
    write_json(ARTIFACTS / "final_holdout_report.json", final)
    np.savez_compressed(ARTIFACTS / "features.npz", X=x, X_baseline=old_x, y=labels, groups=groups,
                        file_ids=np.array([row["file_unit_id"] for row in rows]),
                        raw_sha256=np.array([row["raw_sha256"] for row in rows]),
                        development_indices=dev, final_holdout_indices=holdout)
    report = {"trained_at_utc": now(), **POLICY, "clinical_diagnosis": False, "source_counts": counts,
              "training_script_sha256": sha256(Path(__file__)), "legacy_script_sha256": sha256(LEGACY_SCRIPT),
              "original40_comparison": {key: original[key] for key in ("file_count", "fixed_baseline_metrics", "nested_spectral_metrics")},
              "expanded_development": {key: expanded[key] for key in ("file_count", "fixed_baseline_metrics", "nested_spectral_metrics")},
              "final_reserved_holdout": final, "final_candidate": candidate,
              "final_training_files": len(dev), "final_training_groups": len(set(groups[dev])),
              "final_training_target_counts": dict(Counter(CLASSES[labels[i]] for i in dev)),
              "final_training_source_counts": dict(Counter(rows[i]["source_id"] for i in dev)),
              "final_holdout_not_in_runtime_model": True,
              "environment": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                              "sklearn": sklearn.__version__, "platform": platform.platform(), "device": "CPU", "numeric_threads": 1},
              "elapsed_seconds": round(time.monotonic() - start, 3),
              "limitations": ["Animal/session mappings unknown; filename family grouping is unverified",
                  "Author test folder locally repartitioned; does not reproduce author experiment",
                  "Source clip durations differ and can confound event statistics; classifier excludes explicit duration",
                  "Whole-clip evaluation is not a validation of 1-second streaming boundaries or barn false alarms",
                  "ab class excluded because semantics unknown; no healthy or disease mapping",
                  "Holdout is fixed; no confidence interval or statistical significance claimed with unknown source units",
                  "Final runtime model fits development data only; independent ESP32/INMP441 calibration remains absent"]}
    write_json(ARTIFACTS / "training_report.json", report)
    write_json(ARTIFACTS / "unit_checks.json", checks)
    return report


def assert_model_parameters(saved, expected):
    for field in ("model_type", "training_file_ids", "training_raw_sha256"):
        if saved[field] != expected[field]:
            raise ValueError(f"Saved model {field} differs from deterministic refit")
    fields = ["scaler_mean", "scaler_scale", "intercept"]
    fields += ["coefficients"] if saved["model_type"] == "standardized_binary_logistic_regression" else ["support_vectors", "dual_coefficients", "gamma"]
    for field in fields:
        np.testing.assert_allclose(saved[field], expected[field], atol=1e-12, rtol=1e-12, err_msg=f"Saved {field} changed")


def checksums():
    path = ARTIFACTS / "SHA256SUMS.txt"
    files = {Path(__file__).resolve(), LEGACY_SCRIPT, TESTS, REPORT}
    for directory in (DATA, ARTIFACTS):
        files.update(item for item in directory.rglob("*") if item.is_file() and item != path and "__pycache__" not in item.parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{sha256(item)}  {relative(item)}\n" for item in sorted(files, key=relative)), encoding="utf-8")
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        expected, name = line.split("  ", 1)
        item = (ROOT / name).resolve()
        if not item.is_relative_to(ROOT) or sha256(item) != expected:
            raise ValueError(f"Output checksum mismatch: {name}")
        count += 1
    return {"passed": True, "checksum_entries_verified": count, "checksum_path": str(path)}


def verify():
    """Rebuild source features, all nested choices and numeric models; do not change model selection."""
    from threadpoolctl import threadpool_limits

    report = read_json(ARTIFACTS / "training_report.json")
    if report["training_script_sha256"] != sha256(Path(__file__)) or report["legacy_script_sha256"] != sha256(LEGACY_SCRIPT):
        raise ValueError("Training code changed since fit; rerun the same frozen train command before verification")
    tests = self_test()
    if not tests["passed"]:
        raise ValueError(tests["details"])
    saved_rows = read_jsonl(ARTIFACTS / "input_manifest.jsonl")
    rows, x, old_x, labels, groups, provenance, counts = audit_data()
    if rows != saved_rows or provenance != read_json(ARTIFACTS / "provenance.json")["files"]:
        raise ValueError("Rebuilt source manifest or source hashes differ")
    if counts != report["source_counts"] or read_json(ARTIFACTS / "feature_definition.json") != FEATURE_DEFINITION:
        raise ValueError("Source counts or executable feature definition changed")
    protocol = read_json(ARTIFACTS / "protocol.json")
    if protocol["script_sha256"] != sha256(Path(__file__)) or protocol["input_manifest_sha256"] != sha256(DATA / "included_manifest.jsonl"):
        raise ValueError("Frozen protocol no longer matches code/manifest")
    plan = make_split_plan(rows, labels, groups)
    if plan != read_json(ARTIFACTS / "split_plan.json") or protocol["split_plan"] != plan:
        raise ValueError("Reserved holdout or development membership changed")
    dev, holdout = np.array(plan["development_indices"]), np.array(plan["final_holdout_indices"])
    with np.load(ARTIFACTS / "features.npz", allow_pickle=False) as saved:
        for key, actual in (("X", x), ("X_baseline", old_x), ("y", labels), ("groups", groups),
                            ("file_ids", np.array([r["file_unit_id"] for r in rows])),
                            ("raw_sha256", np.array([r["raw_sha256"] for r in rows])),
                            ("development_indices", dev), ("final_holdout_indices", holdout)):
            np.testing.assert_array_equal(saved[key], actual)
    with np.load(legacy.ARTIFACTS / "features.npz", allow_pickle=False) as old:
        np.testing.assert_array_equal(old_x[:40], old["X"])
        legacy_oof = old["oof_cough_score"].copy()
    zip_checks = 0
    integrity = read_json(DATA / "figshare-complete-integrity.json")
    for field in ("outer", "nested"):
        path = ROOT / integrity[field]["path"]
        if sha256(path) != integrity[field]["sha256"] or path.stat().st_size != integrity[field]["bytes"]:
            raise ValueError("Source ZIP hash/length mismatch")
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError("Source ZIP CRC failed")
    with zipfile.ZipFile(ROOT / integrity["nested"]["path"]) as archive:
        extracted = DATA / "raw/figshare-31979640/unpacked/dataset"
        for member in archive.infolist():
            if member.is_dir() or not member.filename.lower().endswith(".wav"):
                continue
            digest = hashlib.sha256()
            with archive.open(member) as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(block)
            if digest.hexdigest() != sha256(extracted / member.filename):
                raise ValueError("Extracted WAV does not match the CRC-verified source archive")
            zip_checks += 1
    parity, models_checked, choices_checked, predictions_checked = [], 0, 0, 0
    original_ids = np.array([row["file_unit_id"] for row in rows[:40]])
    with threadpool_limits(limits=1):
        for name in ("original40_comparison", "expanded_development"):
            saved_report = read_json(ARTIFACTS / f"{name}_report.json")
            all_predictions, old_oof, new_oof = [], {}, {}
            group_values = original_ids if name == "original40_comparison" else groups
            expected_original = legacy.build_folds(labels[:40], original_ids) if name == "original40_comparison" else None
            for number, fold in enumerate(saved_report["folds"], 1):
                train, test = np.array(fold["train_indices"]), np.array(fold["test_indices"])
                if name == "original40_comparison":
                    if train.tolist() != expected_original[number-1][0].tolist() or test.tolist() != expected_original[number-1][1].tolist():
                        raise ValueError("Legacy comparison folds changed")
                else:
                    expected_fold = plan["development_outer_folds"][number-1]
                    if fold["train_indices"] != expected_fold["train_indices"] or fold["test_indices"] != expected_fold["test_indices"]:
                        raise ValueError("Development folds differ from the prefit protocol")
                    if set(train) & set(holdout) or set(test) & set(holdout):
                        raise ValueError("Final holdout used in development")
                if set(group_values[train]) & set(group_values[test]):
                    raise ValueError("Outer grouping leakage")
                for field in ("file_unit_id", "raw_sha256", "pcm_sha256"):
                    if {rows[i][field] for i in train} & {rows[i][field] for i in test}:
                        raise ValueError(f"Outer {field} leakage")
                candidate, inner = select_nested(x[train], labels[train], group_values[train], seed=SEED + number)
                for inner_fold in inner["folds"]:
                    inner_fold["train_global_indices"] = train[inner_fold["train_indices"]].tolist()
                    inner_fold["test_global_indices"] = train[inner_fold["test_indices"]].tolist()
                    if name != "original40_comparison" and (set(inner_fold["train_global_indices"]) | set(inner_fold["test_global_indices"])) & set(holdout):
                        raise ValueError("Final holdout used in inner selection")
                if candidate != fold["candidate"] or inner != fold["inner_selection"]:
                    raise ValueError("Nested candidate choice/audit did not reproduce")
                fitted = new_pipeline(candidate).fit(x[train], labels[train])
                baseline = legacy.new_pipeline().fit(old_x[train], labels[train])
                model, old_model = read_json(ROOT / fold["model_path"]), read_json(ROOT / fold["baseline_model_path"])
                assert_model_parameters(model, export_model(fitted, rows, train, candidate))
                assert_model_parameters(old_model, export_baseline(baseline, rows, train))
                score, old_score = portable_probability(model, x[test]), portable_probability(old_model, old_x[test])
                parity += [float(np.max(np.abs(score - decision_score(fitted, x[test])))),
                           float(np.max(np.abs(old_score - baseline.predict_proba(old_x[test])[:, 1])))]
                if legacy.metrics_for(labels[test], score) != fold["nested_spectral_metrics"] or legacy.metrics_for(labels[test], old_score) != fold["fixed_baseline_metrics"]:
                    raise ValueError("Outer fold metrics changed")
                for i, a, b in zip(test, old_score, score, strict=True):
                    old_oof[int(i)], new_oof[int(i)] = float(a), float(b)
                all_predictions += predictions(rows, test, old_score, number, "fixed_baseline")
                all_predictions += predictions(rows, test, score, number, "nested_spectral")
                models_checked += 2
                choices_checked += 1
            actual = sorted(all_predictions, key=lambda p: (p["row_index"], p["model"]))
            if actual != read_jsonl(ARTIFACTS / f"{name}_oof_predictions.jsonl"):
                raise ValueError("Saved OOF prediction records changed")
            indices = np.array(sorted(old_oof))
            for model_name, score_values in (("fixed_baseline", old_oof), ("nested_spectral", new_oof)):
                scores = np.array([score_values[int(i)] for i in indices])
                if legacy.metrics_for(labels[indices], scores) != saved_report[f"{model_name}_metrics"]:
                    raise ValueError("Aggregate OOF metrics changed")
            if name == "original40_comparison":
                np.testing.assert_array_equal(np.array([old_oof[i] for i in range(40)]), legacy_oof)
            predictions_checked += len(actual)
        candidate, inner = select_nested(x[dev], labels[dev], groups[dev], seed=SEED)
        for fold in inner["folds"]:
            fold["train_global_indices"] = dev[fold["train_indices"]].tolist()
            fold["test_global_indices"] = dev[fold["test_indices"]].tolist()
        if inner != read_json(ARTIFACTS / "final_development_selection.json") or candidate != report["final_candidate"]:
            raise ValueError("Final development-only candidate choice changed")
        fitted = new_pipeline(candidate).fit(x[dev], labels[dev])
        baseline = legacy.new_pipeline().fit(old_x[dev], labels[dev])
        model, old_model = load_model(ARTIFACTS / "model.json"), read_json(ARTIFACTS / "baseline_model.json")
        assert_model_parameters(model, export_model(fitted, rows, dev, candidate))
        assert_model_parameters(old_model, export_baseline(baseline, rows, dev))
        if set(model["training_file_ids"]) & {rows[i]["file_unit_id"] for i in holdout}:
            raise ValueError("Runtime model includes the final holdout")
        score, old_score = portable_probability(model, x[holdout]), portable_probability(old_model, old_x[holdout])
        parity += [float(np.max(np.abs(score - decision_score(fitted, x[holdout])))),
                   float(np.max(np.abs(old_score - baseline.predict_proba(old_x[holdout])[:, 1])))]
        expected = predictions(rows, holdout, score, "final_reserved_holdout", "nested_spectral")
        expected += predictions(rows, holdout, old_score, "final_reserved_holdout", "fixed_baseline")
        if expected != read_jsonl(ARTIFACTS / "final_holdout_predictions.jsonl"):
            raise ValueError("Final held-out predictions changed")
        final = read_json(ARTIFACTS / "final_holdout_report.json")
        if legacy.metrics_for(labels[holdout], score) != final["nested_spectral_metrics"] or legacy.metrics_for(labels[holdout], old_score) != final["fixed_baseline_metrics"]:
            raise ValueError("Final held-out metrics changed")
        unseal = read_json(ARTIFACTS / "holdout_unseal_record.json")
        for field, filename in (("model_sha256", "model.json"), ("baseline_model_sha256", "baseline_model.json"),
                                ("development_selection_sha256", "final_development_selection.json"), ("split_plan_sha256", "split_plan.json")):
            if unseal[field] != sha256(ARTIFACTS / filename):
                raise ValueError("Pre-holdout frozen artifact hash changed")
    if max(parity) > 1e-12:
        raise ValueError("Portable inference diverges from sklearn")
    independent = {}
    for model_name in ("fixed_baseline", "nested_spectral"):
        subset = [row for row in expected if row["model"] == model_name]
        matrix = [[0, 0], [0, 0]]
        for row in subset:
            matrix[row["target"]][CLASSES.index(row["predicted_event"])]+=1
        tn, fp, fn, tp = matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1]
        manual_accuracy = (tn + tp) / len(subset)
        manual_macro_f1 = (2 * tn / (2 * tn + fp + fn) + 2 * tp / (2 * tp + fp + fn)) / 2
        np.testing.assert_allclose([manual_accuracy, manual_macro_f1],
                                   [final[f"{model_name}_metrics"]["accuracy"], final[f"{model_name}_metrics"]["macro_f1"]], atol=1e-15, rtol=0)
        independent[model_name] = {"confusion_matrix": matrix, "accuracy": manual_accuracy, "macro_f1": manual_macro_f1}
    fixture = legacy.SOURCE / "derived/rdg-FP5LA9-8khz-2s/cough_001.wav"
    known, unknown = predict(fixture, valid_input_samples=8000), predict(fixture)
    if [w["quality"]["observed_samples"] for w in known["windows"]] != [8000, 0] or unknown["windows"][1]["status"] != "abstain_silence":
        raise ValueError("Runtime coverage/padding changed")
    write_json(ARTIFACTS / "examples/known_padding.json", known)
    write_json(ARTIFACTS / "examples/unknown_coverage.json", unknown)
    native, source_rate, _ = legacy.decode_wav(str(ROOT / rows[0]["path"]))
    quantized = np.clip(np.rint(128 + legacy.resample_audio(native, source_rate) * 128), 0, 255).astype(np.uint8)
    quantized_path = ARTIFACTS / "examples/cough001_unsigned8_format_fixture.wav"
    scipy.io.wavfile.write(quantized_path, RATE, quantized)
    quantized_result = predict(quantized_path)
    write_json(ARTIFACTS / "examples/unsigned8_format_fixture.json", {**quantized_result,
        "fixture_only": True, "derived_from_original": rows[0]["path"], "new_recording": False,
        "note": "Runtime format check only; not independent field audio or an 8-bit calibration result"})
    result = {"verified_at_utc": now(), "passed": True, **POLICY,
              "included_original_wav_hashes_verified": len(rows), "excluded_original_wav_hashes_verified": counts["excluded_additional_files"],
              "original_inrae_repository_md5_verified": 40, "figshare_extracted_wavs_match_crc_checked_archive": zip_checks,
              "complete_archives_crc_revalidated": 2, "feature_rows_regenerated_exactly": len(rows),
              "legacy_40_feature_rows_and_oof_scores_unchanged": True,
              "saved_models_refit_and_checked": models_checked + 2, "nested_choices_reproduced": choices_checked + 1,
              "saved_prediction_records_reproduced": predictions_checked + len(expected),
              "train_only_scalers_refit_checked": models_checked + 2,
              "final_holdout_train_group_overlap": 0, "final_holdout_train_raw_sha256_overlap": 0,
              "final_holdout_animal_independence_established": False,
              "portable_sklearn_max_absolute_error": max(parity), "behavior_tests_passed": tests["tests_run"],
              "independently_counted_final_holdout_metrics": independent,
              "runtime_two_second_declared_observed_samples": [8000, 0], "unsigned8_runtime_format_check": True,
              "runtime_model_bytes": (ARTIFACTS / "model.json").stat().st_size}
    write_json(ARTIFACTS / "unit_checks.json", tests)
    write_json(ARTIFACTS / "verification.json", result)
    checksum_result = checksums()
    return {**result, **checksum_result}


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "_fetch-worker":
        print(json.dumps(_fetch_public_inline(**json.load(sys.stdin)), ensure_ascii=True, allow_nan=False))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("acquire", help="Bounded official public dataset queries and downloads")
    commands.add_parser("resume-figshare", help="Bounded standard Range requests and full ZIP CRC validation")
    commands.add_parser("contract", help="Write and show the stable research prediction input/output contract")
    commands.add_parser("self-test", help="Behavioral signal, grouping, leakage and JSON parity tests")
    commands.add_parser("inspect-figshare", help="Full archive lengths, all CRCs, safe extraction and directory inventory")
    commands.add_parser("audit-data", help="Audit all source labels, hashes, original file counts and heuristic grouping")
    commands.add_parser("train", help="CPU nested paired comparisons, fixed final holdout and runtime JSON export")
    commands.add_parser("verify", help="Revalidate all hashes, ZIP CRCs, features, nested fits and held-out predictions")
    commands.add_parser("checksums", help="Refresh and validate scoped artifact/source checksums")
    prediction = commands.add_parser("predict", help="Per-window research acoustic-event JSON for one WAV")
    prediction.add_argument("wav", type=Path)
    prediction.add_argument("--model", type=Path, default=ARTIFACTS / "model.json")
    prediction.add_argument("--valid-input-samples", type=int)
    prediction.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "acquire":
        result = acquire()
    elif args.command == "resume-figshare":
        result = resume_figshare()
    elif args.command == "contract":
        result = input_contract()
    elif args.command == "self-test":
        result = self_test()
    elif args.command == "inspect-figshare":
        result = inspect_figshare()
    elif args.command == "audit-data":
        result = audit_data()[-1]
    elif args.command == "train":
        result = train()
    elif args.command == "verify":
        result = verify()
    elif args.command == "checksums":
        result = checksums()
    elif args.command == "predict":
        result = predict(args.wav, args.model, args.valid_input_samples)
        if args.output:
            write_json(args.output, result)
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
    return 1 if result.get("passed") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
