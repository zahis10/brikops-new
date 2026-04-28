import re
import uuid
import logging
import calendar
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)

INVOICE_DUE_DAYS = 7
GRACE_DAYS = 7

HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרץ", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}

VALID_INVOICE_STATUSES = {'draft', 'issued', 'paid', 'past_due', 'void'}

_PERIOD_RE = re.compile(r'^(\d{4})-(0[1-9]|1[0-2])$')

_db = None


def set_invoicing_db(db):
    global _db
    _db = db


def get_db():
    if _db is None:
        raise RuntimeError("Invoicing DB not initialized")
    return _db


def _now():
    return datetime.now(timezone.utc).isoformat()


def _now_dt():
    return datetime.now(timezone.utc)


def validate_period_ym(period_ym: str) -> tuple:
    m = _PERIOD_RE.match(period_ym)
    if not m:
        raise ValueError("period_ym must be YYYY-MM with month 01-12")
    return int(m.group(1)), int(m.group(2))


def _end_of_month_utc(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)


def _compute_due_at(year: int, month: int) -> str:
    eom = _end_of_month_utc(year, month)
    due = eom + timedelta(days=INVOICE_DUE_DAYS)
    return due.isoformat()


async def ensure_indexes():
    db = get_db()
    await db.invoices.create_index(
        [('org_id', 1), ('period_ym', 1)],
        unique=True,
        name='idx_invoices_org_period_unique'
    )
    await db.invoices.create_index([('org_id', 1), ('status', 1)])
    await db.invoice_line_items.create_index([('invoice_id', 1)])


async def build_invoice_preview(org_id: str, period_ym: str) -> dict:
    year, month = validate_period_ym(period_ym)
    db = get_db()

    active_pbs = await db.project_billing.find(
        {'org_id': org_id, 'status': 'active'},
        {'_id': 0}
    ).to_list(1000)

    project_ids = [pb['project_id'] for pb in active_pbs]
    projects_map = {}
    if project_ids:
        proj_docs = await db.projects.find(
            {'id': {'$in': project_ids}},
            {'_id': 0, 'id': 1, 'name': 1, 'total_units': 1}
        ).to_list(1000)
        projects_map = {p['id']: {'name': p.get('name', ''), 'total_units': p.get('total_units')} for p in proj_docs}

    from contractor_ops.billing_plans import calculate_monthly, PRICE_PER_UNIT
    line_items = []
    total = 0
    for pb in active_pbs:
        proj_info = projects_map.get(pb['project_id'], {})
        total_units_declared = proj_info.get('total_units')

        if total_units_declared is not None and total_units_declared > 0:
            plan_id = pb.get('plan_id')
            mt = calculate_monthly(total_units_declared, plan_id=plan_id, project_index=1)
            units_for_display = total_units_declared
            price_per_unit_for_display = PRICE_PER_UNIT
        else:
            mt = pb.get('monthly_total', 0)
            units_for_display = pb.get('contracted_units', 0)
            price_per_unit_for_display = pb.get('price_per_unit', 15)

        total += mt
        line_items.append({
            'project_id': pb['project_id'],
            'project_name_snapshot': proj_info.get('name', ''),
            'plan_id_snapshot': pb.get('plan_id'),
            'tier_code_snapshot': pb.get('tier_code', 'none'),
            'contracted_units_snapshot': units_for_display,
            'project_fee_snapshot': pb.get('project_fee_snapshot', 0),
            'tier_fee_snapshot': pb.get('tier_fee_snapshot', 0),
            'license_fee_snapshot': pb.get('license_fee', 0),
            'units_fee_snapshot': pb.get('units_fee', 0),
            'price_per_unit': price_per_unit_for_display,
            'units_count': units_for_display,
            'monthly_total_snapshot': mt,
        })

    return {
        'org_id': org_id,
        'period_ym': period_ym,
        'total_amount': total,
        'currency': 'ILS',
        'due_at': _compute_due_at(year, month),
        'line_items': line_items,
    }


async def _try_create_gi_document(db, org_id: str, invoice_id: str, amount: float, period_ym: str, paid_until: str = "", card_last4: str = ""):
    from config import GI_BASE_URL
    if not GI_BASE_URL or amount <= 0:
        logger.info("[INVOICING:GI] Skipped — GI not configured or amount=0. invoice=%s amount=%s gi_configured=%s", invoice_id, amount, bool(GI_BASE_URL))
        return None
    logger.info("[INVOICING:GI] Starting GI document creation for invoice %s org=%s amount=%s", invoice_id, org_id, amount)
    from contractor_ops.green_invoice_service import create_or_get_client, create_document
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1, 'billing': 1, 'tax_id': 1})
    org_name = org.get('name', '') if org else ''
    billing_data = org.get('billing', {}) if org else {}
    billing_email = billing_data.get('billing_email', '')
    if not billing_email:
        owner = await db.users.find_one({'org_id': org_id, 'role': {'$in': ['owner', 'admin']}}, {'_id': 0, 'email': 1})
        billing_email = owner.get('email', '') if owner else ''
    tax_id = org.get('tax_id', '') if org else ''
    gi_client_id = billing_data.get('gi_client_id', '')
    if not gi_client_id:
        gi_client_id = await create_or_get_client(org_name or 'BrikOps Client', billing_email, tax_id)
        await db.organizations.update_one(
            {'id': org_id},
            {'$set': {'billing.gi_client_id': gi_client_id}}
        )
    if paid_until:
        try:
            pu_dt = datetime.fromisoformat(paid_until.replace('Z', '+00:00'))
            gi_description = f"מנוי חודשי BrikOps — {pu_dt.month:02d}/{pu_dt.year}"
        except Exception:
            gi_description = f"מנוי BrikOps — {period_ym}"
    else:
        gi_description = f"מנוי BrikOps — {period_ym}"
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    gi_doc = await create_document(
        client_name=org_name or 'BrikOps Client',
        client_email=billing_email,
        description=gi_description,
        amount=amount,
        currency='ILS',
        remarks=f"org_id={org_id} invoice_id={invoice_id}",
        client_id=gi_client_id,
        payment_date=today_str,
        card_last4=card_last4,
    )
    gi_document_id = gi_doc.get('id', '')
    url_field = gi_doc.get('url', {})
    if isinstance(url_field, dict):
        gi_download_url = url_field.get('he', '') or url_field.get('origin', '') or url_field.get('en', '')
    elif isinstance(url_field, str) and url_field:
        gi_download_url = url_field
    else:
        gi_download_url = gi_doc.get('download_url', '') or gi_doc.get('shareUrl', '')
    if not gi_download_url and gi_document_id:
        from config import GI_BASE_URL
        base = (GI_BASE_URL or "https://api.greeninvoice.co.il/api/v1").replace("/api/v1", "")
        gi_download_url = f"{base}/api/v1/documents/{gi_document_id}/download"
        logger.warning("[INVOICING:GI] No URL in response, using fallback URL for doc=%s", gi_document_id)
    if gi_document_id:
        update_fields = {'gi_document_id': gi_document_id, 'gi_download_url': gi_download_url, 'updated_at': _now()}
        await db.invoices.update_one(
            {'id': invoice_id},
            {'$set': update_fields}
        )
    logger.info("[INVOICING:GI] SUCCESS doc_id=%s url=%s for invoice %s", gi_document_id or '(none)', bool(gi_download_url), invoice_id)
    return gi_document_id


async def send_invoice_email(org_id: str, invoice: dict):
    from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("[INVOICE-EMAIL] SMTP not configured — skipping")
        return

    db = get_db()
    period_ym = invoice.get('period_ym', '')
    gi_download_url = invoice.get('gi_download_url', '')
    total_amount = invoice.get('total_amount', 0)

    if not gi_download_url:
        logger.info("[INVOICE-EMAIL] No GI URL — skipping email for org=%s", org_id)
        return

    try:
        m = _PERIOD_RE.match(period_ym)
        year = int(m.group(1)) if m else datetime.now(timezone.utc).year
        month = int(m.group(2)) if m else datetime.now(timezone.utc).month
    except Exception:
        year = datetime.now(timezone.utc).year
        month = datetime.now(timezone.utc).month
    hebrew_month = HEBREW_MONTHS.get(month, str(month))

    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1, 'manager_id': 1, 'billing': 1})
    if not org:
        logger.warning("[INVOICE-EMAIL] Org not found org=%s", org_id)
        return

    manager_id = org.get('manager_id', '')
    owner = None
    if manager_id:
        owner = await db.users.find_one({'id': manager_id}, {'_id': 0, 'email': 1, 'name': 1})
    if not owner:
        owner = await db.users.find_one({'org_id': org_id, 'role': {'$in': ['owner', 'admin']}}, {'_id': 0, 'email': 1, 'name': 1})
    if not owner or not owner.get('email'):
        logger.warning("[INVOICE-EMAIL] No owner email found for org=%s", org_id)
        return

    to_email = owner['email']
    owner_name = owner.get('name', '')

    sub = await db.subscriptions.find_one({'org_id': org_id}, {'_id': 0, 'plan_id': 1})
    plan_id = sub.get('plan_id', 'standard') if sub else 'standard'
    plan_names = {'standard': 'רישיון פרויקט', 'founder_6m': 'מייסדים'}
    plan_name = plan_names.get(plan_id, plan_id)

    subject = f"החשבונית שלך מ-BrikOps — {hebrew_month} {year}"

    html_body = f'''
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background: #ffffff;">
        <h2 style="color: #1a1a2e; margin-bottom: 24px;">BrikOps</h2>
        <p>שלום {owner_name},</p>
        <p>החשבונית שלך עבור חודש {hebrew_month} {year} מוכנה.</p>
        <div style="background: #f8f9fa; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <p style="margin: 4px 0;"><strong>סכום:</strong> ₪{total_amount:,.0f} (כולל מע״מ)</p>
            <p style="margin: 4px 0;"><strong>תוכנית:</strong> {plan_name}</p>
        </div>
        <div style="text-align: center; margin: 24px 0;">
            <a href="{gi_download_url}" style="display: inline-block; background: #f57c00; color: #ffffff; text-decoration: none; padding: 12px 32px; border-radius: 6px; font-weight: bold; font-size: 16px;">הורד חשבונית</a>
        </div>
        <p style="color: #666; font-size: 13px;">החשבונית זמינה גם בדף החשבוניות באפליקציה.</p>
    </div>
    '''

    text_body = f"שלום {owner_name},\nהחשבונית שלך עבור חודש {hebrew_month} {year} מוכנה.\nסכום: ₪{total_amount:,.0f} (כולל מע״מ)\nתוכנית: {plan_name}\nהורד חשבונית: {gi_download_url}"

    msg = MIMEMultipart('alternative')
    msg['From'] = 'BrikOps <invoice@brikops.com>'
    msg['To'] = to_email
    msg['Reply-To'] = 'zahi@brikops.com'
    msg['Subject'] = subject
    from contractor_ops.email_templates import wrap_email
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(wrap_email(html_body, 'invoice'), 'html', 'utf-8'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail('invoice@brikops.com', to_email, msg.as_string())
        logger.info("[INVOICE-EMAIL] Sent to %s for org=%s period=%s", to_email, org_id, period_ym)
    except Exception as e:
        logger.warning("[INVOICE-EMAIL] SMTP failed for org=%s: %s", org_id, e)


async def _resolve_org_billing_recipient(org_id: str):
    """Mirror send_invoice_email recipient resolution.
    Returns (org_doc, owner_email, owner_name) — owner_email is None if no recipient.
    """
    db = get_db()
    org = await db.organizations.find_one(
        {'id': org_id}, {'_id': 0, 'name': 1, 'manager_id': 1, 'billing': 1}
    )
    if not org:
        return None, None, None
    manager_id = org.get('manager_id', '')
    owner = None
    if manager_id:
        owner = await db.users.find_one(
            {'id': manager_id}, {'_id': 0, 'email': 1, 'name': 1}
        )
    if not owner:
        owner = await db.users.find_one(
            {'org_id': org_id, 'role': {'$in': ['owner', 'admin']}},
            {'_id': 0, 'email': 1, 'name': 1}
        )
    if not owner or not owner.get('email'):
        return org, None, None
    return org, owner['email'], owner.get('name', '')


def _format_hebrew_date(iso_str) -> str:
    if not iso_str:
        return ''
    try:
        dt = datetime.fromisoformat(str(iso_str).replace('Z', '+00:00'))
        return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"
    except Exception:
        return str(iso_str)


def _plan_name_he(plan_id) -> str:
    plan_names = {'standard': 'רישיון פרויקט', 'founder_6m': 'מייסדים'}
    return plan_names.get(plan_id, plan_id or 'רגיל')


def _smtp_send(msg, from_addr: str, to_addr: str, log_tag: str, org_id: str):
    """SMTP send helper with the same try/except pattern as send_invoice_email."""
    from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(from_addr, to_addr, msg.as_string())
        logger.info("[%s] Sent to %s for org=%s", log_tag, to_addr, org_id)
    except Exception as e:
        logger.warning("[%s] SMTP failed for org=%s: %s", log_tag, org_id, e)


async def send_cancellation_email_user(org_id: str, sub: dict, user: dict, reason: Optional[str]):
    """Confirmation email to the org's billing recipient when a subscription is cancelled.
    Mirrors send_invoice_email infrastructure exactly."""
    from config import SMTP_USER, SMTP_PASS
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("[CANCEL-EMAIL-USER] SMTP not configured — skipping")
        return

    _org, to_email, owner_name = await _resolve_org_billing_recipient(org_id)
    if not to_email:
        logger.warning("[CANCEL-EMAIL-USER] No recipient found for org=%s", org_id)
        return

    expires_at = sub.get('expires_at') or sub.get('paid_until') or ''
    formatted_expires = _format_hebrew_date(expires_at)

    subject = "אישור ביטול מנוי — BrikOps"

    html_body = f'''
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background: #ffffff;">
        <h2 style="color: #1a1a2e; margin-bottom: 24px;">BrikOps</h2>
        <p>שלום {owner_name},</p>
        <p>בוצע ביטול חידוש אוטומטי למנוי שלך ב-BrikOps.</p>
        <div style="background:#f8f9fa;padding:16px;border-radius:8px;margin:16px 0;">
            <p style="margin:4px 0;"><strong>הגישה למערכת תישאר פעילה עד:</strong></p>
            <p style="margin:4px 0;font-size:18px;color:#f57c00;">{formatted_expires}</p>
        </div>
        <p>אחרי תאריך זה לא יבוצעו חיובים נוספים.</p>
        <p style="font-size:13px;color:#666;">
            החיוב הזה לא יוחזר כי השירות סופק עד תום התקופה,
            בהתאם לחוק הגנת הצרכן.
        </p>
        <p style="font-size:13px;color:#666;">
            ניתן להפעיל מחדש את המנוי בכל עת לפני תאריך הפקיעה דרך
            <a href="https://app.brikops.com/billing" style="color:#f57c00;">דף החשבון שלך</a>.
        </p>
        <p style="font-size:12px;color:#999;margin-top:24px;">
            אם הביטול בוצע בטעות או בלי אישורך, פנה אלינו מיד דרך
            <a href="mailto:billing@brikops.com" style="color:#f57c00;">billing@brikops.com</a>.
        </p>
    </div>
    '''

    text_body = (
        f"שלום {owner_name},\n"
        f"בוצע ביטול חידוש אוטומטי למנוי שלך ב-BrikOps.\n"
        f"הגישה למערכת תישאר פעילה עד: {formatted_expires}\n"
        f"אחרי תאריך זה לא יבוצעו חיובים נוספים.\n"
        f"ניתן להפעיל מחדש לפני תאריך הפקיעה: https://app.brikops.com/billing\n"
    )

    msg = MIMEMultipart('alternative')
    msg['From'] = 'BrikOps <invoice@brikops.com>'
    msg['To'] = to_email
    msg['Reply-To'] = 'zahi@brikops.com'
    msg['Subject'] = subject
    from contractor_ops.email_templates import wrap_email
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(wrap_email(html_body, 'invoice'), 'html', 'utf-8'))

    _smtp_send(msg, 'invoice@brikops.com', to_email, 'CANCEL-EMAIL-USER', org_id)


async def send_cancellation_email_zahi(org_id: str, sub: dict, user: dict, reason: Optional[str]):
    """Internal alert to zahi@brikops.com when a subscription is cancelled.
    Hardcoded recipient — Zahi is the BrikOps owner."""
    from config import SMTP_USER, SMTP_PASS
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("[CANCEL-EMAIL-ZAHI] SMTP not configured — skipping")
        return

    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1})
    org_name = (org.get('name') if org else None) or org_id

    user_name = user.get('name') or user.get('email') or user.get('id', '')
    user_email = user.get('email', '')
    plan_name = _plan_name_he(sub.get('plan_id', ''))
    expires_at = sub.get('expires_at') or sub.get('paid_until') or ''
    formatted_expires = _format_hebrew_date(expires_at)
    reason_display = reason or 'לא צוינה'

    to_email = 'zahi@brikops.com'
    subject = f"[BrikOps] ביטול מנוי — {org_name}"

    html_body = f'''
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; background: #ffffff;">
        <h2 style="color: #1a1a2e; margin-bottom: 16px;">BrikOps — התראת ביטול מנוי</h2>
        <p>לקוח ביטל חידוש אוטומטי. הגישה תפוג בתאריך הסיום.</p>
        <table style="border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;">
            <tr><td style="padding:6px 4px;"><strong>ארגון:</strong></td><td style="padding:6px 4px;">{org_name}</td></tr>
            <tr><td style="padding:6px 4px;"><strong>משתמש:</strong></td><td style="padding:6px 4px;">{user_name} ({user_email})</td></tr>
            <tr><td style="padding:6px 4px;"><strong>תוכנית:</strong></td><td style="padding:6px 4px;">{plan_name}</td></tr>
            <tr><td style="padding:6px 4px;"><strong>גישה תפוג:</strong></td><td style="padding:6px 4px;">{formatted_expires}</td></tr>
            <tr><td style="padding:6px 4px;vertical-align:top;"><strong>סיבה:</strong></td><td style="padding:6px 4px;">{reason_display}</td></tr>
        </table>
        <p style="margin-top:24px;">
            <a href="https://app.brikops.com/admin/orgs/{org_id}"
               style="background:#f57c00;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;display:inline-block;">
                לארגון
            </a>
        </p>
        <p style="font-size:13px;color:#666;margin-top:16px;">
            פעולה אפשרית: הצעת save call לפני פקיעת הגישה.
        </p>
    </div>
    '''

    text_body = (
        f"BrikOps — התראת ביטול מנוי\n"
        f"ארגון: {org_name}\n"
        f"משתמש: {user_name} ({user_email})\n"
        f"תוכנית: {plan_name}\n"
        f"גישה תפוג: {formatted_expires}\n"
        f"סיבה: {reason_display}\n"
        f"לארגון: https://app.brikops.com/admin/orgs/{org_id}\n"
    )

    msg = MIMEMultipart('alternative')
    msg['From'] = 'BrikOps <invoice@brikops.com>'
    msg['To'] = to_email
    msg['Reply-To'] = 'zahi@brikops.com'
    msg['Subject'] = subject
    from contractor_ops.email_templates import wrap_email
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(wrap_email(html_body, 'invoice'), 'html', 'utf-8'))

    _smtp_send(msg, 'invoice@brikops.com', to_email, 'CANCEL-EMAIL-ZAHI', org_id)


async def send_reactivation_email_user(org_id: str, sub: dict, user: dict):
    """Confirmation email to the org's billing recipient when a subscription is reactivated."""
    from config import SMTP_USER, SMTP_PASS
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("[REACTIVATE-EMAIL-USER] SMTP not configured — skipping")
        return

    _org, to_email, owner_name = await _resolve_org_billing_recipient(org_id)
    if not to_email:
        logger.warning("[REACTIVATE-EMAIL-USER] No recipient found for org=%s", org_id)
        return

    paid_until = sub.get('paid_until') or ''
    formatted_paid = _format_hebrew_date(paid_until)

    subject = "המנוי שלך הופעל מחדש — BrikOps"

    html_body = f'''
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background: #ffffff;">
        <h2 style="color: #1a1a2e; margin-bottom: 24px;">BrikOps</h2>
        <p>שלום {owner_name},</p>
        <p>המנוי שלך הופעל מחדש בהצלחה.</p>
        <div style="background:#e8f5e9;padding:16px;border-radius:8px;margin:16px 0;">
            <p style="margin:4px 0;"><strong>החיוב הבא יבוצע ב:</strong></p>
            <p style="margin:4px 0;font-size:18px;color:#2e7d32;">{formatted_paid}</p>
        </div>
        <p>חידוש אוטומטי שב לפעולה.</p>
    </div>
    '''

    text_body = (
        f"שלום {owner_name},\n"
        f"המנוי שלך הופעל מחדש בהצלחה.\n"
        f"החיוב הבא יבוצע ב: {formatted_paid}\n"
        f"חידוש אוטומטי שב לפעולה.\n"
    )

    msg = MIMEMultipart('alternative')
    msg['From'] = 'BrikOps <invoice@brikops.com>'
    msg['To'] = to_email
    msg['Reply-To'] = 'zahi@brikops.com'
    msg['Subject'] = subject
    from contractor_ops.email_templates import wrap_email
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(wrap_email(html_body, 'invoice'), 'html', 'utf-8'))

    _smtp_send(msg, 'invoice@brikops.com', to_email, 'REACTIVATE-EMAIL-USER', org_id)


async def generate_invoice(org_id: str, period_ym: str, created_by: str, paid_until: str = "", card_last4: str = "", override_amount: float = None) -> dict:
    year, month = validate_period_ym(period_ym)
    db = get_db()

    existing = await db.invoices.find_one(
        {'org_id': org_id, 'period_ym': period_ym},
        {'_id': 0}
    )
    if existing:
        items = await db.invoice_line_items.find(
            {'invoice_id': existing['id']},
            {'_id': 0}
        ).to_list(1000)
        existing['line_items'] = items
        if not existing.get('gi_document_id'):
            try:
                gi_id = await _try_create_gi_document(db, org_id, existing['id'], existing.get('total_amount', 0), period_ym, paid_until=paid_until, card_last4=card_last4)
                if gi_id:
                    existing['gi_document_id'] = gi_id
            except Exception as e:
                logger.warning("[INVOICING:GI] Backfill FAILED for existing invoice %s: %s", existing['id'], str(e))
        return existing

    preview = await build_invoice_preview(org_id, period_ym)

    final_amount = preview['total_amount']
    if override_amount is not None:
        logger.info("[INVOICE] Using override amount=%.2f instead of computed=%.2f for org=%s period=%s", override_amount, final_amount, org_id, period_ym)
        final_amount = override_amount

    ts = _now()
    invoice_id = str(uuid.uuid4())
    invoice_doc = {
        'id': invoice_id,
        'org_id': org_id,
        'period_ym': period_ym,
        'status': 'issued',
        'total_amount': final_amount,
        'currency': 'ILS',
        'issued_at': ts,
        'due_at': preview['due_at'],
        'paid_at': None,
        'created_by': created_by,
        'created_at': ts,
        'updated_at': ts,
    }

    try:
        await db.invoices.insert_one(invoice_doc)
    except Exception as e:
        if 'duplicate key' in str(e).lower() or 'E11000' in str(e):
            existing = await db.invoices.find_one(
                {'org_id': org_id, 'period_ym': period_ym},
                {'_id': 0}
            )
            if existing:
                items = await db.invoice_line_items.find(
                    {'invoice_id': existing['id']},
                    {'_id': 0}
                ).to_list(1000)
                existing['line_items'] = items
                return existing
        raise

    item_docs = []
    for li in preview['line_items']:
        item_doc = {
            'id': str(uuid.uuid4()),
            'invoice_id': invoice_id,
            **li,
            'created_at': ts,
        }
        item_docs.append(item_doc)

    if item_docs:
        await db.invoice_line_items.insert_many(item_docs)

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'invoice',
        'entity_id': invoice_id,
        'action': 'invoice_generated',
        'actor_id': created_by,
        'payload': {
            'org_id': org_id,
            'period_ym': period_ym,
            'total_amount': final_amount,
            'line_item_count': len(item_docs),
        },
        'created_at': ts,
    })

    invoice_doc.pop('_id', None)
    for doc in item_docs:
        doc.pop('_id', None)
    invoice_doc['line_items'] = item_docs

    from config import GI_BASE_URL
    logger.info("[INVOICING:GI] About to attempt GI. invoice=%s amount=%s gi_configured=%s", invoice_id, final_amount, bool(GI_BASE_URL))
    try:
        gi_document_id = await _try_create_gi_document(db, org_id, invoice_id, final_amount, period_ym, paid_until=paid_until, card_last4=card_last4)
        if gi_document_id:
            invoice_doc['gi_document_id'] = gi_document_id
            gi_inv = await db.invoices.find_one({'id': invoice_id}, {'_id': 0, 'gi_download_url': 1})
            if gi_inv and gi_inv.get('gi_download_url'):
                invoice_doc['gi_download_url'] = gi_inv['gi_download_url']
    except Exception as e:
        logger.warning("[INVOICING:GI] FAILED for invoice %s: %s", invoice_id, str(e))

    try:
        await send_invoice_email(org_id, invoice_doc)
    except Exception as e:
        logger.warning("[INVOICE-EMAIL] Failed for org=%s: %s", org_id, e)

    logger.info(f"[INVOICING] Generated invoice {invoice_id} for org {org_id} period {period_ym}, total={final_amount}")
    return invoice_doc


async def get_invoice(org_id: str, invoice_id: str) -> Optional[dict]:
    db = get_db()
    inv = await db.invoices.find_one(
        {'id': invoice_id, 'org_id': org_id},
        {'_id': 0}
    )
    if not inv:
        return None
    items = await db.invoice_line_items.find(
        {'invoice_id': invoice_id},
        {'_id': 0}
    ).to_list(1000)
    inv['line_items'] = items
    return inv


async def list_invoices(org_id: str) -> List[dict]:
    db = get_db()
    invoices = await db.invoices.find(
        {'org_id': org_id},
        {'_id': 0}
    ).sort('period_ym', -1).to_list(1000)
    return invoices


async def mark_invoice_paid(org_id: str, invoice_id: str, actor_id: str) -> dict:
    db = get_db()
    inv = await db.invoices.find_one(
        {'id': invoice_id, 'org_id': org_id},
        {'_id': 0}
    )
    if not inv:
        raise ValueError("חשבונית לא נמצאה")
    if inv['status'] not in ('issued', 'past_due'):
        raise ValueError(f"לא ניתן לסמן חשבונית בסטטוס {inv['status']} כשולם")

    ts = _now()
    before_status = inv['status']

    year, month = validate_period_ym(inv['period_ym'])
    paid_until = _end_of_month_utc(year, month).isoformat()

    await db.invoices.update_one(
        {'id': invoice_id},
        {'$set': {
            'status': 'paid',
            'paid_at': ts,
            'updated_at': ts,
        }}
    )

    await db.subscriptions.update_one(
        {'org_id': org_id},
        {'$set': {
            'status': 'active',
            'paid_until': paid_until,
            'updated_at': ts,
        }}
    )

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'invoice',
        'entity_id': invoice_id,
        'action': 'invoice_marked_paid',
        'actor_id': actor_id,
        'payload': {
            'org_id': org_id,
            'period_ym': inv['period_ym'],
            'total_amount': inv['total_amount'],
            'before_status': before_status,
            'after_status': 'paid',
            'paid_until': paid_until,
        },
        'created_at': ts,
    })

    logger.info(f"[INVOICING] Invoice {invoice_id} marked paid for org {org_id}, paid_until={paid_until}")

    updated = await db.invoices.find_one({'id': invoice_id}, {'_id': 0})
    items = await db.invoice_line_items.find(
        {'invoice_id': invoice_id}, {'_id': 0}
    ).to_list(1000)
    updated['line_items'] = items
    return updated


async def check_and_enforce_dunning(org_id: str) -> dict:
    db = get_db()
    now = _now_dt()
    result = {'transitioned': [], 'enforced': []}

    issued_invoices = await db.invoices.find(
        {'org_id': org_id, 'status': 'issued'},
        {'_id': 0}
    ).to_list(1000)

    for inv in issued_invoices:
        due_dt = datetime.fromisoformat(inv['due_at'])
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        if now > due_dt:
            await db.invoices.update_one(
                {'id': inv['id'], 'status': 'issued'},
                {'$set': {'status': 'past_due', 'updated_at': _now()}}
            )
            result['transitioned'].append({
                'invoice_id': inv['id'],
                'period_ym': inv['period_ym'],
                'from': 'issued',
                'to': 'past_due',
            })
            logger.info(f"[INVOICING] Invoice {inv['id']} transitioned issued→past_due for org {org_id}")

    latest_invoice = await db.invoices.find_one(
        {"org_id": org_id},
        sort=[("period_ym", -1)]
    )

    past_due_invoices = await db.invoices.find(
        {'org_id': org_id, 'status': 'past_due'},
        {'_id': 0}
    ).to_list(1000)

    for inv in past_due_invoices:
        due_dt = datetime.fromisoformat(inv['due_at'])
        if due_dt.tzinfo is None:
            due_dt = due_dt.replace(tzinfo=timezone.utc)
        grace_end = due_dt + timedelta(days=GRACE_DAYS)
        if now > grace_end:
            if latest_invoice and latest_invoice["status"] not in ("past_due",) and inv["period_ym"] != latest_invoice["period_ym"]:
                logger.info(f"[INVOICING] Skipping paid_until clear for old invoice {inv['id']} (period {inv['period_ym']}); latest period {latest_invoice['period_ym']} is {latest_invoice['status']}")
                continue
            sub = await db.subscriptions.find_one(
                {'org_id': org_id}, {'_id': 0, 'paid_until': 1}
            )
            if sub and sub.get('paid_until'):
                await db.subscriptions.update_one(
                    {'org_id': org_id},
                    {'$set': {'paid_until': None, 'updated_at': _now()}}
                )
                result['enforced'].append({
                    'invoice_id': inv['id'],
                    'period_ym': inv['period_ym'],
                    'action': 'cleared_paid_until',
                })
                logger.info(f"[INVOICING] Cleared paid_until for org {org_id} due to past_due invoice {inv['id']} past grace")

    return result
