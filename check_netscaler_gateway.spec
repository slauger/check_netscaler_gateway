# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for check_netscaler_gateway
Creates a single-file executable for cross-platform distribution
"""

block_cipher = None

a = Analysis(
    ['run_check_netscaler_gateway.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna',
        'check_netscaler_gateway.client',
        'check_netscaler_gateway.client.session',
        'check_netscaler_gateway.client.gateway',
        'check_netscaler_gateway.client.storefront',
        'check_netscaler_gateway.client.exceptions',
        'check_netscaler_gateway.output',
        'check_netscaler_gateway.output.nagios',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pytest-cov',
        'pytest-mock',
        'black',
        'ruff',
        'mypy',
        'setuptools',
        '_pytest',
        'py',
    ],
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
    name='check_netscaler_gateway',
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
)
