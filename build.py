"""
Build a standalone executable (no Python needed to run it).

    pip install -r requirements.txt pyinstaller
    python build.py

Output: dist/gantt-builder (Linux/macOS) or dist/gantt-builder.exe (Windows).
PyInstaller can't cross-compile, so run this on each OS you want a build for
(.github/workflows/build.yml does Linux and Windows for you).
"""
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).parent

PyInstaller.__main__.run([
    str(ROOT / "gantt_app.py"),
    "--name", "gantt-builder",
    "--onefile",
    "--console",                      # it's a terminal app
    "--noconfirm",
    "--clean",
    "--distpath", str(ROOT / "dist"),
    "--workpath", str(ROOT / "build"),
    "--specpath", str(ROOT / "build"),
    "--collect-all", "textual",       # CSS / data files and lazily imported widgets
    "--exclude-module", "tkinter",    # matplotlib only needs the Agg (PNG) backend
])
