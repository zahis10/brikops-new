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

NO conduct flow, NO snapshot writer, NO delete endpoint in this batch
(IND-2 / IND-3). induction_content_snapshots gets its unique index only.
"""
import hashlib
import json
import uuid

from contractor_ops.safety._shared import (  # noqa: F401
    BaseModel, Depends, Field, HTTPException, List,
    get_current_user, get_db, logger, router, _audit, _now,
)


# =====================================================================
# Constants
# =====================================================================
INDUCTION_READ_GLOBAL_ROLES = ("project_manager", "management_team")
MAX_SECTIONS = 200
MAX_TITLE_LEN = 200
MAX_BODY_LEN = 5000

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
    org = await get_user_org(user["id"])
    if not org:
        return None, False
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
@router.get("/induction-template")
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


@router.put("/induction-template")
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
