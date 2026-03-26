import hashlib
import os
import secrets
import uuid
import logging
import re
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from contractor_ops.phone_utils import normalize_israeli_phone
from contractor_ops.billing import get_user_org, get_effective_access
from contractor_ops.msg_logger import log_msg_delivery, log_msg_queued, mask_phone, DeliveryTimer

logger = logging.getLogger(__name__)

TRANSFER_EXPIRY_HOURS = 48
INITIATE_COOLDOWN_SECONDS = 60
ACCEPT_MAX_ATTEMPTS = 5

_db_ref = None
_sms_client_ref = None
_otp_service_ref = None


def set_transfer_db(db):
    global _db_ref
    _db_ref = db


def set_transfer_sms_client(sms_client):
    global _sms_client_ref
    _sms_client_ref = sms_client


def set_transfer_otp_service(otp_service):
    global _otp_service_ref
    _otp_service_ref = otp_service


def _get_db():
    if _db_ref is None:
        raise RuntimeError("Ownership transfer DB not initialized")
    return _db_ref


def _now():
    return datetime.now(timezone.utc).isoformat()


def _now_dt():
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _normalize_org_name(name: str) -> str:
    return re.sub(r'\s+', ' ', name.strip())


def _get_base_url():
    import os
    url = os.environ.get('PUBLIC_APP_URL', '').rstrip('/')
    if url:
        return url
    raw = os.environ.get('REPLIT_DOMAINS', os.environ.get('REPLIT_DEV_DOMAIN', ''))
    if raw:
        if ',' in raw:
            raw = raw.split(',')[0]
        return f"https://{raw}"
    return ''


async def _audit(entity_type, entity_id, action, actor_id, payload):
    db = _get_db()
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': entity_type,
        'entity_id': entity_id,
        'action': action,
        'actor_id': actor_id,
        'payload': payload,
        'created_at': _now(),
    })


async def _send_transfer_notification(target_phone, org_name, initiator_name, accept_link, request_id):
    rid = str(uuid.uuid4())[:8]
    phone_masked = mask_phone(target_phone)

    sms_text = (
        f"בקשת העברת בעלות על הארגון: {org_name}\n"
        f"נשלחה על ידי: {initiator_name}\n"
        f"לאישור העברה: {accept_link}\n"
        f"תוקף: 48 שעות"
    )

    log_msg_queued(msg_type="ownership_transfer", rid=rid, phone_masked=phone_masked)

    notification_status = {
        'channel_used': 'none',
        'delivery_status': 'not_attempted',
        'rid': rid,
    }

    sms_client = _sms_client_ref
    if not sms_client or not sms_client.enabled:
        log_msg_delivery(msg_type="ownership_transfer", rid=rid, channel="none", result="failed",
                         error_code="sms_disabled", phone_masked=phone_masked)
        notification_status['delivery_status'] = 'failed'
        notification_status['error'] = 'sms_disabled'
        return notification_status

    timer = DeliveryTimer()
    try:
        sms_result = await sms_client.send_sms(
            target_phone, sms_text, context=f'ownership_transfer:{request_id}'
        )
        elapsed = timer.elapsed_ms()

        if sms_result.get('status') == 'sent':
            log_msg_delivery(msg_type="ownership_transfer", rid=rid, channel="sms", result="sent",
                             external_ms=elapsed, provider_status=sms_result.get('provider_message_id', ''),
                             phone_masked=phone_masked)
            notification_status['channel_used'] = 'sms'
            notification_status['delivery_status'] = 'sent'
            notification_status['provider_message_id'] = sms_result.get('provider_message_id', '')
        else:
            log_msg_delivery(msg_type="ownership_transfer", rid=rid, channel="sms", result="failed",
                             external_ms=elapsed, error_code=sms_result.get('error', ''),
                             phone_masked=phone_masked)
            notification_status['channel_used'] = 'sms'
            notification_status['delivery_status'] = 'failed'
            notification_status['error'] = sms_result.get('error', '')
    except Exception as e:
        log_msg_delivery(msg_type="ownership_transfer", rid=rid, channel="sms", result="failed",
                         error_code=str(e), phone_masked=phone_masked)
        notification_status['delivery_status'] = 'failed'
        notification_status['error'] = str(e)

    return notification_status


async def ensure_indexes(db):
    try:
        await db.ownership_transfer_requests.create_index('token_hash', unique=True)
        await db.ownership_transfer_requests.create_index(
            [('org_id', 1), ('status', 1)],
        )
        await db.ownership_transfer_requests.create_index(
            'expires_at', expireAfterSeconds=0
        )
        logger.info("Ownership transfer indexes ensured")
    except Exception as e:
        logger.warning(f"Ownership transfer index creation: {e}")


def create_transfer_router(get_current_user):
    router = APIRouter(prefix="/api/org/transfer", tags=["ownership-transfer"])

    @router.post("/initiate")
    async def initiate_transfer(body: dict, user: dict = Depends(get_current_user)):
        db = _get_db()

        org = await get_user_org(user['id'])
        if not org:
            raise HTTPException(status_code=404, detail='לא נמצא ארגון')

        if org.get('owner_user_id') != user['id']:
            raise HTTPException(status_code=403, detail='רק בעל הארגון יכול להעביר בעלות')

        phone_raw = body.get('target_phone', '').strip()
        if not phone_raw:
            raise HTTPException(status_code=400, detail='מספר טלפון נדרש')

        try:
            norm = normalize_israeli_phone(phone_raw)
            target_phone = norm['phone_e164']
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))

        owner_phone = user.get('phone_e164', '')
        if target_phone == owner_phone:
            raise HTTPException(status_code=409, detail='לא ניתן להעביר בעלות לעצמך')

        existing = await db.ownership_transfer_requests.find_one(
            {'org_id': org['id'], 'status': 'pending'}, {'_id': 0}
        )
        if existing:
            raise HTTPException(status_code=409, detail={
                'message': 'כבר קיימת בקשת העברה פעילה',
                'target_phone_masked': mask_phone(existing.get('target_phone_e164', '')),
                'created_at': existing.get('created_at', ''),
                'expires_at': existing.get('expires_at', ''),
                'request_id': existing.get('id', ''),
            })

        recent = await db.ownership_transfer_requests.find_one(
            {'org_id': org['id'], 'initiator_user_id': user['id']},
            sort=[('created_at', -1)]
        )
        if recent and recent.get('created_at'):
            created = recent['created_at']
            if isinstance(created, str):
                created = datetime.fromisoformat(created.replace('Z', '+00:00'))
            if isinstance(created, datetime):
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                diff = (_now_dt() - created).total_seconds()
                if diff < INITIATE_COOLDOWN_SECONDS:
                    remaining = int(INITIATE_COOLDOWN_SECONDS - diff)
                    raise HTTPException(status_code=429, detail=f'נסה שוב בעוד {remaining} שניות')

        ts = _now()
        request_id = str(uuid.uuid4())
        token_plaintext = secrets.token_urlsafe(32)
        token_hash = _hash_token(token_plaintext)
        expires_at = (_now_dt() + timedelta(hours=TRANSFER_EXPIRY_HOURS)).isoformat()

        await db.ownership_transfer_requests.insert_one({
            'id': request_id,
            'org_id': org['id'],
            'org_name': org.get('name', ''),
            'initiator_user_id': user['id'],
            'initiator_name': user.get('name', ''),
            'target_phone_e164': target_phone,
            'token_hash': token_hash,
            'status': 'pending',
            'accept_attempts': 0,
            'expires_at': expires_at,
            'created_at': ts,
            'accepted_at': None,
            'completed_at': None,
            'cancelled_at': None,
        })

        base = _get_base_url()
        accept_link = f"{base}/org/transfer/{token_plaintext}" if base else ""

        notification_status = await _send_transfer_notification(
            target_phone=target_phone,
            org_name=org.get('name', ''),
            initiator_name=user.get('name', ''),
            accept_link=accept_link,
            request_id=request_id,
        )

        await _audit('organization', org['id'], 'ownership_transfer_initiated', user['id'], {
            'org_id': org['id'],
            'org_name': org.get('name', ''),
            'request_id': request_id,
            'target_phone_masked': mask_phone(target_phone),
            'expires_at': expires_at,
        })

        logger.info(f"[TRANSFER] initiated org={org['id']} by={user['id']} target={mask_phone(target_phone)} request={request_id}")

        resp = {
            'success': True,
            'request_id': request_id,
            'target_phone_masked': mask_phone(target_phone),
            'expires_at': expires_at,
            'notification_status': notification_status,
        }
        if os.environ.get('APP_MODE', 'dev') == 'dev':
            resp['_debug_token'] = token_plaintext
        return resp

    @router.post("/cancel")
    async def cancel_transfer(body: dict, user: dict = Depends(get_current_user)):
        db = _get_db()

        org = await get_user_org(user['id'])
        if not org:
            raise HTTPException(status_code=404, detail='לא נמצא ארגון')

        if org.get('owner_user_id') != user['id']:
            raise HTTPException(status_code=403, detail='רק בעל הארגון יכול לבטל')

        request_id = body.get('request_id', '').strip()
        if not request_id:
            raise HTTPException(status_code=400, detail='מזהה בקשה נדרש')

        result = await db.ownership_transfer_requests.find_one_and_update(
            {'id': request_id, 'org_id': org['id'], 'status': 'pending'},
            {'$set': {'status': 'cancelled', 'cancelled_at': _now()}},
        )
        if not result:
            raise HTTPException(status_code=404, detail='לא נמצאה בקשה פעילה לביטול')

        await _audit('organization', org['id'], 'ownership_transfer_cancelled', user['id'], {
            'org_id': org['id'],
            'request_id': request_id,
            'target_phone_masked': mask_phone(result.get('target_phone_e164', '')),
        })

        logger.info(f"[TRANSFER] cancelled org={org['id']} by={user['id']} request={request_id}")

        return {'success': True, 'message': 'בקשת ההעברה בוטלה'}

    @router.get("/pending")
    async def get_pending_transfer(user: dict = Depends(get_current_user)):
        db = _get_db()

        org = await get_user_org(user['id'])
        if not org:
            return {'has_pending': False}

        if org.get('owner_user_id') != user['id']:
            return {'has_pending': False}

        request = await db.ownership_transfer_requests.find_one(
            {'org_id': org['id'], 'status': 'pending'}, {'_id': 0, 'token_hash': 0}
        )
        if not request:
            return {'has_pending': False}

        if request.get('expires_at', '') < _now():
            await db.ownership_transfer_requests.update_one(
                {'id': request['id']}, {'$set': {'status': 'expired'}}
            )
            return {'has_pending': False}

        return {
            'has_pending': True,
            'request_id': request['id'],
            'target_phone_masked': mask_phone(request.get('target_phone_e164', '')),
            'created_at': request.get('created_at', ''),
            'expires_at': request.get('expires_at', ''),
        }

    @router.get("/verify/{token}")
    async def verify_transfer_token(token: str):
        db = _get_db()
        token_hash = _hash_token(token)

        request = await db.ownership_transfer_requests.find_one(
            {'token_hash': token_hash}, {'_id': 0}
        )
        if not request:
            raise HTTPException(status_code=404, detail='בקשה לא נמצאה')

        if request.get('status') != 'pending':
            status_messages = {
                'cancelled': 'בקשה זו בוטלה',
                'expired': 'בקשה זו פגה',
                'completed': 'בקשה זו כבר הושלמה',
            }
            msg = status_messages.get(request['status'], 'בקשה לא תקפה')
            raise HTTPException(status_code=409, detail=msg)

        if request.get('expires_at', '') < _now():
            await db.ownership_transfer_requests.update_one(
                {'id': request['id']}, {'$set': {'status': 'expired'}}
            )
            raise HTTPException(status_code=410, detail='תוקף הבקשה פג')

        return {
            'valid': True,
            'org_name': request.get('org_name', ''),
            'target_phone_masked': mask_phone(request.get('target_phone_e164', '')),
            'initiator_name': request.get('initiator_name', ''),
            'expires_at': request.get('expires_at', ''),
        }

    @router.post("/request-otp")
    async def request_transfer_otp(body: dict):
        db = _get_db()
        token = body.get('token', '').strip()
        if not token:
            raise HTTPException(status_code=400, detail='טוקן נדרש')

        token_hash = _hash_token(token)
        request = await db.ownership_transfer_requests.find_one(
            {'token_hash': token_hash, 'status': 'pending'}, {'_id': 0}
        )
        if not request:
            raise HTTPException(status_code=404, detail='בקשה לא נמצאה או שאינה פעילה')

        if request.get('expires_at', '') < _now():
            await db.ownership_transfer_requests.update_one(
                {'id': request['id']}, {'$set': {'status': 'expired'}}
            )
            raise HTTPException(status_code=410, detail='תוקף הבקשה פג')

        target_phone = request.get('target_phone_e164', '')
        if not target_phone:
            raise HTTPException(status_code=500, detail='שגיאה פנימית')

        otp_service = _otp_service_ref
        if otp_service:
            otp_result = await otp_service.request_otp(target_phone)
            debug_code = otp_result.get('debug_code')
            resp = {
                'success': True,
                'message': 'קוד אימות נשלח',
                'expires_in': otp_result.get('expires_in', 600),
            }
            if debug_code:
                resp['otp_debug_code'] = debug_code
            return resp

        raise HTTPException(status_code=503, detail='שירות OTP לא זמין')

    @router.post("/accept")
    async def accept_transfer(body: dict):
        db = _get_db()
        token = body.get('token', '').strip()
        otp_code = body.get('otp_code', '').strip()
        typed_org_name = body.get('typed_org_name', '').strip()

        if not token:
            raise HTTPException(status_code=400, detail='טוקן נדרש')
        if not otp_code:
            raise HTTPException(status_code=400, detail='קוד אימות נדרש')
        if not typed_org_name:
            raise HTTPException(status_code=400, detail='שם הארגון נדרש לאישור')

        token_hash = _hash_token(token)
        request = await db.ownership_transfer_requests.find_one(
            {'token_hash': token_hash}, {'_id': 0}
        )
        if not request:
            raise HTTPException(status_code=404, detail='בקשה לא נמצאה')

        if request.get('status') != 'pending':
            status_messages = {
                'cancelled': 'בקשה זו בוטלה',
                'expired': 'בקשה זו פגה',
                'completed': 'בקשה זו כבר הושלמה',
            }
            msg = status_messages.get(request['status'], 'בקשה לא תקפה')
            raise HTTPException(status_code=409, detail=msg)

        if request.get('expires_at', '') < _now():
            await db.ownership_transfer_requests.update_one(
                {'id': request['id']}, {'$set': {'status': 'expired'}}
            )
            raise HTTPException(status_code=410, detail='תוקף הבקשה פג')

        if request.get('accept_attempts', 0) >= ACCEPT_MAX_ATTEMPTS:
            await db.ownership_transfer_requests.update_one(
                {'id': request['id']}, {'$set': {'status': 'expired'}}
            )
            await _audit('organization', request['org_id'], 'ownership_transfer_locked_out', 'system', {
                'request_id': request['id'],
                'reason': 'max_accept_attempts',
            })
            raise HTTPException(status_code=429, detail='חרגת ממספר הניסיונות. הבקשה בוטלה.')

        await db.ownership_transfer_requests.update_one(
            {'id': request['id']}, {'$inc': {'accept_attempts': 1}}
        )

        target_phone = request.get('target_phone_e164', '')

        otp_service = _otp_service_ref
        if otp_service:
            otp_result = await otp_service.verify_otp(target_phone, otp_code)
            if not otp_result.get('success'):
                await _audit('organization', request['org_id'], 'ownership_transfer_accept_attempt_failed', 'unknown', {
                    'request_id': request['id'],
                    'reason': 'otp_failed',
                    'target_phone_masked': mask_phone(target_phone),
                })
                detail = otp_result.get('error', 'קוד אימות שגוי')
                raise HTTPException(status_code=403, detail=detail)

        expected_name = _normalize_org_name(request.get('org_name', ''))
        actual_name = _normalize_org_name(typed_org_name)
        if expected_name != actual_name:
            await _audit('organization', request['org_id'], 'ownership_transfer_accept_attempt_failed', 'unknown', {
                'request_id': request['id'],
                'reason': 'typed_confirmation_mismatch',
                'target_phone_masked': mask_phone(target_phone),
            })
            raise HTTPException(status_code=422, detail=f'שם הארגון אינו תואם. הקלד/י בדיוק: {expected_name}')

        recipient = await db.users.find_one({'phone_e164': target_phone}, {'_id': 0})
        if not recipient:
            raise HTTPException(status_code=404, detail='משתמש לא נמצא. יש להירשם קודם.')

        if recipient.get('user_status') == 'pending_deletion':
            raise HTTPException(status_code=409, detail='לא ניתן להעביר בעלות למשתמש בתהליך מחיקה')

        if recipient.get('user_status') != 'active':
            raise HTTPException(status_code=409, detail='לא ניתן להעביר בעלות למשתמש לא פעיל')

        new_owner_id = recipient['id']
        org_id = request['org_id']
        initiator_id = request.get('initiator_user_id', '')

        target_org_mem = await db.organization_memberships.find_one({
            'user_id': new_owner_id, 'org_id': org_id
        }, {'_id': 0, 'role': 1})
        target_project_mem = None
        if not target_org_mem:
            org_projects = await db.projects.find(
                {'org_id': org_id}, {'_id': 0, 'id': 1}
            ).to_list(1000)
            proj_ids = [p['id'] for p in org_projects]
            if proj_ids:
                target_project_mem = await db.project_memberships.find_one({
                    'user_id': new_owner_id,
                    'project_id': {'$in': proj_ids},
                }, {'_id': 0, 'role': 1})

        if not target_org_mem and not target_project_mem:
            raise HTTPException(status_code=409, detail='המשתמש חייב להיות חבר בארגון לפני העברת בעלות')

        pm_role = None
        if target_project_mem:
            pm_role = target_project_mem.get('role')
        if pm_role == 'contractor':
            raise HTTPException(status_code=409, detail='לא ניתן להעביר בעלות לקבלן. יש לשנות את תפקידו קודם.')

        from contractor_ops.member_management import check_role_conflict_for_ownership
        await check_role_conflict_for_ownership(db, new_owner_id, org_id,
                                                 actor_id=initiator_id)

        ts = _now()

        org_update = await db.organizations.find_one_and_update(
            {'id': org_id, 'owner_user_id': initiator_id},
            {'$set': {
                'owner_user_id': new_owner_id,
                'owner_set_at': ts,
            }},
        )
        if not org_update:
            raise HTTPException(status_code=409, detail='העברה נכשלה – ייתכן שהבעלות כבר השתנתה')

        await db.ownership_transfer_requests.update_one(
            {'id': request['id']},
            {'$set': {
                'status': 'completed',
                'accepted_at': ts,
                'completed_at': ts,
                'accepted_by_user_id': new_owner_id,
            }}
        )

        await db.organization_memberships.update_one(
            {'org_id': org_id, 'user_id': new_owner_id},
            {'$setOnInsert': {
                'id': str(uuid.uuid4()),
                'org_id': org_id,
                'user_id': new_owner_id,
                'role': 'member',
                'source': 'ownership_transfer',
                'created_at': ts,
            }},
            upsert=True
        )

        await db.organization_memberships.update_one(
            {'org_id': org_id, 'user_id': initiator_id},
            {'$set': {'role': 'billing_admin'}},
        )

        await db.users.update_one(
            {'id': initiator_id},
            {'$inc': {'session_version': 1}}
        )

        await _audit('organization', org_id, 'ownership_transfer_accepted', new_owner_id, {
            'request_id': request['id'],
            'org_id': org_id,
            'org_name': request.get('org_name', ''),
            'old_owner_id': initiator_id,
            'new_owner_id': new_owner_id,
            'target_phone_masked': mask_phone(target_phone),
        })

        await _audit('organization', org_id, 'ownership_transfer_completed', new_owner_id, {
            'request_id': request['id'],
            'org_id': org_id,
            'org_name': request.get('org_name', ''),
            'old_owner_id': initiator_id,
            'new_owner_id': new_owner_id,
            'completed_at': ts,
        })

        logger.info(f"[TRANSFER] completed org={org_id} old_owner={initiator_id} new_owner={new_owner_id} request={request['id']}")

        return {
            'success': True,
            'message': 'העברת הבעלות הושלמה בהצלחה',
            'org_id': org_id,
            'org_name': request.get('org_name', ''),
            'new_owner_id': new_owner_id,
            'new_owner_name': recipient.get('name', ''),
        }

    return router
