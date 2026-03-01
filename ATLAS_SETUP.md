# MongoDB Atlas Setup — BrikOps Production

## Cluster Details

| Field | Value |
|-------|-------|
| **Provider** | MongoDB Atlas |
| **Cluster** | brikops-prod |
| **Region** | (user-configured) |
| **DB Name** | `brikops_prod` |
| **DB User** | `zahis10_db_user` (readWrite@brikops_prod) |
| **Connection** | `mongodb+srv://...@brikops-prod.vmjxkr.mongodb.net/brikops_prod` |

## Network Access

- **Current**: `0.0.0.0/0` (temporary, for initial setup)
- **TODO**: Restrict to Replit deployment IP only after confirming stable connection

## Environment Configuration

| Environment | MONGO_URL | DB_NAME |
|-------------|-----------|---------|
| **Development** | `mongodb://localhost:27017` (env var override) | `contractor_ops` (local demo data) |
| **Production** | Atlas `mongodb+srv://` (Replit secret) | `brikops_prod` (env var) |

## Code Changes

1. **run.sh**: Detects Atlas (`mongodb+srv://`) in MONGO_URL and skips local mongod startup
2. **config.py**: `DB_NAME` read from env via `_require('DB_NAME')` — no hardcoded default
3. **Hardcoded fallbacks updated**: `backup_restore.py`, `normalize_phones.py` default changed from `contractor_ops` → `brikops_prod`
4. **Guards preserved**:
   - Production refuses `localhost` MongoDB (fail-fast `sys.exit(1)`)
   - Seed requires `RUN_SEED=true` + `APP_MODE=dev`

## Verification

### Dev (before deploy)
```json
{
  "db_name": "contractor_ops",
  "db_host": "localhost",
  "app_mode": "dev",
  "counts": { "users": 15, "projects": 2, "tasks": 35 }
}
```

### Production (after deploy)
Expected via `GET /api/admin/system-info`:
- `db_host`: Atlas hostname (masked: `****@brikops-prod.vmjxkr.mongodb.net`)
- `db_name`: `brikops_prod`
- `app_mode`: `prod`

## Post-Deploy Checklist

- [ ] Verify `/api/admin/system-info` shows Atlas host
- [ ] Verify `db_name` = `brikops_prod`
- [ ] Create test user + project + task
- [ ] Redeploy and verify data persists
- [ ] Harden Network Access (remove `0.0.0.0/0`)
