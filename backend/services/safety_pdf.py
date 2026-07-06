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

    # Rubik-Bold has historically shipped as a Latin-only subset (~47KB) with NO
    # Hebrew glyphs, so every bold heading rendered as tofu boxes. reportlab does
    # NOT reliably override an already-registered font NAME (verified — a second
    # registerFont under the same name is ignored), so we must pick the correct
    # file BEFORE registering rather than register-then-fallback. Inspect glyph
    # coverage with TTFontFile (always available, no fontTools dependency) and
    # register the right file ONCE under "Rubik-Bold" so no downstream code
    # (which hardcodes the name "Rubik-Bold") needs to change.
    from reportlab.pdfbase.ttfonts import TTFontFile

    _dejavu_bold = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    def _has_hebrew(path):
        try:
            return 0x05D0 in TTFontFile(path).charToGlyph
        except Exception as e:
            logger.warning(f"[SAFETY-PDF] glyph inspect failed for {path}: {e}")
            return False

    bold_path = bold
    if not _has_hebrew(bold_path):
        if os.path.exists(_dejavu_bold) and _has_hebrew(_dejavu_bold):
            bold_path = _dejavu_bold
            logger.warning("[SAFETY-PDF] Rubik-Bold lacks Hebrew — using DejaVuSans-Bold")
        else:
            bold_path = regular
            logger.warning("[SAFETY-PDF] No Hebrew bold available — aliasing bold to regular")
    try:
        pdfmetrics.registerFont(TTFont("Rubik-Bold", bold_path))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] Failed to register Rubik-Bold at {bold_path}: {e}")
        try:
            pdfmetrics.registerFont(TTFont("Rubik-Bold", regular))
        except Exception as e2:
            logger.warning(f"[SAFETY-PDF] Bold alias to regular failed: {e2}")

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


# Brand palette used by the canvas layer (header band + footer credit).
_NAVY_HEX = "#1E293B"
_SLATE400_HEX = "#94A3B8"


def _load_brikops_logo():
    """BrikOps logo bundled with the backend (fonts/ ships on EB). Fail-soft."""
    from reportlab.lib.utils import ImageReader
    try:
        p = os.path.join(_FONTS_DIR, "brikops-logo.png")
        if os.path.exists(p):
            return ImageReader(p)
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] BrikOps logo load failed: {e}")
    return None


async def _load_client_logo(db, org_id):
    """Client org logo from org.logo_url (S3 key) → presigned → bytes. Fail-soft."""
    if not org_id:
        return None
    try:
        org = await db.organizations.find_one({"id": org_id}, {"_id": 0, "logo_url": 1})
        key = (org or {}).get("logo_url")
        if not key:
            return None
        from services.object_storage import generate_url
        from reportlab.lib.utils import ImageReader
        url = generate_url(key)
        if not url:
            return None
        if str(url).startswith("http"):
            import requests
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200 and resp.content:
                return ImageReader(io.BytesIO(resp.content))
        elif os.path.exists(str(url)):
            return ImageReader(str(url))
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] client logo load failed: {e}")
    return None


async def _load_signature_image(ref):
    """Tour signature PNG (permanent S3 key) → presigned URL → io.BytesIO for
    the platypus Image flowable (Image() rejects ImageReader in reportlab 4.4.x);
    fail-soft None.
    Also serves failed-item evidence photos (same permanent-key → BytesIO shape).
    PER-IMAGE fail-soft (modeled on _load_client_logo): ANY failure returns
    None so the caller falls back to a name-only row and the PDF still renders.
    A single unreachable image must never abort the whole report."""
    if not ref:
        return None
    try:
        from services.object_storage import generate_url
        url = generate_url(ref)
        if not url:
            return None
        if str(url).startswith("http"):
            import requests
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200 and resp.content:
                return io.BytesIO(resp.content)
        elif os.path.exists(str(url)):
            with open(str(url), "rb") as f:
                return io.BytesIO(f.read())
    except Exception as e:
        logger.warning(f"[SAFETY-PDF] tour signature load failed: {e}")
    return None


class _NumberedCanvas:
    """
    Two-pass page-X-of-Y footer canvas. Buffers each page's state during
    the first build pass, then stamps the true total-page count on every
    page during save() (reportlab's standard idiom for X/Y footers).
    """

    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen import canvas as _canvas_mod
        self._canvas_cls = _canvas_mod.Canvas
        self._canvas = _canvas_mod.Canvas(*args, **kwargs)
        self._saved_states = []
        self._brikops_logo = None
        self._client_logo = None

    def __getattr__(self, name):
        return getattr(self._canvas, name)

    def showPage(self):
        self._saved_states.append(self._canvas.__dict__.copy())
        self._canvas._startPage()

    def save(self):
        total = len(self._saved_states)
        for state in self._saved_states:
            self._canvas.__dict__.update(state)
            self._draw_header(self._canvas.getPageNumber())
            self._draw_footer(total)
            self._canvas_cls.showPage(self._canvas)
        self._canvas.save()

    def _draw_header(self, page):
        """Navy brand band on every page: BrikOps logo (right/leading in RTL),
        client logo (left/trailing, fail-soft), centered wordmark on the cover."""
        from reportlab.lib.colors import HexColor, white
        c = self._canvas
        W, H = 595.27, 841.89
        band_h = 74.0          # ~26mm; sits inside the 30mm topMargin
        logo_h = 40.0          # ~14mm, aspect-preserved
        c.saveState()
        c.setFillColor(HexColor(_NAVY_HEX))
        c.rect(0, H - band_h, W, band_h, fill=1, stroke=0)
        cy = H - band_h + (band_h - logo_h) / 2.0

        bl = getattr(self, "_brikops_logo", None)
        if bl is not None:
            try:
                iw, ih = bl.getSize()
                w = logo_h * (iw / float(ih)) if ih else logo_h
                c.drawImage(bl, W - 18 - w, cy, width=w, height=logo_h,
                            mask="auto", preserveAspectRatio=True)
            except Exception:
                pass

        cl = getattr(self, "_client_logo", None)
        if cl is not None:
            try:
                iw, ih = cl.getSize()
                w = logo_h * (iw / float(ih)) if ih else logo_h
                c.drawImage(cl, 18, cy, width=w, height=logo_h,
                            mask="auto", preserveAspectRatio=True)
            except Exception:
                pass

        if page == 1:
            c.setFillColor(white)
            try:
                c.setFont("Rubik-Bold", 13)
            except Exception:
                c.setFont("Helvetica-Bold", 13)
            c.drawCentredString(W / 2.0, H - band_h / 2.0 - 5, hebrew("פנקס כללי — בטיחות"))
        c.restoreState()

    def _draw_footer(self, total):
        from reportlab.lib.colors import HexColor
        c = self._canvas
        page = c.getPageNumber()
        c.saveState()
        try:
            c.setFont("Rubik", 8)
        except Exception:
            c.setFont("Helvetica", 8)
        # A4 width = 595.27 pts; 28.35 pts ~= 1 cm
        text = hebrew(f"עמוד {page} מתוך {total}")
        c.drawCentredString(595.27 / 2.0, 28.35, text)
        c.setFillColor(HexColor(_SLATE400_HEX))
        try:
            c.setFont("Rubik", 7)
        except Exception:
            c.setFont("Helvetica", 7)
        c.drawCentredString(595.27 / 2.0, 42.0, hebrew("נוצר באמצעות BrikOps · brikops.com"))
        c.restoreState()


def _make_canvas(*args, **kwargs):
    """Factory used as SimpleDocTemplate(..., canvasmaker=_make_canvas)."""
    return _NumberedCanvas(*args, **kwargs)


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
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak, HRFlowable
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
    # Split into defects (ליקויים) and observations (תיעוד) — one collection,
    # kind discriminator. Legacy docs (no kind) count as defects.
    defects = [d for d in documents if d.get("kind") != "observation"]
    observations = [d for d in documents if d.get("kind") == "observation"]

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

    # Management team: PM role + safety_officer sub_role (Part 3a)
    memberships = await db.project_memberships.find(
        {
            "project_id": project_id,
            "deletedAt": None,
            "$or": [
                {"role": {"$in": ["project_manager", "management_team"]}},
                {"sub_role": "safety_officer"},
            ],
        },
        {"_id": 0, "user_id": 1, "role": 1, "sub_role": 1},
    ).to_list(length=100)

    mgmt_user_ids = list({m["user_id"] for m in memberships if m.get("user_id")})
    mgmt_users: dict = {}
    if mgmt_user_ids:
        for u in await db.users.find(
            {"id": {"$in": mgmt_user_ids}},
            {"_id": 0, "id": 1, "name": 1, "phone": 1, "email": 1},
        ).to_list(length=100):
            mgmt_users[u["id"]] = u

    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    GREY_HDR = colors.HexColor("#E5E7EB")
    NAVY = colors.HexColor("#1E293B")     # header band + table header
    ORANGE = colors.HexColor("#F97316")   # BrikOps accent rules
    SLATE_50 = colors.HexColor("#F8FAFC")  # zebra + cover panel

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
    cell_hdr_white = ParagraphStyle(
        "RCellHdrW", parent=cell_hdr, textColor=colors.white,
    )

    def _table(headers, rows, col_widths):
        # RTL: reportlab lays column 0 LEFTMOST; call sites pass columns in
        # logical Hebrew reading order, so reverse headers, every row and the
        # widths ONCE here so the first logical column renders RIGHTMOST.
        data = [[Paragraph(hebrew(h), cell_hdr_white) for h in reversed(headers)]]
        for r in rows:
            data.append([Paragraph(hebrew(c), cell) for c in reversed(list(r))])
        t = Table(data, colWidths=list(reversed(col_widths)), repeatRows=1)
        t.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_50]),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def _section(title):
        """Section header + a 2pt orange accent rule beneath it."""
        return [
            Paragraph(hebrew(title), h2),
            HRFlowable(width="100%", thickness=2, color=ORANGE,
                       spaceBefore=1, spaceAfter=6, lineCap="round"),
        ]

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=3.0 * cm, bottomMargin=2.4 * cm,
        title="פנקס כללי - בטיחות",
    )
    elems = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Section 1: Cover — centered title block on a light rounded panel
    project_name = project.get("name", "")
    cover_lines = [f"פרויקט: {project_name}"]
    if project.get("client_name"):
        cover_lines.append(f"לקוח: {project['client_name']}")
    if project.get("address"):
        cover_lines.append(f"כתובת: {project['address']}")
    cover_lines.append(f"תאריך הפקה: {today}")

    panel_rows = [[Paragraph(hebrew("פנקס כללי - בטיחות בעבודה"), title_style)]]
    for line in cover_lines:
        panel_rows.append([Paragraph(hebrew(line), sub)])
    cover_panel = Table(panel_rows, colWidths=[16 * cm])
    cover_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    elems.append(Spacer(1, 6 * mm))
    elems.append(cover_panel)
    elems.append(Spacer(1, 8 * mm))

    # Section 2: Project metadata table
    elems.extend(_section("1. פרטי הפרויקט"))
    meta_rows = [
        ["שם פרויקט", project_name or "—"],
        ["מזהה פרויקט", project_id],
        ["לקוח", project.get("client_name", "—") or "—"],
        ["כתובת", project.get("address", "—") or "—"],
        ["תאריך הפקת הפנקס", today],
    ]
    elems.append(_table(["שדה", "ערך"], meta_rows, [5 * cm, 11 * cm]))
    elems.append(Spacer(1, 6 * mm))

    # Section 2: Management Team (Part 3a)
    elems.extend(_section("2. צוות ניהולי"))
    MGMT_ROLE_HE = {
        "project_manager": "מנהל פרויקט",
        "management_team": "צוות ניהולי",
    }
    if memberships:
        mgmt_rows = []
        for m in memberships:
            u = mgmt_users.get(m.get("user_id", ""), {})
            role_label = MGMT_ROLE_HE.get(m.get("role", ""), m.get("role", ""))
            if m.get("sub_role") == "safety_officer":
                role_label = "ממונה בטיחות"
            mgmt_rows.append([
                u.get("name", "") or "—",
                role_label,
                u.get("phone", "") or "—",
                u.get("email", "") or "—",
            ])
        elems.append(_table(
            ["שם", "תפקיד", "טלפון", "אימייל"],
            mgmt_rows, [4 * cm, 4 * cm, 3.5 * cm, 4.5 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין צוות ניהולי רשום לפרויקט."), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 3: Workers (NO id_number)
    elems.extend(_section("3. רשימת עובדים"))
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
    elems.extend(_section("4. הדרכות בטיחות"))
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
    elems.extend(_section("5. ליקויי בטיחות פתוחים"))
    open_docs = [d for d in defects if d.get("status") in ("open", "in_progress")]
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

    # Section 5b: Observations (תיעוד) — archival, no status filter
    doc_sub_h = ParagraphStyle(
        "RH3docs", fontName="Rubik-Bold", fontSize=11,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=15,
        spaceBefore=6, spaceAfter=3,
    )
    elems.append(Paragraph(hebrew("5ב. תיעוד"), doc_sub_h))
    if observations:
        rows = []
        for d in observations:
            rows.append([
                d.get("title", ""),
                CATEGORY_HE.get(d.get("category", ""), d.get("category", "")),
                d.get("location", "") or "—",
                _fmt_date(d.get("found_at")),
            ])
        elems.append(_table(
            ["כותרת", "קטגוריה", "מיקום", "תאריך"],
            rows, [5 * cm, 3.5 * cm, 3.5 * cm, 3 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין רשומות תיעוד."), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 6: Corrective tasks
    elems.extend(_section("6. משימות מתקנות"))
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
    elems.extend(_section("7. אירועי בטיחות"))
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
    elems.extend(_section("8. סיכום סטטיסטי"))
    by_category = {}
    for d in defects:
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
        f"סה״כ ליקויים: {len(defects)}",
        f"סה״כ רשומות תיעוד: {len(observations)}",
        f"סה״כ משימות: {len(tasks)}",
        f"סה״כ אירועים: {len(incidents)}",
    ):
        elems.append(Paragraph(hebrew(line), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 8b: Audit trail (last 30 days) — sub-block under section 8 (Part 3a)
    sub_h = ParagraphStyle(
        "RH3", fontName="Rubik-Bold", fontSize=11,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=15,
        spaceBefore=6, spaceAfter=3,
    )
    elems.append(Paragraph(hebrew("תיעוד פעולות (30 ימים אחרונים)"), sub_h))
    cutoff_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    audit_events = await db.audit_events.find(
        {"entity_type": {"$regex": "^safety"}, "created_at": {"$gte": cutoff_30d},
         "payload.project_id": project_id},
        {"_id": 0, "entity_type": 1, "action": 1, "created_at": 1, "actor_id": 1},
    ).sort("created_at", -1).limit(50).to_list(length=50)
    actor_ids = list({ev.get("actor_id") for ev in audit_events if ev.get("actor_id")})
    actor_map = {}
    if actor_ids:
        for u in await db.users.find(
            {"id": {"$in": actor_ids}}, {"_id": 0, "id": 1, "name": 1}
        ).to_list(length=200):
            actor_map[u["id"]] = u.get("name", "")
    if audit_events:
        rows = []
        for ev in audit_events:
            rows.append([
                _fmt_date(ev.get("created_at")),
                ev.get("entity_type", ""),
                ev.get("action", ""),
                actor_map.get(ev.get("actor_id"), "") or (ev.get("actor_id", "")[:8] if ev.get("actor_id") else "—"),
            ])
        elems.append(_table(
            ["תאריך", "ישות", "פעולה", "מבצע"],
            rows, [3 * cm, 4 * cm, 5 * cm, 4 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("אין פעולות בתקופה זו."), body))
    elems.append(PageBreak())

    # Section 9: Work-manager declaration + 3 signature lines
    elems.extend(_section("9. הצהרת מנהל העבודה וחתימות"))
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

    brikops_logo = _load_brikops_logo()
    client_logo = await _load_client_logo(db, project.get("org_id"))

    def make_canvas(*a, **k):
        cv = _NumberedCanvas(*a, **k)
        cv._brikops_logo = brikops_logo
        cv._client_logo = client_logo
        return cv

    doc.build(elems, canvasmaker=make_canvas)
    out.seek(0)
    return out.getvalue()


# =====================================================================
# Safety Tour Report PDF (Batch 4c 2026-07-06)
# Per-tour report: header, per-item results, failed-item defect refs, and
# the 3-slot signature block. Any tour status is exportable. Reuses the
# same fonts / brand canvas / _table conventions as generate_safety_register.
# =====================================================================

_TOUR_TYPE_HE = {
    "officer_monthly": "דוח ממונה בטיחות",
    "assistant_morning": "דוח עוזר בטיחות — בוקר",
    "assistant_evening": "דוח עוזר בטיחות — ערב",
    "custom": "סיור מותאם",
}
_TOUR_STATUS_HE = {"draft": "טיוטה", "pending_signature": "ממתין לחתימה", "signed": "חתום"}
_TOUR_RESULT_HE = {"pass": "תקין", "fail": "נכשל", "na": "לא רלוונטי"}
_SUB_ROLE_HE = {
    "safety_officer": "ממונה בטיחות",
    "safety_assistant": "עוזר בטיחות",
    "work_manager": "מנהל עבודה",
    "project_manager": "מנהל פרויקט",
    "management_team": "צוות ניהולי",
}


async def generate_tour_report(db, project_id: str, tour_id: str) -> bytes:
    """Build the per-tour safety report PDF for `tour_id`.

    Exportable at ANY status (draft / pending_signature / signed). PII fields
    are never selected. Signature images are loaded per-image fail-soft.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, HRFlowable, Image
    )

    _register_fonts_once()

    project = await db.projects.find_one({"id": project_id}, {"_id": 0}) or {}
    tour = await db.safety_tours.find_one(
        {"id": tour_id, "project_id": project_id, "deletedAt": None}, {"_id": 0}
    ) or {}
    items = tour.get("items") or []

    creator_name = None
    if tour.get("created_by"):
        u = await db.users.find_one({"id": tour["created_by"]}, {"_id": 0, "name": 1})
        creator_name = (u or {}).get("name")

    # Failed-item defect titles (fail-soft — a missing defect just drops the ref).
    defect_ids = [it.get("defect_id") for it in items if it.get("defect_id")]
    defect_title_map: dict = {}
    if defect_ids:
        for d in await db.safety_documents.find(
            {"id": {"$in": defect_ids}}, {"_id": 0, "id": 1, "title": 1}
        ).to_list(length=10000):
            defect_title_map[d["id"]] = d.get("title", "")

    # Pre-load canvas signature images (per-image fail-soft) BEFORE the sync build.
    slot_defs = [
        ("work_manager", "מנהל עבודה *", True),
        ("safety_assistant", "עוזר בטיחות *", True),
        ("safety_officer", "ממונה בטיחות", False),
    ]
    sig_images: dict = {}
    for slot, _lbl, _mand in slot_defs:
        sig = tour.get(f"{slot}_signature")
        if sig and sig.get("signature_type") == "canvas" and sig.get("signature_ref"):
            sig_images[slot] = await _load_signature_image(sig.get("signature_ref"))

    # Pre-load failed-item evidence photos (per-image fail-soft) BEFORE the sync
    # build. Only failed items carry photos; a broken key is silently skipped and
    # an item with zero loadable photos gets no photo row (never an error).
    fail_photos: dict = {}          # item_id → [BytesIO, ...]
    for it in items:
        if it.get("result") == "fail" and it.get("photo_urls"):
            loaded = []
            for ref in it["photo_urls"]:
                img = await _load_signature_image(ref)
                if img is not None:
                    loaded.append(img)
            if loaded:
                fail_photos[it.get("id")] = loaded

    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    NAVY = colors.HexColor("#1E293B")
    ORANGE = colors.HexColor("#F97316")
    SLATE_50 = colors.HexColor("#F8FAFC")
    RED_700 = colors.HexColor("#B91C1C")

    title_style = ParagraphStyle(
        "TTitle", fontName="Rubik-Bold", fontSize=20,
        alignment=TA_CENTER, textColor=SLATE_700, leading=26,
    )
    h2 = ParagraphStyle(
        "TH2", fontName="Rubik-Bold", fontSize=13,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=18,
        spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "TBody", fontName="Rubik", fontSize=10,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=14,
    )
    sub = ParagraphStyle(
        "TSub", fontName="Rubik", fontSize=9,
        alignment=TA_CENTER, textColor=SLATE_500, leading=12,
    )
    cell = ParagraphStyle(
        "TCell", fontName="Rubik", fontSize=9,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=12,
    )
    cell_hdr_white = ParagraphStyle(
        "TCellHdrW", fontName="Rubik-Bold", fontSize=9,
        alignment=TA_RIGHT, textColor=colors.white, leading=12,
    )

    def _table(headers, rows, col_widths):
        # RTL: reverse headers/rows/widths ONCE so logical col 0 renders rightmost.
        data = [[Paragraph(hebrew(h), cell_hdr_white) for h in reversed(headers)]]
        for r in rows:
            data.append([Paragraph(hebrew(c), cell) for c in reversed(list(r))])
        t = Table(data, colWidths=list(reversed(col_widths)), repeatRows=1)
        t.setStyle(TableStyle([
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_50]),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return t

    def _section(t):
        return [
            Paragraph(hebrew(t), h2),
            HRFlowable(width="100%", thickness=2, color=ORANGE,
                       spaceBefore=1, spaceAfter=6, lineCap="round"),
        ]

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=3.0 * cm, bottomMargin=2.4 * cm,
        title="דוח סיור בטיחות",
    )
    elems = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    ttype = tour.get("tour_type", "")
    type_label = _TOUR_TYPE_HE.get(ttype, ttype)
    if ttype == "custom" and tour.get("custom_name"):
        type_label = tour["custom_name"]

    # Cover panel
    cover_lines = [f"סוג סיור: {type_label}"]
    if project.get("name"):
        cover_lines.append(f"פרויקט: {project['name']}")
    cover_lines.append(f"תאריך סיור: {_fmt_date(tour.get('tour_date'))}")
    cover_lines.append(f"סטטוס: {_TOUR_STATUS_HE.get(tour.get('status'), tour.get('status', '—'))}")
    if creator_name:
        cover_lines.append(f"נוצר על ידי: {creator_name}")
    cover_lines.append(f"תאריך הפקה: {today}")

    panel_rows = [[Paragraph(hebrew("דוח סיור בטיחות"), title_style)]]
    for line in cover_lines:
        panel_rows.append([Paragraph(hebrew(line), sub)])
    cover_panel = Table(panel_rows, colWidths=[16 * cm])
    cover_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SLATE_50),
        ("BOX", (0, 0), (-1, -1), 0.5, SLATE_200),
        ("ROUNDEDCORNERS", [10, 10, 10, 10]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    elems.append(Spacer(1, 6 * mm))
    elems.append(cover_panel)
    elems.append(Spacer(1, 8 * mm))

    # Section 1: item results
    elems.extend(_section("1. תוצאות הסיור"))
    if items:
        item_rows = []
        for it in items:
            item_rows.append([
                it.get("label", "") or "—",
                CATEGORY_HE.get(it.get("category", ""), it.get("category", "") or "—"),
                _TOUR_RESULT_HE.get(it.get("result"), "—"),
                it.get("note", "") or "—",
            ])
        elems.append(_table(
            ["פריט", "קטגוריה", "תוצאה", "הערה"],
            item_rows, [5.5 * cm, 3.5 * cm, 2.5 * cm, 4.5 * cm],
        ))
    else:
        elems.append(Paragraph(hebrew("לא הוזנו פריטים בסיור זה."), body))
    elems.append(Spacer(1, 6 * mm))

    # Section 2: failed items (only when any exist)
    failed = [it for it in items if it.get("result") == "fail"]
    if failed:
        elems.extend(_section("2. ליקויים שנמצאו"))
        fail_style = ParagraphStyle(
            "TFail", fontName="Rubik", fontSize=10,
            alignment=TA_RIGHT, textColor=RED_700, leading=15,
        )
        for it in failed:
            label = it.get("label", "") or "—"
            elems.append(Paragraph(hebrew(f"• {label}"), fail_style))
            did = it.get("defect_id")
            if did and did in defect_title_map:
                elems.append(Paragraph(
                    hebrew(f"נפתח ליקוי: {defect_title_map[did] or did}"), body))
            if it.get("note"):
                elems.append(Paragraph(hebrew(f"הערה: {it['note']}"), body))
            iid = it.get("id")
            if iid in fail_photos:
                imgs = [Image(b, width=4 * cm, height=3 * cm, kind='proportional')
                        for b in fail_photos[iid]]
                for chunk in [imgs[i:i + 4] for i in range(0, len(imgs), 4)]:
                    pt = Table([chunk], colWidths=[4.4 * cm] * len(chunk), hAlign="RIGHT")
                    pt.setStyle(TableStyle([
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 2),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                        ("TOPPADDING", (0, 0), (-1, -1), 2),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    ]))
                    elems.append(pt)
                elems.append(Spacer(1, 2 * mm))
            elems.append(Spacer(1, 3 * mm))
        elems.append(Spacer(1, 4 * mm))

    # Section: signatures (3 fixed slots)
    sec_num = "3" if failed else "2"
    elems.extend(_section(f"{sec_num}. חתימות"))

    sig_rows = []
    for slot, slot_label, mandatory in slot_defs:
        sig = tour.get(f"{slot}_signature")
        if sig:
            stype = sig.get("signature_type")
            if stype == "canvas" and sig_images.get(slot) is not None:
                sig_cell = Image(sig_images[slot], width=3.2 * cm, height=1.2 * cm)
            elif stype == "canvas":
                sig_cell = Paragraph(hebrew("חתימה גרפית"), cell)
            elif stype == "typed":
                tn = sig.get("typed_name") or sig.get("name") or ""
                sig_cell = Paragraph(hebrew(f"חתימה מוקלדת: {tn}"), cell)
            else:
                sig_cell = Paragraph(hebrew("נחתם"), cell)
            name_bits = [sig.get("name", "") or "—"]
            if sig.get("sub_role"):
                name_bits.append(f"({_SUB_ROLE_HE.get(sig['sub_role'], sig['sub_role'])})")
            name_cell = Paragraph(hebrew(" ".join(name_bits)), cell)
            date_cell = Paragraph(hebrew(_fmt_date(sig.get("signed_at"))), cell)
        else:
            sig_cell = Paragraph(
                hebrew("טרם נחתם" if mandatory else "לא נחתם (אופציונלי)"), cell)
            name_cell = Paragraph(hebrew("—"), cell)
            date_cell = Paragraph(hebrew("—"), cell)
        role_cell = Paragraph(hebrew(slot_label), cell)
        # logical order: תפקיד | חתימה | חותם | תאריך → reversed for RTL
        sig_rows.append(list(reversed([role_cell, sig_cell, name_cell, date_cell])))

    hdr = [Paragraph(hebrew(h), cell_hdr_white)
           for h in reversed(["תפקיד", "חתימה", "חותם", "תאריך"])]
    sig_widths = list(reversed([4 * cm, 4.5 * cm, 4.5 * cm, 3 * cm]))
    sig_table = Table([hdr] + sig_rows, colWidths=sig_widths, repeatRows=1)
    sig_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SLATE_50]),
        ("GRID", (0, 0), (-1, -1), 0.3, SLATE_200),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(sig_table)
    elems.append(Spacer(1, 4 * mm))
    elems.append(Paragraph(hebrew("* חתימת חובה"), sub))

    elems.append(Spacer(1, 6 * mm))
    elems.append(Paragraph(hebrew("נוצר באמצעות BrikOps · brikops.com"), sub))

    brikops_logo = _load_brikops_logo()
    client_logo = await _load_client_logo(db, project.get("org_id"))

    def make_canvas(*a, **k):
        cv = _NumberedCanvas(*a, **k)
        cv._brikops_logo = brikops_logo
        cv._client_logo = client_logo
        return cv

    doc.build(elems, canvasmaker=make_canvas)
    out.seek(0)
    return out.getvalue()


# =====================================================================
# Safety Project Registration PDF (Batch S2A 2026-05-04)
# Israeli Ministry of Economy "פנקס הקבלנים" format.
# Uses 'Rubik' / 'Rubik-Bold' fonts (registered at module top, lines 40,44)
# and hebrew() helper (imported at line 21) for proper RTL/bidi rendering.
# =====================================================================

def _today_iso() -> str:
    from datetime import datetime
    return datetime.now().strftime("%d/%m/%Y")


def _draw_field(c, width, y, label: str, value):
    """Draws "label: value" right-aligned for RTL Hebrew."""
    from reportlab.lib.units import cm
    val = value if value not in (None, "") else "—"
    c.drawRightString(width - 2 * cm, y, hebrew(f"{label}: {val}"))


def generate_registration_pdf(registration: dict, project: dict) -> bytes:
    """Generate the formal Israeli safety project registration PDF.
    Layout matches Ministry of Economy 'פנקס הקבלנים' template:
      - Cover with project name + date
      - Section 1: כללי (developer, contractor, registry number)
      - Section 2: מען המשרד
      - Section 3: מנהלים (repeat group)
      - Footer: permit number + form 4 target date
    """
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    _register_fonts_once()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Title
    c.setFont('Rubik-Bold', 18)
    project_name = project.get('name', '') if project else ''
    c.drawRightString(width - 2 * cm, height - 2 * cm,
                      hebrew(f"רישומי זיהוי — {project_name}"))

    # Date
    c.setFont('Rubik', 10)
    c.drawRightString(width - 2 * cm, height - 3 * cm,
                      hebrew(f"תאריך הפקה: {_today_iso()}"))

    y = height - 5 * cm

    # Section 1 — כללי
    c.setFont('Rubik-Bold', 14)
    c.drawRightString(width - 2 * cm, y, hebrew("1. כללי"))
    y -= 0.8 * cm
    c.setFont('Rubik', 11)
    _draw_field(c, width, y, "שם היזם", registration.get("developer_name"))
    y -= 0.6 * cm
    _draw_field(c, width, y, "שם המבצע", registration.get("main_contractor_name"))
    y -= 0.6 * cm
    _draw_field(c, width, y, "מספר רישום בפנקס הקבלנים",
                registration.get("contractor_registry_number"))

    y -= 1 * cm

    # Section 2 — מען
    c.setFont('Rubik-Bold', 14)
    c.drawRightString(width - 2 * cm, y, hebrew("2. מען המשרד הראשי / המשרד הרשום"))
    y -= 0.8 * cm
    c.setFont('Rubik', 11)
    addr = registration.get("office_address") or {}
    _draw_field(c, width, y, "הישוב", addr.get("city")); y -= 0.6 * cm
    _draw_field(c, width, y, "רחוב / ת.ד", addr.get("street")); y -= 0.6 * cm
    _draw_field(c, width, y, "מס' בית", addr.get("house_number")); y -= 0.6 * cm
    _draw_field(c, width, y, "מיקוד", addr.get("postal_code")); y -= 0.6 * cm
    _draw_field(c, width, y, "דואר אלקטרוני", addr.get("email")); y -= 0.6 * cm
    _draw_field(c, width, y, "טלפון", addr.get("phone")); y -= 0.6 * cm
    _draw_field(c, width, y, "נייד", addr.get("mobile")); y -= 0.6 * cm
    _draw_field(c, width, y, "פקס", addr.get("fax"))

    y -= 1.2 * cm

    # Section 3 — מנהלים
    c.setFont('Rubik-Bold', 14)
    c.drawRightString(width - 2 * cm, y, hebrew("3. מנהלי החברה / האגודה / השותפות"))
    y -= 0.8 * cm
    c.setFont('Rubik', 11)
    managers = registration.get("managers") or []
    if not managers:
        c.drawRightString(width - 2 * cm, y, hebrew("(לא הוזנו מנהלים)"))
    else:
        for i, mgr in enumerate(managers, 1):
            c.setFont('Rubik-Bold', 12)
            c.drawRightString(width - 2 * cm, y, hebrew(f"מנהל #{i}"))
            y -= 0.5 * cm
            c.setFont('Rubik', 11)
            full = f"{mgr.get('first_name', '')} {mgr.get('last_name', '')}".strip()
            _draw_field(c, width, y, "שם מלא", full or None); y -= 0.5 * cm
            _draw_field(c, width, y, "ת.ז (מוסתרת)", mgr.get("id_number")); y -= 0.5 * cm
            _draw_field(c, width, y, "מען", mgr.get("address")); y -= 0.7 * cm

    # Footer (permit + form 4) near bottom
    y = 2 * cm
    c.setFont('Rubik', 10)
    _draw_field(c, width, y, "מספר היתר בנייה",
                registration.get("permit_number"))
    _draw_field(c, width, y - 0.5 * cm, "תאריך יעד טופס 4",
                registration.get("form_4_target_date"))

    c.showPage()
    c.save()
    return buffer.getvalue()
