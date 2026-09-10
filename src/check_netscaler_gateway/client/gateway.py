"""
Authentication flows against the NetScaler Gateway vServer

Two flows exist in the wild:

- classic: gateways with the classic portal theme answer POST /cgi/login
  with a 302 to /cgi/setclient?wica. Builds since 13.1-63.x reject a bare
  POST without the cookies from a prior visit of the login page and an
  Origin header (302 to /vpn/index.html with NSC_VPNERR=4001, issue #7),
  so the flow loads /vpn/index.html first like a real browser.
- nfactor: gateways with the RfWebUI theme use the nFactor protocol under
  /nf/auth/ and redirect to the logon page (/logon/LogonPoint/...)
"""

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
REDIRECT_CODES = (301, 302, 303, 307)


def login(session: GatewaySession, auth_mode: str = AUTH_MODE_AUTO) -> str:
    """
    Authenticate against the gateway vServer

    Returns:
        The flow that was used ('classic' or 'nfactor')
    """
    if auth_mode == AUTH_MODE_NFACTOR:
        _nfactor_login(session)
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
    if (
        auth_mode == AUTH_MODE_AUTO
        and response.status_code in REDIRECT_CODES
        and LOGON_POINT_MARKER in location
    ):
        _nfactor_login(session)
        return AUTH_MODE_NFACTOR

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

    Newer 13.1 builds reject a bare POST /cgi/login without the session
    cookies handed out here (302 to /vpn/index.html, NSC_VPNERR=4001).
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
    nFactor flow: fetch the authentication requirements, then post the
    credentials to the postback URL.

    Endpoint names, field names and the success criterion are reconstructed
    from the documented nFactor protocol; they still need verification
    against a live 13.1/14.1 gateway (see issue #7 debug output).
    """
    requirements_url = f"{session.base_url}/nf/auth/getAuthenticationRequirements.do"
    response = session.post(
        requirements_url,
        headers={
            "Accept": "application/xml, text/xml, */*; q=0.01",
            "Content-Length": "0",
            "X-Citrix-IsUsingHTTPS": "Yes",
        },
    )
    if response.status_code == 404:
        raise GatewayAuthenticationError(
            f"request to {requirements_url} returned HTTP 404; the gateway does not "
            "speak the nFactor protocol (wrong auth-mode or invalid credentials on "
            "a classic gateway)"
        )
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
        headers={
            "Accept": "application/xml, text/xml, */*; q=0.01",
            "X-Citrix-IsUsingHTTPS": "Yes",
        },
        data={
            "login": session.username,
            "passwd": session.password,
            "savecredentials": "false",
            "StateContext": state_context,
            "nsg-x1-logon-button": "Log On",
        },
    )
    if response.status_code >= 300:
        raise UnexpectedResponseError(
            f"request to {auth_url} failed with HTTP {response.status_code}",
            url=auth_url,
            status_code=response.status_code,
        )

    _check_authentication_result(session, response.text)


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
    postback = _find_text(root, "PostBack") or "/nf/auth/doAuthentication.do"

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
