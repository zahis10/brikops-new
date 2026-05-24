# BATCH upload-abuse-hardening (2026-05-22)
# Per-organisation total-storage quota. A ledger counter
# (org_storage_usage collection) is incremented on every successful
# upload and checked before each upload, so a single account cannot
# drive unbounded S3 storage cost. Increment-only in v1 — see the
# spec's DESIGN note. Quota checks fail OPEN (a DB error must not
# block a legitimate upload); recording is best-effort.
import os
import logging
from datetime import datetime, timezone
from fastapi import HTTPException

from contractor_ops.router import get_db

logger = logging.getLogger(__name__)

ORG_STORAGE_LIMIT_GB = int(os.environ.get('ORG_STORAGE_LIMIT_GB', '100'))
ORG_STORAGE_LIMIT_BYTES = ORG_STORAGE_LIMIT_GB * 1024 * 1024 * 1024


async def check_storage_quota(org_id, incoming_bytes: int):
    """Reject (413) when org_id's stored bytes + incoming would
    exceed ORG_STORAGE_LIMIT_BYTES. No-op when org_id is falsy
    (legacy org-less projects). Fails OPEN on any DB error."""
    if not org_id:
        return
    try:
        db = get_db()
        doc = await db.org_storage_usage.find_one({'org_id': org_id})
        used = (doc or {}).get('bytes_used', 0)
    except Exception as e:
        logger.warning(f"[STORAGE_QUOTA] check failed open org={org_id}: {e}")
        return
    if used + incoming_bytes > ORG_STORAGE_LIMIT_BYTES:
        logger.warning(
            f"[STORAGE_QUOTA] blocked org={org_id} used={used} "
            f"incoming={incoming_bytes} limit={ORG_STORAGE_LIMIT_BYTES}"
        )
        raise HTTPException(
            status_code=413,
            detail="מכסת האחסון של הארגון מלאה. פנה לתמיכה כדי להגדיל אותה.",
        )


async def record_upload(org_id, file_size: int):
    """Add file_size to org_id's storage ledger. Best-effort — the
    file is already stored, so a ledger failure must not error the
    request; it is only logged."""
    if not org_id or not file_size:
        return
    try:
        db = get_db()
        await db.org_storage_usage.update_one(
            {'org_id': org_id},
            {
                '$inc': {'bytes_used': int(file_size)},
                '$set': {'updated_at': datetime.now(timezone.utc).isoformat()},
            },
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"[STORAGE_QUOTA] record failed org={org_id}: {e}")
