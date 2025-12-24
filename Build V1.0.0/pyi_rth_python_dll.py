"""
PyInstaller runtime hook to ensure Python DLL is found and handle DLL loading errors

This hook runs early in the boot process to help locate DLLs.
Note: PyInstaller's bootloader loads the Python DLL before this hook runs,
but this can help with DLL dependencies.
"""
import os
import sys
from pathlib import Path

# In one-directory mode, Python DLL should be in the same directory as the exe
if hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle - DLLs are in the same directory as the exe
    exe_dir = Path(sys.executable).parent
    base_path = Path(sys._MEIPASS)
else:
    # Development mode
    exe_dir = Path(sys.executable).parent
    base_path = exe_dir

# Add exe directory to DLL search path (most important - where Python DLL should be)
# PyInstaller places Python DLL in the same directory as the executable
if sys.platform == 'win32':
    try:
        # Add executable directory first (highest priority)
        os.add_dll_directory(str(exe_dir))
    except (OSError, AttributeError):
        pass  # Ignore errors on older Python versions
    
    try:
        # Also add base path as fallback
        os.add_dll_directory(str(base_path))
    except (OSError, AttributeError):
        pass
    
    # Add torch/lib directory if it exists (for torch DLLs)
    try:
        torch_lib_path = base_path / 'torch' / 'lib'
        if torch_lib_path.exists():
            os.add_dll_directory(str(torch_lib_path))
    except (OSError, AttributeError):
        pass

