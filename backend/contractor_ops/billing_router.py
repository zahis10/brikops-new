from fastapi import APIRouter, HTTPException, Depends, Request

from contractor_ops.router import get_db, get_current_user, _is_super_admin, logger
from contractor_ops.billing import get_billing_info

router = APIRouter(prefix="/api")


@router.get("/billing/me")
async def billing_me(user: dict = Depends(get_current_user)):
    info = await get_billing_info(user['id'])
    return info


@router.get("/billing/plans/active")
async def billing_plans_active(user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    if not _is_super_admin(user):
        has_any_project = await db.project_memberships.find_one(
            {'user_id': user['id'], 'role': {'$nin': ['contractor', 'viewer']}},
            {'_id': 0, 'project_id': 1}
        )
        if not has_any_project:
            has_org_role = await db.organization_memberships.find_one(
                {'user_id': user['id'], 'role': {'$in': ['org_admin', 'billing_admin']}},
                {'_id': 0}
            )
            if not has_org_role:
                org_owned = await db.organizations.find_one(
                    {'owner_user_id': user['id']}, {'_id': 0}
                )
                if not org_owned:
                    raise HTTPException(status_code=403, detail='אין הרשאה')
    plans = await db.billing_plans.find(
        {'is_active': True},
        {'_id': 0, 'id': 1, 'name': 1, 'version': 1, 'project_fee_monthly': 1, 'unit_tiers': 1}
    ).to_list(100)
    return plans


@router.get("/billing/org/{org_id}")
async def billing_org(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, get_billing_for_org
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            is_pm = await check_org_pm_role(user['id'], org_id)
            if not is_pm:
                raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיוב ארגון')
    result = await get_billing_for_org(org_id, user_id=user['id'])
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.post("/billing/org/{org_id}/checkout")
async def billing_checkout(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, preview_renewal
    from config import GI_BASE_URL
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not GI_BASE_URL:
        raise HTTPException(status_code=501, detail='Credit card payment coming soon')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת ניהול חיוב')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    cycle = body.get('cycle', 'monthly')
    renewal = await preview_renewal(org_id, cycle)
    amount = renewal.get('amount_ils', 0)
    if not amount or amount <= 0:
        raise HTTPException(status_code=400, detail='סכום לתשלום הוא ₪0 — יש לעדכן תמחור פרויקטים')
    db = get_db()
    org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1, 'billing': 1, 'tax_id': 1})
    org_name = org.get('name', '') if org else ''
    billing_data = org.get('billing', {}) if org else {}
    billing_email = billing_data.get('billing_email', '')
    if not billing_email:
        user_doc = await db.users.find_one({'id': user['id']}, {'_id': 0, 'email': 1})
        billing_email = user_doc.get('email', '') if user_doc else ''
    from contractor_ops.green_invoice_service import create_payment_form, create_or_get_client, GreenInvoiceError
    gi_client_id = billing_data.get('gi_client_id', '')
    if not gi_client_id:
        try:
            gi_client_id = await create_or_get_client(
                name=org_name or 'לקוח BrikOps',
                email=billing_email,
                tax_id=org.get('tax_id', '') if org else '',
            )
            await db.organizations.update_one(
                {'id': org_id},
                {'$set': {'billing.gi_client_id': gi_client_id}}
            )
            logger.info("[BILLING-GI] Stored gi_client_id=%s for org=%s", gi_client_id, org_id)
        except GreenInvoiceError as e:
            logger.warning("[BILLING-GI] Client creation failed for org %s: %s — proceeding without client_id (webhook will backfill)", org_id, str(e))
            gi_client_id = ''
    from config import PASSWORD_RESET_BASE_URL
    base_url = PASSWORD_RESET_BASE_URL.rstrip('/')
    success_url = f"{base_url}/billing/org/{org_id}?payment=success"
    failure_url = f"{base_url}/billing/org/{org_id}?payment=failure"
    cycle_he = 'שנתי' if cycle == 'yearly' else 'חודשי'
    description = f"מנוי BrikOps — {cycle_he} — {org_name}"
    try:
        result = await create_payment_form(
            client_name=org_name or 'לקוח BrikOps',
            client_email=billing_email,
            description=description,
            amount=amount,
            success_url=success_url,
            failure_url=failure_url,
            remarks=f"org_id={org_id} cycle={cycle}",
            client_id=gi_client_id,
        )
    except GreenInvoiceError as e:
        logger.error("[BILLING-GI] Payment form creation failed for org %s: %s", org_id, str(e))
        raise HTTPException(status_code=502, detail=f'שגיאה ביצירת טופס תשלום: {str(e)}')
    payment_url = result.get('url', '')
    if not payment_url:
        logger.error("[BILLING-GI] No URL in payment form response for org %s: %s", org_id, result)
        raise HTTPException(status_code=502, detail='לא התקבל קישור תשלום')
    import uuid
    from contractor_ops.billing import _now
    await db.audit_events.insert_one({
        'id': str(uuid.uuid4()),
        'event_type': 'billing',
        'entity_type': 'checkout',
        'entity_id': org_id,
        'action': 'gi_checkout_created',
        'actor_id': user['id'],
        'payload': {
            'org_id': org_id,
            'cycle': cycle,
            'amount': amount,
            'payment_url': payment_url,
        },
        'created_at': _now(),
    })
    return {'url': payment_url, 'amount': amount, 'cycle': cycle}


@router.get("/billing/preview-renewal")
async def billing_preview_renewal(request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, preview_renewal
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    scope = request.query_params.get('scope', 'org')
    org_id = request.query_params.get('id', '')
    cycle = request.query_params.get('cycle', 'monthly')
    if not org_id:
        raise HTTPException(status_code=400, detail='חובה לציין id')
    if cycle not in ('monthly', 'yearly'):
        raise HTTPException(status_code=400, detail='cycle חייב להיות monthly או yearly')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        pm_role = await check_org_pm_role(user['id'], org_id) if not billing_role else False
        if not billing_role and not pm_role:
            raise HTTPException(status_code=403, detail='אין הרשאה לצפות בתצוגה מקדימה של חידוש')
    result = await preview_renewal(org_id, cycle)
    return result


@router.post("/billing/org/{org_id}/payment-request")
async def billing_payment_request(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, create_payment_request
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    requested_by_kind = None
    if _is_super_admin(user):
        requested_by_kind = 'billing_manager'
    else:
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role in ('org_admin', 'billing_admin', 'owner'):
            requested_by_kind = 'billing_manager'
        else:
            raise HTTPException(status_code=403, detail='אין הרשאה ליצירת בקשת תשלום')
    body = await request.json()
    cycle = body.get('cycle', 'monthly')
    if cycle not in ('monthly', 'yearly'):
        raise HTTPException(status_code=400, detail='cycle חייב להיות monthly או yearly')
    note = body.get('note', '')
    contact_email = body.get('contact_email', '')
    try:
        result = await create_payment_request(org_id, user['id'], cycle, note, contact_email, requested_by_kind=requested_by_kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.get("/billing/org/{org_id}/payment-requests")
async def billing_list_payment_requests(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, check_org_pm_role, list_payment_requests
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    pm_only_filter = None
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            is_pm = await check_org_pm_role(user['id'], org_id)
            if not is_pm:
                raise HTTPException(status_code=403, detail='אין הרשאה לצפייה בבקשות תשלום')
            pm_only_filter = user['id']
    status_param = request.query_params.get('status', '')
    statuses = [s.strip() for s in status_param.split(',') if s.strip()] if status_param else None
    valid_statuses = {'requested', 'sent', 'paid', 'canceled', 'pending_review', 'rejected'}
    if statuses and not all(s in valid_statuses for s in statuses):
        raise HTTPException(status_code=400, detail='סטטוס לא תקין')
    result = await list_payment_requests(org_id, statuses, requested_by_user_id=pm_only_filter)
    return result


@router.get("/billing/org/{org_id}/payment-config")
async def billing_get_payment_config(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, get_payment_config
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאה לצפייה בהגדרות תשלום')
    result = await get_payment_config(org_id)
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.put("/billing/org/{org_id}/payment-config")
async def billing_update_payment_config(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, update_payment_config
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='רק אדמין ראשי יכול לעדכן הגדרות תשלום')
    body = await request.json()
    bank_details = body.get('bank_details', '')
    bit_phone = body.get('bit_phone', '')
    result = await update_payment_config(org_id, user['id'], bank_details, bit_phone)
    return result


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/mark-paid-by-customer")
async def billing_customer_mark_paid(org_id: str, request_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, customer_mark_paid
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה לסימון תשלום')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    customer_paid_note = body.get('customer_paid_note', '')
    try:
        result = await customer_mark_paid(org_id, request_id, user['id'], customer_paid_note)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/receipt")
async def billing_upload_receipt_form(org_id: str, request_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, upload_receipt
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה להעלאת אסמכתא')
    form = await request.form()
    file = form.get('file')
    if not file:
        raise HTTPException(status_code=400, detail='חובה לצרף קובץ')
    file_data = await file.read()
    if len(file_data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail='גודל הקובץ חורג מ-10MB')
    filename = file.filename or 'receipt'
    content_type = file.content_type or 'application/octet-stream'
    allowed_types = {'application/pdf', 'image/jpeg', 'image/png', 'image/jpg'}
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail='סוג קובץ לא נתמך — PDF, JPG, PNG בלבד')
    try:
        result = await upload_receipt(org_id, request_id, user['id'], file_data, filename, content_type)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/billing/org/{org_id}/payment-requests/{request_id}/receipt")
async def billing_get_receipt(org_id: str, request_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, get_receipt_url
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה לצפייה באסמכתא')
    try:
        result = await get_receipt_url(org_id, request_id)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/cancel")
async def billing_cancel_request(org_id: str, request_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, cancel_payment_request
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('org_admin', 'billing_admin', 'owner'):
            raise HTTPException(status_code=403, detail='אין הרשאה לבטל בקשות תשלום')
    try:
        result = await cancel_payment_request(org_id, request_id, user['id'])
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/org/{org_id}/payment-requests/{request_id}/reject")
async def billing_reject_request(org_id: str, request_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, reject_payment_request
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='רק אדמין ראשי יכול לדחות בקשות')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    rejection_reason = body.get('rejection_reason', '')
    try:
        result = await reject_payment_request(org_id, request_id, user['id'], rejection_reason)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/billing/org/{org_id}/mark-paid")
async def billing_mark_paid(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, mark_paid
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='רק אדמין ראשי יכול לאשר תשלומים')
    body = await request.json()
    request_id = body.get('request_id')
    cycle = body.get('cycle')
    paid_note = body.get('paid_note', '')
    try:
        result = await mark_paid(org_id, user['id'], request_id, cycle, paid_note)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/billing/project/{project_id}")
async def billing_project(project_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, get_billing_for_project
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון — לא ניתן להציג חיוב')
    if not _is_super_admin(user):
        membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0, 'role': 1}
        )
        mem_role = membership.get('role', 'none') if membership else 'none'
        if mem_role in ('contractor', 'viewer'):
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיוב פרויקט')
        if mem_role == 'none':
            billing_role = await check_org_billing_role(user['id'], org_id)
            if not billing_role:
                raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיוב פרויקט')
    result = await get_billing_for_project(project_id)
    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])
    can_edit = False
    if _is_super_admin(user):
        can_edit = True
    else:
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role in ('org_admin', 'billing_admin', 'owner'):
            can_edit = True
    result['user_can_edit_billing'] = can_edit
    membership = await db.project_memberships.find_one(
        {'user_id': user['id'], 'project_id': project_id}, {'_id': 0, 'role': 1}
    )
    result['user_project_role'] = membership.get('role') if membership else None
    return result


@router.patch("/billing/project/{project_id}")
async def billing_project_update(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, update_project_billing,
        recalc_org_total, create_project_billing
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת עדכון חיוב פרויקט')
    body = await request.json()
    allowed_fields = {'plan_id', 'contracted_units', 'status', 'setup_state', 'billing_contact_note'}
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail='לא סופקו שדות לעדכון')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        try:
            result = await create_project_billing(
                project_id, org_id, user['id'],
                plan_id=updates.get('plan_id'),
                contracted_units=updates.get('contracted_units', 0)
            )
            await recalc_org_total(org_id)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    try:
        result = await update_project_billing(pb['id'], updates, user['id'])
        await recalc_org_total(org_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/project/{project_id}/handoff-request")
async def billing_handoff_request(project_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, request_billing_handoff
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0, 'role': 1}
        )
        mem_role = membership.get('role', 'none') if membership else 'none'
        if mem_role in ('contractor', 'viewer', 'none'):
            billing_role = await check_org_billing_role(user['id'], org_id)
            if not billing_role:
                raise HTTPException(status_code=403, detail='אין הרשאה לבקשת העברת חיוב')
        if mem_role == 'management_team':
            raise HTTPException(status_code=403, detail='אין הרשאה לבקשת העברת חיוב')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    note = body.get('note', None)
    try:
        result = await request_billing_handoff(pb['id'], user['id'], note)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/project/{project_id}/handoff-ack")
async def billing_handoff_ack(project_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, acknowledge_billing_handoff
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאה לאישור העברת חיוב')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    try:
        result = await acknowledge_billing_handoff(pb['id'], user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/project/{project_id}/setup-complete")
async def billing_setup_complete(project_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, check_org_billing_role, complete_billing_setup
    )
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    db = get_db()
    project = await db.projects.find_one({'id': project_id}, {'_id': 0, 'org_id': 1})
    if not project:
        raise HTTPException(status_code=404, detail='פרויקט לא נמצא')
    org_id = project.get('org_id')
    if not org_id:
        raise HTTPException(status_code=400, detail='פרויקט ללא ארגון')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאה להשלמת הגדרת חיוב')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    try:
        result = await complete_billing_setup(pb['id'], user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/billing/org/{org_id}/invoice/preview")
async def invoice_preview(org_id: str, period: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import build_invoice_preview, check_and_enforce_dunning, validate_period_ym
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    try:
        validate_period_ym(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיובי ארגון')
    await check_and_enforce_dunning(org_id)
    preview = await build_invoice_preview(org_id, period)
    return preview


@router.post("/billing/org/{org_id}/invoice/generate")
async def invoice_generate(org_id: str, period: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import generate_invoice, validate_period_ym
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    try:
        validate_period_ym(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role or billing_role == 'org_admin':
            raise HTTPException(status_code=403, detail='אין הרשאה להפקת חשבוניות')
    invoice = await generate_invoice(org_id, period, user['id'])
    return invoice


@router.get("/billing/org/{org_id}/invoices")
async def invoice_list(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import list_invoices, check_and_enforce_dunning
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיובי ארגון')
    await check_and_enforce_dunning(org_id)
    invoices = await list_invoices(org_id)
    return {'invoices': invoices}


@router.get("/billing/org/{org_id}/invoices/{invoice_id}")
async def invoice_detail(org_id: str, invoice_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import get_invoice
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בחיובי ארגון')
    invoice = await get_invoice(org_id, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail='חשבונית לא נמצאה')
    return invoice


@router.post("/billing/org/{org_id}/invoices/{invoice_id}/mark-paid")
async def invoice_mark_paid(org_id: str, invoice_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    from contractor_ops.invoicing import mark_invoice_paid
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role or billing_role == 'org_admin':
            raise HTTPException(status_code=403, detail='אין הרשאה לסימון חשבונית כשולם')
    try:
        result = await mark_invoice_paid(org_id, invoice_id, user['id'])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/orgs/{org_id}/billing-contact")
async def get_billing_contact_endpoint(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, get_billing_contact
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת צפייה בפרטי חיוב ארגון')
    result = await get_billing_contact(org_id)
    if result.get('error'):
        raise HTTPException(status_code=404, detail=result['error'])
    return result


@router.put("/orgs/{org_id}/billing-contact")
async def update_billing_contact_endpoint(org_id: str, request: Request, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role, update_billing_contact
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if billing_role not in ('owner', 'billing_admin'):
            raise HTTPException(status_code=403, detail='אין הרשאת עדכון פרטי חיוב ארגון')
    body = await request.json()
    result = await update_billing_contact(org_id, body, user['id'])
    if result.get('error'):
        raise HTTPException(status_code=400, detail=result['error'])
    return result


RENEWAL_MAX_ATTEMPTS = 3
RENEWAL_GRACE_DAYS = 7


def _send_billing_alert_email(org_name: str, amount: float, gi_document_id: str, error_message: str, timestamp: str):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from config import STEPUP_EMAIL, SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_FROM_NAME, SMTP_REPLY_TO

    if not STEPUP_EMAIL or not SMTP_USER or not SMTP_PASS:
        logger.warning("[RENEWAL-ALERT] Cannot send alert email: STEPUP_EMAIL or SMTP not configured")
        return

    msg = MIMEMultipart('alternative')
    msg['From'] = f'{SMTP_FROM_NAME} <{SMTP_FROM}>'
    msg['To'] = STEPUP_EMAIL
    msg['Reply-To'] = SMTP_REPLY_TO
    msg['Subject'] = '⚠️ BrikOps: חיוב הצליח אבל עדכון המנוי נכשל'

    text_body = (
        f'ארגון: {org_name}\n'
        f'סכום: ₪{amount:.2f}\n'
        f'מסמך GI: {gi_document_id}\n'
        f'שגיאה: {error_message}\n'
        f'זמן: {timestamp}\n\n'
        '→ היכנס לפאנל ניהול ולחץ "Resolve"'
    )
    html_body = f'''
    <div dir="rtl" style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #dc2626;">⚠️ חיוב הצליח — עדכון מנוי נכשל</h2>
        <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 16px; margin: 16px 0;">
            <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
                <tr><td style="padding: 4px 0; font-weight: bold; width: 100px;">ארגון:</td><td>{org_name}</td></tr>
                <tr><td style="padding: 4px 0; font-weight: bold;">סכום:</td><td>₪{amount:.2f}</td></tr>
                <tr><td style="padding: 4px 0; font-weight: bold;">מסמך GI:</td><td style="font-family: monospace;">{gi_document_id}</td></tr>
                <tr><td style="padding: 4px 0; font-weight: bold;">שגיאה:</td><td style="color: #dc2626;">{error_message}</td></tr>
                <tr><td style="padding: 4px 0; font-weight: bold;">זמן:</td><td>{timestamp}</td></tr>
            </table>
        </div>
        <p style="color: #666; font-size: 13px;">הלקוח חויב בהצלחה אך המנוי לא עודכן. היכנס לפאנל ניהול ולחץ <b>"Resolve"</b> כדי לתקן.</p>
    </div>
    '''
    msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, STEPUP_EMAIL, msg.as_string())
        logger.info("[RENEWAL-ALERT] Alert email sent to %s for org=%s doc=%s", STEPUP_EMAIL[:4] + '***', org_name, gi_document_id)
    except Exception as e:
        logger.error("[RENEWAL-ALERT] Failed to send alert email: %s", str(e))


@router.post("/billing/run-renewals")
async def billing_run_renewals(request: Request, user: dict = Depends(get_current_user)):
    import uuid
    from datetime import timedelta
    from contractor_ops.billing import (
        BILLING_V1_ENABLED, get_subscription, mark_paid,
        compute_org_billing_amount, apply_pending_decreases,
        _now, _now_dt, _parse_dt,
    )
    from contractor_ops.green_invoice_service import charge_saved_card, GreenInvoiceError

    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail='Super admin only')

    db = get_db()
    now = _now_dt()
    now_iso = _now()
    period_ym = now.strftime("%Y-%m")

    all_subs = await db.subscriptions.find(
        {'status': {'$in': ['active', 'past_due']}, 'auto_renew': True},
        {'_id': 0, 'org_id': 1, 'paid_until': 1, 'status': 1, 'auto_renew': 1}
    ).to_list(10000)

    due_orgs = []
    for sub in all_subs:
        paid_until = _parse_dt(sub.get('paid_until'))
        if paid_until and paid_until < now:
            due_orgs.append({'org_id': sub['org_id'], 'status': sub.get('status', 'active'), 'paid_until': paid_until})

    results = {'processed': 0, 'charged': 0, 'skipped': 0, 'failed': 0, 'past_due': 0, 'charged_but_mark_paid_failed': 0, 'errors': []}

    for org_info in due_orgs:
        org_id = org_info['org_id']
        sub_status = org_info['status']
        paid_until_dt = org_info['paid_until']
        results['processed'] += 1

        existing_success = await db.gi_webhook_log.find_one({
            'org_id': org_id,
            'cycle': 'monthly',
            'result': 'success',
            'created_at': {'$gte': (now - timedelta(days=35)).isoformat()},
        }, {'_id': 0, 'id': 1})
        if existing_success:
            logger.info("[RENEWALS] Org %s already has successful charge this period, skipping", org_id)
            results['skipped'] += 1
            continue

        existing_attempt = await db.billing_renewal_attempts.find_one({
            'org_id': org_id,
            'period_ym': period_ym,
            'result': 'success',
        }, {'_id': 0})
        if existing_attempt:
            logger.info("[RENEWALS] Org %s already renewed for %s, skipping", org_id, period_ym)
            results['skipped'] += 1
            continue

        attempt_count = await db.billing_renewal_attempts.count_documents({
            'org_id': org_id,
            'period_ym': period_ym,
        })

        if attempt_count >= RENEWAL_MAX_ATTEMPTS:
            days_overdue = (now - paid_until_dt).days
            if days_overdue > RENEWAL_GRACE_DAYS and sub_status != 'past_due':
                await db.subscriptions.update_one(
                    {'org_id': org_id},
                    {'$set': {'status': 'past_due', 'updated_at': now_iso}}
                )
                await db.audit_events.insert_one({
                    'id': str(uuid.uuid4()),
                    'event_type': 'billing',
                    'entity_type': 'organization',
                    'entity_id': org_id,
                    'action': 'billing_past_due',
                    'actor_id': 'system',
                    'created_at': now_iso,
                    'payload': {
                        'period_ym': period_ym,
                        'attempts': attempt_count,
                        'days_overdue': days_overdue,
                    },
                })
                logger.warning("[RENEWALS] Org %s moved to past_due after %d attempts, %d days overdue",
                               org_id, attempt_count, days_overdue)
                results['past_due'] += 1
            else:
                logger.info("[RENEWALS] Org %s: %d attempts exhausted, %d days overdue (grace=%d days, status=%s)",
                            org_id, attempt_count, days_overdue, RENEWAL_GRACE_DAYS, sub_status)
                results['skipped'] += 1
            continue

        org = await db.organizations.find_one({'id': org_id}, {'_id': 0, 'name': 1, 'billing': 1})
        if not org:
            results['skipped'] += 1
            continue

        billing_data = org.get('billing', {})
        card_token = billing_data.get('gi_card_token', '')
        client_id = billing_data.get('gi_client_id', '')
        org_name = org.get('name', '')

        attempt_id = str(uuid.uuid4())
        attempt_entry = {
            'id': attempt_id,
            'org_id': org_id,
            'period_ym': period_ym,
            'attempt_number': attempt_count + 1,
            'result': 'pending',
            'created_at': now_iso,
        }
        await db.billing_renewal_attempts.insert_one(attempt_entry)

        if not card_token:
            await db.billing_renewal_attempts.update_one(
                {'id': attempt_id},
                {'$set': {'result': 'no_card_token', 'error': 'No saved card token'}}
            )
            logger.warning("[RENEWALS] Org %s has no card token, skipping charge", org_id)
            results['failed'] += 1
            results['errors'].append({'org_id': org_id, 'error': 'no_card_token'})
            continue

        try:
            await apply_pending_decreases(org_id)
            billing_calc = await compute_org_billing_amount(org_id, 'monthly')
            amount = billing_calc.get('amount_ils', 0)
        except Exception as e:
            await db.billing_renewal_attempts.update_one(
                {'id': attempt_id},
                {'$set': {'result': 'billing_calc_error', 'error': str(e)}}
            )
            logger.error("[RENEWALS] compute_org_billing_amount failed for org %s: %s", org_id, str(e))
            results['failed'] += 1
            results['errors'].append({'org_id': org_id, 'error': f'billing_calc_error: {e}'})
            continue

        if not amount or amount <= 0:
            await db.billing_renewal_attempts.update_one(
                {'id': attempt_id},
                {'$set': {'result': 'zero_amount', 'error': f'Amount is {amount}'}}
            )
            logger.warning("[RENEWALS] Org %s has zero amount, skipping", org_id)
            results['skipped'] += 1
            continue

        try:
            description = f"מנוי BrikOps — חודשי — {org_name}"
            charge_result = await charge_saved_card(
                client_id=client_id,
                card_token=card_token,
                description=description,
                amount=amount,
                remarks=f"org_id={org_id} cycle=monthly renewal=auto period={period_ym}",
            )
            doc_id = charge_result.get('id', '')

            try:
                await mark_paid(org_id, 'system_renewal', None, 'monthly', f"Auto-renewal doc={doc_id} amount={amount}")
                await db.billing_renewal_attempts.update_one(
                    {'id': attempt_id},
                    {'$set': {'result': 'success', 'gi_document_id': doc_id, 'amount': amount}}
                )
                logger.info("[RENEWALS] Charged org=%s amount=%.2f doc=%s", org_id, amount, doc_id)
                results['charged'] += 1
            except Exception as mp_err:
                await db.billing_renewal_attempts.update_one(
                    {'id': attempt_id},
                    {'$set': {
                        'result': 'charged_but_mark_paid_failed',
                        'gi_document_id': doc_id,
                        'amount': amount,
                        'error': str(mp_err),
                    }}
                )
                logger.error("[RENEWALS] Charge succeeded (doc=%s) but mark_paid failed for org %s: %s",
                             doc_id, org_id, str(mp_err))
                results['charged_but_mark_paid_failed'] += 1
                results['errors'].append({'org_id': org_id, 'error': f'mark_paid_failed: {mp_err}', 'gi_document_id': doc_id})
                try:
                    _send_billing_alert_email(
                        org_name=org_name,
                        amount=amount,
                        gi_document_id=doc_id,
                        error_message=str(mp_err),
                        timestamp=now_iso,
                    )
                except Exception:
                    pass

        except GreenInvoiceError as e:
            await db.billing_renewal_attempts.update_one(
                {'id': attempt_id},
                {'$set': {'result': 'charge_failed', 'error': str(e), 'error_code': e.error_code}}
            )
            logger.error("[RENEWALS] Charge failed for org %s (attempt %d): %s",
                         org_id, attempt_count + 1, str(e))
            results['failed'] += 1
            results['errors'].append({'org_id': org_id, 'error': str(e), 'attempt': attempt_count + 1})

        except Exception as e:
            await db.billing_renewal_attempts.update_one(
                {'id': attempt_id},
                {'$set': {'result': 'unexpected_error', 'error': str(e)}}
            )
            logger.error("[RENEWALS] Unexpected error for org %s: %s", org_id, str(e))
            results['failed'] += 1
            results['errors'].append({'org_id': org_id, 'error': f'unexpected: {e}'})

    logger.info("[RENEWALS] Run complete: %s", results)
    return results


_webhook_call_times: list = []
WEBHOOK_RATE_LIMIT_MAX = 30
WEBHOOK_RATE_LIMIT_WINDOW = 60


@router.post("/billing/webhook/greeninvoice")
async def billing_webhook_greeninvoice(request: Request):
    import time
    import uuid
    import json
    from contractor_ops.billing import _now, get_subscription, mark_paid
    from contractor_ops.green_invoice_service import get_document, compute_payload_hash, GreenInvoiceError
    from config import GI_BASE_URL

    client_ip = request.client.host if request.client else 'unknown'
    now_ts = time.time()

    while _webhook_call_times and _webhook_call_times[0] < now_ts - WEBHOOK_RATE_LIMIT_WINDOW:
        _webhook_call_times.pop(0)
    if len(_webhook_call_times) >= WEBHOOK_RATE_LIMIT_MAX:
        logger.warning("[GI-WEBHOOK] Rate limited from IP=%s", client_ip)
        return {"status": "rate_limited"}
    _webhook_call_times.append(now_ts)

    try:
        payload = await request.json()
    except Exception:
        logger.error("[GI-WEBHOOK] Invalid JSON from IP=%s", client_ip)
        return {"status": "invalid_json"}

    from datetime import datetime, timedelta, timezone

    payload_hash = compute_payload_hash(payload)
    safe_summary = {k: payload.get(k) for k in ("id", "type", "number", "total", "currency", "status") if k in payload}
    logger.info("[GI-WEBHOOK] Received webhook IP=%s hash=%s summary=%s",
                client_ip, payload_hash, json.dumps(safe_summary, ensure_ascii=False))

    db = get_db()

    RAW_PAYLOAD_LOG_LIMIT = 10
    raw_log_count = await db.gi_webhook_log.count_documents({'raw_payload': {'$exists': True}})
    should_log_raw = raw_log_count < RAW_PAYLOAD_LOG_LIMIT

    def _add_raw(entry: dict) -> dict:
        if should_log_raw:
            entry['raw_payload'] = payload
            entry['raw_payload_expires_at'] = datetime.now(timezone.utc) + timedelta(days=30)
        return entry

    doc_id = payload.get("id", "")
    if not doc_id:
        logger.warning("[GI-WEBHOOK] No document id in payload hash=%s", payload_hash)
        await db.gi_webhook_log.insert_one(_add_raw({
            'id': str(uuid.uuid4()),
            'payload_hash': payload_hash,
            'ip': client_ip,
            'result': 'no_doc_id',
            'created_at': _now(),
        }))
        return {"status": "ok"}

    existing = await db.gi_webhook_log.find_one({'gi_document_id': doc_id, 'result': 'success'}, {'_id': 0, 'id': 1})
    if existing:
        logger.info("[GI-WEBHOOK] Duplicate doc_id=%s, already processed", doc_id)
        return {"status": "ok"}

    from config import GI_WEBHOOK_SECRET
    if GI_WEBHOOK_SECRET:
        incoming_secret = request.headers.get("X-Webhook-Token", "") or request.query_params.get("token", "")
        if incoming_secret != GI_WEBHOOK_SECRET:
            logger.warning("[GI-WEBHOOK] Invalid webhook secret from IP=%s", client_ip)
            await db.gi_webhook_log.insert_one(_add_raw({
                'id': str(uuid.uuid4()),
                'payload_hash': payload_hash,
                'ip': client_ip,
                'result': 'auth_failed',
                'created_at': _now(),
            }))
            return {"status": "ok"}

    if not GI_BASE_URL:
        logger.error("[GI-WEBHOOK] GI_BASE_URL not configured, cannot verify document")
        await db.gi_webhook_log.insert_one(_add_raw({
            'id': str(uuid.uuid4()),
            'gi_document_id': doc_id,
            'payload_hash': payload_hash,
            'ip': client_ip,
            'result': 'no_gi_config',
            'created_at': _now(),
        }))
        return {"status": "ok"}

    verified_doc = None
    try:
        verified_doc = await get_document(doc_id)
    except GreenInvoiceError as e:
        logger.error("[GI-WEBHOOK] Failed to verify doc %s: %s", doc_id, str(e))
        await db.gi_webhook_log.insert_one(_add_raw({
            'id': str(uuid.uuid4()),
            'gi_document_id': doc_id,
            'payload_hash': payload_hash,
            'ip': client_ip,
            'result': 'verification_failed',
            'error': str(e),
            'created_at': _now(),
        }))
        return {"status": "ok"}

    doc_status = verified_doc.get("status", "")
    if doc_status not in ("", "active", "paid"):
        logger.warning("[GI-WEBHOOK] Doc %s has non-paid status: %s", doc_id, doc_status)
        await db.gi_webhook_log.insert_one(_add_raw({
            'id': str(uuid.uuid4()),
            'gi_document_id': doc_id,
            'payload_hash': payload_hash,
            'ip': client_ip,
            'result': 'not_paid_status',
            'doc_status': doc_status,
            'created_at': _now(),
        }))
        return {"status": "ok"}

    remarks = verified_doc.get("remarks", "") or ""
    org_id = ""
    cycle = "monthly"
    if remarks:
        for part in remarks.split():
            if part.startswith("org_id="):
                org_id = part.split("=", 1)[1]
            elif part.startswith("cycle="):
                cycle = part.split("=", 1)[1]

    doc_total = verified_doc.get("total", 0) or verified_doc.get("amount", 0) or 0

    log_entry = {
        'id': str(uuid.uuid4()),
        'gi_document_id': doc_id,
        'payload_hash': payload_hash,
        'ip': client_ip,
        'org_id': org_id,
        'cycle': cycle,
        'doc_total': doc_total,
        'doc_status': doc_status,
        'result': 'pending',
        'created_at': _now(),
    }
    if should_log_raw:
        log_entry['raw_payload'] = payload
        log_entry['raw_verified_doc'] = verified_doc
        log_entry['raw_payload_expires_at'] = datetime.now(timezone.utc) + timedelta(days=30)
        logger.info("[GI-WEBHOOK] Logging full raw payload+doc (%d/%d)", raw_log_count + 1, RAW_PAYLOAD_LOG_LIMIT)

    if not org_id:
        log_entry['result'] = 'no_org_id'
        logger.warning("[GI-WEBHOOK] Could not extract org_id from verified remarks: %s", remarks)
        await db.gi_webhook_log.insert_one(log_entry)
        return {"status": "ok"}

    if doc_total <= 0:
        log_entry['result'] = 'zero_amount'
        logger.warning("[GI-WEBHOOK] Doc %s has zero/negative total: %s", doc_id, doc_total)
        await db.gi_webhook_log.insert_one(log_entry)
        return {"status": "ok"}

    try:
        result = await mark_paid(org_id, 'gi_webhook', None, cycle, f"GI doc={doc_id} total={doc_total}")
        log_entry['result'] = 'success'
        log_entry['mark_paid_result'] = {
            'paid_until': result.get('paid_until'),
            'status': result.get('status'),
        }
        logger.info("[GI-WEBHOOK] Payment processed for org=%s doc=%s cycle=%s total=%s", org_id, doc_id, cycle, doc_total)
    except Exception as e:
        log_entry['result'] = 'mark_paid_error'
        log_entry['error'] = str(e)
        logger.error("[GI-WEBHOOK] mark_paid failed for org=%s: %s", org_id, str(e))

    payment_details = {}
    if verified_doc.get("payment") and isinstance(verified_doc["payment"], list) and len(verified_doc["payment"]) > 0:
        p = verified_doc["payment"][0]
        payment_details = {
            'card_suffix': p.get("cardSuffix", p.get("last4", "")),
            'card_type': p.get("cardType", ""),
        }
        if p.get("cardToken"):
            payment_details['has_card_token'] = True

    gi_client_id_from_doc = ""
    if verified_doc.get("client") and isinstance(verified_doc["client"], dict):
        gi_client_id_from_doc = verified_doc["client"].get("id", "")

    if payment_details:
        log_entry['payment_details'] = payment_details
        if org_id:
            update_fields = {'billing.gi_document_id': doc_id}
            if payment_details.get('has_card_token'):
                p = verified_doc["payment"][0]
                update_fields['billing.gi_card_token'] = p["cardToken"]
                update_fields['billing.gi_card_suffix'] = payment_details.get('card_suffix', '')
            if gi_client_id_from_doc:
                update_fields['billing.gi_client_id'] = gi_client_id_from_doc
            await db.organizations.update_one(
                {'id': org_id},
                {'$set': update_fields}
            )
            logger.info("[GI-WEBHOOK] Updated billing for org=%s suffix=%s client_id=%s",
                        org_id, payment_details.get('card_suffix', ''), gi_client_id_from_doc or 'none')
    elif gi_client_id_from_doc and org_id:
        await db.organizations.update_one(
            {'id': org_id},
            {'$set': {'billing.gi_client_id': gi_client_id_from_doc, 'billing.gi_document_id': doc_id}}
        )
        logger.info("[GI-WEBHOOK] Stored gi_client_id=%s for org=%s from webhook", gi_client_id_from_doc, org_id)

    await db.gi_webhook_log.insert_one(log_entry)
    return {"status": "ok"}


@router.get("/billing/failed-renewals")
async def billing_failed_renewals(request: Request, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="Super admin only")
    db = get_db()
    cursor = db.billing_renewal_attempts.find(
        {'result': 'charged_but_mark_paid_failed'},
        sort=[('created_at', -1)],
    ).limit(50)
    items = []
    async for doc in cursor:
        org = await db.organizations.find_one({'id': doc.get('org_id')}, {'name': 1})
        items.append({
            'id': doc.get('id'),
            'org_id': doc.get('org_id'),
            'org_name': org.get('name', '') if org else '',
            'gi_document_id': doc.get('gi_document_id', ''),
            'amount': doc.get('amount', 0),
            'error': doc.get('error', ''),
            'created_at': doc.get('created_at', '') if isinstance(doc.get('created_at'), str) else (doc['created_at'].isoformat() if doc.get('created_at') else ''),
            'resolved': doc.get('resolved', False),
            'resolved_at': doc.get('resolved_at', None) if isinstance(doc.get('resolved_at'), str) else (doc['resolved_at'].isoformat() if doc.get('resolved_at') else None),
        })
    unresolved = [i for i in items if not i.get('resolved')]
    return {"items": items, "unresolved_count": len(unresolved)}


@router.post("/billing/resolve-failed-renewal")
async def billing_resolve_failed_renewal(request: Request, user: dict = Depends(get_current_user)):
    if not _is_super_admin(user):
        raise HTTPException(status_code=403, detail="Super admin only")
    from contractor_ops.billing import mark_paid, _now
    db = get_db()
    body = await request.json()
    attempt_id = body.get('attempt_id')
    if not attempt_id:
        raise HTTPException(status_code=400, detail="attempt_id required")

    attempt = await db.billing_renewal_attempts.find_one({'id': attempt_id})
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    if attempt.get('result') != 'charged_but_mark_paid_failed':
        raise HTTPException(status_code=400, detail="Attempt is not in charged_but_mark_paid_failed state")
    if attempt.get('resolved'):
        raise HTTPException(status_code=400, detail="Already resolved")

    org_id = attempt['org_id']
    doc_id = attempt.get('gi_document_id', '')
    amount = attempt.get('amount', 0)

    result = await mark_paid(org_id, 'system_renewal_resolve', None, 'monthly', f"Resolved failed renewal doc={doc_id} amount={amount}")

    await db.billing_renewal_attempts.update_one(
        {'id': attempt_id},
        {'$set': {
            'resolved': True,
            'resolved_at': _now(),
            'resolved_by': user.get('email', user.get('id', '')),
            'resolve_result': result,
        }}
    )

    logger.info("[RESOLVE-RENEWAL] Resolved attempt=%s org=%s doc=%s by=%s",
                attempt_id, org_id, doc_id, user.get('email', ''))
    return {"status": "resolved", "mark_paid_result": result}
