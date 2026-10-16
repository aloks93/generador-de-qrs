"""Empaqueta la app de escritorio en un .exe portable y un .zip para Windows.

Uso:  python scripts/build_windows.py
Salida: dist/GeneradorQR.exe y dist/GeneradorQR-windows.zip
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
NAME = "GeneradorQR"


def main() -> None:
    sep = ";" if sys.platform == "win32" else ":"
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", NAME,
            "--icon", str(ROOT / "assets" / "icon.ico"),
            "--add-data", f"{ROOT / 'assets'}{sep}assets",
            "--collect-data", "customtkinter",
            # Módulos que la app no usa: reducen el tamaño del ejecutable.
            "--exclude-module", "numpy",
            "--exclude-module", "pytest",
            "--exclude-module", "unittest",
            "--exclude-module", "pydoc",
            "--distpath", str(DIST),
            "--workpath", str(ROOT / "build"),
            "--specpath", str(ROOT / "build"),
            str(ROOT / "main.py"),
        ],
        check=True,
        cwd=ROOT,
    )
    exe = DIST / (NAME + (".exe" if sys.platform == "win32" else ""))
    archive = DIST / f"{NAME}-windows.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe, exe.name)
        for extra in ("LICENSE", "README.md"):
            zf.write(ROOT / extra, extra)
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    print(f"Listo: {exe} ({exe.stat().st_size / 1e6:.1f} MB) y {archive}")


if __name__ == "__main__":
    main()
