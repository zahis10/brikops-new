"""
Safety Project Registration router — Batch S2A v3 + Addendum #1.

Israeli Ministry of Economy "פנקס הקבלנים" project registration record.
1:1 with project, lazy-init on first GET, manual entry only.

Extracted from safety_router.py (which was approaching 2,000 lines)
per Zahi's decision 2026-05-04. Pure relocation — zero logic edits.

Registered in server.py alongside the main safety_router. Uses the
identical prefix `/api/safety` so URL paths are bit-identical and the
frontend doesn't change.
"""
from fastapi import APIRouter, Depends, Response

from contractor_ops.router import (
    get_current_user, get_db, _now, _audit,
    _check_project_access, require_roles,
)
from contractor_ops.safety_router import (
    SAFETY_WRITERS, _hash_id_number, _new_id,
)
from contractor_ops.schemas import (
    SafetyProjectRegistration,
    SafetyProjectRegistrationUpsert,
)

router = APIRouter(prefix="/api/safety", tags=["safety"])


async def _get_or_init_registration(db, project_id: str) -> dict:
    """Lazy init: if no registration doc exists for this project,
    create an empty one. Idempotent."""
    existing = await db.safety_project_settings.find_one(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    )
    if existing:
        return existing
    now = _now()
    doc = {
        "id": _new_id(),
        "project_id": project_id,
        "developer_name": None,
        "main_contractor_name": None,
        "contractor_registry_number": None,
        "office_address": None,
        "managers": [],
        "personnel": [],
        "permit_number": None,
        "form_4_target_date": None,
        "created_at": now,
        "updated_at": now,
        "updated_by": None,
        "deletedAt": None,
    }
    await db.safety_project_settings.insert_one(doc)
    return await db.safety_project_settings.find_one(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    )


@router.get("/{project_id}/registration")
async def get_registration(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await _get_or_init_registration(db, project_id)
    return doc


@router.put("/{project_id}/registration", response_model=SafetyProjectRegistration)
async def upsert_registration(
    project_id: str,
    payload: SafetyProjectRegistrationUpsert,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    db = get_db()
    await _check_project_access(user, project_id)

    existing = await _get_or_init_registration(db, project_id)
    updates = payload.dict(exclude_unset=True)

    # PII pattern matches workers (safety_router.py:67 _hash_id_number).
    # No _mask_id helper exists — inline mask: keep first 1 + last 3.
    if "managers" in updates and updates["managers"] is not None:
        for mgr in updates["managers"]:
            raw_id = mgr.get("id_number")
            if raw_id:
                mgr["id_number_hash"] = _hash_id_number(raw_id)
                stripped = raw_id.strip()
                if len(stripped) >= 4:
                    mgr["id_number"] = f"{stripped[:1]}***{stripped[-3:]}"
                else:
                    mgr["id_number"] = "***"

    if "personnel" in updates and updates["personnel"] is not None:
        for person in updates["personnel"]:
            raw_id = person.get("id_number")
            if raw_id:
                person["id_number_hash"] = _hash_id_number(raw_id)
                stripped = raw_id.strip()
                if len(stripped) >= 4:
                    person["id_number"] = f"{stripped[:1]}***{stripped[-3:]}"
                else:
                    person["id_number"] = "***"

    updates["updated_at"] = _now()
    updates["updated_by"] = user["id"]

    await db.safety_project_settings.update_one(
        {"project_id": project_id, "deletedAt": None},
        {"$set": updates},
    )
    await _audit(
        "safety_project_settings", project_id,
        "upsert", user["id"],
        {"before": existing, "after": updates},
    )
    after = await db.safety_project_settings.find_one(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    )
    return after


@router.get("/{project_id}/registration/export/pdf")
async def export_registration_pdf(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Export the registration record as a formal Israeli-format PDF
    (פנקס הקבלנים). Layout matches Ministry of Economy template."""
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await _get_or_init_registration(db, project_id)
    project = await db.projects.find_one({"id": project_id}, {"_id": 0})
    from services.safety_pdf import generate_registration_pdf
    pdf_bytes = generate_registration_pdf(doc, project)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="registration_{project_id}.pdf"'
        },
    )


@router.get("/{project_id}/registration/required-fields")
async def get_required_fields(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """Returns which fields are missing for a complete registration.
    Used by frontend to show a 'completion %' indicator."""
    db = get_db()
    await _check_project_access(user, project_id)
    doc = await _get_or_init_registration(db, project_id)
    required = [
        "developer_name", "main_contractor_name",
        "contractor_registry_number", "permit_number",
    ]
    required_address = ["city", "street", "house_number"]
    missing = [f for f in required if not doc.get(f)]
    addr = doc.get("office_address") or {}
    for f in required_address:
        if not addr.get(f):
            missing.append(f"office_address.{f}")
    if not doc.get("managers"):
        missing.append("managers")
    total_required = len(required) + len(required_address) + 1
    filled = total_required - len(missing)
    return {
        "missing_fields": missing,
        "completion_pct": int((filled / total_required) * 100),
        "is_complete": len(missing) == 0,
    }
