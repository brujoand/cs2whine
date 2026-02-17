a = Analysis(
    ['gsi_server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('gamestate_integration_coach.cfg', '.'),
        ('config.json', '.'),
    ],
    hiddenimports=[
        'windows_toasts',
        'winrt.windows.foundation',
        'winrt.windows.foundation.collections',
        'winrt.windows.data.xml.dom',
        'winrt.windows.ui.notifications',
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
    name='cs2whine',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)
