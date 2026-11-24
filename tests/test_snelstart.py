import base64
import json
import stat
import time
from hashlib import sha256
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest

from snelstart_mcp import auth as authentication
from snelstart_mcp.auth import CLIENT_ID, REDIRECT_URI, Auth
from snelstart_mcp.client import Client, catalog
from snelstart_mcp.config import SnelStartError, Store
from snelstart_mcp.enums import LoginMethod
from snelstart_mcp.har import import_har, request_data
from snelstart_mcp.server import create_server

ADMIN = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"


def token(admin=ADMIN, expires=None):
    payload = {"exp": expires or int(time.time()) + 3600, "data": {"a": {"aid": admin}}}
    part = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return "header." + part + ".signature"


@pytest.fixture
def store(tmp_path):
    result = Store(tmp_path / "private")
    result.write("config.json", {"administration_id": ADMIN})
    result.write(
        "tokens.json",
        {"access_token": token(), "refresh_token": "old-refresh", "expires_at": time.time() + 3600},
    )
    return result


def test_browser_sign_in_validates_pkce_and_stores_tokens_without_credentials(store, monkeypatch):
    authorization = {}

    def browser(url):
        location = urlsplit(url)
        assert location.netloc == "login.snelstart.nl" and location.path == "/authorize"
        authorization.update({key: values[0] for key, values in parse_qs(location.query).items()})
        assert authorization["redirect_uri"] == REDIRECT_URI
        return (
            REDIRECT_URI
            + "/?"
            + urlencode({"code": "fixture-code", "state": authorization["state"]})
        )

    def exchange(request):
        assert request.url.host == "login.snelstart.nl" and request.url.path == "/oauth/token"
        payload = json.loads(request.content)
        assert payload["grant_type"] == "authorization_code"
        assert payload["code"] == "fixture-code"
        assert payload["redirect_uri"] == REDIRECT_URI
        actual_challenge = base64.urlsafe_b64encode(
            sha256(payload["code_verifier"].encode()).digest()
        )
        assert actual_challenge.decode().rstrip("=") == authorization["code_challenge"]
        return httpx.Response(200, json={"access_token": token(), "refresh_token": "rotated"})

    monkeypatch.setattr(authentication, "open_browser_callback", browser)
    with httpx.Client(transport=httpx.MockTransport(exchange)) as http:
        Auth(store, http).login(LoginMethod.BROWSER)
    assert store.read("tokens.json")["refresh_token"] == "rotated"
    assert not (store.directory / "credentials.json").exists()
    assert store.read("config.json")["administration_id"] == ADMIN


@pytest.mark.parametrize(
    ("origin", "path", "query"),
    [
        ("https://web.snelstart.nl.evil.test", "/", "state={state}&code=private-fixture"),
        (REDIRECT_URI, "/unexpected", "state={state}&code=private-fixture"),
        (REDIRECT_URI, "/", "state=wrong&code=private-fixture"),
        (REDIRECT_URI, "/", "state={state}&state=wrong&code=private-fixture"),
        (REDIRECT_URI, "/", "state={state}&code=private-fixture&code=duplicate"),
        (REDIRECT_URI, "/", "state={state}&error=access_denied&error_description=private-fixture"),
    ],
)
def test_invalid_browser_callback_is_rejected_without_exchange(
    store, monkeypatch, origin, path, query
):
    def browser(url):
        state = parse_qs(urlsplit(url).query)["state"][0]
        return origin + path + "?" + query.format(state=state)

    original = store.read("tokens.json")
    monkeypatch.setattr(authentication, "open_browser_callback", browser)
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected token exchange"))
        ) as http,
        pytest.raises(SnelStartError, match="OAuth callback|did not authorize") as error,
    ):
        Auth(store, http).login(LoginMethod.BROWSER)
    assert "private-fixture" not in str(error.value)
    assert store.read("tokens.json") == original


def test_browser_sign_in_without_refresh_does_not_replace_the_current_profile(store, monkeypatch):
    def browser(url):
        state = parse_qs(urlsplit(url).query)["state"][0]
        return REDIRECT_URI + "?" + urlencode({"code": "fixture", "state": state})

    original = store.read("tokens.json")
    monkeypatch.setattr(authentication, "open_browser_callback", browser)
    with (
        httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"access_token": token()})
            )
        ) as http,
        pytest.raises(SnelStartError, match="no refresh token"),
    ):
        Auth(store, http).login(LoginMethod.BROWSER)
    assert store.read("tokens.json") == original


def test_private_atomic_storage(store):
    store.write("credentials.json", {"username": "example@test.nl", "password": "private"})
    assert stat.S_IMODE(store.directory.stat().st_mode) == 0o700
    assert stat.S_IMODE((store.directory / "credentials.json").stat().st_mode) == 0o600
    store.write("credentials.json", {"password": "replacement"})
    assert not list(store.directory.glob(".pending-*"))
    assert store.read("credentials.json") == {"password": "replacement"}


def test_reject_symlink(store, tmp_path):
    external = tmp_path / "external"
    external.write_text("{}")
    (store.directory / "credentials.json").symlink_to(external)
    with pytest.raises(SnelStartError, match="symbolic link"):
        store.read("credentials.json")


def test_refresh_rotates_and_preserves_admin(store):
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"access_token": token(), "refresh_token": "new-refresh"})

    auth = Auth(store, httpx.Client(transport=httpx.MockTransport(handle)))
    auth.access_token(ADMIN, force=True)
    assert requests[0]["administrationId"] == ADMIN
    assert requests[0]["refresh_token"] == "old-refresh"
    assert store.read("tokens.json")["refresh_token"] == "new-refresh"
    auth.access_token(ADMIN)
    assert len(requests) == 1


def test_wrong_admin_token_never_returned(store):
    auth = Auth(
        store,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(200, json={"access_token": token(OTHER)})
            )
        ),
    )
    with pytest.raises(SnelStartError, match="does not match the selected"):
        auth.access_token(ADMIN, force=True)


def test_refresh_error_does_not_expose_response(store):
    auth = Auth(
        store,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(403, json={"error_description": "SECRET-PASSWORD"})
            )
        ),
    )
    with pytest.raises(SnelStartError) as error:
        auth.access_token(force=True)
    assert "SECRET" not in str(error.value)
    assert "Run 'snelstart-mcp login' locally" in str(error.value)
    assert store.read("tokens.json")["refresh_token"] == "old-refresh"


def test_failed_refresh_signs_in_again_and_rebinds_the_administration(store):
    store.write("credentials.json", {"username": "user@example.test", "password": "fixture"})
    grants = []
    bound_token = token()

    def handle(request):
        assert request.url.host == "login.snelstart.nl"
        if request.url.path == "/authorize":
            return httpx.Response(
                302,
                headers={
                    "Location": "https://web.snelstart.nl?"
                    + urlencode({"state": request.url.params["state"], "code": "new-code"})
                },
            )
        assert request.url.path == "/oauth/token"
        body = json.loads(request.content)
        grants.append(body)
        if body["grant_type"] == "authorization_code":
            assert body["code"] == "new-code"
            return httpx.Response(
                200, json={"access_token": token(OTHER), "refresh_token": "new-refresh"}
            )
        assert body["administrationId"] == ADMIN
        if body["refresh_token"] == "old-refresh":
            return httpx.Response(403)
        assert body["refresh_token"] == "new-refresh"
        return httpx.Response(
            200, json={"access_token": bound_token, "refresh_token": "bound-refresh"}
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        assert Auth(store, http).access_token(ADMIN, force=True) == bound_token
    assert [grant["grant_type"] for grant in grants] == [
        "refresh_token",
        "authorization_code",
        "refresh_token",
    ]
    assert store.read("tokens.json")["refresh_token"] == "bound-refresh"


@pytest.mark.parametrize(
    ("location", "page", "message"),
    [
        ("https://web.snelstart.nl?state=wrong&code=fixture", "", "callback"),
        ("/u/mfa-otp-challenge", "<form/>", "requires interactive sign-in"),
        ("/u/login/password", "<form/>", "page changed"),
    ],
)
def test_login_stops_before_sending_credentials_to_an_unexpected_page(
    store, location, page, message
):
    store.write("credentials.json", {"username": "user@example.test", "password": "fixture"})
    original_tokens = store.read("tokens.json")

    def handle(request):
        assert request.method == "GET" and request.url.host == "login.snelstart.nl"
        if request.url.path == "/authorize":
            return httpx.Response(302, headers={"Location": location})
        return httpx.Response(200, text=page)

    with (
        httpx.Client(transport=httpx.MockTransport(handle)) as http,
        pytest.raises(SnelStartError, match=message),
    ):
        Auth(store, http).login()
    assert store.read("tokens.json") == original_tokens


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        (httpx.Response(200, text="not JSON"), "Invalid response"),
        (httpx.Response(200, json={"refresh_token": "unused"}), "no access token"),
    ],
)
def test_invalid_refresh_does_not_replace_saved_tokens(store, reply, message):
    original_tokens = store.read("tokens.json")
    with (
        httpx.Client(transport=httpx.MockTransport(lambda request: reply)) as http,
        pytest.raises(SnelStartError, match=message),
    ):
        Auth(store, http).access_token(force=True)
    assert store.read("tokens.json") == original_tokens


def test_universal_login_pkce_and_form_encoding(store):
    password = "private + percent% & equals="
    store.write("credentials.json", {"username": "user@test.nl", "password": password})
    oauth = {}

    def handle(request):
        path = request.url.path
        if path == "/authorize":
            oauth.update(dict(request.url.params))
            return httpx.Response(302, headers={"Location": "/u/login/identifier"})
        if path == "/u/login/identifier":
            if request.method == "GET":
                return httpx.Response(
                    200,
                    text='<form method="POST"><input name="state" value="flow"><input name="username"></form>',
                )
            assert parse_qs(request.content.decode())["username"] == ["user@test.nl"]
            return httpx.Response(302, headers={"Location": "/u/login/password"})
        if path == "/u/login/password":
            if request.method == "GET":
                return httpx.Response(
                    200,
                    text='<form><input name="state" value="flow"><input name="password" type="password"></form>',
                )
            assert parse_qs(request.content.decode())["password"] == [password]
            return httpx.Response(
                302,
                headers={
                    "Location": "https://web.snelstart.nl?"
                    + urlencode({"code": "the-code", "state": oauth["state"]})
                },
            )
        if path == "/oauth/token":
            body = json.loads(request.content)
            assert body["code"] == "the-code"
            assert len(body["code_verifier"]) >= 43
            assert oauth["code_challenge_method"] == "S256"
            return httpx.Response(
                200, json={"access_token": token(), "refresh_token": "independent"}
            )
        pytest.fail("Unexpected network destination")

    auth = Auth(store, httpx.Client(transport=httpx.MockTransport(handle)))
    auth.login()
    assert store.read("tokens.json")["refresh_token"] == "independent"


@pytest.mark.parametrize(
    "target",
    [
        "http://login.snelstart.nl/x",
        "https://evil.test/x",
        "https://login.snelstart.nl@evil.test/x",
    ],
)
def test_login_rejects_external_redirects(store, target):
    store.write("credentials.json", {"username": "user@test.nl", "password": "private"})
    auth = Auth(
        store,
        httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(302, headers={"Location": target})
            )
        ),
    )
    with pytest.raises(SnelStartError, match="unexpected destination"):
        auth.login()


def test_har_form_values_decode_exactly_once():
    data = {"username": "user@test.nl", "password": "a+b%40 &="}
    request = {
        "postData": {
            "mimeType": "application/x-www-form-urlencoded",
            "text": urlencode(data),
            "params": [{"name": "username", "value": "user%40test.nl"}],
        }
    }
    assert request_data(request) == data


def test_har_import_ignores_lookalike_hosts_and_keeps_last_rotation(store, tmp_path):
    def entry(host, access, refresh):
        body = json.dumps({"access_token": access, "refresh_token": refresh}).encode()
        return {
            "startedDateTime": "2020-01-01T12:00:00Z",
            "request": {
                "url": f"https://{host}/oauth/token",
                "method": "POST",
                "postData": {
                    "mimeType": "application/json",
                    "text": json.dumps({"client_id": CLIENT_ID}),
                },
            },
            "response": {
                "status": 200,
                "content": {"encoding": "base64", "text": base64.b64encode(body).decode()},
            },
        }

    path = tmp_path / "capture.har"
    path.write_text(
        json.dumps(
            {
                "log": {
                    "entries": [
                        entry("login.snelstart.nl", token(), "first"),
                        entry("login.snelstart.nl", token(), "latest"),
                        entry("login.snelstart.nl.evil.test", token(OTHER), "evil"),
                    ]
                }
            }
        )
    )
    auth = Auth(store, httpx.Client())
    result = import_har(path, store, auth)
    assert result["password_saved"] is False
    assert store.read("tokens.json")["refresh_token"] == "latest"
    assert not (store.directory / "credentials.json").exists()


@pytest.mark.parametrize(
    ("capture", "error"),
    [
        (b"{", "Invalid HAR export"),
        (b"{}", "Invalid HAR export"),
        (b'{"log": {"entries": []}}', "no SnelStart OAuth token"),
    ],
)
def test_rejected_har_keeps_existing_tokens(store, tmp_path, capture, error):
    path = tmp_path / "invalid.har"
    path.write_bytes(capture)
    existing = store.read("tokens.json")
    with (
        httpx.Client(
            transport=httpx.MockTransport(lambda _: pytest.fail("Unexpected network"))
        ) as http,
        pytest.raises(SnelStartError, match=error),
    ):
        import_har(path, store, Auth(store, http))
    assert store.read("tokens.json") == existing


def test_api_guards_run_before_network(store):
    def handle(request):
        pytest.fail("Blocked operation reached the network")

    client = Client(store, httpx.Client(transport=httpx.MockTransport(handle)))
    with pytest.raises(SnelStartError, match="Unknown operation"):
        client.request("GET https://evil.test")
    with pytest.raises(SnelStartError, match="Writing is disabled"):
        client.request("POST /MemoriaalBoekingen/Create", body={})
    with pytest.raises(SnelStartError, match="Unknown query parameter"):
        client.request("GET /Grootboek/GetAllMinimal", {"api_key": "secret"})
    with pytest.raises(SnelStartError, match="Missing query parameters"):
        client.request("GET /Purchases/Get")


def test_admin_open_checks_access(store):
    requests = []

    def handle(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=[{"id": 10, "identifier": ADMIN}])

    client = Client(store, httpx.Client(transport=httpx.MockTransport(handle)))
    with pytest.raises(SnelStartError, match="unavailable"):
        client.select_administration(OTHER)
    assert requests == ["/Administrations/All"]


def test_read_401_refresh_once_and_write_never_retried(store):
    requests = []

    def handle(request):
        requests.append(request.url.path)
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": token(), "refresh_token": "rotated"})
        return httpx.Response(401, text="SECRET")

    client = Client(store, httpx.Client(transport=httpx.MockTransport(handle)))
    with pytest.raises(SnelStartError) as error:
        client._send("GET", "/Grootboek/GetAllMinimal", administration=ADMIN)
    assert "SECRET" not in str(error.value)
    assert requests == ["/Grootboek/GetAllMinimal", "/oauth/token", "/Grootboek/GetAllMinimal"]
    requests.clear()
    with pytest.raises(SnelStartError, match="was not retried"):
        client._send("POST", "/MemoriaalBoekingen/Create", body={}, administration=ADMIN)
    assert requests == ["/MemoriaalBoekingen/Create"]


def test_status_never_contains_credentials(store):
    store.write("credentials.json", {"username": "user@test.nl", "password": "private-password"})
    status = json.dumps(Client(store).status())
    assert "private-password" not in status
    assert "old-refresh" not in status
    assert token() not in status


def test_all_specialized_operations_match_catalog():
    expected = {
        "GET /Grootboek/GetBalansResultaatAndRubrieken": ["datumTotEnMet"],
        "GET /MemoriaalBoekingen/GetDetails": ["publicIdentifier"],
        "GET /BalansBoekingen/GetDetails": ["publicIdentifier"],
        "GET /Purchases/Get": ["journaalpostIdentifier"],
    }
    for operation, params in expected.items():
        assert catalog()[operation]["query_parameters"] == params
        assert catalog()[operation]["read_only"]


def test_server_tools_have_schemas_and_annotations(store):
    import asyncio

    server = create_server(Client(store))
    tools = asyncio.run(server.list_tools())
    by_name = {tool.name: tool for tool in tools}
    assert by_name["snelstart_download_document"].annotations.readOnlyHint is True
    assert by_name["snelstart_search_sales"].annotations.readOnlyHint is True
    assert by_name["snelstart_bank_entries"].annotations.readOnlyHint is True
    assert by_name["snelstart_balance_sheet"].inputSchema["required"] == ["through_date"]
    assert by_name["snelstart_read"].annotations.readOnlyHint is True
    assert by_name["snelstart_write"].annotations.readOnlyHint is False
    assert all(tool.outputSchema is not None for tool in tools)
    upload = by_name["snelstart_upload_purchase_pdf"]
    assert set(upload.inputSchema["required"]) == {"administration_id", "file_path"}
    assert upload.inputSchema["properties"]["administration_id"]["format"] == "uuid"
