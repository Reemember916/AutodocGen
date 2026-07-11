@echo off
setlocal

REM Win7 build recommendation:
REM 1) Use CPython 3.8.x (last stable branch for older Windows compatibility)
REM 2) Use PyInstaller 5.x for better Win7 compatibility

python --version
if errorlevel 1 (
  echo Python not found. Please install Python 3.8.x first.
  exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

python -m pip install pyinstaller==5.13.2
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --onefile --windowed --name DocDiffWin7 gui_app.py
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo EXE path: dist\DocDiffWin7.exe
endlocal
