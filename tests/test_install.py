import json
from pathlib import Path
import tempfile
import unittest
from token_speedometer.config import OWNER
from token_speedometer.install import manifest_files, remove_files, owned_root

class InstallScopeTests(unittest.TestCase):
    def test_unknown_files_survive_exact_manifest_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/".owner").write_text(OWNER)
            (root/"app.py").write_text("owned")
            (root/"personal.txt").write_text("retain")
            remove_files(root, {"files": ["app.py", ".owner"]})
            self.assertFalse((root/"app.py").exists())
            self.assertEqual((root/"personal.txt").read_text(), "retain")
    def test_manifest_traversal_rejected_before_any_removal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/"app";root.mkdir()
            (root/".owner").write_text(OWNER)
            outside = Path(folder)/"keep.txt";outside.write_text("retain")
            with self.assertRaises(RuntimeError):
                remove_files(root, {"files":[".owner", "../keep.txt"]})
            self.assertTrue((root/".owner").exists())
            self.assertEqual(outside.read_text(), "retain")
    def test_unowned_root_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/".owner").write_text("other")
            with self.assertRaises(RuntimeError):
                owned_root(root)
