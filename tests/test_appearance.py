import contextlib
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from token_speedometer.appearance import windows_dark, linux_preference, resolved_mode
from token_speedometer.config import validate_config
from token_speedometer.controller import Controller
from token_speedometer.adapters import observation

class AppearanceTests(unittest.TestCase):
    def windows(self, values, missing=False):
        def query(_key, name):
            if name not in values:
                raise FileNotFoundError(name)
            return values[name]
        api = SimpleNamespace(HKEY_CURRENT_USER=1, REG_DWORD=4,
            OpenKey=Mock(side_effect=OSError("missing")) if missing else
                    Mock(side_effect=lambda *_: contextlib.nullcontext(object())),
            QueryValueEx=Mock(side_effect=query))
        with patch.dict(sys.modules, {"winreg": api}):
            return windows_dark()

    def test_windows_follows_app_dark_over_light_shell(self):
        self.assertTrue(self.windows({"AppsUseLightTheme": (0,4), "SystemUsesLightTheme": (1,4)}))
    def test_windows_follows_app_light_over_dark_shell(self):
        self.assertFalse(self.windows({"AppsUseLightTheme": (1,4), "SystemUsesLightTheme": (0,4)}))
    def test_windows_missing_app_value_uses_shell_fallback(self):
        self.assertTrue(self.windows({"SystemUsesLightTheme": (0,4)}))
    def test_missing_windows_preference_falls_back_to_light(self):
        self.assertFalse(self.windows({}, missing=True))
    def test_invalid_windows_value_is_not_treated_as_dark(self):
        self.assertFalse(self.windows({"AppsUseLightTheme": ("0",1)}))
    def test_portal_explicit_preference_has_priority(self):
        self.assertFalse(linux_preference(2,"prefer-dark","Yaru-dark",True))
        self.assertTrue(linux_preference(1,"prefer-light","Yaru",False))
    def test_gnome_and_gtk_fallbacks(self):
        self.assertTrue(linux_preference(0,"prefer-dark"))
        self.assertFalse(linux_preference(None,"prefer-light","Yaru-dark",True))
        self.assertTrue(linux_preference(99,"","Yaru-dark"))
        self.assertTrue(linux_preference(None,"","",True))
    def test_follow_desktop_tracks_changes_between_checks(self):
        reader=Mock(side_effect=[False,True,False])
        self.assertEqual([resolved_mode("system",reader) for _ in range(3)],["light","dark","light"])
    def test_manual_appearance_does_not_change_or_query_desktop(self):
        reader=Mock(side_effect=AssertionError("Desktop should not be queried"))
        self.assertEqual(resolved_mode("dark",reader),"dark")
        self.assertEqual(resolved_mode("light",reader),"light")
    def test_default_is_system_and_invalid_appearance_rejected(self):
        self.assertEqual(validate_config({})["appearance"],"system")
        with self.assertRaises(ValueError):
            validate_config({"appearance":"unknown"})
    def test_appearance_change_keeps_timing_and_capture_history(self):
        controller=Controller(validate_config({"backend":"native"}))
        controller.store.observe(observation(2500,50,"native","m","Native",10))
        epoch,revision=controller.store.epoch,controller.revision
        controller.update_view_settings(appearance="dark")
        self.assertEqual(controller.store.sample()["write"]["rate"],50)
        self.assertEqual((controller.store.epoch,controller.revision),(epoch,revision))
    def test_presentation_update_cannot_change_the_engine(self):
        controller=Controller(validate_config({}))
        with self.assertRaises(ValueError):
            controller.update_view_settings(backend="ollama")
