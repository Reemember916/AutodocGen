@echo off
setlocal

cd /d "%~dp0"

echo [INFO] PROJECT RS422 Host Windows package build
echo [INFO] Working dir: %CD%
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [ERR] python not found. Install Python 3.8.x first.
    pause
    exit /b 1
)

python --version
echo.

echo [INFO] Installing build dependencies...
python -m pip install --upgrade pip
python -m pip install pyserial==3.5 pyinstaller==5.13.2
if errorlevel 1 (
    echo [ERR] dependency install failed
    pause
    exit /b 2
)

echo.
echo [INFO] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [INFO] Building...
python -m PyInstaller --clean --noconfirm rs422_host_gui_win7.spec
if errorlevel 1 (
    echo [ERR] PyInstaller build failed
    pause
    exit /b 3
)

echo.
echo [OK] Build finished.
echo [OK] Run: %CD%\dist\PROJECT_RS422_Host\PROJECT_RS422_Host.exe
echo [OK] Copy the whole folder "dist\PROJECT_RS422_Host" to Windows 7.
echo.
pause
