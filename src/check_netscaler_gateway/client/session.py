"""
HTTP session for the NetScaler Gateway login simulation
"""

import re
import sys
from typing import Optional, Union

import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

from check_netscaler_gateway.client.exceptions import (
    GatewayConnectionError,
    GatewayTimeoutError,
)

MASK = "********"

# Patterns for values that must never show up in debug output
_BODY_SECRET_RE = re.compile(r"(passwd=)[^&]*")
_SECRET_HEADERS = {"cookie", "set-cookie", "authorization"}


class GatewaySession:
    """Holds the requests session, cookie jar and debug/verbose output"""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str,
        store: str = "Store",
        timeout: int = 15,
        verify: Union[bool, str] = False,
        verbose: bool = False,
        debug: bool = False,
        ssl: bool = True,
        port: Optional[int] = None,
    ):
        """
        Initialize gateway session

        Args:
            hostname: Hostname of the NetScaler Gateway vServer
            username: Username for the login simulation
            password: Password for the login simulation
            store: StoreFront store name (URL becomes /Citrix/<store>Web)
            timeout: Request timeout in seconds
            verify: Verify TLS certificates (bool or path to CA bundle)
            verbose: Print one line per request to stderr
            debug: Print full requests and responses to stderr (secrets masked)
            ssl: Use HTTPS (default: True; HTTP only used by the test suite)
            port: Custom port (default: 443 for HTTPS, 80 for HTTP)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.store = store
        self.timeout = timeout
        self.verify = verify
        self.verbose = verbose
        self.debug = debug

        if ssl and not verify:
            urllib3.disable_warnings(InsecureRequestWarning)

        protocol = "https" if ssl else "http"
        if port:
            netloc = f"{hostname}:{port}"
        else:
            netloc = hostname
        self.base_url = f"{protocol}://{netloc}"
        self.store_url = f"{self.base_url}/Citrix/{store}Web"

        self.session = requests.Session()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Perform a request without following redirects and map transport errors

        The gateway login flow makes decisions based on Location headers, so
        redirects are never followed automatically.

        Raises:
            GatewayTimeoutError: If the request times out
            GatewayConnectionError: If the connection fails
        """
        kwargs.setdefault("timeout", self.timeout)
        kwargs.setdefault("verify", self.verify)
        kwargs.setdefault("allow_redirects", False)

        try:
            response = self.session.request(method, url, **kwargs)
        except requests.exceptions.Timeout as e:
            raise GatewayTimeoutError(f"request to {url} timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise GatewayConnectionError(f"connection to {url} failed: {e}") from e
        except requests.exceptions.RequestException as e:
            raise GatewayConnectionError(f"request to {url} failed: {e}") from e

        if self.verbose:
            print(
                f"** {method} {url} ==> {response.status_code} {response.reason}", file=sys.stderr
            )
        if self.debug:
            self._dump(response)

        return response

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)

    def cookie(self, name: str) -> Optional[str]:
        """Read a cookie value from the jar"""
        return self.session.cookies.get(name)

    def _dump(self, response: requests.Response) -> None:
        """Print full request and response to stderr with secrets masked"""
        req = response.request
        print(f"----- request: {req.method} {req.url}", file=sys.stderr)
        for name, value in req.headers.items():
            print(f"{name}: {self._mask_header(name, value)}", file=sys.stderr)
        if req.body:
            body = req.body if isinstance(req.body, str) else repr(req.body)
            print(f"\n{self._mask_body(body)}", file=sys.stderr)
        print(f"----- response: {response.status_code} {response.reason}", file=sys.stderr)
        for name, value in response.headers.items():
            print(f"{name}: {self._mask_header(name, value)}", file=sys.stderr)
        if response.text:
            print(f"\n{response.text}", file=sys.stderr)
        print("-----", file=sys.stderr)

    def _mask_header(self, name: str, value: str) -> str:
        if name.lower() in _SECRET_HEADERS:
            return MASK
        return value

    def _mask_body(self, body: str) -> str:
        body = _BODY_SECRET_RE.sub(rf"\g<1>{MASK}", body)
        if self.password:
            body = body.replace(self.password, MASK)
        return body
