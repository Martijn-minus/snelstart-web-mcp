"""SnelStart's own Authorization Code + PKCE login and rotating refresh tokens."""

import base64
import hashlib
import secrets
import time
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from uuid import UUID

import httpx
from pydantic import SecretStr, ValidationError

from .browser_login import is_web_callback, open_browser_callback
from .config import SnelStartError, Store
from .enums import LoginMethod
from .models.oauth import (
    AuthorizationRequest,
    AuthorizationSession,
    CodeExchangeRequest,
    Credentials,
    RefreshTokenRequest,
    StoredTokens,
    TokenClaims,
    TokenResponse,
)

LOGIN_ORIGIN = "https://login.snelstart.nl"
CLIENT_ID = "olaMwCEeCfRGgx1n8EF1cnPxIY7DYE40"
AUDIENCE = "https://webapi.snelstart.nl"
REDIRECT_URI = "https://web.snelstart.nl"


def claims(token: str) -> TokenClaims:
    """Read expiry and administration hints. The API verifies the token signature."""
    try:
        part = token.split(".")[1]
        return TokenClaims.model_validate_json(
            base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))
        )
    except (IndexError, ValueError, TypeError):
        return TokenClaims()


def new_authorization() -> AuthorizationSession:
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
    return AuthorizationSession(
        verifier=SecretStr(verifier),
        request=AuthorizationRequest(
            client_id=CLIENT_ID,
            audience=AUDIENCE,
            redirect_uri=REDIRECT_URI,
            code_challenge=challenge.decode().rstrip("="),
            state=secrets.token_urlsafe(32),
        ),
    )


def authorization_url(session: AuthorizationSession) -> str:
    return LOGIN_ORIGIN + "/authorize?" + urlencode(session.request.model_dump(mode="json"))


class LoginForm(HTMLParser):
    def __init__(self, html: str):
        super().__init__()
        self.fields = {}
        self.action = ""
        self.in_form = False
        self.found = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form" and not self.found:
            self.in_form = self.found = True
            self.action = attrs.get("action", "")
        if (
            self.in_form
            and tag == "input"
            and attrs.get("name")
            and attrs.get("type") not in {"submit", "button", "checkbox"}
        ):
            self.fields[attrs["name"]] = attrs.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False


class Auth:
    def __init__(self, store: Store, http: httpx.Client):
        self.store, self.http = store, http

    def stored_tokens(self) -> StoredTokens:
        try:
            return StoredTokens.model_validate(self.store.read("tokens.json"))
        except ValidationError:
            raise SnelStartError("Invalid token profile. Sign in again.") from None

    def credentials(self) -> Credentials:
        try:
            return Credentials.model_validate(self.store.read("credentials.json"))
        except ValidationError:
            raise SnelStartError("Invalid saved sign-in credentials.") from None

    def save_tokens(
        self,
        tokens: TokenResponse,
        previous: StoredTokens | None = None,
        *,
        observed_at: float | None = None,
    ) -> StoredTokens:
        result = previous.model_copy() if previous is not None else StoredTokens()
        result.access_token = tokens.access_token
        if "refresh_token" in tokens.model_fields_set:
            result.refresh_token = tokens.refresh_token
        if "scope" in tokens.model_fields_set:
            result.scope = tokens.scope
        hints = claims(tokens.access_token.get_secret_value())
        result.expires_at = (
            hints.exp
            if hints.exp is not None
            else (observed_at if observed_at is not None else time.time()) + tokens.expires_in
        )
        self.store.write("tokens.json", result.storage_data())
        return result

    def exchange(self, payload: CodeExchangeRequest | RefreshTokenRequest) -> TokenResponse:
        response = self.http.post(LOGIN_ORIGIN + "/oauth/token", json=payload.wire_payload())
        if response.status_code != 200:
            raise SnelStartError(
                f"SnelStart sign-in was rejected (HTTP {response.status_code}). "
                "Run 'snelstart-mcp login' locally or use 'login --method browser'."
            )
        try:
            raw = response.json()
        except ValueError:
            raise SnelStartError("Invalid response from the sign-in server.") from None
        try:
            return TokenResponse.model_validate(raw)
        except ValidationError:
            if isinstance(raw, dict) and not raw.get("access_token"):
                raise SnelStartError("The sign-in server returned no access token.") from None
            raise SnelStartError("Invalid response from the sign-in server.") from None

    def _refresh(self, tokens: StoredTokens, administration: UUID | None) -> StoredTokens:
        if not tokens.refresh_token:
            raise SnelStartError("No refresh token. Run 'snelstart-mcp login --method browser'.")
        payload = RefreshTokenRequest(
            client_id=CLIENT_ID,
            redirect_uri=REDIRECT_URI,
            refresh_token=tokens.refresh_token,
            administration_id=administration,
        )
        return self.save_tokens(self.exchange(payload), tokens)

    def access_token(self, administration: str | None = None, force: bool = False) -> str:
        identifier = UUID(administration) if administration else None
        with self.store.locked():
            tokens = self.stored_tokens()
            access = tokens.access_token.get_secret_value() if tokens.access_token else ""
            correct_admin = not identifier or claims(access).administration_id == identifier
            if (
                not force
                and access
                and (tokens.expires_at or 0) > time.time() + 90
                and correct_admin
            ):
                return access
            if tokens.refresh_token:
                try:
                    return self._check_context(self._refresh(tokens, identifier), identifier)
                except SnelStartError:
                    if not self.credentials().password:
                        raise
            tokens = self._login()
            if identifier:
                tokens = self._refresh(tokens, identifier)
            return self._check_context(tokens, identifier)

    @staticmethod
    def _check_context(tokens: StoredTokens, administration: UUID | None) -> str:
        if not tokens.access_token:
            raise SnelStartError("The sign-in server returned no access token.")
        token = tokens.access_token.get_secret_value()
        if administration and claims(token).administration_id != administration:
            raise SnelStartError("The returned token does not match the selected administration.")
        return token

    def login(self, method: LoginMethod = LoginMethod.CREDENTIALS) -> StoredTokens:
        if method is LoginMethod.BROWSER:
            session = new_authorization()
            callback = open_browser_callback(authorization_url(session))
            with self.store.locked():
                tokens = self._exchange_callback(callback, session)
                if not tokens.refresh_token:
                    raise SnelStartError("SnelStart returned no refresh token for browser sign-in.")
                return self.save_tokens(tokens)
        with self.store.locked():
            return self._login()

    def _exchange_callback(self, url: str, session: AuthorizationSession) -> TokenResponse:
        query = parse_qs(urlsplit(url).query, keep_blank_values=True)
        states = query.get("state", [])
        if (
            not is_web_callback(url)
            or len(states) != 1
            or not secrets.compare_digest(states[0].encode(), session.request.state.encode())
        ):
            raise SnelStartError("The OAuth callback could not be validated.")
        if "error" in query:
            raise SnelStartError("SnelStart did not authorize this browser sign-in.")
        codes = query.get("code", [])
        if len(codes) != 1 or not codes[0]:
            raise SnelStartError("The OAuth callback could not be validated.")
        return self.exchange(
            CodeExchangeRequest(
                client_id=CLIENT_ID,
                redirect_uri=REDIRECT_URI,
                code=SecretStr(codes[0]),
                code_verifier=session.verifier,
            )
        )

    def _login(self) -> StoredTokens:
        credentials = self.credentials()
        if not credentials.username or not credentials.password:
            raise SnelStartError(
                "No saved sign-in. Run 'snelstart-mcp login --method browser' "
                "or import a token-only HAR."
            )
        session = new_authorization()
        url = authorization_url(session)
        # Fresh cookies isolate this session from a previous sign-in and from Chrome.
        self.http.cookies.clear()
        response = self.http.get(url)
        submitted_password = False
        for _ in range(20):
            current = urlsplit(str(response.url))
            if response.is_redirect:
                location = urljoin(str(response.url), response.headers.get("location", ""))
                if is_web_callback(location):
                    return self.save_tokens(self._exchange_callback(location, session))
                self._check_login_url(location)
                response = self.http.get(location)
                continue
            allowed = {
                "/u/login/identifier",
                "/u/login/password",
                "/u/login",
                "/u/mfa-detect-browser-capabilities",
            }
            if current.path not in allowed or response.status_code != 200:
                raise SnelStartError(
                    "SnelStart requires interactive sign-in, such as MFA or CAPTCHA. "
                    "Run 'snelstart-mcp login --method browser'."
                )
            form = LoginForm(response.text)
            if not form.found or "state" not in form.fields:
                raise SnelStartError("The SnelStart sign-in page changed. Use a HAR export.")
            fields = dict(form.fields)
            if current.path != "/u/mfa-detect-browser-capabilities":
                fields["username"] = credentials.username
                if "password" in fields:
                    if submitted_password:
                        raise SnelStartError("SnelStart rejected the saved password.")
                    fields["password"] = credentials.password.get_secret_value()
                    submitted_password = True
            else:
                fields.update(
                    {"action": "default", "js-available": "false", "webauthn-available": "false"}
                )
            action = urljoin(str(response.url), form.action)
            self._check_login_url(action)
            response = self.http.post(action, data=fields)
        raise SnelStartError("Sign-in did not complete. Use a fresh HAR export.")

    @staticmethod
    def _check_login_url(url: str):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc != "login.snelstart.nl":
            raise SnelStartError("Sign-in stopped at an unexpected destination.")
