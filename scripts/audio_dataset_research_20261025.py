#!/usr/bin/env python3
"""Bounded public audio evidence collection and recording-group experiments.

All generated files stay under audio-training-data/external/20261025. This
script does not use credentials, contact the local backend, or export firmware.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import sys
import time
import wave
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "audio-training-data" / "external" / "20261025"
MAX_RESPONSE = 4 * 1024 * 1024
SENSITIVE = re.compile(r"token|secret|password|signature|credential|api.?key", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_url(url: str) -> str:
    parts = urlsplit(url)
    query = [(k, "REDACTED" if SENSITIVE.search(k) else v)
             for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    host = parts.hostname or ""
    if parts.port:
        host += f":{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, urlencode(query), ""))


def query(args) -> None:
    import requests

    if not re.fullmatch(r"[a-zA-Z0-9_.-]+", args.name):
        raise ValueError("use a simple evidence name")
    parts = urlsplit(args.url)
    if parts.scheme != "https" or parts.username or parts.password:
        raise ValueError("public HTTPS URLs without credentials only")
    if parts.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("local backend requests are out of scope")
    for key, _ in parse_qsl(parts.query):
        if SENSITIVE.search(key):
            raise ValueError("credential parameters are not allowed")
    directory = OUT / "evidence"
    directory.mkdir(parents=True, exist_ok=True)
    entry = {"name": args.name, "requestedAt": now(), "method": args.method,
             "url": safe_url(args.url), "maxBytes": args.max_bytes}
    start = time.monotonic()
    try:
        with requests.Session() as session:
            # Do not pick up ~/.netrc or cookies from an authenticated browser.
            session.trust_env = False
            headers = {"User-Agent": "CattleAudioDataEvidence/20261025 (public research)",
                       "Accept": "application/json,text/html,application/xml,*/*"}
            with session.request(args.method, args.url, headers=headers,
                                 json=json.loads(args.body) if args.body else None,
                                 timeout=(12, 35), stream=True) as response:
                entry.update(status=response.status_code, finalUrl=safe_url(response.url),
                             contentType=response.headers.get("Content-Type", ""),
                             contentLength=response.headers.get("Content-Length"),
                             redirects=[{"status": r.status_code, "url": safe_url(r.url)}
                                        for r in response.history])
                content = bytearray()
                truncated = False
                for block in response.iter_content(65536):
                    if len(content) + len(block) > args.max_bytes:
                        content.extend(block[:args.max_bytes - len(content)])
                        truncated = True
                        break
                    content.extend(block)
                suffix = ".json" if "json" in entry["contentType"] else ".txt"
                target = directory / (args.name + suffix)
                target.write_bytes(content)
                entry.update(bytes=len(content), truncated=truncated,
                             responseFile=str(target.relative_to(OUT)), sha256=sha256(target))
                if args.method == "POST":
                    entry["publicRequestBody"] = json.loads(args.body)
    except requests.RequestException as error:
        entry["errorType"] = type(error).__name__
        # Exception strings may contain signed redirect URLs; do not log them.
    entry["elapsedSeconds"] = round(time.monotonic() - start, 3)
    with (directory / "http_checks.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(json.dumps(entry, ensure_ascii=False))


def checksums() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "SHA256SUMS.txt")
    lines = [f"{sha256(p)}  {p.relative_to(OUT).as_posix()}" for p in files]
    (OUT / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"checksummedFiles": len(files), "root": str(OUT)}))


def collect_dataverse() -> None:
    import numpy as np
    import requests
    from scipy.signal import resample_poly

    metadata_path = OUT / "evidence" / "dataverse-FP5LA9.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    version = metadata["data"]["latestVersion"]
    if version["license"]["name"] != "etalab 2.0":
        raise ValueError("review the changed license before downloading")
    selected = [f for f in version["files"]
                if re.fullmatch(r"(?:non_)?cough_\d{3}\.wav", f["dataFile"]["filename"])]
    if sum(f["dataFile"]["filesize"] for f in selected) > 5 * 1024 * 1024:
        raise ValueError("small annotated sample budget exceeded")
    raw = OUT / "raw" / "rdg-FP5LA9"
    derived = OUT / "derived" / "rdg-FP5LA9-8khz-2s"
    raw.mkdir(parents=True, exist_ok=True)
    derived.mkdir(parents=True, exist_ok=True)
    records, downloads = [], []
    session = requests.Session()
    session.trust_env = False
    for item in selected:
        f = item["dataFile"]
        if item.get("restricted") or f["filesize"] > 1024 * 1024:
            raise ValueError("unexpected restricted/large file")
        target = raw / f["filename"]
        url = f"https://entrepot.recherche.data.gouv.fr/api/access/datafile/{f['id']}"
        log = {"fileId": f["id"], "url": url, "checkedAt": now()}
        if not target.exists():
            with session.get(url, timeout=(12, 40), stream=True) as response:
                response.raise_for_status()
                content = bytearray()
                for block in response.iter_content(65536):
                    content.extend(block)
                    if len(content) > f["filesize"]:
                        raise ValueError("download exceeds the declared file size")
                if len(content) != f["filesize"]:
                    raise ValueError("download size mismatch")
                log.update(status=response.status_code, finalUrl=safe_url(response.url),
                           contentType=response.headers.get("Content-Type"))
                target.write_bytes(content)
        else:
            log["status"] = "existing_file_verified"
        content = target.read_bytes()
        actual_md5 = hashlib.md5(content).hexdigest()
        if actual_md5 != f["checksum"]["value"]:
            raise ValueError(f"repository MD5 mismatch: {target.name}")
        with wave.open(str(target), "rb") as source:
            channels, width, rate, frames = (source.getnchannels(), source.getsampwidth(),
                                            source.getframerate(), source.getnframes())
            if width != 2:
                raise ValueError("review non-16bit input before conversion")
            pcm = np.frombuffer(source.readframes(frames), dtype="<i2").reshape(-1, channels)
            mono = pcm.astype(np.float64).mean(axis=1) / 32768.0
        converted = resample_poly(mono, 8000, rate)
        count = len(converted)
        converted = np.pad(converted[:16000], (0, max(0, 16000 - count)))
        normalized = derived / target.name
        with wave.open(str(normalized), "wb") as writer:
            writer.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
            writer.writeframes(np.rint(np.clip(converted, -1.0, 32767 / 32768) * 32768)
                               .astype("<i2").tobytes())
        event = "non_cough" if target.name.startswith("non_") else "cough"
        record = {
            "schemaVersion": 1, "sourceId": "rdg-FP5LA9-v1.0",
            "sourceDoi": "10.57745/FP5LA9", "fileDoi": f.get("persistentId"),
            "sourcePage": "https://doi.org/10.57745/FP5LA9", "downloadUrl": url,
            "path": str(target.relative_to(OUT)).replace("\\", "/"),
            "rawSha256": sha256(target), "repositoryMd5": actual_md5,
            "rawBytes": len(content), "originalLabel": event,
            "label": f"calf_{event}_event_author_reported",
            "labelProvenance": "depositor_filename_directory_and_description",
            "labelDescription": item.get("description"),
            "species": "calf_as_reported_by_depositor",
            "license": "etalab-2.0", "licenseUrl": version["license"]["uri"],
            "groupId": "rdg-FP5LA9:recording-session-unknown",
            "fileUnitId": f"rdg-FP5LA9:file-{f['id']}",
            "groupingEvidence": "Original parent recording, animal, pen and session of each clip were not supplied; all clips conservatively kept in one group.",
            "animalId": None, "recordingSessionId": None, "veterinarian": None,
            "clinicalEvidenceReference": None,
            "clinicalVerified": False, "allowForDiseaseLabels": False,
            "split": "unassigned_source_review",
            "quality": {"sampleRate": rate, "channels": channels, "bitDepth": width * 8,
                        "frameCount": frames, "durationSeconds": frames / rate,
                        "peak": float(np.abs(mono).max()),
                        "rms": float(np.sqrt(np.mean(mono ** 2))),
                        "saturationRatio": float(np.mean(np.abs(pcm) >= 32760))},
            "derived": {"path": str(normalized.relative_to(OUT)).replace("\\", "/"),
                        "sha256": sha256(normalized), "sampleRate": 8000,
                        "channels": 1, "bitDepth": 16, "windowSamples": 16000,
                        "windowSeconds": 2, "unpaddedSamples": min(count, 16000),
                        "paddedSamples": max(0, 16000 - count),
                        "resampler": "scipy.signal.resample_poly (anti-aliasing)"},
            "publicationDoi": "10.1016/j.animal.2026.101928",
            "supportingPreprintDoi": "10.64898/2026.01.20.700576",
            "trainingStatus": "research_event_examples_only_clinical_and_group_lineage_missing",
        }
        records.append(record)
        log.update(bytes=len(content), md5Verified=True, rawSha256=record["rawSha256"])
        downloads.append(log)
        print(json.dumps({"downloaded": target.name, "bytes": len(content), "rate": rate,
                          "durationSeconds": frames / rate, "md5Verified": True}), flush=True)
    session.close()
    (OUT / "manifest.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records), encoding="utf-8")
    save_json(OUT / "evidence" / "rdg-download-checks.json", downloads)
    save_json(OUT / "evidence" / "rdg-source-summary.json", {
        "checkedAt": now(), "doi": "10.57745/FP5LA9", "version": "1.0",
        "license": version["license"], "metadataSha256": sha256(metadata_path),
        "repositoryFileCount": len(version["files"]), "downloadedAudioFiles": len(records),
        "rawBytes": sum(r["rawBytes"] for r in records),
        "labelCounts": dict(Counter(r["originalLabel"] for r in records)),
        "sampleRateCounts": dict(Counter(r["quality"]["sampleRate"] for r in records)),
        "clinicalVerifiedCount": 0, "knownOriginalRecordingGroups": 0,
        "skipped": [{"filename": f["dataFile"]["filename"],
                     "bytes": f["dataFile"]["filesize"],
                     "reason": "outside the small annotated-audio download scope"}
                    for f in version["files"] if f not in selected],
    })


def train_events() -> None:
    import numpy as np
    import scipy
    import sklearn
    from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
    from sklearn.model_selection import StratifiedGroupKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    started = now()
    experiment = OUT / "experiment"
    experiment.mkdir(parents=True, exist_ok=True)
    evidence = OUT / "evidence"
    upstream_response = json.loads((evidence / "esc50-metadata-api.json").read_text(encoding="utf-8"))
    csv_content = base64.b64decode(upstream_response["content"])
    (evidence / "esc50.csv").write_bytes(csv_content)
    readme_response = json.loads((evidence / "esc50-readme-api.json").read_text(encoding="utf-8"))
    readme = base64.b64decode(readme_response["content"])
    (evidence / "esc50-readme.md").write_bytes(readme)
    license_response = json.loads((evidence / "esc50-license-api.json").read_text(encoding="utf-8"))
    license_text = base64.b64decode(license_response["content"]).decode("utf-8")
    (evidence / "esc50-LICENSE.txt").write_text(license_text, encoding="utf-8")
    attribution = {}
    for line in license_text.splitlines():
        match = re.match(r"- \[([^]]+)\]:", line)
        if match:
            attribution[Path(match.group(1)).stem] = line
    upstream = {}
    for item in csv.DictReader(io.StringIO(csv_content.decode("utf-8"))):
        short = re.sub(r"-\d+\.wav$", ".wav", item["filename"])
        upstream[short] = item
    manifest = ROOT / "audio-training-data" / "prepared" / "kaggle-asc24-v2" / "manifest.jsonl"
    source_records = [json.loads(x) for x in manifest.read_text(encoding="utf-8").splitlines() if x.strip()]
    tools_path = ROOT / "\u786c\u4ef6\u4ee3\u7801" / "\u73b0\u6709\u786c\u4ef6\u6f14\u793a\u8282\u70b9" / "tools" / "train_audio_model.py"
    spec = importlib.util.spec_from_file_location("audio_training_readonly", tools_path)
    trainer = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = trainer
    spec.loader.exec_module(trainer)
    x_rows, row_records, file_records = [], [], []
    seen_hashes = {}
    group_folds = {}
    for item in source_records:
        original = Path(item["originalPath"]).name
        if original not in upstream:
            continue
        meta = upstream[original]
        if meta["category"] not in {"cow", "dog", "frog"}:
            raise ValueError("upstream category mismatch")
        label = "cow_vocalization" if meta["category"] == "cow" else "non_cattle_audio"
        if label != item["label"]:
            raise ValueError("local label disagrees with upstream category")
        group = f"esc50:freesound:{meta['src_file']}"
        fold = int(meta["fold"])
        if group in group_folds and group_folds[group] != fold:
            raise ValueError("upstream recording group crosses official folds")
        group_folds[group] = fold
        path = (manifest.parent / item["path"]).resolve()
        digest = sha256(path)
        if digest != item["normalizedSha256"]:
            raise ValueError("existing PCM hash mismatch")
        if digest in seen_hashes:
            raise ValueError("duplicate audio found in the strict experiment")
        seen_hashes[digest] = group
        samples, rate = trainer.read_wav(path)
        if rate != 8000:
            raise ValueError("strict experiment expects the existing 8 kHz normalized data")
        features = trainer.window_features(samples, rate, 2.0, 2.0, 3)
        file_record = {"path": str(path), "normalizedSha256": digest,
                       "sourceId": item["sourceId"], "sourcePage": item["sourcePage"],
                       "upstreamSourceId": "ESC-50", "upstreamFilename": meta["filename"],
                       "groupId": group, "groupProvenance": "official ESC-50 src_file (Freesound recording ID)",
                       "outerFold": fold, "label": label, "originalLabel": meta["category"],
                       "labelProvenance": "official ESC-50 category", "clinicalVerified": False,
                       "allowForDiseaseLabels": False, "upstreamEsc10": meta["esc10"],
                       "license": "CC-BY-3.0" if meta["esc10"] == "True" else "CC-BY-NC-3.0",
                       "upstreamAttribution": attribution.get(Path(original).stem),
                       "sampleRate": rate, "windowSeconds": 2.0, "windows": len(features)}
        file_records.append(file_record)
        for index, feature in enumerate(features):
            x_rows.append(feature)
            row_records.append({**file_record, "windowIndex": index})
    if len(file_records) != 120:
        raise ValueError(f"expected 120 traceable sound-event files, got {len(file_records)}")
    (experiment / "input-manifest.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in file_records), encoding="utf-8")
    classes = ["cow_vocalization", "non_cattle_audio"]
    x = np.asarray(x_rows)
    y = np.asarray([classes.index(r["label"]) for r in row_records])
    groups = np.asarray([r["groupId"] for r in row_records])
    folds = np.asarray([r["outerFold"] for r in row_records])
    np.savez_compressed(experiment / "features.npz", features=x, labels=y,
                        groups=groups, folds=folds)

    def metric(true, predicted):
        return {"accuracy": float(accuracy_score(true, predicted)),
                "macroF1": float(f1_score(true, predicted, labels=[0, 1], average="macro", zero_division=0)),
                "confusionMatrix": confusion_matrix(true, predicted, labels=[0, 1]).tolist(),
                "classMetrics": classification_report(true, predicted, labels=[0, 1],
                                                       target_names=classes, output_dict=True, zero_division=0)}

    def grouped_scores(indices, values):
        pool = defaultdict(list)
        for index, value in zip(indices, values, strict=True):
            pool[groups[index]].append((int(y[index]), float(value)))
        result = []
        for group, rows in sorted(pool.items()):
            if len({row[0] for row in rows}) != 1:
                raise ValueError("one source recording has inconsistent class labels")
            score = float(np.mean([row[1] for row in rows]))
            result.append({"groupId": group, "truth": rows[0][0], "score": score,
                           "predicted": int(score >= 0), "windowCount": len(rows)})
        return result

    def group_metric(rows):
        return metric([r["truth"] for r in rows], [r["predicted"] for r in rows])

    def fit_svc(indices, c, gamma):
        model = make_pipeline(StandardScaler(), SVC(C=c, gamma=gamma, kernel="rbf", class_weight="balanced"))
        group_counts = Counter(groups[indices])
        weight = np.asarray([1.0 / group_counts[g] for g in groups[indices]])
        weight *= len(weight) / weight.sum()
        model.fit(x[indices], y[indices], svc__sample_weight=weight)
        return model

    grid = [(c, gamma) for c in (0.1, 1.0, 10.0, 100.0) for gamma in (0.01, 0.1, 1.0, "scale")]
    outer_reports, baseline_groups, improved_groups, predictions = [], [], [], []
    baseline_window = np.full(len(y), -1, dtype=int)
    improved_window = np.full(len(y), -1, dtype=int)
    for outer_fold in range(1, 6):
        train = np.flatnonzero(folds != outer_fold)
        test = np.flatnonzero(folds == outer_fold)
        if set(groups[train]) & set(groups[test]):
            raise ValueError("outer fold source-recording leakage")
        inner = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=20261025)
        inner_splits = list(inner.split(x[train], y[train], groups[train]))
        candidates = []
        for c, gamma in grid:
            scores = []
            for fit_indices, valid_indices in inner_splits:
                fit_indices, valid_indices = train[fit_indices], train[valid_indices]
                if set(groups[fit_indices]) & set(groups[valid_indices]):
                    raise ValueError("inner fold source-recording leakage")
                candidate = fit_svc(fit_indices, c, gamma)
                result = grouped_scores(valid_indices, candidate.decision_function(x[valid_indices]))
                scores.append(group_metric(result)["macroF1"])
            candidates.append({"C": c, "gamma": gamma, "innerGroupMacroF1": float(np.mean(scores)),
                               "innerFoldScores": scores})
        # Deterministic tie breaking preserves the first (smaller C) candidate.
        chosen = max(candidates, key=lambda row: row["innerGroupMacroF1"])
        model = fit_svc(train, chosen["C"], chosen["gamma"])
        scores = model.decision_function(x[test])
        improved_result = grouped_scores(test, scores)
        weights, bias, mean, scale = trainer.train_softmax(x, y, train, 1200, 0.06, 0.001)
        probabilities = trainer.prediction_probabilities(x, test, weights, bias, mean, scale)
        baseline_scores = probabilities[:, 1] - 0.5
        baseline_result = grouped_scores(test, baseline_scores)
        baseline_groups.extend({**r, "outerFold": outer_fold} for r in baseline_result)
        improved_groups.extend({**r, "outerFold": outer_fold} for r in improved_result)
        baseline_window[test] = (baseline_scores >= 0).astype(int)
        improved_window[test] = (scores >= 0).astype(int)
        outer_reports.append({"outerFold": outer_fold, "trainingGroups": len(set(groups[train])),
                              "validationGroups": len(set(groups[test])), "groupOverlap": 0,
                              "selected": chosen, "candidates": candidates,
                              "baselineGroupMetrics": group_metric(baseline_result),
                              "improvedGroupMetrics": group_metric(improved_result),
                              "supportVectors": int(model.named_steps["svc"].support_vectors_.shape[0])})
        svc = model.named_steps["svc"]
        scaler = model.named_steps["standardscaler"]
        np.savez_compressed(experiment / f"svc-fold-{outer_fold}.npz", mean=scaler.mean_,
                            scale=scaler.scale_, supportVectors=svc.support_vectors_,
                            dualCoefficients=svc.dual_coef_, intercept=svc.intercept_, gamma=svc._gamma)
        print(json.dumps({"outerFoldComplete": outer_fold,
                          "baselineGroupMacroF1": outer_reports[-1]["baselineGroupMetrics"]["macroF1"],
                          "improvedGroupMacroF1": outer_reports[-1]["improvedGroupMetrics"]["macroF1"],
                          "selectedC": chosen["C"], "selectedGamma": chosen["gamma"]}), flush=True)
    if (baseline_window < 0).any() or (improved_window < 0).any():
        raise ValueError("incomplete out-of-fold validation")
    if len({r["groupId"] for r in improved_groups}) != len(improved_groups):
        raise ValueError("a group was evaluated more than once")
    for index, record in enumerate(row_records):
        predictions.append({"path": record["path"], "groupId": record["groupId"],
                            "outerFold": record["outerFold"], "windowIndex": record["windowIndex"],
                            "truth": classes[y[index]], "baseline": classes[baseline_window[index]],
                            "improved": classes[improved_window[index]]})
    save_json(experiment / "window-predictions.json", predictions)
    save_json(experiment / "group-predictions.json", {"baseline": baseline_groups, "improved": improved_groups})
    rng = np.random.default_rng(20261025)
    base_map = {r["groupId"]: r for r in baseline_groups}
    ordered = sorted(improved_groups, key=lambda r: r["groupId"])
    deltas = []
    for _ in range(2000):
        chosen_rows = [ordered[i] for i in rng.integers(0, len(ordered), len(ordered))]
        if len({r["truth"] for r in chosen_rows}) < 2:
            continue
        truth = [r["truth"] for r in chosen_rows]
        a = [r["predicted"] for r in chosen_rows]
        b = [base_map[r["groupId"]]["predicted"] for r in chosen_rows]
        deltas.append(float(f1_score(truth, a, average="macro", zero_division=0) -
                            f1_score(truth, b, average="macro", zero_division=0)))
    summary = {
        "startedAt": started, "completedAt": now(), "status": "completed",
        "scope": "NON-DISEASE sound events: cow vocalization versus dog/frog; no cough or disease model trained",
        "inputFiles": len(file_records), "excludedUnmappedFiles": len(source_records) - len(file_records),
        "inputWindows": len(y), "inputGroups": len(set(groups)),
        "filesByLabel": dict(Counter(r["label"] for r in file_records)),
        "upstreamLicenseCounts": dict(Counter(r["license"] for r in file_records)),
        "groupsByLabel": {label: len({r["groupId"] for r in file_records if r["label"] == label}) for label in classes},
        "featureRateHz": 8000, "windowSeconds": 2, "windowSamples": 16000,
        "featureCount": int(x.shape[1]), "featureExtractor": str(tools_path),
        "featureExtractorSha256": sha256(tools_path), "inputManifestSha256": sha256(manifest),
        "sourceGrouping": "official ESC-50 src_file; official five folds; inner three-fold StratifiedGroupKFold",
        "validation": "nested 5 x 3 group CV; each original recording evaluated once; parameters selected using inner training folds only",
        "groupOverlap": 0, "fixedDecisionThresholds": {"baselineProbability": 0.5, "svcDecision": 0.0},
        "baseline": {"method": "existing ten-feature softmax, 1200 epochs, lr=0.06, l2=0.001; no validation-calibrated rejection",
                     "groupMetrics": group_metric(baseline_groups), "windowMetrics": metric(y, baseline_window)},
        "improved": {"method": "standardized ten-feature RBF SVC; balanced classes and equal total training weight per recording; nested parameter selection",
                     "groupMetrics": group_metric(improved_groups), "windowMetrics": metric(y, improved_window)},
        "pairedRecordingBootstrapMacroF1Delta95Percent": np.quantile(deltas, [0.025, 0.975]).tolist(),
        "bootstrapLimitation": "Conditional on this small dataset and fitted folds; does not estimate new-farm performance",
        "folds": outer_reports, "clinicalVerifiedFiles": 0, "firmwareExported": False,
        "deploymentApproved": False, "versions": {"python": sys.version.split()[0], "numpy": np.__version__,
                                                     "scipy": scipy.__version__, "sklearn": sklearn.__version__},
        "limitations": ["Only original sound recording groups are known, not animals or farms.",
                        "No farm noise, normal-breathing, bovine cough or disease labels in this experiment.",
                        "Kaggle CC0 claim does not override upstream ESC-50 non-commercial license; commercial clearance unverified.",
                        "New calf cough clips were excluded because their original recording groups and clip-level clinical lineage are unavailable.",
                        "RBF SVC is an offline experiment and is not implemented in the current firmware."]}
    save_json(experiment / "training-report.json", summary)
    print(json.dumps({"status": summary["status"], "files": len(file_records), "groups": len(set(groups)),
                      "baseline": summary["baseline"]["groupMetrics"],
                      "improved": summary["improved"]["groupMetrics"],
                      "delta95Percent": summary["pairedRecordingBootstrapMacroF1Delta95Percent"]}, ensure_ascii=False), flush=True)


def audit() -> None:
    import numpy as np
    from bs4 import BeautifulSoup
    from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

    evidence = OUT / "evidence"
    records = [json.loads(line) for line in (OUT / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) == 40
    assert len({r["rawSha256"] for r in records}) == 40
    assert {r["groupId"] for r in records} == {"rdg-FP5LA9:recording-session-unknown"}
    above4k, durations = [], []
    for record in records:
        raw, derived = OUT / record["path"], OUT / record["derived"]["path"]
        assert sha256(raw) == record["rawSha256"]
        assert hashlib.md5(raw.read_bytes()).hexdigest() == record["repositoryMd5"]
        assert sha256(derived) == record["derived"]["sha256"]
        assert record["clinicalVerified"] is False and record["allowForDiseaseLabels"] is False
        assert all(record[k] is None for k in ["animalId", "recordingSessionId", "veterinarian", "clinicalEvidenceReference"])
        with wave.open(str(raw), "rb") as reader:
            assert reader.getnchannels() == 1 and reader.getsampwidth() == 2 and reader.getframerate() == 44100
            audio = np.frombuffer(reader.readframes(reader.getnframes()), dtype="<i2").astype(float) / 32768
            durations.append(len(audio) / 44100)
            spectrum = np.abs(np.fft.rfft(audio - audio.mean())) ** 2
            frequencies = np.fft.rfftfreq(len(audio), 1 / 44100)
            fraction = float(spectrum[frequencies > 4000].sum() / max(spectrum.sum(), 1e-20))
            above4k.append(fraction)
            record["quality"]["fullClipAbove4kHzSpectralEnergyFraction"] = fraction
        with wave.open(str(derived), "rb") as reader:
            assert (reader.getframerate(), reader.getnchannels(), reader.getsampwidth(), reader.getnframes()) == (8000, 1, 2, 16000)
        record["publicationDoi"] = "10.1016/j.animal.2026.101928"
        record["supportingPreprintDoi"] = "10.64898/2026.01.20.700576"
        record["trainingStatus"] = "research_event_examples_only_clinical_and_group_lineage_missing"
    (OUT / "manifest.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    summary_path = evidence / "rdg-source-summary.json"
    source_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    source_summary.update({"actualDurationSeconds": sum(durations),
                           "durationRangeSeconds": [min(durations), max(durations)],
                           "channels": 1, "bitDepth": 16,
                           "publicationDoi": "10.1016/j.animal.2026.101928",
                           "supportingPreprintDoi": "10.64898/2026.01.20.700576",
                           "above4kHzEnergyFractionMedian": float(np.median(above4k)),
                           "above4kHzEnergyFractionRange": [min(above4k), max(above4k)],
                           "licenseCaveat": "Repository states Etalab 2.0; preprint says research/educational purposes only. Resolve scope with the depositor before commercial use."})
    save_json(summary_path, source_summary)
    page = BeautifulSoup((evidence / "preprint-calf-acoustic.txt").read_text(encoding="utf-8"), "html.parser")
    excerpts = [p.get_text(" ", strip=True) for p in page.select("p")
                if any(term in p.get_text(" ", strip=True).lower()
                       for term in ["40 short", "1,045", "48 khz", "16 khz", "data repository", "research and educational"])]
    save_json(evidence / "paper-data-and-preprocessing-excerpts.json", {
        "url": "https://www.biorxiv.org/content/10.64898/2026.01.20.700576v1.full",
        "pageSha256": sha256(evidence / "preprint-calf-acoustic.txt"), "excerpts": excerpts})
    experiment = OUT / "experiment"
    report = json.loads((experiment / "training-report.json").read_text(encoding="utf-8"))
    inputs = [json.loads(line) for line in (experiment / "input-manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    for record in inputs:
        assert sha256(Path(record["path"])) == record["normalizedSha256"]
        assert record["upstreamAttribution"]
    with np.load(experiment / "features.npz", allow_pickle=False) as cache:
        x, y, folds, groups = (cache[k] for k in ["features", "labels", "folds", "groups"])
        assert x.shape == (240, 10) and np.isfinite(x).all()
        restored = np.full(len(y), -1, dtype=int)
        for fold in range(1, 6):
            test = np.flatnonzero(folds == fold)
            assert not set(groups[test]) & set(groups[folds != fold])
            with np.load(experiment / f"svc-fold-{fold}.npz", allow_pickle=False) as saved:
                normalized = (x[test] - saved["mean"]) / saved["scale"]
                distances = ((normalized[:, None, :] - saved["supportVectors"][None, :, :]) ** 2).sum(axis=2)
                scores = np.exp(-float(saved["gamma"]) * distances) @ saved["dualCoefficients"].ravel() + saved["intercept"].item()
                restored[test] = (scores >= 0).astype(int)
        saved_predictions = json.loads((experiment / "window-predictions.json").read_text(encoding="utf-8"))
        classes = ["cow_vocalization", "non_cattle_audio"]
        assert all(classes[pred] == row["improved"] for pred, row in zip(restored, saved_predictions, strict=True))
        assert accuracy_score(y, restored) == report["improved"]["windowMetrics"]["accuracy"]
    predictions = json.loads((experiment / "group-predictions.json").read_text(encoding="utf-8"))
    for method in ["baseline", "improved"]:
        rows = predictions[method]
        assert len(rows) == len({r["groupId"] for r in rows}) == 86
        true, predicted = [r["truth"] for r in rows], [r["predicted"] for r in rows]
        metric = report[method]["groupMetrics"]
        assert accuracy_score(true, predicted) == metric["accuracy"]
        assert f1_score(true, predicted, average="macro") == metric["macroF1"]
        assert confusion_matrix(true, predicted).tolist() == metric["confusionMatrix"]
    save_json(OUT / "source-records.json", {
        "checkedAt": now(), "sources": [
            {"id": "rdg-FP5LA9-v1.0", "doi": "10.57745/FP5LA9", "status": "40 author-annotated calf event WAV files downloaded and MD5/SHA256 verified",
             "license": "etalab-2.0", "clinicalVerified": False, "allowForDiseaseLabels": False,
             "sampleCount": 40, "cough": 20, "nonCough": 20, "sampleRateHz": 44100,
             "groupId": "rdg-FP5LA9:recording-session-unknown", "evidence": "evidence/rdg-source-summary.json",
             "downloadLog": "evidence/rdg-download-checks.json", "manifest": "manifest.jsonl",
             "citation": "Mach et al. (2026), AI-powered acoustic surveillance for early detection of calf respiratory disease, Animal 20(10):101928, doi:10.1016/j.animal.2026.101928",
             "licenseCaveat": source_summary["licenseCaveat"]},
            {"id": "zenodo-17764250", "doi": "10.5281/zenodo.17764250", "status": "restricted; metadata HTTP 200; no downloadable public files returned",
             "license": "metadata cc-by-4.0 plus restricted non-commercial Data Access Agreement", "reportedClipCount": 569,
             "downloadedAudio": 0, "sampleRateHz": None, "evidence": "evidence/zenodo-17764250.json"},
            {"id": "figshare-31979640", "doi": "10.6084/m9.figshare.31979640", "status": "calf dataset DOI metadata HTTP 200; webpage and two file API routes HTTP 403",
             "license": "cc-by-4.0 (DOI metadata)", "declaredBytes": 133087841, "downloadedAudio": 0,
             "sampleCount": None, "sampleRateHz": None, "clinicalVerified": False,
             "evidence": "evidence/datacite-31979640.json"},
            {"id": "github-calf-cough-array", "url": "https://github.com/Goosefeatherr/calf-cough-array",
             "status": "HTTP 200; tree has no audio; repository has no declared license",
             "downloadedAudio": 0, "sampleCount": 0, "sampleRateHz": None, "evidence": "evidence/github-calf-cough-tree.json"},
            {"id": "ESC-50-existing-local-subset", "status": "120 existing local sound-event WAV files mapped to upstream recording IDs; non-disease training completed",
             "licenseCounts": report["upstreamLicenseCounts"], "originalRecordingGroups": 86,
             "evidence": "experiment/training-report.json", "manifest": "experiment/input-manifest.jsonl"}],
        "searchFailures": ["Hugging Face cattle search ConnectTimeout; do not interpret as no datasets existing",
                           "raw.githubusercontent.com connection failures; public GitHub contents API succeeded"],
        "searchScopeLimitation": "A bounded public search, not proof that no other bovine disease audio exists."})
    result = {"checkedAt": now(), "status": "passed", "downloadedRawFiles": 40,
              "md5Matches": 40, "rawSha256Matches": 40, "derivedSha256Matches": 40,
              "derived8000HzMono16bit16000FrameFiles": 40, "existingExperimentInputSha256Matches": len(inputs),
              "restoredSvcPredictionsMatch": len(saved_predictions), "groupMetricRecomputations": 2,
              "clinicalVerifiedFiles": 0, "firmwareExported": False}
    save_json(OUT / "verification.json", result)
    print(json.dumps(result), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("query")
    fetch.add_argument("--name", required=True)
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--method", choices=("GET", "POST"), default="GET")
    fetch.add_argument("--body")
    fetch.add_argument("--max-bytes", type=int, default=MAX_RESPONSE)
    sub.add_parser("checksums")
    sub.add_parser("collect-dataverse")
    sub.add_parser("train-events")
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.command == "query":
        query(args)
    elif args.command == "collect-dataverse":
        collect_dataverse()
    elif args.command == "train-events":
        train_events()
    elif args.command == "audit":
        audit()
    else:
        checksums()


if __name__ == "__main__":
    main()
