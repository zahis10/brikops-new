"""Batch refactor-safety-split — section moved verbatim from safety_router.py (lines 3197-3263). MOVE, never edit."""
from contractor_ops.safety._shared import (  # noqa: F401
    Depends,
    File,
    HTTPException,
    MAX_SAFETY_UPLOAD_SIZE,
    Request,
    SAFETY_ALLOWED_CONTENT_TYPES,
    SAFETY_ALLOWED_EXTENSIONS,
    SAFETY_WRITERS,
    UploadFile,
    _audit,
    _check_project_access,
    _new_id,
    check_content_length,
    check_storage_quota,
    check_upload_bytes,
    check_upload_rate_limit,
    get_db,
    record_upload,
    require_roles,
    router,
    validate_upload,
)

# =====================================================================
# Photo / PDF upload helper (one endpoint for all resources)
# =====================================================================
@router.post("/{project_id}/upload")
async def upload_safety_file(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    # BATCH upload-hardening-phase3c-safety-imports (2026-05-24) —
    # per-user count limit + Content-Length pre-check (10MB cap =
    # module-level MAX_SAFETY_UPLOAD_SIZE).
    check_upload_rate_limit(user['id'])
    check_content_length(request.headers.get('content-length'), MAX_SAFETY_UPLOAD_SIZE)
    db = get_db()
    await _check_project_access(user, project_id)

    validate_upload(file, SAFETY_ALLOWED_EXTENSIONS, SAFETY_ALLOWED_CONTENT_TYPES)

    content = await file.read()
    if len(content) > MAX_SAFETY_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="הקובץ גדול מדי (מקסימום 10MB)")

    # BATCH upload-hardening-phase3c-safety-imports (2026-05-24) —
    # byte rate limit + per-org storage quota, BEFORE the file
    # reaches S3.
    check_upload_bytes(user['id'], len(content))
    _proj = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    _org_id = (_proj or {}).get('org_id')
    await check_storage_quota(_org_id, len(content))

    content_type = file.content_type or "application/octet-stream"
    if content_type == "application/pdf":
        ext = "pdf"
    else:
        ext = content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"

    file_id = _new_id()
    key = f"safety/{project_id}/{file_id}.{ext}"

    from services.object_storage import save_bytes as obj_save_bytes, generate_url as obj_generate_url
    stored_ref = obj_save_bytes(content, key, content_type)
    # BATCH upload-hardening-phase3c-safety-imports (2026-05-24) — ledger
    await record_upload(_org_id, len(content))
    url = obj_generate_url(stored_ref)

    await _audit("safety_upload", file_id, "upload", user["id"], {
        "project_id": project_id,
        "filename": file.filename,
        "key": key,
        "size": len(content),
        "content_type": content_type,
    })

    return {
        "id": file_id,
        "url": url,
        "stored_ref": stored_ref,
        "filename": file.filename,
        "content_type": content_type,
        "size": len(content),
    }


