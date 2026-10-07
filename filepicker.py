"""
Native "open file" dialog for choosing a CSV, so nobody has to type a path.

Windows uses the standard Explorer dialog (through PowerShell, no extra install), macOS uses
AppleScript, and Linux uses whichever of zenity / kdialog / yad / qarma is installed: zenity and
yad give the GTK dialog (Thunar, GNOME, XFCE...), kdialog the Qt one (Dolphin, KDE). With none of
them available `pick_csv` says so and the app falls back to typing the path.
"""
from __future__ import annotations

import os
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
        done = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return False, None
    chosen = done.stdout.strip().splitlines()
    if done.returncode == 0 and chosen:
        return True, Path(chosen[0])
    # Cancelling gives exit 1 (zenity, kdialog, osascript) or exit 0 with no output (PowerShell);
    # any other failure means the dialog itself is broken, so let the caller fall back.
    return done.returncode in (0, 1), None
