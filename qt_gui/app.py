from __future__ import annotations

import os
import sys


def _asset_path(*parts: str) -> str:
    base_dir = os.path.dirname(__file__)
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = os.path.join(sys._MEIPASS, "qt_gui")
    return os.path.join(base_dir, "assets", *parts)


def run_qt_gui(*, backend) -> int:
    from PyQt5 import QtGui, QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    app.setApplicationName("AutoDocGen")
    app.setOrganizationName("c2wordGen")
    app.setStyle("Fusion")

    try:
        try:
            from .main_window import MainWindow
            from .settings_store import SettingsStore
        except ImportError:
            from qt_gui.main_window import MainWindow
            from qt_gui.settings_store import SettingsStore

        store = SettingsStore()
        win = MainWindow(backend=backend, settings_store=store)

        icon_candidates = [
            _asset_path("app.ico"),
            os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "app.ico")),
        ]
        icon_path = next((p for p in icon_candidates if os.path.exists(p)), "")
        if icon_path:
            app.setWindowIcon(QtGui.QIcon(icon_path))

        qss_path = _asset_path("app.qss")
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())

        win.show()
        return app.exec_()
    except Exception:
        raise


if __name__ == "__main__":
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from autodoc import backend as _backend

    raise SystemExit(run_qt_gui(backend=_backend))
