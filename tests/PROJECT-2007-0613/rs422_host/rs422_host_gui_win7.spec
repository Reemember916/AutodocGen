# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ["rs422_host_gui.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        "serial",
        "serial.tools.list_ports",
        "serial.tools.list_ports_windows",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    name="PROJECT_RS422_Host",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PROJECT_RS422_Host",
)
