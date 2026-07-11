@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "INSTALLER=%SCRIPT_DIR%LLVM-14.0.6-win64.exe"
set "TARGET_DIR=%SCRIPT_DIR%llvm"

if not exist "%INSTALLER%" (
  echo [ERROR] Installer not found: %INSTALLER%
  exit /b 1
)

if exist "%TARGET_DIR%\bin\clangd.exe" (
  echo [INFO] clangd already installed at %TARGET_DIR%\bin\clangd.exe
  exit /b 0
)

echo [INFO] Installing LLVM/clangd into %TARGET_DIR%
"%INSTALLER%" /S /D=%TARGET_DIR%
if errorlevel 1 (
  echo [ERROR] LLVM installer failed with code %errorlevel%
  exit /b %errorlevel%
)

if not exist "%TARGET_DIR%\bin\clangd.exe" (
  echo [ERROR] clangd.exe was not found after install.
  exit /b 2
)

echo [OK] clangd installed: %TARGET_DIR%\bin\clangd.exe
exit /b 0
