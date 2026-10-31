"""Resolve real Windows known folders, including redirected Desktop locations."""
import ctypes
from pathlib import Path
import uuid

FOLDERS = {
    "local": "F1B32785-6FBA-4FCF-9D55-7B8E7F157091",
    "roaming": "3EB685DB-65F9-4CF6-A03A-E3EF65729F3D",
    "desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
}

def known_folder(name):
    # KF_FLAG_NO_PACKAGE_REDIRECTION avoids inheriting a host app's private paths.
    folder_id = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID(FOLDERS[name]).bytes_le)
    value = ctypes.c_wchar_p()
    shell = ctypes.WinDLL("shell32")
    shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_wchar_p)]
    shell.SHGetKnownFolderPath.restype = ctypes.c_long
    result = shell.SHGetKnownFolderPath(ctypes.byref(folder_id), 0x00010000, None, ctypes.byref(value))
    if result:
        raise OSError("Unable to locate Windows folder: " + name)
    try:
        return Path(value.value)
    finally:
        free = ctypes.WinDLL("ole32").CoTaskMemFree
        free.argtypes = [ctypes.c_void_p]
        free(ctypes.cast(value, ctypes.c_void_p))
