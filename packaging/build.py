"""Build the Windows installer: tests -> PyInstaller (dist/Gleaner) -> sign (optional) -> Inno Setup.

  py packaging/build.py              full build
  py packaging/build.py --skip-tests

Code signing (stops Smart App Control / "An Application Control policy has blocked this file"): set
GLEANER_SIGNTOOL_ARGS to the signtool "sign" options for your certificate, for example
  /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /a /n "Your Company"           (certificate in store)
  /fd SHA256 /tr http://timestamp.acs.microsoft.com /td SHA256 /dlib <Azure.CodeSigning.Dlib.dll>
      /dmdf <metadata.json>                                                              (Trusted Signing)
Optional: GLEANER_SIGNTOOL = full path of signtool.exe (else found in the Windows SDK). Never put a
certificate password in these variables; keep the certificate in the Windows store or in Trusted Signing.
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


def find_signtool() -> str:
    explicit = os.environ.get("GLEANER_SIGNTOOL")
    if explicit:
        return explicit
    kits = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Windows Kits" / "10" / "bin"
    found = shutil.which("signtool") or next(
        (str(p) for p in sorted(kits.glob("10.*/x64/signtool.exe"), reverse=True)), None)
    if not found:
        sys.exit("signtool.exe not found. Install the Windows SDK signing tools or set GLEANER_SIGNTOOL.")
    return found


def is_signed(signtool, path) -> bool:
    return subprocess.run([signtool, "verify", "/pa", "/q", str(path)], capture_output=True).returncode == 0


def sign_app(signtool, args):
    """Sign every program file in dist/Gleaner that isn't signed yet (Python and Qt files mostly are)."""
    files = [p for p in (ROOT / "dist" / "Gleaner").rglob("*") if p.suffix.lower() in (".exe", ".dll", ".pyd")]
    unsigned = [p for p in files if not is_signed(signtool, p)]
    print(f"Signing {len(unsigned)} of {len(files)} program files", flush=True)
    for start in range(0, len(unsigned), 50):
        # One Windows command line: the options are passed exactly as written in GLEANER_SIGNTOOL_ARGS.
        names = " ".join(f'"{p}"' for p in unsigned[start:start + 50])
        subprocess.run(f'"{signtool}" sign {args} {names}', cwd=ROOT, check=True)


def main():
    sign_args = os.environ.get("GLEANER_SIGNTOOL_ARGS", "").strip()
    if "--skip-tests" not in sys.argv:
        run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."])
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         "--distpath", "dist", "--workpath", "build", "packaging/gleaner.spec"])
    iscc = [find_iscc(), f"/DAppVersion={__version__}"]
    if sign_args:
        signtool = find_signtool()
        sign_app(signtool, sign_args)
        quoted = sign_args.replace('"', "$q")  # Inno Setup writes a quote as $q in a sign tool command
        iscc += ["/DSign", f"/Sgleaner=$q{signtool}$q sign {quoted} $f"]
    else:
        print("Not signing (GLEANER_SIGNTOOL_ARGS not set). Smart App Control may block this build.", flush=True)
    subprocess.run([*map(str, iscc), "packaging/gleaner.iss"], cwd=ROOT, check=True)
    setup = ROOT / "dist" / "installer" / f"Gleaner-Setup-{__version__}.exe"
    print(f"\nInstaller: {setup} ({setup.stat().st_size / 1_000_000:.0f} MB)")


if __name__ == "__main__":
    main()
