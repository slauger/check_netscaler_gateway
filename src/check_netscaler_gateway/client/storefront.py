"""
StoreFront resource enumeration through the gateway session

This part of the flow is identical for both authentication flows: fetch the
CsrfToken, authenticate the StoreFront session through the gateway and list
the available resources.
"""

from typing import List

import requests

from check_netscaler_gateway.client.exceptions import (
    CsrfTokenError,
    UnexpectedResponseError,
)
from check_netscaler_gateway.client.session import GatewaySession

XML_HEADERS = {
    "Accept": "application/xml, text/xml, */*; q=0.01",
    "Content-Length": "0",
    "X-Citrix-IsUsingHTTPS": "Yes",
}


def list_resources(session: GatewaySession) -> List[str]:
    """
    Enumerate the resources available to the logged-in user

    Returns:
        List of resource names
    """
    _post_expect_ok(session, f"{session.store_url}/Home/Configuration", headers=XML_HEADERS)

    csrf_token = session.cookie("CsrfToken")
    if not csrf_token:
        raise CsrfTokenError("failed to get CsrfToken cookie from StoreFront")

    csrf_headers = dict(XML_HEADERS, **{"Csrf-Token": csrf_token})
    _post_expect_ok(
        session, f"{session.store_url}/Authentication/GetAuthMethods", headers=csrf_headers
    )
    _post_expect_ok(session, f"{session.store_url}/GatewayAuth/Login", headers=csrf_headers)

    response = _post_expect_ok(
        session,
        f"{session.store_url}/Resources/List",
        headers={
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "X-Citrix-IsUsingHTTPS": "Yes",
            "Csrf-Token": csrf_token,
        },
        data={"format": "json", "resourceDetails": "Default"},
    )

    try:
        payload = response.json()
    except ValueError as e:
        raise UnexpectedResponseError(
            f"request to {session.store_url}/Resources/List returned invalid JSON: {e}",
            url=f"{session.store_url}/Resources/List",
            status_code=response.status_code,
        ) from e

    resources = payload.get("resources")
    if resources is None:
        raise UnexpectedResponseError(
            f"request to {session.store_url}/Resources/List returned no resources element",
            url=f"{session.store_url}/Resources/List",
            status_code=response.status_code,
        )

    return [resource["name"] for resource in resources if "name" in resource]


def _post_expect_ok(session: GatewaySession, url: str, **kwargs) -> requests.Response:
    """POST and treat any redirect or error status as a failure"""
    response = session.post(url, **kwargs)
    if response.status_code >= 400:
        raise UnexpectedResponseError(
            f"request to {url} failed with HTTP {response.status_code}",
            url=url,
            status_code=response.status_code,
        )
    if response.status_code >= 300:
        raise UnexpectedResponseError(
            f"request to {url} redirected with HTTP {response.status_code} "
            "(session not authenticated?)",
            url=url,
            status_code=response.status_code,
        )
    return response
