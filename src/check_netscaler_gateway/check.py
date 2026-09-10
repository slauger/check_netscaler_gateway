"""
The gateway login check: orchestrates login, resource enumeration and logout
"""

from typing import Any, Dict, List, Optional

from check_netscaler_gateway.client import gateway, storefront
from check_netscaler_gateway.client.session import GatewaySession
from check_netscaler_gateway.constants import STATE_CRITICAL, STATE_OK, STATE_WARNING


class CheckResult:
    """Result of a check execution"""

    def __init__(
        self,
        status: int,
        message: str,
        perfdata: Optional[Dict[str, Any]] = None,
        long_output: Optional[List[str]] = None,
    ):
        self.status = status
        self.message = message
        self.perfdata = perfdata or {}
        self.long_output = long_output or []


def run_check(
    session: GatewaySession,
    auth_mode: str = gateway.AUTH_MODE_AUTO,
    warning: Optional[int] = None,
    critical: Optional[int] = None,
) -> CheckResult:
    """
    Perform the full login simulation and evaluate the result

    Args:
        session: Prepared gateway session
        auth_mode: 'auto', 'classic' or 'nfactor'
        warning: Minimum number of resources before WARNING
        critical: Minimum number of resources before CRITICAL

    Returns:
        CheckResult with Nagios status, message and perfdata
    """
    gateway.login(session, auth_mode)
    resources = storefront.list_resources(session)
    logout_ok = gateway.logout(session)

    count = len(resources)
    perfdata = {
        "resources": {
            "value": count,
            "warn": str(warning) if warning else "",
            "crit": str(critical) if critical else "",
            "min": "0",
        }
    }

    messages = [f"{name};" for name in resources]
    status = STATE_OK

    if critical and count < critical:
        status = STATE_CRITICAL
        messages.append(f"Only {count} applications found, expected at least {critical}")
    elif warning and count < warning:
        status = STATE_WARNING
        messages.append(f"Only {count} applications found, expected at least {warning}")

    if not logout_ok:
        if status == STATE_OK:
            status = STATE_WARNING
        messages.append("Logout failed")

    return CheckResult(status, " ".join(messages), perfdata=perfdata)
