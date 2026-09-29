"""
Authentication flows against the NetScaler Gateway vServer

Two flows exist in the wild:

- classic: gateways with the classic portal theme answer POST /cgi/login
  with a 302 to /cgi/setclient?wica. Builds since 13.1-63.x reject a POST
  without an Origin header (302 to /vpn/index.html with NSC_VPNERR=4001),
  so the flow sends one and loads /vpn/index.html first like a browser.
- nfactor: gateways with the RfWebUI theme (/logon/LogonPoint/...) use the
  nFactor protocol under /p/u/. On these gateways /cgi/login is dead and
  just bounces to /vpn/index.html with NSC_VPNERR=4001, so in auto mode a
  rejected classic login falls back to nFactor. The endpoints and the
  request/response shape below were captured from a real 13.1 gateway
  (issue #7).
"""

import re
import xml.etree.ElementTree as ET
from typing import Optional

import requests

from check_netscaler_gateway.client.exceptions import (
    GatewayAuthenticationError,
    UnexpectedResponseError,
    UnsupportedAuthFlowError,
)
from check_netscaler_gateway.client.session import GatewaySession

AUTH_MODE_AUTO = "auto"
AUTH_MODE_CLASSIC = "classic"
AUTH_MODE_NFACTOR = "nfactor"
AUTH_MODES = [AUTH_MODE_AUTO, AUTH_MODE_CLASSIC, AUTH_MODE_NFACTOR]

SETCLIENT_LOCATION = "/cgi/setclient?wica"
LOGON_POINT_MARKER = "/logon/LogonPoint"
LOGON_POINT_PAGE = "/logon/LogonPoint/index.html"
REDIRECT_CODES = (301, 302, 303, 307)

# nFactor endpoints (RfWebUI theme), captured from a live 13.1 gateway
NF_REQUIREMENTS_PATH = "/p/u/getAuthenticationRequirements.do"
NF_DEFAULT_POSTBACK = "/p/u/doAuthentication.do"
NF_SETCLIENT_PATH = "/p/u/setClient.do"
NF_ACCEPT = "application/vnd.citrix.authenticateresponse-1+xml, text/xml, */*; q=0.01"

# the store path the gateway redirects to is announced in the setClient.do
# response (e.g. /Citrix/StoreWeb)
_STORE_PATH_RE = re.compile(r"/Citrix/([A-Za-z0-9_]+)Web")


class _NotNFactorGateway(Exception):
    """Internal signal: the gateway does not expose the nFactor endpoints"""


def login(session: GatewaySession, auth_mode: str = AUTH_MODE_AUTO) -> str:
    """
    Authenticate against the gateway vServer

    Returns:
        The flow that was used ('classic' or 'nfactor')
    """
    if auth_mode == AUTH_MODE_NFACTOR:
        try:
            _nfactor_login(session)
        except _NotNFactorGateway as e:
            raise GatewayAuthenticationError(
                "gateway does not expose the nFactor endpoints (try --auth-mode classic)"
            ) from e
        return AUTH_MODE_NFACTOR

    preamble = _browser_preamble(session)

    # auto: an RfWebUI gateway redirects the login page to /logon/LogonPoint,
    # so the flow is decided before any credentials are sent
    location = preamble.headers.get("Location", "")
    if (
        auth_mode == AUTH_MODE_AUTO
        and preamble.status_code in REDIRECT_CODES
        and LOGON_POINT_MARKER in location
    ):
        _nfactor_login(session)
        return AUTH_MODE_NFACTOR

    response = _post_cgi_login(session)
    location = response.headers.get("Location", "")
    classic_ok = response.status_code in REDIRECT_CODES and location == SETCLIENT_LOCATION

    # auto: if /cgi/login does not accept us (RfWebUI gateways bounce to
    # /vpn/index.html with NSC_VPNERR=4001), try the nFactor flow. If the
    # gateway turns out not to speak nFactor either, report the classic
    # rejection so the message stays meaningful (e.g. wrong credentials).
    if not classic_ok and auth_mode == AUTH_MODE_AUTO:
        try:
            _nfactor_login(session)
            return AUTH_MODE_NFACTOR
        except _NotNFactorGateway:
            pass

    _finish_classic_login(session, response)
    return AUTH_MODE_CLASSIC


def logout(session: GatewaySession) -> bool:
    """
    Logout from the gateway

    Returns:
        True if the logout succeeded, False otherwise (never raises)
    """
    try:
        response = session.get(f"{session.base_url}/cgi/logout")
    except Exception:
        return False
    return response.status_code < 400


def _browser_preamble(session: GatewaySession) -> requests.Response:
    """
    Load the login page like a real browser before posting credentials.

    Also serves as the auto-detect probe: RfWebUI gateways redirect the
    login page to /logon/LogonPoint.
    """
    return session.get(
        f"{session.base_url}/vpn/index.html",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )


def _post_cgi_login(session: GatewaySession) -> requests.Response:
    """Post the credentials to /cgi/login"""
    response = session.post(
        f"{session.base_url}/cgi/login",
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{session.base_url}/vpn/index.html",
            "Origin": session.base_url,
        },
        data={
            "login": session.username,
            "passwd": session.password,
        },
    )
    if response.status_code >= 400:
        raise UnexpectedResponseError(
            f"request to {session.base_url}/cgi/login failed with HTTP {response.status_code}",
            url=f"{session.base_url}/cgi/login",
            status_code=response.status_code,
        )
    return response


def _finish_classic_login(session: GatewaySession, login_response: requests.Response) -> None:
    """Classic flow: expect the 302 to /cgi/setclient?wica, then call it"""
    location = login_response.headers.get("Location", "")
    if login_response.status_code in REDIRECT_CODES:
        if location != SETCLIENT_LOCATION:
            # happens with invalid credentials or missing required headers
            error_code = session.cookie("NSC_VPNERR")
            hint = f", gateway error code {error_code}" if error_code else ""
            raise GatewayAuthenticationError(
                f"request to {session.base_url}/cgi/login redirected to '{location}' "
                f"instead of '{SETCLIENT_LOCATION}' (check credentials and auth-mode{hint})"
            )

    response = session.post(f"{session.base_url}{location or SETCLIENT_LOCATION}")
    if response.status_code >= 300:
        raise UnexpectedResponseError(
            f"request to {session.base_url}{SETCLIENT_LOCATION} failed with "
            f"HTTP {response.status_code}",
            url=f"{session.base_url}{SETCLIENT_LOCATION}",
            status_code=response.status_code,
        )


def _nfactor_login(session: GatewaySession) -> None:
    """
    nFactor flow (RfWebUI theme): load the logon page, fetch the
    authentication requirements, post the credentials to the postback URL
    and finish with setClient.do.

    Endpoints, field names and the success criterion were captured from a
    live 13.1 gateway (issue #7).
    """
    # load the RfWebUI logon page to establish the session cookies
    session.get(
        f"{session.base_url}{LOGON_POINT_PAGE}",
        headers={"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"},
    )

    requirements_url = f"{session.base_url}{NF_REQUIREMENTS_PATH}"
    response = session.post(
        requirements_url,
        headers={
            "Accept": NF_ACCEPT,
            "Content-Length": "0",
            "X-Citrix-IsUsingHTTPS": "Yes",
        },
    )
    if response.status_code == 404:
        raise _NotNFactorGateway()
    if response.status_code >= 300:
        raise UnexpectedResponseError(
            f"request to {requirements_url} failed with HTTP {response.status_code}",
            url=requirements_url,
            status_code=response.status_code,
        )

    state_context, postback = _parse_requirements(response.text)

    auth_url = f"{session.base_url}{postback}"
    response = session.post(
        auth_url,
        headers={"Accept": NF_ACCEPT, "X-Citrix-IsUsingHTTPS": "Yes"},
        data={
            "login": session.username,
            "passwd": session.password,
            "savecredentials": "false",
            "nsg-x1-logon-button": "Log On",
            "StateContext": state_context,
        },
    )
    if response.status_code >= 300:
        raise UnexpectedResponseError(
            f"request to {auth_url} failed with HTTP {response.status_code}",
            url=auth_url,
            status_code=response.status_code,
        )

    _check_authentication_result(session, response.text)

    # tell the gateway which client to use; the resource listing works without
    # a successful setClient, so failures here are not fatal. The response also
    # announces the StoreFront store path, which we use to auto detect the
    # store unless one was given explicitly.
    try:
        response = session.post(
            f"{session.base_url}{NF_SETCLIENT_PATH}",
            headers={"Accept": NF_ACCEPT, "X-Citrix-IsUsingHTTPS": "Yes"},
            data={"nsg-setclient": "wica", "StateContext": state_context},
        )
    except Exception:
        return

    if not session.store_explicit:
        match = _STORE_PATH_RE.search(response.text or "")
        if match:
            session.set_store(match.group(1))


def _parse_requirements(xml_text: str) -> tuple[str, str]:
    """
    Extract StateContext and postback URL from an AuthenticationRequirements
    document and make sure the requested factor is username plus password.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise UnexpectedResponseError(
            f"failed to parse authentication requirements XML: {e}"
        ) from e

    state_context = _find_text(root, "StateContext") or ""
    postback = _find_text(root, "PostBack") or NF_DEFAULT_POSTBACK

    credential_types = {
        (element.text or "").lower() for element in root.iter() if _localname(element.tag) == "Type"
    }
    if credential_types and not {"username", "password"} <= credential_types:
        raise UnsupportedAuthFlowError(
            "gateway requests an authentication factor this plugin does not support "
            f"(credential types: {', '.join(sorted(credential_types))}); only "
            "single-factor username/password is supported"
        )

    return state_context, postback


def _check_authentication_result(session: GatewaySession, xml_text: str) -> None:
    """Evaluate the doAuthentication.do response"""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise UnexpectedResponseError(f"failed to parse authentication result XML: {e}") from e

    result = (_find_text(root, "Result") or "").lower()

    if result == "success":
        if not session.cookie("NSC_AAAC"):
            raise GatewayAuthenticationError(
                "authentication reported success but no NSC_AAAC session cookie was set"
            )
        return

    if result == "more-info":
        # wrong credentials come back as more-info with an error text (retry),
        # a genuine next factor comes back as more-info without one
        errors = _find_text(root, "Message") or _find_text(root, "Text")
        if errors:
            raise GatewayAuthenticationError(f"authentication failed: {errors}")
        raise UnsupportedAuthFlowError(
            "gateway requests an additional authentication factor (multi-factor "
            "setup); only single-factor username/password is supported"
        )

    errors = _find_text(root, "Message")
    detail = f": {errors}" if errors else ""
    raise GatewayAuthenticationError(
        f"authentication failed with result '{result or 'unknown'}'{detail} (check credentials)"
    )


def _localname(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _find_text(root: ET.Element, localname: str) -> Optional[str]:
    """Find the text of the first element with the given local name, ignoring namespaces"""
    for element in root.iter():
        if _localname(element.tag) == localname:
            return element.text
    return None
