import uuid
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Request

from contractor_ops.router import (
    get_db, get_current_user, get_current_user_allow_pending_deletion,
    _is_super_admin, _verify_password, _now, _audit,
    require_stepup,
)
from contractor_ops.billing import get_user_org

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["deletion"])

DELETION_GRACE_DAYS = 7

_otp_service_ref = None


def set_deletion_otp_service(svc):
    global _otp_service_ref
    _otp_service_ref = svc


def _scheduled_for():
    return (datetime.now(timezone.utc) + timedelta(days=DELETION_GRACE_DAYS)).isoformat()


async def _verify_auth_for_deletion(user: dict, body: dict, db):
    pw_hash = user.get('password_hash')
    if pw_hash:
        password = body.get('password', '').strip()
        if not password:
            raise HTTPException(status_code=400, detail='נדרשת סיסמה לאישור מחיקה')
        valid = await _verify_password(password, pw_hash)
        if not valid:
            raise HTTPException(status_code=401, detail='סיסמה שגויה')
        return
    otp_code = body.get('otp_code', '').strip()
    if not otp_code:
        raise HTTPException(status_code=400, detail='נדרש קוד אימות (OTP) לאישור מחיקה')
    otp_svc = _otp_service_ref
    if not otp_svc:
        raise HTTPException(status_code=503, detail='שירות OTP לא זמין')
    phone = user.get('phone_e164', '')
    if not phone:
        raise HTTPException(status_code=400, detail='לא נמצא מספר טלפון בחשבון')
    result = await otp_svc.verify_otp(phone, otp_code)
    if not result.get('success'):
        detail = result.get('error', 'קוד אימות שגוי')
        raise HTTPException(status_code=403, detail=detail)


@router.post("/users/me/request-deletion-otp")
async def request_deletion_otp(user: dict = Depends(get_current_user)):
    pw_hash = user.get('password_hash')
    if pw_hash:
        return {'auth_method': 'password', 'message': 'יש להזין סיסמה לאישור'}
    otp_svc = _otp_service_ref
    if not otp_svc:
        raise HTTPException(status_code=503, detail='שירות OTP לא זמין')
    phone = user.get('phone_e164', '')
    if not phone:
        raise HTTPException(status_code=400, detail='לא נמצא מספר טלפון בחשבון')
    result = await otp_svc.request_otp(phone)
    if not result.get('success'):
        error_type = result.get('error', '')
        if error_type in ('rate_limited', 'too_many_attempts'):
            raise HTTPException(status_code=429, detail=result['message'])
        raise HTTPException(status_code=422, detail=result['message'])
    resp = {
        'auth_method': 'otp',
        'message': 'קוד אימות נשלח',
        'expires_in': result.get('expires_in', 600),
    }
    import os
    if os.environ.get('APP_MODE', '') == 'dev' and os.environ.get('SMS_MODE', '') == 'stub':
        debug_code = result.get('debug_code')
        if debug_code:
            resp['otp_debug_code'] = debug_code
    return resp


@router.post("/users/me/request-deletion")
async def request_account_deletion(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = user['id']

    if user.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='כבר קיימת בקשת מחיקה פעילה')

    org = await get_user_org(user_id)
    if org and org.get('owner_user_id') == user_id:
        raise HTTPException(
            status_code=400,
            detail='יש להעביר בעלות על הארגון לפני מחיקת החשבון'
        )

    body = await request.json()
    await _verify_auth_for_deletion(user, body, db)

    ts = _now()
    scheduled = _scheduled_for()
    old_sv = user.get('session_version', 0)
    new_sv = old_sv + 1

    await db.users.update_one({'id': user_id}, {'$set': {
        'user_status': 'pending_deletion',
        'deletion_requested_at': ts,
        'deletion_scheduled_for': scheduled,
        'deletion_type': 'account_only',
        'session_version': new_sv,
    }})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'deletion_requested',
        'actor_id': user_id,
        'payload': {
            'deletion_type': 'account_only',
            'scheduled_for': scheduled,
        },
        'created_at': ts,
    })

    logger.info(f"[DELETION] account_only requested user={user_id} scheduled={scheduled}")
    return {
        'success': True,
        'deletion_type': 'account_only',
        'scheduled_for': scheduled,
        'message': f'בקשת מחיקת חשבון התקבלה. החשבון יימחק ב-{DELETION_GRACE_DAYS} ימים.',
    }


@router.post("/users/me/request-full-deletion")
async def request_full_deletion(request: Request, user: dict = Depends(get_current_user)):
    db = get_db()
    user_id = user['id']

    if user.get('user_status') == 'pending_deletion':
        raise HTTPException(status_code=409, detail='כבר קיימת בקשת מחיקה פעילה')

    org = await get_user_org(user_id)
    if not org:
        raise HTTPException(status_code=400, detail='אין לך ארגון. השתמש במחיקת חשבון רגילה.')

    if org.get('owner_user_id') != user_id:
        raise HTTPException(status_code=403, detail='רק בעל הארגון יכול למחוק את הארגון')

    body = await request.json()

    typed_org_name = body.get('typed_org_name', '').strip()
    if not typed_org_name:
        raise HTTPException(status_code=400, detail='יש להקליד את שם הארגון לאישור')

    import re
    expected = re.sub(r'\s+', ' ', org.get('name', '').strip())
    actual = re.sub(r'\s+', ' ', typed_org_name)
    if expected != actual:
        raise HTTPException(status_code=422, detail=f'שם הארגון אינו תואם. יש להקליד בדיוק: {expected}')

    await _verify_auth_for_deletion(user, body, db)

    ts = _now()
    scheduled = _scheduled_for()
    old_sv = user.get('session_version', 0)
    new_sv = old_sv + 1

    await db.users.update_one({'id': user_id}, {'$set': {
        'user_status': 'pending_deletion',
        'deletion_requested_at': ts,
        'deletion_scheduled_for': scheduled,
        'deletion_type': 'full_purge',
        'deletion_org_id': org['id'],
        'session_version': new_sv,
    }})

    org_id = org['id']
    await db.organizations.update_one({'id': org_id}, {'$set': {
        'status': 'pending_purge',
        'purge_scheduled_for': scheduled,
        'purge_requested_at': ts,
        'purge_requested_by': user_id,
    }})

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'organization',
        'entity_id': org_id,
        'action': 'full_deletion_requested',
        'actor_id': user_id,
        'payload': {
            'deletion_type': 'full_purge',
            'org_name': org.get('name', ''),
            'scheduled_for': scheduled,
        },
        'created_at': ts,
    })

    logger.info(f"[DELETION] full_purge requested user={user_id} org={org_id} scheduled={scheduled}")
    return {
        'success': True,
        'deletion_type': 'full_purge',
        'org_name': org.get('name', ''),
        'scheduled_for': scheduled,
        'message': f'בקשת מחיקת חשבון וארגון התקבלה. הכל יימחק ב-{DELETION_GRACE_DAYS} ימים.',
    }


@router.post("/users/me/cancel-deletion")
async def cancel_deletion(user: dict = Depends(get_current_user_allow_pending_deletion)):
    db = get_db()
    user_id = user['id']

    if user.get('user_status') != 'pending_deletion':
        raise HTTPException(status_code=409, detail='אין בקשת מחיקה פעילה')

    ts = _now()
    deletion_type = user.get('deletion_type', 'account_only')

    await db.users.update_one({'id': user_id}, {
        '$set': {'user_status': 'active'},
        '$unset': {
            'deletion_requested_at': '',
            'deletion_scheduled_for': '',
            'deletion_type': '',
            'deletion_org_id': '',
        },
    })

    if deletion_type == 'full_purge':
        org = await get_user_org(user_id)
        if org and org.get('status') == 'pending_purge':
            await db.organizations.update_one({'id': org['id']}, {
                '$set': {'status': 'active'},
                '$unset': {
                    'purge_scheduled_for': '',
                    'purge_requested_at': '',
                    'purge_requested_by': '',
                },
            })

    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'entity_type': 'user',
        'entity_id': user_id,
        'action': 'deletion_cancelled',
        'actor_id': user_id,
        'payload': {'deletion_type': deletion_type},
        'created_at': ts,
    })

    logger.info(f"[DELETION] cancelled user={user_id} type={deletion_type}")
    return {'success': True, 'message': 'בקשת המחיקה בוטלה. החשבון פעיל.'}


@router.get("/users/me/deletion-status")
async def get_deletion_status(user: dict = Depends(get_current_user_allow_pending_deletion)):
    if user.get('user_status') != 'pending_deletion':
        return {'pending': False}

    return {
        'pending': True,
        'deletion_type': user.get('deletion_type', 'account_only'),
        'requested_at': user.get('deletion_requested_at'),
        'scheduled_for': user.get('deletion_scheduled_for'),
    }


async def _collect_s3_keys_for_user(db, user_id: str, org_id: str = None):
    keys = []

    user_doc = await db.users.find_one({'id': user_id}, {'_id': 0, 'photo_url': 1})
    if user_doc and user_doc.get('photo_url'):
        keys.append(user_doc['photo_url'])

    if org_id:
        org_doc = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'logo_url': 1})
        if org_doc and org_doc.get('logo_url'):
            keys.append(org_doc['logo_url'])

        org_projects = await db.projects.find(
            {'org_id': org_id}, {'_id': 0, 'id': 1}
        ).to_list(10000)
        project_ids = [p['id'] for p in org_projects]

        if project_ids:
            tasks = await db.tasks.find(
                {'project_id': {'$in': project_ids}},
                {'_id': 0, 'proof_urls': 1, 'file_url': 1}
            ).to_list(100000)
            for t in tasks:
                for url in (t.get('proof_urls') or []):
                    if url:
                        keys.append(url)
                if t.get('file_url'):
                    keys.append(t['file_url'])

            updates = await db.task_updates.find(
                {'project_id': {'$in': project_ids}},
                {'_id': 0, 'attachment_url': 1}
            ).to_list(100000)
            for u in updates:
                if u.get('attachment_url'):
                    keys.append(u['attachment_url'])

            plans = await db.project_plans.find(
                {'project_id': {'$in': project_ids}},
                {'_id': 0, 'file_url': 1, 'thumbnail_url': 1}
            ).to_list(10000)
            for p in plans:
                if p.get('file_url'):
                    keys.append(p['file_url'])
                if p.get('thumbnail_url'):
                    keys.append(p['thumbnail_url'])

            qc_inspections = await db.qc_inspections.find(
                {'project_id': {'$in': project_ids}},
                {'_id': 0, 'items': 1}
            ).to_list(100000)
            for insp in qc_inspections:
                for item in (insp.get('items') or []):
                    for photo in (item.get('photos') or []):
                        if isinstance(photo, dict) and photo.get('url'):
                            keys.append(photo['url'])
                        elif isinstance(photo, str) and photo:
                            keys.append(photo)

            handovers = await db.handover_protocols.find(
                {'project_id': {'$in': project_ids}},
                {'_id': 0, 'pdf_url': 1, 'signatures': 1}
            ).to_list(10000)
            for h in handovers:
                if h.get('pdf_url'):
                    keys.append(h['pdf_url'])
                for sig in (h.get('signatures') or []):
                    if isinstance(sig, dict) and sig.get('signature_url'):
                        keys.append(sig['signature_url'])

    return [k for k in keys if k and isinstance(k, str)]


async def _anonymize_user_db(db, user_id: str):
    ts = _now()
    await db.users.update_one({'id': user_id}, {'$set': {
        'user_status': 'deleted',
        'name': 'משתמש שנמחק',
        'email': None,
        'phone': None,
        'phone_e164': None,
        'password_hash': None,
        'photo_url': None,
        'specialties': [],
        'deleted_at': ts,
    }})


async def _anonymize_org_db(db, org_id: str, project_ids: list):
    ts = _now()

    billing_records = await db.billing_subscriptions.find(
        {'org_id': org_id}, {'_id': 0, 'id': 1}
    ).to_list(10000)
    for rec in billing_records:
        await db.billing_subscriptions.update_one({'id': rec['id']}, {'$set': {
            'billing_email': None,
            'billing_name': 'משתמש שנמחק',
        }, '$unset': {
            'gi_card_token': '',
            'gi_card_suffix': '',
        }})

    await db.organizations.update_one({'id': org_id}, {'$set': {
        'status': 'deleted',
        'name': 'ארגון שנמחק',
        'logo_url': None,
        'deleted_at': ts,
        'billing': {},
    }})

    if project_ids:
        await db.project_memberships.delete_many({'project_id': {'$in': project_ids}})
    await db.organization_memberships.delete_many({'org_id': org_id})


async def _clean_s3_keys(keys: list):
    from services.object_storage import delete as s3_delete
    deleted = 0
    failed = 0
    for key in keys:
        try:
            s3_delete(key)
            deleted += 1
        except Exception as e:
            logger.warning(f"[DELETION] S3 delete failed key={key[:50]}... error={e}")
            failed += 1
    return deleted, failed


@router.post("/admin/execute-deletion/{target_user_id}")
async def execute_deletion(target_user_id: str, admin: dict = Depends(require_stepup)):
    db = get_db()

    target = await db.users.find_one({'id': target_user_id}, {'_id': 0})
    if not target:
        raise HTTPException(status_code=404, detail='משתמש לא נמצא')

    if target.get('user_status') != 'pending_deletion':
        raise HTTPException(status_code=409, detail='המשתמש אינו בתהליך מחיקה')

    scheduled = target.get('deletion_scheduled_for', '')
    if scheduled and scheduled > _now():
        raise HTTPException(
            status_code=409,
            detail=f'תקופת הגרייס טרם הסתיימה. מחיקה אפשרית מ-{scheduled}'
        )

    existing_job = await db.deletion_jobs.find_one({
        'user_id': target_user_id,
        'status': {'$in': ['collecting', 'db_done', 's3_cleaning']},
    })
    if existing_job:
        raise HTTPException(status_code=409, detail='כבר קיימת משימת מחיקה בביצוע')

    deletion_type = target.get('deletion_type', 'account_only')
    ts = _now()
    job_id = str(uuid.uuid4())

    org_id = None
    project_ids = []
    if deletion_type == 'full_purge':
        org_id = target.get('deletion_org_id')
        if not org_id:
            org = await get_user_org(target_user_id)
            if org:
                org_id = org['id']
        if org_id:
            org_projects = await db.projects.find(
                {'org_id': org_id}, {'_id': 0, 'id': 1}
            ).to_list(10000)
            project_ids = [p['id'] for p in org_projects]

    await db.deletion_jobs.insert_one({
        'id': job_id,
        'user_id': target_user_id,
        'org_id': org_id,
        'deletion_type': deletion_type,
        'status': 'collecting',
        'created_at': ts,
        'completed_at': None,
        'executed_by': admin['id'],
    })

    try:
        s3_keys = await _collect_s3_keys_for_user(db, target_user_id, org_id)

        await db.deletion_jobs.update_one({'id': job_id}, {'$set': {
            'status': 'db_done',
            's3_keys_count': len(s3_keys),
        }})

        await _anonymize_user_db(db, target_user_id)

        if deletion_type == 'full_purge' and org_id:
            await _anonymize_org_db(db, org_id, project_ids)

        await db.deletion_jobs.update_one({'id': job_id}, {'$set': {
            'status': 's3_cleaning',
        }})

        deleted, failed = await _clean_s3_keys(s3_keys)

        final_status = 'complete' if failed == 0 else 's3_partial'
        await db.deletion_jobs.update_one({'id': job_id}, {'$set': {
            'status': final_status,
            'completed_at': _now(),
            's3_deleted': deleted,
            's3_failed': failed,
        }})

        await db.audit_events.insert_one({
            'id': str(uuid.uuid4()),
            'entity_type': 'user',
            'entity_id': target_user_id,
            'action': 'deletion_executed',
            'actor_id': admin['id'],
            'payload': {
                'job_id': job_id,
                'deletion_type': deletion_type,
                'org_id': org_id,
                's3_keys': len(s3_keys),
                's3_deleted': deleted,
                's3_failed': failed,
            },
            'created_at': _now(),
        })

        logger.info(
            f"[DELETION] executed user={target_user_id} type={deletion_type} "
            f"org={org_id} s3_keys={len(s3_keys)} deleted={deleted} failed={failed} "
            f"job={job_id} by={admin['id']}"
        )

        return {
            'success': True,
            'job_id': job_id,
            'deletion_type': deletion_type,
            'status': final_status,
            's3_keys': len(s3_keys),
            's3_deleted': deleted,
            's3_failed': failed,
        }

    except Exception as e:
        await db.deletion_jobs.update_one({'id': job_id}, {'$set': {
            'status': 'error',
            'error': str(e)[:500],
        }})
        logger.error(f"[DELETION] execution failed user={target_user_id} job={job_id} error={e}")
        raise HTTPException(status_code=500, detail=f'שגיאה בביצוע מחיקה: {str(e)[:200]}')


@router.get("/admin/deletion-jobs")
async def list_deletion_jobs(admin: dict = Depends(require_stepup)):
    db = get_db()
    jobs = await db.deletion_jobs.find(
        {}, {'_id': 0}
    ).sort('created_at', -1).to_list(100)
    return {'jobs': jobs}


@router.get("/admin/pending-deletions")
async def list_pending_deletions(admin: dict = Depends(require_stepup)):
    db = get_db()
    users = await db.users.find(
        {'user_status': 'pending_deletion'},
        {'_id': 0, 'id': 1, 'name': 1, 'email': 1, 'phone_e164': 1,
         'deletion_requested_at': 1, 'deletion_scheduled_for': 1, 'deletion_type': 1}
    ).to_list(1000)
    return {'users': users}
