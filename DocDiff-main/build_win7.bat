@echo off
setlocal EnableExtensions

REM ============================================================
REM DocDiff Win7 one-file GUI build
REM Recommended host: Windows 7 + Python 3.8.x + pip online/offline
REM Output: dist\DocDiffWin7.exe
REM ============================================================

cd /d "%~dp0"

echo.
echo [1/5] Python version
python --version
if errorlevel 1 (
  echo ERROR: Python not found. Install CPython 3.8.x and add to PATH.
  exit /b 1
)

echo.
echo [2/5] Upgrade pip
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo.
echo [3/5] Install project dependencies
python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
REM openpyxl optional: xlsx ticket ledger
python -m pip install openpyxl>=3.0.0
if errorlevel 1 (
  echo WARN: openpyxl install failed. .xlsx tickets will be unavailable; CSV/JSON still work.
)

echo.
echo [4/5] Install PyInstaller 5.13.2 ^(Win7 friendly^)
python -m pip install pyinstaller==5.13.2
if errorlevel 1 exit /b 1

echo.
echo [5/5] Build one-file windowed EXE
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist DocDiffWin7.spec del /f /q DocDiffWin7.spec

pyinstaller --noconfirm --clean --onefile --windowed ^
  --name DocDiffWin7 ^
  --paths . ^
  --hidden-import tickets ^
  --hidden-import tickets.tickets ^
  --hidden-import tickets.match ^
  --hidden-import tickets.strategy ^
  --hidden-import tickets.llm_match ^
  --hidden-import diff.collect_changes ^
  --hidden-import diff.block_diff ^
  --hidden-import canonical.normalize ^
  --hidden-import code_diff.collect_code_changes ^
  --hidden-import render.change_order ^
  --hidden-import render.code_change_order ^
  --hidden-import extractor.reader ^
  --hidden-import extractor.text_extract ^
  --hidden-import model.ast ^
  --collect-submodules lxml ^
  --collect-submodules docx ^
  gui_app.py

if errorlevel 1 (
  echo.
  echo BUILD FAILED.
  exit /b 1
)

echo.
echo ============================================================
echo Build complete.
echo EXE: %cd%\dist\DocDiffWin7.exe
echo ============================================================
dir dist\DocDiffWin7.exe
endlocal
