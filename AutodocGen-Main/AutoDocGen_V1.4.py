"""AutoDocGen V1.4 — CSCI detailed design document generator.

Entry point: delegates to autodoc.backend for all logic.
"""
import sys


def _ensure_autodoc_on_path():
    """Ensure the autodoc package is importable."""
    import os
    entry_dir = os.path.dirname(os.path.abspath(__file__))
    if entry_dir not in sys.path:
        sys.path.insert(0, entry_dir)


def main():
    _ensure_autodoc_on_path()
    from autodoc.cli import main as _main
    _main()


if __name__ == "__main__":
    main()
