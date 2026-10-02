"""
Exceptions for the NetScaler Gateway client
"""

from typing import Optional


class GatewayException(Exception):
    """Base exception for all gateway client errors"""

    pass


class GatewayAuthenticationError(GatewayException):
    """Authentication against the gateway failed"""

    pass


class GatewayConnectionError(GatewayException):
    """Connection to the gateway failed"""

    pass


class GatewayTimeoutError(GatewayException):
    """Request timed out"""

    pass


class UnexpectedResponseError(GatewayException):
    """A request returned an unexpected status code or redirect"""

    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code


class CsrfTokenError(GatewayException):
    """StoreFront did not hand out a CsrfToken cookie"""

    pass


class UnsupportedAuthFlowError(GatewayException):
    """The gateway requires an authentication flow this plugin does not support"""

    pass
