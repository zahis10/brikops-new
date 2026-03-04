import uuid
import secrets
from typing import Optional
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from contractor_ops.router import (
    get_db, get_current_user, require_roles,
    _get_project_membership, _audit, _now, _is_super_admin,
    get_notification_engine, get_public_base_url, logger,
)
from contractor_ops.schemas import InviteCreate
from contractor_ops.phone_utils import normalize_israeli_phone
from contractor_ops.bucket_utils import BUCKET_LABELS

router = APIRouter(prefix="/api")


@router.put("/projects/{project_id}/members/{user_id}/contractor-profile")
async def update_contractor_profile(project_id: str, user_id: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    is_sa = user.get('platform_role') == 'super_admin'
    caller_membership = await _get_project_membership(user, project_id)
    caller_role = caller_membership.get('role', 'none') if caller_membership else 'none'

    org_id = project.get('org_id')
    caller_org_role = None
    if org_id:
        org_mem = await db.organization_memberships.find_one({'org_id': org_id, 'user_id': user['id']}, {'_id': 0, 'role': 1})
        caller_org_role = org_mem.get('role') if org_mem else None
        org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'owner_user_id': 1})
        if org and org.get('owner_user_id') == user['id']:
            caller_org_role = 'owner'

    can_edit = is_sa or caller_role in ('project_manager',) or caller_org_role in ('owner', 'org_admin')
    if not can_edit:
        raise HTTPException(status_code=403, detail='אין הרשאה לעדכן פרופיל קבלן')

    membership = await db.project_memberships.find_one({
        'project_id': project_id, 'user_id': user_id
    })
    if not membership:
        raise HTTPException(status_code=404, detail='חברות בפרויקט לא נמצאה')
    if membership.get('role') != 'contractor':
        raise HTTPException(status_code=400, detail='ניתן לעדכן פרופיל חברה/תחום רק לקבלנים')

    new_company_id = body.get('company_id')
    new_trade_key = body.get('trade_key')

    if not new_company_id or not str(new_company_id).strip():
        raise HTTPException(status_code=422, detail='חברה היא שדה חובה')
    if not new_trade_key or not str(new_trade_key).strip():
        raise HTTPException(status_code=422, detail='תחום הוא שדה חובה')

    company_doc = await db.project_companies.find_one({
        'id': new_company_id, 'project_id': project_id,
        'deletedAt': {'$exists': False},
    })
    if not company_doc:
        raise HTTPException(status_code=422, detail='חברה לא נמצאה בפרויקט זה')

    is_global_trade = new_trade_key in BUCKET_LABELS
    is_project_trade = False
    if not is_global_trade:
        is_project_trade = await db.project_trades.find_one({'project_id': project_id, 'key': new_trade_key}) is not None
    if not is_global_trade and not is_project_trade:
        raise HTTPException(status_code=422, detail=f'מקצוע לא תקין: {new_trade_key}')

    old_company_id = membership.get('company_id')
    old_trade_key = membership.get('contractor_trade_key')

    ts = _now()
    await db.project_memberships.update_one(
        {'project_id': project_id, 'user_id': user_id},
        {'$set': {
            'company_id': new_company_id,
            'contractor_trade_key': new_trade_key,
            'updated_at': ts,
        }}
    )

    await _audit('membership', f'{project_id}_{user_id}', 'member_contractor_profile_changed', user['id'], {
        'project_id': project_id,
        'target_user_id': user_id,
        'old_company_id': old_company_id,
        'new_company_id': new_company_id,
        'old_trade_key': old_trade_key,
        'new_trade_key': new_trade_key,
    })

    return {
        'success': True,
        'company_id': new_company_id,
        'contractor_trade_key': new_trade_key,
    }


@router.get("/users")
async def list_users(
    role: Optional[str] = Query(None),
    company_id: Optional[str] = Query(None),
    specialty: Optional[str] = Query(None),
    user: dict = Depends(require_roles('project_manager')),
):
    db = get_db()
    query = {}
    if role:
        query['role'] = role
    if company_id:
        query['company_id'] = company_id
    users = await db.users.find(query, {'_id': 0, 'password_hash': 0}).to_list(1000)
    if specialty:
        company_ids_with_specialty = await db.companies.distinct('id', {'specialties': specialty})
        users = [u for u in users if
                 u.get('company_id') in company_ids_with_specialty or
                 specialty in (u.get('specialties') or [])]
    return users


# ── Team invites (RBAC invite system) ──
INVITE_RBAC = {
    'project_manager': ['project_manager', 'management_team', 'contractor'],
    'management_team': ['contractor'],
}
VALID_SUB_ROLES = ['site_manager', 'execution_engineer', 'safety_assistant', 'work_manager', 'safety_officer']


@router.post("/projects/{project_id}/invites")
async def create_team_invite(project_id: str, body: InviteCreate, user: dict = Depends(get_current_user)):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    project = await db.projects.find_one({'id': project_id})
    if not project:
        raise HTTPException(status_code=404, detail='Project not found')

    membership = await _get_project_membership(user, project_id)
    inviter_role = membership['role']
    allowed_roles = INVITE_RBAC.get(inviter_role, [])
    if not allowed_roles:
        raise HTTPException(status_code=403, detail='אין לך הרשאה להזמין משתמשים')

    target_role = body.role.value
    if target_role not in allowed_roles:
        raise HTTPException(status_code=403, detail=f'אין לך הרשאה להזמין {target_role}')

    if not body.full_name or not body.full_name.strip():
        raise HTTPException(status_code=422, detail='שם מלא הוא שדה חובה')

    try:
        phone_result = normalize_israeli_phone(body.phone)
        phone = phone_result['phone_e164']
        phone_raw = phone_result['phone_raw']
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if target_role == 'contractor':
        if not body.trade_key or not body.trade_key.strip():
            raise HTTPException(status_code=422, detail='מקצוע הוא שדה חובה עבור קבלן')
        is_global = body.trade_key in BUCKET_LABELS
        is_project = False
        if not is_global:
            is_project = await db.project_trades.find_one({'project_id': project_id, 'key': body.trade_key}) is not None
        if not is_global and not is_project:
            raise HTTPException(status_code=422, detail=f'מקצוע לא תקין: {body.trade_key}')
        if not body.company_id or not body.company_id.strip():
            raise HTTPException(status_code=422, detail='חברה היא שדה חובה עבור קבלן')
        company_doc = await db.project_companies.find_one({
            'id': body.company_id, 'project_id': project_id,
            'deletedAt': {'$exists': False},
        })
        if not company_doc:
            raise HTTPException(status_code=422, detail='חברה לא נמצאה בפרויקט זה')
    elif body.trade_key:
        raise HTTPException(status_code=400, detail='trade_key מותר רק לתפקיד קבלן')
    if body.company_id and target_role != 'contractor':
        raise HTTPException(status_code=400, detail='company_id מותר רק לתפקיד קבלן')

    if target_role == 'management_team':
        if body.sub_role and body.sub_role not in VALID_SUB_ROLES:
            raise HTTPException(status_code=400, detail=f'sub_role חייב להיות אחד מ: {", ".join(VALID_SUB_ROLES)}')
    else:
        if body.sub_role:
            raise HTTPException(status_code=400, detail='sub_role מותר רק לתפקיד management_team')

    existing_invite = await db.invites.find_one({
        'project_id': project_id, 'target_phone': phone,
        'role': target_role, 'status': 'pending',
    })
    if existing_invite:
        raise HTTPException(status_code=400, detail='הזמנה ממתינה כבר קיימת עבור טלפון ותפקיד זה')

    existing_user = await db.users.find_one({'phone_e164': phone}, {'_id': 0})
    if existing_user:
        existing_membership = await db.project_memberships.find_one({
            'project_id': project_id, 'user_id': existing_user['id'],
        })
        if existing_membership:
            raise HTTPException(status_code=400, detail='משתמש כבר חבר בפרויקט זה')
        from contractor_ops.member_management import check_role_conflict
        await check_role_conflict(db, existing_user['id'], project_id, target_role,
                                  actor_id=user['id'], attempted_action='create_team_invite_auto_link')
        ts = _now()
        membership_doc = {
            'id': str(uuid.uuid4()),
            'project_id': project_id,
            'user_id': existing_user['id'],
            'role': target_role,
            'sub_role': body.sub_role if target_role == 'management_team' else None,
            'created_at': ts,
        }
        if target_role == 'contractor' and body.trade_key:
            membership_doc['contractor_trade_key'] = body.trade_key
        if target_role == 'contractor' and body.company_id:
            membership_doc['company_id'] = body.company_id
        await db.project_memberships.update_one(
            {'project_id': project_id, 'user_id': existing_user['id']},
            {'$set': membership_doc},
            upsert=True
        )
        if target_role == 'project_manager':
            await db.users.update_one(
                {'id': existing_user['id']},
                {'$set': {'role': 'project_manager', 'updated_at': ts}}
            )
        await _audit('invite', 'auto_link', 'auto_linked', user['id'], {
            'project_id': project_id, 'target_user_id': existing_user['id'],
            'role': target_role, 'phone': phone,
            'trade_key': body.trade_key if target_role == 'contractor' else None,
            'company_id': body.company_id if target_role == 'contractor' else None,
        })
        return {
            'success': True, 'auto_linked': True,
            'user_id': existing_user['id'],
            'message': f'משתמש {existing_user.get("name", phone)} שויך אוטומטית לפרויקט',
        }

    invite_id = str(uuid.uuid4())
    ts = _now()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    doc = {
        'id': invite_id,
        'project_id': project_id,
        'inviter_user_id': user['id'],
        'target_phone': phone,
        'phone_raw': phone_raw,
        'role': target_role,
        'sub_role': body.sub_role if target_role == 'management_team' else None,
        'trade_key': body.trade_key if target_role == 'contractor' else None,
        'company_id': body.company_id if target_role == 'contractor' else None,
        'full_name': body.full_name,
        'token': secrets.token_urlsafe(32),
        'status': 'pending',
        'expires_at': expires_at,
        'accepted_by_user_id': None,
        'accepted_at': None,
        'created_at': ts,
        'updated_at': ts,
    }
    await db.invites.insert_one(doc)
    await _audit('invite', invite_id, 'created', user['id'], {
        'project_id': project_id, 'phone': phone, 'role': target_role,
        'trade_key': body.trade_key if target_role == 'contractor' else None,
        'company_id': body.company_id if target_role == 'contractor' else None,
    })

    role_labels = {
        'project_manager': 'מנהל פרויקט',
        'management_team': 'צוות ניהול',
        'contractor': 'קבלן',
    }
    notification_status = {'channel_used': 'none', 'reason': 'not_attempted'}
    engine = get_notification_engine()
    if engine:
        try:
            base = get_public_base_url()
            join_link = f"{base}/onboarding?invite={invite_id}" if base else ""
            job = await engine.enqueue_invite(
                invite_id=invite_id,
                target_phone=phone,
                project_name=project.get('name', ''),
                join_link=join_link,
                inviter_name=user.get('name', ''),
                role_label=role_labels.get(target_role, target_role),
                created_by=user['id'],
            )
            if job and job.get('status') == 'queued':
                result = await engine.process_invite_job(job)
                notification_status = {
                    'channel_used': result.get('channel', 'none'),
                    'delivery_status': result.get('status', 'unknown'),
                    'reason': result.get('reason', ''),
                    'provider_message_id': result.get('provider_message_id', ''),
                    'job_id': result.get('job_id', ''),
                    'wa_skipped': result.get('wa_skipped', False),
                }
        except Exception as e:
            logger.warning(f"[INVITE] Notification failed for invite {invite_id}: {e}")
            notification_status = {'channel_used': 'none', 'delivery_status': 'failed', 'reason': str(e)[:200]}

    response = {k: v for k, v in doc.items() if k != '_id'}
    response['notification_status'] = notification_status
    return response


@router.get("/projects/{project_id}/invites")
async def list_team_invites(project_id: str, status: Optional[str] = Query(None), user: dict = Depends(get_current_user)):
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    if membership['role'] not in ('project_manager', 'management_team'):
        raise HTTPException(status_code=403, detail='אין הרשאה')

    query = {'project_id': project_id}
    if status:
        query['status'] = status
    invites = await db.invites.find(query, {'_id': 0}).sort('created_at', -1).to_list(1000)

    legacy_query = {'project_id': project_id}
    if status:
        legacy_query['status'] = status
    legacy_invites = await db.team_invites.find(legacy_query, {'_id': 0}).sort('created_at', -1).to_list(1000)
    legacy_ids = {inv.get('id') for inv in invites}
    for li in legacy_invites:
        if li.get('id') not in legacy_ids:
            invites.append(li)

    return invites


@router.post("/projects/{project_id}/invites/{invite_id}/resend")
async def resend_team_invite(project_id: str, invite_id: str, user: dict = Depends(get_current_user)):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    if membership['role'] not in ('project_manager',):
        raise HTTPException(status_code=403, detail='אין הרשאה')
    invite = await db.invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        invite = await db.team_invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        raise HTTPException(status_code=404, detail='Invite not found')
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail='Can only resend pending invites')
    ts = _now()
    if 'target_phone' in invite:
        await db.invites.update_one({'id': invite_id}, {'$set': {'updated_at': ts}})
    else:
        await db.team_invites.update_one({'id': invite_id}, {'$set': {'updated_at': ts}})
    await _audit('invite', invite_id, 'resend', user['id'], {'project_id': project_id})

    notification_status = {'channel_used': 'none', 'reason': 'not_attempted'}
    target_phone = invite.get('target_phone', invite.get('phone', ''))
    engine = get_notification_engine()
    if engine and target_phone:
        try:
            project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})
            base = get_public_base_url()
            join_link = f"{base}/onboarding?invite={invite_id}" if base else ""
            role_labels = {'project_manager': 'מנהל פרויקט', 'management_team': 'צוות ניהול', 'contractor': 'קבלן'}
            resend_id = f"{invite_id}_resend_{ts}"
            job = await engine.enqueue_invite(
                invite_id=resend_id,
                target_phone=target_phone,
                project_name=project.get('name', '') if project else '',
                join_link=join_link,
                inviter_name=user.get('name', ''),
                role_label=role_labels.get(invite.get('role', ''), invite.get('role', '')),
                created_by=user['id'],
            )
            if job and job.get('status') == 'queued':
                result = await engine.process_invite_job(job)
                delivery_status = result.get('status', 'unknown')
                channel = result.get('channel', 'none')
                notification_status = {
                    'channel_used': channel,
                    'delivery_status': delivery_status,
                    'reason': result.get('reason', ''),
                    'provider_message_id': result.get('provider_message_id', ''),
                    'job_id': result.get('job_id', ''),
                    'wa_skipped': result.get('wa_skipped', False),
                }
        except Exception as e:
            logger.warning(f"[INVITE-RESEND] Notification failed: {e}")
            notification_status = {'channel_used': 'none', 'delivery_status': 'failed', 'reason': str(e)[:200]}

    return {'success': True, 'message': 'הזמנה נשלחה מחדש', 'notification_status': notification_status}


@router.post("/projects/{project_id}/invites/{invite_id}/resend-sms")
async def resend_invite_sms(project_id: str, invite_id: str, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        membership = await _get_project_membership(user, project_id)
        if membership['role'] not in ('project_manager',):
            raise HTTPException(status_code=403, detail='אין הרשאה')
    db = get_db()
    invite = await db.invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        invite = await db.team_invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        raise HTTPException(status_code=404, detail='Invite not found')
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail='Can only resend pending invites')

    ts = _now()
    last_sms = await db.notification_jobs.find_one(
        {'invite_id': invite_id, 'channel': 'sms', 'status': 'sent'},
        sort=[('created_at', -1)]
    )
    if last_sms:
        from datetime import datetime, timezone
        last_ts = last_sms.get('updated_at') or last_sms.get('created_at', '')
        if last_ts:
            try:
                if isinstance(last_ts, str):
                    last_dt = datetime.fromisoformat(last_ts.replace('Z', '+00:00'))
                else:
                    last_dt = last_ts
                now_dt = datetime.now(timezone.utc)
                diff_secs = (now_dt - last_dt).total_seconds()
                if diff_secs < 60:
                    remaining = int(60 - diff_secs)
                    raise HTTPException(status_code=429, detail=f'SMS נשלח לאחרונה. נסה שוב בעוד {remaining} שניות.')
            except HTTPException:
                raise
            except Exception:
                pass

    target_phone = invite.get('target_phone', invite.get('phone', ''))
    if not target_phone:
        raise HTTPException(status_code=400, detail='אין מספר טלפון בהזמנה')

    notification_status = {'channel_used': 'none', 'delivery_status': 'not_attempted'}
    engine = get_notification_engine()
    if not engine or not engine.sms_client or not engine.sms_client.enabled:
        raise HTTPException(status_code=503, detail='שירות SMS לא זמין כרגע')

    try:
        project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'name': 1})
        base = get_public_base_url()
        join_link = f"{base}/onboarding?invite={invite_id}" if base else ""
        role_labels = {'project_manager': 'מנהל פרויקט', 'management_team': 'צוות ניהול', 'contractor': 'קבלן'}

        text_lines = [
            f"הזמנה לפרויקט {project.get('name', '') if project else ''}",
            f"הוזמנת על ידי: {user.get('name', '')}",
            f"תפקיד: {role_labels.get(invite.get('role', ''), invite.get('role', ''))}",
            f"להצטרפות: {join_link}",
        ]
        sms_text = "\n".join(text_lines)

        sms_job_id = f"{invite_id}_sms_{ts}"
        from contractor_ops.msg_logger import log_msg_delivery, mask_phone
        phone_masked = mask_phone(target_phone)

        log_msg_delivery(msg_type="invite", rid=sms_job_id, channel="sms", result="queued",
                         phone_masked=phone_masked)

        sms_result = await engine.sms_client.send_sms(target_phone, sms_text, context=f'invite_sms:{invite_id}')

        if sms_result.get('status') == 'sent':
            sms_sid = sms_result.get('provider_message_id', '')
            await db.notification_jobs.insert_one({
                'id': sms_job_id,
                'invite_id': invite_id,
                'event_type': 'invite_sms_direct',
                'target_phone': target_phone,
                'status': 'sent',
                'channel': 'sms',
                'provider_message_id': sms_sid,
                'created_by': user['id'],
                'created_at': ts,
                'updated_at': ts,
            })
            await _audit('invite', invite_id, 'resend_sms', user['id'], {
                'project_id': project_id, 'twilio_sid': sms_sid,
            })
            log_msg_delivery(msg_type="invite", rid=sms_job_id, channel="sms", result="sent",
                             provider_status=sms_sid[:20], phone_masked=phone_masked)
            notification_status = {
                'channel_used': 'sms', 'delivery_status': 'sent',
                'provider_message_id': sms_sid, 'job_id': sms_job_id,
            }
        else:
            error = sms_result.get('error', 'unknown')
            log_msg_delivery(msg_type="invite", rid=sms_job_id, channel="sms", result="failed",
                             error_code=str(error)[:80], phone_masked=phone_masked)
            notification_status = {
                'channel_used': 'sms', 'delivery_status': 'failed',
                'reason': str(error)[:200],
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"[INVITE-RESEND-SMS] Failed: {e}")
        notification_status = {'channel_used': 'none', 'delivery_status': 'failed', 'reason': str(e)[:200]}

    return {'success': True, 'message': 'SMS נשלח', 'notification_status': notification_status}


@router.post("/projects/{project_id}/invites/{invite_id}/cancel")
async def cancel_team_invite(project_id: str, invite_id: str, user: dict = Depends(get_current_user)):
    if user['role'] == 'viewer':
        raise HTTPException(status_code=403, detail='Viewers have read-only access')
    db = get_db()
    membership = await _get_project_membership(user, project_id)
    if membership['role'] not in ('project_manager',):
        raise HTTPException(status_code=403, detail='אין הרשאה')
    invite = await db.invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        invite = await db.team_invites.find_one({'id': invite_id, 'project_id': project_id})
    if not invite:
        raise HTTPException(status_code=404, detail='Invite not found')
    if invite['status'] != 'pending':
        raise HTTPException(status_code=400, detail='Can only cancel pending invites')
    ts = _now()
    if 'target_phone' in invite:
        await db.invites.update_one({'id': invite_id}, {'$set': {'status': 'cancelled', 'updated_at': ts}})
    else:
        await db.team_invites.update_one({'id': invite_id}, {'$set': {'status': 'cancelled', 'updated_at': ts}})
    await _audit('invite', invite_id, 'cancelled', user['id'], {'project_id': project_id})
    return {'success': True, 'message': 'הזמנה בוטלה'}
