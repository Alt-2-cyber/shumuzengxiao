#!/usr/bin/env python3
import unittest

from export_reviewed_vision_dataset import clinical_fields_complete


class ReviewedVisionExportTest(unittest.TestCase):
    def test_incomplete_review_cannot_enable_disease_labels(self):
        self.assertFalse(clinical_fields_complete({
            "clinicalAnimalId": "cow-001",
            "veterinarian": "",
            "clinicalEvidenceReference": "case-1",
            "clinicallyVerifiedAt": "2026-09-18T10:00:00Z",
        }))

    def test_complete_review_enables_disease_labels(self):
        self.assertTrue(clinical_fields_complete({
            "clinicalAnimalId": "cow-001",
            "veterinarian": "vet-1",
            "clinicalEvidenceReference": "case-1",
            "clinicallyVerifiedAt": "2026-09-18T10:00:00Z",
        }))


if __name__ == "__main__":
    unittest.main()
