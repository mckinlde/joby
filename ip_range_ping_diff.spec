# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for ip-range-ping-diff.

Produces a single-file executable bundling the Python runtime,
PySide6 libraries, and all application modules.

Usage:
    pyinstaller ip_range_ping_diff.spec
"""

a = Analysis(
    ['ip_range_ping_diff/__main__.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PySide6.QtWidgets',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'ip_range_ping_diff',
        'ip_range_ping_diff.cli',
        'ip_range_ping_diff.config',
        'ip_range_ping_diff.diagnostic_executor',
        'ip_range_ping_diff.diagnostic_reporter',
        'ip_range_ping_diff.diff_reporter',
        'ip_range_ping_diff.exclusion',
        'ip_range_ping_diff.executor',
        'ip_range_ping_diff.models',
        'ip_range_ping_diff.scanner',
        'ip_range_ping_diff.gui',
        'ip_range_ping_diff.gui.control_panel',
        'ip_range_ping_diff.gui.dot_grid',
        'ip_range_ping_diff.gui.main_window',
        'ip_range_ping_diff.gui.results_panel',
        'ip_range_ping_diff.gui.scan_controller',
    ],
    hookspath=[],
    hooksconfig={},
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
    name='ip-range-ping-diff',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
