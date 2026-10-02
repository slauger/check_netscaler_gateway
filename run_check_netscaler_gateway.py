#!/usr/bin/env python3
"""
PyInstaller entry point that avoids relative-import problems in the frozen binary
"""

import sys

from check_netscaler_gateway.cli import main

if __name__ == "__main__":
    sys.exit(main())
