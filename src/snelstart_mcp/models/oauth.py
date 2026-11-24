"""SnelStart OAuth wire contracts and private profile records."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from ..enums import CodeChallengeMethod, OAuthGrant, OAuthResponseType


class PrivateModel(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)


class Credentials(PrivateModel):
    username: str | None = None
    password: SecretStr | None = None


class AuthorizationRequest(PrivateModel):
    client_id: str
    audience: str
    redirect_uri: str
    scope: str = "openid profile email offline_access"
    response_type: OAuthResponseType = OAuthResponseType.CODE
    code_challenge: str
    code_challenge_method: CodeChallengeMethod = CodeChallengeMethod.S256
    state: str = Field(repr=False)


class AuthorizationSession(PrivateModel):
    request: AuthorizationRequest
    verifier: SecretStr


class CodeExchangeRequest(PrivateModel):
    client_id: str
    redirect_uri: str
    grant_type: OAuthGrant = OAuthGrant.AUTHORIZATION_CODE
    code: SecretStr
    code_verifier: SecretStr

    def wire_payload(self) -> dict[str, str]:
        return {
            **self.model_dump(mode="json", exclude={"code", "code_verifier"}),
            "code": self.code.get_secret_value(),
            "code_verifier": self.code_verifier.get_secret_value(),
        }


class RefreshTokenRequest(PrivateModel):
    client_id: str
    redirect_uri: str
    grant_type: OAuthGrant = OAuthGrant.REFRESH_TOKEN
    refresh_token: SecretStr
    administration_id: UUID | None = Field(default=None, serialization_alias="administrationId")

    def wire_payload(self) -> dict[str, str]:
        return {
            **self.model_dump(
                mode="json", by_alias=True, exclude={"refresh_token"}, exclude_none=True
            ),
            "refresh_token": self.refresh_token.get_secret_value(),
        }


class TokenResponse(PrivateModel):
    access_token: SecretStr = Field(min_length=1)
    refresh_token: SecretStr | None = None
    scope: str | None = None
    expires_in: int = 0


class StoredTokens(PrivateModel):
    model_config = ConfigDict(extra="allow")

    access_token: SecretStr | None = None
    refresh_token: SecretStr | None = None
    scope: str | None = None
    expires_at: int | float | None = None

    def storage_data(self) -> dict:
        data = self.model_dump(
            mode="json", exclude={"access_token", "refresh_token"}, exclude_none=True
        )
        if self.access_token is not None:
            data["access_token"] = self.access_token.get_secret_value()
        if self.refresh_token is not None:
            data["refresh_token"] = self.refresh_token.get_secret_value()
        return data


class AdministrationClaim(PrivateModel):
    aid: UUID | None = None


class TokenDataClaim(PrivateModel):
    a: AdministrationClaim | None = None


class TokenClaims(PrivateModel):
    exp: int | float | None = None
    data: TokenDataClaim | None = None

    @property
    def administration_id(self) -> UUID | None:
        return self.data.a.aid if self.data is not None and self.data.a is not None else None
