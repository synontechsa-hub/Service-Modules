import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth.config import AuthConfig
from auth.exceptions import (
    AccountDisabledError,
    AccountLockedError,
    DuplicateUserError,
    InvalidCredentialsError,
    InvalidTokenError,
)
from auth.models import AuthBase, RefreshToken, User
from auth.schemas import UserCreate, UserLogin
from auth.router import get_auth_router, get_current_user_dependency
from auth.security import SecurityManager
from auth.service import AuthService


def _key_pair(key_size: int = 2048) -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


@pytest.fixture(scope="session")
def rsa_keys() -> tuple[str, str]:
    return _key_pair()


@pytest.fixture
def auth_config(rsa_keys: tuple[str, str]) -> AuthConfig:
    private_key, public_key = rsa_keys
    return AuthConfig(
        jwt_private_key=private_key,
        jwt_public_key=public_key,
        secret_key="test-secret-key-that-is-at-least-32-bytes",
        jwt_issuer="test-product",
        jwt_audience="test-product-api",
        max_failed_logins=2,
    )


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(AuthBase.metadata.create_all)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


def test_config_rejects_unsafe_or_unknown_values(rsa_keys: tuple[str, str]) -> None:
    private_key, public_key = rsa_keys
    common = {
        "jwt_private_key": private_key,
        "jwt_public_key": public_key,
        "jwt_issuer": "product",
        "jwt_audience": "product-api",
    }
    with pytest.raises(ValidationError):
        AuthConfig(**common, secret_key="too-short")
    with pytest.raises(ValidationError):
        AuthConfig(**common, secret_key="x" * 32, misspelled_setting=True)
    with pytest.raises(ValidationError):
        AuthConfig(
            jwt_private_key=private_key,
            jwt_public_key=public_key,
            secret_key="x" * 32,
            jwt_issuer=" ",
            jwt_audience="product-api",
        )


def test_security_rejects_weak_or_mismatched_keys(rsa_keys: tuple[str, str]) -> None:
    private_key, public_key = rsa_keys
    _, other_public_key = _key_pair()
    mismatched = AuthConfig(
        jwt_private_key=private_key,
        jwt_public_key=other_public_key,
        secret_key="x" * 32,
        jwt_issuer="product",
        jwt_audience="product-api",
    )
    with pytest.raises(ValueError, match="does not match"):
        SecurityManager(mismatched)

    weak_private, weak_public = _key_pair(1024)
    weak = AuthConfig(
        jwt_private_key=weak_private,
        jwt_public_key=weak_public,
        secret_key="x" * 32,
        jwt_issuer="product",
        jwt_audience="product-api",
    )
    with pytest.raises(ValueError, match="at least 2048 bits"):
        SecurityManager(weak)


def test_access_tokens_enforce_claims_and_signature(auth_config: AuthConfig) -> None:
    security = SecurityManager(auth_config)
    user_id = uuid.uuid4()
    token, expires_in = security.create_access_token(user_id, {"role": "member"})
    payload = security.decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "member"
    assert payload["type"] == "access"
    assert expires_in == auth_config.access_token_expire_minutes * 60

    with pytest.raises(ValueError, match="reserved JWT claims"):
        security.create_access_token(user_id, {"sub": str(uuid.uuid4())})
    header, claims, signature = token.split(".")
    replacement = "A" if signature[0] != "A" else "B"
    tampered = ".".join((header, claims, replacement + signature[1:]))
    with pytest.raises(InvalidTokenError):
        security.decode_access_token(tampered)

    wrong_audience = jwt.encode(
        {
            "sub": str(user_id),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iss": auth_config.jwt_issuer,
            "aud": "another-product",
            "jti": str(uuid.uuid4()),
            "type": "access",
        },
        auth_config.jwt_private_key,
        algorithm="RS256",
    )
    with pytest.raises(InvalidTokenError):
        security.decode_access_token(wrong_audience)


def test_symmetric_encryption_round_trip(auth_config: AuthConfig) -> None:
    security = SecurityManager(auth_config)
    encrypted = security.encrypt_value("provider-token")
    assert encrypted != "provider-token"
    assert security.decrypt_value(encrypted) == "provider-token"


@pytest.mark.asyncio
async def test_service_accepts_only_matching_shared_security(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    security = SecurityManager(auth_config)
    assert AuthService(auth_config, db, security=security).security is security

    different_config = auth_config.model_copy(update={"jwt_audience": "different-api"})
    with pytest.raises(ValueError, match="same AuthConfig"):
        AuthService(different_config, db, security=security)


@pytest.mark.asyncio
async def test_registration_normalizes_and_rejects_duplicates(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)
    user = await service.register(
        UserCreate(
            username="  Example.User  ",
            email="Example@Email.COM",
            password="correct horse battery",
        )
    )
    assert user.username == "Example.User"
    assert user.email == "example@email.com"

    with pytest.raises(DuplicateUserError):
        await service.register(
            UserCreate(
                username="another-user",
                email="EXAMPLE@email.com",
                password="correct horse battery",
            )
        )


@pytest.mark.asyncio
async def test_login_lockout_does_not_enumerate_locked_accounts(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)
    user = await service.register(
        UserCreate(
            username="locked-user",
            email="locked@example.com",
            password="correct horse battery",
        )
    )
    username = user.username

    for _ in range(auth_config.max_failed_logins):
        with pytest.raises(InvalidCredentialsError):
            await service.login(
                UserLogin(identifier=username, password="wrong-password")
            )

    with pytest.raises(InvalidCredentialsError):
        await service.login(UserLogin(identifier=username, password="still-wrong"))
    with pytest.raises(AccountLockedError):
        await service.login(
            UserLogin(identifier=username, password="correct horse battery")
        )

    user = (
        await db.execute(select(User).where(User.username == username))
    ).scalar_one()
    user.locked_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db.commit()
    tokens = await service.login(
        UserLogin(identifier=" LOCKED@EXAMPLE.COM ", password="correct horse battery")
    )
    assert tokens.access_token
    assert user.failed_login_attempts == 0


@pytest.mark.asyncio
async def test_disabled_account_requires_valid_password_before_disclosure(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)
    user = await service.register(
        UserCreate(
            username="disabled-user",
            email="disabled@example.com",
            password="correct horse battery",
        )
    )
    username = user.username
    user.is_active = False
    await db.commit()

    with pytest.raises(InvalidCredentialsError):
        await service.login(UserLogin(identifier=username, password="wrong-password"))
    with pytest.raises(AccountDisabledError):
        await service.login(
            UserLogin(identifier=username, password="correct horse battery")
        )


@pytest.mark.asyncio
async def test_refresh_replay_revokes_the_live_token_family(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)
    user = await service.register(
        UserCreate(
            username="refresh-user",
            email="refresh@example.com",
            password="correct horse battery",
        )
    )
    first = await service.login(
        UserLogin(identifier=user.username, password="correct horse battery")
    )
    second = await service.refresh(first.refresh_token)

    with pytest.raises(InvalidTokenError):
        await service.refresh(first.refresh_token)
    with pytest.raises(InvalidTokenError):
        await service.refresh(second.refresh_token)

    records = (
        (await db.execute(select(RefreshToken).where(RefreshToken.user_id == user.id)))
        .scalars()
        .all()
    )
    assert len(records) == 2
    assert all(record.revoked for record in records)
    assert len({record.family_id for record in records}) == 1


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)
    user = await service.register(
        UserCreate(
            username="logout-user",
            email="logout@example.com",
            password="correct horse battery",
        )
    )
    tokens = await service.login(
        UserLogin(identifier=user.username, password="correct horse battery")
    )
    await service.logout(tokens.refresh_token)
    with pytest.raises(InvalidTokenError):
        await service.refresh(tokens.refresh_token)


@pytest.mark.asyncio
async def test_access_token_resolves_only_active_users(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)
    user = await service.register(
        UserCreate(
            username="active-user",
            email="active@example.com",
            password="correct horse battery",
        )
    )
    tokens = await service.login(
        UserLogin(identifier=user.username, password="correct horse battery")
    )
    resolved = await service.user_from_access_token(tokens.access_token)
    assert resolved.id == user.id

    user.is_active = False
    await db.commit()
    with pytest.raises(InvalidTokenError):
        await service.user_from_access_token(tokens.access_token)


@pytest.mark.asyncio
async def test_audit_failure_does_not_reverse_completed_auth(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    class BrokenAudit:
        async def log_action(self, **event: object) -> None:
            raise RuntimeError("audit unavailable")

    service = AuthService(auth_config, db, audit_service=BrokenAudit())
    user = await service.register(
        UserCreate(
            username="audit-user",
            email="audit@example.com",
            password="correct horse battery",
        )
    )
    assert user.id is not None
    assert (
        await db.execute(select(User).where(User.id == user.id))
    ).scalar_one().email == "audit@example.com"


@pytest.mark.asyncio
async def test_fastapi_router_and_current_user_dependency(
    db: AsyncSession, auth_config: AuthConfig
) -> None:
    service = AuthService(auth_config, db)

    async def get_auth_service() -> AuthService:
        return service

    app = FastAPI()
    app.include_router(get_auth_router(get_auth_service))
    current_user = get_current_user_dependency(get_auth_service)

    @app.get("/protected")
    async def protected(user: User = Depends(current_user)) -> dict[str, str]:
        return {"user_id": str(user.id)}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        registration = await client.post(
            "/auth/register",
            json={
                "username": "router-user",
                "email": "router@example.com",
                "password": "correct horse battery",
            },
        )
        assert registration.status_code == 201

        login = await client.post(
            "/auth/login",
            json={"identifier": "router-user", "password": "correct horse battery"},
        )
        assert login.status_code == 200
        tokens = login.json()

        missing = await client.get("/protected")
        assert missing.status_code == 401
        assert missing.headers["www-authenticate"] == "Bearer"

        authenticated = await client.get(
            "/protected",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert authenticated.status_code == 200
        assert authenticated.json()["user_id"] == registration.json()["id"]

        logout = await client.post(
            "/auth/logout", json={"refresh_token": tokens["refresh_token"]}
        )
        assert logout.status_code == 204


def test_schema_matches_the_orm_table_contract() -> None:
    schema = (
        (Path(__file__).parents[1] / "schema.sql").read_text(encoding="utf-8").lower()
    )
    assert set(AuthBase.metadata.tables) == {
        "auth_users",
        "auth_oauth_accounts",
        "auth_refresh_tokens",
    }
    for table_name in AuthBase.metadata.tables:
        assert f"create table if not exists {table_name}" in schema
    assert "family_id uuid not null" in schema
    assert "revoked_at timestamptz" in schema
