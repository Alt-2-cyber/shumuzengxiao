"""Leakage, physical feature, and portable inference contract tests."""

import importlib.util
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


SCRIPT = Path(__file__).with_name("train_motion_temporal_20261026.py")
spec = importlib.util.spec_from_file_location("motion_temporal_under_test", SCRIPT)
motion = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = motion
if SCRIPT.exists():
    spec.loader.exec_module(motion)


class TemporalContractTests(unittest.TestCase):
    def record(self, cow="cow1", labels=None, timestamps=None):
        n = 1000 if labels is None else len(labels)
        xyz = np.zeros((n, 3), dtype=np.float32)
        xyz[:, 2] = 1
        return motion.RawRecord(
            cow, cow, "2020-06-12", np.arange(n) / 25 if timestamps is None else timestamps,
            xyz, np.array(["RES"] * n if labels is None else labels),
        )

    def test_stationary_gravity_has_zero_variation_and_unit_norm(self):
        self.assertTrue(hasattr(motion, "extract_features"), "missing deterministic feature extractor")
        xyz = np.tile(np.array([0, 0, 1], dtype=np.float32), (80, 1))
        expected = np.array([0] * 12 + [1, 0, 1, 1, 0, 0] * 2, dtype=np.float32)
        np.testing.assert_array_equal(motion.extract_features(xyz), expected)

    def test_alternating_acceleration_exposes_temporal_energy(self):
        xyz = np.zeros((80, 3), dtype=np.float32)
        xyz[:, 0] = np.tile([-1, 1], 40)
        expected_x = [0, 1, -1, 1, 2, 2]
        np.testing.assert_allclose(motion.extract_features(xyz)[:6], expected_x)
        np.testing.assert_allclose(motion.extract_features(xyz)[18:], [1, 0, 1, 1, 0, 0])

    def test_rejects_nonfinite_and_wrong_window_length(self):
        for xyz in (np.zeros((79, 3)), np.full((80, 3), np.nan), np.full((80, 3), np.inf)):
            with self.assertRaises(ValueError):
                motion.extract_features(xyz)

    def test_windows_cannot_cross_class_gap_or_missing_label(self):
        labels = ["RES"] * 300 + ["BLN"] * 100 + ["MOV"] * 300 + ["GRZ"] * 300
        record = self.record(labels=labels)
        record.timestamps[850:] += 2
        windows = motion.make_windows([record], {"cow1": "train"})
        self.assertGreater(len(windows), 0)
        for w in windows:
            self.assertEqual(len(set(record.labels[w.raw_start:w.raw_stop])), 1)
            self.assertIn(record.labels[w.raw_start], motion.SOURCE_LABELS)
            self.assertTrue(np.all(np.diff(record.timestamps[w.raw_start:w.raw_stop]) < 0.06))
            self.assertGreaterEqual(w.raw_start, w.segment_start + 1)
            self.assertLessEqual(w.raw_stop, w.segment_stop - 1)

    def test_split_is_by_whole_animal_before_overlapping_windows(self):
        records = [self.record("cow1"), self.record("cow4")]
        windows = motion.make_windows(records, {"cow1": "train", "cow4": "test"})
        train = [w for w in windows if w.split == "train"]
        test = [w for w in windows if w.split == "test"]
        self.assertTrue(train and test)
        self.assertFalse({w.animal for w in train} & {w.animal for w in test})
        self.assertLess(train[1].target_start - train[0].target_start, 80)
        motion.validate_windows(windows)

    def test_refuses_missing_animal_assignment(self):
        with self.assertRaises(ValueError):
            motion.make_windows([self.record()], {})

    def test_leakage_validator_rejects_one_animal_in_two_roles(self):
        window = motion.make_windows([self.record()], {"cow1": "train"})[0]
        with self.assertRaisesRegex(ValueError, "Animal shared"):
            motion.validate_windows([window, replace(window, split="test")])

    def test_two_lying_animals_cannot_support_inner_and_external_validation(self):
        records = [self.record(cow, labels=["REL"] * 400) for cow in ("cow2", "cow4")]
        with tempfile.TemporaryDirectory() as directory:
            support = motion.audit_posture_support(records, Path(directory))
        self.assertFalse(support["support_sufficient"])
        self.assertFalse(support["new_binary_posture_model_created"])
        self.assertEqual(support["decision"], "retain_existing_binary_posture_with_limitations")
        self.assertNotIn("MOV", support["verified_mapping"])
        self.assertNotIn("GRZ", support["verified_mapping"])
        self.assertEqual([r["eligible_4s_lying_windows_after_1s_edge_purge"] for r in support["per_animal"]], [6, 6])

    def test_threshold_export_keeps_sklearn_float32_branch_semantics(self):
        lo = np.float32(1)
        hi = np.nextafter(lo, np.float32(2))
        threshold = (float(lo) + float(hi)) / 2
        exported = motion.floor_float32(threshold)
        self.assertLessEqual(float(exported), threshold)
        self.assertTrue(lo <= exported)
        self.assertFalse(hi <= exported)

    def test_public_unix_milliseconds_are_converted_before_gap_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cow1.csv").write_text(
                "TimeStamp_UNIX,TimeStamp_JST,AccX,AccY,AccZ,Label\n"
                "1591928577026,11:22:57.026000,0,0,-1,RES\n"
                "1591928577066,11:22:57.066000,0,0,-1,RES\n",
                encoding="ascii")
            records = motion.load_records(root, root)
        self.assertAlmostEqual(records[0].timestamps[1] - records[0].timestamps[0], .04, places=6)

    def test_generated_c_and_cpp_match_python_features_and_forest(self):
        self.assertTrue(hasattr(motion, "export_headers"), "missing portable model export")
        rng = np.random.default_rng(19)
        fixtures = rng.normal(0, 0.4, (12, 80, 3)).astype(np.float32)
        fixtures[:, :, 2] += 1
        x = np.stack([motion.extract_features(w) for w in fixtures])
        model = motion.RandomForestClassifier(n_estimators=3, max_depth=3,
                    min_samples_leaf=1, random_state=4, n_jobs=1).fit(x, np.arange(12) % 4)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            exported = motion.model_to_json(model)
            motion.export_headers(output, exported)
            result = motion.verify_portable(output, exported, fixtures,
                                            reference_probabilities=model.predict_proba(x))
        self.assertTrue(result["passed"])
        self.assertEqual(result["languages"], ["c99", "c++11"])
        self.assertEqual(result["prediction_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
