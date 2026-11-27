# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec to bundle PanelCraft AI FastAPI backend + frontend for Windows/macOS/Linux."""

from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "packaging" / "run_backend.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "frontend"), "frontend"),
        (str(ROOT / "VERSION"), "."),
        (str(ROOT / "CHANGELOG.md"), "."),
    ],
    hiddenimports=[
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "multipart",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="panelcraft-backend",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ROOT / "assets" / "icons" / "icon.ico"),
)
