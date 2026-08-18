# auth

Copy-in authentication and user management module. Provides full registration, login, JWT issuance, and refresh token rotation.

**Convention:** importable Python package, not a standalone service.
Copy the `auth/` folder into your project and wire it into your FastAPI app.

## What it does

- **User registration and login** (Argon2id hashing)
- **JWT access tokens** (RS256 asymmetric signing)
- **Refresh token rotation** (opaque tokens, hashed in DB, single-use with replay detection)
- **Account lockout** (brute-force protection)
- **OAuth support** (Google, Facebook, Discord, Apple) — via `OAuthAccount` links
- **Modular configuration** (Pydantic-settings with `AUTH_` prefix)

## Setup

1. Copy the `auth/` folder into your project.
2. Define your SQLAlchemy models by inheriting from `AuthBase` or mapping the provided models.
3. Configure your RSA keys (private and public) for JWT signing.
4. Copy `.env.example` values into your `.env` (prefixed with `AUTH_`).
5. `pip install -r requirements.txt`.

## Wiring it in

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from auth import AuthConfig, AuthService, get_auth_router

app = FastAPI()

# 1. Config
auth_config = AuthConfig(secret_key="your-secret-key")

# 2. Service Dependency
async def get_auth_service(db: AsyncSession = Depends(get_db)):
    return AuthService(config=auth_config, db=db)

# 3. Router
auth_router = get_auth_router(auth_service_dep=get_auth_service)
app.include_router(auth_router)
```

## Security recommendations

- **RS256 keys**: Use a minimum of 2048-bit RSA keys.
- **Secret Key**: Use a strong, random string for `AUTH_SECRET_KEY` (used for symmetric encryption of sensitive data like OAuth states).
- **Production**: Always run behind HTTPS. The module itself is protocol-agnostic but expects to be served securely.

## Files

| File | Purpose |
|---|---|
| `config.py` | Env-driven settings (`AUTH_` prefix) |
| `models.py` | SQLAlchemy models (`User`, `RefreshToken`, `OAuthAccount`) |
| `schemas.py` | Pydantic request/response models |
| `security.py` | Cryptographic primitives (JWT, hashing, encryption) |
| `service.py` | `AuthService` — the core business logic |
| `router.py` | FastAPI router factory |
