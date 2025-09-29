# PyInstaller spec file for bundling Noctics Core with Ollama and a default model.
# Adjust the paths in `ollama_binaries` and `model_files` before building.

block_cipher = None

OLLAMA_BINARIES = [
    ('ollama', 'resources/ollama/bin/ollama', 'BINARY'),
    ('libollama.so', 'resources/ollama/lib/libollama.so', 'BINARY'),
]

MODEL_FILES = [
    ('models/your-model.gguf', 'resources/models/your-model.gguf', 'DATA'),
]

a = Analysis(
    ['noctics_core.py'],
    pathex=['.'],
    binaries=OLLAMA_BINARIES,
    datas=MODEL_FILES,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    name='noctics-bundle',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='dist/noctics-bundle',
)
