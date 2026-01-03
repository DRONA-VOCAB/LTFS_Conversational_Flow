#!/usr/bin/env python3
"""Script to run the FastAPI backend server"""
import sys
import os
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir.parent))
sys.path.insert(0, str(backend_dir))

if __name__ == "__main__":
    os.chdir(backend_dir)
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

