"""PyInstaller build script for DiskPilot."""

import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def build():
    icon_path = os.path.join(SCRIPT_DIR, "icon.ico")
    icon_flag = f"--icon={icon_path}" if os.path.exists(icon_path) else ""

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", "DiskPilot",
        "--uac-admin",
        "--add-data", f"icon.ico;." if os.path.exists(icon_path) else "",
        icon_flag,
        "gui.py",
    ]
    # Filter out empty strings
    cmd = [c for c in cmd if c]

    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=SCRIPT_DIR, check=True)
    print("\nBuild complete! Executable is in dist/DiskPilot.exe")


if __name__ == "__main__":
    build()
