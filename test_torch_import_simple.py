#!/usr/bin/env python
"""Simple test to verify torch and ultralytics can be imported"""
import sys

# Remove dist from path to use site-packages
sys.path = [p for p in sys.path if 'dist' not in p]

print("Testing torch import...")
try:
    import torch
    print(f"OK: torch imported successfully (version: {torch.__version__})")
    print(f"  torch file: {torch.__file__}")
    print(f"  Has CUDA: {torch.cuda.is_available()}")
except Exception as e:
    print(f"FAILED: torch import failed: {e}")
    sys.exit(1)

print("\nTesting ultralytics import...")
try:
    import ultralytics
    print(f"OK: ultralytics imported successfully")
except Exception as e:
    print(f"FAILED: ultralytics import failed: {e}")
    sys.exit(1)

print("\n[SUCCESS] Both torch and ultralytics imported successfully!")
print("You can now run the application or rebuild the executable.")

