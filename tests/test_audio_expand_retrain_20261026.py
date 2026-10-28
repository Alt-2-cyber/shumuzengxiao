"""Behavioral checks for the isolated expanded calf-cough experiment."""

import importlib.util
import io
import json
import sys
import tempfile
import threading
import time
import types
import unittest
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
from scipy.io import wavfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audio_expand_retrain_20261026.py"
if SCRIPT.exists():
    specification = importlib.util.spec_from_file_location("audio_expanded", SCRIPT)
    audio = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = audio
    specification.loader.exec_module(audio)
else:
    audio = types.SimpleNamespace()


class ExpandedAudioTests(unittest.TestCase):
    def require(self, name):
        function = getattr(audio, name, None)
        self.assertTrue(callable(function), f"Missing expanded audio behavior: {name}")
        return function

    @staticmethod
    def tone(hz, count=8000):
        return 0.1 * np.sin(2 * np.pi * hz * np.arange(count) / 8000)

    def test_spectral_features_keep_frequency_and_ignore_gain_dc(self):
        extract = self.require("spectral_features")
        low = self.tone(500) + self.tone(1100) * 0.3
        a = extract(low)
        b = extract(low * 0.2 + 0.11)
        c = extract(self.tone(2700))
        self.assertTrue(np.isfinite(a).all())
        self.assertGreater(len(a), 60)
        np.testing.assert_allclose(a, b, atol=1e-8, rtol=1e-9)
        self.assertGreater(np.linalg.norm(a - c), 10.0)

    def test_known_padding_preserves_short_features_and_silent_window(self):
        window = self.require("make_windows")
        raw = window(self.tone(700, 3104))
        padded = window(np.pad(self.tone(700, 3104), (0, 12896)), valid_samples=3104)
        self.assertEqual([w["quality"]["observed_samples"] for w in padded], [3104, 0])
        self.assertEqual(padded[1]["status"], "abstain_no_observed_samples")
        np.testing.assert_array_equal(raw[0]["features"], padded[0]["features"])
        actual = window(np.r_[self.tone(700), np.zeros(8000)])
        self.assertEqual(actual[1]["quality"]["observed_samples"], 8000)
        self.assertEqual(actual[1]["status"], "abstain_silence")
        with self.assertRaises(ValueError):
            window(np.r_[self.tone(700), self.tone(1500)], valid_samples=8000)

    def test_duplicate_content_and_parent_groups_cannot_cross_folds(self):
        group = self.require("effective_groups")
        rows = [
            {"file_unit_id": "a", "raw_sha256": "raw1", "pcm_sha256": "pcm1", "parent_recording_id": "session1"},
            {"file_unit_id": "b", "raw_sha256": "raw2", "pcm_sha256": "pcm2", "parent_recording_id": "session1"},
            {"file_unit_id": "c", "raw_sha256": "raw3", "pcm_sha256": "pcm2", "parent_recording_id": None},
            {"file_unit_id": "d", "raw_sha256": "raw4", "pcm_sha256": "pcm4", "parent_recording_id": None},
        ]
        values = group(rows)
        self.assertEqual(values[0], values[1])
        self.assertEqual(values[1], values[2])
        self.assertNotEqual(values[2], values[3])

    def test_json_logistic_inference_matches_an_independent_literal(self):
        probability = self.require("portable_probability")
        model = {"model_type": "standardized_binary_logistic_regression",
                 "scaler_mean": [1.0, 2.0], "scaler_scale": [2.0, 4.0],
                 "coefficients": [0.5, -1.0], "intercept": 0.25}
        result = probability(model, [[3.0, 6.0]])
        self.assertAlmostEqual(float(result[0]), 0.4378234991142019, places=14)
        for bad in ([2.0, 0.0], [2.0, float("nan")]):
            with self.assertRaises(ValueError):
                probability({**model, "scaler_scale": bad}, [[3.0, 6.0]])

    def test_http_bound_and_failure_body_are_persisted(self):
        fetch = self.require("fetch_public")

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(403 if self.path == "/denied" else 200)
                if self.path == "/short":
                    self.send_header("Content-Length", "1000")
                self.end_headers()
                self.wfile.write(b"denied" if self.path == "/denied" else b"x" * (10 if self.path == "/short" else 1000))

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                base = f"http://127.0.0.1:{server.server_port}"
                truncated = fetch(base + "/big", Path(tmp) / "big.bin", max_bytes=100,
                                  timeout_seconds=3, route="direct")
                self.assertTrue(truncated["truncated"])
                self.assertEqual(truncated["bytes"], 100)
                self.assertEqual((Path(tmp) / "big.bin").stat().st_size, 100)
                denied = fetch(base + "/denied", Path(tmp) / "denied.bin", max_bytes=100,
                               timeout_seconds=3, route="direct")
                self.assertEqual(denied["status"], 403)
                self.assertEqual((Path(tmp) / "denied.bin").read_bytes(), b"denied")
                short = fetch(base + "/short", Path(tmp) / "short.bin", max_bytes=2000,
                              timeout_seconds=3, route="direct")
                self.assertFalse(short["complete"])
                self.assertEqual(short["error_type"], "ContentLengthMismatch")

        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=3)

    def test_nested_selection_fits_scalers_only_on_training_members(self):
        select = self.require("select_nested")
        rng = np.random.default_rng(7)
        features = rng.normal(size=(24, 4))
        labels = np.tile([0, 1], 12)
        groups = np.array([f"file-{i}" for i in range(24)])
        choice, audit = select(features, labels, groups, candidates=[{"C": 0.1}], seed=15)
        self.assertEqual(choice, {"C": 0.1})
        seen = np.zeros(24, dtype=int)
        for fold in audit["folds"]:
            train, test = fold["train_indices"], fold["test_indices"]
            self.assertFalse(set(train) & set(test))
            np.testing.assert_allclose(fold["scaler_mean"], np.mean(features[train], axis=0), atol=1e-14)
            seen[test] += 1
        np.testing.assert_array_equal(seen, np.ones(24, dtype=int))

    def test_http_total_budget_also_bounds_process_and_dns_startup(self):
        fetch = self.require("fetch_public")
        with tempfile.TemporaryDirectory() as tmp:
            start = time.monotonic()
            result = fetch("http://127.0.0.1:9/", Path(tmp) / "bounded.bin", max_bytes=100,
                           timeout_seconds=10, total_seconds=0.05, route="direct")
            self.assertLess(time.monotonic() - start, 3.0)
            self.assertFalse(result["complete"])
            self.assertEqual(result["error_type"], "HardTotalTimeBudgetExceeded")

    def test_exported_rbf_scores_match_fitted_model_without_pickle(self):
        export = self.require("export_model")
        probability = self.require("portable_probability")
        pipeline_factory = self.require("new_pipeline")
        rng = np.random.default_rng(22)
        features = rng.normal(size=(20, 133))
        labels = np.tile([0, 1], 10)
        candidate = {"kind": "rbf_svc", "C": 1.0, "gamma": "scale"}
        fitted = pipeline_factory(candidate).fit(features, labels)
        rows = [{"file_unit_id": str(i), "raw_sha256": str(i)} for i in range(20)]
        model = export(fitted, rows, np.arange(20), candidate)
        np.testing.assert_allclose(probability(model, features),
                                   1 / (1 + np.exp(-fitted.decision_function(features))), atol=2e-14, rtol=0)

    def test_native_prefix_is_resampled_separately_from_padding(self):
        analyze = self.require("analyze_wav")
        source = np.rint(32767 * np.r_[self.tone(1000), np.zeros(8000)]).astype(np.int16)
        stream = io.BytesIO()
        wavfile.write(stream, 8000, source)
        stream.seek(0)
        windows, metadata = analyze(stream, valid_input_samples=8000)
        self.assertEqual([w["quality"]["observed_samples"] for w in windows], [8000, 0])
        self.assertEqual(metadata["coverage_provenance"], "explicit_valid_prefix")

    def test_unsigned_pcm_rails_abstain_without_treating_silence_as_cough(self):
        analyze = self.require("analyze_wav")
        for data, status in ((np.full(8000, 128, dtype=np.uint8), "abstain_silence"),
                             (np.tile(np.array([0, 255], dtype=np.uint8), 4000), "abstain_clipped")):
            stream = io.BytesIO()
            wavfile.write(stream, 8000, data)
            stream.seek(0)
            windows, _ = analyze(stream)
            self.assertEqual(windows[0]["status"], status)
            self.assertIsNone(windows[0]["features"])

    def test_runtime_prediction_has_stable_event_only_contract(self):
        predict = self.require("predict")
        export = self.require("export_model")
        rng = np.random.default_rng(25)
        candidate = {"kind": "logistic", "C": 0.1}
        pipeline = self.require("new_pipeline")(candidate).fit(rng.normal(size=(20, 133)), np.tile([0, 1], 10))
        rows = [{"file_unit_id": str(i), "raw_sha256": str(i)} for i in range(20)]
        model = export(pipeline, rows, np.arange(20), candidate)
        with tempfile.TemporaryDirectory() as tmp:
            model_path, wav_path = Path(tmp) / "model.json", Path(tmp) / "tone.wav"
            model_path.write_text(json.dumps(model), encoding="utf-8")
            wavfile.write(wav_path, 8000, np.rint(128 + 127 * self.tone(700)).astype(np.uint8))
            result = predict(wav_path, model_path)
            self.assertTrue(result["research_only"])
            self.assertFalse(result["clinical_diagnosis"])
            self.assertFalse(result["clinicalDiagnosis"])
            self.assertEqual(result["input_duration_seconds"], 1.0)
            window = result["windows"][0]
            self.assertEqual(window["status"], "scored")
            self.assertEqual(window["start_seconds"], 0.0)
            self.assertEqual(window["end_seconds"], 1.0)
            self.assertIn(window["label"], ("cough", "non_cough"))
            self.assertIsNone(window["abstention_reason"])
            self.assertGreaterEqual(window["score"], 0.0)
            self.assertLessEqual(window["score"], 1.0)
            model["feature_id"] = "wrong-extractor"
            model_path.write_text(json.dumps(model), encoding="utf-8")
            with self.assertRaises(ValueError):
                predict(wav_path, model_path)

    def test_zip_extraction_rejects_parent_traversal_before_writing(self):
        extract = self.require("safe_extract_zip")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "bad.zip"
            with zipfile.ZipFile(archive, "w") as zipped:
                zipped.writestr("../outside.wav", b"bad")
            with self.assertRaises(ValueError):
                extract(archive, Path(tmp) / "output")
            self.assertFalse((Path(tmp) / "outside.wav").exists())

    def test_final_holdout_excludes_all_original_and_development_groups(self):
        split = self.require("make_split_plan")
        rows = [{"file_unit_id": f"file-{i}", "is_additional_recording": i >= 40} for i in range(80)]
        labels = np.tile([0, 1], 40)
        groups = np.array(["original-unknown"] * 40 + [f"new-{i // 2}" for i in range(40)])
        result = split(rows, labels, groups)
        development, holdout = result["development_indices"], result["final_holdout_indices"]
        self.assertTrue(set(range(40)).issubset(development))
        self.assertTrue(holdout)
        self.assertFalse(set(groups[development]) & set(groups[holdout]))
        self.assertEqual(set(development) | set(holdout), set(range(80)))
        for fold in result["development_outer_folds"]:
            self.assertFalse(set(fold["train_indices"] + fold["test_indices"]) & set(holdout))
            self.assertFalse(set(groups[fold["train_indices"]]) & set(groups[fold["test_indices"]]))

    def test_model_revalidation_detects_scaler_or_membership_tampering(self):
        validate = self.require("assert_model_parameters")
        expected = {"model_type": "standardized_binary_logistic_regression", "scaler_mean": [1.0, 2.0],
                    "scaler_scale": [2.0, 4.0], "coefficients": [0.1, 0.2], "intercept": 0.3,
                    "training_file_ids": ["a", "b"], "training_raw_sha256": ["x", "y"]}
        for changed in ({**expected, "scaler_mean": [1.0, 5.0]},
                        {**expected, "training_file_ids": ["a", "test-file"]}):
            with self.assertRaises((ValueError, AssertionError)):
                validate(changed, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
