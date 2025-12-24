@echo off
REM Build script using Nuitka instead of PyInstaller
REM Nuitka often handles PyTorch DLLs better than PyInstaller

REM Change to script directory first
cd /d "%~dp0"

echo ========================================
echo Building with Nuitka (Alternative to PyInstaller)
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 goto no_python

REM Check if Nuitka is installed
python -c "import nuitka" 2>nul
if errorlevel 1 goto install_nuitka

REM Check for fast build mode
if "%1"=="--fast" goto fast_build

echo.
echo Cleaning previous build...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "FREE_Football_Analysis.build" rmdir /s /q "FREE_Football_Analysis.build"
if exist "FREE_Football_Analysis.dist" rmdir /s /q "FREE_Football_Analysis.dist"

:fast_build
echo.
echo Building with Nuitka...
if "%1"=="--fast" echo FAST MODE: Using cached files for faster rebuild...
if not "%1"=="--fast" echo This may take a while...
echo.
echo TIP: Use "BUILD_WITH_NUITKA.bat --fast" for faster rebuilds (skips cleaning)
echo.

REM Change to project root directory
cd /d "%~dp0\.."
if errorlevel 1 goto cd_error

REM Get number of CPU cores for parallel compilation
echo Detecting CPU cores...
set CORES=4
cd /d "%~dp0"
python get_cores.py > cores_temp.txt 2>nul
if exist cores_temp.txt goto read_cores
goto set_cores

:read_cores
set /p CORES=<cores_temp.txt
del cores_temp.txt >nul 2>&1

:set_cores
cd /d "%~dp0\.."
if "%CORES%"=="" set CORES=4
if "%CORES%"=="0" set CORES=4
echo Using %CORES% CPU cores for parallel compilation (this will speed up the build significantly)...
echo.

REM Verify we're in the correct directory
if not exist "run_desktop_app.py" goto no_file

REM Run Nuitka with optimizations for faster build
REM Note: Nuitka build can take 30-60 minutes for large projects with PyTorch
echo WARNING: Nuitka build may take 30-60 minutes. Please be patient...
echo The build is running in the background. You can check progress below.
echo.
echo Including Qt plugins (especially multimedia) for video playback...
python -m nuitka --standalone --windows-console-mode=force --jobs=%CORES% --assume-yes-for-downloads --enable-plugin=pyqt6 --include-qt-plugins=multimedia,platforms --include-module=torch --include-module=ultralytics --include-module=cv2 --include-module=numpy --include-module=pandas --include-module=sklearn --include-module=scipy --include-module=matplotlib --include-module=openpyxl --include-module=supervision --include-module=roboflow --include-package-data=ultralytics --include-package-data=torch --include-data-dir=models=models --include-data-dir=frontend=frontend --include-data-dir=demos=demos --include-data-file=translations.xlsx=translations.xlsx --include-data-file=openh264-1.8.0-win64.dll=openh264-1.8.0-win64.dll --windows-icon-from-ico=football.ico --output-dir="Build V1.0.0\dist" --output-filename=FREE_Football_Analysis.exe --show-progress --show-memory run_desktop_app.py

if errorlevel 1 goto build_error

echo.
echo ========================================
echo Build complete!
echo ========================================
echo.
echo Executable should be in: Build V1.0.0\dist\run_desktop_app.dist\
echo.
pause
exit /b 0

:no_python
echo ERROR: Python is not found in PATH!
echo Please make sure Python is installed and added to PATH.
pause
exit /b 1

:install_nuitka
echo Nuitka is not installed. Installing...
pip install nuitka
if errorlevel 1 goto install_error
goto :eof

:install_error
echo ERROR: Failed to install Nuitka
pause
exit /b 1

:cd_error
echo ERROR: Failed to change to project root directory
pause
exit /b 1

:no_file
echo ERROR: run_desktop_app.py not found!
echo Current directory: %CD%
echo Please make sure you are running this from the project root.
pause
exit /b 1

:build_error
echo.
echo ERROR: Nuitka build failed
pause
exit /b 1
