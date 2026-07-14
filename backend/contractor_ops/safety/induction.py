"""
Batch safety-ind1 — site-induction org templates + snapshot infra (IND-1).

Org-scoped induction content template: ONE versioned doc per org
(unique index on org_id), languages MAP from day 1 (v1 = Hebrew only;
IND-3 adds en/ru/ar additively — zero schema change).

Gates (Zahi D1/D2, 2026-07-12):
  - PUT: org owner (organizations.owner_user_id == user.id) OR
    organization_memberships role == 'org_admin'. billing_admin EXCLUDED
    (finance role, not a safety-content editor).
  - GET/starter: global role in {project_manager, management_team} OR the
    same org owner / org_admin resolution.
org_id is ALWAYS resolved from the AUTHENTICATED user (get_user_org —
organization_memberships); never from path/body.

IND-2 (batch safety-ind2) adds the conduct flow: project-scoped content
GET + one-ceremony conduct POST (born-signed training, extended
evidentiary signature, dedup snapshot writer on uidx_ics). Conduct-side
org resolution goes via the PROJECT (sign_training idiom), NOT
get_user_org. NO delete endpoints; en/ru/ar content = IND-3.
"""
import hashlib
import json
import uuid
from datetime import date, timedelta

from contractor_ops.safety._shared import (  # noqa: F401
    ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES,
    BaseModel, Depends, Field, File, Form, HTTPException, List,
    SAFETY_WRITERS, SafetyTraining, UploadFile,
    _check_project_access, _new_id,
    check_storage_quota, check_upload_bytes, check_upload_rate_limit,
    generate_url, get_current_user, get_db, logger, record_upload,
    require_roles, router, validate_upload, _audit, _now,
)


# =====================================================================
# Constants
# =====================================================================
INDUCTION_READ_GLOBAL_ROLES = ("project_manager", "management_team")
MAX_SECTIONS = 200
MAX_TITLE_LEN = 200
MAX_BODY_LEN = 5000

# --- IND-2 (batch safety-ind2, 2026-07-14) ---
INDUCTION_TRAINING_TYPE = "הדרכת אתר"
DEFAULT_INDUCTION_VALIDITY_DAYS = 365  # DRAFT — pending regulatory verification (Zahi)
INDUCTION_LEGAL_TEXT_HE = "עברתי הדרכה פרונטלית בשפה המובנת לי"
INDUCTION_LEGAL_TEXT_INTERPRETER_HE = (
    "ההדרכה הועברה לי בעל-פה בשפה המובנת לי ({worker_language}) "
    "באמצעות מתורגמן/ת: {interpreter_name}"
)
# NO en/ru/ar legal constants this batch (IND-3 — no unreviewed translations).

# DRAFT content — requires Zahi approval before prod
STARTER_INDUCTION_SECTIONS_HE = [
    {
        "title": "כללי ונהלי אתר",
        "body": "ברוכים הבאים לאתר. הכניסה לאתר מותרת רק לאחר קליטה בטיחותית וחתימה על תדריך זה. יש להישמע להוראות מנהל העבודה וממונה הבטיחות בכל עת, להיכנס ולצאת רק בשערים המוסדרים, ולהחנות רק במקומות שהוקצו לכך. אין להכניס אורחים ללא אישור מראש.",
    },
    {
        "title": "ציוד מגן אישי",
        "body": "חובה לחבוש קסדת מגן ולנעול נעלי בטיחות בכל שטח האתר. יש ללבוש אפוד זוהר, ולהשתמש בציוד מגן ייעודי לפי המשימה: משקפי מגן, אטמי אוזניים, כפפות ורתמת בטיחות בעבודה בגובה. עובד ללא ציוד מגן תקין יורחק מהאתר.",
    },
    {
        "title": "עבודה בגובה",
        "body": "עבודה בגובה מעל 2 מטר מותרת רק לעובד בעל הדרכת עבודה בגובה בתוקף. חובה להשתמש ברתמת בטיחות מעוגנת לנקודת עיגון תקנית, לוודא משטחי עבודה תקינים ומעקות במקומם, ואין לעבוד בקרבת פתחים לא מגודרים.",
    },
    {
        "title": "פיגומים וסולמות",
        "body": "אין לעלות על פיגום שלא נבדק ואושר על ידי בונה מקצועי. יש לוודא שילוט תקינות בתוקף על הפיגום, ואין לשנות, לפרק או להזיז רכיבי פיגום ללא אישור. סולמות — רק תקניים, מוצבים על משטח יציב ובזווית נכונה.",
    },
    {
        "title": "חשמל",
        "body": "עבודות חשמל יבוצעו רק על ידי חשמלאי מוסמך. אין לגעת בלוחות חשמל, כבלים חשופים או ציוד חשמלי פגום — יש לדווח מיד. כלי עבודה חשמליים יחוברו רק דרך לוח זמני תקני עם ממסר פחת.",
    },
    {
        "title": "כלים וציוד מכני",
        "body": "יש להשתמש רק בכלים תקינים עם מגני בטיחות במקומם. הפעלת ציוד מכני הנדסי מותרת רק לבעלי היתר מתאים בתוקף. אין לעמוד בטווח פעולה של ציוד מכני עובד, ויש לשמור קשר עין עם המפעיל.",
    },
    {
        "title": "הרמה ומנופים",
        "body": "אסור לשהות מתחת למטען מורם. הרמת מטענים תבוצע רק על ידי מפעיל מנוף מוסמך ובליווי אתת מוסמך. יש לוודא שהמטען קשור ומאוזן כנדרש, ולהתרחק מאזור ההנפה המסומן.",
    },
    {
        "title": "חפירות",
        "body": "אין להיכנס לחפירה בעומק העולה על 1.2 מטר ללא דיפון תקני או שיפוע מתאים. יש לוודא דרכי מילוט תקינות, לגדר ולסמן כל חפירה פתוחה, ולא לאחסן חומרים או ציוד בסמוך לשפת החפירה.",
    },
    {
        "title": "אש וחומרים מסוכנים",
        "body": "עבודות בחום (ריתוך, חיתוך, השחזה) מחייבות היתר עבודה בחום וצופה אש עם אמצעי כיבוי זמינים. חומרים דליקים ומסוכנים יאוחסנו במקום ייעודי ומסומן בלבד. העישון מותר רק באזורים מוסדרים.",
    },
    {
        "title": "סדר וניקיון",
        "body": "יש לשמור על סביבת עבודה נקייה ומסודרת: לפנות פסולת למכולות, לא לחסום דרכי גישה ומילוט, לאחסן חומרים בערימות יציבות, ולסלק מסמרים בולטים ושאריות חומרים מדרכי מעבר.",
    },
    {
        "title": "מצבי חירום ופינוי",
        "body": "בעת אירוע חירום יש להפסיק את העבודה מיד, להתרחק מאזור הסכנה ולהתפנות לנקודת הריכוז שהוגדרה בתדריך. יש להכיר את מיקום ערכת העזרה הראשונה, המטפים ודרכי המילוט. מספרי חירום מפורסמים בלוח האתר.",
    },
    {
        "title": "דיווח על מפגעים ותאונות",
        "body": "כל עובד חייב לדווח מיד למנהל העבודה על כל מפגע, כמעט-תאונה או תאונה — גם ללא נפגעים. אין להזיז ציוד שהיה מעורב בתאונה עד לקבלת אישור. דיווח מוקדם מציל חיים.",
    },
]


# =====================================================================
# Pure helper — IND-2's evidentiary contract (unit-probed, no I/O)
# =====================================================================
def induction_content_hash(sections: list, legal_text: str) -> str:
    """sha256 hex over canonical JSON — determinism is the contract."""
    canonical = json.dumps(
        {"sections": sections, "legal_text": legal_text},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =====================================================================
# Org resolution + gates (D1/D2)
# =====================================================================
async def _resolve_user_org_edit(user: dict):
    """Returns (org_doc_or_None, can_edit: bool) for the authenticated user.

    can_edit iff org owner (organizations.owner_user_id) or org_admin in
    organization_memberships (canonical collection — get_user_org idiom).
    billing_admin excluded per D1.
    """
    from contractor_ops.billing import get_user_org
    from contractor_ops.router import _is_super_admin
    org = await get_user_org(user["id"])
    if not org:
        return None, False
    if _is_super_admin(user):
        return org, True
    if org.get("owner_user_id") == user["id"]:
        return org, True
    db = get_db()
    mem = await db.organization_memberships.find_one(
        {"org_id": org["id"], "user_id": user["id"]}, {"_id": 0, "role": 1}
    )
    return org, bool(mem and mem.get("role") == "org_admin")


async def _require_induction_read(user: dict):
    """D2: global {project_manager, management_team} OR org owner/org_admin."""
    org, can_edit = await _resolve_user_org_edit(user)
    if user.get("role") in INDUCTION_READ_GLOBAL_ROLES or can_edit:
        return org, can_edit
    raise HTTPException(status_code=403, detail="אין הרשאה לצפייה בתוכן הדרכת האתר")


# =====================================================================
# Schemas
# =====================================================================
class InductionSection(BaseModel):
    title: str
    body: str


class InductionTemplateSave(BaseModel):
    sections: List[InductionSection] = Field(...)


def _validate_sections(payload: InductionTemplateSave) -> list:
    sections = payload.sections
    if not sections:
        raise HTTPException(status_code=422, detail="יש להוסיף לפחות סעיף אחד")
    if len(sections) > MAX_SECTIONS:
        raise HTTPException(status_code=422, detail=f"מספר הסעיפים המרבי הוא {MAX_SECTIONS}")
    clean = []
    for i, s in enumerate(sections, start=1):
        title = (s.title or "").strip()
        body = (s.body or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail=f"סעיף {i}: כותרת הסעיף לא יכולה להיות ריקה")
        if len(title) > MAX_TITLE_LEN:
            raise HTTPException(status_code=422, detail=f"סעיף {i}: כותרת הסעיף ארוכה מדי (עד {MAX_TITLE_LEN} תווים)")
        if not body:
            raise HTTPException(status_code=422, detail=f"סעיף {i}: תוכן הסעיף לא יכול להיות ריק")
        if len(body) > MAX_BODY_LEN:
            raise HTTPException(status_code=422, detail=f"סעיף {i}: תוכן הסעיף ארוך מדי (עד {MAX_BODY_LEN} תווים)")
        clean.append({"title": title, "body": body})
    return clean


# =====================================================================
# Endpoints
# =====================================================================
@router.get("/induction-template")  # unused by FE since ind2-fix1 (kept for probes + future org console)
async def get_induction_template(user: dict = Depends(get_current_user)):
    org, can_edit = await _require_induction_read(user)
    if not org:
        return {"template": None, "can_edit": False}
    db = get_db()
    doc = await db.induction_templates.find_one({"org_id": org["id"]}, {"_id": 0})
    if not doc:
        return {"template": None, "can_edit": can_edit}
    return {"template": doc, "can_edit": can_edit}


@router.get("/induction-template/starter")
async def get_induction_starter(user: dict = Depends(get_current_user)):
    await _require_induction_read(user)
    # Returning the starter saves NOTHING — the editor fills local state only.
    return {"sections": STARTER_INDUCTION_SECTIONS_HE, "draft": True}


@router.put("/induction-template")  # unused by FE since ind2-fix1 (kept for probes + future org console)
async def save_induction_template(
    payload: InductionTemplateSave,
    user: dict = Depends(get_current_user),
):
    org, can_edit = await _resolve_user_org_edit(user)
    if not org:
        raise HTTPException(status_code=403, detail="לא נמצא ארגון למשתמש")
    if not can_edit:
        raise HTTPException(status_code=403, detail="רק בעל הארגון או מנהל ארגון יכולים לערוך את תוכן ההדרכה")
    sections = _validate_sections(payload)
    db = get_db()
    await db.induction_templates.update_one(
        {"org_id": org["id"]},
        {
            "$set": {
                "languages.he": {"sections": sections},
                "updated_at": _now(),
                "updated_by": user["id"],
            },
            "$inc": {"version": 1},
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "org_id": org["id"],
                "created_at": _now(),
            },
        },
        upsert=True,
    )
    doc = await db.induction_templates.find_one({"org_id": org["id"]}, {"_id": 0})
    await _audit("induction_template", doc["id"], "induction_template_saved", user["id"], {
        "org_id": org["id"],
        "version": doc.get("version"),
        "sections_count": len(sections),
    })
    return {"template": doc, "can_edit": True}

# =====================================================================
# IND-2 — conduct flow (batch safety-ind2, 2026-07-14)
# =====================================================================
def _template_languages_filled(doc: dict) -> list:
    """Languages that actually carry sections (empty map entries excluded)."""
    langs = (doc or {}).get("languages") or {}
    return [k for k, v in langs.items() if v and v.get("sections")]


async def _load_template_via_project(project_id: str):
    """IND-2 org resolution: via the PROJECT's org (sign_training quota
    idiom), NOT get_user_org — conductors are PMs who may have no
    organization_memberships row; the project always knows its org.
    Returns (org_id, template_doc_or_None)."""
    db = get_db()
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
    org_id = (proj or {}).get("org_id")
    if not org_id:
        return None, None
    doc = await db.induction_templates.find_one({"org_id": org_id}, {"_id": 0})
    return org_id, doc


@router.get("/{project_id}/induction/content")
async def get_induction_content(
    project_id: str,
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    await _check_project_access(user, project_id)
    _org_id, doc = await _load_template_via_project(project_id)
    filled = _template_languages_filled(doc)
    if not doc or "he" not in filled:
        raise HTTPException(status_code=404, detail="לא הוגדר תוכן הדרכת אתר לארגון")
    return {
        "template_version": doc.get("version"),
        "languages_filled": filled,
        "sections": doc["languages"]["he"]["sections"],
        "legal_text": INDUCTION_LEGAL_TEXT_HE,
        "legal_text_interpreter": INDUCTION_LEGAL_TEXT_INTERPRETER_HE,
        "default_validity_days": DEFAULT_INDUCTION_VALIDITY_DAYS,
    }


async def _upsert_content_snapshot(org_id: str, version: int, language: str,
                                   sections: list, legal_text: str) -> str:
    """Ruling ה-7: dedup-upsert keyed (org_id, template_version, language)
    on uidx_ics_org_version_lang. Insert full copy if absent; reuse the
    existing row's id otherwise. The PERSONALIZED attestation (interpreter
    name) lives on the signature, NOT here — keeps dedup valid."""
    from pymongo.errors import DuplicateKeyError
    db = get_db()
    try:
        await db.induction_content_snapshots.update_one(
            {"org_id": org_id, "template_version": version, "language": language},
            {"$setOnInsert": {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "template_version": version,
                "language": language,
                "sections": sections,
                "legal_text": legal_text,
                "content_hash": induction_content_hash(sections, legal_text),
                "created_at": _now(),
            }},
            upsert=True,
        )
    except DuplicateKeyError:
        # Concurrent first-write race on uidx_ics_org_version_lang: the
        # other request inserted between our filter miss and the upsert.
        # The row now exists — fall through to the read below.
        pass
    row = await db.induction_content_snapshots.find_one(
        {"org_id": org_id, "template_version": version, "language": language},
        {"_id": 0, "id": 1, "content_hash": 1},
    )
    return row["id"], row["content_hash"]


@router.post("/{project_id}/induction/conduct", status_code=201, response_model=SafetyTraining)
async def conduct_induction(
    project_id: str,
    worker_id: str = Form(...),
    language_choice: str = Form(...),
    worker_language: str = Form(None),
    interpreter_name: str = Form(None),
    expires_at: str = Form(None),
    signer_name: str = Form(...),
    signature_type: str = Form(...),
    typed_name: str = Form(None),
    signature_image: UploadFile = File(None),
    user: dict = Depends(require_roles(*SAFETY_WRITERS)),
):
    """One atomic ceremony — the induction training is BORN SIGNED.
    No half-created unsigned record, no claim race."""
    db = get_db()
    await _check_project_access(user, project_id)

    worker = await db.safety_workers.find_one({
        "id": worker_id, "project_id": project_id, "deletedAt": None,
    })
    if not worker:
        raise HTTPException(status_code=404, detail="worker not found or deleted")

    # (a) template via PROJECT org
    org_id, tmpl = await _load_template_via_project(project_id)
    filled = _template_languages_filled(tmpl)
    if not tmpl or "he" not in filled:
        raise HTTPException(status_code=409, detail="לא הוגדר תוכן הדרכת אתר לארגון")

    choice = (language_choice or "").strip()
    if choice != "other" and choice not in filled:
        raise HTTPException(status_code=422, detail="שפה לא זמינה בתוכן ההדרכה")

    interpreter = (interpreter_name or "").strip() or None
    w_lang = (worker_language or "").strip() or None
    if choice == "other":
        # Ruling ה-12: no path where a worker signs content not understood.
        if not interpreter:
            raise HTTPException(status_code=422, detail="נדרש שם מתורגמן כאשר אין תוכן בשפת העובד")
        if not w_lang:
            raise HTTPException(status_code=422, detail="יש להזין את שפת העובד")

    # Displayed content: "other" reads the he content via interpreter.
    displayed_language = "he" if choice == "other" else choice
    sections = tmpl["languages"][displayed_language]["sections"]
    base_legal = INDUCTION_LEGAL_TEXT_HE  # v1: he is the only content language

    # expires_at: ruling ה-5 — editable at capture; default today+DRAFT days.
    if expires_at is not None and str(expires_at).strip():
        exp = str(expires_at).strip()
        try:
            date.fromisoformat(exp[:10])
        except ValueError:
            raise HTTPException(status_code=422, detail="תאריך תפוגה לא תקין")
        expires_val = exp[:10]
    else:
        expires_val = (date.today() + timedelta(days=DEFAULT_INDUCTION_VALIDITY_DAYS)).isoformat()

    name = (signer_name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="יש להזין שם")

    training_id = _new_id()

    # Signature — EXACT mirror of sign_training incl. full upload hardening.
    signature_ref = None
    if signature_type == "canvas":
        if signature_image is None:
            raise HTTPException(status_code=422, detail="חסרה תמונת חתימה")
        check_upload_rate_limit(user["id"])
        validate_upload(signature_image, ALLOWED_IMAGE_EXTENSIONS, ALLOWED_IMAGE_TYPES)
        img_bytes = await signature_image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="קובץ ריק")
        check_upload_bytes(user["id"], len(img_bytes))
        await check_storage_quota(org_id, len(img_bytes))
        from services.object_storage import save_bytes as _save_bytes
        s3_key = f"safety/{project_id}/trainings/{training_id}/sig_worker_{_new_id()}.png"
        signature_ref = _save_bytes(img_bytes, s3_key, "image/png")
        await record_upload(org_id, len(img_bytes))
    elif signature_type == "typed":
        if not (typed_name or "").strip():
            raise HTTPException(status_code=422, detail="יש להזין שם")
    else:
        raise HTTPException(status_code=422, detail="סוג חתימה לא מוכר")

    # (b) SNAPSHOT — dedup-upsert (ruling ה-7)
    snapshot_id, content_hash = await _upsert_content_snapshot(
        org_id, tmpl.get("version"), displayed_language, sections, base_legal)

    # (c) attestation text (ruling ה-11/ה-12)
    if choice == "other":
        attestation_text = INDUCTION_LEGAL_TEXT_INTERPRETER_HE.format(
            worker_language=w_lang, interpreter_name=interpreter)
    else:
        attestation_text = base_legal

    # (d) BORN-SIGNED training insert (ruling ה-6 extended signature)
    now = _now()
    sig = {
        "name": name,
        "signed_at": now,
        "signature_ref": signature_ref,
        "signature_type": signature_type,
        "typed_name": (typed_name.strip() if (signature_type == "typed" and typed_name) else None),
        "captured_by": user["id"],
        "language_read": displayed_language,
        "worker_language": (w_lang if choice == "other" else displayed_language),
        "via_interpreter": bool(choice == "other" or interpreter),
        "interpreter_name": interpreter,
        "content_version": tmpl.get("version"),
        "content_hash": content_hash,
        "snapshot_id": snapshot_id,
        "attestation_text": attestation_text,
    }
    doc = {
        "id": training_id,
        "project_id": project_id,
        "worker_id": worker_id,
        "training_type": INDUCTION_TRAINING_TYPE,
        "instructor_name": None,
        "duration_minutes": None,
        "location": None,
        "trained_at": now,
        "expires_at": expires_val,
        "certificate_url": None,
        "worker_signature": sig,
        "created_at": now,
        "created_by": user["id"],
        "deletedAt": None,
        "deletedBy": None,
    }
    await db.safety_trainings.insert_one(doc)

    # (e) audit — no new PII
    await _audit("safety_training", training_id, "induction_conducted", user["id"], {
        "project_id": project_id,
        "worker_id": worker_id,
        "template_version": tmpl.get("version"),
        "language_read": displayed_language,
        "via_interpreter": sig["via_interpreter"],
    })

    out = {k: v for k, v in doc.items() if k != "_id"}
    s = out.get("worker_signature")
    if s and s.get("signature_ref"):
        try:
            s["signature_display_url"] = generate_url(s["signature_ref"])
        except Exception:
            s["signature_display_url"] = None
    return SafetyTraining(**out)


# =====================================================================
# ind2-fix1 — PROJECT-scoped editor pair (ONE org key for the feature)
# =====================================================================
async def _resolve_project_org_edit(user: dict, project_id: str):
    """(org_id, can_edit) resolved via the PROJECT's org — the SAME key the
    conduct flow uses. can_edit iff user is organizations.owner_user_id of
    the project's org OR org_admin member IN that org (billing_admin
    excluded — same D1 semantics as IND-1)."""
    db = get_db()
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0, "org_id": 1})
    org_id = (proj or {}).get("org_id")
    if not org_id:
        return None, False
    from contractor_ops.router import _is_super_admin
    if _is_super_admin(user):
        return org_id, True
    org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "id": 1, "owner_user_id": 1})
    if not org:
        return org_id, False
    if org.get("owner_user_id") == user["id"]:
        return org_id, True
    mem = await db.organization_memberships.find_one(
        {"org_id": org_id, "user_id": user["id"]}, {"_id": 0, "role": 1}
    )
    return org_id, bool(mem and mem.get("role") == "org_admin")


@router.get("/{project_id}/induction-template")
async def get_project_induction_template(
    project_id: str,
    user: dict = Depends(get_current_user),
):
    """ind2-fix1: read audience = conduct-content readers (SAFETY_WRITERS
    with project access) OR project-org managers (can_edit)."""
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not can_edit:
        if user.get("role") not in SAFETY_WRITERS:
            raise HTTPException(status_code=403, detail="אין הרשאה לצפייה בתוכן הדרכת האתר")
        await _check_project_access(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    db = get_db()
    doc = await db.induction_templates.find_one({"org_id": org_id}, {"_id": 0})
    return {"template": doc, "can_edit": can_edit}


@router.put("/{project_id}/induction-template")
async def save_project_induction_template(
    project_id: str,
    payload: InductionTemplateSave,
    user: dict = Depends(get_current_user),
):
    """ind2-fix1: SAME behavior as the org-level PUT (validation, atomic
    $inc version upsert, audit, response shape) — org keyed via PROJECT."""
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    if not can_edit:
        raise HTTPException(status_code=403, detail="רק בעל הארגון או מנהל ארגון יכולים לערוך את תוכן ההדרכה")
    sections = _validate_sections(payload)
    db = get_db()
    await db.induction_templates.update_one(
        {"org_id": org_id},
        {
            "$set": {
                "languages.he": {"sections": sections},
                "updated_at": _now(),
                "updated_by": user["id"],
            },
            "$inc": {"version": 1},
            "$setOnInsert": {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "created_at": _now(),
            },
        },
        upsert=True,
    )
    doc = await db.induction_templates.find_one({"org_id": org_id}, {"_id": 0})
    await _audit("induction_template", doc["id"], "induction_template_saved", user["id"], {
        "org_id": org_id,
        "version": doc.get("version"),
        "sections_count": len(sections),
    })
    return {"template": doc, "can_edit": True}
