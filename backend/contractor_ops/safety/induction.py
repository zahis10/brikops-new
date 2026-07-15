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

# --- IND-3 (batch safety-ind3, 2026-07-15) ---
# Content languages. LEGAL/attestation texts stay the HEBREW code constants
# (locked concept ruling) — only the SECTIONS are multi-language.
INDUCTION_CONTENT_LANGS = ("he", "en", "ru", "ar", "zh")
TRANSLATE_TARGETS = ("en", "ru", "ar", "zh")
# Google Cloud Translation v2 language codes (store as our short code).
_GOOGLE_LANG_CODE = {"en": "en", "ru": "ru", "ar": "ar", "zh": "zh-CN"}
LANG_NATIVE_NAMES = {
    "he": "עברית", "en": "English", "ru": "Русский", "ar": "العربية", "zh": "中文",
}
# Certificate PDF renders with Rubik (Latin/Cyrillic/Hebrew/Arabic glyphs);
# CJK glyphs are NOT in Rubik — zh uses a Hebrew label there.
_PDF_LANG_NAMES = {
    "he": "עברית", "en": "English", "ru": "Русский", "ar": "العربية",
    "zh": "סינית (Chinese)",
}

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


class InductionTemplateSaveMulti(BaseModel):
    """IND-3 E2 — multi-language save. BACKWARD COMPATIBLE: the legacy
    he-only body {sections: [...]} keeps working (languages omitted)."""
    sections: List[InductionSection] = Field(None)
    languages: dict = Field(None)


def _validate_sections_list(sections, lang_label: str = "") -> list:
    prefix = f"[{lang_label}] " if lang_label else ""
    if not sections:
        raise HTTPException(status_code=422, detail="יש להוסיף לפחות סעיף אחד")
    if len(sections) > MAX_SECTIONS:
        raise HTTPException(status_code=422, detail=f"מספר הסעיפים המרבי הוא {MAX_SECTIONS}")
    clean = []
    for i, s in enumerate(sections, start=1):
        title = (s.title or "").strip()
        body = (s.body or "").strip()
        if not title:
            raise HTTPException(status_code=422, detail=f"{prefix}סעיף {i}: כותרת הסעיף לא יכולה להיות ריקה")
        if len(title) > MAX_TITLE_LEN:
            raise HTTPException(status_code=422, detail=f"{prefix}סעיף {i}: כותרת הסעיף ארוכה מדי (עד {MAX_TITLE_LEN} תווים)")
        if not body:
            raise HTTPException(status_code=422, detail=f"{prefix}סעיף {i}: תוכן הסעיף לא יכול להיות ריק")
        if len(body) > MAX_BODY_LEN:
            raise HTTPException(status_code=422, detail=f"{prefix}סעיף {i}: תוכן הסעיף ארוך מדי (עד {MAX_BODY_LEN} תווים)")
        clean.append({"title": title, "body": body})
    return clean


def _validate_sections(payload: InductionTemplateSave) -> list:
    return _validate_sections_list(payload.sections)


def _validate_languages_map(raw: dict) -> dict:
    """IND-3 E2: {code: {sections: [...]}} → clean {code: {sections: clean}}.
    Codes must be ⊆ INDUCTION_CONTENT_LANGS; empty sections REMOVE the
    language (excluded from the returned map); he REQUIRED non-empty."""
    if not isinstance(raw, dict):
        raise HTTPException(status_code=422, detail="מבנה שפות לא תקין")
    bad = [c for c in raw.keys() if c not in INDUCTION_CONTENT_LANGS]
    if bad:
        raise HTTPException(status_code=422, detail=f"קוד שפה לא נתמך: {', '.join(sorted(bad))}")
    out = {}
    for code in INDUCTION_CONTENT_LANGS:
        if code not in raw:
            continue
        entry = raw.get(code) or {}
        if not isinstance(entry, dict):
            raise HTTPException(status_code=422, detail="מבנה שפות לא תקין")
        secs_raw = entry.get("sections") or []
        if not secs_raw:
            continue  # empty sections → language removed (un-filled)
        # Architect fix: sections MUST be a list of {title, body} dicts —
        # any other shape (string, object, list of scalars) → 422, not 500.
        if not isinstance(secs_raw, list) or not all(isinstance(s, dict) for s in secs_raw):
            raise HTTPException(status_code=422, detail="מבנה סעיפים לא תקין")
        try:
            secs = [InductionSection(**s) for s in secs_raw]
        except Exception:
            raise HTTPException(status_code=422, detail="מבנה סעיפים לא תקין")
        label = LANG_NATIVE_NAMES.get(code, code)
        out[code] = {"sections": _validate_sections_list(secs, lang_label=label)}
    if "he" not in out:
        raise HTTPException(status_code=422, detail="תוכן בעברית הוא חובה")
    return out


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
        # IND-3: the ceremony's READ step shows the CHOSEN language —
        # additive map so the FE displays exactly what will be snapshotted.
        "sections_by_language": {
            code: doc["languages"][code]["sections"] for code in filled
        },
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
# ind2-fix4 E3 — read-only evidence view of a signed induction training
# =====================================================================
@router.get("/{project_id}/induction/evidence/{training_id}")
async def get_induction_evidence(
    project_id: str,
    training_id: str,
    user: dict = Depends(get_current_user),
):
    """Read-only: exactly what the worker read (snapshot sections), the
    attestation text and the signature. Same gate as reading trainings."""
    db = get_db()
    await _check_project_access(user, project_id)

    tr = await db.safety_trainings.find_one(
        {"id": training_id, "project_id": project_id, "deletedAt": None}, {"_id": 0})
    if not tr or str(tr.get("training_type") or "").strip() != INDUCTION_TRAINING_TYPE:
        raise HTTPException(status_code=404, detail="הדרכת אתר לא נמצאה")
    sig = tr.get("worker_signature")
    if not sig:
        raise HTTPException(status_code=404, detail="הדרכת האתר אינה חתומה — אין ראיות להצגה")

    sections = None
    snapshot_id = sig.get("snapshot_id")
    if snapshot_id:
        snap = await db.induction_content_snapshots.find_one(
            {"id": snapshot_id}, {"_id": 0, "sections": 1})
        sections = (snap or {}).get("sections")
    if sections is None:
        raise HTTPException(status_code=404, detail="תוכן ההדרכה החתומה לא נמצא")

    signature_display_url = None
    if sig.get("signature_ref"):
        try:
            signature_display_url = generate_url(sig["signature_ref"])
        except Exception:
            signature_display_url = None

    return {
        "training_id": training_id,
        "worker_id": tr.get("worker_id"),
        "sections": sections,
        "attestation_text": sig.get("attestation_text"),
        "language_read": sig.get("language_read"),
        "worker_language": sig.get("worker_language"),
        "via_interpreter": sig.get("via_interpreter"),
        "interpreter_name": sig.get("interpreter_name"),
        "content_version": sig.get("content_version"),
        "content_hash": sig.get("content_hash"),
        "signer_name": sig.get("name"),
        "signed_at": sig.get("signed_at"),
        "signature_type": sig.get("signature_type"),
        "typed_name": sig.get("typed_name"),
        "signature_display_url": signature_display_url,
        "trained_at": tr.get("trained_at"),
        "expires_at": tr.get("expires_at"),
    }


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
    if mem and mem.get("role") == "org_admin":
        return org_id, True
    # ind2-fix3 D1: project managers OF THIS PROJECT can edit (one indexed
    # project_memberships lookup). billing_admin exclusion applies to the
    # ORG path only — a real project_manager membership grants edit.
    pmem = await db.project_memberships.find_one(
        {"project_id": project_id, "user_id": user["id"]}, {"_id": 0, "role": 1}
    )
    return org_id, bool(pmem and pmem.get("role") == "project_manager")


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
    payload: InductionTemplateSaveMulti,
    user: dict = Depends(get_current_user),
):
    """ind2-fix1: SAME behavior as the org-level PUT (validation, atomic
    $inc version upsert, audit, response shape) — org keyed via PROJECT.

    IND-3 E2: also accepts {languages: {code: {sections}}} (codes ⊆
    he/en/ru/ar/zh; he required non-empty; empty sections REMOVE the
    language). Legacy he-only {sections} body keeps working — it $sets
    languages.he only and preserves other languages. ONE version $inc per
    save either way. Audit event unchanged."""
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    if not can_edit:
        raise HTTPException(status_code=403, detail="רק בעל הארגון או מנהל ארגון יכולים לערוך את תוכן ההדרכה")
    if payload.languages is not None:
        lang_map = _validate_languages_map(payload.languages)
        set_fields = {"languages": lang_map}
        he_count = len(lang_map["he"]["sections"])
    else:
        if payload.sections is None:
            raise HTTPException(status_code=422, detail="יש להוסיף לפחות סעיף אחד")
        sections = _validate_sections_list(payload.sections)
        set_fields = {"languages.he": {"sections": sections}}
        he_count = len(sections)
    db = get_db()
    await db.induction_templates.update_one(
        {"org_id": org_id},
        {
            "$set": {
                **set_fields,
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
        "sections_count": he_count,
    })
    return {"template": doc, "can_edit": True}


# =====================================================================
# IND-3 E1 — Google-Translate DRAFT (persists NOTHING)
# =====================================================================
async def _google_translate_batch(texts: list, target: str) -> list:
    """One isolated provider call. TRANSLATE_MOCK=1 → deterministic
    pseudo-translation (probes; same pattern as the blanked-WA probes).
    The real key lives ONLY in env GOOGLE_TRANSLATE_API_KEY."""
    import os
    if os.environ.get("TRANSLATE_MOCK") == "1":
        return [f"[{target}] {t}" for t in texts]
    key = (os.environ.get("GOOGLE_TRANSLATE_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=503, detail="שירות התרגום אינו מוגדר — פנו לתמיכה")
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://translation.googleapis.com/language/translate/v2",
                params={"key": key},
                json={"q": texts, "source": "he",
                      "target": _GOOGLE_LANG_CODE[target], "format": "text"},
            )
    except Exception:
        logger.exception("induction translate: provider call failed")
        raise HTTPException(status_code=502, detail="שירות התרגום נכשל — נסו שוב מאוחר יותר")
    if resp.status_code != 200:
        logger.error("induction translate: provider status %s", resp.status_code)
        raise HTTPException(status_code=502, detail="שירות התרגום נכשל — נסו שוב מאוחר יותר")
    try:
        out = [t["translatedText"] for t in resp.json()["data"]["translations"]]
    except Exception:
        raise HTTPException(status_code=502, detail="שירות התרגום נכשל — נסו שוב מאוחר יותר")
    if len(out) != len(texts):
        # NEVER partial results.
        raise HTTPException(status_code=502, detail="שירות התרגום נכשל — נסו שוב מאוחר יותר")
    return out


class InductionTranslateRequest(BaseModel):
    target_language: str


@router.post("/{project_id}/induction-template/translate")
async def translate_induction_template(
    project_id: str,
    payload: InductionTranslateRequest,
    user: dict = Depends(get_current_user),
):
    """Returns a DRAFT translation of the CURRENT he sections — persists
    NOTHING; the org reviews in the editor and saves manually. Gate:
    exactly the template PUT edit gate."""
    org_id, can_edit = await _resolve_project_org_edit(user, project_id)
    if not org_id:
        raise HTTPException(status_code=404, detail="הפרויקט לא נמצא")
    if not can_edit:
        raise HTTPException(status_code=403, detail="רק בעל הארגון או מנהל ארגון יכולים לערוך את תוכן ההדרכה")
    target = (payload.target_language or "").strip()
    if target not in TRANSLATE_TARGETS:
        raise HTTPException(status_code=422, detail="שפת יעד לא נתמכת לתרגום")
    db = get_db()
    doc = await db.induction_templates.find_one({"org_id": org_id}, {"_id": 0})
    he_sections = (((doc or {}).get("languages") or {}).get("he") or {}).get("sections") or []
    if not he_sections:
        raise HTTPException(status_code=409, detail="אין תוכן בעברית לתרגום — יש לשמור קודם את התוכן העברי")
    # Structure preserved 1:1 — title and body translated separately.
    texts = []
    for s in he_sections:
        texts.append(s.get("title") or "")
        texts.append(s.get("body") or "")
    translated = await _google_translate_batch(texts, target)
    sections = [
        {"title": translated[i * 2], "body": translated[i * 2 + 1]}
        for i in range(len(he_sections))
    ]
    return {"target_language": target, "sections": sections, "draft": True}


# =====================================================================
# IND-3 E5 — induction certificate PDF (read-only, evidence semantics)
# =====================================================================
@router.get("/{project_id}/induction/certificate/{training_id}")
async def get_induction_certificate(
    project_id: str,
    training_id: str,
    user: dict = Depends(get_current_user),
):
    """Certificate PDF for a SIGNED induction training. Gate + lookups
    identical to the evidence endpoint (404/403 same semantics)."""
    db = get_db()
    await _check_project_access(user, project_id)

    tr = await db.safety_trainings.find_one(
        {"id": training_id, "project_id": project_id, "deletedAt": None}, {"_id": 0})
    if not tr or str(tr.get("training_type") or "").strip() != INDUCTION_TRAINING_TYPE:
        raise HTTPException(status_code=404, detail="הדרכת אתר לא נמצאה")
    sig = tr.get("worker_signature")
    if not sig:
        raise HTTPException(status_code=404, detail="הדרכת האתר אינה חתומה — אין תעודה להפקה")

    worker = await db.safety_workers.find_one(
        {"id": tr.get("worker_id")}, {"_id": 0, "full_name": 1})
    proj = await db.projects.find_one(
        {"id": project_id}, {"_id": 0, "name": 1, "org_id": 1})
    org = await db.organizations.find_one(
        {"id": (proj or {}).get("org_id")}, {"_id": 0, "name": 1})

    sig_url = None
    if sig.get("signature_ref"):
        try:
            sig_url = generate_url(sig["signature_ref"])
        except Exception:
            sig_url = None

    pdf_bytes = _build_induction_certificate_pdf(
        org_name=(org or {}).get("name") or "",
        project_name=(proj or {}).get("name") or "",
        worker_name=(worker or {}).get("full_name") or "",
        trained_at=tr.get("trained_at"),
        expires_at=tr.get("expires_at"),
        sig=sig,
        signature_url=sig_url,
    )

    import io as _io
    import urllib.parse
    from fastapi.responses import StreamingResponse
    fname = f"תעודת הדרכת אתר - {(worker or {}).get('full_name') or training_id}.pdf"
    quoted = urllib.parse.quote(fname)
    return StreamingResponse(
        _io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )


def _il_date(val) -> str:
    """ISO-ish → DD/MM/YYYY (IL format); tolerant of datetime strings."""
    s = str(val or "")[:10]
    try:
        d = date.fromisoformat(s)
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return s


def _build_induction_certificate_pdf(org_name, project_name, worker_name,
                                     trained_at, expires_at, sig, signature_url):
    """reportlab A4, Hebrew RTL per the diary/defects export pattern —
    build in memory, return bytes (house lesson)."""
    import io
    import os
    import arabic_reshaper
    from bidi.algorithm import get_display
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage,
    )
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    fonts_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "fonts")
    try:
        pdfmetrics.registerFont(TTFont("Rubik", os.path.join(fonts_dir, "Rubik-Regular.ttf")))
        pdfmetrics.registerFont(TTFont("Rubik-Bold", os.path.join(fonts_dir, "Rubik-Bold.ttf")))
    except Exception:
        pass

    def heb(text):
        if not text:
            return ""
        reshaped = arabic_reshaper.reshape(str(text))
        return get_display(reshaped)

    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    PURPLE = colors.HexColor("#7C3AED")

    st_brand = ParagraphStyle("CertBrand", fontName="Rubik-Bold", fontSize=12,
                              alignment=TA_CENTER, textColor=PURPLE, leading=16)
    st_title = ParagraphStyle("CertTitle", fontName="Rubik-Bold", fontSize=20,
                              alignment=TA_CENTER, textColor=SLATE_700, leading=26)
    st_sub = ParagraphStyle("CertSub", fontName="Rubik", fontSize=11,
                            alignment=TA_CENTER, textColor=SLATE_500, leading=15)
    st_label = ParagraphStyle("CertLabel", fontName="Rubik", fontSize=9,
                              alignment=TA_RIGHT, textColor=SLATE_500, leading=12)
    st_value = ParagraphStyle("CertValue", fontName="Rubik", fontSize=11,
                              alignment=TA_RIGHT, textColor=SLATE_700, leading=15)
    st_attest = ParagraphStyle("CertAttest", fontName="Rubik", fontSize=11,
                               alignment=TA_CENTER, textColor=SLATE_700, leading=17)
    st_footer = ParagraphStyle("CertFooter", fontName="Rubik", fontSize=8,
                               alignment=TA_CENTER, textColor=SLATE_500, leading=11)

    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    els = []
    els.append(Paragraph("BrikOps", st_brand))
    els.append(Spacer(1, 2 * mm))
    els.append(Paragraph(heb("תעודת הדרכת אתר"), st_title))
    els.append(Spacer(1, 2 * mm))
    line = Table([[""]], colWidths=[4 * cm], rowHeights=[0.8 * mm])
    line.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PURPLE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    line.hAlign = "CENTER"
    els.append(line)
    els.append(Spacer(1, 4 * mm))
    els.append(Paragraph(heb(f"{org_name} · {project_name}"), st_sub))
    els.append(Spacer(1, 8 * mm))

    lang_read = sig.get("language_read")
    lang_name = _PDF_LANG_NAMES.get(lang_read, lang_read or "")
    rows = [
        ("שם העובד", worker_name),
        ("תאריך ביצוע", _il_date(trained_at)),
        ("בתוקף עד", _il_date(expires_at)),
        ("שפת ההדרכה", lang_name),
    ]
    if sig.get("via_interpreter") and sig.get("interpreter_name"):
        rows.append(("מתורגמן/ת", f"באמצעות מתורגמן/ת: {sig['interpreter_name']}"))
    table_data = [
        [Paragraph(heb(v), st_value), Paragraph(heb(k), st_label)]
        for k, v in rows
    ]
    tbl = Table(table_data, colWidths=[11 * cm, 4 * cm])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    els.append(tbl)
    els.append(Spacer(1, 8 * mm))

    if sig.get("attestation_text"):
        att = Table(
            [[Paragraph(heb(sig["attestation_text"]), st_attest)]],
            colWidths=[15 * cm],
        )
        att.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        els.append(att)
        els.append(Spacer(1, 8 * mm))

    signed_line = f"חתימת העובד: {sig.get('name') or ''} · {_il_date(sig.get('signed_at'))}"
    els.append(Paragraph(heb(signed_line), st_value))
    els.append(Spacer(1, 2 * mm))
    sig_added = False
    if signature_url:
        try:
            from contractor_ops.export_router import _fetch_image_for_pdf
            buf = _fetch_image_for_pdf(signature_url)
            if buf:
                img = RLImage(buf, width=5 * cm, height=2.5 * cm, kind="proportional")
                img.hAlign = "RIGHT"
                els.append(img)
                sig_added = True
        except Exception:
            logger.exception("induction certificate: signature image embed failed")
    if not sig_added and sig.get("typed_name"):
        els.append(Paragraph(heb(f'"{sig["typed_name"]}" (חתימה מוקלדת)'), st_value))

    els.append(Spacer(1, 12 * mm))
    footer = (
        f"גרסת תוכן {sig.get('content_version')} · "
        f"מזהה תוכן {(sig.get('content_hash') or '')[:12]}"
    )
    els.append(Paragraph(heb(footer), st_footer))

    doc.build(els)
    return output.getvalue()
