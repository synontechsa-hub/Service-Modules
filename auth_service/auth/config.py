from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthConfig(BaseSettings):
    """
    Configuration for the Auth module.
    Settings are prefixed with AUTH_ in environment variables.
    """
    # JWT
    private_key_path: str = Field("./keys/private.pem", description="Path to RSA private key")
    public_key_path: str = Field("./keys/public.pem", description="Path to RSA public key")
    access_token_expire_minutes: int = Field(15, description="Access token TTL")
    refresh_token_expire_days: int = Field(30, description="Refresh token TTL")
    jwt_issuer: str = Field("auth-service", description="JWT iss claim")
    jwt_audience: str = Field("core", description="JWT aud claim")

    # Security
    secret_key: str = Field(..., description="Secret key for symmetric encryption (e.g. Fernet)")
    max_failed_logins: int = Field(5, description="Max failed attempts before lockout")
    lockout_minutes: int = Field(15, description="Lockout duration")

    # OAuth - Google (Optional)
    google_client_id: str = ""
    google_client_secret: str = ""

    # OAuth - Facebook (Optional)
    facebook_client_id: str = ""
    facebook_client_secret: str = ""

    # OAuth - Discord (Optional)
    discord_client_id: str = ""
    discord_client_secret: str = ""

    # OAuth - Apple (Optional)
    apple_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key_path: str = "./keys/apple_auth_key.p8"

    model_config = SettingsConfigDict(env_prefix="AUTH_", extra="ignore")

    @property
    def jwt_private_key(self) -> str:
        return Path(self.private_key_path).read_text()

    @property
    def jwt_public_key(self) -> str:
        return Path(self.public_key_path).read_text()


@lru_cache
def get_auth_config() -> AuthConfig:
    return AuthConfig()
