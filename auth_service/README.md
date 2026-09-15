# Auth Service Module

Reusable authentication backend for Python/FastAPI applications using SQLAlchemy async sessions and PostgreSQL-compatible databases.

## Scope

The module provides:

- Local username/email registration with normalized, case-insensitive email uniqueness.
- Argon2id password hashing and automatic rehashing when parameters change.
- RS256 access tokens with strict issuer, audience, expiry, subject, JWT ID, and token-type validation.
- Opaque, hashed refresh tokens with rotation, token families, replay detection, and logout revocation.
- Brute-force lockout with account-enumeration-resistant failure behavior.
- A FastAPI router and reusable Bearer/current-user dependency.
- Optional fail-open audit events without a hard dependency on another library module.

OAuth provider redirects/callbacks, password recovery, email delivery/verification workflows, MFA, and browser token storage are intentionally host-owned. `OAuthAccount` is only the persistence primitive for linking an external identity.

## Architecture contract

- Copy-in package: `auth/` has no application entry point, database engine, Docker runtime, or environment loader.
- The host creates one `AsyncSession` per request or task and injects it into `AuthService`.
- The host constructs `AuthConfig` explicitly. The module never reads environment variables or secret files.
- The host owns database migrations. This repository's `schema.sql` is the canonical initial PostgreSQL/Supabase schema.
- No key files or environment files are included. Generate application-specific secrets when integrating the module.

## Files to copy

Copy these into the host project:

- `auth/` — importable Python package.
- `schema.sql` — translate into the host's migration system or apply to a new database.
- Runtime entries from `requirements.txt` — merge them with the host's dependency manifest.

Do not copy `tests/`, `pytest.ini`, or `requirements-dev.txt` into production unless the host wants to retain the module's verification suite.

## Configuration

Generate a matching RSA private/public key pair of at least 2048 bits outside source control. Load the PEM strings through the host's secret/configuration system.

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

`secret_key` must contain at least 32 UTF-8 bytes. Issuer and audience are mandatory so independently copied applications cannot accidentally trust each other's tokens. Unknown or misspelled configuration fields are rejected.

## FastAPI wiring

```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from auth import (
    AuthService,
    SecurityManager,
    User,
    get_auth_router,
    get_current_user_dependency,
)

app = FastAPI()
auth_security = SecurityManager(auth_config)  # validate keys and build crypto state once

async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(
        config=auth_config,
        db=db,
        audit_service=audit_service,  # optional
        security=auth_security,
    )

app.include_router(get_auth_router(get_auth_service))
get_current_user = get_current_user_dependency(get_auth_service)

@app.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": str(user.id), "email": user.email}
```

The included router exposes:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/auth/register` | Create a local account |
| `POST` | `/auth/login` | Issue access and refresh tokens |
| `POST` | `/auth/refresh` | Rotate a refresh token |
| `POST` | `/auth/logout` | Revoke a refresh token |

## Database contract

The ORM and `schema.sql` use the same three tables: `auth_users`, `auth_oauth_accounts`, and `auth_refresh_tokens`.

Email uniqueness is enforced with a unique index on `lower(email)`, not only by application normalization. Refresh-token family state is retained for a configurable period after expiry so replay can revoke the remaining live family.

For Supabase, the schema enables RLS without permissive policies. The application's direct database role must therefore be intentionally configured to access these tables, while anon/authenticated PostgREST access remains denied. Do not assume that every custom database role bypasses RLS.

If upgrading an older installation, write an explicit migration. `CREATE TABLE IF NOT EXISTS` does not retrofit `family_id`, `revoked_at`, constraints, or indexes onto existing tables.

## Security behavior

- Reserved JWT claims cannot be overridden through custom claims.
- RSA key type, minimum size, and private/public pairing are validated at startup.
- Invalid, malformed, incorrectly scoped, or incorrectly signed access tokens map to one public token error.
- Unknown-user login performs a dummy Argon2 verification to reduce timing differences.
- Password hashing and verification run outside the async event loop.
- Locked or disabled accounts are disclosed only after a correct password.
- Login counters and refresh rotation use PostgreSQL row locks to prevent lost updates and double rotation.
- Reusing a rotated refresh token revokes all remaining live tokens in that token family.
- Audit-hook failure is logged but cannot turn an already-committed auth action into an apparent failure.

## Host responsibilities

The host application must still provide:

- HTTPS, appropriate CORS policy, and secure client-side token handling.
- Rate limits for register, login, refresh, password recovery, and other abuse-sensitive routes.
- RSA and application-secret generation, storage, rotation, and incident response.
- Database migrations, backups, least-privilege roles, and production PostgreSQL verification.
- Product-specific password recovery, email verification, OAuth, MFA, and notification workflows.
- A policy for access-token lifetime versus immediate revocation. Access tokens are stateless and remain valid until expiry; disabling a user is enforced when the current-user dependency loads the user.

Construct one `SecurityManager` per application configuration and reuse it across request-scoped `AuthService` instances. It contains validated immutable key/config state and avoids regenerating the dummy Argon2 hash on every request.

## Verification

Install development dependencies and run from `auth_service/`:

```text
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The suite covers configuration rejection, RSA validation, JWT tampering/scope, encryption, normalized registration, duplicates, lockout behavior, disabled accounts, refresh rotation and family replay, logout, current-user resolution, audit failure, FastAPI integration, and ORM/schema agreement.

SQLite is used for fast behavioral tests. PostgreSQL is still required for final integration verification because SQLite does not implement PostgreSQL row-level locking or RLS.
