"""
Work Diary (יומן עבודה) PDF generator — batch diary-d3 + diary-d4a.

Public API:
  • `async generate_work_diary_pdf(db, project_id, entry_id) -> bytes`
       one signed-or-draft entry (d3).
  • `async generate_work_diary_monthly_pdf(db, project_id, month) -> bytes`
       consolidated SIGNED-only entries for YYYY-MM, one per page (d4a Part 1).

MODEL: services/safety_pdf.py generate_tour_report. All shared plumbing is
IMPORTED from safety_pdf (fonts, logos, generic image loader, X-of-Y canvas)
— nothing reimplemented here per the D3 do-not-touch list.

The per-entry flowable story is built ONCE in `_entry_story` and reused by both
generators, so the single-entry visual output is byte-identical (V4 regression
guard) and the monthly PDF renders the SAME entry layout per page.

Legal-deliverable posture:
  • Unsigned (draft) → a diagonal "טיוטה — לא חתום" watermark on EVERY page,
    so an unsigned print can never masquerade as final. The MONTHLY PDF is
    signed-only, so it never carries the watermark.
  • entered_late → a red "⚠ הוזן באיחור" line in the entry cover panel (always)
    PLUS a header-band stamp on page 1 (single-entry export ONLY — in the
    monthly doc page 1 is the month cover, so the band stamp is suppressed and
    the per-entry cover-panel line carries the late signal instead).
  • Photos + signature images are per-image fail-soft: the try/except wraps
    the Image(...) CONSTRUCTION (corrupt bytes raise UnidentifiedImageError
    at construction on reportlab 4.4.x — sandbox-verified 2026-07-09), never
    just the byte fetch. One bad image never aborts the report.
"""
import io
import logging
import re
from datetime import datetime, timezone

from services.pdf_service import hebrew
from services.safety_pdf import (
    _NumberedCanvas,
    _fmt_date,
    _load_brikops_logo,
    _load_client_logo,
    _load_signature_image,
    _register_fonts_once,
    INCIDENT_TYPE_HE,
    _TOUR_TYPE_HE,
    _TOUR_STATUS_HE,
)
# THE shared safety-ref pattern — the SAME compiled object used by the write
# gates (work_diary_router / safety.workers). Here it is the SSRF READ gate:
# the generic loader HTTP-fetches refs that generate_url passes through as
# http(s) URLs, so ONLY storage keys shaped like the safety-upload output for
# THIS project may reach it (batch d4a fold-in 2e — was a duplicated local
# re.compile, now single-source to make byte-drift impossible).
from contractor_ops.upload_safety import SAFETY_STORED_REF_RE

logger = logging.getLogger(__name__)

_WEEKDAYS_HE = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
# python weekday(): Monday=0 … Sunday=6 → Hebrew names aligned to that order.

_STATUS_HE = {"draft": "טיוטה", "signed": "חתום"}


def _weekday_he(diary_date: str) -> str:
    try:
        d = datetime.strptime(diary_date, "%Y-%m-%d")
        return f"יום {_WEEKDAYS_HE[d.weekday()]}"
    except Exception:
        return ""


def _safe_int(v) -> int:
    """Coerce a workers-count cell to int; anything non-numeric → 0. A direct-API
    entry with count="abc" must never 500 the export (batch d4a fold-in 2b)."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


class _DiaryCanvas(_NumberedCanvas):
    """The shared X-of-Y canvas with a diary header band: same navy band +
    logos. The page-1 wordmark is `_wordmark` (default "יומן עבודה"; the
    monthly generator overrides it), with an optional red "הוזן באיחור" stamp
    and a diagonal draft watermark on every page (both opt-in per document)."""

    def _draw_header(self, page):
        from reportlab.lib.colors import Color, HexColor, white
        c = self._canvas
        W, H = 595.27, 841.89
        band_h = 74.0
        logo_h = 40.0
        c.saveState()
        c.setFillColor(HexColor("#1E293B"))
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
            wordmark = getattr(self, "_wordmark", "יומן עבודה")
            c.drawCentredString(W / 2.0, H - band_h / 2.0 - 5, hebrew(wordmark))
            if getattr(self, "_late_stamp", False):
                try:
                    c.setFont("Rubik-Bold", 10)
                except Exception:
                    c.setFont("Helvetica-Bold", 10)
                c.setFillColor(HexColor("#B91C1C"))
                c.setStrokeColor(HexColor("#B91C1C"))
                text = hebrew("הוזן באיחור")
                tw = c.stringWidth(text, c._fontname, 10)
                bx, by = 18, H - band_h - 22
                c.roundRect(bx, by - 5, tw + 16, 20, 4, fill=0, stroke=1)
                c.drawString(bx + 8, by, text)
        c.restoreState()

        # Draft watermark — EVERY page, so no single printed page of an
        # unsigned diary can pass as final.
        if getattr(self, "_draft_watermark", False):
            c.saveState()
            try:
                c.setFont("Rubik-Bold", 54)
            except Exception:
                c.setFont("Helvetica-Bold", 54)
            c.setFillColor(Color(0.72, 0.11, 0.11, alpha=0.13))
            c.translate(W / 2.0, H / 2.0)
            c.rotate(35)
            c.drawCentredString(0, 0, hebrew("טיוטה — לא חתום"))
            c.restoreState()


# =====================================================================
# Async media pre-loaders (must run BEFORE the sync platypus build)
# =====================================================================
async def _load_entry_signature(entry: dict):
    """Return the signature image bytes (BytesIO) for a canvas signature, else
    None. Fail-soft: a missing/failed load renders as the typed/graphic
    fallback in the signature block."""
    sig = entry.get("worker_signature") or None
    if sig and sig.get("signature_type") == "canvas" and sig.get("signature_ref"):
        return await _load_signature_image(sig.get("signature_ref"))
    return None


async def _load_entry_photos(project_id: str, entry: dict) -> list:
    """Return [BytesIO, ...] for the entry's photo_refs. SSRF gate: only refs
    shaped like the safety upload output for THIS project reach the loader;
    each load is fail-soft (None dropped)."""
    photo_bytes = []
    for ref in (entry.get("photo_refs") or []):
        m = SAFETY_STORED_REF_RE.match(ref or "")
        if not m or m.group(1) != project_id or ".." in ref:
            logger.warning("work_diary_pdf: skipping unsafe photo ref %r", ref)
            continue
        b = await _load_signature_image(ref)   # generic loader; fail-soft None
        if b is not None:
            photo_bytes.append(b)
    return photo_bytes


# =====================================================================
# The per-entry flowable story (shared by both generators)
# =====================================================================
def _entry_story(project: dict, entry: dict, photo_bytes: list, sig_img_bytes) -> list:
    """Build the full flowable list for ONE diary entry — cover panel through
    the brand footer. Byte-identical to the pre-d4a single-entry body (V4
    regression guard). `photo_bytes` / `sig_img_bytes` are pre-loaded async by
    the caller. Self-contained: styles are built here so the monthly generator
    can call it per page."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
    )

    is_draft = entry.get("status") != "signed"
    sig = entry.get("worker_signature") or None

    # ---- Styles (tour-report palette) ----
    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    NAVY = colors.HexColor("#1E293B")
    ORANGE = colors.HexColor("#F97316")
    SLATE_50 = colors.HexColor("#F8FAFC")
    RED_700 = colors.HexColor("#B91C1C")

    title_style = ParagraphStyle(
        "WTitle", fontName="Rubik-Bold", fontSize=20,
        alignment=TA_CENTER, textColor=SLATE_700, leading=26,
    )
    h2 = ParagraphStyle(
        "WH2", fontName="Rubik-Bold", fontSize=13,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=18,
        spaceBefore=8, spaceAfter=4,
    )
    body = ParagraphStyle(
        "WBody", fontName="Rubik", fontSize=10,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=14,
    )
    sub = ParagraphStyle(
        "WSub", fontName="Rubik", fontSize=9,
        alignment=TA_CENTER, textColor=SLATE_500, leading=12,
    )
    cell = ParagraphStyle(
        "WCell", fontName="Rubik", fontSize=9,
        alignment=TA_RIGHT, textColor=SLATE_700, leading=12,
    )
    cell_hdr_white = ParagraphStyle(
        "WCellHdrW", fontName="Rubik-Bold", fontSize=9,
        alignment=TA_RIGHT, textColor=colors.white, leading=12,
    )
    red_note = ParagraphStyle(
        "WRed", fontName="Rubik-Bold", fontSize=10,
        alignment=TA_CENTER, textColor=RED_700, leading=14,
    )

    def _table(headers, rows, col_widths):
        # RTL: reverse ONCE so logical col 0 renders rightmost (house idiom).
        data = [[Paragraph(hebrew(h), cell_hdr_white) for h in reversed(headers)]]
        for r in rows:
            data.append([Paragraph(hebrew(str(c) if c is not None else "—"), cell)
                         for c in reversed(list(r))])
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

    elems = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    diary_date = entry.get("diary_date", "")

    # ---- Cover panel ----
    cover_lines = []
    if project.get("name"):
        cover_lines.append(f"פרויקט: {project['name']}")
    wd = _weekday_he(diary_date)
    cover_lines.append(f"תאריך: {diary_date}" + (f" ({wd})" if wd else ""))
    cover_lines.append(f"סטטוס: {_STATUS_HE.get(entry.get('status'), entry.get('status', '—'))}")
    if entry.get("no_work"):
        reason = (entry.get("no_work_reason") or "").strip()
        cover_lines.append("לא בוצעה עבודה" + (f" — {reason}" if reason else ""))
    cover_lines.append(f"תאריך הפקה: {today}")

    panel_rows = [[Paragraph(hebrew("יומן עבודה יומי"), title_style)]]
    for line in cover_lines:
        panel_rows.append([Paragraph(hebrew(line), sub)])
    if entry.get("entered_late"):
        panel_rows.append([Paragraph(hebrew("⚠ הוזן באיחור"), red_note)])
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

    # ---- Sections (batch order; empties skipped) ----
    weather = entry.get("weather") or {}
    if weather.get("desc"):
        elems.extend(_section("מזג אוויר"))
        elems.append(Paragraph(hebrew(weather["desc"]), body))
        elems.append(Spacer(1, 4 * mm))

    workers = entry.get("workers_by_company") or []
    if workers:
        elems.extend(_section("עובדים באתר"))
        total = sum(_safe_int(w.get("count")) for w in workers)
        elems.append(_table(
            ["חברה / קבוצה", "מספר עובדים"],
            [[w.get("company_name") or "ללא חברה", _safe_int(w.get("count"))] for w in workers],
            [10 * cm, 4 * cm],
        ))
        elems.append(Spacer(1, 1.5 * mm))
        elems.append(Paragraph(hebrew(f"סה\u05f4כ עובדים: {total}"), body))
        elems.append(Spacer(1, 4 * mm))

    subs = entry.get("subcontractors") or []
    if subs:
        elems.extend(_section("קבלני משנה"))
        names = [s.get("name") or s.get("company_name") or "—" for s in subs]
        elems.append(Paragraph(hebrew(" · ".join(names)), body))
        elems.append(Spacer(1, 4 * mm))

    equipment = entry.get("equipment_list") or []
    if equipment:
        elems.extend(_section("ציוד באתר"))
        eq_lines = []
        for eq in equipment:
            label = eq.get("name") or " · ".join(
                x for x in [eq.get("internal_code"), eq.get("category")] if x) or "—"
            eq_lines.append(label)
        elems.append(Paragraph(hebrew(" · ".join(eq_lines)), body))
        elems.append(Spacer(1, 4 * mm))

    if (entry.get("work_description") or "").strip():
        elems.extend(_section("תיאור עבודות"))
        for para in entry["work_description"].splitlines():
            if para.strip():
                elems.append(Paragraph(hebrew(para), body))
        elems.append(Spacer(1, 4 * mm))

    materials = entry.get("materials") or []
    if materials:
        elems.extend(_section("חומרים שהגיעו"))
        elems.append(Paragraph(hebrew(" · ".join(str(m) for m in materials)), body))
        elems.append(Spacer(1, 4 * mm))

    incidents = entry.get("incidents_summary") or []
    if incidents:
        elems.extend(_section("אירועי בטיחות"))
        for it in incidents:
            t = INCIDENT_TYPE_HE.get(it.get("incident_type"), it.get("incident_type") or "")
            line = " — ".join(x for x in [t, it.get("description")] if x) or "—"
            elems.append(Paragraph(hebrew(f"• {line}"), body))
        elems.append(Spacer(1, 4 * mm))

    tours = entry.get("tours_summary") or []
    if tours:
        elems.extend(_section("סיורים"))
        for t in tours:
            tt = _TOUR_TYPE_HE.get(t.get("tour_type"), t.get("tour_type") or "")
            ts = _TOUR_STATUS_HE.get(t.get("status"), t.get("status") or "")
            elems.append(Paragraph(hebrew(f"• {' · '.join(x for x in [tt, ts] if x) or '—'}"), body))
        elems.append(Spacer(1, 4 * mm))

    trainings = entry.get("trainings_summary") or []
    if trainings:
        elems.extend(_section("הדרכות"))
        for tr in trainings:
            line = " — ".join(x for x in [tr.get("worker_name"), tr.get("training_type")] if x) or "—"
            elems.append(Paragraph(hebrew(f"• {line}"), body))
        elems.append(Spacer(1, 4 * mm))

    dc = entry.get("defect_counts")
    if isinstance(dc, dict) and (dc.get("opened") or dc.get("closed")):
        elems.extend(_section("ליקויים"))
        elems.append(Paragraph(
            hebrew(f"נפתחו {dc.get('opened') or 0} · נסגרו {dc.get('closed') or 0}"), body))
        elems.append(Spacer(1, 4 * mm))

    iv = entry.get("inspector_visit") or {}
    iv_line = " · ".join(x for x in [iv.get("visitor"), iv.get("checked"), iv.get("notes")] if x)
    if iv_line:
        elems.extend(_section("ביקורת מפקח"))
        elems.append(Paragraph(hebrew(iv_line), body))
        elems.append(Spacer(1, 4 * mm))

    if (entry.get("special_instructions") or "").strip():
        elems.extend(_section("הוראות מיוחדות"))
        for para in entry["special_instructions"].splitlines():
            if para.strip():
                elems.append(Paragraph(hebrew(para), body))
        elems.append(Spacer(1, 4 * mm))

    # ---- Photos (per-image fail-soft AT CONSTRUCTION — sandbox-verified) ----
    if photo_bytes:
        imgs = []
        for b in photo_bytes:
            try:
                imgs.append(Image(b, width=5 * cm, height=4 * cm, kind='proportional'))
            except Exception as e:
                logger.warning(f"[DIARY-PDF] photo Image() construction failed (skipped): {e}")
        if imgs:
            elems.extend(_section("תמונות"))
            for chunk in [imgs[i:i + 3] for i in range(0, len(imgs), 3)]:
                pt = Table([chunk], colWidths=[5.6 * cm] * len(chunk), hAlign="RIGHT")
                pt.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                elems.append(pt)
            elems.append(Spacer(1, 4 * mm))

    # ---- Signature block ----
    elems.extend(_section("חתימת מנהל העבודה"))
    if sig:
        sig_cell_flow = None
        if sig.get("signature_type") == "canvas" and sig_img_bytes is not None:
            try:
                sig_cell_flow = Image(sig_img_bytes, width=3.2 * cm, height=1.2 * cm)
            except Exception as e:
                logger.warning(f"[DIARY-PDF] signature Image() construction failed: {e}")
        if sig_cell_flow is None:
            if sig.get("signature_type") == "typed":
                sig_cell_flow = Paragraph(
                    hebrew(f"(חתימה מוקלדת) {sig.get('typed_name') or ''}"), cell)
            else:
                sig_cell_flow = Paragraph(hebrew("חתימה גרפית"), cell)
        name_cell = Paragraph(hebrew(sig.get("name") or "—"), cell)
        date_cell = Paragraph(hebrew(_fmt_date(sig.get("signed_at"))), cell)
        hdr = [Paragraph(hebrew(h), cell_hdr_white)
               for h in reversed(["חותם", "חתימה", "תאריך"])]
        row = list(reversed([name_cell, sig_cell_flow, date_cell]))
        st = Table([hdr, row], colWidths=list(reversed([6 * cm, 5 * cm, 3 * cm])))
        st.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("GRID", (0, 0), (-1, -1), 0.3, SLATE_200),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elems.append(st)
    else:
        elems.append(Paragraph(hebrew("טיוטה — לא חתום"), red_note))
    elems.append(Spacer(1, 4 * mm))

    # ---- Addendums ----
    addendums = entry.get("addendums") or []
    if addendums:
        elems.extend(_section("תוספות"))
        for a in addendums:
            when = _fmt_date(a.get("created_at"))
            elems.append(Paragraph(hebrew(f"• {a.get('text') or ''}"), body))
            if when:
                elems.append(Paragraph(hebrew(f"נוסף בתאריך {when}"), sub))
            elems.append(Spacer(1, 1.5 * mm))
        elems.append(Spacer(1, 2 * mm))

    elems.append(Spacer(1, 4 * mm))
    elems.append(Paragraph(hebrew("נוצר באמצעות BrikOps · brikops.com"), sub))
    return elems


async def generate_work_diary_pdf(db, project_id: str, entry_id: str) -> bytes:
    """Build the work-diary PDF for one entry. Any status is exportable —
    a draft carries the watermark. Empty sections are skipped."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate

    _register_fonts_once()

    project = await db.projects.find_one({"id": project_id}, {"_id": 0}) or {}
    entry = await db.work_diary_entries.find_one(
        {"id": entry_id, "project_id": project_id, "deletedAt": None}, {"_id": 0}
    ) or {}

    is_draft = entry.get("status") != "signed"

    # ---- Pre-load ALL images (async) BEFORE the sync platypus build ----
    sig_img_bytes = await _load_entry_signature(entry)
    photo_bytes = await _load_entry_photos(project_id, entry)

    brikops_logo = _load_brikops_logo()
    client_logo = await _load_client_logo(db, project.get("org_id"))

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=3.0 * cm, bottomMargin=2.4 * cm,
        title="יומן עבודה",
    )
    elems = _entry_story(project, entry, photo_bytes, sig_img_bytes)

    def make_canvas(*a, **k):
        cv = _DiaryCanvas(*a, **k)
        cv._brikops_logo = brikops_logo
        cv._client_logo = client_logo
        cv._late_stamp = bool(entry.get("entered_late"))
        cv._draft_watermark = is_draft
        return cv

    doc.build(elems, canvasmaker=make_canvas)
    out.seek(0)
    return out.getvalue()


async def generate_work_diary_monthly_pdf(db, project_id: str, month: str) -> bytes:
    """Consolidated monthly PDF: ALL SIGNED entries for `month` (YYYY-MM),
    ascending by date, one entry per page after a month cover. Signed-only, so
    no draft watermark; the per-entry late signal rides the cover-panel line
    (the header band stamp is single-export-only). The caller (router) is
    responsible for the empty-month 404 and month-format 422; this guards empty
    defensively by still producing a cover-only document."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
    )

    _register_fonts_once()

    project = await db.projects.find_one({"id": project_id}, {"_id": 0}) or {}
    entries = await db.work_diary_entries.find(
        {"project_id": project_id, "deletedAt": None, "status": "signed",
         "diary_date": {"$regex": f"^{re.escape(month)}"}},
        {"_id": 0},
    ).sort("diary_date", 1).to_list(400)

    brikops_logo = _load_brikops_logo()
    client_logo = await _load_client_logo(db, project.get("org_id"))

    SLATE_700 = colors.HexColor("#334155")
    SLATE_500 = colors.HexColor("#64748B")
    SLATE_200 = colors.HexColor("#E2E8F0")
    SLATE_50 = colors.HexColor("#F8FAFC")

    title_style = ParagraphStyle(
        "MTitle", fontName="Rubik-Bold", fontSize=22,
        alignment=TA_CENTER, textColor=SLATE_700, leading=28,
    )
    sub = ParagraphStyle(
        "MSub", fontName="Rubik", fontSize=11,
        alignment=TA_CENTER, textColor=SLATE_500, leading=16,
    )

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cover_lines = []
    if project.get("name"):
        cover_lines.append(f"פרויקט: {project['name']}")
    cover_lines.append(f"חודש: {month}")
    cover_lines.append(f"מספר רשומות חתומות: {len(entries)}")
    cover_lines.append(f"תאריך הפקה: {today}")

    panel_rows = [[Paragraph(hebrew("יומן עבודה — סיכום חודשי"), title_style)]]
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
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
    ]))

    elems = [Spacer(1, 40 * mm), cover_panel]

    for i, entry in enumerate(entries):
        # Pre-load THIS entry's media (async) before the sync story build.
        sig_img_bytes = await _load_entry_signature(entry)
        photo_bytes = await _load_entry_photos(project_id, entry)
        elems.append(PageBreak())
        elems.extend(_entry_story(project, entry, photo_bytes, sig_img_bytes))

    out = io.BytesIO()
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=3.0 * cm, bottomMargin=2.4 * cm,
        title="יומן עבודה — חודשי",
    )

    def make_canvas(*a, **k):
        cv = _DiaryCanvas(*a, **k)
        cv._brikops_logo = brikops_logo
        cv._client_logo = client_logo
        cv._late_stamp = False        # month page 1 is the cover, not an entry
        cv._draft_watermark = False   # signed-only document
        cv._wordmark = "יומן עבודה — חודשי"
        return cv

    doc.build(elems, canvasmaker=make_canvas)
    out.seek(0)
    return out.getvalue()
