"""Windows specific utility functions"""
import ctypes
import os
from pathlib import Path
from typing import Optional

# Known folder IDs
FOLDERID_SavedGames = "{4C5C32FF-BB9D-43B0-B5B4-2D72E54EAAA4}"


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def get_saved_games_path() -> Optional[Path]:
    """
    Get the path to the user's Saved Games folder on Windows.
    """
    try:
        # Use SHGetKnownFolderPath to get the path
        ptr = ctypes.c_wchar_p()
        ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(GUID.from_buffer_copy(bytes.fromhex(FOLDERID_SavedGames.replace('-', '').replace('{', '').replace('}', '')))),
            0,
            None,
            ctypes.byref(ptr),
        )
        path = ptr.value
        ctypes.windll.ole32.CoTaskMemFree(ptr)
        if path:
            return Path(path)
    except Exception:
        pass

    # Fallback to user profile
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return Path(user_profile) / "Saved Games"

    return None
