#!/usr/bin/env python3
"""Bounded pointwise posture experiment on the exact historical raw split."""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "4"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = ROOT / "\u725b\u884c\u4e3a\u8bc6\u522b\u6570\u636e\u96c6"
LEGACY = DATA_ROOT / "esp32_motion_model"
DATASET = DATA_ROOT / "free_datasets/cattle_classification_github_andssuu/data/dataset_6.csv"
FROZEN_HEADER = ROOT / "\u786c\u4ef6\u4ee3\u7801/\u725b\u8eab\u8282\u70b9/include/cattle_posture_model.h"
OUTPUT = DATA_ROOT / "esp32_posture_refinement_20261026"
FEATURES = ("ax_g", "ay_g", "az_g", "norm_g", "abs_ax_g", "abs_ay_g", "abs_az_g",
            "tilt_x_rad", "tilt_y_rad", "tilt_z_rad")
CLASSES = ("lying", "standing")
GRID = [
    {"n_estimators": 32, "max_depth": 10, "max_leaf_nodes": 64, "min_samples_leaf": 8, "max_features": "sqrt"},
    {"n_estimators": 48, "max_depth": 12, "max_leaf_nodes": 64, "min_samples_leaf": 4, "max_features": "sqrt"},
    {"n_estimators": 32, "max_depth": 12, "max_leaf_nodes": 128, "min_samples_leaf": 4, "max_features": 1.0},
    {"n_estimators": 48, "max_depth": 14, "max_leaf_nodes": 128, "min_samples_leaf": 4, "max_features": 1.0},
]


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def protected():
    paths = [DATASET, LEGACY / "train_export_model.py", LEGACY / "posture_binary_accel_training_report.json"]
    for folder in (FROZEN_HEADER.parent, ROOT / "\u786c\u4ef6\u4ee3\u7801/\u73b0\u6709\u786c\u4ef6\u6f14\u793a\u8282\u70b9/include"):
        paths.extend(p for p in folder.glob("cattle*model.h"))
    return {str(path): sha(path) for path in sorted(set(paths))}


def reconstruct_split():
    spec = importlib.util.spec_from_file_location("posture_legacy_readonly", LEGACY / "train_export_model.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.LABELS = module.BINARY_POSTURE_LABELS
    module.SOURCE_LABELS = module.BINARY_POSTURE_SOURCE_LABELS
    xyz, y, groups = module.load_dataset(DATASET)
    train, test = module.split_by_contiguous_run(y, groups, .2, 20260719)
    return module, xyz, y, groups, train, test


def extract_features(xyz):
    xyz = np.asarray(xyz, dtype=np.float32)
    if xyz.ndim != 2 or xyz.shape[1] != 3 or not np.isfinite(xyz).all():
        raise ValueError("Expected finite pointwise XYZ in legacy g units")
    v = xyz.astype(np.float64)
    x, y, z = v.T
    norm = np.sqrt(x*x + y*y + z*z)
    return np.column_stack((v, norm, np.abs(v), np.arctan2(x, np.sqrt(y*y+z*z)),
                            np.arctan2(y, np.sqrt(x*x+z*z)), np.arctan2(z, np.sqrt(x*x+y*y)))).astype(np.float32)


def inner_folds(y, groups, train):
    splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=20261026)
    return [(train[fit], train[val]) for fit, val in splitter.split(np.zeros(len(train)), y[train], groups[train])]


def metrics(y, prediction):
    report = classification_report(y, prediction, labels=[0, 1], target_names=CLASSES,
                                   output_dict=True, zero_division=0)
    return {"accuracy": float(accuracy_score(y, prediction)),
            "balanced_accuracy": float(np.mean([report[c]["recall"] for c in CLASSES])),
            "macro_f1": float(f1_score(y, prediction, average="macro", zero_division=0)),
            "classes": {c: {"precision": report[c]["precision"], "recall": report[c]["recall"],
                             "f1": report[c]["f1-score"], "support": int(report[c]["support"])} for c in CLASSES},
            "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist()}


BASELINE_RUNNER = r'''#include <stdio.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "baseline_frozen.h"
int main() {
  float xyz[3];
#ifdef _WIN32
  _setmode(_fileno(stdin), _O_BINARY); _setmode(_fileno(stdout), _O_BINARY);
#endif
  while (fread(xyz, sizeof(float), 3, stdin) == 3) {
    unsigned char label = cattle_posture_model::predict(xyz);
    if (fwrite(&label, 1, 1, stdout) != 1) return 2;
  }
  return 0;
}'''


def baseline_predictions(output, xyz):
    (output / "baseline_frozen.h").write_bytes(FROZEN_HEADER.read_bytes())
    source = output / "baseline_runner.cpp"
    source.write_text(BASELINE_RUNNER, encoding="ascii")
    binary = output / "baseline_runner.exe"
    subprocess.run([shutil.which("g++"), "-std=c++11", "-O2", "-Wall", "-Wextra", "-Werror",
                    str(source), "-o", str(binary)], check=True, capture_output=True, timeout=60)
    result = subprocess.run([str(binary)], input=np.asarray(xyz, dtype="<f4").tobytes(), capture_output=True, check=True, timeout=30)
    return np.frombuffer(result.stdout, dtype=np.uint8)


def train(output):
    if (output / "heldout_evaluation.json").exists():
        raise RuntimeError("Heldout result already exists; training is frozen. Use --export-only or --verify-only.")
    started = time.perf_counter()
    before = protected()
    write_json(output / "protected_inputs_before.json", before)
    write_json(output / "fixed_training_plan.json", {"feature_names": FEATURES, "grid": GRID,
        "old_split": {"test_fraction": .2, "seed": 20260719},
        "selection": "5-fold StratifiedGroupKFold inside exact old training rows; mean fold macro F1",
        "candidate_heldout_evaluations_allowed": 1, "compute_limit_seconds": 300,
        "seed": 20261026, "max_cpu_threads": 4, "clinical_lameness_enabled": False})
    module, xyz, y, groups, training, test = reconstruct_split()
    frozen = json.loads((LEGACY / "posture_binary_accel_training_report.json").read_text(encoding="utf-8"))
    expected_support = [frozen["metrics"]["classes"][c]["support"] for c in CLASSES]
    if (len(training), len(test)) != (frozen["train_rows"], frozen["test_rows"]) or np.bincount(y[test]).tolist() != expected_support:
        raise RuntimeError("BLOCKED: historical split counts cannot be reconstructed")
    baseline = baseline_predictions(output, xyz[test])
    baseline_metrics = metrics(y[test], baseline)
    if baseline_metrics["confusion_matrix"] != frozen["metrics"]["confusion_matrix"]:
        write_json(output / "baseline_mismatch.json", {"actual": baseline_metrics, "reported": frozen["metrics"]})
        raise RuntimeError("BLOCKED: frozen binary header does not reproduce original report confusion matrix")
    print(f"Exact baseline reproduced: train={len(training)} ({len(np.unique(groups[training]))} groups), test={len(test)} ({len(np.unique(groups[test]))} groups), confusion={baseline_metrics['confusion_matrix']}", flush=True)
    write_json(output / "baseline_reconstruction.json", {"dataset_sha256": sha(DATASET),
        "legacy_script_sha256": sha(LEGACY / "train_export_model.py"), "frozen_report_sha256": sha(LEGACY / "posture_binary_accel_training_report.json"),
        "frozen_header_sha256": sha(FROZEN_HEADER), "train_rows": len(training), "test_rows": len(test),
        "train_groups": len(np.unique(groups[training])), "test_groups": len(np.unique(groups[test])),
        "train_indices_int64_le_sha256": hashlib.sha256(training.astype("<i8").tobytes()).hexdigest(),
        "test_indices_int64_le_sha256": hashlib.sha256(test.astype("<i8").tobytes()).hexdigest(),
        "baseline_metrics": baseline_metrics, "frozen_confusion_reproduced_exactly": True})
    features = extract_features(xyz)
    folds = inner_folds(y, groups, training)
    scores = []
    for config in GRID:
        results = []
        for fit, val in folds:
            if set(groups[fit]) & set(groups[val]) or set(fit) & set(test) or set(val) & set(test):
                raise AssertionError("Group/test leakage")
            if time.perf_counter() - started > 300:
                raise RuntimeError("Bounded compute budget reached before test evaluation")
            forest = RandomForestClassifier(**config, class_weight="balanced_subsample", random_state=20261026, n_jobs=4)
            forest.fit(features[fit], y[fit])
            results.append(metrics(y[val], forest.predict(features[val])))
        score = float(np.mean([r["macro_f1"] for r in results]))
        scores.append({"configuration": config, "mean_group_cv_macro_f1": score, "fold_metrics": results})
        print(f"Train-only CV {config}: macro_f1={score:.6f}", flush=True)
    best = max(range(len(scores)), key=lambda i: scores[i]["mean_group_cv_macro_f1"])
    selected = scores[best]["configuration"]
    write_json(output / "train_only_selection.json", {"candidates": scores, "selected": selected,
               "heldout_used_for_selection": False})
    forest = RandomForestClassifier(**selected, class_weight="balanced_subsample", random_state=20261026, n_jobs=4)
    forest.fit(features[training], y[training])
    joblib.dump(forest, output / "candidate_model.joblib")
    probabilities = forest.predict_proba(features[test])
    prediction = probabilities.argmax(1)
    candidate_metrics = metrics(y[test], prediction)
    np.savez_compressed(output / "evaluation_cache.npz", xyz_test=xyz[test], y_test=y[test], features_test=features[test],
                        probabilities=probabilities, baseline=baseline, train_indices=training, test_indices=test)
    report = {"status": "trained_once_export_pending", "candidate": "posture-refinement-20261026-v1",
        "source_url": "https://github.com/andssuu/cattle_classification", "feature_names": FEATURES,
        "dataset_rows": len(y), "train_rows": len(training), "test_rows": len(test),
        "train_groups": len(np.unique(groups[training])), "test_groups": len(np.unique(groups[test])),
        "selected_configuration": selected, "candidate_metrics": candidate_metrics, "baseline_metrics": baseline_metrics,
        "candidate_heldout_evaluations": 1, "heldout_used_for_hyperparameters": False,
        "accuracy_improved": candidate_metrics["accuracy"] > baseline_metrics["accuracy"],
        "macro_f1_improved": candidate_metrics["macro_f1"] > baseline_metrics["macro_f1"],
        "original_binary_mapping_preserved": module.BINARY_POSTURE_SOURCE_LABELS,
        "limitations": ["contiguous row-label-run groups only; animal and session IDs unknown; not animal-independent validation",
            "no verified timestamps or sample rate; pointwise only, no temporal data created",
            "grazing/walking -> standing is the historical operational task mapping, not new independently verified posture truth",
            "16,384 LSB/g scale and sensor mounting provenance unverified; no field validation",
            "public behavior labels are not clinical lameness labels; no learned three-position fusion"],
        "production_eligible": False, "clinical_lameness_enabled": False,
        "execution": {"cpu_only": True, "max_threads": 4, "elapsed_seconds": time.perf_counter() - started,
                      "python": sys.version, "numpy": np.__version__, "sklearn": __import__("sklearn").__version__}}
    write_json(output / "heldout_evaluation.json", report)
    fold_id = np.full(len(y), -1, dtype=np.int8)
    for i, (_, val) in enumerate(folds): fold_id[val] = i
    with (output / "raw_split.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["raw_row_0based", "original_label_run", "legacy_binary_label", "role", "inner_validation_fold"])
        test_set = set(test.tolist())
        writer.writerows((i, int(groups[i]), CLASSES[y[i]], "test" if i in test_set else "train", int(fold_id[i])) for i in range(len(y)))
    if protected() != before: raise AssertionError("Protected originals changed")
    print(json.dumps({"candidate": candidate_metrics, "frozen_baseline": baseline_metrics,
                      "elapsed_seconds": report["execution"]["elapsed_seconds"]}, indent=2), flush=True)
    (output / "training_script_snapshot.py").write_bytes(Path(__file__).read_bytes())


FEATURE_HEADER = r'''/* Research experiment only. Pointwise legacy units; no temporal/clinical model. */
#ifndef POSTURE_REFINEMENT_FEATURES_20261026_H
#define POSTURE_REFINEMENT_FEATURES_20261026_H
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#define POSTURE_REFINEMENT_FEATURE_COUNT 10
#define POSTURE_REFINEMENT_CLASS_COUNT 2
#define POSTURE_REFINEMENT_PRODUCTION_ELIGIBLE 0
#define POSTURE_REFINEMENT_CLINICAL_LAMENESS_ENABLED 0
static inline int posture_refinement_extract_features(const float *xyz, float *out) {
  double x, y, z;
  if (!xyz || !out || !isfinite(xyz[0]) || !isfinite(xyz[1]) || !isfinite(xyz[2])) return 0;
  x=xyz[0]; y=xyz[1]; z=xyz[2];
  out[0]=(float)x; out[1]=(float)y; out[2]=(float)z;
  out[3]=(float)sqrt(x*x+y*y+z*z);
  out[4]=(float)fabs(x); out[5]=(float)fabs(y); out[6]=(float)fabs(z);
  out[7]=(float)atan2(x,sqrt(y*y+z*z));
  out[8]=(float)atan2(y,sqrt(x*x+z*z));
  out[9]=(float)atan2(z,sqrt(x*x+y*y));
  return 1;
}
#endif
'''


def c_float(value):
    text = format(float(np.float32(value)), ".9g")
    if "." not in text and "e" not in text: text += ".0"
    return text + "f"


def export_model(output, forest):
    nodes, leaves, roots = [], [], []
    for estimator in forest.estimators_:
        tree = estimator.tree_
        offset = len(nodes)
        roots.append(offset)
        for i in range(tree.node_count):
            if tree.children_left[i] < 0:
                probabilities = tree.value[i, 0]
                nodes.append({"feature": -1, "threshold": 0.0, "left": 0, "right": 0, "leaf": len(leaves)})
                leaves.append((probabilities / probabilities.sum()).astype(np.float32).tolist())
            else:
                threshold = np.float32(tree.threshold[i])
                if float(threshold) > tree.threshold[i]: threshold = np.nextafter(threshold, np.float32(-np.inf))
                nodes.append({"feature": int(tree.feature[i]), "threshold": float(threshold),
                              "left": offset+int(tree.children_left[i]), "right": offset+int(tree.children_right[i]), "leaf": 0})
    if len(nodes) >= 65536 or len(leaves) >= 65536: raise ValueError("Model exceeds 16-bit node index")
    encoded = {"version": "posture-refinement-20261026-v1", "classes": CLASSES, "features": FEATURES,
               "roots": roots, "nodes": nodes, "leaf_probabilities": leaves,
               "production_eligible": False, "clinical_lameness_enabled": False, "recommended_for_integration": False}
    write_json(output / "candidate_model.json", encoded)
    (output / "posture_refinement_features.h").write_text(FEATURE_HEADER, encoding="ascii")
    lines = ["/* Fixed research candidate. Heldout result is inferior to frozen baseline; retain original. */",
             "#ifndef POSTURE_REFINEMENT_CANDIDATE_20261026_H", "#define POSTURE_REFINEMENT_CANDIDATE_20261026_H",
             '#include "posture_refinement_features.h"',
             '#define POSTURE_REFINEMENT_MODEL_VERSION "posture-refinement-20261026-v1"',
             f'#define POSTURE_REFINEMENT_TREE_COUNT {len(roots)}',
             'typedef struct { float threshold; uint16_t left, right, leaf; int8_t feature; } PostureRefinementNode;',
             'typedef struct { uint8_t label; float confidence; uint8_t rejected; float probabilities[2]; } PostureRefinementPrediction;',
             'static const char *const posture_refinement_class_names[2] = {"lying", "standing"};',
             'static const uint16_t posture_refinement_roots[] = {' + ', '.join(str(i) for i in roots) + '};',
             'static const PostureRefinementNode posture_refinement_nodes[] = {']
    lines += [f'  {{{c_float(n["threshold"])}, {n["left"]}, {n["right"]}, {n["leaf"]}, {n["feature"]}}},' for n in nodes]
    lines += ['};', 'static const float posture_refinement_leaves[][2] = {']
    lines += ['  {' + ', '.join(c_float(v) for v in row) + '},' for row in leaves]
    lines += ['};', r'''
static inline PostureRefinementPrediction posture_refinement_rejected(void) {
  PostureRefinementPrediction p={255,0.0f,1,{0.0f,0.0f}}; return p;
}
static inline PostureRefinementPrediction posture_refinement_predict_features(const float *features) {
  PostureRefinementPrediction p=posture_refinement_rejected();
  double score[2]={0.0,0.0}; size_t tree; int i;
  if (!features) return p;
  for(i=0;i<10;++i) if(!isfinite(features[i])) return p;
  for(tree=0;tree<POSTURE_REFINEMENT_TREE_COUNT;++tree) {
    uint16_t index=posture_refinement_roots[tree];
    while(posture_refinement_nodes[index].feature>=0) {
      const PostureRefinementNode *node=&posture_refinement_nodes[index];
      index=features[(uint8_t)node->feature]<=node->threshold ? node->left : node->right;
    }
    for(i=0;i<2;++i) score[i]+=posture_refinement_leaves[posture_refinement_nodes[index].leaf][i];
  }
  for(i=0;i<2;++i) p.probabilities[i]=(float)(score[i]/POSTURE_REFINEMENT_TREE_COUNT);
  p.label=(uint8_t)(score[1]>score[0]); p.confidence=p.probabilities[p.label]; p.rejected=0; return p;
}
static inline PostureRefinementPrediction posture_refinement_predict_xyz(const float *xyz) {
  float features[10];
  if(!posture_refinement_extract_features(xyz,features)) return posture_refinement_rejected();
  return posture_refinement_predict_features(features);
}
''', '#endif', '']
    (output / "cattle_posture_refinement_candidate.h").write_text("\n".join(lines), encoding="ascii")
    return encoded


def predict_encoded(encoded, features):
    nodes = encoded["nodes"]
    feature = np.array([n["feature"] for n in nodes], dtype=np.int16)
    threshold = np.array([n["threshold"] for n in nodes], dtype=np.float32)
    left = np.array([n["left"] for n in nodes], dtype=np.int32)
    right = np.array([n["right"] for n in nodes], dtype=np.int32)
    leaf = np.array([n["leaf"] for n in nodes], dtype=np.int32)
    leaves = np.array(encoded["leaf_probabilities"], dtype=np.float64)
    score = np.zeros((len(features), 2))
    for root in encoded["roots"]:
        index = np.full(len(features), root, dtype=np.int32)
        while True:
            active = np.flatnonzero(feature[index] >= 0)
            if not len(active): break
            current = index[active]
            index[active] = np.where(features[active, feature[current]] <= threshold[current], left[current], right[current])
        score += leaves[leaf[index]]
    return score / len(encoded["roots"])


PARITY_RUNNER = r'''#include <stdio.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
#include "cattle_posture_refinement_candidate.h"
int main(void) {
  float xyz[3], out[14]; int i;
#ifdef _WIN32
  _setmode(_fileno(stdin),_O_BINARY); _setmode(_fileno(stdout),_O_BINARY);
#endif
  if(posture_refinement_extract_features(NULL,out)) return 10;
  if(!posture_refinement_predict_features(NULL).rejected) return 11;
  while(fread(xyz,sizeof(float),3,stdin)==3) {
    PostureRefinementPrediction p;
    if(!posture_refinement_extract_features(xyz,out)) {
      p=posture_refinement_predict_xyz(xyz);
      if(!p.rejected || p.label!=255) return 12;
      for(i=0;i<10;++i) out[i]=0;
    } else p=posture_refinement_predict_features(out);
    out[10]=p.probabilities[0]; out[11]=p.probabilities[1]; out[12]=(float)p.label; out[13]=(float)p.rejected;
    if(fwrite(out,sizeof(float),14,stdout)!=14) return 13;
  }
  return 0;
}'''


def verify_native(output, encoded, xyz, reference):
    features = extract_features(xyz)
    py_probability = predict_encoded(encoded, features)
    source = output / "parity_runner.c"
    source.write_text(PARITY_RUNNER, encoding="ascii")
    invalid = np.array([[np.nan, 0, 1], [0, np.inf, 1]], dtype=np.float32)
    payload = np.concatenate((xyz, invalid)).astype("<f4").tobytes()
    results = []
    for compiler, standard in (("gcc", "c99"), ("g++", "c++11")):
        binary = output / ("parity_" + standard.replace("+", "p") + ".exe")
        command = [shutil.which(compiler), "-std="+standard, "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror", "-pedantic", str(source), "-o", str(binary), "-lm"]
        subprocess.run(command, check=True, capture_output=True, timeout=60)
        ran = subprocess.run([str(binary)], input=payload, check=True, capture_output=True, timeout=30)
        values = np.frombuffer(ran.stdout, dtype="<f4").reshape(-1, 14)
        actual = values[:len(xyz)]
        mismatch = int(np.sum(actual[:, 12] != reference.argmax(1)))
        invalid_ok = bool(np.all(values[-2:, 12] == 255) and np.all(values[-2:, 13] == 1))
        passed = bool(np.allclose(actual[:, :10], features, atol=2e-7, rtol=2e-6) and
                      np.allclose(actual[:, 10:12], reference, atol=2e-6, rtol=2e-6) and not mismatch and invalid_ok)
        results.append({"language": standard, "compile_command": command, "samples": len(xyz),
            "feature_max_abs_error": float(np.max(np.abs(actual[:, :10]-features))),
            "probability_max_abs_error": float(np.max(np.abs(actual[:, 10:12]-reference))),
            "prediction_mismatches": mismatch, "invalid_rejected": invalid_ok, "passed": passed})
    result = {"passed": all(r["passed"] for r in results) and bool(np.allclose(py_probability, reference, atol=2e-6)),
              "prediction_mismatches": sum(r["prediction_mismatches"] for r in results), "results": results,
              "json_probability_max_abs_error": float(np.max(np.abs(py_probability-reference))),
              "scope": "native desktop C99/C++11 numerical parity; not an ESP32 timing benchmark"}
    write_json(output / "numerical_parity.json", result)
    if not result["passed"]: raise AssertionError(json.dumps(result))
    return result


def finalize(output, export):
    evaluation = json.loads((output / "heldout_evaluation.json").read_text(encoding="utf-8"))
    if export:
        encoded = export_model(output, joblib.load(output / "candidate_model.joblib"))
    else:
        encoded = json.loads((output / "candidate_model.json").read_text(encoding="utf-8"))
    with np.load(output / "evaluation_cache.npz", allow_pickle=False) as cache:
        parity = verify_native(output, encoded, cache["xyz_test"], cache["probabilities"])
        module, xyz, y, groups, training, test = reconstruct_split()
        folds = inner_folds(y, groups, training)
        checks = {
            "exact_historical_train_test_indices": np.array_equal(training, cache["train_indices"]) and np.array_equal(test, cache["test_indices"]),
            "original_raw_features_and_labels_match": np.array_equal(xyz[test], cache["xyz_test"]) and np.array_equal(y[test], cache["y_test"]),
            "feature_recomputation": np.array_equal(extract_features(xyz[test]), cache["features_test"]),
            "groups_disjoint": not bool(set(groups[training]) & set(groups[test])),
            "inner_cv_has_no_heldout_rows_or_group_overlap": all(not (set(fit) & set(test) or set(val) & set(test) or set(groups[fit]) & set(groups[val])) for fit, val in folds),
            "encoded_model_matches_recorded_metrics": metrics(cache["y_test"], predict_encoded(encoded, cache["features_test"]).argmax(1)) == evaluation["candidate_metrics"],
            "baseline_matches_frozen_confusion": metrics(cache["y_test"], cache["baseline"])["confusion_matrix"] == [[728, 110], [229, 1523]],
            "candidate_heldout_selection_once": evaluation["candidate_heldout_evaluations"] == 1 and not evaluation["heldout_used_for_hyperparameters"],
            "native_c99_cpp11_parity": parity["passed"],
            "protected_originals_unchanged": protected() == json.loads((output / "protected_inputs_before.json").read_text(encoding="utf-8")),
            "clinical_disabled": not encoded["clinical_lameness_enabled"] and not encoded["production_eligible"],
        }
    checks = {name: bool(value) for name, value in checks.items()}
    write_json(output / "verification_results.json", {"passed": all(checks.values()), "checks": checks,
               "checked_at_utc": datetime.now(timezone.utc).isoformat()})
    if not all(checks.values()): raise AssertionError(checks)
    contract = {"version": encoded["version"], "classes": CLASSES, "feature_names": FEATURES,
        "input": "one pointwise XYZ float32 vector; g under the historical 16,384 LSB/g assumption",
        "feature_arithmetic": "promote XYZ to float64; norm=sqrt(x*x+y*y+z*z); absolute axes; atan2(axis,sqrt(other_axis_squares)); output float32",
        "tilt_units": "radians", "sample_rate_hz": None, "temporal_window": None,
        "mapping": module.BINARY_POSTURE_SOURCE_LABELS, "sensor_location_provenance": "not independently verified in original source README",
        "api": ["posture_refinement_extract_features(xyz, features)", "posture_refinement_predict_features(features)", "posture_refinement_predict_xyz(xyz)"],
        "invalid_input": "null or nonfinite -> rejected, label 255", "confidence": "uncalibrated mean tree leaf probability",
        "production_eligible": False, "clinical_lameness_enabled": False, "recommended_for_integration": False,
        "decision": "retain_original_binary_posture; fixed refinement did not improve heldout accuracy or macro F1"}
    write_json(output / "feature_model_contract.json", contract)
    report = dict(evaluation)
    report["status"] = "exported_and_verified_inferior_research_candidate"
    report["decision"] = contract["decision"]
    report["footprint"] = {"trees": len(encoded["roots"]), "nodes": len(encoded["nodes"]),
        "leaves": len(encoded["leaf_probabilities"]),
        "model_arrays_bytes_assuming_12byte_node": len(encoded["nodes"])*12+len(encoded["leaf_probabilities"])*8+len(encoded["roots"])*2}
    report["verification_passed"] = True
    write_json(output / "training_report.json", report)
    summary = f'''# Pointwise Posture Refinement, 2026-10-26

Decision: retain the original binary posture model. The fixed candidate did
not improve the untouched historical heldout set. No firmware/model header
in a production directory was edited.

| Same 2,590 heldout rows | Accuracy | Balanced accuracy | Macro F1 |
| --- | ---: | ---: | ---: |
| Frozen old binary | {report['baseline_metrics']['accuracy']:.8f} | {report['baseline_metrics']['balanced_accuracy']:.8f} | {report['baseline_metrics']['macro_f1']:.8f} |
| Fixed refinement | {report['candidate_metrics']['accuracy']:.8f} | {report['candidate_metrics']['balanced_accuracy']:.8f} | {report['candidate_metrics']['macro_f1']:.8f} |

Source: https://github.com/andssuu/cattle_classification, dataset_6.csv.
The original loader/split seed 20260719 exactly reconstructed 13,088 rows,
671 row-label runs, 10,498 training rows/537 groups and 2,590 test rows/134
groups. Frozen compiled header confusion [[728,110],[229,1523]] matches the
old report exactly. Candidate confusion is {report['candidate_metrics']['confusion_matrix']}.
Split index hashes are in baseline_reconstruction.json; every row/group/fold
is recorded in raw_split.csv.

Ten deterministic pointwise features are XYZ, norm, absolute axes, and three
signed axis tilt angles in radians. Four forest budgets were fixed before
test access and compared using five-fold StratifiedGroupKFold only within
the original training partition. Selected configuration: {report['selected_configuration']}.
The model was fit once after selection. Candidate heldout accuracy was
evaluated once for the decision; later inference only checks export parity.
There was no tuning or retraining after observing test results. CPU training
used at most four threads and took {report['execution']['elapsed_seconds']:.2f} seconds.

Per-class F1 (old -> candidate): lying
{report['baseline_metrics']['classes']['lying']['f1']:.6f} -> {report['candidate_metrics']['classes']['lying']['f1']:.6f}; standing
{report['baseline_metrics']['classes']['standing']['f1']:.6f} -> {report['candidate_metrics']['classes']['standing']['f1']:.6f}.

All {len(checks)} verification checks pass. Native C99 and C++11 each match
all 2,590 heldout predictions, with NaN/Inf rejected. Numerical error details
are in numerical_parity.json. The portable headers and candidate_model.json
are isolated research artifacts, not recommended for firmware integration.

Animal/session IDs and timestamps are absent. Run-group validation is not
animal-independent validation. No 20 Hz samples, temporal windows, clinical
lameness labels or three-position data were created. The legacy mapping
Grazing/Walking -> standing is preserved only as the historical operational
task; it is not newly verified posture truth. Source scale (16,384 LSB/g)
and local sensor mounting remain unverified. Both clinical and production
eligibility flags remain false.

Reproduce tests: python -m unittest scripts.test_train_posture_refinement_20261026 -v
Fresh offline verification: python scripts/train_posture_refinement_20261026.py --verify-only
Training refuses if heldout_evaluation.json already exists, preventing an
accidental second tuning/evaluation cycle in this run directory.
'''
    (output / "REPORT.md").write_text(summary, encoding="utf-8")
    write_json(output / "artifact_manifest.json", {"files": [{"path": p.name, "bytes": p.stat().st_size, "sha256": sha(p)}
               for p in sorted(output.iterdir()) if p.is_file() and p.name != "artifact_manifest.json"]})
    print(f"Export/parity complete: {len(checks)} checks passed; retain original; no further training", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--export-only", action="store_true")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with threadpool_limits(limits=4):
        if args.export_only or args.verify_only:
            finalize(args.output, export=args.export_only)
        else:
            try:
                train(args.output)
                finalize(args.output, export=True)
            except RuntimeError as error:
                write_json(args.output / "blocker.json", {"status": "blocked", "reason": str(error), "no_improvement_validated": True})
                raise


if __name__ == "__main__":
    main()
