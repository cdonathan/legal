"""
Build Script for SeedJura Agreement Summary Tool
==================================================
Creates a standalone Windows executable using PyInstaller.

The executable bundles:
- FastAPI web app + static frontend
- Agreement type configs (lease/)
- Field anchors
- All Python dependencies

On launch, it starts the local web server and opens the browser.

Usage (from Windows - NOT WSL):
  cd C:\path\to\lease_summary_app
  pip install pyinstaller
  python build_exe.py

Or manually:
  pyinstaller seedjura.spec
"""

import os
import sys
import subprocess
from pathlib import Path


def build():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(app_dir)

    print("=" * 60)
    print("SeedJura Agreement Summary - Build Executable")
    print("=" * 60)

    # Check PyInstaller is available
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
    except ImportError:
        print("ERROR: PyInstaller not installed.")
        print("Install with: pip install pyinstaller")
        sys.exit(1)

    # Generate the spec file
    spec_path = os.path.join(app_dir, "seedjura.spec")
    _write_spec(spec_path, app_dir, parent_dir)
    print(f"Spec file: {spec_path}")

    # Run PyInstaller
    print("\nBuilding executable...")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", spec_path, "--clean", "-y"],
        cwd=app_dir,
    )

    if result.returncode == 0:
        dist_path = os.path.join(app_dir, "dist", "SeedJura")
        print(f"\n{'=' * 60}")
        print("BUILD COMPLETE")
        print(f"{'=' * 60}")
        print(f"Output: {dist_path}")
        print(f"\nTo run: {os.path.join(dist_path, 'SeedJura.exe')}")
        print("\nTo distribute: zip the entire 'dist/SeedJura/' folder.")
    else:
        print("\nBUILD FAILED")
        sys.exit(1)


def _write_spec(spec_path: str, app_dir: str, parent_dir: str):
    """Write the PyInstaller spec file."""
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for SeedJura Agreement Summary Tool.
Bundles FastAPI app + static files + configs into a single-folder executable.
"""

import os
import sys

block_cipher = None

app_dir = r"{app_dir}"
parent_dir = r"{parent_dir}"

a = Analysis(
    [os.path.join(app_dir, 'launcher.py')],
    pathex=[app_dir, parent_dir],
    binaries=[],
    datas=[
        # Static frontend
        (os.path.join(app_dir, 'static'), 'static'),
        # Agreement type configs
        (os.path.join(app_dir, 'agreement_types', 'lease'), os.path.join('agreement_types', 'lease')),
        (os.path.join(app_dir, 'agreement_types', '__init__.py'), 'agreement_types'),
        (os.path.join(app_dir, 'agreement_types', 'base.py'), 'agreement_types'),
        # Engine and XML export
        (os.path.join(app_dir, 'engine.py'), '.'),
        (os.path.join(app_dir, 'xml_export.py'), '.'),
        (os.path.join(app_dir, 'app.py'), '.'),
        # Parent dir files needed
        (os.path.join(parent_dir, 'lease_summary_tool.py'), '.'),
        (os.path.join(parent_dir, 'redactor.py'), '.'),
    ],
    hiddenimports=[
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'fastapi',
        'starlette',
        'starlette.routing',
        'starlette.responses',
        'starlette.middleware',
        'starlette.staticfiles',
        'anyio',
        'anyio._backends',
        'anyio._backends._asyncio',
        'multipart',
        'python_multipart',
        'openai',
        'httpx',
        'httpcore',
        'docx',
        'pymupdf',
        'thefuzz',
        'Levenshtein',
        'PIL',
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SeedJura',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for logs
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SeedJura',
)
'''
    with open(spec_path, "w") as f:
        f.write(spec_content)


if __name__ == "__main__":
    build()
