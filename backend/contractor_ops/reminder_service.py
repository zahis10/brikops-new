import os
import uuid
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx

from .notification_service import (
    NotificationEngine, validate_e164, mask_phone, _resolve_fallback_image,
)
from contractor_ops.utils.timezone import IL_TZ
from contractor_ops.constants import TERMINAL_TASK_STATUSES

logger = logging.getLogger(__name__)

OVERDUE_THRESHOLD_DAYS = 7
COOLDOWN_HOURS = 48
SEND_PACING_SECONDS = 0.1
DEFAULT_WORKDAYS = [0, 1, 2, 3, 4]
DORMANT_USER_DAYS = 45
PYTHON_TO_ISRAEL_WEEKDAY = {6: 0, 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}

_db = None
_wa_access_token = ""
_wa_phone_number_id = ""
_wa_api_url = ""
_wa_enabled = False


def set_reminder_deps(db, wa_access_token: str, wa_phone_number_id: str, wa_enabled: bool):
    global _db, _wa_access_token, _wa_phone_number_id, _wa_api_url, _wa_enabled
    _db = db
    _wa_access_token = wa_access_token
    _wa_phone_number_id = wa_phone_number_id
    _wa_api_url = f"https://graph.facebook.com/v21.0/{wa_phone_number_id}/messages"
    _wa_enabled = wa_enabled


def _now():
    return datetime.now(timezone.utc).isoformat()


def _now_dt():
    return datetime.now(timezone.utc)


def is_shabbat() -> Optional[str]:
    now_il = datetime.now(IL_TZ)
    if now_il.weekday() == 5:
        return "shabbat"
    if now_il.weekday() == 4 and now_il.hour >= 14:
        return "erev_shabbat"
    return None


def _get_israel_weekday() -> int:
    """Return current Israel weekday: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat.
    Python datetime.weekday() uses Mon=0, Sun=6 — convert via PYTHON_TO_ISRAEL_WEEKDAY."""
    py_wd = datetime.now(IL_TZ).weekday()
    return PYTHON_TO_ISRAEL_WEEKDAY[py_wd]


def _check_user_reminder_prefs(user: dict, reminder_type: str) -> Optional[str]:
    """Check if user's reminder_preferences allow sending this type today.
    Returns None if allowed, or a skip reason string.
    Only applies to auto (cron) reminders — manual triggers bypass this."""
    prefs = user.get("reminder_preferences", {})
    type_prefs = prefs.get(reminder_type, {})
    if type_prefs.get("enabled") is False:
        return f"user_disabled_{reminder_type}"
    allowed_days = type_prefs.get("days", DEFAULT_WORKDAYS)
    israel_wd = _get_israel_weekday()
    if israel_wd not in allowed_days:
        return f"day_{israel_wd}_not_in_user_days"
    return None


def _is_user_dormant(user: dict) -> bool:
    """Return True if the user has not logged in for >DORMANT_USER_DAYS.

    Primary signal: `last_login_at` (ISO-8601). If absent or malformed,
    fall back to `created_at` to avoid permanently dead-locking fresh
    invites that have not yet logged in (per Replit V2 feedback). If
    BOTH `last_login_at` and `created_at` are missing/malformed, treat
    as dormant — a defensive default that protects against spamming
    accounts in unknown states.
    """
    if not user:
        return True
    cutoff = _now_dt() - timedelta(days=DORMANT_USER_DAYS)
    last_login = user.get("last_login_at")
    if last_login:
        try:
            ts = datetime.fromisoformat(str(last_login).replace("Z", "+00:00"))
            return ts < cutoff
        except (ValueError, TypeError):
            pass  # malformed → fall through to created_at
    created = user.get("created_at")
    if created:
        try:
            ts = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            # New-user exception: account < 45d old → not dormant.
            return ts < cutoff
        except (ValueError, TypeError):
            pass
    # No usable timestamps at all → defensive dormant.
    return True


def _user_disabled_whatsapp(user: dict) -> bool:
    """Return True iff the user has explicitly opted out of WhatsApp.

    Field default is True (opt-in), so missing/None must NOT be treated
    as disabled — only explicit `False` counts.
    """
    if not user:
        return False
    return user.get("whatsapp_notifications_enabled") is False


def _resolve_phone_for_user(user: dict) -> Optional[str]:
    phone = user.get('phone_e164') or user.get('phone', '')
    phone = NotificationEngine._normalize_israeli_phone(phone)
    if phone and validate_e164(phone):
        return phone
    return None


async def _resolve_phone_for_company(company_id: str) -> Optional[str]:
    company = await _db.companies.find_one({'id': company_id}, {'_id': 0})
    if not company:
        return None
    phone = company.get('phone_e164') or company.get('phone', '')
    phone = NotificationEngine._normalize_israeli_phone(phone)
    if phone and validate_e164(phone):
        return phone
    return None


async def _send_wa_template(to_phone: str, template_name: str, body_params: list, button_params: list = None, lang_code: str = "he") -> dict:
    if not _wa_enabled:
        logger.info(f"[REMINDER:DRY-RUN] template={template_name} to={mask_phone(to_phone)}")
        return {"success": True, "dry_run": True, "provider_message_id": f"dry_{uuid.uuid4().hex[:12]}"}

    to_digits = to_phone.lstrip('+')
    from config import WA_TEMPLATE_PARAM_MODE
    params = []
    for p in body_params:
        param = {"type": "text", "text": str(p.get("text", ""))}
        if WA_TEMPLATE_PARAM_MODE == 'named' and p.get("parameter_name"):
            param["parameter_name"] = p["parameter_name"]
        params.append(param)

    components = [
        {"type": "body", "parameters": params}
    ]
    if button_params:
        for bp in button_params:
            components.append({
                "type": "button",
                "sub_type": "url",
                "index": bp["index"],
                "parameters": [{"type": "text", "text": bp["text"]}]
            })

    body = {
        "messaging_product": "whatsapp",
        "to": to_digits,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang_code},
            "components": components
        }
    }

    headers = {
        "Authorization": f"Bearer {_wa_access_token}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(_wa_api_url, json=body, headers=headers)

    if resp.status_code in (200, 201):
        data = resp.json()
        mid = data.get("messages", [{}])[0].get("id", "")
        logger.info(f"[REMINDER:SEND] SUCCESS template={template_name} to={mask_phone(to_phone)} mid={mid}")
        return {"success": True, "provider_message_id": mid}
    else:
        error_msg = resp.text[:500]
        logger.error(f"[REMINDER:SEND] FAILED template={template_name} to={mask_phone(to_phone)} status={resp.status_code} error={error_msg}")
        raise RuntimeError(f"WhatsApp API error ({resp.status_code}): {error_msg}")


async def _log_reminder(entry: dict):
    entry.setdefault("id", f"rem_{uuid.uuid4().hex[:16]}")
    entry.setdefault("sent_at", _now())
    await _db.reminder_log.insert_one(entry)
    return entry


async def _check_cooldown(project_id: str, reminder_type: str = "contractor_reminder", company_id: str = None, user_id: str = None) -> bool:
    cutoff = (_now_dt() - timedelta(hours=COOLDOWN_HOURS)).isoformat()
    query = {
        "type": reminder_type,
        "project_id": project_id,
        "sent_at": {"$gte": cutoff},
        "status": {"$ne": "failed"},
    }
    if reminder_type == "contractor_reminder" and company_id:
        query["company_id"] = company_id
    elif user_id:
        query["recipient_user_id"] = user_id
    last = await _db.reminder_log.find_one(query)
    return last is not None


async def _check_cooldown_for_user(project_id: str, user_id: str) -> bool:
    """Cooldown gate for the per-user contractor digest path (Bug A fix).

    Backward compatible: matches BOTH the legacy
    `contractor_reminder` type AND the new `contractor_reminder_digest`
    type so cooldowns straddle the deploy boundary.
    """
    cutoff = (_now_dt() - timedelta(hours=COOLDOWN_HOURS)).isoformat()
    query = {
        "type": {"$in": ["contractor_reminder", "contractor_reminder_digest"]},
        "project_id": project_id,
        "recipient_user_id": user_id,
        "sent_at": {"$gte": cutoff},
        "status": {"$ne": "failed"},
    }
    last = await _db.reminder_log.find_one(query)
    return last is not None


async def _check_cooldown_for_company(project_id: str, company_id: str) -> bool:
    """Cooldown gate for the orphan-task company-fallback path."""
    cutoff = (_now_dt() - timedelta(hours=COOLDOWN_HOURS)).isoformat()
    query = {
        "type": {"$in": ["contractor_reminder", "contractor_reminder_digest"]},
        "project_id": project_id,
        "company_id": company_id,
        "sent_at": {"$gte": cutoff},
        "status": {"$ne": "failed"},
    }
    last = await _db.reminder_log.find_one(query)
    return last is not None


def _build_location_string(task: dict, building_map: dict, floor_map: dict, unit_map: dict) -> str:
    parts = []
    bld_name = building_map.get(task.get("building_id", ""), "")
    if bld_name:
        parts.append(bld_name)
    floor_name = floor_map.get(task.get("floor_id", ""), "")
    if floor_name:
        parts.append(f"קומה {floor_name}")
    unit_name = unit_map.get(task.get("unit_id", ""), "")
    if unit_name:
        parts.append(f"דירה {unit_name}")
    return " / ".join(parts) if parts else "לא צוין"


def _calc_wait_days(task: dict) -> int:
    created = task.get("created_at", "")
    if not created:
        return 0
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - created_dt
        return max(delta.days, 1)
    except (ValueError, TypeError):
        return 0


def _resolve_digest_template_for_user(user: dict) -> tuple:
    """Pick the digest template (name + lang_code) for a recipient based on
    users.preferred_language. Mirrors WA_DEFECT_TEMPLATES resolution logic
    in notification_service.py:189-194.

    Returns (template_name, lang_code). Falls back to Hebrew → English chain.
    """
    from config import WA_REMINDER_DIGEST_TEMPLATES, WA_REMINDER_DIGEST_DEFAULT_LANG
    lang_key = (user or {}).get('preferred_language') or WA_REMINDER_DIGEST_DEFAULT_LANG
    lang_key = lang_key.lower().strip()
    tpl_info = WA_REMINDER_DIGEST_TEMPLATES.get(lang_key)
    if not tpl_info:
        # First fallback: English (matches notification_service.py pattern)
        if lang_key != 'en':
            logger.info(f"[REMINDER:DIGEST] Lang '{lang_key}' not configured, falling back to en")
            tpl_info = WA_REMINDER_DIGEST_TEMPLATES.get('en')
        # Last-resort fallback: Hebrew default (should always exist)
        if not tpl_info:
            logger.warning(f"[REMINDER:DIGEST] English template missing too, falling back to he")
            tpl_info = WA_REMINDER_DIGEST_TEMPLATES.get(WA_REMINDER_DIGEST_DEFAULT_LANG)
    return (tpl_info['name'], tpl_info['lang'])


async def send_contractor_reminder(
    project_id: str,
    assignee_user_id: str,
    triggered_by: str = "cron",
    skip_cooldown: bool = False,
    skip_preferences: bool = False,
) -> dict:
    """Send ONE WhatsApp digest to a contractor user for a single project,
    aggregating ALL of that user's open tasks across all companies in the
    project (Bug A fix — keyed by user, not company).

    3-tier eligibility for cron sends:
      1. WhatsApp toggle  (whatsapp_notifications_enabled is False)   → skip
      2. Dormant >45 days (with new-user exception via created_at)    → skip
      3. Reminder prefs   (day-of-week + per-type enabled flag)       → skip
    Cooldown is keyed to (project_id, user_id) — see
    `_check_cooldown_for_user`.
    """
    open_filter = {"status": {"$nin": list(TERMINAL_TASK_STATUSES)}}
    tasks = await _db.tasks.find({
        "project_id": project_id,
        "assignee_id": assignee_user_id,
        **open_filter,
    }, {"_id": 0, "id": 1, "title": 1, "company_id": 1, "created_at": 1, "assignee_id": 1}).to_list(500)

    if not tasks:
        return {"status": "skipped", "reason": "no_open_defects",
                "project_id": project_id, "user_id": assignee_user_id}

    project = await _db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1, "org_id": 1})
    if not project:
        return {"status": "skipped", "reason": "project_not_found"}

    org_id = project.get("org_id", "")

    user = await _db.users.find_one({"id": assignee_user_id}, {"_id": 0})
    if not user:
        logger.warning(f"[REMINDER] Assignee {assignee_user_id} not found, skipping")
        return {"status": "skipped", "reason": "user_not_found", "user_id": assignee_user_id}

    # 3-tier eligibility — only on auto/cron sends; manual triggers bypass.
    if not skip_preferences:
        if _user_disabled_whatsapp(user):
            logger.info(f"[REMINDER] User {assignee_user_id} disabled WhatsApp, skipping")
            return {"status": "skipped", "reason": "wa_disabled", "user_id": assignee_user_id}
        if _is_user_dormant(user):
            logger.info(f"[REMINDER] User {assignee_user_id} is dormant (>{DORMANT_USER_DAYS}d), skipping")
            return {"status": "skipped", "reason": "user_dormant", "user_id": assignee_user_id}
        pref_skip = _check_user_reminder_prefs(user, "contractor_reminder")
        if pref_skip:
            logger.info(f"[REMINDER] Skipping contractor reminder for user {assignee_user_id}: {pref_skip}")
            return {"status": "skipped", "reason": pref_skip, "user_id": assignee_user_id}

    phone = _resolve_phone_for_user(user)
    if not phone:
        logger.warning(f"[REMINDER] User {assignee_user_id} has no valid phone, skipping")
        return {"status": "skipped", "reason": "no_valid_phone", "user_id": assignee_user_id}

    if not skip_cooldown:
        if await _check_cooldown_for_user(project_id, assignee_user_id):
            return {"status": "skipped", "reason": "cooldown",
                    "project_id": project_id, "user_id": assignee_user_id}

    open_count = len(tasks)
    user_name = user.get("name", "קבלן")
    tpl_name, lang_code = _resolve_digest_template_for_user(user)

    log_entry = {
        "type": "contractor_reminder_digest",
        "recipient_user_id": assignee_user_id,
        "recipient_phone": phone,
        "project_id": project_id,
        "org_id": org_id,
        "open_count": open_count,
        "message_template": tpl_name,
        "lang_code": lang_code,
        "triggered_by": triggered_by,
    }

    try:
        body_params = [
            {"parameter_name": "name", "text": user_name},
            {"parameter_name": "count", "text": str(open_count)},
            {"parameter_name": "project", "text": project.get("name", "")},
        ]
        button_params = [
            {"index": 0, "text": f"{project_id}?src=wa"}
        ]
        wa_result = await _send_wa_template(
            phone, tpl_name, body_params,
            button_params=button_params,
            lang_code=lang_code,
        )
        log_entry["status"] = "sent"
        log_entry["wa_message_id"] = wa_result.get("provider_message_id", "")
        result = {"status": "completed", "user_id": assignee_user_id,
                  "messages_sent": 1, "open_count": open_count,
                  "results": [{"user_id": assignee_user_id, "status": "sent",
                               "messages_sent": 1, "open_count": open_count}],
                  "defect_count": open_count}
    except Exception as e:
        log_entry["status"] = "failed"
        log_entry["error_detail"] = str(e)[:500]
        logger.error(f"[REMINDER:DIGEST] Failed to send digest to {mask_phone(phone)} "
                     f"for project {project_id} user {assignee_user_id}: {e}")
        result = {"status": "completed", "user_id": assignee_user_id,
                  "results": [{"user_id": assignee_user_id, "status": "failed",
                               "error": str(e)[:200]}],
                  "defect_count": open_count}

    await _log_reminder(log_entry)
    await asyncio.sleep(SEND_PACING_SECONDS)
    return result


async def send_contractor_reminder_to_company(
    project_id: str,
    company_id: str,
    triggered_by: str = "cron",
    skip_cooldown: bool = False,
) -> dict:
    """Fallback path for orphan tasks (no `assignee_id` but `company_id`
    set). Sends one Hebrew digest to the company's phone. Skips dormant
    + WA-toggle checks since there's no user to evaluate. Used by
    `send_all_contractor_reminders` after the per-user primary path.
    """
    open_filter = {"status": {"$nin": list(TERMINAL_TASK_STATUSES)}}
    tasks = await _db.tasks.find({
        "project_id": project_id,
        "company_id": company_id,
        "$or": [
            {"assignee_id": {"$exists": False}},
            {"assignee_id": None},
            {"assignee_id": ""},
        ],
        **open_filter,
    }, {"_id": 0, "id": 1, "title": 1, "company_id": 1, "created_at": 1}).to_list(500)

    if not tasks:
        return {"status": "skipped", "reason": "no_orphan_defects",
                "project_id": project_id, "company_id": company_id}

    project = await _db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1, "org_id": 1})
    if not project:
        return {"status": "skipped", "reason": "project_not_found"}

    org_id = project.get("org_id", "")

    company_phone = await _resolve_phone_for_company(company_id)
    if not company_phone:
        return {"status": "skipped", "reason": "no_valid_phone",
                "company_id": company_id}

    if not skip_cooldown:
        if await _check_cooldown_for_company(project_id, company_id):
            return {"status": "skipped", "reason": "cooldown",
                    "project_id": project_id, "company_id": company_id}

    company = await _db.companies.find_one({"id": company_id}, {"_id": 0, "name": 1})
    company_name = (company or {}).get("name", "קבלן")
    open_count = len(tasks)

    # Orphan path uses Hebrew default (no user → no preferred_language).
    tpl_name, lang_code = _resolve_digest_template_for_user({})

    log_entry = {
        "type": "contractor_reminder_digest",
        "company_id": company_id,
        "recipient_phone": company_phone,
        "project_id": project_id,
        "org_id": org_id,
        "open_count": open_count,
        "message_template": tpl_name,
        "lang_code": lang_code,
        "triggered_by": triggered_by,
        "is_orphan_fallback": True,
    }

    try:
        body_params = [
            {"parameter_name": "name", "text": company_name},
            {"parameter_name": "count", "text": str(open_count)},
            {"parameter_name": "project", "text": project.get("name", "")},
        ]
        button_params = [{"index": 0, "text": f"{project_id}?src=wa"}]
        wa_result = await _send_wa_template(
            company_phone, tpl_name, body_params,
            button_params=button_params, lang_code=lang_code,
        )
        log_entry["status"] = "sent"
        log_entry["wa_message_id"] = wa_result.get("provider_message_id", "")
        result = {"status": "completed", "company_id": company_id,
                  "messages_sent": 1, "open_count": open_count,
                  "results": [{"company_id": company_id, "status": "sent",
                               "messages_sent": 1, "open_count": open_count}],
                  "defect_count": open_count}
    except Exception as e:
        log_entry["status"] = "failed"
        log_entry["error_detail"] = str(e)[:500]
        logger.error(f"[REMINDER:DIGEST:ORPHAN] Failed to send to {mask_phone(company_phone)} "
                     f"for project {project_id} company {company_id}: {e}")
        result = {"status": "completed", "company_id": company_id,
                  "results": [{"company_id": company_id, "status": "failed",
                               "error": str(e)[:200]}],
                  "defect_count": open_count}

    await _log_reminder(log_entry)
    await asyncio.sleep(SEND_PACING_SECONDS)
    return result


async def send_pm_digest(
    project_id: str,
    triggered_by: str = "cron",
    skip_preferences: bool = False,
) -> dict:
    project = await _db.projects.find_one({"id": project_id}, {"_id": 0, "name": 1, "org_id": 1})
    if not project:
        return {"status": "skipped", "reason": "project_not_found"}

    org_id = project.get("org_id", "")
    now = _now_dt()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    open_filter = {"project_id": project_id, "status": {"$nin": list(TERMINAL_TASK_STATUSES)}}
    open_count = await _db.tasks.count_documents(open_filter)

    overdue_cutoff = (now - timedelta(days=OVERDUE_THRESHOLD_DAYS)).isoformat()
    overdue_count = await _db.tasks.count_documents({
        **open_filter,
        "created_at": {"$lte": overdue_cutoff},
    })

    awaiting_approval = await _db.tasks.count_documents({
        "project_id": project_id,
        "status": "pending_manager_approval",
    })

    not_responded_cutoff = (now - timedelta(hours=48)).isoformat()
    contractors_not_responded = await _db.tasks.count_documents({
        "project_id": project_id,
        "status": "open",
        "company_id": {"$exists": True, "$nin": [None, ""]},
        "created_at": {"$lte": not_responded_cutoff},
    })

    if open_count == 0 and awaiting_approval == 0:
        return {"status": "skipped", "reason": "no_meaningful_data"}

    pm_memberships = await _db.project_memberships.find({
        "project_id": project_id,
        "role": {"$in": ["project_manager", "owner"]},
    }, {"_id": 0}).to_list(100)

    recipients = []
    for mem in pm_memberships:
        user = await _db.users.find_one({"id": mem["user_id"]}, {"_id": 0})
        if user:
            phone = _resolve_phone_for_user(user)
            if phone:
                recipients.append({"user": user, "phone": phone})
            else:
                logger.warning(f"[DIGEST] PM {mem['user_id']} has no valid phone, skipping")

    if not recipients:
        return {"status": "skipped", "reason": "no_pm_with_phone"}

    from config import WA_DIGEST_TEMPLATE_HE
    results = []

    for r in recipients:
        user = r["user"]
        phone = r["phone"]
        user_id = user.get("id", "")

        if not skip_preferences:
            pref_skip = _check_user_reminder_prefs(user, "pm_digest")
            if pref_skip:
                logger.info(f"[DIGEST] Skipping PM digest for user {user_id}: {pref_skip}")
                results.append({"user_id": user_id, "status": "skipped", "reason": pref_skip})
                continue

        log_entry = {
            "type": "pm_digest",
            "recipient_user_id": user_id,
            "recipient_phone": phone,
            "project_id": project_id,
            "org_id": org_id,
            "message_template": WA_DIGEST_TEMPLATE_HE,
            "defect_count": open_count,
            "triggered_by": triggered_by,
        }

        try:
            body_params = [
                {"parameter_name": "pm_name", "text": user.get("name", "מנהל")},
                {"parameter_name": "project_name", "text": project.get("name", "")},
                {"parameter_name": "open_count", "text": str(open_count)},
                {"parameter_name": "overdue_count", "text": str(overdue_count)},
                {"parameter_name": "awaiting_approval", "text": str(awaiting_approval)},
                {"parameter_name": "contractors_not_responded", "text": str(contractors_not_responded)},
            ]
            button_params = [
                {"index": 0, "text": project_id}
            ]
            wa_result = await _send_wa_template(phone, WA_DIGEST_TEMPLATE_HE, body_params, button_params=button_params)
            log_entry["status"] = "sent"
            log_entry["wa_message_id"] = wa_result.get("provider_message_id", "")
            results.append({"user_id": user_id, "status": "sent"})
        except Exception as e:
            log_entry["status"] = "failed"
            log_entry["error_detail"] = str(e)[:500]
            results.append({"user_id": user_id, "status": "failed", "error": str(e)[:200]})
            logger.error(f"[DIGEST] Failed to send PM digest to {mask_phone(phone)}: {e}")

        await _log_reminder(log_entry)
        await asyncio.sleep(SEND_PACING_SECONDS)

    return {
        "status": "completed",
        "results": results,
        "stats": {
            "open": open_count,
            "overdue": overdue_count,
            "awaiting_approval": awaiting_approval,
            "contractors_not_responded": contractors_not_responded,
        },
    }


def _accumulate_summary(summary: dict, result: dict):
    """Roll up a single send_*_reminder return value into the batch summary."""
    status = result.get("status", "")
    if status == "completed":
        for r in result.get("results", []):
            if r.get("status") == "sent":
                summary["sent"] += r.get("messages_sent", 1)
            elif r.get("status") == "skipped":
                summary["skipped"] += 1
            elif r.get("status") == "failed":
                summary["failed"] += 1
    elif status == "skipped":
        summary["skipped"] += 1


async def send_all_contractor_reminders() -> dict:
    """Cron-driven contractor digest sweep.

    Bug A fix: iterates by `(project, assignee_user)` (PRIMARY path) so
    a contractor in N companies of the same project gets ONE digest with
    N open defects — not N separate messages.

    Bug C fix: only `status='active'` projects with `archived` not true
    are eligible (suspended / archived / deleted projects are skipped).

    Orphan fallback: tasks with `company_id` but no `assignee_id` are
    sent to the company's phone via `send_contractor_reminder_to_company`
    after the primary loop.
    """
    summary = {"sent": 0, "skipped": 0, "failed": 0, "projects": []}
    try:
        # Bug C — filter projects by status + archived flag.
        project_filter = {
            "status": "active",
            "$or": [
                {"archived": {"$exists": False}},
                {"archived": False},
                {"archived": None},
            ],
        }
        projects = await _db.projects.find(
            project_filter, {"_id": 0, "id": 1, "name": 1}
        ).to_list(500)

        for project in projects:
            pid = project["id"]
            open_tasks = await _db.tasks.find({
                "project_id": pid,
                "status": {"$nin": list(TERMINAL_TASK_STATUSES)},
            }, {"_id": 0, "assignee_id": 1, "company_id": 1}).to_list(2000)

            if not open_tasks:
                continue

            assignee_ids = sorted({
                t["assignee_id"] for t in open_tasks
                if t.get("assignee_id")
            })
            orphan_company_ids = sorted({
                t["company_id"] for t in open_tasks
                if not t.get("assignee_id") and t.get("company_id")
            })

            # PRIMARY — per-user digest (Bug A: aggregate across companies).
            for aid in assignee_ids:
                try:
                    result = await send_contractor_reminder(
                        pid, aid, triggered_by="cron", skip_cooldown=False
                    )
                    _accumulate_summary(summary, result)
                except Exception as e:
                    summary["failed"] += 1
                    logger.error(f"[REMINDER-BATCH] Error for project={pid} user={aid}: {e}")

            # FALLBACK — orphan tasks (no assignee but with company).
            for cid in orphan_company_ids:
                try:
                    result = await send_contractor_reminder_to_company(
                        pid, cid, triggered_by="cron", skip_cooldown=False
                    )
                    _accumulate_summary(summary, result)
                except Exception as e:
                    summary["failed"] += 1
                    logger.error(f"[REMINDER-BATCH:ORPHAN] Error for project={pid} company={cid}: {e}")

            summary["projects"].append(pid)
    except Exception as e:
        logger.critical(f"[REMINDER-BATCH] Catastrophic failure: {e}")
        summary["critical_error"] = str(e)[:500]

    return summary


async def send_all_pm_digests() -> dict:
    summary = {"sent": 0, "skipped": 0, "failed": 0, "projects": []}
    try:
        projects = await _db.projects.find({}, {"_id": 0, "id": 1, "name": 1}).to_list(500)
        for project in projects:
            pid = project["id"]
            try:
                result = await send_pm_digest(pid, triggered_by="cron")
                status = result.get("status", "")
                if status == "completed":
                    for r in result.get("results", []):
                        if r.get("status") == "sent":
                            summary["sent"] += 1
                        elif r.get("status") == "failed":
                            summary["failed"] += 1
                elif status == "skipped":
                    summary["skipped"] += 1
            except Exception as e:
                summary["failed"] += 1
                logger.error(f"[DIGEST-BATCH] Error for project={pid}: {e}")

            summary["projects"].append(pid)
    except Exception as e:
        logger.critical(f"[DIGEST-BATCH] Catastrophic failure: {e}")
        summary["critical_error"] = str(e)[:500]

    return summary


async def ensure_indexes():
    try:
        await _db.reminder_log.create_index([
            ("company_id", 1),
            ("type", 1),
            ("project_id", 1),
            ("sent_at", -1),
        ])
        await _db.reminder_log.create_index([
            ("recipient_user_id", 1),
            ("type", 1),
            ("project_id", 1),
            ("sent_at", -1),
        ])
        await _db.reminder_log.create_index([("wa_message_id", 1)])
        # Rate-limit collection (pentest HIGH-N1 2026-05-16)
        await _db.reminder_rate_limits.create_index(
            "expires_at",
            expireAfterSeconds=0,
            background=True,
        )
        await _db.reminder_rate_limits.create_index(
            [("kind", 1), ("key", 1)],
            unique=True,
            background=True,
        )
        logger.info("[REMINDER] Indexes created on reminder_log + reminder_rate_limits")
    except Exception as e:
        logger.warning(f"[REMINDER] Index creation issue: {e}")
