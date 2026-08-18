import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from passlib.context import CryptContext

from .config import AuthConfig

# Argon2id for new hashes, supports verifying bcrypt
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


class SecurityManager:
    def __init__(self, config: AuthConfig):
        self.config = config

    # --- Passwords ---
    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, password_hash: str) -> bool:
        return pwd_context.verify(plain_password, password_hash)

    # --- Access Tokens (RS256) ---
    def create_access_token(self, user_id: uuid.UUID, extra_claims: Optional[dict] = None) -> Tuple[str, int]:
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(minutes=self.config.access_token_expire_minutes)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "iat": now,
            "exp": expire,
            "iss": self.config.jwt_issuer,
            "aud": self.config.jwt_audience,
            "jti": str(uuid.uuid4()),
            "type": "access",
        }
        if extra_claims:
            payload.update(extra_claims)

        token = jwt.encode(payload, self.config.jwt_private_key, algorithm="RS256")
        return token, int(expires_delta.total_seconds())

    def decode_access_token(self, token: str) -> dict:
        return jwt.decode(
            token,
            self.config.jwt_public_key,
            algorithms=["RS256"],
            audience=self.config.jwt_audience,
            issuer=self.config.jwt_issuer,
        )

    # --- Refresh Tokens ---
    def generate_refresh_token(self) -> str:
        return secrets.token_urlsafe(64)

    def hash_refresh_token(self, token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def get_refresh_token_expiry(self) -> datetime:
        return datetime.now(timezone.utc) + timedelta(days=self.config.refresh_token_expire_days)

    # --- Symmetric Encryption ---
    def _get_fernet(self) -> Fernet:
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"auth-fernet-salt",
            info=b"auth-fernet-info",
        )
        key = base64.urlsafe_b64encode(hkdf.derive(self.config.secret_key.encode()))
        return Fernet(key)

    def encrypt_value(self, plaintext: str) -> str:
        return self._get_fernet().encrypt(plaintext.encode()).decode()

    def decrypt_value(self, ciphertext: str) -> str:
        return self._get_fernet().decrypt(ciphertext.encode()).decode()
