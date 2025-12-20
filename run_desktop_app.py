#!/usr/bin/env python
"""
Launcher script for FREE Football Analysis Desktop Application
Run this script to start the desktop GUI application.
"""

import sys
import os
import traceback

# Enable faulthandler to catch crashes at C/C++ level
try:
    import faulthandler
    # Write to stderr and also to a file
    faulthandler.enable()
    # Also dump to file for debugging
    if hasattr(sys, '_MEIPASS'):
        fault_log = os.path.join(os.path.dirname(sys.executable), 'crash.log')
    else:
        fault_log = 'crash.log'
    try:
        fault_file = open(fault_log, 'w')
        faulthandler.enable(file=fault_file, all_threads=True)
        print(f"Faulthandler enabled. Crash logs will be written to: {fault_log}")
    except:
        pass  # If we can't open file, just use stderr
except ImportError:
    print("Warning: faulthandler not available")
except Exception as e:
    print(f"Warning: Could not enable faulthandler: {e}")

# Set up exception hook to catch all unhandled exceptions
def excepthook(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    error_msg = f"\n{'='*60}\n"
    error_msg += f"UNHANDLED EXCEPTION: {exc_type.__name__}: {exc_value}\n"
    error_msg += f"{'='*60}\n"
    error_msg += "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    error_msg += f"{'='*60}\n"
    
    try:
        print(error_msg, file=sys.stderr)
        print(error_msg)
    except:
        pass
    
    try:
        input("\nPress Enter to exit...")
    except:
        pass

sys.excepthook = excepthook

# Add current directory to path
if hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle mode
    BASE_DIR = sys._MEIPASS
    EXE_DIR = os.path.dirname(sys.executable)
    # Add BASE_DIR to path for imports
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
else:
    # Development mode
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    EXE_DIR = BASE_DIR
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)

# Create output and logs directories early
if hasattr(sys, '_MEIPASS'):
    # PyInstaller bundle mode - create directories in executable directory
    output_dir = os.path.join(EXE_DIR, "output")
    logs_dir = os.path.join(EXE_DIR, "logs")
    
    # Add torch/lib to PATH environment variable to help with DLL loading
    # This is critical for Windows DLL signature validation issues
    torch_lib_path = os.path.join(BASE_DIR, "torch", "lib")
    if os.path.exists(torch_lib_path):
        current_path = os.environ.get('PATH', '')
        if torch_lib_path not in current_path:
            os.environ['PATH'] = torch_lib_path + os.pathsep + current_path
            # Also add exe directory
            if EXE_DIR not in current_path:
                os.environ['PATH'] = EXE_DIR + os.pathsep + os.environ['PATH']
else:
    # Development mode
    output_dir = os.path.join(EXE_DIR, "output")
    logs_dir = os.path.join(EXE_DIR, "logs")

try:
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
except Exception as e:
    print(f"Warning: Could not create output/logs directories: {e}", file=sys.stderr)

def main():
    """Main entry point with error handling"""
    try:
        print("Starting FREE Football Analysis...")
        print(f"Python version: {sys.version}")
        print(f"Base directory: {BASE_DIR}")
        print(f"sys.path: {sys.path[:3]}...")  # Show first 3 entries
        
        # Import and run
        print("Importing desktop_app module...")
        sys.stdout.flush()  # Force output
        try:
            print("  - Attempting to import frontend.desktop_app...")
            sys.stdout.flush()
            
            # Try importing step by step
            print("  - Importing frontend module...")
            sys.stdout.flush()
            import frontend
            
            print("  - Importing frontend.desktop_app...")
            sys.stdout.flush()
            from frontend.desktop_app import main as app_main
            print("✓ desktop_app module imported successfully")
            sys.stdout.flush()
        except Exception as import_error:
            error_detail = f"✗ Failed to import desktop_app: {import_error}"
            print(error_detail, file=sys.stderr)
            print(error_detail)
            traceback_str = traceback.format_exc()
            print(f"Full traceback:\n{traceback_str}", file=sys.stderr)
            print(f"Full traceback:\n{traceback_str}")
            sys.stderr.flush()
            sys.stdout.flush()
            raise
        
        print("Starting application...")
        app_main()
        
    except ImportError as e:
        error_msg = f"Import Error: {str(e)}\n\nFull traceback:\n{traceback.format_exc()}"
        print(error_msg, file=sys.stderr)
        
        # Try to show error in GUI if possible
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Import Error")
            msg.setText(f"Failed to import required module:\n{str(e)}")
            msg.setDetailedText(traceback.format_exc())
            msg.exec()
        except:
            pass
            
        input("\nPress Enter to exit...")
        sys.exit(1)
        
    except Exception as e:
        error_msg = f"\n{'='*60}\n"
        error_msg += f"ERROR: {type(e).__name__}: {str(e)}\n"
        error_msg += f"{'='*60}\n"
        error_msg += f"Full traceback:\n{traceback.format_exc()}\n"
        error_msg += f"{'='*60}\n"
        print(error_msg, file=sys.stderr)
        print(error_msg)  # Also print to stdout
        
        # Try to show error in GUI if possible
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("Application Error")
            msg.setText(f"An error occurred:\n{str(e)}")
            msg.setDetailedText(traceback.format_exc())
            msg.exec()
        except Exception as gui_error:
            print(f"Could not show GUI error dialog: {gui_error}", file=sys.stderr)
            
        print("\nPress Enter to exit...")
        try:
            input()
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()

