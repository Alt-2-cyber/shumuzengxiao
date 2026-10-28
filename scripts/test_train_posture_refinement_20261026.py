"""Numerical and partition contract checks for the isolated posture candidate."""

import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np


SCRIPT = Path(__file__).with_name("train_posture_refinement_20261026.py")
spec = importlib.util.spec_from_file_location("posture_refinement_tested", SCRIPT)
posture = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = posture
if SCRIPT.exists():
    spec.loader.exec_module(posture)


class PostureRefinementTests(unittest.TestCase):
    def test_axis_orientation_features_have_physical_values(self):
        self.assertTrue(hasattr(posture, "extract_features"), "missing pointwise feature extractor")
        features = posture.extract_features(np.array([[0, 0, 1]], dtype=np.float32))
        np.testing.assert_allclose(features[0], [0, 0, 1, 1, 0, 0, 1, 0, 0, np.pi / 2])

    def test_zero_input_is_finite_and_nonfinite_input_is_rejected(self):
        np.testing.assert_array_equal(posture.extract_features(np.zeros((1, 3))), np.zeros((1, 10)))
        with self.assertRaises(ValueError):
            posture.extract_features(np.array([[np.nan, 0, 1]]))

    def test_exact_old_split_and_train_only_group_folds(self):
        _, x, y, groups, train, test = posture.reconstruct_split()
        self.assertEqual((len(x), len(train), len(test)), (13088, 10498, 2590))
        self.assertEqual(np.bincount(y[test]).tolist(), [838, 1752])
        self.assertFalse(set(groups[train]) & set(groups[test]))
        validation = []
        for fit, val in posture.inner_folds(y, groups, train):
            self.assertTrue(set(fit) <= set(train) and set(val) <= set(train))
            self.assertFalse(set(groups[fit]) & set(groups[val]))
            validation.extend(val.tolist())
        self.assertEqual(sorted(validation), train.tolist())

    def test_generated_c_cpp_features_and_predictions_match(self):
        self.assertTrue(hasattr(posture, "export_model"), "missing portable export")
        rng = np.random.default_rng(9)
        xyz = rng.normal(size=(30, 3)).astype(np.float32)
        x = posture.extract_features(xyz)
        model = posture.RandomForestClassifier(n_estimators=3, max_depth=3,
                                               random_state=8, n_jobs=1).fit(x, np.arange(30) % 2)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            encoded = posture.export_model(output, model)
            checked = posture.verify_native(output, encoded, xyz, model.predict_proba(x))
        self.assertTrue(checked["passed"])
        self.assertEqual(checked["prediction_mismatches"], 0)


if __name__ == "__main__":
    unittest.main()
