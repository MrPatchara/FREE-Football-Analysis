@echo off
REM Clean build folders and temporary files

echo Cleaning build folders...
if exist "dist" (
    echo Removing dist folder...
    rmdir /s /q "dist"
)
if exist "build" (
    echo Removing build folder...
    rmdir /s /q "build"
)
if exist "*.build" (
    echo Removing .build folders...
    for /d %%d in (*.build) do rmdir /s /q "%%d"
)
if exist "*.dist" (
    echo Removing .dist folders...
    for /d %%d in (*.dist) do rmdir /s /q "%%d"
)

echo.
echo Clean complete!
echo.
echo Remaining files:
dir /b
echo.
pause

