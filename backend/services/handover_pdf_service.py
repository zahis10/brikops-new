import os
import io
import re
import asyncio
import base64
import logging
import time
from datetime import datetime
from typing import Optional
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger("contractor_ops.handover_pdf")

_BACKEND_DIR = Path(__file__).parent.parent
_TEMPLATES_DIR = _BACKEND_DIR / "templates"
_FONTS_DIR = _BACKEND_DIR / "fonts"

_BRIKOPS_LOGO_PATH = _BACKEND_DIR / "static" / "logo.png"
try:
    _raw_logo = _BRIKOPS_LOGO_PATH.read_bytes()
    try:
        from PIL import Image as _PILImage
        _pil = _PILImage.open(io.BytesIO(_raw_logo))
        if _pil.width > 400:
            _ratio = 400 / _pil.width
            _pil = _pil.resize((400, int(_pil.height * _ratio)), _PILImage.LANCZOS)
        _buf = io.BytesIO()
        _pil.save(_buf, format='PNG', optimize=True)
        _raw_logo = _buf.getvalue()
    except Exception:
        pass
    _BRIKOPS_LOGO_B64 = "data:image/png;base64," + base64.b64encode(_raw_logo).decode()
except (OSError, IOError):
    _BRIKOPS_LOGO_B64 = ""

_IMAGE_FETCH_TIMEOUT = 5
_MAX_IMAGE_WIDTH = 300
_PHOTO_THUMB_WIDTH = 150
_JPEG_QUALITY = 65

_b64_cache = {}
_B64_CACHE_TTL = 900

HARDCODED_PROPERTY_LABELS = {
    "address": "כתובת",
    "building": "בניין",
    "floor": "קומה",
    "apartment": "דירה",
    "rooms": "חדרים",
    "parking": "חניה",
    "storage": "מחסן",
    "storage_num": "מספר מחסנים",
    "parking_num": "מספר חניות",
    "model": "דגם",
    "area": "שטח דירה",
    "balcony_area": "שטח מרפסת",
    "parking_area": "שטח חניה",
    "laundry_area": "שטח מרפסת שירות",
}

DEFAULT_SIGNATURE_LABELS = {
    "manager": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כמנהל/ת הפרויקט",
    "tenant": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כרוכש/ת ראשי/ת",
    "tenant_2": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כרוכש/ת נוסף/ת",
    "contractor_rep": "אני מאשר/ת את חתימתי על פרוטוקול המסירה כנציג/ת הקבלן",
}

STATUS_LABELS = {
    "ok": "תקין",
    "partial": "חלקי",
    "defective": "לא תקין",
    "not_relevant": "לא רלוונטי",
    "not_checked": "לא נבדק",
}

STATUS_COLORS = {
    "ok": "#16a34a",
    "partial": "#d97706",
    "defective": "#dc2626",
    "not_relevant": "#9ca3af",
    "not_checked": "#e5e7eb",
}

STATUS_BG_COLORS = {
    "ok": "#DCFCE7",
    "partial": "#FEF3C7",
    "defective": "#FEE2E2",
    "not_relevant": "#F1F5F9",
    "not_checked": "#F1F5F9",
}

STATUS_TEXT_COLORS = {
    "ok": "#166534",
    "partial": "#92400e",
    "defective": "#991b1b",
    "not_relevant": "#64748b",
    "not_checked": "#94a3b8",
}

SEVERITY_LABELS = {
    "critical": "קריטי",
    "normal": "רגיל",
    "cosmetic": "קוסמטי",
}

SEVERITY_COLORS = {
    "critical": "#dc2626",
    "normal": "#d97706",
    "cosmetic": "#6b7280",
}

HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}


def _format_hebrew_date(dt_str: Optional[str]) -> str:
    if not dt_str:
        return ""
    try:
        if isinstance(dt_str, datetime):
            dt = dt_str
        else:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        month_name = HEBREW_MONTHS.get(dt.month, str(dt.month))
        return f"{dt.day} ב{month_name} {dt.year}"
    except Exception:
        return str(dt_str)[:10]


def _format_short_date(dt_obj: Optional[datetime] = None) -> str:
    if dt_obj is None:
        dt_obj = datetime.now()
    return f"{dt_obj.day:02d}.{dt_obj.month:02d}.{dt_obj.year}"


def _sanitize_filename(text: str) -> str:
    if not text:
        return "unknown"
    ascii_safe = re.sub(r'[^\w\-.]', '_', text)
    ascii_safe = re.sub(r'_+', '_', ascii_safe).strip('_')
    return ascii_safe or "unknown"


async def _fetch_image_as_base64(url: str, session=None, max_width=None) -> Optional[str]:
    if not url:
        return None
    try:
        import aiohttp
        if session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=_IMAGE_FETCH_TIMEOUT)) as resp:
                if resp.status != 200:
                    logger.warning(f"[PDF] Image fetch failed: {url} status={resp.status}")
                    return None
                data = await resp.read()
        else:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=_IMAGE_FETCH_TIMEOUT)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.read()

        data = _resize_image(data, max_width=max_width)
        content_type = "image/jpeg"
        if data[:4] == b'\x89PNG':
            content_type = "image/png"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        logger.warning(f"[PDF] Image fetch error: {url} -> {e}")
        return None


def _resize_image(data: bytes, max_width=None) -> bytes:
    if max_width is None:
        max_width = _MAX_IMAGE_WIDTH
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        if img.width > max_width:
            ratio = max_width / img.width
            new_h = int(img.height * ratio)
            img = img.resize((max_width, new_h), Image.LANCZOS)
        if img.mode == 'RGBA':
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3])
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=_JPEG_QUALITY, optimize=True)
        return buf.getvalue()
    except Exception:
        return data


def _local_image_to_base64(file_path: str) -> Optional[str]:
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'rb') as f:
            data = f.read()
        if file_path.endswith('.png'):
            ct = 'image/png'
        else:
            ct = 'image/jpeg'
        return f"data:{ct};base64,{base64.b64encode(data).decode('ascii')}"
    except Exception:
        return None


async def _fetch_local_or_remote_image(stored_ref: str, session=None, max_width=None) -> Optional[str]:
    if not stored_ref:
        return None

    now = time.time()
    cache_key = f"{stored_ref}:{max_width or 'default'}"
    cached = _b64_cache.get(cache_key)
    if cached and (now - cached[1]) < _B64_CACHE_TTL:
        return cached[0]

    from services.object_storage import generate_url

    result = None
    if stored_ref.startswith("s3://"):
        url = generate_url(stored_ref)
        result = await _fetch_image_as_base64(url, session, max_width=max_width)
    elif stored_ref.startswith("/api/uploads/"):
        rel_path = stored_ref[len("/api/uploads/"):]
        uploads_root = (_BACKEND_DIR / "uploads").resolve()
        local_path = (uploads_root / rel_path).resolve()
        if not str(local_path).startswith(str(uploads_root)):
            logger.warning(f"[PDF] Path traversal blocked: {stored_ref}")
            return None
        result = _local_image_to_base64(str(local_path))
    else:
        logger.debug(f"[PDF] Ignoring unrecognized image ref: {stored_ref[:60]}")
        return None

    if result:
        if len(_b64_cache) > 500:
            cutoff = now - _B64_CACHE_TTL
            expired = [k for k, v in _b64_cache.items() if v[1] < cutoff]
            for k in expired:
                del _b64_cache[k]
        _b64_cache[cache_key] = (result, now)

    return result


async def generate_handover_pdf(protocol: dict, db) -> bytes:
    try:
        from weasyprint import HTML
        use_weasyprint = True
    except (ImportError, OSError) as e:
        logger.warning(f"[PDF] WeasyPrint not available: {e}. Using fallback.")
        use_weasyprint = False

    context = await _build_template_context(protocol, db)

    jinja_env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    template = jinja_env.get_template("handover_protocol_pdf.html")
    html_content = template.render(**context)

    if use_weasyprint:
        pdf_bytes = HTML(string=html_content, base_url=str(_BACKEND_DIR)).write_pdf()
    else:
        try:
            from xhtml2pdf import pisa
            logger.warning("[PDF] Using xhtml2pdf fallback — fonts, RTL, and page counters may not render correctly")
            result_buf = io.BytesIO()
            pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=result_buf)
            if pisa_status.err:
                logger.error(f"[PDF] xhtml2pdf errors: {pisa_status.err}")
            pdf_bytes = result_buf.getvalue()
        except ImportError:
            raise RuntimeError("PDF generation requires WeasyPrint (production) or xhtml2pdf. Neither is available in this environment.")

    return pdf_bytes


async def _build_template_context(protocol: dict, db) -> dict:
    import aiohttp

    snapshot = protocol.get("snapshot", {})
    sections = protocol.get("sections", [])
    signatures = protocol.get("signatures", {})
    if isinstance(signatures, list):
        signatures = {}

    protocol_type = protocol.get("type", "initial")

    display_number = protocol.get("display_number")
    protocol_id = protocol.get("id", "")
    if display_number:
        display_number_str = str(display_number)
    else:
        display_number_str = protocol_id[:8] if protocol_id else ""

    signed_at_str = protocol.get("signed_at", protocol.get("updated_at", ""))
    signed_date = _format_hebrew_date(signed_at_str)
    generation_date = _format_short_date()

    property_schema = protocol.get("property_fields_schema")
    property_details = protocol.get("property_details", {}) or {}

    if property_schema and isinstance(property_schema, list):
        property_rows = []
        for field in property_schema:
            key = field.get("key", "")
            label = field.get("label", key)
            value = property_details.get(key, "")
            if value:
                property_rows.append({"label": label, "value": value})
    else:
        property_rows = []
        for key, label in HARDCODED_PROPERTY_LABELS.items():
            value = property_details.get(key, "")
            if value:
                property_rows.append({"label": label, "value": value})

    tenants = protocol.get("tenants", [])
    tenants_data = [t for t in tenants if t.get("name")]

    defect_ids = []
    for sec in sections:
        for item in sec.get("items", []):
            did = item.get("defect_id")
            if did:
                defect_ids.append(did)

    defect_map = {}
    if defect_ids:
        cursor = db.tasks.find({"id": {"$in": defect_ids}}, {"_id": 0, "id": 1, "proof_urls": 1, "severity": 1, "description": 1})
        async for task_doc in cursor:
            defect_map[task_doc["id"]] = task_doc

    image_keys = []

    logo_url = snapshot.get("company_logo_url")
    if logo_url:
        image_keys.append(("logo", logo_url))

    for role in ("manager", "tenant", "tenant_2", "contractor_rep"):
        sig = signatures.get(role, {})
        if sig and sig.get("type") == "canvas" and sig.get("image_key"):
            image_keys.append((f"sig_{role}", sig["image_key"]))

    item_photo_map = {}
    photo_counter = 0
    for sec in sections:
        for item in sec.get("items", []):
            # Source of truth: task.proof_urls (primary, updated on upload).
            # Fallback: item.photos (legacy/cached copy for pre-fix data).
            item_photos = item.get("photos", [])
            defect_id = item.get("defect_id")
            if defect_id and defect_id in defect_map:
                defect_doc = defect_map[defect_id]
                defect_photos = defect_doc.get("proof_urls", [])
                if defect_photos:
                    item_photos = defect_photos

            if item_photos and item.get("status") in ("defective", "partial"):
                for photo_ref in item_photos[:3]:
                    key_name = f"photo_{photo_counter}"
                    image_keys.append((key_name, photo_ref))
                    item_key = f"{sec.get('section_id', '')}_{item.get('item_id', '')}"
                    if item_key not in item_photo_map:
                        item_photo_map[item_key] = []
                    item_photo_map[item_key].append(key_name)
                    photo_counter += 1

    meters = protocol.get("meters") or {}
    meter_photo_keys = {}
    for meter_type in ("water", "electricity"):
        meter_data = meters.get(meter_type) or {}
        photo_url = meter_data.get("photo_url")
        if photo_url:
            key_name = f"meter_{meter_type}_photo"
            image_keys.append((key_name, photo_url))
            meter_photo_keys[meter_type] = key_name

    legal_sections_raw = protocol.get("legal_sections", [])
    legal_section_image_keys = {}
    for ls_idx, ls in enumerate(legal_sections_raw):
        sigs_obj = ls.get("signatures") or {}
        for slot in ("tenant", "tenant_2"):
            slot_sig = sigs_obj.get(slot)
            if slot_sig and isinstance(slot_sig, dict) and slot_sig.get("type") == "canvas" and slot_sig.get("image_key"):
                key_name = f"legal_sig_{ls_idx}_{slot}"
                image_keys.append((key_name, slot_sig["image_key"]))
                legal_section_image_keys[(ls_idx, slot)] = key_name
        sig = ls.get("signature")
        if sig and isinstance(sig, dict) and sig.get("type") == "canvas" and sig.get("image_key"):
            key_name = f"legal_sig_{ls_idx}"
            image_keys.append((key_name, sig["image_key"]))
            legal_section_image_keys[ls_idx] = key_name

    images = {}
    if image_keys:
        async with aiohttp.ClientSession() as session:
            fetch_tasks = []
            for key_name, stored_ref in image_keys:
                is_photo = key_name.startswith("photo_")
                mw = _PHOTO_THUMB_WIDTH if is_photo else None
                fetch_tasks.append(_fetch_local_or_remote_image(stored_ref, session, max_width=mw))

            results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for i, (key_name, _) in enumerate(image_keys):
                result = results[i]
                if isinstance(result, Exception):
                    logger.warning(f"[PDF] Image fetch failed for {key_name}: {result}")
                    images[key_name] = None
                else:
                    images[key_name] = result

    inspection_sections = []
    all_defects = []
    global_ok = global_fail = global_partial = 0

    for sec in sections:
        sec_items = []
        sec_ok = sec_fail = sec_partial = sec_na = 0
        all_not_checked = True
        all_not_relevant = True

        for idx, item in enumerate(sec.get("items", []), 1):
            status = item.get("status", "not_checked")
            if status not in (None, "", "not_checked"):
                all_not_checked = False
            if status != "not_relevant":
                all_not_relevant = False

            item_key = f"{sec.get('section_id', '')}_{item.get('item_id', '')}"
            photo_keys = item_photo_map.get(item_key, [])
            photo_b64s = [images.get(pk) for pk in photo_keys]

            defect_id = item.get("defect_id")
            description = item.get("notes", "")
            severity = None

            if defect_id and defect_id in defect_map:
                defect_doc = defect_map[defect_id]
                if not description:
                    description = defect_doc.get("description", "")
                severity = defect_doc.get("severity")

            if not severity and status in ("defective", "partial"):
                severity = item.get("severity", "normal")

            item_data = {
                "num": idx,
                "name": item.get("name", ""),
                "trade": item.get("trade", ""),
                "status": status,
                "status_label": STATUS_LABELS.get(status, status),
                "status_color": STATUS_COLORS.get(status, "#e5e7eb"),
                "status_bg": STATUS_BG_COLORS.get(status, "#F1F5F9"),
                "status_text_color": STATUS_TEXT_COLORS.get(status, "#64748b"),
                "description": description,
                "severity": severity,
                "severity_label": SEVERITY_LABELS.get(severity, "") if severity else "",
                "severity_color": SEVERITY_COLORS.get(severity, "#6b7280") if severity else "",
                "photos": photo_b64s,
            }
            sec_items.append(item_data)

            if status == "ok": sec_ok += 1
            elif status == "defective": sec_fail += 1
            elif status == "partial": sec_partial += 1
            elif status == "not_relevant": sec_na += 1

            if status in ("defective", "partial"):
                all_defects.append({
                    "section_name": sec.get("name", ""),
                    "item_name": item.get("name", ""),
                    "trade": item.get("trade", ""),
                    "severity": severity,
                    "severity_label": SEVERITY_LABELS.get(severity, "") if severity else "",
                    "severity_color": SEVERITY_COLORS.get(severity, "#6b7280") if severity else "",
                    "description": description,
                })

        global_ok += sec_ok
        global_fail += sec_fail
        global_partial += sec_partial

        is_collapsed = all_not_checked or all_not_relevant
        collapsed_reason = "not_checked" if all_not_checked else ("not_relevant" if all_not_relevant else None)

        inspection_sections.append({
            "name": sec.get("name", ""),
            "items": sec_items,
            "total": len(sec_items),
            "ok": sec_ok,
            "fail": sec_fail,
            "partial": sec_partial,
            "na": sec_na,
            "collapsed": is_collapsed,
            "collapsed_reason": collapsed_reason,
        })

    stats_total = global_ok + global_fail + global_partial

    delivered_items = protocol.get("delivered_items", [])
    delivered_data = [
        {"num": i + 1, "name": d.get("name", ""), "quantity": d.get("quantity", ""), "notes": d.get("notes", "")}
        for i, d in enumerate(delivered_items) if d.get("name")
    ]
    has_any_quantity = any(d.get("quantity") for d in delivered_data)

    legal_sections = []
    for ls_idx, ls in enumerate(legal_sections_raw):
        sigs_obj = ls.get("signatures") or {}
        sig = ls.get("signature")
        is_dual = ls.get("requires_both_tenants", False)

        ls_data = {
            "title": ls.get("title", ""),
            "body": ls.get("body", ""),
            "edited": ls.get("edited", False),
            "requires_signature": ls.get("requires_signature", False),
            "is_dual": is_dual,
            "signers": [],
        }

        if is_dual and sigs_obj:
            for slot, label in [("tenant", "רוכש/ת ראשי/ת"), ("tenant_2", "רוכש/ת נוסף/ת")]:
                slot_sig = sigs_obj.get(slot)
                if slot_sig and isinstance(slot_sig, dict) and slot_sig.get("signed_at"):
                    signer_entry = {
                        "label": label,
                        "signer_name": slot_sig.get("signer_name", ""),
                        "signed_at": _format_hebrew_date(slot_sig.get("signed_at")),
                        "sig_type": slot_sig.get("type", ""),
                        "typed_name": slot_sig.get("typed_name", ""),
                        "sig_image_b64": images.get(legal_section_image_keys.get((ls_idx, slot))),
                    }
                    ls_data["signers"].append(signer_entry)

        if not ls_data["signers"] and sig and isinstance(sig, dict):
            signer_entry = {
                "label": "",
                "signer_name": ls.get("signer_name", ""),
                "signed_at": _format_hebrew_date(ls.get("signed_at")),
                "sig_type": sig.get("type", ""),
                "typed_name": sig.get("typed_name", ""),
                "sig_image_b64": images.get(legal_section_image_keys.get(ls_idx)),
            }
            ls_data["signers"].append(signer_entry)

        ls_data["is_signed"] = len(ls_data["signers"]) > 0
        ls_data["signer_name"] = ls_data["signers"][0]["signer_name"] if ls_data["signers"] else ""
        ls_data["signed_at"] = ls_data["signers"][0]["signed_at"] if ls_data["signers"] else ""

        legal_sections.append(ls_data)

    valid_tenants = [t for t in (protocol.get("tenants") or []) if t and (t.get("name") or "").strip()]
    is_tenant2_required = len(valid_tenants) >= 2

    sig_labels = protocol.get("signature_labels", {}) or {}
    signature_data = {}
    for role in ("manager", "tenant", "tenant_2", "contractor_rep"):
        sig = signatures.get(role, {})
        label = sig_labels.get(role, DEFAULT_SIGNATURE_LABELS.get(role, role))
        if not sig:
            signature_data[role] = {
                "label": label,
                "type": None,
                "image_b64": None,
                "typed_name": "",
                "signer_name": "",
                "signed_at": "",
                "signed": False,
            }
            continue
        sig_type = sig.get("type", "")
        image_b64 = images.get(f"sig_{role}")
        typed_name = sig.get("typed_name", "")
        signer_name = sig.get("signer_name", "")
        signed_at = _format_hebrew_date(sig.get("signed_at"))

        signature_data[role] = {
            "label": label,
            "type": sig_type,
            "image_b64": image_b64,
            "typed_name": typed_name,
            "signer_name": signer_name,
            "signed_at": signed_at,
            "signed": True,
        }

    defect_severity_counts = {"critical": 0, "normal": 0, "cosmetic": 0}
    for d in all_defects:
        sev = d.get("severity", "normal")
        if sev in defect_severity_counts:
            defect_severity_counts[sev] += 1

    fonts_dir_str = str(_FONTS_DIR.resolve())
    if os.name == 'nt':
        fonts_dir_str = fonts_dir_str.replace('\\', '/')

    return {
        "protocol_type": protocol_type,
        "protocol_id": protocol_id,
        "display_number": display_number_str,
        "project_name": snapshot.get("project_name", ""),
        "building_name": snapshot.get("building_name", ""),
        "floor_name": snapshot.get("floor_name", ""),
        "unit_name": snapshot.get("unit_name", ""),
        "unit_number": snapshot.get("unit_number", ""),
        "company_name": snapshot.get("company_name", ""),
        "logo_b64": images.get("logo"),
        "brikops_logo_b64": _BRIKOPS_LOGO_B64,
        "signed_date": signed_date,
        "generation_date": generation_date,
        "property_rows": property_rows,
        "tenants": tenants_data,
        "inspection_sections": inspection_sections,
        "delivered_items": delivered_data,
        "has_any_quantity": has_any_quantity,
        "legal_sections": legal_sections,
        "signatures": signature_data,
        "is_tenant2_required": is_tenant2_required,
        "all_defects": all_defects,
        "total_defects": len(all_defects),
        "defect_severity_counts": defect_severity_counts,
        "stats_total": stats_total,
        "stats_ok": global_ok,
        "stats_fail": global_fail,
        "stats_partial": global_partial,
        "tenant_notes": protocol.get("tenant_notes", ""),
        "meter_water_reading": (meters.get("water") or {}).get("reading"),
        "meter_water_photo_b64": images.get(meter_photo_keys.get("water")),
        "meter_electricity_reading": (meters.get("electricity") or {}).get("reading"),
        "meter_electricity_photo_b64": images.get(meter_photo_keys.get("electricity")),
        "fonts_dir": fonts_dir_str,
    }
