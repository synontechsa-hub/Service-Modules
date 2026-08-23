import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .config import AuthConfig
from .exceptions import InvalidTokenError

_RESERVED_CLAIMS = {"sub", "iat", "exp", "iss", "aud", "jti", "type"}


class SecurityManager:
    def __init__(self, config: AuthConfig):
        self.config = config
        self._password_hasher = PasswordHasher(type=Type.ID)
        self._dummy_password_hash = self._password_hasher.hash(secrets.token_urlsafe(32))
        self._private_key, self._public_key = self._load_and_validate_jwt_keys()
        self._fernet = self._build_fernet()

    def _load_and_validate_jwt_keys(self) -> tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        try:
            private_key = serialization.load_pem_private_key(self.config.jwt_private_key.encode("utf-8"), password=None)
            public_key = serialization.load_pem_public_key(self.config.jwt_public_key.encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid JWT PEM key material") from exc
        if not isinstance(private_key, rsa.RSAPrivateKey) or not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("JWT keys must be RSA keys")
        if private_key.key_size < 2048 or public_key.key_size < 2048:
            raise ValueError("JWT RSA keys must be at least 2048 bits")
        if private_key.public_key().public_numbers() != public_key.public_numbers():
            raise ValueError("JWT public key does not match the private key")
        return private_key, public_key

    def _build_fernet(self) -> Fernet:
        hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"auth-module-fernet-v1", info=b"auth-module-encryption")
        secret = self.config.secret_key.get_secret_value().encode("utf-8")
        return Fernet(base64.urlsafe_b64encode(hkdf.derive(secret)))

    def hash_password(self, password: str) -> str:
        return self._password_hasher.hash(password)

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        try:
            return self._password_hasher.verify(password_hash, plain_password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def burn_password_check(self, password: str) -> None:
        self.verify_password(password, self._dummy_password_hash)

    def password_needs_rehash(self, password_hash: str) -> bool:
        try:
            return self._password_hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return False

    def create_access_token(self, user_id: uuid.UUID, extra_claims: dict[str, Any] | None = None) -> tuple[str, int]:
        if extra_claims and _RESERVED_CLAIMS.intersection(extra_claims):
            raise ValueError("extra_claims may not override reserved JWT claims")
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(minutes=self.config.access_token_expire_minutes)
        payload: dict[str, Any] = {"sub": str(user_id), "iat": now, "exp": now + expires_delta, "iss": self.config.jwt_issuer, "aud": self.config.jwt_audience, "jti": str(uuid.uuid4()), "type": "access"}
        if extra_claims:
            payload.update(extra_claims)
        return jwt.encode(payload, self._private_key, algorithm="RS256"), int(expires_delta.total_seconds())

    def decode_access_token(self, token: str) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self._public_key, algorithms=["RS256"], audience=self.config.jwt_audience, issuer=self.config.jwt_issuer, options={"require": list(_RESERVED_CLAIMS)})
            if payload.get("type") != "access":
                raise InvalidTokenError("Invalid access token.")
            uuid.UUID(str(payload["sub"]))
            uuid.UUID(str(payload["jti"]))
            return payload
        except InvalidTokenError:
            raise
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError("Invalid access token.") from exc

    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)

    def hash_refresh_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def get_refresh_token_expiry(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=self.config.refresh_token_expire_days)

    def encrypt_value(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt_value(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
