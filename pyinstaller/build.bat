@echo off
REM PyInstaller build script for FretBurstStudio
REM Windows batch file

echo ========================================
echo FretBurstStudio PyInstaller Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed!
    echo Please install it with: pip install pyinstaller
    pause
    exit /b 1
)

echo [1/3] Cleaning previous builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo Done.
echo.

echo [2/3] Running PyInstaller...
REM PyQt6 is excluded in the spec file and via custom hooks
python -m PyInstaller FretBurstStudio.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    pause
    exit /b 1
)
echo Done.
echo.

echo [3/3] Build complete!
echo.
echo Executable location: dist\FretBurstStudio.exe
echo.
echo You can now test the executable or create an installer.
pause

