# Lazy import torch to avoid DLL loading issues at import time
# Import torch only when get_device() is actually called

def get_device() -> str:
    """Get the best available device (cuda, mps, or cpu)"""
    try:
        import torch
        
        if torch.cuda.is_available():
            return "cuda"  
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            return "mps"  # Metal Performance Shaders (Apple Silicon)
        else:
            return "cpu"
    except Exception as e:
        # If torch fails to load, fallback to CPU
        import sys
        print(f"Warning: Could not import torch: {e}", file=sys.stderr)
        print("Warning: Falling back to CPU device", file=sys.stderr)
        return "cpu"