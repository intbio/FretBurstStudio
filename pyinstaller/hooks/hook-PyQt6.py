# Custom hook to prevent PyQt6 from being processed
# This prevents PyInstaller from collecting PyQt6 when PySide6 is used
# By defining an empty datas and binaries list, we prevent collection

# Explicitly set empty collections to prevent PyInstaller from processing PyQt6
datas = []
binaries = []
hiddenimports = []

