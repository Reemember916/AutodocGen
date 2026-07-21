from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType


_BACKEND_MODULE_NAME = "autodoc.backend"
_LEGACY_BACKEND_ALIAS = "_autodoc_legacy_backend"


def app_root() -> str:
    """Return the application root directory.

    When running from a PyInstaller bundle (sys.frozen), this is the
    directory containing the executable.  Otherwise it is the project
    root (parent of the ``autodoc/`` package).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return str(Path(__file__).resolve().parents[1])


def legacy_backend() -> ModuleType:
    mod = sys.modules.get(_LEGACY_BACKEND_ALIAS)
    if mod is not None:
        return mod
    mod = sys.modules.get(_BACKEND_MODULE_NAME)
    if mod is not None:
        return mod
    from . import backend as backend_mod
    return backend_mod


__all__ = ["app_root", "legacy_backend"]
