# feature_flags

Copy-in feature flags module that allows for dynamic feature toggling, progressive rollouts (canary), and user-specific targeting without code redeploys.

**Convention:** importable Python package, not a standalone service.
Copy the `feature_flags/` folder into your project and wire it into your services.

## What it does

- **Dynamic Toggling**: Flip features on/off instantly via the database.
- **Progressive Rollout**: Deterministically enable features for a percentage of your users (0-100%).
- **Targeting Rules**: Support for environment-specific toggles and user ID whitelists.
- **High Performance**: Designed for minimal overhead with simple SQL lookups.

## Setup

1. Copy the `feature_flags/` folder into your project.
2. Run `schema.sql` in your Supabase project.
3. Define your SQLAlchemy models by inheriting from `FlagBase`.
4. `pip install -r requirements.snippet.txt`.

## Wiring it in

```python
from fastapi import FastAPI, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from feature_flags import FeatureFlagService, FeatureFlagsConfig

app = FastAPI()
config = FeatureFlagsConfig()

# 1. Service Dependency
async def get_flag_service(db: AsyncSession = Depends(get_db)):
    return FeatureFlagService(db=db, config=config)

# 2. Usage
async def some_endpoint(user_id: str, flags: FeatureFlagService = Depends(get_flag_service)):
    if await flags.is_enabled("new-ui-v2", user_id=user_id):
        # show new UI
        ...
    else:
        # show old UI
        ...
```

## Targeting Rules Example

Rules are stored as JSONB. Example `rules` payload:
```json
{
  "user_ids": ["user-123", "user-456"],
  "environments": ["staging", "development"]
}
```

## Files

| File | Purpose |
|---|---|
| `config.py` | Env-driven settings (`FLAGS_` prefix) |
| `models.py` | SQLAlchemy model (`FeatureFlag`) |
| `service.py` | `FeatureFlagService` — the core logic |
| `schema.sql` | Postgres table and seed data |
