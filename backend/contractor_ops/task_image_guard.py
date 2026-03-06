import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

NO_IMAGE_ERROR_CODE = 'NO_TASK_IMAGE'
NO_IMAGE_MESSAGE = 'יש לצרף לפחות תמונה אחת לפני שליחה לקבלן'


async def task_has_real_image(db, task_id: str) -> bool:
    doc = await db.task_updates.find_one({
        'task_id': task_id,
        'update_type': 'attachment',
        'content_type': {'$regex': '^image/'},
        'deletedAt': {'$exists': False},
    })
    return doc is not None


async def require_task_image(db, task_id: str):
    has_image = await task_has_real_image(db, task_id)
    if not has_image:
        logger.info(f"[IMAGE_GUARD] blocked contractor send for task_id={task_id} — no real image attached")
        raise HTTPException(
            status_code=400,
            detail={'error_code': NO_IMAGE_ERROR_CODE, 'message': NO_IMAGE_MESSAGE},
        )
