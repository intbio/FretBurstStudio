block_cipher = None

a = Analysis(
    ['../src/fretGUI/main.py'],
    pathex=['../src/fretGUI'],  # Add source directory so PyInstaller can find local modules
    binaries=[],
    datas=[
        ('../src/fretGUI/static/*', 'static'),
        ('../src/fretGUI/configs/*', 'configs'),  # Include config files
        # Include hotkeys JSON and Python files as real files (NodeGraphQt loads them by path)
        ('../src/fretGUI/hotkeys/hotkeys.json', 'hotkeys'),
        ('../src/fretGUI/hotkeys/*.py', 'hotkeys'),
    ],
    hiddenimports=[
        # Qt.py shim and its submodules
        'Qt',
        'Qt.QtCore',
        'Qt.QtGui',
        'Qt.QtWidgets',

        # QtSvg is required by NodeGraphQt (via "from Qt import QtSvg").
        # Ensure the underlying Qt binding's SVG modules are collected.
        # NOTE: this assumes PySide6 + PySide6-Addons are installed in the env.
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        
        # Local application modules
        'custom_nodes',
        'custom_nodes.custom_nodes',
        'custom_nodes.selector_nodes',
        'custom_nodes.abstract_nodes',
        'custom_nodes.plotter_nodes',
        'custom_nodes.resizable_node_item',
        'custom_widgets',
        'custom_widgets.toogle_widget',
        'custom_widgets.progressbar_widget',
        'custom_widgets.path_selector',
        'custom_widgets.plot_widget',
        'custom_widgets.sliders',
        'custom_widgets.abstract_widget_wrapper',
        'singletons',
        'graph_engene',
        'node_workers',
        'node_builder',
        'fbs_data',
        'misc',
        'misc.plot_utils',
        'misc.fcsfiles',
        'hotkeys',
        'hotkeys.hotkey_functions',
    ],
    hookspath=['hooks'],      # you already have hook-PyQt6.py there
    runtime_hooks=[],
    excludes=['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FretBurstStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # set True if you want a console window
    icon='../src/fretGUI/static/fb_logo.ico',  # remove or adjust if needed
)