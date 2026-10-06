"""In-app OAuth module tests: paste parsing, GUID extraction, local server.

The local-callback test hits a real (bound) 127.0.0.1:8480 server with a
real HTTP GET — no network beyond loopback. Token exchange is tested with
the HTTP layer monkeypatched.
"""

import base64
import json
import time
import urllib.parse

import pytest
import requests

from ball_buddy.io.yahoo import oauth


def _jwt(sub: str) -> str:
    def seg(payload: dict) -> str:
        raw = json.dumps(payload).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    return f"{seg({'alg': 'none'})}.{seg({'sub': sub, 'exp': 9999999999})}.sig"


def test_extract_guid():
    assert oauth.extract_guid(_jwt("987654321")) == "987654321"


def test_extract_guid_rejects_garbage():
    with pytest.raises(oauth.OAuthError, match="GUID"):
        oauth.extract_guid("not-a-jwt")


def test_build_authorize_url():
    url = oauth.build_authorize_url(oauth.HTTPS_CALLBACK_URI, "mykey")
    assert url.startswith(oauth.AUTHORIZE_URL)
    params = dict(
        urllib.parse.parse_qsl(urllib.parse.urlparse(url).query)
    )
    assert params == {
        "client_id": "mykey",  # Yahoo requires it as a query param
        "redirect_uri": oauth.HTTPS_CALLBACK_URI,
        "response_type": "code",
    }


def test_parse_paste_full_url():
    paste = "http://127.0.0.1:8480/callback?code=abc123&foo=bar"
    code, callback = oauth.parse_paste(paste)
    assert code == "abc123"
    assert callback == "http://127.0.0.1:8480/callback"


def test_parse_paste_other_callback_url():
    paste = "https://myapp.example.com/done?code=xyz&state=1"
    code, callback = oauth.parse_paste(paste)
    assert code == "xyz"
    assert callback == "https://myapp.example.com/done"


def test_parse_paste_query_only():
    code, callback = oauth.parse_paste("code=abc123")
    assert code == "abc123"
    assert callback == oauth.HTTPS_CALLBACK_URI


def test_parse_paste_bare_code():
    code, callback = oauth.parse_paste("  abc123  ")
    assert code == "abc123"
    assert callback == oauth.HTTPS_CALLBACK_URI


def test_ensure_loopback_cert_generates_and_reuses(tmp_path):
    cert, key = oauth.ensure_loopback_cert(tmp_path)
    assert cert.name == "oauth_cert.pem" and key.name == "oauth_key.pem"
    assert cert.exists() and key.exists()
    # second call reuses the same files (no regeneration)
    assert oauth.ensure_loopback_cert(tmp_path) == (cert, key)
    # the cert is loadable and names localhost
    import ssl

    context = oauth.make_ssl_context(cert, key)
    assert isinstance(context, ssl.SSLContext)


def test_parse_paste_empty_code():
    with pytest.raises(oauth.OAuthError, match="empty"):
        oauth.parse_paste("http://127.0.0.1:8480/callback?code=")


def test_parse_paste_blank():
    with pytest.raises(oauth.OAuthError, match="empty"):
        oauth.parse_paste("   ")


def test_new_token_dict_shape():
    tokens = oauth.new_token_dict(
        {"access_token": _jwt("987654321"), "refresh_token": "ref", "token_type": "Bearer"},
        "k",
        "s",
    )
    assert tokens["guid"] == "987654321"
    assert tokens["refresh_token"] == "ref"
    assert tokens["token_type"] == "Bearer"
    assert tokens["consumer_key"] == "k"
    assert tokens["consumer_secret"] == "s"
    assert tokens["token_time"] > time.time() - 5
    # refresh must replay the exact grant URI; default is the https one
    assert tokens["callback_uri"] == oauth.HTTPS_CALLBACK_URI


def test_new_token_dict_non_jwt_token_guid_best_effort():
    """A token without a decodable JWT sub must not kill the sign-in:
    the GUID is bookkeeping only (yfpy never sends it), so "" is fine."""
    tokens = oauth.new_token_dict({"access_token": "opaque-token"}, "k", "")
    assert tokens["guid"] == ""
    assert tokens["access_token"] == "opaque-token"


def test_new_token_dict_payload_guid_field_fallback():
    tokens = oauth.new_token_dict(
        {"access_token": "opaque", "guid": "777"}, "k", ""
    )
    assert tokens["guid"] == "777"


def test_new_pkce_shape():
    verifier, challenge = oauth.new_pkce()
    assert 43 <= len(verifier) <= 128
    import base64
    import hashlib

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    assert challenge == base64.urlsafe_b64encode(digest).decode().rstrip("=")


def test_build_authorize_url_with_pkce():
    url = oauth.build_authorize_url(
        oauth.HTTPS_CALLBACK_URI, "mykey", "chall123"
    )
    params = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
    assert params["code_challenge"] == "chall123"
    assert params["code_challenge_method"] == "S256"
    assert params["client_id"] == "mykey"


def test_token_request_public_client_uses_body_client_id(monkeypatch):
    """No secret: no Basic auth header, client_id in the body."""
    import requests

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"access_token": "t", "refresh_token": "r", "token_type": "Bearer"}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured.update(url=url, data=data, headers=headers)
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    oauth._token_request({"code": "c", "grant_type": "authorization_code"}, "pk", "")
    assert captured["data"]["client_id"] == "pk"
    assert "Authorization" not in captured["headers"]


def test_token_request_confidential_uses_basic_auth(monkeypatch):
    import requests

    captured = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {"access_token": "t"}

    def fake_post(url, data=None, headers=None, timeout=None):
        captured.update(headers=headers)
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)
    oauth._token_request({}, "pk", "sk")
    assert captured["headers"]["Authorization"].startswith("Basic ")


def test_exchange_code_and_complete(monkeypatch):
    payload = {
        "access_token": _jwt("987654321"),
        "refresh_token": "ref",
        "token_type": "Bearer",
    }
    seen = {}

    def fake_token_request(data, key, secret):
        seen.update(data, key=key, secret=secret)
        return payload

    monkeypatch.setattr(oauth, "_token_request", fake_token_request)
    tokens = oauth.complete_exchange(
        "abc123", "http://127.0.0.1:8480/callback", "k", "s"
    )
    assert tokens["guid"] == "987654321"
    assert seen["code"] == "abc123"
    assert seen["grant_type"] == "authorization_code"
    assert seen["redirect_uri"] == "http://127.0.0.1:8480/callback"
    assert seen["key"] == "k"
    assert seen["secret"] == "s"
    # the persisted token must carry the EXACT grant URI (refresh replays it)
    assert tokens["callback_uri"] == "http://127.0.0.1:8480/callback"


def test_exchange_code_public_client_sends_verifier(monkeypatch):
    payload = {"access_token": _jwt("1"), "refresh_token": "r", "token_type": "Bearer"}
    seen = {}

    def fake_token_request(data, key, secret):
        seen.update(data, key=key, secret=secret)
        return payload

    monkeypatch.setattr(oauth, "_token_request", fake_token_request)
    oauth.complete_exchange("abc", "cb", "pk", "", code_verifier="v123")
    assert seen["code_verifier"] == "v123"
    assert seen["secret"] == ""


def test_refresh_access_token_grant(monkeypatch):
    payload = {"access_token": _jwt("1"), "refresh_token": "ref2", "token_type": "Bearer"}
    seen = {}

    def fake_token_request(data, key, secret):
        seen.update(data)
        return payload

    monkeypatch.setattr(oauth, "_token_request", fake_token_request)
    result = oauth.refresh_access_token("ref", "k", "s")
    assert result == payload
    assert seen["grant_type"] == "refresh_token"
    assert seen["refresh_token"] == "ref"
    # OAuth2 4124 s6: refresh must replay the exact grant redirect_uri
    assert seen["redirect_uri"] == oauth.HTTPS_CALLBACK_URI
    result = oauth.refresh_access_token("ref", "k", "s", "http://localhost:8480/callback")
    assert seen["redirect_uri"] == "http://localhost:8480/callback"


def test_local_server_captures_code():
    server = oauth.LocalCallbackServer()
    server.start()
    try:
        response = requests.get(f"{server.callback_uri}?code=abc123", timeout=5)
        assert response.status_code == 200
        assert server.wait(timeout=2) == "abc123"
        assert server.captured
    finally:
        server.stop()


def test_local_server_ignores_second_codeless_request():
    """Regression: a reload/bare-URL hit after the real redirect must not
    clobber the captured code with 'redirect had no code parameter'."""
    server = oauth.LocalCallbackServer()
    server.start()
    try:
        response = requests.get(f"{server.callback_uri}?code=abc123", timeout=5)
        assert response.status_code == 200
        second = requests.get(server.callback_uri, timeout=5)
        assert second.status_code == 400
        assert server.wait(timeout=2) == "abc123"  # still the code, no error
    finally:
        server.stop()


def test_local_server_reports_error_param():
    server = oauth.LocalCallbackServer()
    server.start()
    try:
        requests.get(
            f"{server.callback_uri}?error=access_denied&error_description=nope",
            timeout=5,
        )
        with pytest.raises(oauth.OAuthError, match="nope"):
            server.wait(timeout=2)
    finally:
        server.stop()


def test_local_server_times_out():
    server = oauth.LocalCallbackServer()
    server.start()
    try:
        assert server.wait(timeout=0.2) is None
        assert not server.captured
    finally:
        server.stop()


def test_local_server_https_captures_code(tmp_path):
    """The real sign-in path: https loopback with the generated cert."""
    cert, key = oauth.ensure_loopback_cert(tmp_path)
    server = oauth.LocalCallbackServer()
    server.start(oauth.make_ssl_context(cert, key))
    try:
        assert server.callback_uri == oauth.HTTPS_CALLBACK_URI
        response = requests.get(
            f"{server.callback_uri}?code=abc123",
            verify=str(cert),
            timeout=5,
        )
        assert response.status_code == 200
        assert server.wait(timeout=2) == "abc123"
    finally:
        server.stop()


def test_local_server_plain_http_fallback(tmp_path):
    """No cert (generation failed) -> plain http URI, still captures."""
    server = oauth.LocalCallbackServer()
    server.start()
    try:
        assert server.callback_uri == oauth.HTTP_CALLBACK_URI
        requests.get(f"{server.callback_uri}?code=plain", timeout=5)
        assert server.wait(timeout=2) == "plain"
    finally:
        server.stop()
