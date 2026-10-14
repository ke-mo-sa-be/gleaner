# PyInstaller spec for Gleaner.exe (one folder, no console). Built by packaging/build.py.
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "launch.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "app" / "picker.js"), "app"),
        (str(ROOT / "recipes"), "recipes"),
        (str(ROOT / "docs" / "USER_GUIDE.md"), "docs"),
    ],
    # Optional imports pulled in by dependencies but never used by Gleaner.
    excludes=["tkinter", "scraper", "tests", "unittest", "pydoc", "numpy", "PIL", "cryptography",
              "setuptools", "pkg_resources", "yaml"],
    noarchive=False,
)


def _keep(dest):
    """English-only UI: drop Qt translations (keep the browser engine's en-US pack) and QML (Widgets app)."""
    d = dest.replace("\\", "/")
    if d.startswith("PySide6/qml/"):
        return False
    if d.startswith("PySide6/translations/"):
        return d.endswith("qtwebengine_locales/en-US.pak")
    return True


a.datas = [entry for entry in a.datas if _keep(entry[0])]
a.binaries = [entry for entry in a.binaries if _keep(entry[0])]
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Gleaner",
    console=False,
    icon=str(ROOT / "packaging" / "gleaner.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Gleaner")
