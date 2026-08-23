# Auth Service Module

Drop-in authentication package for FastAPI applications using SQLAlchemy async sessions.

## Scope
Provides local username/email registration, Argon2id password hashing, RS256 access tokens, opaque refresh-token rotation, replay detection by token family, brute-force lockout, logout/revocation, and a FastAPI current-user dependency.

`OAuthAccount` is only the persistence primitive for linking external identities. Provider redirect/callback flows are intentionally host-owned and are not implemented by this module.

## Architecture contract
- Copy-in package: no `main.py`, database engine, Docker runtime, or `.env` loader.
- The host creates one `AsyncSession` per request/task and injects it into `AuthService`.
- The host supplies `AuthConfig` directly. The module never reads environment variables or secret files.
- The host owns migrations. `schema.sql` documents the required PostgreSQL/Supabase schema.
- The optional audit hook is fail-open: audit outages are logged and do not turn a completed auth action into an API failure.

## Configuration
Generate an RSA key pair of at least 2048 bits outside the repository. Load the PEM strings through the host's secret/config system:

```python
from auth import AuthConfig

auth_config = AuthConfig(
    jwt_private_key=settings.AUTH_JWT_PRIVATE_KEY,
    jwt_public_key=settings.AUTH_JWT_PUBLIC_KEY,
    secret_key=settings.AUTH_SECRET_KEY,
    jwt_issuer="my-product",
    jwt_audience="my-product-api",
)
```

`secret_key` must be at least 32 bytes. Never commit private keys or production secrets.

## Wiring
```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from auth import AuthService, get_auth_router, get_current_user_dependency

app = FastAPI()

async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(config=auth_config, db=db, audit_service=audit_service)

app.include_router(get_auth_router(get_auth_service))
get_current_user = get_current_user_dependency(get_auth_service)
```

## Refresh-token security
Refresh tokens are stored only as SHA-256 hashes. Each login starts a new token family. A normal refresh revokes the used token and issues its replacement in the same family. Reuse of a revoked token is treated as replay and revokes the remaining live tokens in that family.

## Security behavior
- Passwords: Argon2id via `argon2-cffi`.
- JWTs: RS256 only; issuer, audience, expiry, issued-at, subject, JWT ID, and token type are required on decode.
- Reserved JWT claims cannot be overridden through `extra_claims`.
- RSA keys are validated for type, minimum size, and pairing.
- Unknown-user login performs a dummy Argon2 verification to reduce account-enumeration timing differences.
- Login counters and refresh rotation use database row locks on PostgreSQL to avoid concurrent lost updates/double rotation.
- Revoked refresh records are retained beyond expiry for the configured replay-detection retention window.

## Integration note
`AsyncSession` is stateful and must not be shared across concurrent asyncio tasks. Use one session per request/task.
