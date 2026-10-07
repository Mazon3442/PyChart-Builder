"""
Native "open file" dialog for choosing a CSV, so nobody has to type a path.

Windows uses the standard Explorer dialog (through PowerShell, no extra install), macOS uses
AppleScript, and Linux uses whichever of zenity / kdialog / yad / qarma is installed: zenity and
yad give the GTK dialog (Thunar, GNOME, XFCE...), kdialog the Qt one (Dolphin, KDE). With none of
them available `pick_csv` says so and the app falls back to typing the path.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TITLE = "Choose a CSV file"

_POWERSHELL = (
    "Add-Type -AssemblyName System.Windows.Forms; "
    "$d = New-Object System.Windows.Forms.OpenFileDialog; "
    "$d.Title = '{title}'; $d.InitialDirectory = '{start}'; "
    "$d.Filter = 'CSV files (*.csv)|*.csv|All files (*.*)|*.*'; "
    "if ($d.ShowDialog() -eq 'OK') {{ [Console]::Out.Write($d.FileName) }}"
)


def system_env() -> dict[str, str]:
    """Environment for starting other programs (file dialogs, image viewers).

    The packaged app (PyInstaller) points LD_LIBRARY_PATH at its own bundled libraries. Programs
    it starts would inherit that and load those older copies instead of the system's, which makes
    zenity, xdg-open and the viewers crash on start. Put the original value back for them.
    """
    env = dict(os.environ)
    if getattr(sys, "frozen", False):
        for var in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
            orig = env.pop(f"{var}_ORIG", None)
            if orig is not None:
                env[var] = orig
            else:
                env.pop(var, None)
    return env


def picker_command(start: Path) -> list[str] | None:
    """The command that shows a file dialog on this system, or None if there isn't one."""
    if sys.platform == "win32":
        shell = shutil.which("powershell") or shutil.which("pwsh")
        if shell is None:
            return None
        script = _POWERSHELL.format(title=TITLE, start=str(start).replace("'", "''"))
        return [shell, "-NoProfile", "-STA", "-Command", script]
    if sys.platform == "darwin":
        return ["osascript", "-e",
                f'POSIX path of (choose file with prompt "{TITLE}" of type {{"csv", "public.comma-separated-values-text"}}'
                f' default location POSIX file "{start}")']
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None  # no desktop session (ssh, a bare console): nothing could be shown
    if shutil.which("zenity"):
        return ["zenity", "--file-selection", f"--title={TITLE}", f"--filename={start}/",
                "--file-filter=CSV files | *.csv *.CSV", "--file-filter=All files | *"]
    if shutil.which("kdialog"):
        return ["kdialog", "--title", TITLE, "--getopenfilename", str(start),
                "*.csv *.CSV|CSV files\n*|All files"]
    for name in ("yad", "qarma"):
        if shutil.which(name):
            return [name, "--file", f"--title={TITLE}", f"--filename={start}/",
                    "--file-filter=CSV files | *.csv *.CSV", "--file-filter=All files | *"]
    return None


def install_hint() -> str:
    """Advice shown next to the type-the-path box. Only Linux has a missing-dialog problem to explain."""
    if not sys.platform.startswith("linux"):
        return ""
    return ("Tip: no working file dialog was found. Install zenity (Arch: sudo pacman -S zenity, "
            "Debian/Ubuntu: sudo apt install zenity) and this will open a file picker instead.")


def pick_csv(start: Path | None = None) -> tuple[bool, Path | None]:
    """Show the dialog and wait. Returns (shown, chosen file).

    (False, None) means no dialog could be shown; (True, None) means it was cancelled.
    Blocks until the user answers, so call it from a thread.
    """
    start = start if start is not None and start.is_dir() else Path.home()
    cmd = picker_command(start)
    if cmd is None:
        return False, None
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=system_env())
    except OSError:
        return False, None
    chosen = done.stdout.strip().splitlines()
    if done.returncode == 0 and chosen:
        return True, Path(chosen[0])
    # Cancelling gives exit 1 (zenity, kdialog, osascript) or exit 0 with no output (PowerShell).
    # A dialog that failed to start also exits 1, but says why on stderr - fall back for those.
    failed = re.search(r"error|not found|cannot|can't|failed", done.stderr, re.IGNORECASE)
    return done.returncode in (0, 1) and not failed, None
