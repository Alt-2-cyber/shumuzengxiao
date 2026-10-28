#!/usr/bin/env python3
"""Train an auditable, animal-held-out temporal neck acceleration candidate.

CPU only. All new outputs stay in a dated candidate directory. This script
never invokes the legacy export entry point or writes production headers.
"""

from __future__ import annotations

import os

for _thread_variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                         "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[_thread_variable] = "4"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse
from collections import Counter
import contextlib
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

import numpy as np
import requests
from scipy.signal import resample_poly
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from threadpoolctl import threadpool_limits


ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "\u725b\u884c\u4e3a\u8bc6\u522b\u6570\u636e\u96c6"
DEFAULT_OUTPUT = DATA_ROOT / "esp32_motion_temporal_20261026"
SOURCE_API = "https://zenodo.org/api/records/5849025"
CLASSES = ("grazing", "standing_ruminating", "standing_resting", "moving")
SOURCE_LABELS = {"GRZ": 0, "RUS": 1, "RES": 2, "MOV": 3}
ASSIGNMENTS = {f"cow{i}": ("test" if i in (4, 5) else "train") for i in range(1, 7)}
SAMPLE_RATE = 20
NATIVE_RATE = 25
WINDOW = 80
HOP = 40
PURGE = 20
FILTER_RADIUS_NATIVE = 13
SEED = 20261026
FEATURE_NAMES = tuple(f"{axis}_{stat}" for axis in ("x", "y", "z", "norm")
                      for stat in ("mean", "std", "min", "max", "mean_abs_delta", "rms_delta"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def acquire_sources(output: Path) -> Path:
    sources = output / "sources"
    sources.mkdir(parents=True, exist_ok=True)
    snapshot = sources / "zenodo_5849025.json"
    if not snapshot.exists():
        response = requests.get(SOURCE_API, timeout=(15, 45))
        response.raise_for_status()
        write_json(snapshot, response.json())
        write_json(sources / "retrieval.json", {"url": SOURCE_API,
                   "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
    metadata = json.loads(snapshot.read_text(encoding="utf-8"))
    entry = next(f for f in metadata["files"] if f["key"] == "JapaneseBlackBeefData.zip")
    archive = sources / entry["key"]
    checksum = entry["checksum"].split(":", 1)[1]
    def valid_archive():
        if not archive.exists() or archive.stat().st_size != entry["size"]:
            return False
        with archive.open("rb") as handle:
            return hashlib.file_digest(handle, "md5").hexdigest() == checksum
    if not valid_archive():
        attempts = []
        log = sources / "download_attempts.json"
        if log.exists():
            attempts = json.loads(log.read_text(encoding="utf-8"))
        for attempt in range(12):
            current = archive.stat().st_size if archive.exists() else 0
            if current == entry["size"]:
                break
            if current > entry["size"]:
                raise RuntimeError("Candidate source is larger than its public manifest")
            end = min(current + 1024 * 1024 - 1, entry["size"] - 1)
            url = (entry["links"]["self"] if attempt % 2 == 0 else
                   f'https://zenodo.org/records/5849025/files/{entry["key"]}?download=1')
            state = {"url": url, "start": current, "end": end}
            print(f"Source download range {current}-{end}/{entry['size']}", flush=True)
            try:
                with requests.get(url, headers={"Range": f"bytes={current}-{end}"},
                                  stream=True, timeout=(15, 25)) as response:
                    response.raise_for_status()
                    state["status"] = response.status_code
                    content_range = response.headers.get("Content-Range", "")
                    state["content_range"] = content_range
                    if response.status_code == 206:
                        if not content_range.startswith(f"bytes {current}-"):
                            raise RuntimeError("Server range does not match requested offset")
                    elif current:
                        raise RuntimeError("Server ignored resume range; existing bytes preserved")
                    with archive.open("ab" if current else "wb") as handle:
                        for chunk in response.iter_content(64 * 1024):
                            handle.write(chunk)
                state["written_total"] = archive.stat().st_size
            except (requests.RequestException, RuntimeError) as error:
                state["error"] = str(error)
            attempts.append(state)
            write_json(log, attempts)
            if valid_archive():
                break
    if not valid_archive():
        raise RuntimeError("Public archive size/MD5 does not match Zenodo metadata")
    with zipfile.ZipFile(archive) as zipped:
        bad = zipped.testzip()
        if bad is not None:
            raise RuntimeError(f"Archive CRC failed: {bad}")
        inventory = [{"name": item.filename, "size": item.file_size, "crc32": item.CRC}
                     for item in zipped.infolist()]
        write_json(sources / "zip_inventory.json", inventory)
        for cow in range(1, 7):
            name = f"cow{cow}.csv"
            member = next(n for n in zipped.namelist() if Path(n).name.lower() == name)
            target = sources / name
            contents = zipped.read(member)
            if target.exists():
                if target.read_bytes() != contents:
                    raise RuntimeError(f"Extracted source changed: {name}")
            else:
                target.write_bytes(contents)
        readme_contents = zipped.read("ReadMe.md")
        readme_target = sources / "ReadMe.md"
        if readme_target.exists() and readme_target.read_bytes() != readme_contents:
            raise RuntimeError("Existing extracted public README changed")
        if not readme_target.exists():
            readme_target.write_bytes(readme_contents)
    write_json(sources / "integrity.json", {"archive_sha256": sha256(archive),
               "zenodo_md5": checksum, "zip_crc_passed": True,
               "readme_sha256": sha256(sources / "ReadMe.md"),
               "csv_sha256": {p.name: sha256(p) for p in sorted(sources.glob('cow*.csv'))}})
    return sources


@dataclass
class RawRecord:
    record_id: str
    animal: str
    session: str
    timestamps: np.ndarray
    xyz: np.ndarray
    labels: np.ndarray


@dataclass
class WindowRecord:
    record_id: str
    animal: str
    session: str
    split: str
    segment: int
    segment_start: int
    segment_stop: int
    raw_start: int
    raw_stop: int
    target_start: int
    label: int
    xyz: np.ndarray


def extract_features(xyz: np.ndarray) -> np.ndarray:
    xyz = np.asarray(xyz, dtype=np.float32)
    if xyz.shape != (WINDOW, 3) or not np.isfinite(xyz).all():
        raise ValueError("Expected 80 finite consecutive XYZ samples in g")
    values = xyz.astype(np.float64)
    norm = np.sqrt(np.sum(values * values, axis=1))
    channels = np.column_stack((values, norm))
    result = []
    for channel in channels.T:
        mean = np.mean(channel)
        delta = np.diff(channel)
        result.extend((mean, np.sqrt(np.mean((channel - mean) ** 2)),
                       np.min(channel), np.max(channel), np.mean(np.abs(delta)),
                       np.sqrt(np.mean(delta * delta))))
    return np.asarray(result, dtype=np.float32)


def floor_float32(value: float) -> np.float32:
    rounded = np.float32(value)
    if float(rounded) > value:
        rounded = np.nextafter(rounded, np.float32(-np.inf))
    return rounded


def make_windows(records: list[RawRecord], assignments: dict[str, str]) -> list[WindowRecord]:
    windows = []
    for record in records:
        if record.animal not in assignments:
            raise ValueError(f"No independent raw animal assignment for {record.animal}")
        n = len(record.labels)
        if record.xyz.shape != (n, 3) or len(record.timestamps) != n:
            raise ValueError("Inconsistent raw record arrays")
        finite = np.isfinite(record.xyz).all(axis=1) & np.isfinite(record.timestamps)
        valid = finite & np.isin(record.labels, list(SOURCE_LABELS))
        boundary = np.ones(n, dtype=bool)
        dt = np.diff(record.timestamps)
        boundary[1:] = ((record.labels[1:] != record.labels[:-1]) | ~finite[1:] | ~finite[:-1]
                        | (np.abs(dt - 1 / NATIVE_RATE) > 0.012))
        starts = np.flatnonzero(boundary)
        for segment, (start, stop) in enumerate(zip(starts, np.r_[starts[1:], n])):
            if not valid[start] or stop - start < (WINDOW + 2 * PURGE) * 5 / 4:
                continue
            # scipy's fixed Kaiser FIR has radius ceil(50 / 4)=13 native samples.
            sampled = resample_poly(record.xyz[start:stop].astype(np.float64), 4, 5,
                                    window=("kaiser", 5.0), padtype="constant").astype(np.float32)
            for target in range(PURGE, len(sampled) - PURGE - WINDOW + 1, HOP):
                raw_start = start + int(np.floor(target * 5 / 4)) - FILTER_RADIUS_NATIVE
                raw_stop = start + int(np.ceil((target + WINDOW - 1) * 5 / 4)) + FILTER_RADIUS_NATIVE + 1
                if raw_start < start or raw_stop > stop:
                    raise AssertionError("FIR support crosses segment boundary")
                windows.append(WindowRecord(record.record_id, record.animal, record.session,
                    assignments[record.animal], segment, int(start), int(stop), int(raw_start),
                    int(raw_stop), target, SOURCE_LABELS[str(record.labels[start])],
                    sampled[target:target + WINDOW].copy()))
    validate_windows(windows)
    return windows


def validate_windows(windows: list[WindowRecord]) -> None:
    roles = {}
    for window in windows:
        previous = roles.setdefault(window.animal, window.split)
        if previous != window.split:
            raise ValueError("Animal shared across raw splits")
        if window.raw_start < window.segment_start or window.raw_stop > window.segment_stop:
            raise ValueError("Window/FIR context crosses raw segment")
        if window.xyz.shape != (WINDOW, 3) or not np.isfinite(window.xyz).all():
            raise ValueError("Invalid window")


def model_to_json(forest: RandomForestClassifier) -> dict:
    if forest.classes_.tolist() != list(range(len(CLASSES))):
        raise ValueError("Forest must contain all four source-backed classes")
    nodes, leaves, roots = [], [], []
    for estimator in forest.estimators_:
        tree = estimator.tree_
        offset = len(nodes)
        roots.append(offset)
        for i in range(tree.node_count):
            if tree.children_left[i] < 0:
                value = tree.value[i, 0]
                probabilities = (value / value.sum()).astype(np.float32).tolist()
                nodes.append({"feature": -1, "threshold": 0.0, "left": 0, "right": 0,
                              "leaf": len(leaves)})
                leaves.append(probabilities)
            else:
                nodes.append({"feature": int(tree.feature[i]),
                              "threshold": float(floor_float32(tree.threshold[i])),
                              "left": offset + int(tree.children_left[i]),
                              "right": offset + int(tree.children_right[i]), "leaf": 0})
    if len(nodes) >= 65536 or len(leaves) >= 65536:
        raise ValueError("Candidate exceeds 16-bit portable node indices")
    return {"version": "motion-temporal-20261026-v1", "classes": list(CLASSES),
            "features": list(FEATURE_NAMES), "roots": roots, "nodes": nodes,
            "leaf_probabilities": leaves, "production_eligible": False,
            "clinical_lameness_enabled": False, "trained_animals":
            sorted(c for c, role in ASSIGNMENTS.items() if role == "train")}


def predict_json(model: dict, features: np.ndarray) -> np.ndarray:
    features = np.asarray(features, dtype=np.float32)
    nodes = model["nodes"]
    feature = np.array([n["feature"] for n in nodes], dtype=np.int16)
    thresholds = np.array([n["threshold"] for n in nodes], dtype=np.float32)
    left = np.array([n["left"] for n in nodes], dtype=np.int32)
    right = np.array([n["right"] for n in nodes], dtype=np.int32)
    leaf = np.array([n["leaf"] for n in nodes], dtype=np.int32)
    probabilities = np.array(model["leaf_probabilities"], dtype=np.float64)
    scores = np.zeros((len(features), len(CLASSES)), dtype=np.float64)
    for root in model["roots"]:
        index = np.full(len(features), root, dtype=np.int32)
        while True:
            active = np.flatnonzero(feature[index] >= 0)
            if not len(active):
                break
            current = index[active]
            index[active] = np.where(features[active, feature[current]] <= thresholds[current],
                                     left[current], right[current])
        scores += probabilities[leaf[index]]
    return scores / len(model["roots"])


FEATURE_HEADER = r'''/* Generated research candidate; neck XYZ only, calibrated g at 20 Hz. */
#ifndef MOTION_TEMPORAL_FEATURES_20261026_H
#define MOTION_TEMPORAL_FEATURES_20261026_H
#include <stddef.h>
#include <stdint.h>
#include <math.h>
#define MOTION_TEMPORAL_SAMPLE_RATE_HZ 20
#define MOTION_TEMPORAL_WINDOW_SAMPLES 80
#define MOTION_TEMPORAL_HOP_SAMPLES 40
#define MOTION_TEMPORAL_FEATURE_COUNT 24
#define MOTION_TEMPORAL_CLASS_COUNT 4
#define MOTION_TEMPORAL_UNKNOWN_LABEL 255
#define MOTION_TEMPORAL_PRODUCTION_ELIGIBLE 0
#define MOTION_TEMPORAL_CLINICAL_LAMENESS_ENABLED 0

/* Interleaved X,Y,Z float32 samples, channel-major feature output. */
static inline int motion_temporal_extract_features(const float *xyz, size_t samples, float *out) {
  size_t i;
  int channel;
  double values[MOTION_TEMPORAL_WINDOW_SAMPLES];
  if (!xyz || !out || samples != MOTION_TEMPORAL_WINDOW_SAMPLES) return 0;
  for (i = 0; i < samples * 3; ++i) if (!isfinite(xyz[i])) return 0;
  for (channel = 0; channel < 4; ++channel) {
    double sum = 0.0, variance = 0.0, abs_delta = 0.0, delta_energy = 0.0;
    double mean, minimum, maximum;
    for (i = 0; i < samples; ++i) {
      double x = xyz[i * 3], y = xyz[i * 3 + 1], z = xyz[i * 3 + 2];
      values[i] = channel < 3 ? (double)xyz[i * 3 + (size_t)channel] : sqrt(x*x + y*y + z*z);
      sum += values[i];
    }
    mean = sum / (double)samples;
    minimum = maximum = values[0];
    for (i = 0; i < samples; ++i) {
      double centered = values[i] - mean;
      variance += centered * centered;
      if (values[i] < minimum) minimum = values[i];
      if (values[i] > maximum) maximum = values[i];
      if (i) {
        double delta = values[i] - values[i-1];
        abs_delta += fabs(delta);
        delta_energy += delta * delta;
      }
    }
    out[channel*6] = (float)mean;
    out[channel*6+1] = (float)sqrt(variance / (double)samples);
    out[channel*6+2] = (float)minimum;
    out[channel*6+3] = (float)maximum;
    out[channel*6+4] = (float)(abs_delta / (double)(samples-1));
    out[channel*6+5] = (float)sqrt(delta_energy / (double)(samples-1));
  }
  return 1;
}
#endif
'''


def c_float(value: float) -> str:
    text = format(float(np.float32(value)), ".9g")
    if "." not in text and "e" not in text:
        text += ".0"
    return text + "f"


def export_headers(output: Path, model: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "motion_temporal_features.h").write_text(FEATURE_HEADER, encoding="ascii")
    lines = ["/* Generated CPU-trained research candidate. No clinical labels or three-position fusion. */",
             "#ifndef CATTLE_MOTION_TEMPORAL_CANDIDATE_20261026_H",
             "#define CATTLE_MOTION_TEMPORAL_CANDIDATE_20261026_H",
             '#include "motion_temporal_features.h"',
             '#define MOTION_TEMPORAL_MODEL_VERSION "motion-temporal-20261026-v1"',
             f'#define MOTION_TEMPORAL_TREE_COUNT {len(model["roots"])}',
             f'#define MOTION_TEMPORAL_NODE_COUNT {len(model["nodes"])}',
             "typedef struct { float threshold; uint16_t left, right, leaf; int8_t feature; } MotionTemporalNode;",
             "typedef struct { uint8_t label; float confidence; uint8_t rejected; float probabilities[4]; } MotionTemporalPrediction;",
             'static const char *const motion_temporal_class_names[4] = {' +
             ", ".join(json.dumps(c) for c in CLASSES) + "};",
             "static const uint16_t motion_temporal_roots[] = {" +
             ", ".join(str(r) for r in model["roots"]) + "};",
             "static const MotionTemporalNode motion_temporal_nodes[] = {"]
    lines += [f'  {{{c_float(n["threshold"])}, {n["left"]}, {n["right"]}, {n["leaf"]}, {n["feature"]}}},'
              for n in model["nodes"]]
    lines += ["};", "static const float motion_temporal_leaf_probabilities[][4] = {"]
    lines += ["  {" + ", ".join(c_float(p) for p in row) + "}," for row in model["leaf_probabilities"]]
    lines += ["};", r'''
static inline MotionTemporalPrediction motion_temporal_rejected(void) {
  MotionTemporalPrediction p = {MOTION_TEMPORAL_UNKNOWN_LABEL, 0.0f, 1, {0,0,0,0}};
  return p;
}
static inline MotionTemporalPrediction motion_temporal_predict_features(const float *features) {
  MotionTemporalPrediction p = motion_temporal_rejected();
  double scores[4] = {0,0,0,0};
  size_t tree;
  int i, best = 0;
  if (!features) return p;
  for (i = 0; i < 24; ++i) if (!isfinite(features[i])) return p;
  for (tree = 0; tree < MOTION_TEMPORAL_TREE_COUNT; ++tree) {
    uint16_t index = motion_temporal_roots[tree];
    while (motion_temporal_nodes[index].feature >= 0) {
      const MotionTemporalNode *node = &motion_temporal_nodes[index];
      index = features[(uint8_t)node->feature] <= node->threshold ? node->left : node->right;
    }
    for (i = 0; i < 4; ++i) scores[i] += motion_temporal_leaf_probabilities[motion_temporal_nodes[index].leaf][i];
  }
  for (i = 0; i < 4; ++i) {
    p.probabilities[i] = (float)(scores[i] / MOTION_TEMPORAL_TREE_COUNT);
    if (scores[i] > scores[best]) best = i;
  }
  p.label = (uint8_t)best;
  p.confidence = p.probabilities[best];
  p.rejected = 0;
  return p;
}
static inline MotionTemporalPrediction motion_temporal_predict_window(const float *xyz, size_t samples) {
  float features[24];
  if (!motion_temporal_extract_features(xyz, samples, features)) return motion_temporal_rejected();
  return motion_temporal_predict_features(features);
}
''', "#endif", ""]
    (output / "cattle_motion_temporal_candidate.h").write_text("\n".join(lines), encoding="ascii")


PARITY_RUNNER = r'''
#include <stdio.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "cattle_motion_temporal_candidate.h"
int main(void) {
  float xyz[80*3], result[31];
  int j;
  MotionTemporalPrediction bad;
#ifdef _WIN32
  _setmode(_fileno(stdin), _O_BINARY);
  _setmode(_fileno(stdout), _O_BINARY);
#endif
  if (motion_temporal_extract_features(NULL, 80, result)) return 10;
  if (motion_temporal_extract_features(xyz, 79, result)) return 11;
  bad = motion_temporal_predict_features(NULL);
  if (!bad.rejected || bad.label != 255) return 12;
  while (fread(xyz, sizeof(float), 240, stdin) == 240) {
    MotionTemporalPrediction p;
    if (!motion_temporal_extract_features(xyz, 80, result)) {
      p = motion_temporal_predict_window(xyz, 80);
      if (!p.rejected || p.label != 255) return 13;
      for (j=0; j<24; ++j) result[j] = 0;
    } else p = motion_temporal_predict_features(result);
    for (j=0; j<4; ++j) result[24+j] = p.probabilities[j];
    result[28] = (float)p.label;
    result[29] = (float)p.rejected;
    result[30] = p.confidence;
    if (fwrite(result, sizeof(float), 31, stdout) != 31) return 14;
  }
  return 0;
}
'''


def verify_portable(output: Path, model: dict, fixtures: np.ndarray,
                    reference_probabilities: np.ndarray | None = None) -> dict:
    runner = output / "parity_runner.c"
    runner.write_text(PARITY_RUNNER, encoding="ascii")
    fixtures = np.asarray(fixtures, dtype=np.float32)
    python_features = np.stack([extract_features(w) for w in fixtures])
    python_probabilities = predict_json(model, python_features)
    if reference_probabilities is None:
        reference_probabilities = python_probabilities
    reference_error = float(np.max(np.abs(python_probabilities - reference_probabilities)))
    reference_mismatches = int(np.sum(python_probabilities.argmax(1) != reference_probabilities.argmax(1)))
    nonfinite = np.zeros((2, WINDOW, 3), dtype=np.float32)
    nonfinite[0, 2, 0] = np.nan
    nonfinite[1, 7, 1] = np.inf
    payload = np.concatenate((fixtures, nonfinite)).astype("<f4").tobytes()
    reports = []
    for language, compiler, standard in (("c99", "gcc", "c99"), ("c++11", "g++", "c++11")):
        executable = output / f"parity_{language.replace('+', 'p')}.exe"
        compiler_path = shutil.which(compiler)
        if not compiler_path:
            raise RuntimeError(f"Missing compiler for real portable parity: {compiler}")
        cmd = [compiler_path, f"-std={standard}", "-O2", "-ffp-contract=off", "-Wall", "-Wextra",
               "-Werror", str(runner), "-o", str(executable), "-lm"]
        built = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if built.returncode:
            raise RuntimeError(f"{language} compile failed: {built.stderr}")
        start = time.perf_counter()
        ran = subprocess.run([str(executable)], input=payload, capture_output=True, timeout=60)
        elapsed = time.perf_counter() - start
        if ran.returncode:
            raise RuntimeError(f"{language} parity runner failed: {ran.returncode} {ran.stderr!r}")
        actual = np.frombuffer(ran.stdout, dtype="<f4").reshape(-1, 31)
        if len(actual) != len(fixtures) + 2:
            raise AssertionError("Portable runner returned incomplete results")
        numeric = actual[:len(fixtures)]
        features_ok = np.allclose(numeric[:, :24], python_features, rtol=2e-6, atol=2e-7)
        probabilities_ok = np.allclose(numeric[:, 24:28], reference_probabilities, atol=2e-6, rtol=2e-6)
        mismatch = int(np.sum(numeric[:, 28] != reference_probabilities.argmax(1)))
        invalid_ok = bool(np.all(actual[-2:, 28] == 255) and np.all(actual[-2:, 29] == 1))
        reports.append({"language": language, "compile_command": cmd, "compiler_stderr": built.stderr,
                        "fixtures": len(fixtures), "invalid_fixtures": 2,
                        "max_feature_abs_error": float(np.max(np.abs(numeric[:, :24] - python_features))),
                        "max_probability_abs_error": float(np.max(np.abs(numeric[:, 24:28] - reference_probabilities))),
                        "prediction_mismatches": mismatch, "invalid_rejected": invalid_ok,
                        "desktop_elapsed_seconds_including_process_start": elapsed,
                        "passed": bool(features_ok and probabilities_ok and mismatch == 0 and invalid_ok)})
    result = {"passed": all(r["passed"] for r in reports) and reference_error < 2e-6 and not reference_mismatches,
              "languages": [r["language"] for r in reports], "reports": reports,
              "prediction_mismatches": sum(r["prediction_mismatches"] for r in reports) + reference_mismatches,
              "json_vs_sklearn_max_probability_error": reference_error,
              "timing_scope": "Windows desktop, not an ESP32 benchmark"}
    write_json(output / "numerical_parity.json", result)
    if not result["passed"]:
        raise AssertionError(json.dumps(result))
    return result


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def audit_existing(output: Path) -> dict:
    base = DATA_ROOT / "free_datasets"
    paths = [base / "cattle_classification_github_andssuu/data/dataset_6.csv"]
    paths += sorted((base / "cattle_behavior_github_HannahJames123/curc data accel").glob("*.csv"))
    results = []
    for path in paths:
        columns, rows = read_csv(path)
        result = {"path": str(path), "sha256": sha256(path), "rows": len(rows), "columns": columns}
        if path.name == "dataset_6.csv":
            labels = [r["label"] for r in rows]
            runs = []
            for label in labels:
                if not runs or runs[-1][0] != label:
                    runs.append([label, 0])
                runs[-1][1] += 1
            result.update({"label_counts": dict(Counter(labels)), "contiguous_label_runs": len(runs),
                "runs_per_label": dict(Counter(r[0] for r in runs)),
                "run_length_quantiles": np.quantile([r[1] for r in runs], [0, .25, .5, .75, 1]).tolist(),
                "time_order_verified": False, "animal_ids": None, "session_ids": None,
                "sample_rate_hz": None, "unit_scale_provenance": "16384 LSB/g assumed by legacy trainer; not documented in local README",
                "sensor_location": "legacy firmware calls this neck; local source README has no placement evidence",
                "use": "excluded from temporal training: no verified chronology, animal, or session identifiers",
                "source_url": "https://github.com/andssuu/cattle_classification"})
        elif path.name.startswith("AX3_RAW"):
            timestamps = np.array([int(r["hour"]) * 3600 + int(r["minute"]) * 60 + int(r["second"]) for r in rows])
            result.update({"time_delta_counts_seconds": dict(Counter(str(int(d)) for d in np.diff(timestamps))),
                "locomotion_counts": dict(Counter(r["Locomotion_Chloe"] for r in rows)),
                "feeding_counts": dict(Counter(r["Feeding_Chloe"] for r in rows)),
                "observer_locomotion_disagreements": sum(r["Locomotion_Chloe"] != r["Locomotion_Steven"] for r in rows),
                "observer_feeding_disagreements": sum(r["Feeding_Chloe"] != r["Feeding_Steven"] for r in rows),
                "observed_row_rate_hz": 1, "raw_device_rate_hz": None, "animal_ids": None,
                "session": "single filename-dated 2024-06-27 sequence; inferred from filename only",
                "sensor_location": "not documented in available source",
                "use": "not pooled with verified-neck 20 Hz data; only one unidentified record and unknown placement"})
        elif path.name.startswith("Accelerometer_"):
            times = np.array([float(r["Date_time"].split(":")[0]) * 60 + float(r["Date_time"].split(":")[1]) for r in rows])
            delta = np.round(np.diff(times), 3)
            result.update({"time_format": "minute:second.tenth only, no hour or date",
                "time_delta_counts_seconds": dict(Counter(str(float(d)) for d in delta)),
                "animal_ids": None, "session_ids": None, "behavior_labels": False,
                "use": "excluded: ambiguous absolute time; cannot certify join to observer date/hour labels"})
        else:
            result.update({"locomotion_counts": dict(Counter(r["Locomotion"] for r in rows)),
                "use": "observer events have full date/time but cannot disambiguate the matching raw clock"})
        results.append(result)
    report = {"existing_sources": results, "hannah_source_url": "https://github.com/HannahJames123/cattle-behavior",
              "no_source_rows_reordered_or_overwritten": True,
              "clinical_lameness": "No independently verified clinical labels acquired; disabled"}
    write_json(output / "existing_data_audit.json", report)
    return report


def load_records(sources: Path, output: Path) -> list[RawRecord]:
    records, audits = [], []
    for path in sorted(sources.glob("cow*.csv")):
        columns, rows = read_csv(path)
        normalized = {c.strip().lower().replace(" ", ""): c for c in columns}
        def key(prefix):
            matches = [c for normalized_name, c in normalized.items() if normalized_name.startswith(prefix)]
            if len(matches) != 1:
                raise ValueError(f"Unrecognized public schema: {columns}; expected {prefix}")
            return matches[0]
        ts_key, label_key = key("timestamp_unix"), key("label")
        axes = [key("acc" + axis) for axis in "xyz"]
        # The actual v2 CSV encodes UNIX timestamps in integer milliseconds.
        timestamps = np.array([float(row[ts_key]) / 1000 for row in rows], dtype=np.float64)
        xyz = np.array([[float(row[axis]) for axis in axes] for row in rows], dtype=np.float32)
        labels = np.array([row[label_key].strip() for row in rows])
        record = RawRecord(path.stem, path.stem, "2020-06-12", timestamps, xyz, labels)
        records.append(record)
        dt = np.diff(timestamps)
        audits.append({"record_id": record.record_id, "animal": record.animal,
            "source_csv": str(path), "sha256": sha256(path), "rows": len(rows), "columns": columns,
            "raw_split": ASSIGNMENTS[record.animal], "label_counts": dict(Counter(labels.tolist())),
            "finite_xyz_rows": int(np.isfinite(xyz).all(axis=1).sum()),
            "xyz_min_g": np.min(xyz, axis=0).astype(float).tolist(),
            "xyz_max_g": np.max(xyz, axis=0).astype(float).tolist(),
            "rows_with_any_axis_abs_gt_2g": int(np.sum(np.any(np.abs(xyz) > 2, axis=1))),
            "timestamps_first_last": [float(timestamps[0]), float(timestamps[-1])],
            "timestamp_encoding": "source UNIX milliseconds divided by 1000; seconds used internally",
            "timestamp_delta_quantiles_seconds": np.quantile(dt, [0, .25, .5, .75, 1]).tolist(),
            "nonincreasing_timestamp_count": int(np.sum(dt <= 0)),
            "sampling_gap_count": int(np.sum(np.abs(dt - 1 / 25) > .012)),
            "native_sample_rate_hz": 25, "sensor_location": "neck", "accelerometer": "Kionix KX122-1037, 16-bit +/-2g"})
        print(f"Read {record.animal}: {len(rows)} native samples, {dict(Counter(labels.tolist()))}", flush=True)
    write_json(output / "public_data_audit.json", {"records": audits,
        "source_doi": "10.5281/zenodo.5849025", "collection_day": "2020-06-12",
        "farm_count": 1, "animal_count": len(records), "native_samples": sum(len(r.labels) for r in records),
        "session_id_provenance": "source provides one CSV per animal and collection date, not independent session IDs; timestamp discontinuities define separate segments",
        "label_protocol": "GPS-synchronized video; three annotators; majority-voted labels; 69 person-hours reported by source",
        "units": "g (source column names)", "source_rows_reordered": False,
        "source_metadata_license": "CC BY 4.0", "source_description_license": "CC BY-NC-ND 4.0",
        "license_resolution": "unresolved conflicting source statements; research candidate, no production eligibility"})
    return records


def audit_posture_support(records: list[RawRecord], output: Path) -> dict:
    per_animal = []
    for record in records:
        counts = Counter(record.labels.tolist())
        delta = np.diff(record.timestamps)
        changes = np.r_[True, (record.labels[1:] != record.labels[:-1]) | (np.abs(delta - .04) > .012)]
        starts = np.flatnonzero(changes)
        lying_windows = 0
        lying_runs = []
        for start, stop in zip(starts, np.r_[starts[1:], len(record.labels)]):
            if record.labels[start] != "REL":
                continue
            length = int(stop - start)
            lying_runs.append(length)
            target_length = int(np.ceil(length * 4 / 5))
            lying_windows += max(0, (target_length - 2 * PURGE - WINDOW) // HOP + 1)
        per_animal.append({"animal": record.animal, "raw_split": ASSIGNMENTS[record.animal],
            "explicit_lying_resting_REL_samples": counts["REL"], "explicit_lying_seconds": counts["REL"] / 25,
            "explicit_standing_RES_RUS_samples": counts["RES"] + counts["RUS"],
            "lying_native_contiguous_run_lengths": lying_runs,
            "eligible_4s_lying_windows_after_1s_edge_purge": lying_windows})
    lying_animals = [r["animal"] for r in per_animal if r["explicit_lying_resting_REL_samples"] > 0]
    sufficient = (len([a for a in lying_animals if ASSIGNMENTS[a] == "train"]) >= 2 and
                  len([a for a in lying_animals if ASSIGNMENTS[a] == "test"]) >= 1)
    report = {"all_observed_labels": sorted(set(np.concatenate([r.labels for r in records]).tolist())),
        "verified_mapping": {"REL": "lying_resting", "RES": "standing_resting", "RUS": "standing_ruminating"},
        "unmapped_for_binary_posture": "GRZ/MOV and all other labels: no implied clinical posture truth",
        "lying_ruminating_label_available": False, "per_animal": per_animal,
        "lying_animal_count": len(lying_animals), "lying_animals": lying_animals,
        "minimum_independent_support_rule": "At least 2 training animals with explicit lying for inner animal validation and at least 1 untouched test animal with explicit lying",
        "support_sufficient": sufficient, "new_binary_posture_model_created": False,
        "decision": "retain_existing_binary_posture_with_limitations" if not sufficient else "eligible_for_separate_binary_experiment",
        "existing_binary": {"accuracy_prior_report": .8691, "macro_f1_prior_report": .8555,
            "validation": "contiguous-label-run split, not animal-independent",
            "limitations": "unknown animal/session identifiers, unverified sampling/placement metadata; not clinical lameness"}}
    write_json(output / "binary_posture_support.json", report)
    return report


def calculate_metrics(y: np.ndarray, predicted: np.ndarray) -> dict:
    report = classification_report(y, predicted, labels=list(range(4)), target_names=CLASSES,
                                   output_dict=True, zero_division=0)
    supported = [report[name] for name in CLASSES if report[name]["support"] > 0]
    return {"accuracy": float(accuracy_score(y, predicted)),
            "balanced_accuracy": float(np.mean([r["recall"] for r in supported])),
            "macro_f1": float(f1_score(y, predicted, labels=list(range(4)), average="macro", zero_division=0)),
            "supported_class_macro_f1": float(np.mean([r["f1-score"] for r in supported])),
            "weighted_f1": float(f1_score(y, predicted, average="weighted", zero_division=0)),
            "classes": {name: {"precision": report[name]["precision"], "recall": report[name]["recall"],
                               "f1": report[name]["f1-score"], "support": int(report[name]["support"])} for name in CLASSES},
            "confusion_matrix": confusion_matrix(y, predicted, labels=list(range(4))).tolist(),
            "windows": len(y)}


def make_forest(configuration: dict) -> RandomForestClassifier:
    return RandomForestClassifier(**configuration, max_depth=8, min_samples_leaf=3,
        max_features="sqrt", class_weight="balanced_subsample", random_state=SEED, n_jobs=4)


def select_configuration(features: np.ndarray, labels: np.ndarray, animals: np.ndarray,
                         train_indices: np.ndarray, output: Path) -> dict:
    configurations = [{"n_estimators": 16, "max_leaf_nodes": 16},
                      {"n_estimators": 24, "max_leaf_nodes": 32},
                      {"n_estimators": 32, "max_leaf_nodes": 48}]
    candidates = []
    for configuration in configurations:
        folds = []
        for cow in sorted(set(animals[train_indices].tolist())):
            fit_indices = train_indices[animals[train_indices] != cow]
            validation_indices = train_indices[animals[train_indices] == cow]
            forest = make_forest(configuration).fit(features[fit_indices], labels[fit_indices])
            metrics = calculate_metrics(labels[validation_indices], forest.predict(features[validation_indices]))
            folds.append({"validation_animal": cow, "training_animals": sorted(set(animals[fit_indices].tolist())),
                          "train_windows": len(fit_indices), "metrics": metrics})
        score = float(np.mean([f["metrics"]["macro_f1"] for f in folds]))
        candidates.append({"configuration": configuration, "mean_animal_macro_f1": score, "folds": folds})
        print(f"Train-only grouped selection {configuration}: mean macro F1={score:.6f}", flush=True)
    best = max(range(len(candidates)), key=lambda i: candidates[i]["mean_animal_macro_f1"])
    report = {"selection_data": "training cows 1,2,3,6 only; leave-one-training-animal-out",
              "test_animals_never_scored_during_selection": ["cow4", "cow5"],
              "selection_metric": "mean validation animal macro F1 over fixed four labels; missing labels contribute zero",
              "window_and_features_fixed_before_test": True,
              "candidates": candidates, "selected_configuration": candidates[best]["configuration"]}
    write_json(output / "train_only_model_selection.json", report)
    return report["selected_configuration"]


def unique_window_points(windows: list[WindowRecord]) -> tuple[np.ndarray, np.ndarray, list[list[int]]]:
    lookup, points, labels, indices = {}, [], [], []
    for window in windows:
        row_indices = []
        for i, point in enumerate(window.xyz):
            key = (window.record_id, window.segment, window.target_start + i)
            if key not in lookup:
                lookup[key] = len(points)
                points.append(point)
                labels.append(window.label)
            row_indices.append(lookup[key])
        indices.append(row_indices)
    return np.asarray(points, dtype=np.float32), np.asarray(labels, dtype=np.int8), indices


def train_legacy_comparison(train_windows: list[WindowRecord], test_windows: list[WindowRecord],
                            output: Path) -> tuple[np.ndarray, dict]:
    legacy_path = DATA_ROOT / "esp32_motion_model/train_export_model.py"
    spec = importlib.util.spec_from_file_location("legacy_motion_readonly", legacy_path)
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    legacy.LABELS = CLASSES  # In-memory task adaptation; the legacy source is never written.
    x_train, y_train, _ = unique_window_points(train_windows)
    x_test, _, test_point_indices = unique_window_points(test_windows)
    parameters = {"trees": 40, "max_depth": 11, "min_samples_leaf": 8,
                  "max_features": 3, "samples_per_class": 800, "seed": 20260719}
    model = legacy.CompactRandomForest(**parameters)
    print(f"Re-training exact legacy pointwise algorithm: {len(x_train)} unique train points; {len(x_test)} test points", flush=True)
    log = io.StringIO()
    with contextlib.redirect_stdout(log):
        model.fit(x_train, y_train)
    (output / "legacy_comparison_fit.log").write_text(log.getvalue(), encoding="ascii")
    predicted_points = model.predict(x_test)
    predictions = np.array([np.argmax(np.bincount(predicted_points[index], minlength=4))
                            for index in test_point_indices], dtype=np.int8)
    report = {"method": "original CompactRandomForest re-fit on the new four-label task; pointwise XYZ then majority vote over the identical 80-sample heldout windows",
              "source_script": str(legacy_path), "source_sha256": sha256(legacy_path),
              "parameters": parameters, "unique_training_resampled_points": len(x_train),
              "unique_test_resampled_points": len(x_test), "total_nodes": sum(len(t.nodes) for t in model.trees),
              "overlap_weighting": "deduplicated per record/segment/resampled sample before pointwise fitting",
              "prior_64_32_percent_comparison": "not comparable: old six-class dataset/split/task differs; no direct improvement claim",
              "same_holdout_comparison_valid": True,
              "baseline_trees": [[vars(n) for n in tree.nodes] for tree in model.trees]}
    write_json(output / "legacy_pointwise_refit.json", report)
    return predictions, {k: v for k, v in report.items() if k != "baseline_trees"}


def protected_hashes() -> dict[str, str]:
    paths = list((DATA_ROOT / "esp32_motion_model").glob("*.py"))
    paths += list((DATA_ROOT / "esp32_motion_model").glob("*.json"))
    paths += list((DATA_ROOT / "free_datasets/cattle_classification_github_andssuu/data").glob("*.csv"))
    paths += list((DATA_ROOT / "free_datasets/cattle_behavior_github_HannahJames123/curc data accel").glob("*.csv"))
    firmware = ROOT / "\u786c\u4ef6\u4ee3\u7801/\u73b0\u6709\u786c\u4ef6\u6f14\u793a\u8282\u70b9/include"
    paths += [p for p in (firmware / "cattle_behavior_model.h", firmware / "cattle_posture_model.h",
                          firmware / "cattle_lameness_model.h") if p.exists()]
    return {str(p): sha256(p) for p in sorted(paths)}


def predict_legacy_artifact(output: Path, test_windows: list[WindowRecord]) -> np.ndarray:
    saved = json.loads((output / "legacy_pointwise_refit.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("legacy_motion_fresh_verify", Path(saved["source_script"]))
    legacy = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = legacy
    spec.loader.exec_module(legacy)
    legacy.LABELS = CLASSES
    model = legacy.CompactRandomForest(**saved["parameters"])
    for nodes in saved["baseline_trees"]:
        tree = legacy.CompactDecisionTree(11, 8, 3, np.random.default_rng(0))
        tree.nodes = [legacy.Node(**node) for node in nodes]
        model.trees.append(tree)
    points, _, indices = unique_window_points(test_windows)
    predicted_points = model.predict(points)
    return np.array([np.argmax(np.bincount(predicted_points[index], minlength=4)) for index in indices], dtype=np.int8)


def update_contract(output: Path, model: dict) -> None:
    write_json(output / "feature_model_contract.json", {
        "version": model["version"], "status": "trained_candidate_python_c_cpp_parity_verified",
        "sensor_location": "neck_only", "input": {"shape": [80, 3], "layout": "xyz interleaved",
            "dtype": "float32", "units": "g", "sample_rate_hz": 20, "window_seconds": 4,
            "hop_samples": 40, "first_to_last_sample_seconds": 3.95},
        "feature_count": 24, "feature_names": list(FEATURE_NAMES),
        "feature_order": "channel-major: x,y,z,norm; each mean,population_std,min,max,mean_absolute_delta,rms_delta",
        "arithmetic": "promote float32 XYZ to float64; norm=sqrt(x*x+y*y+z*z); double accumulation; float32 features",
        "transform_fit_scope": "No learned normalization, imputation, PCA, SMOTE or filtering parameters",
        "classes": list(CLASSES), "source_labels": SOURCE_LABELS,
        "source": "https://doi.org/10.5281/zenodo.5849025",
        "source_preprocessing": {"native_rate_hz": 25, "timestamp_unit": "UNIX milliseconds -> seconds",
            "resampling": "scipy.signal.resample_poly(up=4,down=5,window=('kaiser',5.0),padtype='constant') per same-label contiguous record segment",
            "resampling_filter_native_radius_samples": 13, "purge_each_segment_edge_seconds": 1,
            "raw_split_before_resampling_and_windows": True, "max_native_interval_error_seconds": .012},
        "raw_animal_split": {role: sorted(c for c, r in ASSIGNMENTS.items() if r == role)
                             for role in ("train", "test")},
        "runtime_requirements": ["real neck XYZ in calibrated g with matching source axis/mounting convention",
            "20 Hz uniform sampling; runtime must reset on dropped, invalid, delayed samples or sensor-location/configuration changes",
            "80 actual consecutive samples before first inference; never duplicate samples to fill a window",
            "samples from m/s^2 must be divided by 9.80665 exactly once",
            "runtime buffers should preserve 40 samples for the next overlapping window",
            "gaps and timestamps are caller responsibilities; array extractor cannot validate elapsed time",
            "MOV means moving; do not rename as walking, standing, or clinical lameness truth"],
        "header": "cattle_motion_temporal_candidate.h", "feature_header": "motion_temporal_features.h",
        "c_api": {"motion_temporal_extract_features": "int (const float *xyz_interleaved, size_t samples, float *features); 1 success / 0 invalid",
            "motion_temporal_predict_features": "MotionTemporalPrediction (const float *features)",
            "motion_temporal_predict_window": "MotionTemporalPrediction (const float *xyz_interleaved, size_t samples)"},
        "prediction": {"fields": ["uint8_t label", "float confidence", "uint8_t rejected", "float probabilities[4]"],
            "invalid_label": 255, "confidence_meaning": "uncalibrated mean tree leaf probability, not diagnostic probability",
            "tie_break": "lowest class index", "rejection": "null/wrong window length/nonfinite; no field OOD threshold validated"},
        "candidate_parameters": {"trees": len(model["roots"]), "nodes": len(model["nodes"]),
            "leaves": len(model["leaf_probabilities"]), "node_index_bits": 16},
        "integration_policy": "Explicit opt-in alongside old default only; never overwrite old neck/posture model or clinical gates",
        "production_eligible": False, "clinical_lameness_enabled": False,
        "limitations": ["four classes, not a drop-in six-class replacement", "no lying-ruminating labels; insufficient independent lying support",
            "one farm, one day, six animals; no local sensor/orientation validation", "no back/leg learned fusion",
            "source description says BY-NC-ND while API says BY; unresolved license conflict"]})


def build_manifest(output: Path) -> None:
    excluded = {"artifact_manifest.json", "verification_results.json", "training_status.json"}
    files = [p for p in output.rglob("*") if p.is_file() and p.name not in excluded
             and "__pycache__" not in p.parts]
    write_json(output / "artifact_manifest.json", {"files": [
        {"path": str(p.relative_to(output)), "bytes": p.stat().st_size, "sha256": sha256(p)}
        for p in sorted(files)]})


def run_training(output: Path) -> None:
    started = time.perf_counter()
    initial_hashes = protected_hashes()
    write_json(output / "protected_inputs_before.json", initial_hashes)
    (output / "training_script_snapshot.py").write_bytes(Path(__file__).read_bytes())
    write_json(output / "training_status.json", {"status": "training", "production_eligible": False,
               "clinical_lameness_enabled": False, "started_at_utc": datetime.now(timezone.utc).isoformat()})
    sources = acquire_sources(output)
    audit_existing(output)
    records = load_records(sources, output)
    posture = audit_posture_support(records, output)
    if posture["support_sufficient"]:
        raise RuntimeError("Unexpected adequate posture support; separate grouped binary experiment required before claiming completion")
    windows = make_windows(records, ASSIGNMENTS)
    if not windows:
        raise RuntimeError("No verified temporal windows")
    features = np.stack([extract_features(w.xyz) for w in windows])
    labels = np.array([w.label for w in windows], dtype=np.int8)
    animals = np.array([w.animal for w in windows])
    roles = np.array([w.split for w in windows])
    train_indices, test_indices = np.flatnonzero(roles == "train"), np.flatnonzero(roles == "test")
    for role, indices in (("train", train_indices), ("test", test_indices)):
        if set(labels[indices].tolist()) != set(range(4)):
            raise ValueError(f"Missing source class in {role}")
    raw_audit = json.loads((output / "public_data_audit.json").read_text(encoding="utf-8"))
    write_csv(output / "raw_animal_split.csv", [{"animal": r.animal, "record_id": r.record_id,
        "session": r.session, "split": ASSIGNMENTS[r.animal], "native_samples": len(r.labels),
        "source_sha256": sha256(sources / f"{r.animal}.csv")} for r in records])
    write_csv(output / "window_manifest.csv", [{"window_id": i, "animal": w.animal,
        "record_id": w.record_id, "session": w.session, "split": w.split, "segment": w.segment,
        "segment_raw_start_0based": w.segment_start, "segment_raw_stop_exclusive": w.segment_stop,
        "raw_fir_support_start_0based": w.raw_start, "raw_fir_support_stop_exclusive": w.raw_stop,
        "resampled_segment_start_0based": w.target_start, "label": CLASSES[w.label],
        "source_label": next(k for k, v in SOURCE_LABELS.items() if v == w.label)} for i, w in enumerate(windows)])
    print(f"Raw animal split fixed; windows train={len(train_indices)}, test={len(test_indices)}", flush=True)
    configuration = select_configuration(features, labels, animals, train_indices, output)
    forest = make_forest(configuration).fit(features[train_indices], labels[train_indices])
    candidate_probabilities = forest.predict_proba(features[test_indices])
    temporal_predictions = candidate_probabilities.argmax(1)
    train_windows = [windows[i] for i in train_indices]
    test_windows = [windows[i] for i in test_indices]
    legacy_predictions, legacy_report = train_legacy_comparison(train_windows, test_windows, output)
    mean_model = make_forest(configuration).fit(features[train_indices][:, [0, 6, 12]], labels[train_indices])
    mean_predictions = mean_model.predict(features[test_indices][:, [0, 6, 12]])
    # Separate windows by 6 seconds to make even their fixed FIR contexts disjoint.
    nonoverlap = np.array([(w.target_start - PURGE) % (3 * HOP) == 0 for w in test_windows])
    model = model_to_json(forest)
    write_json(output / "candidate_model.json", model)
    export_headers(output, model)
    test_xyz = np.stack([w.xyz for w in test_windows])
    np.savez_compressed(output / "evaluation_cache.npz", features=features, labels=labels,
        animals=animals, roles=roles, test_xyz=test_xyz, temporal_predictions=temporal_predictions,
        legacy_predictions=legacy_predictions, mean_predictions=mean_predictions,
        nonoverlap=nonoverlap, sklearn_probabilities=candidate_probabilities)
    candidates = {"temporal_24_features": temporal_predictions,
                  "legacy_pointwise_xyz_majority_refit": legacy_predictions,
                  "window_mean_xyz_ablation": mean_predictions}
    heldout = {name: calculate_metrics(labels[test_indices], pred) for name, pred in candidates.items()}
    per_animal = {cow: {name: calculate_metrics(labels[test_indices][animals[test_indices] == cow],
                    pred[animals[test_indices] == cow]) for name, pred in candidates.items()}
                  for cow in sorted(set(animals[test_indices].tolist()))}
    report = {"model": model["version"], "source_doi": "10.5281/zenodo.5849025",
        "task": "four verified neck behavior labels; not clinical lameness or binary posture",
        "classes": list(CLASSES), "raw_samples": raw_audit["native_samples"],
        "training_animals": sorted(set(animals[train_indices].tolist())),
        "test_animals": sorted(set(animals[test_indices].tolist())),
        "train_windows": len(train_indices), "test_windows": len(test_indices),
        "windows_by_animal_class": {cow: {name: int(np.sum((animals == cow) & (labels == i)))
            for i, name in enumerate(CLASSES)} for cow in sorted(set(animals.tolist()))},
        "configuration": forest.get_params(), "selected_configuration": configuration,
        "heldout_metrics": heldout, "per_test_animal_metrics": per_animal,
        "purged_nonoverlapping_test": {"windows": int(nonoverlap.sum()), "selection": "every third 2-second hop within each segment; 6-second spacing; FIR supports do not overlap",
            "metrics": {name: calculate_metrics(labels[test_indices][nonoverlap], pred[nonoverlap])
                        for name, pred in candidates.items()}},
        "fair_baseline": legacy_report,
        "prior_metrics_comparison": "Old 64.32% six-class and 86.91% binary results are not numerically comparable to this new source/task/animal split",
        "footprint": {"trees": len(model["roots"]), "nodes": len(model["nodes"]),
            "leaves": len(model["leaf_probabilities"]),
            "model_arrays_bytes_assuming_12byte_node": len(model["nodes"]) * 12 + len(model["leaf_probabilities"]) * 16 + len(model["roots"]) * 2,
            "feature_scratch_bytes": WINDOW * 8,
            "raw_window_buffer_bytes": WINDOW * 3 * 4,
            "candidate_header_text_bytes": (output / "cattle_motion_temporal_candidate.h").stat().st_size},
        "binary_posture_decision": posture["decision"], "new_binary_posture_model_created": False,
        "production_eligible": False, "clinical_lameness_enabled": False,
        "validation_limits": ["two independent heldout cows, one farm, one date", "overlapping windows are not independent observations",
            "pure-label windows exclude transitions; field mixed windows and unknown behaviors not validated",
            "no local orientation or ADXL345 domain validation; no calibrated confidence/OOD threshold",
            "hyperparameters chosen only on four training animals; heldout animals not used for fitting/selection",
            "unresolved source licensing conflict"],
        "execution": {"python": sys.version, "numpy": np.__version__,
            "sklearn": __import__("sklearn").__version__, "scipy": __import__("scipy").__version__,
            "cpu_only": True, "max_threads": 4, "training_elapsed_seconds": time.perf_counter() - started}}
    write_json(output / "training_report.json", report)
    write_csv(output / "heldout_predictions.csv", [{"window_id": int(index), "animal": windows[index].animal,
        "source_label": next(k for k, v in SOURCE_LABELS.items() if v == windows[index].label),
        "expected": CLASSES[windows[index].label], "temporal": CLASSES[int(temporal_predictions[j])],
        "legacy_pointwise_refit": CLASSES[int(legacy_predictions[j])],
        "window_mean_xyz": CLASSES[int(mean_predictions[j])],
        "confidence_uncalibrated": float(candidate_probabilities[j].max()),
        "purged_nonoverlapping_subset": int(nonoverlap[j])} for j, index in enumerate(test_indices)])
    print(json.dumps({name: {key: m[key] for key in ("accuracy", "balanced_accuracy", "macro_f1")}
                      for name, m in heldout.items()}, indent=2), flush=True)
    verify_portable(output, model, test_xyz, candidate_probabilities)
    update_contract(output, model)
    if protected_hashes() != initial_hashes:
        raise AssertionError("A protected old input/header changed while training; inspect ownership before claiming unchanged")
    build_manifest(output)
    verify_artifacts(output)
    write_json(output / "training_status.json", {"status": "trained_and_verified_research_candidate",
        "production_eligible": False, "clinical_lameness_enabled": False,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_seconds": time.perf_counter() - started})


def verify_artifacts(output: Path) -> None:
    model = json.loads((output / "candidate_model.json").read_text(encoding="utf-8"))
    report = json.loads((output / "training_report.json").read_text(encoding="utf-8"))
    contract = json.loads((output / "feature_model_contract.json").read_text(encoding="utf-8"))
    checks = {}
    records = load_records(output / "sources", output)
    rebuilt_windows = make_windows(records, ASSIGNMENTS)
    rebuilt_features = np.stack([extract_features(w.xyz) for w in rebuilt_windows])
    rebuilt_test = [w for w in rebuilt_windows if w.split == "test"]
    with np.load(output / "evaluation_cache.npz", allow_pickle=False) as cache:
        test_indices = np.flatnonzero(cache["roles"] == "test")
        feature_recomputed = np.stack([extract_features(xyz) for xyz in cache["test_xyz"]])
        checks["saved_test_features_recomputed_from_xyz"] = bool(np.array_equal(feature_recomputed, cache["features"][test_indices]))
        checks["all_windows_and_features_rebuilt_from_original_csv"] = bool(np.array_equal(rebuilt_features, cache["features"]))
        checks["all_raw_labels_match_window_labels"] = np.array_equal(np.array([w.label for w in rebuilt_windows]), cache["labels"])
        checks["all_raw_animal_assignments_match_cache"] = np.array_equal(np.array([w.animal for w in rebuilt_windows]), cache["animals"])
        checks["raw_animals_disjoint"] = not bool(set(cache["animals"][cache["roles"] == "train"].tolist()) & set(cache["animals"][test_indices].tolist()))
        probabilities = predict_json(model, feature_recomputed)
        metrics = calculate_metrics(cache["labels"][test_indices], probabilities.argmax(1))
        checks["model_json_predictions_and_metrics_recomputed"] = metrics == report["heldout_metrics"]["temporal_24_features"]
        checks["baseline_metrics_recomputed"] = (calculate_metrics(cache["labels"][test_indices], cache["legacy_predictions"]) ==
                                                  report["heldout_metrics"]["legacy_pointwise_xyz_majority_refit"])
        checks["legacy_baseline_inference_recomputed_from_saved_trees"] = np.array_equal(
            predict_legacy_artifact(output, rebuilt_test), cache["legacy_predictions"])
        sparse_windows = [w for w, selected in zip(rebuilt_test, cache["nonoverlap"]) if selected]
        last_stop = {}
        sparse_disjoint = True
        for w in sparse_windows:
            sparse_disjoint = sparse_disjoint and w.raw_start >= last_stop.get(w.record_id, -1)
            last_stop[w.record_id] = w.raw_stop
        checks["six_second_test_subset_raw_fir_contexts_disjoint"] = sparse_disjoint
        parity = verify_portable(output, model, cache["test_xyz"], cache["sklearn_probabilities"])
        checks["fresh_c99_cpp11_full_heldout_parity"] = parity["passed"]
    _, manifest = read_csv(output / "window_manifest.csv")
    checks["all_window_fir_contexts_inside_raw_segments"] = all(
        int(w["segment_raw_start_0based"]) <= int(w["raw_fir_support_start_0based"]) <
        int(w["raw_fir_support_stop_exclusive"]) <= int(w["segment_raw_stop_exclusive"]) for w in manifest)
    checks["edge_purge_at_least_one_second"] = all(int(w["resampled_segment_start_0based"]) >= 20 for w in manifest)
    checks["manifest_matches_rebuilt_raw_contexts"] = (len(manifest) == len(rebuilt_windows) and all(
        int(row["raw_fir_support_start_0based"]) == w.raw_start and
        int(row["raw_fir_support_stop_exclusive"]) == w.raw_stop and
        row["animal"] == w.animal and row["split"] == w.split and row["label"] == CLASSES[w.label]
        for row, w in zip(manifest, rebuilt_windows)))
    checks["clinical_disabled_and_candidate_only"] = (not model["production_eligible"] and
        not model["clinical_lameness_enabled"] and not contract["production_eligible"] and not contract["clinical_lameness_enabled"])
    checks["existing_inputs_and_headers_unchanged"] = protected_hashes() == json.loads((output / "protected_inputs_before.json").read_text(encoding="utf-8"))
    integrity = json.loads((output / "sources/integrity.json").read_text(encoding="utf-8"))
    checks["public_source_hashes_match"] = all(sha256(output / "sources" / name) == digest for name, digest in integrity["csv_sha256"].items())
    with zipfile.ZipFile(output / "sources/JapaneseBlackBeefData.zip") as zipped:
        checks["public_archive_crc"] = zipped.testzip() is None
    checks["public_archive_sha256"] = sha256(output / "sources/JapaneseBlackBeefData.zip") == integrity["archive_sha256"]
    checks = {name: bool(value) for name, value in checks.items()}
    result = {"passed": all(checks.values()), "checks": checks,
              "checked_at_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "recompute features, JSON inference and metrics, full heldout native C/C++ inference, input hashes and window manifest"}
    write_json(output / "verification_results.json", result)
    if not result["passed"]:
        raise AssertionError(json.dumps(result))
    print(f"Verified {len(checks)} artifact checks; C99/C++11 predictions match", flush=True)
    build_manifest(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--acquire-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true", help="Fresh offline artifact and full heldout C/C++ checks")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=4):
        if args.verify_only:
            verify_artifacts(args.output)
        elif args.acquire_only:
            sources = acquire_sources(args.output)
            print(f"Verified public sources: {sources}", flush=True)
        else:
            run_training(args.output)


if __name__ == "__main__":
    main()
