"""Import only first-party login fields; never persist a raw HAR in the repository."""

import base64
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from pydantic import ValidationError

from .auth import CLIENT_ID, Auth, claims
from .config import SnelStartError, Store
from .models.oauth import TokenResponse
from .models.responses import HarImportResponse


def response_json(entry: dict):
    content = entry.get("response", {}).get("content", {})
    text = content.get("text", "")
    try:
        if content.get("encoding") == "base64":
            text = base64.b64decode(text, validate=True).decode()
        return json.loads(text)
    except ValueError:
        return None


def request_data(request: dict) -> dict:
    data = request.get("postData", {})
    if "json" in data.get("mimeType", ""):
        try:
            return json.loads(data.get("text", "{}"))
        except ValueError:
            return {}
    # Chrome's params array may still be percent-encoded. Decode the original
    # application/x-www-form-urlencoded body once, including literal '+'/'%'.
    if data.get("text"):
        return dict(parse_qsl(data["text"], keep_blank_values=True))
    if data.get("params"):
        return {p["name"]: p.get("value", "") for p in data["params"]}
    return {}


def import_har(path: Path, store: Store, auth: Auth, save_password: bool = False) -> dict:
    try:
        entries = json.loads(path.read_text())["log"]["entries"]
    except (ValueError, KeyError):
        raise SnelStartError("Invalid HAR export.") from None
    tokens = None
    observed_at = None
    credentials = {}
    observed = []
    for entry in sorted(entries, key=lambda e: e.get("startedDateTime", "")):
        request = entry.get("request", {})
        url = urlsplit(request.get("url", ""))
        data = request_data(request)
        if url.scheme != "https":
            continue
        if url.netloc == "login.snelstart.nl":
            if (
                url.path in {"/u/login/password", "/u/login"}
                and request.get("method") == "POST"
                and save_password
                and data.get("username")
                and data.get("password")
            ):
                credentials = {"username": data["username"], "password": data["password"]}
            if url.path == "/oauth/token" and data.get("client_id") == CLIENT_ID:
                body = response_json(entry)
                if (
                    entry.get("response", {}).get("status") == 200
                    and isinstance(body, dict)
                    and body.get("access_token")
                ):
                    try:
                        tokens = TokenResponse.model_validate(body)
                    except ValidationError:
                        continue
                    observed_at = None
                    try:
                        observed_at = datetime.fromisoformat(entry["startedDateTime"]).timestamp()
                    except (KeyError, ValueError):
                        pass
        if url.netloc == "webapi.snelstart.nl" and request.get("method") != "OPTIONS":
            observed.append(
                {
                    "operation": request["method"] + " " + url.path,
                    "query_parameters": sorted(
                        {k for k, _ in parse_qsl(url.query, keep_blank_values=True)}
                    ),
                    "body_fields": sorted(data) if isinstance(data, dict) else [],
                    "response_status": entry.get("response", {}).get("status"),
                }
            )
    if not tokens:
        raise SnelStartError(
            "The HAR has no SnelStart OAuth token response. Start recording before sign-in "
            "and enable Preserve log before exporting again."
        )
    with store.locked():
        auth.save_tokens(tokens, observed_at=observed_at)
        if credentials:
            store.write("credentials.json", credentials)
        config = store.read("config.json")
        administration = claims(tokens.access_token.get_secret_value()).administration_id
        if administration:
            config.setdefault("administration_id", str(administration))
        config.setdefault("allow_writes", False)
        store.write("config.json", config)
        unique = {item["operation"]: item for item in observed}
        store.write("observed-api.json", unique)
    return HarImportResponse(
        imported=True, password_saved=bool(credentials), observed_operations=len(unique)
    ).model_dump()
