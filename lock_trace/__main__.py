"""Entry point for lock-trace when run as a module."""

import sys

# Add the lock_trace package to the path for PyInstaller
if getattr(sys, "frozen", False):
    # We're running in a PyInstaller bundle
    bundle_dir = sys._MEIPASS
    sys.path.insert(0, bundle_dir)

from lock_trace.cli import cli_main

if __name__ == "__main__":
    cli_main()
