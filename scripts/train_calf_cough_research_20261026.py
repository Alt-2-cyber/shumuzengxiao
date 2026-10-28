#!/usr/bin/env python3
"""CPU-only, file-level calf cough event research; never a disease model."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import platform
import sys
import time
import unittest
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

for thread_variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                        "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ[thread_variable] = "1"
sys.dont_write_bytecode = True

import numpy as np
import scipy
from scipy.io import wavfile
from scipy.signal import resample_poly
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "audio-training-data" / "external" / "20261025"
ARTIFACTS = ROOT / "audio-training-data" / "artifacts" / "calf-cough-research-20261026"
REPORT = ROOT / "docs" / "2026-10-26-calf-cough-research.md"
RATE = 8000
WINDOW = 8000
SEED = 20261026
CLASSES = ["non_cough", "cough"]
FEATURE_NAMES = [
    "zero_crossing_rate", "log1p_peak_to_rms", "frame_rms_cv", "frame_active_fraction",
    "spectral_centroid_nyquist", "spectral_bandwidth_nyquist", "spectral_rolloff85_nyquist",
    "spectral_flatness", "spectral_flux", "band_0_250_fraction", "band_250_500_fraction",
    "band_500_1000_fraction", "band_1000_2000_fraction", "band_2000_4000_fraction",
]
UNKNOWN_GROUP = "rdg-FP5LA9:recording-session-unknown"
POLICY = {
    "research_only": True, "production_approved": False, "allow_for_disease_labels": False,
    "source_group_status": "source group unknown", "animal_independent_validation": False,
    "non_cough_means_healthy": False,
}
FEATURE_DEFINITION = {
    "schema_version": 1, "id": "calf-event-shape14-8khz-1s-v1",
    "sample_rate_hz": RATE, "window_samples": WINDOW, "hop_samples": WINDOW,
    "resampling": {"method": "scipy.signal.resample_poly", "up_down": "reduce 8000/source_rate by gcd",
                   "window": ["kaiser", 5.0], "padtype": "constant", "minimum_source_rate_hz": RATE},
    "coverage": "Never trim zeros. Valid-prefix metadata is explicit; otherwise all WAV samples are observed.",
    "normalization": "Subtract mean and divide by AC RMS over observed samples only, independently per window.",
    "frames": {"samples": 200, "hop_samples": 80, "fft_samples": 256,
               "window": "periodic Hann: 0.5 - 0.5*cos(2*pi*n/200)",
               "tail_policy": "Use complete frames; if fewer than 200 observed samples, right-pad one frame."},
    "minimum_observed_samples_for_scoring": 800,
    "silence_rms_full_scale": 1e-8,
    "numeric_floor": 1e-12,
    "spectral_power": "abs(rfft(normalized_frame * Hann, n=256))**2; mean power across frames",
    "features": [
        {"name": FEATURE_NAMES[0], "formula": "mean(signbit(x[1:]) != signbit(x[:-1]))"},
        {"name": FEATURE_NAMES[1], "formula": "log1p(max(abs(x))) after unit-RMS normalization"},
        {"name": FEATURE_NAMES[2], "formula": "population std(frame RMS) / max(mean(frame RMS),1e-12)"},
        {"name": FEATURE_NAMES[3], "formula": "mean(frame RMS >= 0.25 * max(frame RMS))"},
        {"name": FEATURE_NAMES[4], "formula": "sum(f * mean_power) / sum(mean_power) / 4000"},
        {"name": FEATURE_NAMES[5], "formula": "sqrt(sum((f-centroid)**2 * mean_power)/sum(mean_power))/4000"},
        {"name": FEATURE_NAMES[6], "formula": "first FFT-bin frequency reaching 85% cumulative mean power / 4000"},
        {"name": FEATURE_NAMES[7], "formula": "exp(mean(log(max(mean_power,1e-12)))) / max(mean(mean_power),1e-12)"},
        {"name": FEATURE_NAMES[8], "formula": "mean over adjacent frames of sum(diff(frame_power/sum(frame_power))**2); 0 for one frame"},
        *[{"name": FEATURE_NAMES[9 + i], "formula": f"sum(mean_power at {lo} <= f < {hi}) / sum(mean_power)"}
          for i, (lo, hi) in enumerate([(0, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4001)])],
    ],
    "excluded_from_classifier": ["duration", "padding", "raw amplitude", "quality flags", "filename", "source IDs"],
    "quality_flag_rules": {"low_rms": "AC RMS < 0.001 full scale (-60 dBFS)",
                           "near_full_scale": "fraction(abs(observed samples)>=0.999) > 0.01",
                           "short_observed_window": "observed samples < 8000"},
}


def finite_mono(samples):
    samples = np.asarray(samples, dtype=np.float64)
    if samples.ndim != 1 or not samples.size or not np.isfinite(samples).all():
        raise ValueError("Audio must be a nonempty, finite mono array")
    return samples


def signal_quality(samples):
    samples = np.asarray(samples, dtype=np.float64)
    if not samples.size:
        return {"dc_offset_full_scale": None, "rms_ac_full_scale": None, "rms_dbfs": None,
                "peak_full_scale": None, "near_full_scale_fraction": None,
                "exact_zero_fraction": None, "trailing_exact_zero_samples": 0}
    dc = float(np.mean(samples))
    rms = float(np.sqrt(np.mean((samples - dc) ** 2)))
    nonzero = np.flatnonzero(samples != 0)
    return {"dc_offset_full_scale": dc, "rms_ac_full_scale": rms,
            "rms_dbfs": float(20 * np.log10(max(rms, 1e-15))),
            "peak_full_scale": float(np.max(np.abs(samples))),
            "near_full_scale_fraction": float(np.mean(np.abs(samples) >= 0.999)),
            "exact_zero_fraction": float(np.mean(samples == 0)),
            "trailing_exact_zero_samples": int(len(samples) - nonzero[-1] - 1) if len(nonzero) else int(len(samples))}


def shape_features(observed):
    centered = observed - np.mean(observed)
    normalized = centered / np.sqrt(np.mean(centered ** 2))
    if len(normalized) < 200:
        frames = np.pad(normalized, (0, 200 - len(normalized)))[None, :]
    else:
        frames = np.lib.stride_tricks.sliding_window_view(normalized, 200)[::80]
    envelope = np.sqrt(np.mean(frames ** 2, axis=1))
    hann = 0.5 - 0.5 * np.cos(2 * np.pi * np.arange(200) / 200)
    power = np.abs(np.fft.rfft(frames * hann, n=256, axis=1)) ** 2
    mean_power = np.mean(power, axis=0)
    total = max(float(np.sum(mean_power)), 1e-12)
    frequencies = np.fft.rfftfreq(256, 1 / RATE)
    centroid = float(np.sum(frequencies * mean_power) / total)
    bandwidth = float(np.sqrt(np.sum((frequencies - centroid) ** 2 * mean_power) / total))
    rolloff_bin = min(int(np.searchsorted(np.cumsum(mean_power), 0.85 * total)), len(frequencies) - 1)
    frame_distribution = power / np.maximum(np.sum(power, axis=1, keepdims=True), 1e-12)
    flux = float(np.mean(np.sum(np.diff(frame_distribution, axis=0) ** 2, axis=1))) if len(frames) > 1 else 0.0
    bands = [(0, 250), (250, 500), (500, 1000), (1000, 2000), (2000, 4001)]
    result = np.asarray([
        np.mean(np.signbit(normalized[1:]) != np.signbit(normalized[:-1])),
        np.log1p(np.max(np.abs(normalized))),
        np.std(envelope) / max(float(np.mean(envelope)), 1e-12),
        np.mean(envelope >= 0.25 * np.max(envelope)),
        centroid / 4000, bandwidth / 4000, frequencies[rolloff_bin] / 4000,
        np.exp(np.mean(np.log(np.maximum(mean_power, 1e-12)))) / max(float(np.mean(mean_power)), 1e-12),
        flux,
        *[float(np.sum(mean_power[(frequencies >= lo) & (frequencies < hi)]) / total) for lo, hi in bands],
    ], dtype=np.float64)
    if result.shape != (len(FEATURE_NAMES),) or not np.isfinite(result).all():
        raise ValueError("Nonfinite or malformed feature vector")
    return result


def make_windows(samples, valid_samples=None):
    samples = finite_mono(samples)
    if valid_samples is None:
        valid_samples = len(samples)
    if isinstance(valid_samples, (bool, np.bool_)) or not isinstance(valid_samples, (int, np.integer)):
        raise ValueError("Observed prefix must be an integer sample count")
    if not 0 <= valid_samples <= len(samples):
        raise ValueError("Observed prefix is outside the WAV container")
    if np.any(samples[valid_samples:] != 0):
        raise ValueError("A declared padded tail must contain only exact zeros")
    windows = []
    for start in range(0, len(samples), WINDOW):
        container_count = min(WINDOW, len(samples) - start)
        observed_count = max(0, min(WINDOW, valid_samples - start))
        observed = samples[start:start + observed_count]
        quality = signal_quality(observed)
        quality.update(container_samples=int(container_count), observed_samples=int(observed_count),
                       observed_duration_seconds=observed_count / RATE,
                       known_input_padding_samples=int(container_count - observed_count),
                       algorithm_padding_samples=int(WINDOW - container_count),
                       total_unobserved_samples=int(WINDOW - observed_count))
        flags = []
        if observed_count < WINDOW:
            flags.append("short_observed_window")
        if observed_count and quality["rms_ac_full_scale"] < 0.001:
            flags.append("low_rms")
        if observed_count and quality["near_full_scale_fraction"] > 0.01:
            flags.append("near_full_scale")
        if not observed_count:
            status = "abstain_no_observed_samples"
        elif quality["rms_ac_full_scale"] <= 1e-8:
            status = "abstain_silence"
        elif observed_count < 800:
            status = "abstain_too_short"
        else:
            status = "research_score"
        windows.append({"window_index": len(windows), "start_seconds": start / RATE,
                        "nominal_end_seconds": (start + WINDOW) / RATE,
                        "quality": quality, "quality_flags": flags, "status": status,
                        "features": shape_features(observed) if status == "research_score" else None})
    return windows


def resample_audio(samples, source_rate):
    samples = finite_mono(samples)
    if not isinstance(source_rate, (int, np.integer)) or source_rate < RATE:
        raise ValueError("Source rate must be an integer >= 8000 Hz; missing bandwidth cannot be restored")
    divisor = math.gcd(int(source_rate), RATE)
    if source_rate == RATE:
        return samples.copy()
    return resample_poly(samples, RATE // divisor, int(source_rate) // divisor,
                         window=("kaiser", 5.0), padtype="constant")


def portable_probability(model, features):
    features = np.atleast_2d(np.asarray(features, dtype=np.float64))
    mean = np.asarray(model["scaler_mean"], dtype=np.float64)
    scale = np.asarray(model["scaler_scale"], dtype=np.float64)
    coefficients = np.asarray(model["coefficients"], dtype=np.float64)
    intercept = float(model["intercept"])
    if features.ndim != 2 or features.shape[1] != len(mean) or mean.shape != scale.shape or mean.shape != coefficients.shape:
        raise ValueError("Model and feature dimensions differ")
    if not all(np.isfinite(a).all() for a in (features, mean, scale, coefficients)) or not np.isfinite(intercept) or np.any(scale <= 0):
        raise ValueError("Nonfinite model/features or nonpositive scaling")
    return expit(((features - mean) / scale) @ coefficients + intercept)


def build_folds(labels, file_ids):
    from sklearn.model_selection import StratifiedGroupKFold

    labels, file_ids = np.asarray(labels), np.asarray(file_ids)
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
    folds = list(splitter.split(np.zeros((len(labels), 1)), labels, groups=file_ids))
    seen = np.zeros(len(labels), dtype=int)
    for train, test in folds:
        if set(file_ids[train]) & set(file_ids[test]):
            raise ValueError("A file crosses a validation boundary")
        if set(labels[train]) != {0, 1} or set(labels[test]) != {0, 1}:
            raise ValueError("Each fold must contain both acoustic event classes")
        seen[test] += 1
    if not np.all(seen == 1):
        raise ValueError("Every file must be held out exactly once")
    return folds


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def output_path(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ARTIFACTS.resolve()):
        raise ValueError(f"Output must stay under {ARTIFACTS}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path, value):
    output_path(path).write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def save_jsonl(path, rows):
    output_path(path).write_text("".join(json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n" for row in rows), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def decode_wav(source):
    source_rate, data = wavfile.read(source)
    if data.ndim not in (1, 2) or not data.size:
        raise ValueError("WAV must have at least one frame and one or more audio channels")
    if data.dtype == np.uint8:
        converted = (data.astype(np.float64) - 128) / 128
        clipped_fraction = float(np.mean((data == 0) | (data == 255)))
    elif data.dtype.kind == "i":
        limits = np.iinfo(data.dtype)
        converted = data.astype(np.float64) / (2.0 ** (limits.bits - 1))
        clipped_fraction = float(np.mean((data == limits.min) | (data == limits.max)))
    elif data.dtype.kind == "f":
        converted = data.astype(np.float64)
        clipped_fraction = float(np.mean(np.abs(converted) >= 1))
    else:
        raise ValueError(f"Unsupported WAV sample dtype: {data.dtype}")
    if not np.isfinite(converted).all():
        raise ValueError("WAV contains NaN or infinity")
    mono = np.mean(converted, axis=1) if converted.ndim == 2 else converted
    return finite_mono(mono), int(source_rate), {
        "input_dtype": str(data.dtype), "input_channels": int(data.shape[1]) if data.ndim == 2 else 1,
        "input_frames": int(len(data)), "source_rate_hz": int(source_rate),
        "channel_policy": "arithmetic mean in full-scale floating point before resampling",
        "source_saturation_fraction_before_downmix": clipped_fraction,
    }


def analyze_wav(path, valid_input_samples=None):
    samples, source_rate, metadata = decode_wav(str(path))
    if source_rate < RATE:
        raise ValueError("WAV rate is below the trained 8 kHz bandwidth")
    observed_count = len(samples) if valid_input_samples is None else valid_input_samples
    if isinstance(observed_count, bool) or not isinstance(observed_count, (int, np.integer)) or not 0 <= observed_count <= len(samples):
        raise ValueError("--valid-input-samples must be a valid prefix count in the WAV's native rate")
    if np.any(samples[observed_count:] != 0):
        raise ValueError("Declared input padding contains nonzero samples; refusing to discard them")
    observed = samples[:observed_count]
    container_8k = (len(samples) * RATE + source_rate - 1) // source_rate
    converted = resample_audio(observed, source_rate) if observed_count else np.array([], dtype=np.float64)
    valid_8k = len(converted)
    converted = np.pad(converted, (0, container_8k - valid_8k))
    if observed_count:
        spectrum = np.abs(np.fft.rfft(observed - np.mean(observed))) ** 2
        frequencies = np.fft.rfftfreq(len(observed), 1 / source_rate)
        high_fraction = float(np.sum(spectrum[frequencies > 4000]) / max(float(np.sum(spectrum)), 1e-30))
    else:
        high_fraction = None
    metadata.update(
        container_duration_seconds=len(samples) / source_rate,
        observed_duration_seconds=observed_count / source_rate,
        valid_input_samples=int(observed_count), resampled_container_samples=int(container_8k),
        resampled_observed_samples=int(valid_8k),
        resampling_duration_rounding_seconds=valid_8k / RATE - observed_count / source_rate,
        coverage_provenance="explicit_valid_prefix" if valid_input_samples is not None else "all_wav_samples_assumed_observed",
        source_observed_quality=signal_quality(observed), source_energy_above_4khz_fraction=high_fraction,
        observed_zero_tail_is_not_missing_duration=True,
    )
    return make_windows(converted, valid_samples=valid_8k), metadata


def load_dataset():
    manifest = SOURCE / "manifest.jsonl"
    expected = "12eef566e91552e380536581c930be7bcbd5f427bc0c832d12297bdc22dc73e6"
    if sha256(manifest) != expected:
        raise ValueError("The evidence manifest changed; this fixed experiment requires re-review")
    records = read_jsonl(manifest)
    if len(records) != 40 or Counter(r["originalLabel"] for r in records) != {"cough": 20, "non_cough": 20}:
        raise ValueError("Expected exactly 20 original cough and 20 original non_cough clips")
    hashes, rows, vectors = [], [], []
    for record in records:
        raw = (SOURCE / record["path"]).resolve()
        if not raw.is_relative_to((SOURCE / "raw" / "rdg-FP5LA9").resolve()):
            raise ValueError("Training input is not an original INRAE WAV")
        if record["groupId"] != UNKNOWN_GROUP or record["animalId"] is not None or record["recordingSessionId"] is not None:
            raise ValueError("Source grouping evidence changed")
        if record["clinicalVerified"] is not False or record["allowForDiseaseLabels"] is not False:
            raise ValueError("Research event evidence must not be upgraded into a clinical label")
        actual = sha256(raw)
        if actual != record["rawSha256"] or raw.stat().st_size != record["rawBytes"]:
            raise ValueError(f"Raw hash or size mismatch: {raw}")
        if hashlib.md5(raw.read_bytes()).hexdigest() != record["repositoryMd5"]:
            raise ValueError(f"Repository MD5 mismatch: {raw}")
        derived = (SOURCE / record["derived"]["path"]).resolve()
        if not derived.is_relative_to((SOURCE / "derived").resolve()) or sha256(derived) != record["derived"]["sha256"]:
            raise ValueError("An excluded derivative failed provenance verification")
        hashes.extend([
            {"path": relative(raw), "sha256": actual, "role": "original_training_wav"},
            {"path": relative(derived), "sha256": sha256(derived), "role": "excluded_padded_derivative_not_a_training_sample"},
        ])
        windows, quality = analyze_wav(raw)
        if quality["source_rate_hz"] != 44100 or quality["input_channels"] != 1 or quality["input_dtype"] != "int16":
            raise ValueError("Unexpected change to the verified original WAV format")
        if len(windows) != 1 or windows[0]["features"] is None:
            raise ValueError("This experiment requires exactly one scoreable original clip/window per file")
        if quality["resampled_observed_samples"] != record["derived"]["unpaddedSamples"]:
            raise ValueError("Resampled observed duration disagrees with evidence")
        window = windows[0]
        rows.append({
            "row_index": len(rows), "file_unit_id": record["fileUnitId"], "path": relative(raw),
            "raw_sha256": actual, "repository_md5": record["repositoryMd5"], "raw_bytes": raw.stat().st_size,
            "source_doi": record["sourceDoi"], "source_group_id": record["groupId"],
            "source_group_status": "source group unknown", "animal_id": None, "recording_session_id": None,
            "original_label": record["originalLabel"], "target": CLASSES.index(record["originalLabel"]),
            "label_provenance": record["labelProvenance"], "clinical_verified": False,
            "allow_for_disease_labels": False, "license": record["license"],
            "excluded_derived_path": relative(derived), "excluded_derived_sha256": record["derived"]["sha256"],
            "window_index": 0, "window_start_seconds": 0.0, "signal_quality_input": quality,
            "signal_quality_window": window["quality"], "quality_flags": window["quality_flags"],
        })
        vectors.append(window["features"])
    if len({r["file_unit_id"] for r in rows}) != 40 or len({r["raw_sha256"] for r in rows}) != 40:
        raise ValueError("Original file IDs and hashes must be unique")
    evidence = [ROOT / "docs" / "2026-10-25-audio-data-evidence.md", manifest,
                SOURCE / "source-records.json", SOURCE / "evidence" / "rdg-source-summary.json",
                SOURCE / "evidence" / "rdg-etalab-license.txt",
                SOURCE / "evidence" / "paper-data-and-preprocessing-excerpts.json",
                SOURCE / "evidence" / "dataverse-FP5LA9.json"]
    hashes.extend({"path": relative(path), "sha256": sha256(path), "role": "source_evidence"} for path in evidence)
    return rows, np.asarray(vectors), np.asarray([r["target"] for r in rows]), hashes


def new_pipeline():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000, tol=1e-8,
                                          fit_intercept=True, random_state=SEED)),
    ])


def export_model(pipeline, rows, indices):
    scaler, classifier = pipeline.named_steps["scaler"], pipeline.named_steps["classifier"]
    if classifier.classes_.tolist() != [0, 1] or int(classifier.n_iter_[0]) >= 2000:
        raise ValueError("Unexpected class order or nonconverged model")
    return {
        "schema_version": 1, "model_type": "standardized_binary_logistic_regression", **POLICY,
        "task": "author_reported_calf_cough_acoustic_event", "classes": CLASSES,
        "positive_class": "cough", "threshold": 0.5, "scores_calibrated_on_external_data": False,
        "feature_definition": FEATURE_DEFINITION, "feature_names": FEATURE_NAMES,
        "scaler_mean": scaler.mean_.tolist(), "scaler_scale": scaler.scale_.tolist(),
        "coefficients": classifier.coef_[0].tolist(), "intercept": float(classifier.intercept_[0]),
        "formula": "p(cough) = sigmoid(sum(((features - scaler_mean) / scaler_scale) * coefficients) + intercept)",
        "fit_parameters": {"C": 0.1, "regularization": "L2", "solver": "lbfgs", "max_iter": 2000,
                           "tol": 1e-8, "fit_intercept": True, "class_weight": None,
                           "scaler_population_variance_ddof": 0},
        "solver_iterations": int(classifier.n_iter_[0]), "training_file_count": len(indices),
        "training_file_ids": [rows[int(i)]["file_unit_id"] for i in indices],
        "training_raw_sha256": [rows[int(i)]["raw_sha256"] for i in indices],
        "training_script_sha256": sha256(Path(__file__)),
        "source_doi": "10.57745/FP5LA9", "source_group_id": UNKNOWN_GROUP,
        "attribution": "Mach et al. (2026), INRAE/ENVT, Animal 20(10):101928, doi:10.1016/j.animal.2026.101928",
        "license_scope": "research and education only pending resolution of Etalab 2.0/preprint scope conflict",
        "modifications": "Original WAV -> anti-aliased 8 kHz -> normalized 1 s shape features -> fixed L2 logistic regression",
    }


def load_model(path):
    model = read_json(path)
    if model.get("model_type") != "standardized_binary_logistic_regression" or model.get("classes") != CLASSES:
        raise ValueError("Incompatible model type or label order")
    if any(model.get(key) != value for key, value in POLICY.items()):
        raise ValueError("Model lacks the required research-only scope")
    if model.get("feature_definition") != FEATURE_DEFINITION or model.get("threshold") != 0.5:
        raise ValueError("Model feature definition or fixed decision threshold differs")
    portable_probability(model, np.zeros((1, len(FEATURE_NAMES))))
    return model


def metrics_for(truth, probabilities):
    from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                                 brier_score_loss, confusion_matrix, f1_score, log_loss,
                                 precision_recall_fscore_support, roc_auc_score)

    truth, probabilities = np.asarray(truth), np.asarray(probabilities)
    predicted = (probabilities >= 0.5).astype(int)
    precision, recall, f1, support = precision_recall_fscore_support(truth, predicted, labels=[0, 1], zero_division=0)
    return {
        "unit": "one original file, one vote", "interpretation": "exploratory file-held-out engineering diagnostic",
        "source_group_status": "source group unknown", "animal_independent_validation": False,
        "file_count": int(len(truth)), "threshold": 0.5, "class_order": CLASSES,
        "accuracy": float(accuracy_score(truth, predicted)),
        "balanced_accuracy": float(balanced_accuracy_score(truth, predicted)),
        "macro_f1": float(f1_score(truth, predicted, average="macro", zero_division=0)),
        "roc_auc": float(roc_auc_score(truth, probabilities)),
        "average_precision_cough": float(average_precision_score(truth, probabilities)),
        "brier_score_cough": float(brier_score_loss(truth, probabilities)),
        "log_loss": float(log_loss(truth, np.c_[1 - probabilities, probabilities], labels=[0, 1])),
        "confusion_matrix_true_rows_predicted_columns": confusion_matrix(truth, predicted, labels=[0, 1]).tolist(),
        "per_class": {label: {"precision": float(precision[i]), "recall": float(recall[i]),
                              "f1": float(f1[i]), "support": int(support[i])} for i, label in enumerate(CLASSES)},
    }


def prediction_rows(rows, indices, probabilities, fold):
    result = []
    for index, probability in zip(indices, probabilities, strict=True):
        row = rows[int(index)]
        predicted = int(probability >= 0.5)
        result.append({"row_index": int(index), "file_unit_id": row["file_unit_id"], "path": row["path"],
                       "raw_sha256": row["raw_sha256"], "fold": fold, "truth": row["original_label"],
                       "truth_target": row["target"], "predicted": CLASSES[predicted], "predicted_target": predicted,
                       "cough_score": float(probability), "source_group_id": UNKNOWN_GROUP,
                       "source_group_status": "source group unknown", "research_only": True,
                       "observed_duration_seconds": row["signal_quality_input"]["observed_duration_seconds"],
                       "quality_flags": row["quality_flags"]})
    return result


def write_checksums():
    entries = {path.resolve() for path in ARTIFACTS.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"}
    entries.update([Path(__file__).resolve(), REPORT.resolve()])
    provenance_path = ARTIFACTS / "provenance.json"
    if provenance_path.exists():
        entries.update((ROOT / row["path"]).resolve() for row in read_json(provenance_path)["files"])
    text = "".join(f"{sha256(path)}  {relative(path)}\n" for path in sorted(entries, key=relative))
    output_path(ARTIFACTS / "SHA256SUMS.txt").write_text(text, encoding="utf-8")


def train():
    import sklearn
    from threadpoolctl import threadpool_limits

    started = time.perf_counter()
    checks = run_unit_checks()
    if not checks["passed"]:
        raise ValueError(checks["details"])
    rows, features, labels, hashes = load_dataset()
    file_ids = np.asarray([row["file_unit_id"] for row in rows])
    folds = build_folds(labels, file_ids)
    assignments = np.full(len(rows), -1, dtype=int)
    oof = np.full(len(rows), np.nan)
    fold_records, predictions = [], []
    parity_errors = []
    save_json(ARTIFACTS / "feature_definition.json", {**POLICY, **FEATURE_DEFINITION})
    save_jsonl(ARTIFACTS / "input_manifest.jsonl", rows)
    save_json(ARTIFACTS / "provenance.json", {**POLICY, "files": hashes,
              "derivatives_used_for_training": False, "original_training_wavs": 40,
              "citation": "Mach et al. (2026), Animal 20(10):101928, doi:10.1016/j.animal.2026.101928",
              "source_doi": "10.57745/FP5LA9", "license": "Etalab Open License 2.0 in repository metadata",
              "license_caveat": "Preprint states research/educational purposes only; commercial authorization unresolved."})
    save_json(ARTIFACTS / "feature_unit_checks.json", checks)
    with threadpool_limits(limits=1):
        for fold_number, (train_indices, test_indices) in enumerate(folds, start=1):
            pipeline = new_pipeline().fit(features[train_indices], labels[train_indices])
            model = export_model(pipeline, rows, train_indices)
            model_path = ARTIFACTS / "fold_models" / f"fold_{fold_number}.json"
            save_json(model_path, model)
            probability = portable_probability(load_model(model_path), features[test_indices])
            error = float(np.max(np.abs(probability - pipeline.predict_proba(features[test_indices])[:, 1])))
            parity_errors.append(error)
            if error > 1e-12:
                raise ValueError("Portable JSON prediction disagrees with sklearn")
            oof[test_indices] = probability
            assignments[test_indices] = fold_number
            predictions.extend(prediction_rows(rows, test_indices, probability, fold_number))
            fold_records.append({
                "fold": fold_number, "train_indices": train_indices.tolist(), "test_indices": test_indices.tolist(),
                "train_file_ids": file_ids[train_indices].tolist(), "test_file_ids": file_ids[test_indices].tolist(),
                "train_file_count": len(train_indices), "test_file_count": len(test_indices),
                "file_id_overlap": [], "source_group_overlap": [UNKNOWN_GROUP],
                "source_group_status": "source group unknown", "animal_independent_validation": False,
                "model_path": relative(model_path), "metrics": metrics_for(labels[test_indices], probability),
                "sklearn_json_probability_max_absolute_error": error,
            })
        final_pipeline = new_pipeline().fit(features, labels)
        final_model = export_model(final_pipeline, rows, np.arange(len(rows)))
        save_json(ARTIFACTS / "model.json", final_model)
        final_probability = portable_probability(load_model(ARTIFACTS / "model.json"), features)
        final_error = float(np.max(np.abs(final_probability - final_pipeline.predict_proba(features)[:, 1])))
        if final_error > 1e-12 or not np.isfinite(oof).all() or np.any(assignments < 1):
            raise ValueError("Final model parity or out-of-fold coverage failed")
    predictions.sort(key=lambda row: row["row_index"])
    save_jsonl(ARTIFACTS / "oof_predictions.jsonl", predictions)
    save_jsonl(ARTIFACTS / "final_fit_predictions.jsonl",
               prediction_rows(rows, np.arange(len(rows)), final_probability, "resubstitution_not_validation"))
    save_json(ARTIFACTS / "fold_assignments.json", {**POLICY, "splitter": "StratifiedGroupKFold",
              "groups": "file_unit_id only; animal/session groups unknown", "seed": SEED, "folds": fold_records})
    np.savez_compressed(output_path(ARTIFACTS / "features.npz"), X=features, y=labels,
                        file_ids=file_ids, raw_sha256=np.asarray([row["raw_sha256"] for row in rows]),
                        fold=assignments, oof_cough_score=oof, feature_names=np.asarray(FEATURE_NAMES))
    metrics = metrics_for(labels, oof)
    report = {
        "schema_version": 1, **POLICY, "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": [sys.executable, *sys.argv], "training_script_sha256": sha256(Path(__file__)),
        "environment": {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
                        "numpy": np.__version__, "scipy": scipy.__version__, "sklearn": sklearn.__version__,
                        "device": "CPU", "numeric_thread_limit": 1},
        "dataset": {"original_files": len(rows), "unique_raw_hashes": len({r["raw_sha256"] for r in rows}),
                    "label_counts": dict(Counter(r["original_label"] for r in rows)),
                    "observed_duration_seconds": sum(r["signal_quality_input"]["observed_duration_seconds"] for r in rows),
                    "training_windows": len(rows), "excluded_padded_derivatives": 40,
                    "known_animal_ids": 0, "known_session_ids": 0, "conservative_source_group_count": 1,
                    "source_group_id": UNKNOWN_GROUP, "clinical_verified_files": 0},
        "experiment": {"seed": SEED, "folds": 5, "grouping_unit": "file_unit_id",
                       "source_group_status": "source group unknown", "parameter_searches": 0,
                       "candidate_models": 1, "parameters_fixed_before_results": True,
                       "scaler_fit": "training files of each fold only", "feature_count": len(FEATURE_NAMES),
                       "model_parameters": final_model["fit_parameters"], "threshold": 0.5,
                       "production_gate_eligible": False, "animal_independent_validation": False},
        "exploratory_file_oof_metrics": metrics, "fold_metrics": [fold["metrics"] for fold in fold_records],
        "json_parity_max_absolute_error": max([final_error, *parity_errors]),
        "unit_check_count": checks["tests_run"], "final_model_fit_files": 40,
        "final_training_scores_are_not_validation": True, "runtime_seconds": time.perf_counter() - started,
        "limitations": [
            "Source group unknown: file holdout cannot exclude animal, session or parent-recording leakage.",
            "Only 40 selected author-annotated event clips; no independent farm, animal or live continuous recording test.",
            "One cough file is only 0.387981859 seconds; duration is metadata, but residual duration confounding is possible.",
            "No disease labels; non_cough does not mean healthy; no BRD/FMD mapping.",
            "8 kHz loses energy above 4 kHz; microphone gain, noise, quantization and boundary alignment remain unvalidated.",
            "Logistic scores are not externally calibrated; no production threshold or clinical performance claim.",
            "Repository Etalab 2.0 and preprint research/education wording conflict; use research_only.",
        ],
    }
    save_json(ARTIFACTS / "training_report.json", report)
    write_checksums()
    return {"artifacts": str(ARTIFACTS), "research_only": True,
            "source_group_status": "source group unknown", "metrics": metrics,
            "unit_checks_passed": checks["tests_run"], "runtime_seconds": report["runtime_seconds"]}


def predict(wav_path, model_path, valid_input_samples=None):
    model = load_model(model_path)
    windows, metadata = analyze_wav(wav_path, valid_input_samples=valid_input_samples)
    for window in windows:
        vector = window.pop("features")
        if vector is None:
            window.update(cough_score=None, predicted_event=None)
        else:
            probability = float(portable_probability(model, vector)[0])
            window.update(cough_score=probability, predicted_event=CLASSES[int(probability >= 0.5)],
                          features=dict(zip(FEATURE_NAMES, vector.tolist(), strict=True)))
    return {
        "schema_version": 1, **POLICY, "wav_path": str(Path(wav_path).resolve()), "wav_sha256": sha256(wav_path),
        "model_path": str(Path(model_path).resolve()), "model_sha256": sha256(model_path),
        "input": metadata, "window_samples": WINDOW, "sample_rate_hz": RATE, "windows": windows,
        "score_interpretation": "Uncalibrated cough acoustic-event research score, not a disease probability.",
        "coverage_note": "Zeros alone cannot identify missing audio. Known tail padding requires --valid-input-samples.",
        "aggregate_event": None,
        "aggregation_note": "Per-window results only; a two-second aggregation rule has not been validated.",
    }


def verify():
    from threadpoolctl import threadpool_limits

    checks = run_unit_checks()
    if not checks["passed"]:
        raise ValueError(checks["details"])
    report = read_json(ARTIFACTS / "training_report.json")
    if sha256(Path(__file__)) != report["training_script_sha256"]:
        raise ValueError("Script changed after training; rerun the fixed training command")
    rows, features, labels, hashes = load_dataset()
    if rows != read_jsonl(ARTIFACTS / "input_manifest.jsonl"):
        raise ValueError("Regenerated input manifest differs")
    if hashes != read_json(ARTIFACTS / "provenance.json")["files"]:
        raise ValueError("Source evidence or input hashes changed")
    if read_json(ARTIFACTS / "feature_definition.json") != {**POLICY, **FEATURE_DEFINITION}:
        raise ValueError("Saved feature definition differs from executable extraction")
    with np.load(ARTIFACTS / "features.npz", allow_pickle=False) as stored:
        np.testing.assert_array_equal(stored["X"], features)
        np.testing.assert_array_equal(stored["y"], labels)
        np.testing.assert_array_equal(stored["feature_names"], FEATURE_NAMES)
        np.testing.assert_array_equal(stored["file_ids"], [r["file_unit_id"] for r in rows])
        np.testing.assert_array_equal(stored["raw_sha256"], [r["raw_sha256"] for r in rows])
        saved_oof, saved_folds = stored["oof_cough_score"].copy(), stored["fold"].copy()
    saved_predictions = read_jsonl(ARTIFACTS / "oof_predictions.jsonl")
    if len(saved_predictions) != 40 or len({r["file_unit_id"] for r in saved_predictions}) != 40:
        raise ValueError("Saved OOF predictions do not cover the original files exactly once")
    assignment = read_json(ARTIFACTS / "fold_assignments.json")
    file_ids = np.asarray([r["file_unit_id"] for r in rows])
    expected_folds = build_folds(labels, file_ids)
    if len(assignment["folds"]) != 5:
        raise ValueError("Expected five saved folds")
    recomputed = np.full(40, np.nan)
    parity_errors = []
    with threadpool_limits(limits=1):
        for fold, (train_indices, test_indices) in zip(assignment["folds"], expected_folds, strict=True):
            if fold["train_indices"] != train_indices.tolist() or fold["test_indices"] != test_indices.tolist():
                raise ValueError("Fixed fold assignment changed")
            if fold["train_file_ids"] != file_ids[train_indices].tolist() or fold["test_file_ids"] != file_ids[test_indices].tolist():
                raise ValueError("Saved file membership differs from fold indices")
            if set(file_ids[train_indices]) & set(file_ids[test_indices]):
                raise ValueError("File leakage found")
            if {rows[int(i)]["raw_sha256"] for i in train_indices} & {rows[int(i)]["raw_sha256"] for i in test_indices}:
                raise ValueError("Exact original-file duplicate crosses a fold")
            np.testing.assert_array_equal(saved_folds[test_indices], np.full(len(test_indices), fold["fold"]))
            saved_model = load_model(ROOT / fold["model_path"])
            pipeline = new_pipeline().fit(features[train_indices], labels[train_indices])
            expected_model = export_model(pipeline, rows, train_indices)
            if saved_model["training_file_ids"] != file_ids[train_indices].tolist():
                raise ValueError("Fold model training membership differs")
            for field in ("scaler_mean", "scaler_scale", "coefficients", "intercept"):
                np.testing.assert_allclose(saved_model[field], expected_model[field], atol=1e-12, rtol=1e-12)
            probabilities = portable_probability(saved_model, features[test_indices])
            parity_errors.append(float(np.max(np.abs(probabilities - pipeline.predict_proba(features[test_indices])[:, 1]))))
            recomputed[test_indices] = probabilities
            if metrics_for(labels[test_indices], probabilities) != fold["metrics"]:
                raise ValueError("Saved per-fold metrics do not reproduce")
        final_model = load_model(ARTIFACTS / "model.json")
        final_pipeline = new_pipeline().fit(features, labels)
        final_probabilities = portable_probability(final_model, features)
        parity_errors.append(float(np.max(np.abs(final_probabilities - final_pipeline.predict_proba(features)[:, 1]))))
        if final_model["training_file_ids"] != file_ids.tolist():
            raise ValueError("Final model did not train on the 40 original files")
    if max(parity_errors) > 1e-12:
        raise ValueError("Saved models disagree with the fixed sklearn refits")
    np.testing.assert_allclose(recomputed, saved_oof, atol=1e-14, rtol=0)
    expected_predictions = []
    for fold, (_, test_indices) in zip(assignment["folds"], expected_folds, strict=True):
        expected_predictions.extend(prediction_rows(rows, test_indices, recomputed[test_indices], fold["fold"]))
    expected_predictions.sort(key=lambda row: row["row_index"])
    if expected_predictions != saved_predictions:
        raise ValueError("Saved OOF predictions differ from saved-model inference")
    if prediction_rows(rows, np.arange(40), final_probabilities, "resubstitution_not_validation") != read_jsonl(ARTIFACTS / "final_fit_predictions.jsonl"):
        raise ValueError("Final-model diagnostic predictions do not reproduce")
    if metrics_for(labels, recomputed) != report["exploratory_file_oof_metrics"]:
        raise ValueError("Aggregate exploratory metrics do not reproduce")
    example = next(row for row in rows if Path(row["path"]).name == "cough_001.wav")
    derived_path = ROOT / example["excluded_derived_path"]
    known = predict(derived_path, ARTIFACTS / "model.json", valid_input_samples=8000)
    unknown = predict(derived_path, ARTIFACTS / "model.json")
    if len(known["windows"]) != 2 or [w["quality"]["observed_samples"] for w in known["windows"]] != [8000, 0]:
        raise ValueError("Known padded two-second container has incorrect observed duration")
    if [w["quality"]["observed_samples"] for w in unknown["windows"]] != [8000, 8000]:
        raise ValueError("Unspecified coverage must preserve all WAV duration")
    if known["windows"][1]["cough_score"] is not None or unknown["windows"][1]["status"] != "abstain_silence":
        raise ValueError("Padding or silent window generated an acoustic event decision")
    short = next(row for row in rows if Path(row["path"]).name == "cough_012.wav")
    short_known = predict(ROOT / short["excluded_derived_path"], ARTIFACTS / "model.json", valid_input_samples=3104)
    if [w["quality"]["observed_samples"] for w in short_known["windows"]] != [3104, 0]:
        raise ValueError("Short clip's 3104 resampled samples were confused with two seconds")
    result = {
        **POLICY, "verified_at_utc": datetime.now(timezone.utc).isoformat(), "passed": True,
        "original_wav_sha256_matches": 40, "original_repository_md5_matches": 40,
        "excluded_derivative_sha256_matches": 40, "source_evidence_files_hashed": len(hashes) - 80,
        "feature_rows_regenerated_exactly": 40, "oof_file_predictions_reproduced": 40,
        "final_fit_file_predictions_reproduced": 40, "saved_models_refit_and_checked": 6,
        "train_only_scalers_verified": 5, "file_overlap_per_fold": [0] * 5,
        "unknown_source_group_overlap_per_fold": [1] * 5,
        "all_fold_and_aggregate_metrics_reproduced": True,
        "sklearn_json_max_probability_absolute_error": max(parity_errors),
        "feature_unit_checks_passed": checks["tests_run"],
        "two_second_known_padding_observed_samples": [8000, 0],
        "two_second_unknown_coverage_observed_samples": [8000, 8000],
        "short_clip_known_padding_observed_samples": [3104, 0],
        "note": "Source group unknown; verified engineering reproducibility is not independent animal validation.",
    }
    save_json(ARTIFACTS / "feature_unit_checks.json", checks)
    save_json(ARTIFACTS / "verification.json", result)
    write_checksums()
    lines = (ARTIFACTS / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected_hash, name = line.split("  ", 1)
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or sha256(path) != expected_hash:
            raise ValueError(f"Output checksum verification failed for {name}")
    return {**result, "checksum_entries_verified": len(lines)}


class FeatureContractTests(unittest.TestCase):
    """Independent signal fixtures catch padding, aliasing and time-loss bugs."""

    def tone(self, hz, count=8000, rate=8000):
        return 0.1 * np.sin(2 * np.pi * hz * np.arange(count) / rate)

    def test_observed_silence_keeps_its_second_window(self):
        windows = make_windows(np.r_[self.tone(1000), np.zeros(8000)])
        self.assertIsNotNone(windows, "window extraction is not implemented")
        self.assertEqual(len(windows), 2)
        self.assertEqual([w["start_seconds"] for w in windows], [0.0, 1.0])
        self.assertEqual([w["quality"]["observed_samples"] for w in windows], [8000, 8000])
        self.assertEqual(windows[1]["status"], "abstain_silence")
        self.assertIsNone(windows[1]["features"])

    def test_known_tail_padding_is_not_observed_duration(self):
        windows = make_windows(np.r_[self.tone(1000), np.zeros(8000)], valid_samples=8000)
        self.assertIsNotNone(windows, "window extraction is not implemented")
        self.assertEqual(len(windows), 2)
        self.assertEqual([w["quality"]["observed_samples"] for w in windows], [8000, 0])
        self.assertEqual(windows[1]["quality"]["known_input_padding_samples"], 8000)
        self.assertEqual(windows[1]["status"], "abstain_no_observed_samples")
        self.assertIsNone(windows[1]["features"])

    def test_partial_tail_keeps_time_and_separates_algorithm_padding(self):
        windows = make_windows(self.tone(1000, count=10000))
        self.assertIsNotNone(windows, "window extraction is not implemented")
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[1]["start_seconds"], 1.0)
        self.assertEqual(windows[1]["quality"]["observed_samples"], 2000)
        self.assertEqual(windows[1]["quality"]["algorithm_padding_samples"], 6000)
        self.assertEqual(windows[1]["quality"]["observed_duration_seconds"], 0.25)

    def test_padding_does_not_dilute_short_clip_features(self):
        tone = self.tone(1000, count=3104)
        raw = make_windows(tone)
        padded = make_windows(np.pad(tone, (0, 12896)), valid_samples=3104)
        self.assertIsNotNone(raw, "window extraction is not implemented")
        self.assertIsNotNone(padded, "window extraction is not implemented")
        self.assertEqual(raw[0]["quality"]["algorithm_padding_samples"], 4896)
        self.assertEqual(padded[0]["quality"]["known_input_padding_samples"], 4896)
        self.assertEqual(padded[1]["quality"]["observed_samples"], 0)
        np.testing.assert_allclose(raw[0]["features"], padded[0]["features"], atol=1e-12)

    def test_two_subwindows_keep_distinct_frequency_and_order(self):
        windows = make_windows(np.r_[self.tone(1000), self.tone(2000)])
        self.assertIsNotNone(windows, "window extraction is not implemented")
        self.assertAlmostEqual(float(windows[0]["features"][4]), 0.25, delta=0.015)
        self.assertAlmostEqual(float(windows[1]["features"][4]), 0.50, delta=0.015)

    def test_gain_and_dc_normalization_preserve_shape(self):
        x = self.tone(700) + 0.3 * self.tone(1700)
        a, b = make_windows(x), make_windows(x * 0.2 + 0.1)
        self.assertIsNotNone(a, "window extraction is not implemented")
        self.assertIsNotNone(b, "window extraction is not implemented")
        np.testing.assert_allclose(a[0]["features"], b[0]["features"], atol=1e-10)
        self.assertAlmostEqual(b[0]["quality"]["dc_offset_full_scale"], 0.1, places=10)
        self.assertLess(b[0]["quality"]["rms_ac_full_scale"], a[0]["quality"]["rms_ac_full_scale"])

    def test_antialiasing_suppresses_out_of_band_tone(self):
        high = resample_audio(self.tone(6000, count=44100, rate=44100), 44100)
        low = resample_audio(self.tone(1000, count=44100, rate=44100), 44100)
        self.assertIsNotNone(high, "anti-aliased resampling is not implemented")
        self.assertIsNotNone(low, "anti-aliased resampling is not implemented")
        self.assertEqual(len(high), 8000)
        attenuation = 20 * np.log10(np.linalg.norm(high[128:-128]) / np.linalg.norm(low[128:-128]))
        self.assertLess(float(attenuation), -40.0)

    def test_empty_and_nonfinite_audio_are_rejected(self):
        for samples in (np.array([]), np.array([np.nan]), np.array([np.inf])):
            with self.subTest(samples=str(samples)), self.assertRaises(ValueError):
                make_windows(samples)

    def test_invalid_observed_sample_count_is_rejected(self):
        for valid in (-1, 8001, 3.5):
            with self.subTest(valid=valid), self.assertRaises(ValueError):
                make_windows(self.tone(1000), valid_samples=valid)

    def test_missing_high_frequencies_are_not_recreated_by_upsampling(self):
        with self.assertRaises(ValueError):
            resample_audio(self.tone(1000, count=4000, rate=4000), 4000)

    def test_portable_logistic_formula_uses_saved_scaler(self):
        model = {"scaler_mean": [1.0, 2.0], "scaler_scale": [2.0, 4.0],
                 "coefficients": [0.5, -1.0], "intercept": 0.25}
        result = portable_probability(model, np.array([[3.0, 6.0]]))
        self.assertIsNotNone(result, "portable inference is not implemented")
        self.assertAlmostEqual(float(result[0]), 0.4378234991142019, places=14)

    def test_all_views_of_a_file_stay_in_one_fold(self):
        ids = np.repeat([f"fixture-{i}" for i in range(20)], 2)
        labels = np.repeat([0] * 10 + [1] * 10, 2)
        folds = build_folds(labels, ids)
        self.assertIsNotNone(folds, "file-level folds are not implemented")
        seen = np.zeros(40, dtype=int)
        for train, test in folds:
            self.assertFalse(set(ids[train]) & set(ids[test]))
            seen[test] += 1
        np.testing.assert_array_equal(seen, np.ones(40, dtype=int))

    def test_wav_integer_and_float_full_scale_conversion(self):
        fixtures = [
            (np.array([0, 128, 255], dtype=np.uint8), [-1.0, 0.0, 0.9921875]),
            (np.array([-32768, 0, 32767], dtype=np.int16), [-1.0, 0.0, 0.999969482421875]),
            (np.array([-0.5, 0.0, 0.5], dtype=np.float32), [-0.5, 0.0, 0.5]),
        ]
        for values, expected in fixtures:
            with self.subTest(dtype=str(values.dtype)):
                stream = io.BytesIO()
                wavfile.write(stream, 8000, values)
                stream.seek(0)
                samples, rate, _ = decode_wav(stream)
                np.testing.assert_array_equal(samples, expected)
                self.assertEqual(rate, 8000)

    def test_stereo_downmix_occurs_in_float_without_integer_overflow(self):
        stream = io.BytesIO()
        wavfile.write(stream, 8000, np.array([[16384, 0], [-16384, 0]], dtype=np.int16))
        stream.seek(0)
        samples, _, metadata = decode_wav(stream)
        np.testing.assert_array_equal(samples, [0.25, -0.25])
        self.assertEqual(metadata["input_channels"], 2)

    def test_metadata_cannot_discard_nonzero_tail(self):
        with self.assertRaises(ValueError):
            make_windows(np.r_[self.tone(1000), self.tone(2000)], valid_samples=8000)

    def test_tiny_observed_tail_is_preserved_but_not_scored(self):
        windows = make_windows(self.tone(1000, count=8300))
        self.assertEqual(len(windows), 2)
        self.assertEqual(windows[1]["quality"]["observed_samples"], 300)
        self.assertEqual(windows[1]["status"], "abstain_too_short")
        self.assertIsNone(windows[1]["features"])

    def test_all_zero_input_has_duration_and_no_decision(self):
        windows = make_windows(np.zeros(16000))
        self.assertEqual([w["quality"]["observed_samples"] for w in windows], [8000, 8000])
        self.assertTrue(all(w["features"] is None and w["status"] == "abstain_silence" for w in windows))


def run_unit_checks():
    stream = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(FeatureContractTests)
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    return {"tests_run": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "passed": result.wasSuccessful(),
            "details": stream.getvalue()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("self-test", help="Run signal, coverage and portable inference contract checks")
    commands.add_parser("train", help="Run the fixed 40-original-file CPU research experiment")
    commands.add_parser("verify", help="Recompute hashes, features, fold models and actual saved metrics")
    prediction = commands.add_parser("predict", help="Score each 1 s subwindow of a new WAV; JSON output")
    prediction.add_argument("wav", type=Path)
    prediction.add_argument("--model", type=Path, default=ARTIFACTS / "model.json")
    prediction.add_argument("--valid-input-samples", type=int,
                            help="Known observed prefix count at the WAV native sample rate; tail must be exact zeros")
    prediction.add_argument("--output", type=Path, help=f"Optional JSON destination under {ARTIFACTS}")
    args = parser.parse_args()
    if args.command == "self-test":
        result = run_unit_checks()
    elif args.command == "train":
        result = train()
    elif args.command == "verify":
        result = verify()
    else:
        result = predict(args.wav, args.model, args.valid_input_samples)
        if args.output:
            save_json(args.output, result)
            write_checksums()
    print(json.dumps(result, indent=2, ensure_ascii=True, allow_nan=False))
    return 1 if result.get("passed") is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
