#!/usr/bin/env python
"""
Launcher script for FREE Football Analysis Desktop Application
Run this script to start the desktop GUI application.
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from frontend.desktop_app import main

if __name__ == "__main__":
    main()

