import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from contractor_ops.router import get_db, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/dashboard")

TERMINAL_TASK_STATUSES = ("closed", "done", "cancelled")


def _require_super_admin(user: dict):
    if user.get('platform_role') != 'super_admin':
        raise HTTPException(status_code=403, detail='Forbidden')


def _churn_status(last_login_iso: str | None) -> str:
    if not last_login_iso:
        return 'unknown'
    try:
        last = datetime.fromisoformat(last_login_iso.replace('Z', '+00:00'))
    except Exception:
        return 'unknown'
    days = (datetime.now(timezone.utc) - last).days
    if days < 7:
        return 'active'
    if days <= 30:
        return 'at_risk'
    return 'dormant'


def _sub_status_label(status: str | None) -> str:
    m = {
        'active': 'פעיל',
        'trial': 'ניסיון',
        'inactive': 'לא פעיל',
        'paywalled': 'חסום',
    }
    return m.get(status or '', status or 'לא ידוע')


@router.get("/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    _require_super_admin(user)
    db = get_db()
    now = datetime.now(timezone.utc)
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    orgs = await db.organizations.find({}, {'_id': 0}).to_list(5000)
    org_map = {o['id']: o for o in orgs}
    org_ids = list(org_map.keys())

    projects = await db.projects.find(
        {'org_id': {'$in': org_ids}},
        {'_id': 0, 'id': 1, 'org_id': 1, 'name': 1}
    ).to_list(50000)
    proj_to_org = {p['id']: p['org_id'] for p in projects}
    org_projects = {}
    for p in projects:
        org_projects.setdefault(p['org_id'], []).append(p)

    buildings_agg = await db.buildings.aggregate([
        {'$match': {'project_id': {'$in': list(proj_to_org.keys())}, 'archived': {'$ne': True}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(50000)
    buildings_per_project = {r['_id']: r['count'] for r in buildings_agg}

    units_agg = await db.units.aggregate([
        {'$lookup': {'from': 'floors', 'localField': 'floor_id', 'foreignField': 'id', 'as': 'floor'}},
        {'$unwind': '$floor'},
        {'$lookup': {'from': 'buildings', 'localField': 'floor.building_id', 'foreignField': 'id', 'as': 'building'}},
        {'$unwind': '$building'},
        {'$match': {'building.project_id': {'$in': list(proj_to_org.keys())}}},
        {'$group': {'_id': '$building.project_id', 'count': {'$sum': 1}}}
    ]).to_list(50000)
    units_per_project = {r['_id']: r['count'] for r in units_agg}

    subs = await db.subscriptions.find(
        {'org_id': {'$in': org_ids}}, {'_id': 0}
    ).to_list(5000)
    sub_map = {s['org_id']: s for s in subs}

    billing_agg = await db.project_billing.aggregate([
        {'$match': {'org_id': {'$in': org_ids}, 'status': 'active'}},
        {'$group': {'_id': '$org_id', 'total': {'$sum': '$monthly_total'}}}
    ]).to_list(5000)
    monthly_cost_map = {r['_id']: r['total'] for r in billing_agg}

    memberships = await db.organization_memberships.find(
        {'org_id': {'$in': org_ids}}, {'_id': 0, 'org_id': 1, 'user_id': 1}
    ).to_list(50000)
    org_user_ids = {}
    for m in memberships:
        org_user_ids.setdefault(m['org_id'], []).append(m['user_id'])
    all_user_ids = list({uid for uids in org_user_ids.values() for uid in uids})

    users_login = await db.users.find(
        {'id': {'$in': all_user_ids}},
        {'_id': 0, 'id': 1, 'last_login_at': 1}
    ).to_list(50000)
    user_login_map = {u['id']: u.get('last_login_at') for u in users_login}

    org_last_login = {}
    for oid, uids in org_user_ids.items():
        logins = [user_login_map.get(uid) for uid in uids if user_login_map.get(uid)]
        org_last_login[oid] = max(logins) if logins else None

    project_ids = list(proj_to_org.keys())
    tasks_30d_agg = await db.tasks.aggregate([
        {'$match': {'project_id': {'$in': project_ids},
                    'created_at': {'$gte': thirty_days_ago}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(50000)
    tasks_30d_per_project = {r['_id']: r['count'] for r in tasks_30d_agg}

    protocols_30d_agg = await db.handover_protocols.aggregate([
        {'$match': {'project_id': {'$in': project_ids},
                    'created_at': {'$gte': thirty_days_ago}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(50000)
    protocols_30d_per_project = {r['_id']: r['count'] for r in protocols_30d_agg}

    tasks_total_agg = await db.tasks.aggregate([
        {'$match': {'project_id': {'$in': project_ids}}},
        {'$group': {
            '_id': '$project_id',
            'total': {'$sum': 1},
            'closed': {'$sum': {'$cond': [{'$in': ['$status', list(TERMINAL_TASK_STATUSES)]}, 1, 0]}}
        }}
    ]).to_list(50000)
    tasks_total_per_project = {r['_id']: r for r in tasks_total_agg}

    has_activity_map = {}
    for pid, org_id in proj_to_org.items():
        t = tasks_total_per_project.get(pid, {}).get('total', 0)
        if t > 0:
            has_activity_map[org_id] = True

    protocols_ever_agg = await db.handover_protocols.aggregate([
        {'$match': {'project_id': {'$in': project_ids}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(50000)
    for r in protocols_ever_agg:
        oid = proj_to_org.get(r['_id'])
        if oid and r['count'] > 0:
            has_activity_map[oid] = True

    invoices_agg = await db.invoices.aggregate([
        {'$match': {'org_id': {'$in': org_ids}, 'status': {'$in': ['issued', 'past_due']}}},
        {'$group': {'_id': '$org_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    open_invoices_map = {r['_id']: r['count'] for r in invoices_agg}

    overdue_invoices = await db.invoices.find(
        {'org_id': {'$in': org_ids}, 'status': 'past_due'},
        {'_id': 0, 'id': 1, 'org_id': 1, 'created_at': 1, 'due_date': 1}
    ).to_list(5000)

    org_rows = []
    churn_counts = {'active': 0, 'at_risk': 0, 'dormant': 0, 'unknown': 0}
    alerts = []

    for org in orgs:
        oid = org['id']
        oname = org.get('name', '')

        proj_list = org_projects.get(oid, [])
        proj_count = len(proj_list)
        proj_ids_for_org = [p['id'] for p in proj_list]

        bldg_count = sum(buildings_per_project.get(pid, 0) for pid in proj_ids_for_org)
        unit_count = sum(units_per_project.get(pid, 0) for pid in proj_ids_for_org)
        defects_30d = sum(tasks_30d_per_project.get(pid, 0) for pid in proj_ids_for_org)
        protocols_30d = sum(protocols_30d_per_project.get(pid, 0) for pid in proj_ids_for_org)

        total_defects = sum(tasks_total_per_project.get(pid, {}).get('total', 0) for pid in proj_ids_for_org)
        closed_defects = sum(tasks_total_per_project.get(pid, {}).get('closed', 0) for pid in proj_ids_for_org)
        close_rate = round(closed_defects / total_defects * 100, 1) if total_defects > 0 else 0

        sub = sub_map.get(oid, {})
        sub_status = sub.get('status', 'inactive')
        monthly_cost = monthly_cost_map.get(oid, 0)
        open_inv = open_invoices_map.get(oid, 0)
        last_login = org_last_login.get(oid)

        churn = _churn_status(last_login)
        if sub_status == 'inactive' and churn != 'unknown':
            churn = 'dormant'
        churn_counts[churn] += 1

        org_rows.append({
            'id': oid,
            'name': oname,
            'created_at': org.get('created_at', ''),
            'projects_count': proj_count,
            'units_count': unit_count,
            'buildings_count': bldg_count,
            'defects_30d': defects_30d,
            'protocols_30d': protocols_30d,
            'defect_close_rate': close_rate,
            'last_login': last_login,
            'subscription_status': sub_status,
            'monthly_cost': monthly_cost,
            'open_invoices': open_inv,
            'churn_status': churn,
        })

        if churn == 'dormant' and has_activity_map.get(oid):
            days_since = None
            if last_login:
                try:
                    days_since = (now - datetime.fromisoformat(last_login.replace('Z', '+00:00'))).days
                except Exception:
                    pass
            alerts.append({
                'type': 'dormant',
                'org_id': oid,
                'org_name': oname,
                'last_login': last_login,
                'days_inactive': days_since,
            })

        if proj_count == 0:
            alerts.append({
                'type': 'no_projects',
                'org_id': oid,
                'org_name': oname,
            })

        if sub_status == 'trial':
            paid_until = sub.get('paid_until')
            if paid_until:
                try:
                    trial_end = datetime.fromisoformat(paid_until.replace('Z', '+00:00'))
                    if 0 <= (trial_end - now).days <= 7:
                        alerts.append({
                            'type': 'trial_ending',
                            'org_id': oid,
                            'org_name': oname,
                            'trial_end': paid_until,
                        })
                except Exception:
                    pass

    for inv in overdue_invoices:
        created = inv.get('due_date') or inv.get('created_at', '')
        try:
            inv_date = datetime.fromisoformat(created.replace('Z', '+00:00'))
            days_overdue = (now - inv_date).days
            if days_overdue > 14:
                alerts.append({
                    'type': 'overdue_invoice',
                    'org_id': inv['org_id'],
                    'org_name': org_map.get(inv['org_id'], {}).get('name', ''),
                    'invoice_id': inv['id'],
                    'days_overdue': days_overdue,
                })
        except Exception:
            pass

    active_sub_count = sum(1 for s in subs if s.get('status') in ('active', 'trial'))
    total_projects = len(projects)
    total_units = sum(units_per_project.values())
    monthly_revenue = sum(monthly_cost_map.values())

    activity_chart = [
        {
            'org_name': r['name'],
            'defects_30d': r['defects_30d'],
            'protocols_30d': r['protocols_30d'],
        }
        for r in sorted(org_rows, key=lambda x: x['defects_30d'] + x['protocols_30d'], reverse=True)
        if r['defects_30d'] + r['protocols_30d'] > 0
    ][:15]

    return {
        'summary': {
            'active_orgs': active_sub_count,
            'total_projects': total_projects,
            'total_units': total_units,
            'monthly_revenue': monthly_revenue,
        },
        'alerts': alerts,
        'activity_chart': activity_chart,
        'churn_chart': churn_counts,
        'organizations': org_rows,
    }
