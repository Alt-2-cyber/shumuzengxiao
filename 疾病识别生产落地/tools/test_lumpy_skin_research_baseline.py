#!/usr/bin/env python3
import unittest

from train_lumpy_skin_research_baseline import release_gate


class LumpySkinResearchGateTest(unittest.TestCase):
    def test_public_folder_dataset_can_never_be_production_approved(self):
        approved, reasons = release_gate(
            has_veterinary_signoff=False,
            has_animal_grouping=False,
            has_external_farm_test=False,
        )
        self.assertFalse(approved)
        self.assertIn("veterinary sign-off is missing", reasons)
        self.assertIn("animal grouping is missing", reasons)
        self.assertIn("external farm test is missing", reasons)


if __name__ == "__main__":
    unittest.main()
