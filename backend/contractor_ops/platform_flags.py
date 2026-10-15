"""Platform-wide runtime switches in app_config; missing values default to OFF."""
from datetime import datetime, timezone

DEFECT_AI_MODE_KEY = 'defect_ai_mode_enabled'


def coerce_flag(doc, default: bool = False) -> bool:
    """Accept only boolean values; missing or malformed values use default."""
    if not isinstance(doc, dict):
        return default
    value = doc.get('value')
    return value if isinstance(value, bool) else default


async def get_defect_ai_mode(db) -> bool:
    doc = await db.app_config.find_one({'key': DEFECT_AI_MODE_KEY}, {'_id': 0})
    return coerce_flag(doc, False)


async def set_defect_ai_mode(db, enabled: bool, actor_id: str) -> dict:
    """Upsert and return the stored value and update metadata."""
    now = datetime.now(timezone.utc).isoformat()
    stored = {'value': bool(enabled), 'updated_at': now, 'updated_by': actor_id}
    await db.app_config.update_one(
        {'key': DEFECT_AI_MODE_KEY}, {'$set': stored}, upsert=True,
    )
    return stored
