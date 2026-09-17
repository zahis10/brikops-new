import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from contractor_ops.router import _audit, _get_project_role, _now, get_current_user, get_db
from contractor_ops.spare_tiles import compute_spare_status, default_spare_settings
from contractor_ops.upload_quota import check_storage_quota, record_upload
from contractor_ops.upload_rate_limit import check_content_length, check_upload_bytes, check_upload_rate_limit
from contractor_ops.upload_safety import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES, validate_upload
from services import object_storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["spare-photos"])

WRITE_ROLES = ("project_manager", "owner", "management_team")
ADMIN_ROLES = ("project_manager", "owner")
MAX_PER_CATEGORY = 3
MAX_PER_UNIT = 20
MAX_PHOTO_SIZE = 10 * 1024 * 1024
ALLOWED_PHOTO_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic", "image/heif",
}
_SNIFF_TYPES = {
    "jpg": "image/jpeg", "png": "image/png",
    "webp": "image/webp", "heic": "image/heic",
}
async def _unit_or_404(db, unit_id):
    unit = await db.units.find_one(
        {"id": unit_id, "archived": {"$ne": True}}, {"_id": 0},
    )
    if not unit or unit.get("archived") is True:
        raise HTTPException(status_code=404, detail="Unit not found")
    return unit


async def _role_or_403(user, project_id):
    role = await _get_project_role(user, project_id)
    if role not in WRITE_ROLES:
        raise HTTPException(status_code=403, detail="אין הרשאה לתעד ריצוף בדירה זו")
    return role


def category_names(unit, spare_settings):
    return [
        row["name"]
        for row in compute_spare_status(unit, spare_settings).get("categories", [])
        if isinstance(row, dict) and row.get("name")
    ]


def serialize_photo(photo):
    stored_ref = photo.get("url")
    display_url = object_storage.resolve_url(stored_ref)
    if isinstance(display_url, str) and display_url.startswith("s3://"):
        display_url = None
    return {
        "id": photo.get("id"),
        "category": photo.get("category"),
        "url": display_url,
        "uploaded_at": photo.get("uploaded_at"),
        "uploaded_by": photo.get("uploaded_by"),
        "uploaded_by_name": photo.get("uploaded_by_name"),
    }


def _ext_for(content_type):
    return {"image/jpeg": "jpg", "image/png": "png",
            "image/webp": "webp", "image/heic": "heic",
            "image/heif": "heic"}[content_type]


def _sniff_image(content: bytes):
    if content[:3] == b"\xff\xd8\xff":
        return "jpg"
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "webp"
    heic_brands = {
        b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis",
        b"hevm", b"hevs", b"mif1", b"msf1",
    }
    if content[4:8] == b"ftyp" and content[8:12] in heic_brands:
        return "heic"
    return None


@router.post("/units/{unit_id}/spare-photos", status_code=201)
async def upload_spare_photo(
    unit_id: str,
    request: Request,
    file: UploadFile = File(...),
    category: str = Form(...),
    user: dict = Depends(get_current_user),
):
    check_upload_rate_limit(user["id"])
    check_content_length(request.headers.get("content-length"), MAX_PHOTO_SIZE)
    db = get_db()
    unit = await _unit_or_404(db, unit_id)
    project_id = unit.get("project_id")
    await _role_or_403(user, project_id)
    project = await db.projects.find_one({"id": project_id}, {"_id": 0}) or {}
    settings = project.get("spare_settings") or default_spare_settings()
    category = (category or "").strip()
    if category not in category_names(unit, settings):
        raise HTTPException(status_code=422, detail="קטגוריה לא קיימת בדירה")

    existing = unit.get("spare_photos") or []
    if sum(isinstance(p, dict) and p.get("category") == category
           for p in existing) >= MAX_PER_CATEGORY:
        raise HTTPException(status_code=422, detail="עד 3 תמונות לקטגוריה")
    if len(existing) >= MAX_PER_UNIT:
        raise HTTPException(status_code=422, detail="עד 20 תמונות לדירה")

    validate_upload(file, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
    declared_type = file.content_type or ""
    if declared_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=400,
            detail="סוג קובץ לא נתמך. נתמכים: JPEG, PNG, WebP, HEIC",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="קובץ ריק")
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="הקובץ גדול מדי (מקסימום 10MB)")
    sniffed = _sniff_image(content)
    if not sniffed:
        raise HTTPException(status_code=400, detail="הקובץ אינו תמונה תקינה")

    check_upload_bytes(user["id"], len(content))
    org_id = project.get("org_id")
    await check_storage_quota(org_id, len(content))
    photo_id = str(uuid.uuid4())
    content_type = _SNIFF_TYPES[sniffed]
    key = f"spare/{project_id}/{unit_id}/{photo_id}.{_ext_for(content_type)}"
    stored_ref = await asyncio.to_thread(
        object_storage.save_bytes, content, key, content_type,
    )
    await record_upload(org_id, len(content))
    photo = {
        "id": photo_id,
        "category": category,
        "url": stored_ref,
        "uploaded_at": _now(),
        "uploaded_by": user["id"],
        "uploaded_by_name": user.get("name") or user.get("email") or user["id"],
    }
    await db.units.update_one({"id": unit_id}, {"$push": {"spare_photos": photo}})
    await _audit("unit", unit_id, "spare_photo_upload", user["id"], {
        "category": category, "photo_id": photo_id, "project_id": project_id,
    })

    return serialize_photo(photo)


@router.delete("/units/{unit_id}/spare-photos/{photo_id}", status_code=204)
async def delete_spare_photo(
    unit_id: str, photo_id: str, user: dict = Depends(get_current_user),
):
    db = get_db()
    unit = await _unit_or_404(db, unit_id)
    role = await _role_or_403(user, unit.get("project_id"))
    photo = next(
        (p for p in unit.get("spare_photos") or []
         if isinstance(p, dict) and p.get("id") == photo_id),
        None,
    )
    if not photo:
        raise HTTPException(status_code=404, detail="תמונה לא נמצאה")
    if photo.get("uploaded_by") != user["id"] and role not in ADMIN_ROLES:
        raise HTTPException(
            status_code=403,
            detail="רק מי שהעלה את התמונה או מנהל הפרויקט יכולים למחוק",
        )
    await db.units.update_one(
        {"id": unit_id}, {"$pull": {"spare_photos": {"id": photo_id}}},
    )
    try:
        deleted = await asyncio.to_thread(object_storage.delete, photo.get("url"))
        if not deleted:
            logger.warning("Spare photo storage delete returned false: %s", photo_id)
    except Exception as exc:
        logger.warning("Spare photo storage delete failed %s: %s", photo_id, exc)
    await _audit("unit", unit_id, "spare_photo_delete", user["id"], {
        "category": photo.get("category"), "photo_id": photo_id,
        "project_id": unit.get("project_id"),
    })
