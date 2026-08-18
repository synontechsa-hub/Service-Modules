# audit_trail

Copy-in audit logging module. Provides an immutable record of sensitive user actions (e.g., logins, deletions, payment events).

**Convention:** importable Python package, not a standalone service.
Copy the `audit/` folder into your project and wire it into your services.

## What it does

- **Immutable event log**: Stores all actions in a local `audit_logs` table.
- **Structured metadata**: Supports rich, unstructured context via JSONB.
- **Contextual tracking**: Optionally records IP addresses and User-Agents.
- **Observability Mirroring**: Can automatically mirror all audit events to the centralized `observability_service` for a cross-product security view.

## Setup

1. Copy the `audit/` folder into your project.
2. Run `schema.sql` in your Supabase project.
3. Define your SQLAlchemy models by inheriting from `AuditBase`.
4. `pip install -r requirements.snippet.txt`.

## Wiring it in

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from audit import AuditTrailService

app = FastAPI()

# 1. Service Dependency
async def get_audit_service(db: AsyncSession = Depends(get_db)):
    return AuditTrailService(db=db)

# 2. Usage in another service
# (e.g., inside AuthService)
async def login(self, ...):
    ...
    if self.audit_service:
        await self.audit_service.log_action(
            action="user.login",
            target_type="user",
            target_id=str(user.id),
            user_id=user.id
        )
```

## Mirroring to Observability Service

To enable cross-product visibility, pass an `observability_handler` (from the `observability_service` client) to the `AuditTrailService` constructor:

```python
from observability_client import RemoteLogHandler

handler = RemoteLogHandler(...)
audit = AuditTrailService(db=db, observability_handler=handler)
```

## Files

| File | Purpose |
|---|---|
| `models.py` | SQLAlchemy model (`AuditLog`) |
| `schemas.py` | Pydantic schemas |
| `service.py` | `AuditTrailService` — the core logic |
| `schema.sql` | Postgres table and indexes |
