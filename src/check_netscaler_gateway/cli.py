"""
Command-line interface for check_netscaler_gateway
"""

import argparse
import os
import sys
import traceback
from typing import Optional, Union

from check_netscaler_gateway import __version__
from check_netscaler_gateway.check import run_check
from check_netscaler_gateway.client.exceptions import (
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayException,
    GatewayTimeoutError,
    UnsupportedAuthFlowError,
)
from check_netscaler_gateway.client.gateway import AUTH_MODE_AUTO, AUTH_MODES
from check_netscaler_gateway.client.session import GatewaySession
from check_netscaler_gateway.constants import (
    DEFAULT_STORE,
    DEFAULT_TIMEOUT,
    STATE_CRITICAL,
    STATE_UNKNOWN,
)
from check_netscaler_gateway.output.nagios import NagiosOutput


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser (options compatible with the Perl plugin)"""
    parser = argparse.ArgumentParser(
        prog="check_netscaler_gateway",
        description=(
            "Nagios monitoring plugin for Citrix NetScaler Gateway. The plugin "
            "emulates a full login process on a NetScaler Gateway vServer and "
            "checks if there are any available resources."
        ),
        epilog="https://github.com/slauger/check_netscaler_gateway",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "-H",
        "--hostname",
        default=os.getenv("NETSCALER_GATEWAY_HOST"),
        help="Hostname of the NetScaler Gateway vServer (env: NETSCALER_GATEWAY_HOST)",
    )
    parser.add_argument(
        "-u",
        "--username",
        default=os.getenv("NETSCALER_GATEWAY_USER"),
        help="Username to log into the gateway as (env: NETSCALER_GATEWAY_USER)",
    )
    parser.add_argument(
        "-p",
        "--password",
        default=os.getenv("NETSCALER_GATEWAY_PASS"),
        help="Password for the login username (env: NETSCALER_GATEWAY_PASS)",
    )
    parser.add_argument(
        "-S",
        "--store",
        default=DEFAULT_STORE,
        help=f"Name of the store in StoreFront (default: {DEFAULT_STORE})",
    )
    parser.add_argument(
        "-w",
        "--warning",
        type=int,
        help="Warning threshold for the number of found applications (minimum)",
    )
    parser.add_argument(
        "-c",
        "--critical",
        type=int,
        help="Critical threshold for the number of found applications (minimum)",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--auth-mode",
        choices=AUTH_MODES,
        default=AUTH_MODE_AUTO,
        help=(
            "Authentication flow: classic (/cgi/login), nfactor (13.1+ firmware) "
            "or auto detection (default: auto)"
        ),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify TLS certificates (default: no verification, like v1.x)",
    )
    parser.add_argument(
        "--ca-file",
        help="Path to a CA bundle for TLS verification (implies --verify)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print one line per HTTP request to stderr",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Print every HTTP request and response to stderr (credentials masked)",
    )

    return parser


def main(argv: Optional[list] = None) -> int:
    """Run the plugin and return the Nagios exit code"""
    parser = create_parser()
    args = parser.parse_args(argv)

    missing = [
        name
        for name, value in (
            ("--hostname", args.hostname),
            ("--username", args.username),
            ("--password", args.password),
        )
        if not value
    ]
    if missing:
        parser.error(f"the following arguments are required: {', '.join(missing)}")

    verify: Union[bool, str] = args.ca_file if args.ca_file else args.verify

    session = GatewaySession(
        hostname=args.hostname,
        username=args.username,
        password=args.password,
        store=args.store,
        timeout=args.timeout,
        verify=verify,
        verbose=args.verbose,
        debug=args.debug,
    )

    try:
        result = run_check(
            session,
            auth_mode=args.auth_mode,
            warning=args.warning,
            critical=args.critical,
        )
        status = result.status
        output = NagiosOutput.format_output(
            result.status, result.message, result.perfdata, result.long_output
        )
    except UnsupportedAuthFlowError as e:
        status = STATE_UNKNOWN
        output = NagiosOutput.format_output(status, str(e))
    except (
        GatewayAuthenticationError,
        GatewayConnectionError,
        GatewayTimeoutError,
        GatewayException,
    ) as e:
        status = STATE_CRITICAL
        output = NagiosOutput.format_output(status, str(e))
    except KeyboardInterrupt:
        status = STATE_UNKNOWN
        output = NagiosOutput.format_output(status, "Interrupted by user")
    except Exception as e:
        status = STATE_UNKNOWN
        output = NagiosOutput.format_output(status, f"Unexpected error: {e}")
        if args.verbose:
            traceback.print_exc(file=sys.stderr)

    print(output)
    return status
