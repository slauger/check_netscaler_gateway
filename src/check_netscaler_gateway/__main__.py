"""
Entry point for python -m check_netscaler_gateway and the console script
"""

import sys

from check_netscaler_gateway.cli import main

if __name__ == "__main__":
    sys.exit(main())
