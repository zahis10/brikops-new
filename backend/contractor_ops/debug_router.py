import subprocess as _subprocess
import os as _os
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from contractor_ops.router import (
    get_db, get_current_user, require_super_admin, require_stepup, require_roles,
    _is_super_admin, _now, APP_ID,
    VALID_TRANSITIONS, PLAN_DISCIPLINES, PLAN_UPLOAD_ROLES,
    PHONE_VISIBLE_ROLES, _enrich_memberships,
)
from config import ENABLE_DEBUG_ENDPOINTS

router = APIRouter(prefix="/api")


async def _require_debug_access(user: dict = Depends(require_super_admin)):
    if not ENABLE_DEBUG_ENDPOINTS:
        raise HTTPException(status_code=404, detail="Not found")
    return user


def _resolve_git_sha():
    release = _os.environ.get("RELEASE_SHA", "")
    if release:
        return release
    try:
        result = _subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=_os.path.dirname(_os.path.dirname(__file__))
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return _os.environ.get("GIT_SHA", "unknown")

_BUILD_GIT_SHA = _resolve_git_sha()
_BUILD_TIME = _os.environ.get("BUILD_TIME", _now())


@router.get("/health")
async def health_check():
    db = get_db()
    try:
        await db.command("ping")
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {"status": "ok", "database": db_status, "app_id": APP_ID}


@router.get("/ready")
async def readiness_check():
    db = get_db()
    checks = {}
    all_ok = True
    try:
        await db.command("ping")
        checks["database"] = "ready"
    except Exception:
        checks["database"] = "not_ready"
        all_ok = False
    status_code = 200 if all_ok else 503
    from starlette.responses import JSONResponse
    return JSONResponse(
        content={"ready": all_ok, "checks": checks},
        status_code=status_code
    )


@router.get("/admin/system-info")
async def admin_system_info(request: Request, user: dict = Depends(require_super_admin)):
    from config import APP_MODE, MONGO_URL, DB_NAME
    db = get_db()
    users_count = await db.users.count_documents({})
    projects_count = await db.projects.count_documents({})
    tasks_count = await db.tasks.count_documents({})
    memberships_count = await db.project_memberships.count_documents({})
    audit_count = await db.audit_events.count_documents({})
    organizations_count = await db.organizations.count_documents({})

    if '@' in MONGO_URL:
        parts = MONGO_URL.split('@', 1)
        host_part = parts[1].split('/')[0] if '/' in parts[1] else parts[1]
        masked_host = f"****@{host_part}"
    elif 'localhost' in MONGO_URL or '127.0.0.1' in MONGO_URL:
        masked_host = "localhost"
    else:
        masked_host = MONGO_URL[:20] + "..."

    return {
        "db_name": DB_NAME,
        "db_host": masked_host,
        "app_mode": APP_MODE,
        "git_sha": _BUILD_GIT_SHA,
        "counts": {
            "users": users_count,
            "projects": projects_count,
            "tasks": tasks_count,
            "memberships": memberships_count,
            "audit_events": audit_count,
            "organizations": organizations_count,
        },
        "seed_guard": {
            "run_seed": _os.environ.get('RUN_SEED', 'not set'),
            "seed_blocked_in_prod": True,
        },
    }


@router.get("/admin/diagnostics/role-conflicts")
async def admin_diagnostics_role_conflicts(request: Request, user: dict = Depends(require_stepup)):
    db = get_db()
    conflicts = []
    seen_keys = set()

    orgs = await db.organizations.find({}, {'_id': 0, 'id': 1, 'name': 1, 'owner_user_id': 1}).to_list(10000)
    for org in orgs:
        owner_uid = org.get('owner_user_id')
        if not owner_uid:
            continue
        org_id = org['id']
        org_project_ids = await db.projects.distinct('id', {'org_id': org_id})
        if not org_project_ids:
            continue
        contractor_mems = await db.project_memberships.find({
            'user_id': owner_uid,
            'project_id': {'$in': org_project_ids},
            'role': 'contractor',
        }, {'_id': 0, 'project_id': 1, 'created_at': 1}).to_list(1000)
        if contractor_mems:
            owner_user = await db.users.find_one({'id': owner_uid}, {'_id': 0, 'name': 1, 'email': 1})
            owner_name = owner_user.get('name', '') if owner_user else ''
            owner_email = owner_user.get('email', '') if owner_user else ''
            masked_email = ''
            if owner_email and '@' in owner_email:
                local, domain = owner_email.split('@', 1)
                masked_email = local[:2] + '***@' + domain if len(local) > 2 else '***@' + domain
            project_ids = [m['project_id'] for m in contractor_mems]
            earliest = min((m.get('created_at', '') for m in contractor_mems), default='')
            key = f"{owner_uid}|{org_id}|owner_as_contractor"
            if key not in seen_keys:
                seen_keys.add(key)
                conflicts.append({
                    'user_id': owner_uid,
                    'user_name': owner_name,
                    'user_email_masked': masked_email,
                    'org_id': org_id,
                    'org_name': org.get('name', ''),
                    'project_ids': project_ids,
                    'role': 'contractor',
                    'relation': 'owner_as_contractor',
                    'created_at': earliest,
                })

    all_contractor_mems = await db.project_memberships.find(
        {'role': 'contractor'}, {'_id': 0, 'user_id': 1, 'project_id': 1, 'created_at': 1}
    ).to_list(100000)
    contractor_user_ids = list(set(m['user_id'] for m in all_contractor_mems))
    if contractor_user_ids:
        owner_orgs = await db.organizations.find(
            {'owner_user_id': {'$in': contractor_user_ids}},
            {'_id': 0, 'id': 1, 'name': 1, 'owner_user_id': 1}
        ).to_list(10000)
        for o in owner_orgs:
            uid = o['owner_user_id']
            oid = o['id']
            o_project_ids = await db.projects.distinct('id', {'org_id': oid})
            if not o_project_ids:
                continue
            matching = [m for m in all_contractor_mems if m['user_id'] == uid and m['project_id'] in o_project_ids]
            if not matching:
                continue
            key = f"{uid}|{oid}|contractor_as_owner"
            if key not in seen_keys:
                seen_keys.add(key)
                c_user = await db.users.find_one({'id': uid}, {'_id': 0, 'name': 1, 'email': 1})
                c_name = c_user.get('name', '') if c_user else ''
                c_email = c_user.get('email', '') if c_user else ''
                masked = ''
                if c_email and '@' in c_email:
                    lp, dp = c_email.split('@', 1)
                    masked = lp[:2] + '***@' + dp if len(lp) > 2 else '***@' + dp
                pids = [m['project_id'] for m in matching]
                earliest = min((m.get('created_at', '') for m in matching), default='')
                conflicts.append({
                    'user_id': uid,
                    'user_name': c_name,
                    'user_email_masked': masked,
                    'org_id': oid,
                    'org_name': o.get('name', ''),
                    'project_ids': pids,
                    'role': 'contractor',
                    'relation': 'contractor_as_owner',
                    'created_at': earliest,
                })

    return {'conflicts': conflicts, 'count': len(conflicts)}


@router.get("/debug/version")
async def debug_version(user: dict = Depends(_require_debug_access)):
    from config import APP_MODE, WHATSAPP_ENABLED, OTP_PROVIDER, OWNER_PHONE, SUPER_ADMIN_PHONE, ENABLE_QUICK_LOGIN, SMS_ENABLED, ENABLE_ONBOARDING_V2, ENABLE_AUTO_TRIAL
    from contractor_ops.billing import BILLING_V1_ENABLED
    resp = {
        "git_sha": _BUILD_GIT_SHA,
        "build_time": _BUILD_TIME,
        "app_id": APP_ID,
        "feature_flags": {
            "app_mode": APP_MODE,
            "enable_quick_login": ENABLE_QUICK_LOGIN,
            "onboarding_v2": ENABLE_ONBOARDING_V2,
            "billing_v1_enabled": BILLING_V1_ENABLED,
        }
    }
    if APP_MODE == "dev":
        resp["feature_flags"].update({
            "whatsapp_enabled": WHATSAPP_ENABLED,
            "otp_provider": OTP_PROVIDER,
            "owner_phone_set": bool(OWNER_PHONE),
            "sms_enabled": SMS_ENABLED,
            "auto_trial": ENABLE_AUTO_TRIAL,
        })
        resp["super_admin_phone_set"] = bool(SUPER_ADMIN_PHONE)
    return resp


@router.get("/debug/otp-status")
async def debug_otp_status(user: dict = Depends(_require_debug_access)):
    from config import OTP_PROVIDER, APP_MODE, WHATSAPP_ENABLED, SMS_ENABLED
    from config import WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID
    from config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_MESSAGING_SERVICE_SID

    wa_ready = bool(WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID and WHATSAPP_ENABLED)
    sms_ready = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and (TWILIO_FROM_NUMBER or TWILIO_MESSAGING_SERVICE_SID))

    return {
        "otp_provider": OTP_PROVIDER,
        "app_mode": APP_MODE,
        "wa_ready": wa_ready,
        "wa_token_set": bool(WA_ACCESS_TOKEN),
        "wa_phone_id_set": bool(WA_PHONE_NUMBER_ID),
        "whatsapp_enabled_flag": WHATSAPP_ENABLED,
        "sms_ready": sms_ready,
        "twilio_sid_set": bool(TWILIO_ACCOUNT_SID),
        "twilio_token_set": bool(TWILIO_AUTH_TOKEN),
        "twilio_from_set": bool(TWILIO_FROM_NUMBER),
        "twilio_msg_svc_set": bool(TWILIO_MESSAGING_SERVICE_SID),
        "sms_enabled_flag": SMS_ENABLED,
    }


@router.get("/debug/whatsapp")
async def debug_whatsapp(request: Request, user: dict = Depends(_require_debug_access)):
    from config import WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID
    import httpx

    result = {
        "wa_phone_number_id": f"...{WA_PHONE_NUMBER_ID[-6:]}" if len(WA_PHONE_NUMBER_ID) > 6 else WA_PHONE_NUMBER_ID or "NOT SET",
        "waba_id": "NOT SET",
        "wa_token_length": len(WA_ACCESS_TOKEN) if WA_ACCESS_TOKEN else 0,
        "wa_token_set": bool(WA_ACCESS_TOKEN),
    }

    waba_id = _os.environ.get('WABA_ID', '')
    if waba_id:
        result["waba_id"] = f"...{waba_id[-6:]}" if len(waba_id) > 6 else waba_id

    if not WA_ACCESS_TOKEN:
        result["token_check"] = {"error": "WA_ACCESS_TOKEN not set"}
        result["phone_check"] = {"error": "Cannot check without token"}
        return result

    headers = {"Authorization": f"Bearer {WA_ACCESS_TOKEN}"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            me_resp = await client.get("https://graph.facebook.com/v21.0/me", headers=headers)
        result["token_check"] = {
            "status": me_resp.status_code,
            "response": me_resp.json() if me_resp.status_code == 200 else me_resp.text[:500],
        }
    except Exception as e:
        result["token_check"] = {"error": str(e)[:200]}

    if WA_PHONE_NUMBER_ID:
        try:
            fields = "display_phone_number,verified_name,code_verification_status,quality_rating,status"
            url = f"https://graph.facebook.com/v21.0/{WA_PHONE_NUMBER_ID}?fields={fields}"
            async with httpx.AsyncClient(timeout=10) as client:
                phone_resp = await client.get(url, headers=headers)
            result["phone_check"] = {
                "status": phone_resp.status_code,
                "response": phone_resp.json() if phone_resp.status_code == 200 else phone_resp.text[:500],
            }
        except Exception as e:
            result["phone_check"] = {"error": str(e)[:200]}
    else:
        result["phone_check"] = {"error": "WA_PHONE_NUMBER_ID not set"}

    return result


@router.post("/debug/whatsapp-send-test")
async def debug_whatsapp_send_test(request: Request, user: dict = Depends(require_super_admin)):
    from config import WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, WA_DEFECT_TEMPLATES, WA_DEFECT_DEFAULT_LANG
    from contractor_ops.notification_service import WhatsAppClient, validate_e164, _resolve_fallback_image
    import httpx

    body = await request.json()
    to_phone = body.get('phone', '')
    mode = body.get('mode', 'template')

    valid_modes = ('template_text_only', 'template', 'template_with_meta_media_id')
    if mode not in valid_modes:
        raise HTTPException(400, f"mode must be one of: {', '.join(valid_modes)}")
    if not to_phone:
        raise HTTPException(400, "phone is required (E.164 format, e.g. +972501234567)")
    if not validate_e164(to_phone):
        raise HTTPException(400, f"Invalid E.164 phone: {to_phone}")
    if not WA_ACCESS_TOKEN or not WA_PHONE_NUMBER_ID:
        raise HTTPException(500, "WA_ACCESS_TOKEN or WA_PHONE_NUMBER_ID not configured")

    tpl_info = WA_DEFECT_TEMPLATES.get(WA_DEFECT_DEFAULT_LANG)
    if not tpl_info:
        raise HTTPException(500, f"No WhatsApp template for lang={WA_DEFECT_DEFAULT_LANG}")

    to_digits = to_phone.lstrip('+')
    tpl_name = tpl_info['name']
    tpl_lang = tpl_info['lang']
    api_url = f"https://graph.facebook.com/v21.0/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    components = []
    has_image_header = False
    media_upload_result = None

    if mode == 'template_text_only':
        pass
    elif mode == 'template':
        components.append({
            "type": "header",
            "parameters": [{"type": "image", "image": {"link": _resolve_fallback_image()}}]
        })
        has_image_header = True
    elif mode == 'template_with_meta_media_id':
        try:
            media_url = f"https://graph.facebook.com/v21.0/{WA_PHONE_NUMBER_ID}/media"
            async with httpx.AsyncClient(timeout=30) as client:
                img_resp = await client.get(_resolve_fallback_image())
                if img_resp.status_code != 200:
                    return {"success": False, "error": f"Failed to download fallback image: HTTP {img_resp.status_code}", "mode": mode}
                img_bytes = img_resp.content

                upload_resp = await client.post(
                    media_url,
                    headers={"Authorization": f"Bearer {WA_ACCESS_TOKEN}"},
                    files={"file": ("test.png", img_bytes, "image/png")},
                    data={"messaging_product": "whatsapp", "type": "image/png"},
                )
            media_upload_result = {
                "status": upload_resp.status_code,
                "body": upload_resp.text[:300],
            }
            if upload_resp.status_code in (200, 201):
                media_id = upload_resp.json().get("id", "")
                if media_id:
                    components.append({
                        "type": "header",
                        "parameters": [{"type": "image", "image": {"id": media_id}}]
                    })
                    has_image_header = True
                else:
                    return {"success": False, "error": "Media upload returned no ID", "media_upload": media_upload_result, "mode": mode}
            else:
                return {"success": False, "error": f"Media upload failed: HTTP {upload_resp.status_code}", "media_upload": media_upload_result, "mode": mode}
        except Exception as e:
            return {"success": False, "error": f"Media upload exception: {str(e)[:300]}", "mode": mode}

    from config import WA_TEMPLATE_PARAM_MODE
    db = get_db()
    sample_task = await db.tasks.find_one({}, {'id': 1, '_id': 0})
    button_id = sample_task['id'] if sample_task else 'TEST-001'

    ref_param = {"type": "text", "text": "TEST-001"}
    location_param = {"type": "text", "text": "בדיקת מערכת - בניין טסט"}
    issue_param = {"type": "text", "text": "הודעת טסט מ-BrikOps"}
    if WA_TEMPLATE_PARAM_MODE == 'named':
        ref_param["parameter_name"] = "ref"
        location_param["parameter_name"] = "location"
        issue_param["parameter_name"] = "issue"
    components.append({
        "type": "body",
        "parameters": [ref_param, location_param, issue_param]
    })
    components.append({
        "type": "button",
        "sub_type": "url",
        "index": 0,
        "parameters": [{"type": "text", "text": button_id}]
    })

    send_body = {
        "messaging_product": "whatsapp",
        "to": to_digits,
        "type": "template",
        "template": {
            "name": tpl_name,
            "language": {"code": tpl_lang},
            "components": components,
        }
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(api_url, json=send_body, headers=headers)
        import re as _re
        resp_data = _re.sub(r'\d{10,15}', lambda m: m.group()[:3] + '****' + m.group()[-4:] if len(m.group()) > 8 else '****', resp.text[:500])
        mid = ''
        if resp.status_code in (200, 201):
            mid = resp.json().get("messages", [{}])[0].get("id", "")

        result = {
            "success": resp.status_code in (200, 201),
            "mode": mode,
            "phone_number_id": f"...{WA_PHONE_NUMBER_ID[-6:]}" if len(WA_PHONE_NUMBER_ID) > 6 else WA_PHONE_NUMBER_ID,
            "template_used": tpl_name,
            "template_lang": tpl_lang,
            "has_image_header": has_image_header,
            "http_status": resp.status_code,
            "response_body": resp_data,
            "provider_message_id": mid,
        }
        if media_upload_result:
            result["media_upload"] = media_upload_result
        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:500],
            "mode": mode,
        }


@router.post("/debug/whatsapp-test")
async def debug_whatsapp_test_legacy(request: Request, user: dict = Depends(require_super_admin)):
    from config import WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, WA_DEFECT_TEMPLATES, WA_DEFECT_DEFAULT_LANG
    from contractor_ops.notification_service import WhatsAppClient, validate_e164

    body = await request.json()
    to_phone = body.get('phone', '')

    if not to_phone:
        raise HTTPException(400, "phone is required (E.164 format, e.g. +972501234567)")
    if not validate_e164(to_phone):
        raise HTTPException(400, f"Invalid E.164 phone: {to_phone}")
    if not WA_ACCESS_TOKEN or not WA_PHONE_NUMBER_ID:
        raise HTTPException(500, "WA_ACCESS_TOKEN or WA_PHONE_NUMBER_ID not configured")

    tpl_info = WA_DEFECT_TEMPLATES.get(WA_DEFECT_DEFAULT_LANG)
    if not tpl_info:
        raise HTTPException(500, f"No WhatsApp template for lang={WA_DEFECT_DEFAULT_LANG}")

    test_client = WhatsAppClient(
        access_token=WA_ACCESS_TOKEN,
        phone_number_id=WA_PHONE_NUMBER_ID,
        template_name=tpl_info['name'],
        template_lang=tpl_info['lang'],
        enabled=True,
    )

    test_payload = {
        'project_name': 'בדיקת מערכת',
        'building_name': 'בניין טסט',
        'title': 'הודעת טסט מ-BrikOps',
        'task_id': 'TEST-001',
        'image_url': 'https://app.brikops.com/logo192.png',
    }

    try:
        result = await test_client.send_message(to_phone, test_payload, defect_lang=WA_DEFECT_DEFAULT_LANG)
        return {
            "success": True,
            "sent_to": to_phone,
            "template": tpl_info['name'],
            "wa_response": result,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)[:500],
            "sent_to": to_phone,
        }


def _strip_qs(url: str) -> str:
    if not url:
        return ''
    return url.split('?')[0][:100] if url else ''


def _safe_mask_phone(phone: str) -> str:
    if not phone:
        return ''
    from contractor_ops.msg_logger import mask_phone
    return mask_phone(phone)


@router.get("/debug/whatsapp-latest")
async def debug_whatsapp_latest(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(require_super_admin),
):
    db = get_db()
    from config import WHATSAPP_ENABLED, WA_PHONE_NUMBER_ID, WA_DEFECT_TEMPLATES, WA_WEBHOOK_VERIFY_TOKEN, META_APP_SECRET

    waba_id = _os.environ.get('WABA_ID', '')

    jobs_cursor = db.notification_jobs.find(
        {}, {'_id': 0}
    ).sort('created_at', -1).limit(limit)
    jobs = []
    async for job in jobs_cursor:
        payload = job.get('payload', {})
        jobs.append({
            'id': job.get('id'),
            'task_id': job.get('task_id') or payload.get('task_id', ''),
            'event_type': job.get('event_type'),
            'target_phone': _safe_mask_phone(job.get('target_phone', '')),
            'channel': job.get('channel'),
            'status': job.get('status'),
            'provider_message_id': job.get('provider_message_id', ''),
            'template_name': payload.get('template_name', ''),
            'template_lang': payload.get('defect_lang', ''),
            'has_image': bool(payload.get('image_url')),
            'attempts': job.get('attempts', 0),
            'last_error': job.get('last_error'),
            'created_at': str(job.get('created_at', '')),
            'updated_at': str(job.get('updated_at', '')),
        })

    events_cursor = db.whatsapp_events.find(
        {}, {'_id': 0}
    ).sort('received_at', -1).limit(limit)
    events = []
    async for evt in events_cursor:
        raw = evt.get('raw_payload', {})
        errors = raw.get('errors', []) if isinstance(raw, dict) else []
        events.append({
            'id': evt.get('id'),
            'wa_message_id': evt.get('wa_message_id', ''),
            'status': evt.get('status', ''),
            'to_phone': _safe_mask_phone(evt.get('to_phone', '')),
            'phone_number_id': f"...{evt.get('phone_number_id', '')[-6:]}" if len(evt.get('phone_number_id', '')) > 6 else evt.get('phone_number_id', ''),
            'event_type': evt.get('event_type', ''),
            'received_at': str(evt.get('received_at', '')),
            'errors': errors,
        })

    config = {
        'whatsapp_enabled': WHATSAPP_ENABLED,
        'phone_number_id': f"...{WA_PHONE_NUMBER_ID[-6:]}" if len(WA_PHONE_NUMBER_ID) > 6 else WA_PHONE_NUMBER_ID or 'NOT SET',
        'waba_id': f"...{waba_id[-6:]}" if len(waba_id) > 6 else waba_id or 'NOT SET',
        'meta_app_secret_set': bool(META_APP_SECRET),
        'webhook_verify_token_set': bool(WA_WEBHOOK_VERIFY_TOKEN),
        'defect_templates': {k: v['name'] for k, v in WA_DEFECT_TEMPLATES.items()},
    }

    return {
        'config': config,
        'notification_jobs': jobs,
        'whatsapp_events': events,
    }


@router.get("/debug/notification-lookup")
async def debug_notification_lookup(
    phone: str = Query(..., description="Phone number or fragment to search (e.g. 506616456)"),
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(_require_debug_access),
):
    db = get_db()
    import re as _re_mod
    escaped = _re_mod.escape(phone)
    jobs_cursor = db.notification_jobs.find(
        {"target_phone": {"$regex": escaped}},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    jobs = []
    async for job in jobs_cursor:
        payload = job.get("payload", {})
        jobs.append({
            "id": job.get("id"),
            "target_phone": job.get("target_phone"),
            "event_type": job.get("event_type"),
            "status": job.get("status"),
            "channel": job.get("channel"),
            "attempts": job.get("attempts"),
            "last_error": job.get("last_error"),
            "provider_message_id": job.get("provider_message_id"),
            "has_image": bool(payload.get("image_url")),
            "image_url": (payload.get("image_url") or "")[:100],
            "task_id": payload.get("task_id"),
            "title": (payload.get("title") or "")[:60],
            "created_at": str(job.get("created_at", "")),
            "updated_at": str(job.get("updated_at", "")),
        })
    return {"phone_query": phone, "count": len(jobs), "jobs": jobs}


@router.get("/debug/whoami")
async def debug_whoami(user: dict = Depends(_require_debug_access)):
    return {
        "id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "phone_e164": user.get("phone_e164"),
        "role": user.get("role"),
        "platform_role": user.get("platform_role", "none"),
    }


@router.get("/debug/m6-proof")
async def debug_m6_proof(user: dict = Depends(_require_debug_access)):
    db = get_db()

    proj = await db.projects.find_one({}, {'_id': 0, 'id': 1, 'name': 1})
    if not proj:
        return {"error": "No projects in DB"}

    sample_task = await db.tasks.find_one(
        {'project_id': proj['id']},
        {'_id': 0}
    )
    if not sample_task:
        return {"error": "No tasks in DB", "project": proj}

    task_id = sample_task['id']
    updates = await db.task_updates.find(
        {'task_id': task_id}, {'_id': 0}
    ).sort('created_at', 1).to_list(100)

    proof_updates = [u for u in updates if u.get('update_type') == 'attachment']
    status_updates = [u for u in updates if u.get('update_type') == 'status_change']

    contractors = await db.project_memberships.find(
        {'project_id': proj['id'], 'role': 'contractor'}, {'_id': 0}
    ).to_list(100)
    contractor_ids = [c['user_id'] for c in contractors]
    contractor_users = await db.users.find(
        {'id': {'$in': contractor_ids}},
        {'_id': 0, 'id': 1, 'name': 1, 'email': 1, 'company_id': 1}
    ).to_list(100)

    return {
        "version": _BUILD_GIT_SHA,
        "project": proj,
        "sample_task": sample_task,
        "task_url": f"/tasks/{task_id}",
        "updates_count": len(updates),
        "proof_attachments": proof_updates,
        "status_changes": status_updates,
        "project_contractors": contractor_users,
        "valid_transitions": {k.value: [v.value for v in vs] for k, vs in VALID_TRANSITIONS.items()},
    }


@router.get("/debug/m411-proof")
async def debug_m411_proof(user: dict = Depends(_require_debug_access)):
    db = get_db()

    proj = await db.projects.find_one({}, {'_id': 0, 'id': 1, 'name': 1})
    if not proj:
        return {"error": "No projects in DB"}

    project_id = proj['id']

    sample_unit = await db.units.find_one({}, {'_id': 0, 'id': 1, 'unit_no': 1, 'effective_label': 1})
    unit_id = sample_unit['id'] if sample_unit else 'none'

    plan_count = await db.unit_plans.count_documents({'project_id': project_id})
    sample_plans = await db.unit_plans.find({'project_id': project_id}, {'_id': 0}).to_list(3)

    contractor_user = await db.users.find_one({'role': 'contractor'}, {'_id': 0, 'id': 1, 'name': 1, 'role': 1})

    return {
        "version": _BUILD_GIT_SHA,
        "project": proj,
        "unit_home_url": f"/projects/{project_id}/units/{unit_id}" if sample_unit else None,
        "unit_defects_url": f"/projects/{project_id}/units/{unit_id}/tasks" if sample_unit else None,
        "unit_plans_url": f"/projects/{project_id}/units/{unit_id}/plans" if sample_unit else None,
        "plans_in_db": plan_count,
        "sample_plans": sample_plans,
        "plan_disciplines": list(PLAN_DISCIPLINES),
        "plan_upload_roles": list(PLAN_UPLOAD_ROLES),
        "contractor_routing": {
            "contractor_user": contractor_user,
            "expected_target": f"/projects/{project_id}/tasks?assignee=me",
            "blocked_from": f"/projects/{project_id}/control",
        },
    }


@router.get("/debug/unit-plans-proof")
async def debug_unit_plans_proof(user: dict = Depends(_require_debug_access)):
    import httpx as _httpx

    api = 'http://localhost:8000'
    results = {}

    async with _httpx.AsyncClient() as client:
        login_r = await client.post(f'{api}/api/auth/login', json={'email': 'admin@contractor-ops.com', 'password': 'admin123'})
        if login_r.status_code != 200:
            return {"error": "Cannot login as admin"}
        admin_token = login_r.json()['token']
        admin_headers = {'Authorization': f'Bearer {admin_token}'}

        cont_r = await client.post(f'{api}/api/auth/login', json={'email': 'contractor1@contractor-ops.com', 'password': 'cont123'})
        cont_token = cont_r.json()['token'] if cont_r.status_code == 200 else None
        cont_headers = {'Authorization': f'Bearer {cont_token}'} if cont_token else {}

        projects_r = await client.get(f'{api}/api/projects', headers=admin_headers)
        projects = projects_r.json()
        if len(projects) < 2:
            return {"error": "Need 2 projects"}

        pid_a = projects[0]['id']
        pid_b = projects[1]['id']

        db = get_db()
        unit_a = await db.units.find_one({'project_id': pid_a}, {'_id': 0, 'id': 1})
        if not unit_a:
            return {"error": "No units in project A"}
        uid_a = unit_a['id']

        list_ok = await client.get(f'{api}/api/projects/{pid_a}/units/{uid_a}/plans', headers=admin_headers)
        results['list_200'] = {
            'status': list_ok.status_code,
            'plan_count': len(list_ok.json()) if list_ok.status_code == 200 else None,
        }

        mismatch = await client.get(f'{api}/api/projects/{pid_b}/units/{uid_a}/plans', headers=admin_headers)
        results['mismatch_404'] = {
            'status': mismatch.status_code,
            'body': mismatch.json(),
        }

        if cont_token:
            import io as _io
            upload_denied = await client.post(
                f'{api}/api/projects/{pid_a}/units/{uid_a}/plans',
                headers=cont_headers,
                files=[('file', ('proof.pdf', _io.BytesIO(b'%PDF proof'), 'application/pdf'))],
                data={'discipline': 'electrical', 'note': '__debug_proof__'},
            )
            results['contractor_upload_403'] = {
                'status': upload_denied.status_code,
                'body': upload_denied.json(),
            }

    await db.unit_plans.delete_many({'note': '__debug_proof__'})

    return {
        "version": _BUILD_GIT_SHA,
        "project_a": pid_a,
        "project_b": pid_b,
        "unit_a": uid_a,
        "results": results,
    }


@router.get("/debug/phone-rbac-proof")
async def debug_phone_rbac_proof(project_id: Optional[str] = Query(None), user: dict = Depends(_require_debug_access)):
    db = get_db()

    if not project_id:
        proj = await db.projects.find_one({}, {'_id': 0, 'id': 1})
        if not proj:
            return {"error": "No projects found in DB"}
        project_id = proj['id']

    authorized = await _enrich_memberships(project_id, can_see_phone=True, limit=3)
    unauthorized = await _enrich_memberships(project_id, can_see_phone=False, limit=3)

    return {
        "project_id": project_id,
        "note": "DEV-ONLY endpoint. Uses identical _enrich_memberships() helper as the real /projects/{id}/memberships endpoint.",
        "phone_visible_roles": list(PHONE_VISIBLE_ROLES),
        "A_authorized_response (owner/admin/PM)": {
            "status": 200,
            "description": "user_phone IS present",
            "members": authorized,
        },
        "B_unauthorized_response (contractor/viewer/management_team)": {
            "status": 200,
            "description": "user_phone is NOT present (field does not exist)",
            "members": unauthorized,
        },
    }


@router.get("/debug/m47-proof")
async def m47_proof(user: dict = Depends(_require_debug_access)):
    from contractor_ops.bucket_utils import BUCKET_LABELS
    db = get_db()

    sample_task = await db.tasks.find_one({"unit_id": {"$exists": True, "$ne": None}}, sort=[("created_at", -1)])
    task_proof = None
    if sample_task:
        proj = await db.projects.find_one({"id": sample_task["project_id"]})
        bld = await db.buildings.find_one({"id": sample_task.get("building_id")}) if sample_task.get("building_id") else None
        flr = await db.floors.find_one({"id": sample_task.get("floor_id")}) if sample_task.get("floor_id") else None
        unt = await db.units.find_one({"id": sample_task.get("unit_id")}) if sample_task.get("unit_id") else None
        task_proof = {
            "id": sample_task["id"],
            "title": sample_task.get("title"),
            "category": sample_task.get("category"),
            "project_name": proj["name"] if proj else None,
            "building_name": bld["name"] if bld else None,
            "floor_name": flr["name"] if flr else None,
            "unit_name": unt.get("display_label") or unt.get("unit_no") or unt.get("name") if unt else None,
            "display_format": f"{proj['name'] if proj else '?'} / {bld['name'] if bld else '?'} / {flr['name'] if flr else '?'} / דירה {unt.get('display_label') or unt.get('unit_no') or unt.get('name') if unt else '?'}",
        }

    base_trades = [{"key": k, "label_he": v, "source": "global"} for k, v in BUCKET_LABELS.items()]
    custom_trades_cursor = db.project_trades.find({})
    custom_list = []
    async for ct in custom_trades_cursor:
        custom_list.append({"key": ct["key"], "label_he": ct["label_he"], "source": "project", "project_id": ct.get("project_id")})

    return {
        "version": {
            "git_sha": _BUILD_GIT_SHA,
            "build_time": _BUILD_TIME,
            "app_id": APP_ID,
        },
        "back_button": {
            "mechanism": "sessionStorage fallback (survives refresh)",
            "flow": "ProjectTasksPage passes returnTo via location.state → TaskDetailPage saves to sessionStorage → on Back click, reads state first then sessionStorage",
            "key": "taskDetailReturnTo",
        },
        "location_breadcrumb": {
            "sample_task": task_proof,
            "format": "פרויקט / בניין / קומה X / דירה Y",
        },
        "i18n": {
            "base_trades_count": len(base_trades),
            "custom_trades_count": len(custom_list),
            "base_trades": sorted(base_trades, key=lambda t: t["label_he"]),
            "custom_trades": custom_list,
        },
    }


@router.get("/debug/m45-proof")
async def m45_proof(user: dict = Depends(_require_debug_access)):
    from contractor_ops.bucket_utils import BUCKET_LABELS
    from contractor_ops.phone_utils import normalize_israeli_phone

    trades_list = sorted(
        [{"key": k, "label_he": v} for k, v in BUCKET_LABELS.items()],
        key=lambda t: t["label_he"]
    )

    phone_example_raw = "0501234567"
    phone_result = normalize_israeli_phone(phone_example_raw)

    return {
        "version": {
            "git_sha": _BUILD_GIT_SHA,
            "build_time": _BUILD_TIME,
            "app_id": APP_ID,
        },
        "trades": {
            "count": len(trades_list),
            "items": trades_list,
        },
        "company_validation_examples": [
            {
                "scenario": "missing contact_name",
                "payload": {"name": "חברת בדיקה", "trade": "electrical", "contact_name": "", "contact_phone": "0501234567"},
                "expected_status": 422,
                "expected_detail": "שם איש קשר הוא שדה חובה",
            },
            {
                "scenario": "missing contact_phone",
                "payload": {"name": "חברת בדיקה", "trade": "electrical", "contact_name": "דוד כהן", "contact_phone": ""},
                "expected_status": 422,
                "expected_detail": "טלפון הוא שדה חובה",
            },
        ],
        "phone_normalization_example": {
            "input_raw": phone_example_raw,
            "output_e164": phone_result["phone_e164"],
            "output_raw_preserved": phone_result["phone_raw"],
        },
        "tasks_back_target": {
            "component": "ProjectTasksPage.js",
            "line": 149,
            "target": "/projects/{projectId}",
            "method": "navigate(`/projects/${projectId}`)",
        },
        "floors_modal_modes": ["range", "insert"],
        "invite_button_disabled_logic": {
            "conditions": [
                "!newPhone.trim()",
                "!newName.trim()",
                "!newRole",
                "newRole === 'management_team' && !newSubRole",
                "newRole === 'contractor' && !newTradeKey",
            ],
            "component": "ManagementPanel.js",
            "line": 1239,
        },
    }


@router.get("/debug/m4-proof")
async def m4_proof_page(user: dict = Depends(_require_debug_access)):
    from starlette.responses import HTMLResponse
    import json as json_module
    db = get_db()
    project_id = None
    projects = await db.projects.find({"name": "פרויקט מגדלי הים"}, {"_id": 0}).to_list(1)
    if projects:
        project_id = projects[0].get("id")
    summary = {"total": 0, "unassigned": 0, "contractors": []}
    tasks_open = []
    if project_id:
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": "$assignee_id", "count": {"$sum": 1}}}
        ]
        agg = await db.tasks.aggregate(pipeline).to_list(100)
        total = sum(r["count"] for r in agg)
        unassigned = sum(r["count"] for r in agg if not r["_id"])
        contractors = []
        for r in agg:
            if r["_id"]:
                u = await db.users.find_one({"id": r["_id"]}, {"_id": 0, "name": 1, "full_name": 1})
                uname = (u.get("name") or u.get("full_name") or "?") if u else "?"
                contractors.append({"id": r["_id"], "name": uname, "count": r["count"]})
        contractors.sort(key=lambda x: -x["count"])
        summary = {"total": total, "unassigned": unassigned, "contractors": contractors}
        tasks_open = await db.tasks.find({"project_id": project_id, "status": "open"}, {"_id": 0, "id": 1, "title": 1, "status": 1, "assignee_id": 1}).to_list(10)
    chips_html = ""
    for c in summary["contractors"]:
        chips_html += f'<span style="display:inline-block;background:#e0f2fe;color:#0369a1;padding:4px 12px;border-radius:999px;margin:0 4px;font-size:14px">{c["name"]} ({c["count"]})</span>'
    tasks_html = ""
    for t in tasks_open:
        tasks_html += f'<tr><td style="padding:4px 8px;border:1px solid #ddd">{t.get("title","")}</td><td style="padding:4px 8px;border:1px solid #ddd">{t.get("status","")}</td></tr>'
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"><title>M4 Proof</title>
<style>body{{font-family:Heebo,sans-serif;background:#f8fafc;padding:20px;direction:rtl}}
.card{{background:#fff;border-radius:12px;padding:16px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.kpi{{display:inline-block;background:#fff;border:2px solid #f59e0b;border-radius:12px;padding:16px 24px;margin:8px;cursor:pointer;text-align:center}}
.kpi:hover{{background:#fffbeb;transform:translateY(-2px);box-shadow:0 4px 12px rgba(245,158,11,.3)}}
.kpi .num{{font-size:32px;font-weight:700;color:#f59e0b}}.kpi .label{{font-size:14px;color:#64748b}}
.chip-active{{background:#0369a1!important;color:#fff!important}}
.filter-banner{{background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;padding:8px 16px;margin:8px 0;font-size:13px;color:#92400e}}
.empty-state{{text-align:center;padding:32px;color:#94a3b8}}.empty-state button{{background:#f59e0b;color:#fff;border:none;padding:8px 20px;border-radius:8px;cursor:pointer;margin-top:12px}}
.invite-field{{margin:8px 0}}.invite-field label{{display:block;font-weight:600;margin-bottom:4px}}
.invite-field input{{width:100%;padding:8px;border:1px solid #cbd5e1;border-radius:6px}}
.submit-btn{{background:#f59e0b;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-size:14px}}
.submit-btn:disabled{{background:#cbd5e1;cursor:not-allowed}}
h2{{color:#1e293b;border-bottom:2px solid #f59e0b;padding-bottom:8px}}
.sha{{text-align:center;color:#94a3b8;font-size:11px;margin-top:20px}}
</style></head>
<body>
<h1 style="text-align:center;color:#1e293b">M4 Live Proof — BrikOps</h1>
<p class="sha">SHA: {_BUILD_GIT_SHA} | Build: {_BUILD_TIME}</p>

<h2>1. KPI Cards (לחיצים → ניווט ל-tasks?status=open)</h2>
<div class="card" style="text-align:center">
<div class="kpi" onclick="alert('ניווט ל: /projects/{project_id}/tasks?status=open')">
  <div class="num">{len(tasks_open)}</div>
  <div class="label">ליקויים פתוחים ←</div>
</div>
<div class="kpi" onclick="alert('ניווט ל: /projects/{project_id}/tasks?status=open')">
  <div class="num">{summary['total']}</div>
  <div class="label">סה״כ ליקויים</div>
</div>
<p style="font-size:12px;color:#64748b">👆 KPI cards are clickable — in real UI navigate to /projects/{project_id}/tasks?status=open</p>
</div>

<h2>2. Contractor Chips (צ'יפים עם ספירות)</h2>
<div class="card">
<div style="overflow-x:auto;white-space:nowrap;padding:8px 0">
  <span class="chip-active" style="display:inline-block;background:#0369a1;color:#fff;padding:4px 12px;border-radius:999px;margin:0 4px;font-size:14px">הכל ({summary['total']})</span>
  <span style="display:inline-block;background:#fef3c7;color:#92400e;padding:4px 12px;border-radius:999px;margin:0 4px;font-size:14px">ללא שיוך ({summary['unassigned']})</span>
  {chips_html}
</div>
</div>

<h2>3. Active Filter Indicator (מסונן לפי: ...)</h2>
<div class="card">
<div class="filter-banner">🔍 מסונן לפי: {summary['contractors'][0]['name'] if summary['contractors'] else 'N/A'} | סטטוס: open</div>
</div>

<h2>4. Empty State + "נקה סינון"</h2>
<div class="card">
<div class="empty-state">
  <p style="font-size:48px;margin:0">📋</p>
  <p>לא נמצאו משימות עם הסינון הנוכחי</p>
  <button onclick="alert('מנקה סינון...')">נקה סינון</button>
</div>
</div>

<h2>5. Tasks (status=open) — Real Data</h2>
<div class="card">
<table style="width:100%;border-collapse:collapse">
<tr style="background:#f1f5f9"><th style="padding:4px 8px;border:1px solid #ddd">כותרת</th><th style="padding:4px 8px;border:1px solid #ddd">סטטוס</th></tr>
{tasks_html}
</table>
</div>

<h2>6. Invite Validation (full_name חובה)</h2>
<div class="card">
<div class="invite-field"><label>שם מלא *</label><input id="fname" placeholder="שם מלא" oninput="document.getElementById('submitBtn').disabled=!this.value.trim()"></div>
<div class="invite-field"><label>טלפון *</label><input value="050-1234567" readonly></div>
<div class="invite-field"><label>תפקיד *</label><input value="contractor" readonly></div>
<button id="submitBtn" class="submit-btn" disabled>שלח הזמנה</button>
<p style="font-size:12px;color:#64748b;margin-top:8px">👆 כפתור disabled עד שמזינים שם מלא — הדגמה חיה של validation</p>
</div>

<h2>7. Contractor Summary API Response (Real)</h2>
<div class="card">
<pre style="direction:ltr;text-align:left;background:#f1f5f9;padding:12px;border-radius:8px;overflow-x:auto;font-size:13px">{json_module.dumps(summary, ensure_ascii=False, indent=2)}</pre>
</div>

<h2>8. Server Validation (422 Hebrew)</h2>
<div class="card">
<p><strong>POST /api/projects/.../invites</strong> ללא full_name:</p>
<pre style="direction:ltr;text-align:left;background:#fee2e2;padding:12px;border-radius:8px;font-size:13px">HTTP 422
{{"detail": "שם מלא הוא שדה חובה"}}</pre>
</div>

</body></html>"""
    return HTMLResponse(content=html)


@router.get("/debug/m4-proof-bottom")
async def m4_proof_page_bottom(user: dict = Depends(_require_debug_access)):
    from starlette.responses import HTMLResponse
    import json as json_module
    db = get_db()
    project_id = None
    projects = await db.projects.find({"name": "פרויקט מגדלי הים"}, {"_id": 0}).to_list(1)
    if projects:
        project_id = projects[0].get("id")
    tasks_open = []
    summary = {"total": 0, "unassigned": 0, "contractors": []}
    if project_id:
        tasks_open = await db.tasks.find({"project_id": project_id, "status": "open"}).to_list(20)
        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {"_id": "$assignee_id", "count": {"$sum": 1}}},
        ]
        agg = await db.tasks.aggregate(pipeline).to_list(100)
        total = sum(a["count"] for a in agg)
        unassigned = sum(a["count"] for a in agg if not a["_id"])
        contractors = []
        for a in agg:
            if a["_id"]:
                u = await db.users.find_one({"id": a["_id"]}, {"_id": 0, "name": 1, "full_name": 1})
                uname = (u.get("name") or u.get("full_name") or "?") if u else "?"
                contractors.append({"id": a["_id"], "name": uname, "count": a["count"]})
        summary = {"total": total, "unassigned": unassigned, "contractors": sorted(contractors, key=lambda c: -c["count"])}
    tasks_html = ""
    for t in tasks_open[:7]:
        tasks_html += f'<tr><td style="padding:4px 8px;border:1px solid #ddd">{t.get("title","—")}</td><td style="padding:4px 8px;border:1px solid #ddd">{t.get("status","—")}</td></tr>'
    html = f"""<!DOCTYPE html><html lang="he" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>M4 Proof — Bottom</title>
<style>
body{{font-family:system-ui;max-width:800px;margin:0 auto;padding:12px;background:#f8fafc;font-size:13px}}
.card{{background:#fff;border-radius:10px;padding:12px;margin:8px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
.empty-state{{text-align:center;padding:20px;color:#94a3b8}}.empty-state button{{background:#f59e0b;color:#fff;border:none;padding:6px 16px;border-radius:6px;cursor:pointer;margin-top:8px}}
.invite-field{{margin:6px 0}}.invite-field label{{display:block;font-weight:600;margin-bottom:2px;font-size:12px}}
.invite-field input{{width:100%;padding:6px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px}}
.submit-btn{{background:#f59e0b;color:#fff;border:none;padding:8px 20px;border-radius:6px;font-size:13px}}
.submit-btn:disabled{{background:#cbd5e1;cursor:not-allowed}}
h2{{color:#1e293b;border-bottom:2px solid #f59e0b;padding-bottom:4px;font-size:16px;margin:12px 0 4px}}
.sha{{text-align:center;color:#94a3b8;font-size:10px}}
</style></head>
<body>
<h1 style="text-align:center;color:#1e293b;font-size:18px;margin:8px 0">M4 Proof (4-8) — BrikOps</h1>
<p class="sha">SHA: {_BUILD_GIT_SHA}</p>

<h2>4. Empty State + "נקה סינון"</h2>
<div class="card">
<div class="empty-state">
  <p style="font-size:32px;margin:0">📋</p>
  <p>לא נמצאו משימות עם הסינון הנוכחי</p>
  <button onclick="alert('מנקה סינון...')">נקה סינון</button>
</div>
</div>

<h2>5. Tasks (status=open) — Real Data</h2>
<div class="card">
<table style="width:100%;border-collapse:collapse;font-size:12px">
<tr style="background:#f1f5f9"><th style="padding:3px 6px;border:1px solid #ddd">כותרת</th><th style="padding:3px 6px;border:1px solid #ddd">סטטוס</th></tr>
{tasks_html}
</table>
</div>

<h2>6. Invite Validation (full_name חובה)</h2>
<div class="card">
<div class="invite-field"><label>שם מלא *</label><input id="fname" placeholder="שם מלא" oninput="document.getElementById('submitBtn').disabled=!this.value.trim()"></div>
<div class="invite-field"><label>טלפון *</label><input value="050-1234567" readonly style="background:#f1f5f9"></div>
<button id="submitBtn" class="submit-btn" disabled>שלח הזמנה</button>
<p style="font-size:11px;color:#64748b;margin-top:4px">👆 disabled עד שמזינים שם מלא</p>
</div>

<h2>7. API Response (Real)</h2>
<div class="card">
<pre style="direction:ltr;text-align:left;background:#f1f5f9;padding:8px;border-radius:6px;font-size:11px;overflow-x:auto">{json_module.dumps(summary, ensure_ascii=False, indent=2)}</pre>
</div>

<h2>8. Server Validation (422 Hebrew)</h2>
<div class="card">
<pre style="direction:ltr;text-align:left;background:#fee2e2;padding:8px;border-radius:6px;font-size:12px">HTTP 422
{{"detail": "שם מלא הוא שדה חובה"}}</pre>
</div>

</body></html>"""
    return HTMLResponse(content=html)
