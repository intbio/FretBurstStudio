# Quick Start Guide

## Prerequisites Check

Before building, ensure you have:

1. **Python 3.9+** installed
2. **PyInstaller** installed: `pip install pyinstaller`
3. **All dependencies** installed (check `environment.yml` or `requirements.txt`)

## Build Steps

1. Open a terminal/command prompt
2. Navigate to the build folder:
   ```bash
   cd build
   ```
3. Run the build script:
   ```bash
   build.bat
   ```
   or
   ```powershell
   .\build.ps1
   ```

## Output

The executable will be created at:
```
dist\FretBurstStudio.exe
```

## Testing

1. Test the executable on your machine first
2. For best results, test on a clean Windows machine without Python installed
3. Check that all features work:
   - Loading files
   - Creating nodes
   - Plotting
   - Saving/loading sessions

## Common Issues

### "Module not found" errors
- Add missing modules to `hiddenimports` in `FretBurstStudio.spec`
- Rebuild after changes

### Missing DLL errors
- Usually means Qt DLLs aren't being found
- Check that PySide6/PyQt6 is properly installed
- May need to manually add DLL paths to `binaries` in spec file

### Large executable size
- This is normal (100-300 MB) due to Qt, NumPy, SciPy, Matplotlib
- UPX compression is enabled to reduce size

## Next Steps

After successful build:
- Create an installer (Inno Setup, NSIS, or WiX)
- Add an icon file (update `icon=` in spec file)
- Test thoroughly before distribution

