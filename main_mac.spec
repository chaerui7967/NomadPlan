# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['nomadplan.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # onedir 방식 (app 번들 안에 따로 모음) - macOS에서 권장
    name='NomadPlan',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,           # GUI 앱이므로 터미널 창 없이 실행
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="source/icon.icns",   # macOS는 .icns 필요 (사전 변환 필요)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='NomadPlan',
)

app = BUNDLE(
    coll,
    name='NomadPlan.app',
    icon='source/icon.icns',
    bundle_identifier='com.chaerui.nomadplan',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'NSRequiresAquaSystemAppearance': 'False',
    },
)
