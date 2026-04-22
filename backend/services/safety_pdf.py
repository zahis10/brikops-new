"""
Safety PDF register generator — "פנקס כללי" (general safety log).

Renders 9 sections in Hebrew RTL using ReportLab. Mirrors the font-resolver
pattern from export_router.py (`__file__`-anchored path, NEVER cwd-relative
since Elastic Beanstalk does not guarantee cwd).

PII guard: NEVER include `id_number` or `id_number_hash` in any section.
"""
import io
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# __file__-anchored — survives any cwd (Elastic Beanstalk safe).
_FONTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fonts")

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

DOC_STATUS_HE = {
    "open": "פתוח",
    "in_progress": "בביצוע",
    "resolved": "נפתר",
    "verified": "אומת",
}

TASK_STATUS_HE = {
    "open": "פתוח",
    "in_progress": "בביצוע",
    "completed": "הושלם",
    "cancelled": "בוטל",
}

INCIDENT_TYPE_HE = {
    "near_miss": "כמעט-תאונה",
    "injury": "פציעה",
    "property_damage": "נזק לרכוש",
}


def _hebrew(text) -> str:
    """Reshape + bidi for Hebrew rendering in ReportLab."""
    if text is None or text == "":
        return ""
    try:
        import arabic_reshaper
        from bidi.algorithm import get_display
        return get_display(arabic_reshaper.reshape(str(text)))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] hebrew reshape failed: {e}")
        return str(text)


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return str(iso)[:10]


def _register_fonts():
    """Register Rubik fonts. Logs warnings on failure (NEVER silent)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    regular_path = os.path.join(_FONTS_DIR, "Rubik-Regular.ttf")
    bold_path = os.path.join(_FONTS_DIR, "Rubik-Bold.ttf")

    try:
        pdfmetrics.registerFont(TTFont("Rubik", regular_path))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] Failed to register Rubik-Regular at {regular_path}: {e}")

    try:
        pdfmetrics.registerFont(TTFont("Rubik-Bold", bold_path))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] Failed to register Rubik-Bold at {bold_path}: {e}")


def generate_pnkas_pdf(
    project: dict,
    score: dict,
    workers: list,
    trainings: list,
    documents: list,
    tasks: list,
    incidents: list,
    company_map: dict,
    user_map: dict,
) -> bytes:
    """
    Build the 9-section פנקס כללי PDF and return raw bytes.

    PII guard: caller MUST strip id_number / id_number_hash from `workers`
    before passing in. This function does NOT render those fields even if
    present, but the contract is that they should never reach this layer.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
    )

    _register_fonts()

    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    AMBER = colors.HexColor("#B45309")
    RED = colors.HexColor("#DC2626")
    GREEN = colors.HexColor("#16A34A")

    title_style = ParagraphStyle(
        "Title", fontName="Rubik-Bold", fontSize=20,
        alignment=TA_CENTER, textColor=SLATE_700, leading=26,
    )
    h2 = ParagraphStyle(
        "H2", fontName="Rubik-Bold", fontSize=14,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=18,
        spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body", fontName="Rubik", fontSize=10,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=14,
    )
    sub = ParagraphStyle(
        "Sub", fontName="Rubik", fontSize=9,
        alignment=TA_CENTER, textColor=SLATE_500, leading=12,
    )
    cell = ParagraphStyle(
        "Cell", fontName="Rubik", fontSize=9,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=12,
    )
    cell_hdr = ParagraphStyle(
        "CellHdr", fontName="Rubik-Bold", fontSize=9,
        alignment=TA_RIGHT, textColor=colors.white, leading=12,
    )

    def _table(headers, rows, col_widths):
        data = [[Paragraph(_hebrew(h), cell_hdr) for h in headers]]
        for r in rows:
            data.append([Paragraph(_hebrew(c), cell) for c in r])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), AMBER),
            ("GRID", (0, 0), (-1, -1), 0.4, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return t

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title="פנקס כללי - בטיחות",
    )
    elements = []

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # --- Section 1: Cover / Project header ----------------------------------
    elements.append(Paragraph(_hebrew("פנקס כללי - בטיחות בעבודה"), title_style))
    elements.append(Spacer(1, 4 * mm))
    project_name = project.get("name") or project.get("project_name") or ""
    client = project.get("client_name") or ""
    address = project.get("address") or ""
    cover_lines = [
        f"פרויקט: {project_name}",
        f"לקוח: {client}" if client else None,
        f"כתובת: {address}" if address else None,
        f"תאריך הפקה: {today}",
    ]
    for line in [l for l in cover_lines if l]:
        elements.append(Paragraph(_hebrew(line), sub))
    elements.append(Spacer(1, 6 * mm))

    # --- Section 2: Safety score summary ------------------------------------
    elements.append(Paragraph(_hebrew("1. תקציר ציון בטיחות"), h2))
    score_value = score.get("score", 0)
    breakdown = score.get("breakdown", {})
    score_color = GREEN if score_value >= 80 else (AMBER if score_value >= 50 else RED)
    score_style = ParagraphStyle(
        "Score", fontName="Rubik-Bold", fontSize=28,
        alignment=TA_CENTER, textColor=score_color, leading=32,
    )
    elements.append(Paragraph(f"{int(score_value)} / 100", score_style))
    elements.append(Spacer(1, 3 * mm))
    score_rows = [
        ["ליקויים פתוחים (גבוהה)", str(breakdown.get("open_sev3", 0))],
        ["ליקויים פתוחים (בינונית)", str(breakdown.get("open_sev2", 0))],
        ["ליקויים פתוחים (נמוכה)", str(breakdown.get("open_sev1", 0))],
        ["משימות באיחור", str(breakdown.get("overdue_tasks", 0))],
        ["אירועים ב-90 ימים אחרונים", str(breakdown.get("recent_incidents", 0))],
        ["עובדים ללא הדרכה בתוקף", str(breakdown.get("untrained_workers", 0))],
    ]
    elements.append(_table(["מדד", "כמות"], score_rows, [11 * cm, 5 * cm]))
    elements.append(Spacer(1, 6 * mm))

    # --- Section 3: Workers (NO id_number) ----------------------------------
    elements.append(Paragraph(_hebrew("2. רשימת עובדים"), h2))
    if workers:
        rows = []
        for w in workers:
            rows.append([
                w.get("full_name", ""),
                w.get("profession", ""),
                company_map.get(w.get("company_id", ""), ""),
                w.get("phone", ""),
                _fmt_date(w.get("created_at")),
            ])
        elements.append(_table(
            ["שם מלא", "מקצוע", "חברה", "טלפון", "תאריך כניסה"],
            rows, [4 * cm, 3 * cm, 4 * cm, 3 * cm, 3 * cm],
        ))
    else:
        elements.append(Paragraph(_hebrew("אין עובדים רשומים."), body))
    elements.append(Spacer(1, 6 * mm))

    # --- Section 4: Trainings -----------------------------------------------
    elements.append(Paragraph(_hebrew("3. הדרכות"), h2))
    if trainings:
        worker_name_map = {w["id"]: w.get("full_name", "") for w in workers}
        rows = []
        for t in trainings:
            rows.append([
                worker_name_map.get(t.get("worker_id", ""), ""),
                t.get("training_type", ""),
                t.get("instructor_name", ""),
                _fmt_date(t.get("trained_at")),
                _fmt_date(t.get("expires_at")) or "—",
            ])
        elements.append(_table(
            ["עובד", "סוג הדרכה", "מדריך", "תאריך הדרכה", "תוקף עד"],
            rows, [4 * cm, 4 * cm, 3 * cm, 3 * cm, 3 * cm],
        ))
    else:
        elements.append(Paragraph(_hebrew("אין הדרכות רשומות."), body))
    elements.append(PageBreak())

    # --- Section 5: Open documents ------------------------------------------
    elements.append(Paragraph(_hebrew("4. ליקויי בטיחות פתוחים"), h2))
    open_docs = [d for d in documents if d.get("status") in ("open", "in_progress")]
    if open_docs:
        rows = []
        for d in open_docs:
            rows.append([
                d.get("title", ""),
                CATEGORY_HE.get(d.get("category", ""), d.get("category", "")),
                SEVERITY_HE.get(d.get("severity", ""), ""),
                DOC_STATUS_HE.get(d.get("status", ""), d.get("status", "")),
                d.get("location", ""),
                _fmt_date(d.get("found_at")),
            ])
        elements.append(_table(
            ["כותרת", "קטגוריה", "חומרה", "סטטוס", "מיקום", "תאריך"],
            rows, [4 * cm, 3 * cm, 2 * cm, 2 * cm, 3 * cm, 3 * cm],
        ))
    else:
        elements.append(Paragraph(_hebrew("אין ליקויים פתוחים."), body))
    elements.append(Spacer(1, 6 * mm))

    # --- Section 6: Corrective tasks ----------------------------------------
    elements.append(Paragraph(_hebrew("5. משימות מתקנות"), h2))
    if tasks:
        rows = []
        for tk in tasks:
            assignee = user_map.get(tk.get("assignee_id", ""), "")
            rows.append([
                tk.get("title", ""),
                TASK_STATUS_HE.get(tk.get("status", ""), tk.get("status", "")),
                SEVERITY_HE.get(tk.get("severity", ""), ""),
                assignee,
                _fmt_date(tk.get("due_at")) or "—",
                _fmt_date(tk.get("completed_at")) or "—",
            ])
        elements.append(_table(
            ["כותרת", "סטטוס", "חומרה", "אחראי", "יעד", "הושלם"],
            rows, [4 * cm, 2.5 * cm, 2 * cm, 3 * cm, 2.5 * cm, 3 * cm],
        ))
    else:
        elements.append(Paragraph(_hebrew("אין משימות מתקנות."), body))
    elements.append(PageBreak())

    # --- Section 7: Incidents -----------------------------------------------
    elements.append(Paragraph(_hebrew("6. אירועי בטיחות"), h2))
    if incidents:
        worker_name_map = {w["id"]: w.get("full_name", "") for w in workers}
        rows = []
        for inc in incidents:
            rows.append([
                INCIDENT_TYPE_HE.get(inc.get("incident_type", ""), inc.get("incident_type", "")),
                SEVERITY_HE.get(inc.get("severity", ""), ""),
                _fmt_date(inc.get("occurred_at")),
                inc.get("location", ""),
                worker_name_map.get(inc.get("injured_worker_id", ""), ""),
                "כן" if inc.get("reported_to_authority") else "לא",
            ])
        elements.append(_table(
            ["סוג", "חומרה", "תאריך", "מיקום", "עובד נפגע", "דווח לרשות"],
            rows, [3 * cm, 2 * cm, 2.5 * cm, 3 * cm, 3.5 * cm, 3 * cm],
        ))
    else:
        elements.append(Paragraph(_hebrew("אין אירועי בטיחות רשומים."), body))
    elements.append(Spacer(1, 6 * mm))

    # --- Section 8: Statistical summary -------------------------------------
    elements.append(Paragraph(_hebrew("7. סיכום סטטיסטי"), h2))
    by_category = {}
    for d in documents:
        cat = d.get("category", "other")
        by_category[cat] = by_category.get(cat, 0) + 1
    if by_category:
        rows = [
            [CATEGORY_HE.get(cat, cat), str(cnt)]
            for cat, cnt in sorted(by_category.items(), key=lambda x: -x[1])
        ]
        elements.append(_table(["קטגוריה", "סה״כ ליקויים"], rows, [10 * cm, 6 * cm]))
    else:
        elements.append(Paragraph(_hebrew("אין נתונים לסיכום."), body))
    elements.append(Spacer(1, 4 * mm))
    summary_lines = [
        f"סה״כ עובדים: {len(workers)}",
        f"סה״כ הדרכות: {len(trainings)}",
        f"סה״כ ליקויים: {len(documents)}",
        f"סה״כ משימות: {len(tasks)}",
        f"סה״כ אירועים: {len(incidents)}",
    ]
    for line in summary_lines:
        elements.append(Paragraph(_hebrew(line), body))
    elements.append(Spacer(1, 8 * mm))

    # --- Section 9: Signature / footer --------------------------------------
    elements.append(Paragraph(_hebrew("8. אישור והפקה"), h2))
    elements.append(Paragraph(
        _hebrew(f"דו״ח זה הופק אוטומטית מתוך מערכת BrikOps בתאריך {today}."),
        body,
    ))
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(_hebrew("חתימת ממונה הבטיחות:"), body))
    elements.append(Spacer(1, 14 * mm))
    sig_line = Table([[""]], colWidths=[8 * cm], rowHeights=[0.4 * mm])
    sig_line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SLATE_700)]))
    sig_line.hAlign = "RIGHT"
    elements.append(sig_line)
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(_hebrew("שם, תאריך וחתימה"), sub))

    # --- Section 9 footer (page numbers via canvas hook would be ideal) ----
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(_hebrew("9. נוצר באמצעות BrikOps · brikops.com"), sub))

    doc.build(elements)
    output.seek(0)
    return output.getvalue()
