"""Targeted macOS compatibility for Qt platform-plugin discovery."""
import os
from pathlib import Path
import stat
import sys


def prepare_platform_plugins(directory=None):
    """Clear UF_HIDDEN on platform DLLs; Qt skips hidden plugins when scanning.

    Files under the local .venv were observed with macOS's hidden flag set.
    The enclosing .venv stays hidden; only this display flag is cleared.
    """
    if sys.platform != "darwin":
        return
    if directory is None:
        from PySide6.QtCore import QLibraryInfo
        directory = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))/"platforms"
    for path in Path(directory).glob("*.dylib"):
        flags = path.stat().st_flags
        if flags & stat.UF_HIDDEN:
            os.chflags(path,flags & ~stat.UF_HIDDEN)
