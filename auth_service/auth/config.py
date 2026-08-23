from pydantic import BaseModel, Field, SecretStr, field_validator


class AuthConfig(BaseModel):
    """Host-supplied configuration for the auth module."""

    jwt_private_key: str = Field(..., description="PEM-encoded RSA private key used to sign access tokens")
    jwt_public_key: str = Field(..., description="PEM-encoded RSA public key used to verify access tokens")
    secret_key: SecretStr = Field(..., description="High-entropy application secret used for symmetric encryption")
    access_token_expire_minutes: int = Field(15, ge=1, le=1440)
    refresh_token_expire_days: int = Field(30, ge=1, le=365)
    refresh_token_retention_days: int = Field(7, ge=0, le=90)
    jwt_issuer: str = Field("auth-service", min_length=1, max_length=255)
    jwt_audience: str = Field("core", min_length=1, max_length=255)
    max_failed_logins: int = Field(5, ge=1, le=100)
    lockout_minutes: int = Field(15, ge=1, le=1440)

    @field_validator("jwt_private_key", "jwt_public_key")
    @classmethod
    def validate_pem_present(cls, value: str) -> str:
        value = value.strip()
        if "-----BEGIN" not in value or "-----END" not in value:
            raise ValueError("JWT keys must be PEM-encoded key material")
        return value

    @field_validator("secret_key")
    @classmethod
    def validate_secret_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value().encode("utf-8")) < 32:
            raise ValueError("secret_key must be at least 32 bytes")
        return value
