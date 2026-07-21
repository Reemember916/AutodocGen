# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['tickets', 'tickets.tickets', 'tickets.match', 'tickets.strategy', 'tickets.llm_match', 'diff.collect_changes', 'diff.block_diff', 'canonical.normalize', 'code_diff.collect_code_changes', 'render.change_order', 'render.code_change_order', 'extractor.reader', 'extractor.text_extract', 'model.ast']
hiddenimports += collect_submodules('lxml')
hiddenimports += collect_submodules('docx')


block_cipher = None


a = Analysis(
    ['gui_app.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='DocDiffWin7',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
