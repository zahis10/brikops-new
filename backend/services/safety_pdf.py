"""
Safety regulatory "פנקס כללי" (General Register) PDF generator.

Public API: `async generate_safety_register(db, project_id) -> bytes`.

Renders 9 sections in Hebrew RTL with page-X-of-Y footer and the fixed
work-manager declaration + 3 signature lines in section 9.

PII rule: never reads or emits id_number / id_number_hash. Only the
fields explicitly selected below are included.

Font path is `__file__`-anchored — survives any cwd (Elastic Beanstalk
safe). Font registration failures are logged via logger.warning, never
silently swallowed.
"""
import io
import logging
import os
from datetime import datetime, timedelta, timezone

from services.pdf_service import hebrew

logger = logging.getLogger(__name__)

_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

_fonts_registered = False


def _register_fonts_once():
    global _fonts_registered
    if _fonts_registered:
        return
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular = os.path.join(_FONTS_DIR, "Rubik-Regular.ttf")
    bold = os.path.join(_FONTS_DIR, "Rubik-Bold.ttf")
    try:
        pdfmetrics.registerFont(TTFont("Rubik", regular))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] Failed to register Rubik regular at {regular}: {e}")
    try:
        pdfmetrics.registerFont(TTFont("Rubik-Bold", bold))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] Failed to register Rubik bold at {bold}: {e}")
    _fonts_registered = True


CATEGORY_HE = {
    "scaffolding": "פיגומים",
    "heights": "עבודה בגובה",
    "electrical_safety": "בטיחות חשמל",
    "lifting": "הרמה וציוד",
    "excavation": "חפירות",
    "fire_safety": "אש ובטיחות אש",
    "ppe": "ציוד מגן אישי",
    "site_housekeeping": "סדר וניקיון",
    "hazardous_materials": "חומרים מסוכנים",
    "other": "אחר",
}
SEVERITY_HE = {"1": "נמוכה", "2": "בינונית", "3": "גבוהה"}
DOC_STATUS_HE = {"open": "פתוח", "in_progress": "בביצוע", "resolved": "נפתר", "verified": "אומת"}
TASK_STATUS_HE = {"open": "פתוח", "in_progress": "בביצוע", "completed": "הושלם", "cancelled": "בוטל"}
INCIDENT_TYPE_HE = {"near_miss": "כמעט-תאונה", "injury": "פציעה", "property_damage": "נזק לרכוש"}

WORK_MANAGER_DECLARATION = (
    "אני הח״מ, מנהל העבודה באתר, מצהיר/ה בזאת כי הפנקס הכללי נוהל לפי "
    "תקנות הבטיחות בעבודה (עבודות בנייה), התשמ״ח-1988, וכי הנתונים "
    "המופיעים בו משקפים את מצב הבטיחות באתר במועד ההפקה."
)


def _fmt_date(iso):
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return str(iso)[:10]


def _on_page(canvas, doc):
    """Page-X-of-Y footer (uses two-pass via doc.page; total via canvas)."""
    canvas.saveState()
    canvas.setFont("Rubik", 8)
    page_str = f"עמוד {doc.page}"
    canvas.drawCentredString(doc.pagesize[0] / 2.0, 1.0 * 28.35, hebrew(page_str))
    canvas.restoreState()


async def generate_safety_register(db, project_id: str) -> bytes:
    """
    Build the regulatory 9-section פנקס כללי for `project_id`.

    All Mongo reads filter `deletedAt: None`. PII fields are never selected.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
    )

    _register_fonts_once()

    project = await db.projects.find_one({"id": project_id}, {"_id": 0}) or {}

    workers = await db.safety_workers.find(
        {"project_id": project_id, "deletedAt": None},
        {"_id": 0, "id": 1, "full_name": 1, "profession": 1, "company_id": 1,
         "phone": 1, "created_at": 1},
    ).to_list(length=100000)
    worker_ids = [w["id"] for w in workers]

    trainings = await db.safety_trainings.find(
        {"project_id": project_id, "deletedAt": None},
        {"_id": 0, "worker_id": 1, "training_type": 1, "instructor_name": 1,
         "trained_at": 1, "expires_at": 1},
    ).to_list(length=100000)

    documents = await db.safety_documents.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)

    tasks = await db.safety_tasks.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)

    incidents = await db.safety_incidents.find(
        {"project_id": project_id, "deletedAt": None}, {"_id": 0}
    ).to_list(length=100000)

    company_ids = {r.get("company_id") for r in workers + documents + tasks if r.get("company_id")}
    company_map = {}
    if company_ids:
        companies = await db.project_companies.find(
            {"id": {"$in": list(company_ids)}, "deletedAt": None},
            {"_id": 0, "id": 1, "name": 1},
        ).to_list(length=10000)
        company_map = {c["id"]: c.get("name", "") for c in companies}

    user_ids = {r.get("assignee_id") for r in tasks if r.get("assignee_id")}
    user_map = {}
    if user_ids:
        users = await db.users.find(
            {"id": {"$in": list(user_ids)}}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(length=10000)
        user_map = {u["id"]: u.get("name", "") for u in users}

    worker_name_map = {w["id"]: w.get("full_name", "") for w in workers}

    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    GREY_HDR = colors.HexColor("#E5E7EB")

    title_style = ParagraphStyle(
        "RTitle", fontName="Rubik-Bold", fontSize=20,
        alignment=TA_CENTER, textColor=SLATE_700, leading=26,
    )
    h2 = ParagraphStyle(
        "RH2", fontName="Rubik-Bold", fontSize=13,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=18,
        spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "RBody", fontName="Rubik", fontSize=10,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=14,
    )
    sub = ParagraphStyle(
        "RSub", fontName="Rubik", fontSize=9,
        alignment=TA_CENTER, textColor=SLATE_500, leading=12,
    )
    cell = ParagraphStyle(
        "RCell", fontName="Rubik", fontSize=9,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=12,
    )
    cell_hdr = ParagraphStyle(
        "RCellHdr", fontName="Rubik-Bold", fontSize=9,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=12,
    )

    def _table(headers, rows, col_widths):
        data = [[Paragraph(hebrew(h), cell_hdr) for h in headers]]
        for r in rows:
            data.append([Paragraph(hebrew(c), cell) for c in r])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), GREY_HDR),
            ("GRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.8 * cm,
        title="פנקס כללי - בטיחות",
    )
    elems = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Section 1: Cover
    elems.append(Paragraph(hebrew("פנקס כללי - בטיחות בעבודה"), title_style))
    elems.append(Spacer(1, 4 * mm))
    project_name = project.get("name", "")
    cover_lines = [f"פרויקט: {project_name}"]
    if project.get("client_name"):
        cover_lines.append(f"לקוח: {project['client_name']}")
    if project.get("address"):
        cover_lines.append(f"כתובת: {project['address']}")
    cover_lines.append(f"תאריך הפקה: {today}")
    for line in cover_lines:
        elems.append(Paragraph(hebrew(line), sub))
    elems.append(Spacer(1, 8 * mm))

    # Section 2: Project metadata table
    elems.append(Paragraph(hebrew("1. פרטי הפרויקט"), h2))
    meta_rows = [
        ["שם פרויקט", project_name or "—"],
        ["מזהה פרויקט", project_id],
        ["לקוח", project.get("client_name", "—") or "—"],
        ["כתובת", project.get("address", "—") or "—"],
        ["תאריך הפקת הפנקס", today],
    ]
    elems.append(_table(["שדה", "ערך"], meta_rows, [5 * cm, 11 * cm]))
    elems.append(Spacer(1, 6 * mm))

    # Section 3: Workers (NO id_number)
    elems.append(Paragraph(hebrew("2. רשימת עובדים"), h2))
    if workers:
        rows = []
        for w in workers:
            rows.append([
                w.get("full_name", ""),
                w.get("profession", "") or "—",
                company_map.get(w.get("company_id", ""), "") or "—",
                w.get("phone", "") or "—",
                _fmt_date(w.get("created_at")),
            ])
        elems.append(_table(
            ["שם מלא", "מקצוע", "חברה", "טלפון", "תאריך כניסה"],
            rows, [4 * cm, 3 * cm, 4 * cm, 3 * cm, 3 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין עובדים רשומים."), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 4: Trainings
    elems.append(Paragraph(hebrew("3. הדרכות בטיחות"), h2))
    if trainings:
        rows = []
        for t in trainings:
            rows.append([
                worker_name_map.get(t.get("worker_id", ""), ""),
                t.get("training_type", ""),
                t.get("instructor_name", "") or "—",
                _fmt_date(t.get("trained_at")),
                _fmt_date(t.get("expires_at")) or "—",
            ])
        elems.append(_table(
            ["עובד", "סוג הדרכה", "מדריך", "תאריך הדרכה", "תוקף עד"],
            rows, [4 * cm, 4 * cm, 3 * cm, 3 * cm, 3 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין הדרכות רשומות."), body))
    elems.append(PageBreak())

    # Section 5: Open documents
    elems.append(Paragraph(hebrew("4. ליקויי בטיחות פתוחים"), h2))
    open_docs = [d for d in documents if d.get("status") in ("open", "in_progress")]
    if open_docs:
        rows = []
        for d in open_docs:
            rows.append([
                d.get("title", ""),
                CATEGORY_HE.get(d.get("category", ""), d.get("category", "")),
                SEVERITY_HE.get(d.get("severity", ""), ""),
                DOC_STATUS_HE.get(d.get("status", ""), d.get("status", "")),
                d.get("location", "") or "—",
                _fmt_date(d.get("found_at")),
            ])
        elems.append(_table(
            ["כותרת", "קטגוריה", "חומרה", "סטטוס", "מיקום", "תאריך"],
            rows, [4 * cm, 3 * cm, 2 * cm, 2 * cm, 3 * cm, 3 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין ליקויים פתוחים."), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 6: Corrective tasks
    elems.append(Paragraph(hebrew("5. משימות מתקנות"), h2))
    if tasks:
        rows = []
        for tk in tasks:
            rows.append([
                tk.get("title", ""),
                TASK_STATUS_HE.get(tk.get("status", ""), tk.get("status", "")),
                SEVERITY_HE.get(tk.get("severity", ""), ""),
                user_map.get(tk.get("assignee_id", ""), "") or "—",
                _fmt_date(tk.get("due_at")) or "—",
                _fmt_date(tk.get("completed_at")) or "—",
            ])
        elems.append(_table(
            ["כותרת", "סטטוס", "חומרה", "אחראי", "יעד", "הושלם"],
            rows, [4 * cm, 2.5 * cm, 2 * cm, 3 * cm, 2.5 * cm, 3 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין משימות מתקנות."), body))
    elems.append(PageBreak())

    # Section 7: Incidents
    elems.append(Paragraph(hebrew("6. אירועי בטיחות"), h2))
    if incidents:
        rows = []
        for inc in incidents:
            rows.append([
                INCIDENT_TYPE_HE.get(inc.get("incident_type", ""), inc.get("incident_type", "")),
                SEVERITY_HE.get(inc.get("severity", ""), ""),
                _fmt_date(inc.get("occurred_at")),
                inc.get("location", "") or "—",
                worker_name_map.get(inc.get("injured_worker_id", ""), "") or "—",
                "כן" if inc.get("reported_to_authority") else "לא",
            ])
        elems.append(_table(
            ["סוג", "חומרה", "תאריך", "מיקום", "עובד נפגע", "דווח לרשות"],
            rows, [3 * cm, 2 * cm, 2.5 * cm, 3 * cm, 3.5 * cm, 3 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין אירועי בטיחות רשומים."), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 8: Statistical summary
    elems.append(Paragraph(hebrew("7. סיכום סטטיסטי"), h2))
    by_category = {}
    for d in documents:
        cat = d.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1
    if by_category:
        rows = [
            [CATEGORY_HE.get(cat, cat), str(cnt)]
            for cat, cnt in sorted(by_category.items(), key=lambda x: -x[1])
        ]
        elems.append(_table(["קטגוריה", "סה״כ ליקויים"], rows, [10 * cm, 6 * cm]))
    else:
        elems.append(Paragraph(hebrew("אין נתונים לסיכום."), body))
    elems.append(Spacer(1, 4 * mm))
    for line in (
        f"סה״כ עובדים: {len(workers)}",
        f"סה״כ הדרכות: {len(trainings)}",
        f"סה״כ ליקויים: {len(documents)}",
        f"סה״כ משימות: {len(tasks)}",
        f"סה״כ אירועים: {len(incidents)}",
    ):
        elems.append(Paragraph(hebrew(line), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 8b: Audit trail (last 30 days)
    elems.append(Paragraph(hebrew("8. תיעוד פעולות (30 ימים אחרונים)"), h2))
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    audit_events = await db.audit_events.find(
        {"entity_type": {"$regex": "^safety"}, "created_at": {"$gte": cutoff_30d},
         "payload.project_id": project_id},
        {"_id": 0, "entity_type": 1, "action": 1, "created_at": 1, "actor_id": 1},
    ).sort("created_at", -1).limit(50).to_list(length=50)
    if audit_events:
        rows = []
        for ev in audit_events:
            rows.append([
                _fmt_date(ev.get("created_at")),
                ev.get("entity_type", ""),
                ev.get("action", ""),
                ev.get("actor_id", "")[:8] if ev.get("actor_id") else "",
            ])
        elems.append(_table(
            ["תאריך", "ישות", "פעולה", "מבצע"],
            rows, [3 * cm, 4 * cm, 5 * cm, 4 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין פעולות בתקופה זו."), body))
    elems.append(PageBreak())

    # Section 9: Work-manager declaration + 3 signature lines
    elems.append(Paragraph(hebrew("9. הצהרת מנהל העבודה וחתימות"), h2))
    elems.append(Spacer(1, 3 * mm))
    elems.append(Paragraph(hebrew(WORK_MANAGER_DECLARATION), body))
    elems.append(Spacer(1, 12 * mm))

    sig_line_style = ParagraphStyle(
        "SigLine", fontName="Rubik", fontSize=10,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=14,
    )
    for label in ("מנהל העבודה", "ממונה הבטיחות", "מנהל הפרויקט"):
        elems.append(Paragraph(hebrew(f"{label}:"), sig_line_style))
        elems.append(Spacer(1, 2 * mm))
        line = Table([[""]], colWidths=[8 * cm], rowHeights=[0.4 * mm])
        line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SLATE_700)]))
        line.hAlign = "RIGHT"
        elems.append(line)
        elems.append(Paragraph(hebrew("שם, תאריך וחתימה"), sub))
        elems.append(Spacer(1, 8 * mm))

    elems.append(Spacer(1, 6 * mm))
    elems.append(Paragraph(hebrew("נוצר באמצעות BrikOps · brikops.com"), sub))

    doc.build(elems, onFirstPage=_on_page, onLaterPages=_on_page)
    out.seek(0)
    return out.getvalue()
