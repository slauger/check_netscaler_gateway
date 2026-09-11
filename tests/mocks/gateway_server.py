"""
Mock NetScaler Gateway + StoreFront server

Simulates both authentication flows (classic and nFactor) plus the StoreFront
part of the login simulation. Can be used standalone or via pytest fixtures.

Usage:
    # Standalone mode
    python -m tests.mocks.gateway_server --port 8080 --mode nfactor

    # In pytest tests
    from tests.mocks.gateway_server import MockGatewayServer
    server = MockGatewayServer(port=8080, mode="classic")
    server.start()
"""

import argparse
import json
import threading
from pathlib import Path
from typing import Optional

from flask import Flask, Response, request

MODE_CLASSIC = "classic"
MODE_NFACTOR = "nfactor"

STATE_CONTEXT = "bG9naW5zY2hlbWE9ZGVmYXVsdA"
CSRF_TOKEN = "0123456789ABCDEF0123456789ABCDEF"
AAA_COOKIE = "aaa-session-cookie"

REQUIREMENTS_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<AuthenticationRequirements xmlns="http://citrix.com/authentication/response/1">
<Status>success</Status>
<Result>more-info</Result>
<StateContext>{STATE_CONTEXT}</StateContext>
<AuthenticationRequirements>
<PostBack>/nf/auth/doAuthentication.do</PostBack>
<CancelPostBack>/nf/auth/stopAuthentication.do</CancelPostBack>
<Requirements>
<Requirement><Credential><ID>login</ID><Type>username</Type></Credential></Requirement>
<Requirement><Credential><ID>passwd</ID><Type>password</Type></Credential></Requirement>
<Requirement><Credential><ID>loginBtn</ID><Type>none</Type></Credential></Requirement>
</Requirements>
</AuthenticationRequirements>
</AuthenticationRequirements>"""

REQUIREMENTS_OTP_XML = REQUIREMENTS_XML.replace(
    "<Type>username</Type>", "<Type>passcode</Type>"
).replace("<Type>password</Type>", "<Type>passcode</Type>")

SUCCESS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<AuthenticationRequirements xmlns="http://citrix.com/authentication/response/1">
<Status>success</Status>
<Result>success</Result>
</AuthenticationRequirements>"""

MORE_INFO_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<AuthenticationRequirements xmlns="http://citrix.com/authentication/response/1">
<Status>success</Status>
<Result>more-info</Result>
<StateContext>{STATE_CONTEXT}</StateContext>
<AuthenticationRequirements>
<PostBack>/nf/auth/doAuthentication.do</PostBack>
<Requirements>
<Requirement><Credential><ID>otp</ID><Type>passcode</Type></Credential></Requirement>
</Requirements>
</AuthenticationRequirements>
</AuthenticationRequirements>"""

FAILURE_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<AuthenticationRequirements xmlns="http://citrix.com/authentication/response/1">
<Status>success</Status>
<Result>more-info</Result>
<StateContext>{STATE_CONTEXT}</StateContext>
<AuthenticationRequirements>
<PostBack>/nf/auth/doAuthentication.do</PostBack>
<Requirements>
<Requirement>
<Credential><Type>none</Type></Credential>
<Label><Text>Incorrect user name or password.</Text><Type>error</Type></Label>
</Requirement>
</Requirements>
</AuthenticationRequirements>
</AuthenticationRequirements>"""


class MockGatewayServer:
    """Mock NetScaler Gateway + StoreFront server"""

    def __init__(
        self,
        port: int = 8080,
        host: str = "127.0.0.1",
        mode: str = MODE_CLASSIC,
        store: str = "Store",
        username: str = "monitoring",
        password: str = "secret",
    ):
        self.port = port
        self.host = host
        self.mode = mode
        self.store = store
        self.username = username
        self.password = password

        # Toggles for error-case tests
        self.csrf_enabled = True
        self.fail_logout = False
        self.multifactor = False
        self.broken_resources_json = False
        self.resources: Optional[list] = None

        self.app = Flask(__name__)
        self.fixtures_dir = Path(__file__).parent / "fixtures"
        self.thread: Optional[threading.Thread] = None

        self._setup_routes()

    def _credentials_valid(self) -> bool:
        return (
            request.form.get("login") == self.username
            and request.form.get("passwd") == self.password
        )

    def _authenticated(self) -> bool:
        return request.cookies.get("NSC_AAAC") == AAA_COOKIE

    def _setup_routes(self):
        app = self.app

        @app.route("/vpn/index.html", methods=["GET"])
        def vpn_index():
            if self.mode == MODE_NFACTOR:
                return Response(status=302, headers={"Location": "/logon/LogonPoint/tmindex.html"})
            response = Response("<html>login page</html>", status=200)
            response.set_cookie("NSC_TASS", "/")
            return response

        @app.route("/cgi/login", methods=["POST"])
        def cgi_login():
            if self.mode == MODE_NFACTOR:
                response = Response(status=302)
                response.headers["Location"] = "/logon/LogonPoint/tmindex.html"
                return response
            response = Response(status=302)
            # 13.1-63.x hardening, confirmed via issue #7: a POST without an
            # Origin header or with a tool user agent fails like a wrong
            # password
            user_agent = request.headers.get("User-Agent", "")
            tool_agent = "libwww-perl" in user_agent or "python-requests" in user_agent
            if request.headers.get("Origin") and not tool_agent and self._credentials_valid():
                response.headers["Location"] = "/cgi/setclient?wica"
                response.set_cookie("NSC_AAAC", AAA_COOKIE)
            else:
                response.headers["Location"] = "/vpn/index.html"
                response.set_cookie("NSC_VPNERR", "4001")
            return response

        @app.route("/cgi/setclient", methods=["POST"])
        def cgi_setclient():
            if not self._authenticated():
                return Response(status=403)
            return Response("", status=200)

        @app.route("/cgi/logout", methods=["GET"])
        def cgi_logout():
            if self.fail_logout:
                return Response(status=500)
            return Response("", status=200)

        @app.route("/nf/auth/getAuthenticationRequirements.do", methods=["POST"])
        def nf_requirements():
            if self.mode != MODE_NFACTOR:
                return Response(status=404)
            body = REQUIREMENTS_OTP_XML if self.multifactor == "first-factor" else REQUIREMENTS_XML
            return Response(body, status=200, mimetype="application/xml")

        @app.route("/nf/auth/doAuthentication.do", methods=["POST"])
        def nf_authenticate():
            if self.mode != MODE_NFACTOR:
                return Response(status=404)
            if request.form.get("StateContext") != STATE_CONTEXT:
                return Response(FAILURE_XML, status=200, mimetype="application/xml")
            if not self._credentials_valid():
                return Response(FAILURE_XML, status=200, mimetype="application/xml")
            if self.multifactor:
                return Response(MORE_INFO_XML, status=200, mimetype="application/xml")
            response = Response(SUCCESS_XML, status=200, mimetype="application/xml")
            response.set_cookie("NSC_AAAC", AAA_COOKIE)
            return response

        @app.route("/Citrix/<store>Web/Home/Configuration", methods=["POST"])
        def home_configuration(store):
            if store != self.store or not self._authenticated():
                return Response(status=302, headers={"Location": "/vpn/index.html"})
            response = Response("<clientSettings/>", status=200, mimetype="application/xml")
            if self.csrf_enabled:
                response.set_cookie("CsrfToken", CSRF_TOKEN)
            return response

        @app.route("/Citrix/<store>Web/Authentication/GetAuthMethods", methods=["POST"])
        def get_auth_methods(store):
            if not self._authenticated() or request.headers.get("Csrf-Token") != CSRF_TOKEN:
                return Response(status=403)
            return Response("<methods/>", status=200, mimetype="application/xml")

        @app.route("/Citrix/<store>Web/GatewayAuth/Login", methods=["POST"])
        def gateway_auth_login(store):
            if not self._authenticated() or request.headers.get("Csrf-Token") != CSRF_TOKEN:
                return Response(status=403)
            return Response("", status=200)

        @app.route("/Citrix/<store>Web/Resources/List", methods=["POST"])
        def resources_list(store):
            if not self._authenticated() or request.headers.get("Csrf-Token") != CSRF_TOKEN:
                return Response(status=403)
            if self.broken_resources_json:
                return Response("this is not json", status=200, mimetype="application/json")
            if self.resources is not None:
                payload = {"resources": self.resources}
            else:
                with open(self.fixtures_dir / "resources.json") as f:
                    payload = json.load(f)
            return Response(json.dumps(payload), status=200, mimetype="application/json")

    def start(self, threaded: bool = True):
        """Start the mock server"""
        if threaded:
            self.thread = threading.Thread(
                target=lambda: self.app.run(host=self.host, port=self.port, debug=False),
                daemon=True,
            )
            self.thread.start()
        else:
            self.app.run(host=self.host, port=self.port, debug=True)

    def stop(self):
        """Stop the mock server (daemon thread dies with the test process)"""
        pass

    def get_url(self) -> str:
        """Get base URL of the server"""
        return f"http://{self.host}:{self.port}"


def main():
    """CLI entry point for standalone mode"""
    parser = argparse.ArgumentParser(description="Mock NetScaler Gateway Server")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument(
        "--mode", choices=[MODE_CLASSIC, MODE_NFACTOR], default=MODE_CLASSIC, help="Firmware mode"
    )
    args = parser.parse_args()

    server = MockGatewayServer(port=args.port, host=args.host, mode=args.mode)
    print(f"Mock NetScaler Gateway Server ({args.mode}) starting on {server.get_url()}")
    print(f"Credentials: {server.username} / {server.password}, store: {server.store}")

    try:
        server.start(threaded=False)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
