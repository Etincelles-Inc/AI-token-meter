import ctypes
from ctypes import wintypes
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
from token_speedometer.bubble import BubbleWindow

class WindowRegionTests(unittest.TestCase):
    def shell(self):
        state = {"handle": 100, "width": 538, "height": 440, "style": 0x80}
        def rectangle(_handle, pointer):
            rect = pointer._obj
            rect.left = rect.top = 0
            rect.right, rect.bottom = state["width"], state["height"]
            return True
        user = SimpleNamespace(
            GetAncestor=lambda *_: state["handle"],
            GetWindowRect=rectangle,
            GetWindowLongPtrW=Mock(side_effect=lambda *_: state["style"]),
            SetWindowLongPtrW=Mock(side_effect=lambda _h, _i, style: state.update(style=style)),
            SetWindowRgn=Mock(return_value=True))
        gdi = SimpleNamespace(CreateRoundRectRgn=Mock(return_value=77), DeleteObject=Mock())
        shell = BubbleWindow.__new__(BubbleWindow)
        shell.root = SimpleNamespace(winfo_exists=lambda: True, state=lambda: "normal", winfo_id=lambda: 10)
        shell.native = ctypes, wintypes, user, gdi
        shell.shaped = shell.styled = shell.pending = None
        return shell, state, user, gdi

    def test_repeated_geometry_notifications_do_not_reapply_native_frame(self):
        shell, state, user, gdi = self.shell()
        for _ in range(100):
            shell._reshape()
        self.assertEqual(gdi.CreateRoundRectRgn.call_count, 1)
        self.assertEqual(user.SetWindowRgn.call_count, 1)
        self.assertEqual(user.SetWindowLongPtrW.call_count, 1)

    def test_resize_updates_rounding_without_reapplying_style(self):
        shell, state, user, gdi = self.shell()
        shell._reshape()
        state["width"] += 20
        shell._reshape()
        self.assertEqual(user.SetWindowRgn.call_count, 2)
        self.assertEqual(user.SetWindowLongPtrW.call_count, 1)

    def test_new_native_handle_after_restore_gets_a_new_region(self):
        shell, state, user, gdi = self.shell()
        shell._reshape()
        state["handle"] += 1
        shell._reshape()
        self.assertEqual(user.SetWindowRgn.call_count, 2)
        self.assertEqual(user.GetWindowLongPtrW.call_count, 2)
