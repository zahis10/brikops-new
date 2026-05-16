# BrikOps — Multi-Market Architecture Standards

**מטרה:** מסמך עקרונות ארכיטקטורה להתרחבות BrikOps לשווקים בינלאומיים
**נוצר:** אפריל 2026
**בעלים:** זהי שמי
**סטטוס:** מסמך reference — לא ליישום מיידי

---

## למה המסמך הזה קיים

BrikOps היום בנויה לשוק הישראלי. בעתיד נתרחב לשווקים נוספים (UAE, קפריסין, יוון, אחרים). **המסמך הזה קובע איך נעשה את זה — בצורה שלא תשבור את המערכת הישראלית ותאפשר גידול בריא.**

**מה המסמך הזה:**
- 3 עקרונות ארכיטקטורה עם דוגמאות קוד
- Standards לכל extension module חדש
- Timeline של מתי להתקדם לכל שלב
- Decision points ל-migration עתידי

**מה המסמך הזה לא:**
- לא spec ליישום מיידי
- לא קוד production-ready
- לא תחליף ל-spec ספציפי שתכתוב כשתגיע להרחבה

---

## מקור הדפוס — אותו עקרון כמו Batch 2b

הגישה כאן **לא חדשה.** היא אותה פילוסופיה הנדסית שכבר יישמנו ב-`Batch 2b Patch` (אפריל 2026) — הpatch שהוסיף `GroupedSelectField` ו-feature flags של `DEFECT_DRAFT_PRESERVATION` / `TRADE_SORT_IN_TEAM_FORM`.

**שתי שכבות הבטיחות שהגדרנו ב-Batch 2b:**

```
1. FEATURE FLAGS:
   Wrap all new behavior in FEATURES.X checks.
   Both flags = true by default.
   If flag=false, code must fall back to existing behavior exactly.

2. DO NOT MODIFY existing code (SelectField / BottomSheetSelect.js):
   Create a wrapper component (GroupedSelectField.js) that handles
   new behavior internally. Original stays 100% unchanged.
   git diff --stat frontend/src/components/BottomSheetSelect.js → MUST BE EMPTY.
```

**אותו דפוס, אותה פילוסופיה, multi-market הוא הרחבה שלו בסקייל אחר:**

| Batch 2b (component level) | Multi-market (module level) |
|---|---|
| `FEATURES.TRADE_SORT_IN_TEAM_FORM` flag | `project.market` field (`"il"` / `"uae"` / …) |
| `GroupedSelectField` wrapper component | `/backend/markets/<code>/` folder |
| `SelectField` **unchanged** (zero diff) | `/backend/core/*` **unchanged** |
| Fallback אם flag=false → SelectField רגיל | Fallback אם market unknown → core (ישראל) |
| Flip ל-false = מחזיר בדיוק התנהגות prod | אין market → מחזיר התנהגות ישראל |
| Zero blast radius על SelectField callers | Zero blast radius על ישראלי code |

**4 העקרונות המשותפים — שלא משתנים בין הרמות:**

1. **Additive, not destructive** — תמיד מוסיפים מעל, לא משנים מתחת
2. **Existing code frozen** — ה-"deep" code (SelectField / core) לא זז
3. **Dispatch at the edge** — ההחלטה על איזה code path לרוץ נעשית כמה שיותר גבוה (ב-AddTeamMemberForm / ב-router handler)
4. **Default to existing** — כל fallback מחזיר לקוד הישן, לא קורס

**הדוגמה המקבילה ב-multi-market:**

```python
# backend/routes/handover_router.py  ← "העטיפה" כאן, אחת לכל endpoint

@router.post("/handover/create")
async def create_handover(project_id: str, user: User):
    project = await get_project(project_id)
    market = project.market or "il"  # ← ה-"flag"

    # ישראלי = core, לא נוגעים
    if market == "il":
        return await core.handover.create(project_id, user)

    # UAE = wrapper חדש, קובץ נפרד (כמו GroupedSelectField)
    if market == "uae":
        from markets.uae import handover as uae_handover
        return await uae_handover.create(project_id, user)

    # Fallback = ישראלי (כמו flag=false)
    return await core.handover.create(project_id, user)
```

**7 שורות. בדיוק כמו** `{FEATURES.TRADE_SORT_IN_TEAM_FORM ? <GroupedSelectField> : <SelectField>}` — switchboard של שורה אחת, שני paths.

### למה זה חשוב לזכור

1. **לא ממציאים גלגל** — כשנגיע ל-Q1 2027 ונפתח את פרויקט UAE, אנחנו לא לומדים patent הנדסי חדש. אותה פילוסופיה, סקייל גדול יותר.
2. **ה-review מתאים גם לזה** — אותם grep checks שעשינו ב-Batch 2b (`git diff --stat frontend/src/components/BottomSheetSelect.js # empty`) ייושמו גם כאן (`git diff --stat backend/core/ # empty` בכל market PR).
3. **Batch 2b הוא ה-"proof of concept"** — הוכחנו שהדפוס הזה עובד על רכיב יחיד. Multi-market הוא אותו דפוס על endpoint, ואם הוכיח את עצמו על SelectField → יעבוד גם על handover.py.
4. **ההבטחה לעצמך** — אם אי-פעם מפתח/Claude/agent מציע refactor שנוגע ב-core code הישראלי "בגלל market X", המסמך הזה הוא ה-veto אוטומטי. **Core stays frozen. Markets add, never modify.**

---

## שלב 0: המצב הנוכחי (2026)

**ישראל בלבד. אין multi-market.**

**מה לעשות:** כלום. להמשיך לפתח ל-ישראל.

**מה לא לעשות:**
- לא להוסיף market fields
- לא ליצור /markets/ folder
- לא לעשות refactor ל-"market-aware"

**העקרון:** Don't pay the cost of flexibility before you need it.

---

## שלב 1: Extension Architecture (כשמתחילים שוק שני — Q4 2026)

### מתי להתחיל

**טריגר להתחלה:** החלטה קונקרטית להיכנס לשוק חדש, עם:
- Recon trip לשוק היעד (הושלם)
- Local partner (נמצא או בתהליך)
- הבנה ברורה של regulatory requirements
- תקציב לפיתוח 3 חודשים לפחות

**לא להתחיל לפני** שיש את ה-4 הנ"ל. אחרת תבנה infrastructure שלא תשתמש בה.

### עקרון היסוד

**Additive, Never Destructive.**

הקוד הישראלי הקיים **לא נוגעים בו**. שוק חדש = folder נפרד עם extensions.

### מבנה הfolder

```
/backend
  /core                    ← הקוד הקיים. לא משתנה. נשאר ישראלי.
    handover.py
    qc.py
    defects.py
    billing.py
    ...

  /markets                 ← חדש
    __init__.py

    /uae                   ← שוק ראשון שנוסף
      __init__.py
      config.py            ← נתונים בלבד
      handover.py          ← logic
      qc.py
      validators.py
      pdf_template.py
      notifications.py

    /cy                    ← שוק שני (עתידי)
      __init__.py
      config.py
      handover.py
      qc.py
      validators.py
      pdf_template.py
      notifications.py
```

**חשוב:** כל folder של market חייב את **אותה structure בדיוק**. זה קריטי ל-migration עתידי.

### Router Switch Pattern

בכל endpoint שמשתנה בין שווקים, הוסף switch:

```python
# /backend/routes/handover_router.py

@router.post("/handover/create")
async def create_handover(project_id: str, user: User):
    project = await get_project(project_id)
    market = project.market or "il"  # default ישראל

    if market == "il":
        return await core.handover.create(project_id, user)

    if market == "uae":
        from markets.uae import handover as uae_handover
        return await uae_handover.create(project_id, user)

    if market == "cy":
        from markets.cy import handover as cy_handover
        return await cy_handover.create(project_id, user)

    # ברירת מחדל — אם market לא מוכר, fallback לישראל
    return await core.handover.create(project_id, user)
```

**נקודות חשובות:**
1. ישראל היא תמיד ה-default. אם משהו נשבר ב-market, המערכת לא קורסת.
2. Import של markets הוא lazy (בתוך ה-if) — לא לייבא modules של שווקים שלא רלוונטיים לבקשה.
3. אם market לא מוכר, fallback לישראל. לא קריסה.

---

## שלב 2: 3 כללי זהב לכתיבת Extension

### כלל 1: אותה Structure בכל Extension

| קובץ | תפקיד |
|---|---|
| `__init__.py` | יצירת module |
| `config.py` | קבועים ונתונים ייחודיים לשוק |
| `handover.py` | logic של פרוטוקול מסירה |
| `qc.py` | logic של בקרת איכות |
| `validators.py` | validation rules (טלפון, ת.ז., וכד') |
| `pdf_template.py` | יצירת דוחות PDF |
| `notifications.py` | WhatsApp/Email templates |

### כלל 2: הפרדה בין Data ל-Logic

**Data** → config.py (sections, validation patterns, currency, VAT, legal refs, template IDs)
**Logic** → קבצי logic (create handover, send notifications, generate PDF)

### כלל 3: אותן Function Signatures בכל Extension

```python
async def create(project_id: str, user: User) -> Handover: ...
async def get(handover_id: str, user: User) -> Handover: ...
async def update(handover_id: str, data: dict, user: User) -> Handover: ...
async def validate(handover: Handover) -> List[ValidationError]: ...
async def generate_pdf(handover: Handover) -> bytes: ...
async def send_notification(handover: Handover, recipient: User) -> None: ...
```

---

## שלב 3: Checklist ל-Extension חדש

### Setup Phase (יום 1)
- [ ] יצירת `/backend/markets/<market_code>/`
- [ ] `__init__.py` ריק
- [ ] `config.py` עם constants (CURRENCY, VAT_RATE, DATE_FORMAT, PHONE_PREFIX)
- [ ] שאר הקבצים כ-stubs
- [ ] Router switches ב-endpoints רלוונטיים
- [ ] Test: משתמש ישראלי עדיין עובד 100%

### Config Phase (יום 2-3)
- [ ] HANDOVER_SECTIONS
- [ ] REQUIRED_FIELDS
- [ ] DEFECT_CATEGORIES (אם שונה)
- [ ] LEGAL_REFERENCES
- [ ] COMPLIANCE_TAGS

### Logic Phase (שבועות 1-8)
- [ ] handover.py — 6 פונקציות
- [ ] qc.py — אותן 6 פונקציות
- [ ] validators.py
- [ ] pdf_template.py
- [ ] notifications.py

### Testing Phase (שבועות 9-10)
- [ ] Unit tests לכל פונקציה
- [ ] Integration test
- [ ] Cross-market test
- [ ] Regression: ישראל לא נשברה

### Launch Phase (שבועות 11-12)
- [ ] Beta עם 1-2 לקוחות
- [ ] משוב + תיקונים
- [ ] Documentation ל-local partner
- [ ] Launch רשמי

---

## שלב 4: דוגמה מלאה — UAE Handover

### `markets/uae/config.py`

```python
"""UAE market configuration - data only, no logic."""

HANDOVER_SECTIONS = [
    {"id": "property_info", "title_en": "Property Information", "required": True,
     "fields": ["address", "pin", "unit_number", "building_name"]},
    {"id": "pin_verification", "title_en": "Property Index Number Verification",
     "required": True, "fields": ["pin", "dld_reference"]},
    {"id": "dlp_acknowledgment", "title_en": "Defect Liability Period",
     "required": True, "fields": ["dlp_start_date", "dlp_duration_months"]},
    {"id": "thermal_imaging", "title_en": "Thermal Imaging Inspection",
     "required": False, "fields": ["thermal_images", "findings"]},
    {"id": "moisture_reading", "title_en": "Moisture Readings",
     "required": False, "fields": ["readings", "acceptable_range"]},
    {"id": "meter_readings", "title_en": "Utility Meter Readings",
     "required": True, "fields": ["dewa_reading", "water_reading", "cooling_reading"]},
    {"id": "keys_handover", "title_en": "Keys and Access Handover",
     "required": True, "fields": ["keys_count", "access_cards", "parking_permits"]},
    {"id": "signatures", "title_en": "Signatures",
     "required": True, "fields": ["buyer_signature", "developer_signature"]},
]

VALIDATION_RULES = {
    "pin": {"pattern": r"^\d{10}$", "error_en": "Property Index Number must be 10 digits"},
    "phone": {"pattern": r"^\+971\d{9}$", "error_en": "Phone must start with +971"},
    "dlp_duration_months": {"min": 12, "max": 12, "error_en": "DLP fixed at 12 months"},
}

CURRENCY = "AED"
VAT_RATE = 0.05
DATE_FORMAT = "DD/MM/YYYY"
PHONE_PREFIX = "+971"
PRIMARY_LANGUAGE = "ar"
SECONDARY_LANGUAGE = "en"
LEGAL_REFERENCES = {
    "structural_warranty": "Article 40, Law No. 6 of 2019",
    "dlp": "Executive Council Resolution No. 6 of 2010",
}
COMPLIANCE_TAGS = ["DLD", "RERA", "Dubai_Municipality"]
```

### `markets/uae/handover.py`

```python
"""UAE-specific handover logic."""

from datetime import datetime, timedelta
from core.models import Handover, Project, User, ValidationError
from core.db import db
from . import config
from .validators import validate_uae_phone, validate_uae_pin


async def create(project_id: str, user: User) -> Handover:
    project = await db.projects.find_one({"id": project_id})
    if not project or project.get("market") != "uae":
        raise ValueError(f"Project {project_id} not valid for UAE")

    handover_data = {
        "id": generate_uuid(),
        "project_id": project_id,
        "market": "uae",
        "sections": [s["id"] for s in config.HANDOVER_SECTIONS],
        "required_sections": [s["id"] for s in config.HANDOVER_SECTIONS if s["required"]],
        "legal_references": config.LEGAL_REFERENCES,
        "currency": config.CURRENCY,
        "created_by": user.id,
        "created_at": datetime.utcnow().isoformat(),
        "status": "draft",
    }
    await db.handovers.insert_one(handover_data)
    return Handover(**handover_data)


async def get(handover_id: str, user: User) -> Handover:
    handover = await db.handovers.find_one({"id": handover_id})
    if not handover:
        raise ValueError(f"Handover {handover_id} not found")
    return Handover(**handover)


async def update(handover_id: str, data: dict, user: User) -> Handover:
    if "dlp_start_date" in data:
        start = datetime.fromisoformat(data["dlp_start_date"])
        data["dlp_expiry_date"] = (start + timedelta(days=365)).isoformat()
    data["updated_at"] = datetime.utcnow().isoformat()
    data["updated_by"] = user.id
    await db.handovers.update_one({"id": handover_id}, {"$set": data})
    return await get(handover_id, user)


async def validate(handover: Handover) -> list[ValidationError]:
    errors = []
    for section in config.HANDOVER_SECTIONS:
        if not section["required"]:
            continue
        data = handover.sections_data.get(section["id"], {})
        for field in section["fields"]:
            if not data.get(field):
                errors.append(ValidationError(
                    section=section["id"], field=field,
                    message_en=f"Field {field} is required"
                ))
    return errors


async def generate_pdf(handover: Handover) -> bytes:
    from .pdf_template import create_uae_handover_pdf
    return await create_uae_handover_pdf(handover, config)


async def send_notification(handover: Handover, recipient: User) -> None:
    from .notifications import send_handover_ready_notification
    await send_handover_ready_notification(handover=handover, recipient=recipient,
                                            language=config.PRIMARY_LANGUAGE)
```

---

## שלב 5: מתי להתקדם ל-Config-Driven

### Decision Criteria (כל 6 חודשים)

**שאלה 1: כמה שווקים יש?**
- 1-3: Extension עובד מצוין
- 4-5: להתחיל לחשוב על migration
- 6+: זמן ל-migration

**שאלה 2: כמה זמן לוקח להוסיף שוק חדש?**
- 2-3 חודשים: מצוין
- 4-6: סימן שיש חזרה על קוד
- 6+: migration דחוף

**שאלה 3: באגים חוזרים?**
- באג מתוקן פעם אחת: מצוין
- 2-3 extensions: סימן מתחיל
- 5+ extensions: migration נדרש

### ה-trigger המוחלט

**אחד מאלה קורה → זמן ל-migration:**
1. 5+ לקוחות מבקשים field מיוחד ב-same market
2. הוספת market חדש > 6 חודשים
3. Bug fixes בsame logic ב-4+ extensions

---

## שלב 6: Migration ל-Config-Driven (2028-2029 אולי)

### מבנה עתידי

```
/backend
  /core/engines
    handover_engine.py     ← generic
    qc_engine.py
    validation_engine.py
    pdf_engine.py

  /configs
    il.json
    uae.json
    cy.json
```

### Config-Driven engine

```python
async def create_handover(project_id: str, user: User) -> Handover:
    project = await get_project(project_id)
    market_config = await load_market_config(project.market)

    handover = Handover(
        project_id=project_id,
        market=project.market,
        sections=market_config["handover_sections"],
        validation_rules=market_config["validation_rules"],
        currency=market_config["currency"],
        legal_references=market_config["legal_references"]
    )
    await handover.save()
    return handover
```

### Migration Effort

- **אם דבקת ב-3 הכללים:** 3-4 חודשים, בעיקר automated
- **אם לא:** 8-12 חודשים, עבודה ידנית, סיכון גבוה

---

## שלב 7: Timeline מוצע

### 2026
| רבעון | פעולה |
|---|---|
| Q1-Q2 | ישראל בלבד. Safety Phase 1, beta users, scaling. |
| Q3 | לא מגעים בארכיטקטורה. focus על ישראל. 15-20 paying customers. |
| Q4 | Recon trip לדובאי. מציאת local partner. עדיין אין שינוי בקוד. |

### 2027
| רבעון | פעולה |
|---|---|
| Q1 | Extension infrastructure (3 ימי עבודה): market field, /markets/ folder, router switches. |
| Q1-Q2 | UAE extension development: 2-3 חודשים. לפי 3 הכללים. |
| Q3 | UAE beta launch. 3-5 לקוחות. |
| Q4 | UAE scaling. 10-20 לקוחות. |

### 2028
| רבעון | פעולה |
|---|---|
| Q1-Q2 | שוק שלישי? (קפריסין/קטר/סעודיה). |
| Q3 | Decision point: 3 שווקים, איך עובד? |
| Q4 | אם יש trigger — מתחיל migration ל-Config-Driven. אחרת — ממשיך Extension. |

### 2029+
| תאריך | פעולה |
|---|---|
| 2029 | Config-Driven באוויר. הוספת שווקים = JSON files. |
| 2030 | 5-10 שווקים, scaling גלובלי. |

---

## שלב 8: Red Flags

### Red Flag 1: קוד כפול בין Extensions
**פתרון:** העבר ל-`core/shared/`

### Red Flag 2: Extension קוראת ל-Extension אחרת
```python
from markets.uae.handover import some_function  # ← לא!
```
**פתרון:** logic משותפת → core. ייחודית → copy.

### Red Flag 3: Logic ב-config.py
**פתרון:** logic → handover.py. config.py רק dicts.

### Red Flag 4: Hardcoded Strings ב-Core
```python
if project.market == "il":
    return "פרוטוקול מסירה"  # ← hardcoded
```
**פתרון:** core.py לא יודעת על שווקים ספציפיים.

### Red Flag 5: זמן הוספת שוק גדל
Market 4 לוקח 6 חודשים? **זמן ל-Config-Driven.**

---

## שלב 9: Quick Reference

### בכל feature חדש (גם בישראל only):
- [ ] hardcoded Hebrew/Israeli? שים `# MARKET-SPECIFIC: Israel`
- [ ] currency? helper function (גם אם היום רק ₪)
- [ ] phone validation? helper
- [ ] date format? helper

### בכל extension חדש:
- [ ] אותה structure: 6 קבצים, אותם שמות
- [ ] config.py — רק data
- [ ] handover.py — 6 פונקציות עם חתימות זהות
- [ ] אין import בין extensions
- [ ] tests לכל פונקציה
- [ ] ישראל עובדת 100%

### בכל decision point:
- [ ] כמה שווקים?
- [ ] זמן להוספת שוק חדש?
- [ ] באגים חוזרים ב-2+ extensions?
- [ ] קוד עדיין נוח לתחזוקה?

---

## שורה תחתונה

**עכשיו:** ישראל only. שום שינוי ארכיטקטוני.
**שוק שני (Q1 2027):** Extension + 3 כללים.
**שוק שלישי (Q3 2028?):** אותו pattern.
**כש pattern מכאיב (Q4 2028?):** שיקול migration ל-Config-Driven.

**העקרון:** אל תעשה over-engineering עכשיו. אבל אל תעשה under-engineering שתשלם עליה ב-8 חודשי refactor בעתיד.

---

*מסמך זה נכתב באפריל 2026. יש לעדכן כל 6-12 חודשים או כשמתחילים שוק חדש. מסמך reference בלבד.*
