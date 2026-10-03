#!/usr/bin/env python3
"""
Executable entry point for Aquile Reader for Ubuntu.
"""

import sys
import os

# Add src to python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from aquile.app import main

if __name__ == "__main__":
    sys.exit(main())
