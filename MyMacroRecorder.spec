# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for building the macOS .app bundle.
# Build with:  pyinstaller MyMacroRecorder.spec --noconfirm

block_cipher = None

a = Analysis(
    ['macro_recorder.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['pynput.keyboard._darwin', 'pynput.mouse._darwin'],
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
    [],
    exclude_binaries=True,
    name='MyMacroRecorder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MyMacroRecorder',
)

app = BUNDLE(
    coll,
    name='MyMacroRecorder.app',
    icon=None,
    bundle_identifier='com.macro.mymacrorecorder',
    info_plist={
        'CFBundleName': 'MyMacroRecorder',
        'CFBundleDisplayName': 'MyMacroRecorder',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        # Explains the prompts macOS shows for input capture/synthesis.
        'NSAppleEventsUsageDescription':
            'MyMacroRecorder needs control of your Mac to replay recorded macros.',
    },
)
