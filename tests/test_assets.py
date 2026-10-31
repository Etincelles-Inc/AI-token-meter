import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from token_speedometer import install as package
from token_speedometer.config import OWNER
from token_speedometer.theme import asset

class AssetInstallTests(unittest.TestCase):
    def test_source_install_copies_logo_and_manifest_removes_only_owned_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "app"
            paths = [Path(folder)/"Etincelles Token Meter.lnk",
                     Path(folder)/"Uninstall Etincelles Token Meter.lnk",
                     Path(folder)/"startup.lnk"]
            with patch.object(package, "installed_root", return_value=root), \
                 patch.object(package, "data_dir", return_value=root), \
                 patch.object(package, "shortcut_paths", return_value=paths), \
                 patch.object(package, "write_shortcut"):
                package.install()
            logo = root / "token_speedometer/assets/etincelles-128.png"
            self.assertEqual(logo.read_bytes(), asset("etincelles-128.png").read_bytes())
            manifest = json.loads((root/"install.json").read_text())
            retained = logo.parent / "personal-note.txt"
            retained.write_text("Keep this user file")
            package.remove_files(root, manifest)
            self.assertFalse(logo.exists())
            self.assertEqual(retained.read_text(), "Keep this user file")

    def test_copied_source_launches_and_finds_its_packaged_logo(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "app"
            with patch.object(package, "installed_root", return_value=root), \
                 patch.object(package, "data_dir", return_value=root), \
                 patch.object(package, "shortcut_paths", return_value=[]):
                package.install()
            result = subprocess.run([sys.executable, str(root/"launcher.py"), "--version"],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Etincelles Token Meter", result.stdout)
            result = subprocess.run([sys.executable, "-B", "-c",
                "from token_speedometer.theme import asset; assert asset('etincelles-64.png').is_file()"],
                cwd=root, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
