"""
Constants and exit codes for Nagios/Icinga monitoring plugins
"""

# Nagios/Icinga plugin exit codes
STATE_OK = 0
STATE_WARNING = 1
STATE_CRITICAL = 2
STATE_UNKNOWN = 3

# State names
STATE_NAMES = {
    STATE_OK: "OK",
    STATE_WARNING: "WARNING",
    STATE_CRITICAL: "CRITICAL",
    STATE_UNKNOWN: "UNKNOWN",
}

# Plugin identity
SHORTNAME = "NetScaler Gateway"

# Default values
DEFAULT_STORE = "Store"
DEFAULT_TIMEOUT = 15
