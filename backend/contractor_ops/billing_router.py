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
async def billing_checkout(org_id: str, user: dict = Depends(get_current_user)):
    from contractor_ops.billing import BILLING_V1_ENABLED, check_org_billing_role
    if not BILLING_V1_ENABLED:
        raise HTTPException(status_code=404, detail='Not found')
    if not _is_super_admin(user):
        billing_role = await check_org_billing_role(user['id'], org_id)
        if not billing_role:
            raise HTTPException(status_code=403, detail='אין הרשאת ניהול חיוב')
    raise HTTPException(status_code=501, detail='Credit card payment coming soon', headers={'X-Feature': 'stripe_checkout'})


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
        is_pm = await check_org_pm_role(user['id'], org_id)
        if billing_role in ('org_admin', 'billing_admin', 'owner'):
            requested_by_kind = 'billing_manager'
        elif is_pm:
            requested_by_kind = 'pm_handoff'
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
        BILLING_V1_ENABLED, check_org_billing_role, update_project_billing, recalc_org_total
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
            from contractor_ops.billing import check_org_pm_role
            is_pm = await check_org_pm_role(user['id'], org_id)
            if not is_pm:
                raise HTTPException(status_code=403, detail='אין הרשאת עדכון חיוב פרויקט')
            pm_project = await db.project_memberships.find_one(
                {'user_id': user['id'], 'project_id': project_id, 'role': 'project_manager'},
                {'_id': 0}
            )
            if not pm_project:
                raise HTTPException(status_code=403, detail='אין הרשאת עדכון חיוב פרויקט זה')
    pb = await db.project_billing.find_one({'project_id': project_id}, {'_id': 0, 'id': 1})
    if not pb:
        raise HTTPException(status_code=404, detail='אין רשומת חיוב לפרויקט')
    body = await request.json()
    allowed_fields = {'plan_id', 'contracted_units', 'status', 'setup_state', 'billing_contact_note'}
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        raise HTTPException(status_code=400, detail='לא סופקו שדות לעדכון')
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
