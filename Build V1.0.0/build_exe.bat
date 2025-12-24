@echo off
REM Build script for FREE Football Analysis Desktop Application
REM Version 1.0.0

REM Change to script directory
cd /d "%~dp0"

echo ========================================
echo Building FREE Football Analysis v1.0.0
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not found in PATH!
    echo Please make sure Python is installed and added to PATH.
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
echo Checking PyInstaller...
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo ERROR: PyInstaller is not installed!
    echo Please install it using: pip install pyinstaller
    pause
    exit /b 1
)
echo PyInstaller found.
echo.

echo Checking required dependencies...
echo.

REM Check and install lapx (required by ultralytics)
echo Checking lapx...
python -c "import lapx" 2>nul
if errorlevel 1 goto install_lapx
echo lapx found.
goto skip_lapx_install

:install_lapx
echo lapx not found. Installing lapx (required by ultralytics)...
python -m pip install lapx --quiet
if errorlevel 1 (
    echo WARNING: Failed to install lapx. Build may fail.
    echo You can try installing manually: pip install lapx
) else (
    echo lapx installed successfully.
)

:skip_lapx_install
echo.

echo Cleaning previous build...
if exist "dist" (
    echo Removing dist folder...
    rmdir /s /q "dist"
)
if exist "build" (
    echo Removing build folder...
    rmdir /s /q "build"
)

echo.
echo Starting PyInstaller build...
echo Current directory: %CD%
echo Spec file: %CD%\FREE_Football_Analysis.spec
echo.

REM Check if spec file exists
if not exist "FREE_Football_Analysis.spec" (
    echo ERROR: Spec file not found: FREE_Football_Analysis.spec
    echo Please make sure you are running this script from the Build V1.0.0 folder.
    pause
    exit /b 1
)

REM Run PyInstaller with the spec file
echo Running PyInstaller...
pyinstaller FREE_Football_Analysis.spec --log-level=DEBUG

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    echo Please check the error messages above for details.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo The executable can be found in: dist\FREE_Football_Analysis\FREE_Football_Analysis.exe
echo.
echo NOTE: You need to distribute the entire folder: dist\FREE_Football_Analysis
echo       (not just the .exe file)
echo.
pause

