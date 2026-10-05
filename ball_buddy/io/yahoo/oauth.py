"""In-app Yahoo OAuth 2.0 (replaces yfpy's console-based browser dance).

yfpy's sign-in path goes through ``yahoo_oauth``'s ``handler()``, which ends
in ``input("Enter verifier : ")`` — a console prompt that cannot exist in the
windowed exe (surfaced as "lost sys.stdin"). Yahoo's default callback for
that flow is ``oob``, whose "code" is useless for manual copy-paste.

So the app drives the OAuth 2.0 three-legged handshake itself:

1. :func:`begin_sign_in` opens a throwaway local **https** server on
   ``https://localhost:8480/callback`` (Yahoo's developer console rejects
   plain-``http`` callback URIs, so the app generates a one-time self-signed
   cert for ``localhost``; the browser shows one "connection isn't private"
   page — Advanced → Continue — which is safe because the callback only ever
   hits the local machine) and hands the browser an authorize URL with that
   URL as the callback.
2. The UI polls :meth:`LocalCallbackServer.wait` in small slices (it is
   non-blocking-friendly) while the user signs in; when Yahoo redirects
   back, the code is captured automatically.
3. If nothing arrives in time (browser blocked, callback URI not
   registered in the Yahoo developer app), the UI falls back to a manual
   paste: :func:`parse_paste` pulls the code out of the redirect URL the
   browser showed (or a bare code) and :func:`complete_exchange` finishes
   the handshake using that URL's own callback.

Token refresh uses the same endpoint with ``grant_type=refresh_token``.
The access token is a JWT whose ``sub`` claim is the Yahoo GUID.

Endpoints (yahoo_oauth 2.1.1 defaults):

- authorize: ``https://api.login.yahoo.com/oauth2/request_auth``
- token:     ``https://api.login.yahoo.com/oauth2/get_token``
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import secrets
import ssl
import threading
import urllib.parse
import webbrowser
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

AUTHORIZE_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
HOST = "127.0.0.1"
PORT = 8480
PATH = "/callback"
#: The callback URI the user registers in the Yahoo developer console.
#: https is mandatory (Yahoo rejects plain-http URIs); the loopback server
#: is served with a self-signed cert for ``localhost``.
HTTPS_CALLBACK_URI = f"https://localhost:{PORT}{PATH}"
#: Last-resort callback when no cert can be generated (paste fallback only).
HTTP_CALLBACK_URI = f"http://{HOST}:{PORT}{PATH}"
#: How long the UI keeps waiting for the browser redirect before offering
#: the manual-paste fallback.
CAPTURE_TIMEOUT_SECONDS = 240


class OAuthError(RuntimeError):
    """Any step of the sign-in handshake failed (network, bad code, ...)."""


class LocalCallbackServer:
    """One-shot local HTTP server that captures the OAuth redirect code.

    Start with :func:`begin_sign_in`; poll :meth:`wait` (non-blocking with
    ``timeout=0``) from the UI. Single-use; shuts itself down when the
    redirect arrives, the timeout is reached and the UI calls :meth:`stop`,
    or :meth:`wait` raises on an error response.
    """

    def __init__(self) -> None:
        self._server: _ThreadingHTTPServer | None = None
        self._event = threading.Event()
        self._code: str | None = None
        self._error: str | None = None
        self._ssl_context: ssl.SSLContext | None = None
        #: PKCE code verifier (public clients only); None for confidential.
        self.code_verifier: str | None = None

    @property
    def callback_uri(self) -> str:
        if self._ssl_context is not None:
            return HTTPS_CALLBACK_URI
        return HTTP_CALLBACK_URI

    @property
    def captured(self) -> bool:
        """True once the redirect arrived (code or error set)."""
        return self._event.is_set()

    def start(self, ssl_context: ssl.SSLContext | None = None) -> None:
        """Bind the loopback port and serve in a daemon thread."""
        handler = _make_handler(self)
        try:
            server = _ThreadingHTTPServer((HOST, PORT), handler, ssl_context)
        except OSError as exc:
            raise OAuthError(
                f"Could not open the local sign-in port {PORT}: {exc}"
            ) from exc
        self._ssl_context = ssl_context
        self._server = server
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def wait(self, timeout: float | None = None) -> str | None:
        """Block up to ``timeout`` seconds; return the code if captured.

        Raises :class:`OAuthError` if the redirect carried an error.
        Returns ``None`` on timeout. With ``timeout=0`` this is a pure poll.
        """
        self._event.wait(timeout)
        if self._error:
            self.stop()
            raise OAuthError(self._error)
        if self._code is not None:
            self.stop()
        return self._code

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None


class _ThreadingHTTPServer(ThreadingHTTPServer):
    """Loopback server that can serve https via a self-signed cert.

    ``ssl_context`` must be set *before* ``super().__init__`` because
    ``server_bind`` (which does the wrapping) runs during it.
    """

    ssl_context: ssl.SSLContext | None = None

    def __init__(
        self,
        server_address: tuple[str, int],
        RequestHandlerClass: type,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        object.__setattr__(self, "ssl_context", ssl_context)
        super().__init__(server_address, RequestHandlerClass)

    def server_bind(self) -> None:
        super().server_bind()
        if self.ssl_context is not None:
            self.socket = self.ssl_context.wrap_socket(
                self.socket, server_side=True
            )


def ensure_loopback_cert(data_dir: Path) -> tuple[Path, Path]:
    """Self-signed ``(cert, key)`` PEM files for ``https://localhost``.

    Generated once per data dir (10-year validity) and reused afterwards.
    Only the local browser ever validates it (with a warning the user
    accepts); nothing about it leaves the machine.
    """
    cert_file = data_dir / "oauth_cert.pem"
    key_file = data_dir / "oauth_key.pem"
    if cert_file.exists() and key_file.exists():
        return cert_file, key_file
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
    now = datetime.now(UTC)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # self-signed
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address(HOST)),
                ]
            ),
            critical=False,
        )
    )
    cert = builder.sign(key, hashes.SHA256())
    key_file.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_file, key_file


def make_ssl_context(cert_file: Path, key_file: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
    return context


def _make_handler(state: LocalCallbackServer) -> type[BaseHTTPRequestHandler]:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - http.server API
            if state._event.is_set():
                # The first redirect already decided the outcome; later
                # requests (a browser refresh, or the user reloading the
                # bare callback URL) must not clobber a captured code with
                # "no code parameter".
                self._respond(
                    400, b"Sign-in already captured - you can close this tab."
                )
                return
            params = urllib.parse.parse_qs(
                urllib.parse.urlparse(self.path).query
            )
            error = params.get("error")
            if error:
                state._error = params.get("error_description", [error[0]])[0]
                state._event.set()
                self._respond(400, b"Yahoo sign-in reported an error.")
                return
            code = params.get("code")
            if not code:
                state._error = "redirect had no code parameter"
                state._event.set()
                self._respond(400, b"Redirect had no code parameter.")
                return
            state._code = code[0]
            state._event.set()
            self._respond(200, b"Sign-in complete - you can close this tab.")

        def _respond(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass  # keep the console clean

    return _Handler


def new_pkce() -> tuple[str, str]:
    """A PKCE ``(code_verifier, code_challenge)`` pair (S256).

    RFC 7636: verifier 43–128 unreserved chars; challenge is the base64url
    (no padding) SHA-256 of the verifier.
    """
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorize_url(
    callback_uri: str, consumer_key: str, code_challenge: str | None = None
) -> str:
    """The browser-redirect URL.

    Yahoo's ``request_auth`` endpoint requires ``client_id`` as a query
    parameter (it identifies the app to the login page); the secret stays
    server-side for the token exchange only. Public clients (no secret)
    additionally need the PKCE ``code_challenge``.
    """
    params: dict[str, str] = {
        "client_id": consumer_key,
        "redirect_uri": callback_uri,
        "response_type": "code",
    }
    if code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    return f"{AUTHORIZE_URL}?" + urllib.parse.urlencode(params)


def begin_sign_in(
    data_dir: Path | None, consumer_key: str, consumer_secret: str = ""
) -> tuple[LocalCallbackServer, str]:
    """Start the capture server and open the browser.

    With ``data_dir`` given, the server serves https with the (one-time)
    self-signed localhost cert so the callback URI matches what Yahoo's
    console accepts. Falls back to plain http (paste-only) if the cert
    cannot be created.

    Returns ``(server, callback_uri)``; the UI polls ``server.wait`` until
    the code arrives or the overall deadline passes, then either calls
    :func:`complete_exchange` with the captured code, or offers the manual
    paste fallback.
    """
    server = LocalCallbackServer()
    ssl_context = None
    if data_dir is not None:
        try:
            cert_file, key_file = ensure_loopback_cert(data_dir)
            ssl_context = make_ssl_context(cert_file, key_file)
        except Exception:  # cert generation must never kill sign-in
            ssl_context = None
    server.start(ssl_context)
    code_challenge = None
    if not consumer_secret:
        # Public client: no client secret, so the exchange is authorized
        # with PKCE instead (the verifier travels with the redirect server).
        server.code_verifier, code_challenge = new_pkce()
    url = build_authorize_url(server.callback_uri, consumer_key, code_challenge)
    webbrowser.open(url)
    return server, url


def complete_exchange(
    code: str,
    callback_uri: str,
    consumer_key: str,
    consumer_secret: str,
    code_verifier: str | None = None,
) -> dict:
    """Exchange an authorization code for the persistable token dict."""
    payload = exchange_code(
        code, callback_uri, consumer_key, consumer_secret, code_verifier
    )
    return new_token_dict(payload, consumer_key, consumer_secret)


def exchange_code(
    code: str,
    callback_uri: str,
    consumer_key: str,
    consumer_secret: str,
    code_verifier: str | None = None,
) -> dict:
    """authorization_code -> raw token payload.

    Raises :class:`OAuthError` with the Yahoo error message on failure.
    """
    data: dict[str, str] = {
        "code": code,
        "redirect_uri": callback_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    return _token_request(data, consumer_key, consumer_secret)


def refresh_access_token(
    refresh_token: str, consumer_key: str, consumer_secret: str
) -> dict:
    """refresh_token -> raw token payload (token_time is set by caller)."""
    return _token_request(
        {
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "redirect_uri": "https://www.yahoo.com",
        },
        consumer_key,
        consumer_secret,
    )


def _token_request(data: dict, consumer_key: str, consumer_secret: str) -> dict:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if consumer_secret:
        # Confidential client: Basic-auth the client credentials.
        credentials = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode())
        headers["Authorization"] = f"Basic {credentials.decode()}"
    else:
        # Public client: no secret exists to authenticate with, so the
        # client id goes in the body and PKCE (code_verifier, added by the
        # caller) is what proves the request is the one that asked.
        data["client_id"] = consumer_key
    response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=30)
    if response.status_code != 200:
        raise OAuthError(
            f"Yahoo token request failed ({response.status_code}): "
            f"{response.text[:300]}"
        )
    payload = response.json()
    if "access_token" not in payload:
        raise OAuthError(f"Yahoo returned no access token: {payload}")
    return payload


def extract_guid(access_token: str) -> str:
    """The Yahoo GUID is the ``sub`` claim of the access-token JWT."""
    try:
        payload = access_token.split(".")[1]
        return json.loads(
            base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
        )["sub"]
    except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
        raise OAuthError("Could not read the Yahoo GUID from the access token") from exc


def new_token_dict(
    payload: dict, consumer_key: str, consumer_secret: str
) -> dict:
    """Map a raw Yahoo token payload onto the persistable token dict.

    The GUID is best-effort: Yahoo's tokens normally are JWTs with a ``sub``
    claim, but the GUID is bookkeeping only (yfpy requires the key to exist,
    never its value — no API call sends it), so a token we can't decode must
    not kill the sign-in.
    """
    access_token = payload["access_token"]
    try:
        guid = extract_guid(access_token)
    except OAuthError:
        guid = str(payload.get("guid") or "")
    return {
        "access_token": access_token,
        "guid": guid,
        "refresh_token": payload.get("refresh_token"),
        "token_time": datetime.now(UTC).timestamp(),
        "token_type": payload.get("token_type", "Bearer"),
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret,
    }


def parse_paste(paste: str) -> tuple[str, str]:
    """Parse a manual code paste into ``(code, callback_uri)``.

    Accepts the whole redirect URL the browser showed
    (``http://127.0.0.1:8480/callback?code=...`` or any other callback),
    a bare query string (``code=...``), or just the code. The callback URI
    is taken from the pasted URL when present so the exchange matches what
    Yahoo issued the code for; a bare code falls back to our standard
    callback. Raises :class:`OAuthError` when no usable code is found.
    """
    text = paste.strip()
    if "code=" in text:
        base, _, query = text.partition("?")
        if not query:
            base, query = "", text  # bare query string like "code=abc123"
        params = urllib.parse.parse_qs(query)
        code = (params.get("code") or [None])[0]
        if not code:
            raise OAuthError("Paste contains 'code=' but the value is empty.")
        callback = (
            base if base.startswith("http") else HTTPS_CALLBACK_URI
        )
        return code, callback
    token = text.split("&", 1)[0]
    if not token:
        raise OAuthError("Paste is empty.")
    return token, HTTPS_CALLBACK_URI
