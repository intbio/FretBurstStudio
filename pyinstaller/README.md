# FretBurstStudio PyInstaller Build

This folder contains PyInstaller configuration and build scripts for creating a Windows executable of FretBurstStudio.

## Prerequisites

1. **Python 3.9+** (tested with Python 3.12)
2. **PyInstaller**: Install with `pip install pyinstaller`
3. **All project dependencies**: Make sure your environment has all required packages installed:
   - PySide6 (or PyQt6)
   - NodeGraphQt
   - fretbursts
   - matplotlib
   - numpy
   - pandas
   - seaborn
   - scipy
   - h5py
   - pytables
   - phconvert

## Building the Executable

### Option 1: Using Batch Script (Windows)
```batch
cd build
build.bat
```

### Option 2: Using PowerShell Script
```powershell
cd build
.\build.ps1
```

### Option 3: Manual Build
```bash
cd build
python -m PyInstaller FretBurstStudio.spec --clean --noconfirm
```

## Output

After a successful build, the executable will be located at:
```
dist\FretBurstStudio.exe
```

## Troubleshooting

### PyQt6/PySide6 Conflict Error

**Error**: `ERROR: Aborting build process due to attempt to collect multiple Qt bindings packages`

**Solution**: This happens when both PyQt6 and PySide6 are installed. The build configuration excludes PyQt6 in favor of PySide6. The build scripts automatically exclude PyQt6 modules, and custom hooks prevent PyQt6 collection.

If you still encounter this error:
1. Uninstall PyQt6: `pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip`
2. Or ensure only PySide6 is installed in your environment

### Missing DLLs or Modules

If the executable fails to run with import errors:

1. **Check hidden imports**: The spec file includes many hidden imports, but you may need to add more if you encounter missing module errors. Add them to the `hiddenimports` list in `FretBurstStudio.spec`.

2. **Qt DLLs**: If Qt-related DLLs are missing, PyInstaller should automatically include them. If not, you may need to manually add them to the `binaries` list in the spec file.

3. **Matplotlib backend**: The spec file includes `matplotlib.backends.backend_qt5agg`. If you're using a different backend, update the hidden imports.

### Large Executable Size

The executable may be large (100+ MB) due to:
- Qt libraries
- NumPy/SciPy
- Matplotlib
- HDF5 libraries

To reduce size, you can:
- Use UPX compression (already enabled in spec file)
- Exclude unnecessary modules (already configured in `excludes`)

### Testing

Before distributing, test the executable on a clean Windows machine without Python installed to ensure all dependencies are bundled correctly.

## Customization

### Adding an Icon

To add a custom icon to the executable:

1. Create or obtain a `.ico` file
2. Update the `icon=None` line in `FretBurstStudio.spec` to point to your icon file:
   ```python
   icon='path/to/your/icon.ico',
   ```

### Including Additional Files

To include additional data files:

1. Add them to the `datas` list in `FretBurstStudio.spec`:
   ```python
   datas = [
       ('path/to/file', 'destination_folder'),
       ...
   ]
   ```

### Creating an Installer

After building the executable, you can create an installer using:
- **Inno Setup** (recommended for Windows)
- **NSIS** (Nullsoft Scriptable Install System)
- **WiX Toolset**

## Notes

- The spec file is configured for a single-file executable (onefile mode)
- Console window is disabled (`console=False`) for a cleaner GUI experience
- UPX compression is enabled to reduce file size
- The build process will create temporary `build/` and `dist/` folders

