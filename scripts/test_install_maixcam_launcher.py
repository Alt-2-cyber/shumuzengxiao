import configparser
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import install_maixcam_launcher as installer


class LauncherInstallTests(unittest.TestCase):
    def test_renamed_research_binary_still_requires_its_expected_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'cattle_research.mud').write_text('[basic]\nmodel=renamed.cvimodel\n')
            (root / 'renamed.cvimodel').write_bytes(b'corrupted model')
            (root / 'conversion_result.json').write_text(json.dumps({
                'status': 'converted_research_only', 'scope': 'research_only',
                'cvimodel_sha256': hashlib.sha256(b'expected model').hexdigest()}))
            (root / 'rejection_thresholds.json').write_text(json.dumps({'minimum_score': .75, 'minimum_margin': .3}))
            with self.assertRaisesRegex(ValueError, 'Model differs'):
                installer.package_files(root)

    def test_registration_preserves_all_other_app_metadata(self):
        before = '[basic]\nversion=1\n\n[camera]\nname=Camera\ndesc=100% preview\nexec=camera\n'
        result = installer.register_app(before)
        parsed = configparser.ConfigParser(interpolation=None)
        parsed.read_string(result)
        self.assertEqual(dict(parsed['camera']), {'name': 'Camera', 'desc': '100% preview', 'exec': 'camera'})
        self.assertEqual(parsed['shumu_ywh']['name[zh]'], '\u6768\u6587\u660a-\u6570\u7267\u589e\u6548')
        self.assertEqual(parsed['shumu_ywh']['exec'], 'main.py')

    def test_reinstallation_replaces_only_our_single_registry_entry(self):
        once = installer.register_app('[basic]\nversion=1\n')
        twice = installer.register_app(once)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('[shumu_ywh]'), 1)

    def test_model_reference_cannot_escape_its_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'candidate.mud'
            model.write_text('[basic]\nmodel=../outside.cvimodel\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                installer.model_pair(model)

    def test_missing_model_binary_is_rejected_before_packaging(self):
        with tempfile.TemporaryDirectory() as directory:
            model = Path(directory) / 'candidate.mud'
            model.write_text('[basic]\nmodel=candidate.cvimodel\n', encoding='utf-8')
            with self.assertRaises(FileNotFoundError):
                installer.model_pair(model)


if __name__ == '__main__':
    unittest.main()
