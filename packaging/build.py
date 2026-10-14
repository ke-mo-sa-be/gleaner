"""Build the Windows installer: tests -> PyInstaller (dist/Gleaner) -> Inno Setup (dist/installer).

  py packaging/build.py              full build
  py packaging/build.py --skip-tests
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import __version__  # noqa: E402


def find_iscc() -> Path:
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
    ]
    found = shutil.which("iscc") or next((str(c) for c in candidates if c.exists()), None)
    if not found:
        sys.exit("Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup --scope user")
    return Path(found)


def run(cmd):
    print("+", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main():
    if "--skip-tests" not in sys.argv:
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."])
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", "dist", "--workpath", "build", "packaging/gleaner.spec"])
    run([find_iscc(), f"/DAppVersion={__version__}", "packaging/gleaner.iss"])
    setup = ROOT / "dist" / "installer" / f"Gleaner-Setup-{__version__}.exe"
    print(f"\nInstaller: {setup} ({setup.stat().st_size / 1_000_000:.0f} MB)")


if __name__ == "__main__":
    main()
