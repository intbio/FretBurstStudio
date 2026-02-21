# PyInstaller build script for FretBurstStudio
# Windows PowerShell script

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "FretBurstStudio PyInstaller Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if PyInstaller is installed
try {
    python -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller not found"
    }
} catch {
    Write-Host "ERROR: PyInstaller is not installed!" -ForegroundColor Red
    Write-Host "Please install it with: pip install pyinstaller" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[1/3] Cleaning previous builds..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
Write-Host "Done." -ForegroundColor Green
Write-Host ""

Write-Host "[2/3] Running PyInstaller..." -ForegroundColor Yellow
# PyQt6 is excluded in the spec file and via custom hooks
python -m PyInstaller FretBurstStudio.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller build failed!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Done." -ForegroundColor Green
Write-Host ""

Write-Host "[3/3] Build complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Executable location: dist\FretBurstStudio.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now test the executable or create an installer." -ForegroundColor Yellow
Read-Host "Press Enter to exit"

