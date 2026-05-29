#!/usr/bin/env python3
"""
Run all script for BAT3 system.

Usage:
    python run_all.py dev   # Start backend + UI dev server concurrently
    python run_all.py prod  # Build UI, then start backend serving static files
    python run_all.py api   # Start backend only
"""

import argparse
import os
import signal
import subprocess
import sys
import time

# Constants
API_PORT = 8000
UI_DIR = "ui"
API_MODULE = "src_new.api.main:app"

# Track child processes for dev mode
_children = []


def _shutdown(signum, frame):
    """Signal handler to gracefully shut down child processes."""
    print("\nShutting down...")
    for proc in _children:
        if proc.poll() is None:
            proc.terminate()
    
    # Wait up to 5 seconds for processes to terminate
    for proc in _children:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    
    sys.exit(0)


def run_dev():
    """Run backend and UI dev server concurrently."""
    print(f"Starting API server on port {API_PORT}...")
    print(f"Starting UI dev server...")
    
    # Register signal handler before spawning processes
    signal.signal(signal.SIGINT, _shutdown)
    
    # Start backend with reload
    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        API_MODULE,
        "--host", "0.0.0.0",
        "--port", str(API_PORT),
        "--reload"
    ]
    
    # Start UI dev server
    ui_cmd = ["npm", "run", "dev"]
    
    backend_proc = subprocess.Popen(backend_cmd, cwd=os.getcwd())
    ui_proc = subprocess.Popen(ui_cmd, cwd=UI_DIR)
    
    _children.extend([backend_proc, ui_proc])
    
    print(f"API running at http://localhost:{API_PORT}")
    print("UI running at http://localhost:8081")
    
    # Wait for both processes
    while True:
        backend_returncode = backend_proc.poll()
        ui_returncode = ui_proc.poll()
        
        if backend_returncode is not None and ui_returncode is not None:
            # Both processes have exited
            sys.exit(max(backend_returncode, ui_returncode))
        
        time.sleep(0.1)


def run_prod():
    """Build UI and start backend serving static files."""
    print("Building UI...")
    
    # Build the UI
    build_result = subprocess.run(
        ["npm", "run", "build"],
        cwd=UI_DIR
    )
    
    if build_result.returncode != 0:
        print(f"Error: UI build failed with exit code {build_result.returncode}")
        sys.exit(build_result.returncode)
    
    print("Starting API server...")
    
    # Start backend without reload
    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        API_MODULE,
        "--host", "0.0.0.0",
        "--port", str(API_PORT)
    ]
    
    # Run backend directly so Ctrl+C works naturally
    os.execvp(sys.executable, backend_cmd)


def run_api():
    """Start backend only."""
    print(f"Starting API server on port {API_PORT}...")
    
    # Start backend with reload
    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        API_MODULE,
        "--host", "0.0.0.0",
        "--port", str(API_PORT),
        "--reload"
    ]
    
    print(f"API running at http://localhost:{API_PORT}")
    
    # Run backend directly so Ctrl+C works naturally
    os.execvp(sys.executable, backend_cmd)


def main():
    parser = argparse.ArgumentParser(
        description="Run the BAT3 system in different modes."
    )
    parser.add_argument(
        "mode",
        choices=["dev", "prod", "api"],
        help="Mode to run: 'dev' for development (backend + UI), "
             "'prod' for production (build UI + backend), "
             "'api' for backend only"
    )
    
    args = parser.parse_args()
    
    if args.mode == "dev":
        run_dev()
    elif args.mode == "prod":
        run_prod()
    elif args.mode == "api":
        run_api()


if __name__ == "__main__":
    main()
