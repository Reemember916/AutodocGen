# -*- mode: python ; coding: utf-8 -*-

import glob
import os

block_cipher = None

# --- clangd 二进制打包 ---
# 优先从 bin-min（最小集，由 prepare_clangd_min.bat 生成）
# 回退到完整 llvm/bin 目录（如果用户已跑 install_clangd_win7.bat）
_clangd_bin_min = os.path.join('tools', 'clangd', 'win7', 'llvm', 'bin-min')
_clangd_bin_full = os.path.join('tools', 'clangd', 'win7', 'llvm', 'bin')
_clangd_dst = os.path.join('tools', 'clangd', 'win7', 'llvm', 'bin')
_clangd_src = _clangd_bin_min if os.path.isdir(_clangd_bin_min) else _clangd_bin_full
_clangd_datas = [(f, _clangd_dst) for f in glob.glob(os.path.join(_clangd_src, '*'))]
if not _clangd_datas:
    print('[WARN] clangd 二进制未找到，exe 将不包含 LSP 功能。')
    print('       请先运行 tools/clangd/win7/prepare_clangd_min.bat')
    print('       或 tools/clangd/win7/install_clangd_win7.bat')

a = Analysis(
    ['AutoDocGen_V1.4.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('qt_gui/assets', 'qt_gui/assets'),
        ('autodocgen.ini', '.'),
        ('symbol_dictionary.json', '.'),
        ('tools/lsp/project_compat.h', 'tools/lsp'),
        ('tools/update_doc_from_code_diff.py', 'tools'),
        ('tools/render_update_review_html.py', 'tools'),
        ('tools/merge_batch_docx.py', 'tools'),
        ('tools/workspace_to_revision.py', 'tools'),
        ('tools/audit_design_workspace.py', 'tools'),
        ('tools/convert_ccs_to_compile_commands.py', 'tools'),
        ('autodoc', 'autodoc'),
        ('qt_gui', 'qt_gui'),
        ('DocDiff-main', 'DocDiff-main'),
    ] + _clangd_datas,
    hiddenimports=[
        'autodoc',
        'autodoc.models',
        'autodoc.utils',
        'autodoc.text',
        'autodoc.scanner',
        'autodoc.compile_db',
        'autodoc.semantic_pack',
        'autodoc.codegraph_adapter',
        'autodoc.graph_visuals',
        'autodoc.naming_context',
        'autodoc.lsp_transport',
        'autodoc.logic',
        'autodoc.semantic_registry',
        'autodoc.runtime',
        'autodoc.parse',
        'autodoc.naming',
        'autodoc.semantic',
        'autodoc.context_pack',
        'autodoc.lsp_adapter',
        'autodoc.lsp_facts',
        'autodoc.lsp_gateway',
        'autodoc.ai',
        'autodoc.render',
        'autodoc.pipeline',
        'autodoc.backend',
        'autodoc.cli',
        'autodoc._legacy_support',
        'autodoc.term_table',
        'autodoc.config',
        'autodoc.incremental',
        'qt_gui',
        'qt_gui.app',
        'qt_gui.main_window',
        'qt_gui.runner',
        'qt_gui.settings_store',
        'qt_gui.consistency_panel',
        'tools.update_doc_from_code_diff',
        'tools.render_update_review_html',
    ],
    hookspath=['hooks'],
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
    [],
    exclude_binaries=True,
    name='AutoDocGen',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['qt_gui\\assets\\app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AutoDocGen',
)
