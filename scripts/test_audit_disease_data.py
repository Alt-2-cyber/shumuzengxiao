#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from audit_disease_data import build_report


class DiseaseDataAuditTest(unittest.TestCase):
    def test_empty_project_is_not_ready_for_any_disease_model(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(Path(directory))

        self.assertFalse(report["overallReady"])
        self.assertFalse(report["families"]["vision"]["ready"])
        self.assertFalse(report["families"]["audio"]["ready"])
        self.assertFalse(report["families"]["lameness"]["ready"])

    def test_placeholder_lameness_annotation_is_not_counted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "疾病识别生产落地" / "数据采集"
            data_dir.mkdir(parents=True)
            (data_dir / "lameness_annotations.csv").write_text(
                "recordingId,animalId,recordingSessionId,startedAt,lamenessScore,gaitReviewer,hoofExaminer,veterinarian,hoofFinding,videoReference,imuReference,clinicalEvidenceReference,verifiedAt\n"
                "motion-0001,cattle-017,session-YYYYMMDD-am,YYYY-MM-DDThh:mm:ssZ,0,trained-scorer,hoof-examiner,vet-identifier,no_lesion,video-file-or-url,imu-file-or-url,hoof-exam-reference,YYYY-MM-DDThh:mm:ssZ\n",
                encoding="utf-8",
            )
            report = build_report(root)

        self.assertEqual(report["families"]["lameness"]["usableAnnotations"], 0)
        self.assertFalse(report["families"]["lameness"]["ready"])

    def test_family_scope_only_gates_the_requested_family(self):
        with tempfile.TemporaryDirectory() as directory:
            report = build_report(Path(directory), family="audio")

        self.assertEqual(report["scope"], "audio")
        self.assertFalse(report["overallReady"])
        self.assertIn("audio", report["families"])
        self.assertNotIn("vision", report["checkedFamilies"])


if __name__ == "__main__":
    unittest.main()
