"""Borderless Tk shell. Native Windows regions provide actual rounded corners."""
import os
from .theme import RADIUS

class BubbleWindow:
    def __init__(self, root):
        self.root = root
        self.minimized = False
        self.pending = None
        self.native = None
        root.withdraw()
        root.overrideredirect(True)
        root.bind("<Configure>", self._configure, add="+")
        root.bind("<Map>", self._mapped, add="+")
        root.bind("<Alt-F4>", lambda _event: root.destroy())
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            user, gdi = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("gdi32", use_last_error=True)
            user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
            user.GetAncestor.restype = wintypes.HWND
            user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
            user.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user.GetWindowLongPtrW.restype = ctypes.c_ssize_t
            user.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            user.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
            gdi.CreateRoundRectRgn.restype = wintypes.HRGN
            gdi.DeleteObject.argtypes = [wintypes.HANDLE]
            self.native = (ctypes, wintypes, user, gdi)
        self.drag_offset = None

    def _hwnd(self):
        return self.native[2].GetAncestor(self.root.winfo_id(), 2)

    def _reshape(self):
        self.pending = None
        if not self.root.winfo_exists() or self.root.state() != "normal" or not self.native:
            return
        ctypes, wintypes, user, gdi = self.native
        hwnd = self._hwnd()
        style = user.GetWindowLongPtrW(hwnd, -20)
        user.SetWindowLongPtrW(hwnd, -20, (style & ~0x80) | 0x40000)
        rect = wintypes.RECT()
        if user.GetWindowRect(hwnd, ctypes.byref(rect)):
            region = gdi.CreateRoundRectRgn(0, 0, rect.right-rect.left+1, rect.bottom-rect.top+1,
                                           RADIUS*2, RADIUS*2)
            if region and not user.SetWindowRgn(hwnd, region, True):
                gdi.DeleteObject(region)
            # Windows owns a region after a successful SetWindowRgn call.

    def _configure(self, event):
        if event.widget is self.root and self.pending is None:
            self.pending = self.root.after_idle(self._reshape)

    def _mapped(self, event):
        if event.widget is self.root and self.minimized and self.root.state() == "normal":
            self.minimized = False
            self.root.overrideredirect(True)
            self.root.after_idle(self._reshape)

    def minimize(self):
        self.root.overrideredirect(False)
        self.root.update_idletasks()
        self.root.iconify()
        self.minimized = True

    def bind_drag(self, widget):
        widget.bind("<ButtonPress-1>", self._begin_drag, add="+")
        widget.bind("<B1-Motion>", self._drag, add="+")

    def _begin_drag(self, event):
        self.drag_offset = (event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y())

    def _drag(self, event):
        if self.drag_offset:
            x, y = event.x_root-self.drag_offset[0], event.y_root-self.drag_offset[1]
            # Tk expresses negative positions as distances from the far edge.
            horizontal = f"+{x}" if x >= 0 else f"-{self.root.winfo_screenwidth()-self.root.winfo_width()-x}"
            vertical = f"+{y}" if y >= 0 else f"-{self.root.winfo_screenheight()-self.root.winfo_height()-y}"
            self.root.geometry(horizontal+vertical)

    def show(self, config):
        self.root.update_idletasks()
        width, height = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        max_x, max_y = self.root.winfo_screenwidth()-width, self.root.winfo_screenheight()-height
        x = max(0, min(int(config.get("x", max_x-24)), max_x))
        y = max(0, min(int(config.get("y", 36)), max_y))
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        if self.native:
            self._reshape()
            ctypes, wintypes, user, gdi = self.native
            hwnd = self._hwnd()
            style = user.GetWindowLongPtrW(hwnd, -20)
            user.SetWindowLongPtrW(hwnd, -20, (style & ~0x80) | 0x40000)
        self.root.deiconify()
        self.root.after(50, self._reshape)
