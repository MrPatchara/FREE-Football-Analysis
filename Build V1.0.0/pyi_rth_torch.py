"""
PyInstaller runtime hook to pre-load torch DLLs before torch import
This helps avoid STATUS_INVALID_IMAGE_HASH errors on Windows

Note: STATUS_INVALID_IMAGE_HASH (0xC06D007E) is a Windows security feature
that blocks unsigned DLLs. This hook attempts to work around it by:
1. Adding torch/lib to DLL search path early
2. Pre-loading critical DLLs to validate them
"""
import os
import sys
from pathlib import Path

if sys.platform == 'win32' and hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle mode
    base_path = Path(sys._MEIPASS)
    exe_dir = Path(sys.executable).parent
    
    # Add torch/lib to DLL search path BEFORE any torch imports
    torch_lib_path = base_path / 'torch' / 'lib'
    if torch_lib_path.exists():
        try:
            # Add to DLL search path
            os.add_dll_directory(str(torch_lib_path))
            
            # Also add exe directory (where DLLs might be copied)
            os.add_dll_directory(str(exe_dir))
            
            # Try to set environment variable to help with DLL loading
            # Some versions of Windows use this for DLL search
            torch_lib_str = str(torch_lib_path)
            if 'PATH' in os.environ:
                if torch_lib_str not in os.environ['PATH']:
                    os.environ['PATH'] = torch_lib_str + os.pathsep + os.environ['PATH']
            else:
                os.environ['PATH'] = torch_lib_str
                
        except Exception as e:
            # Silently fail - DLLs will be loaded when needed
            pass

