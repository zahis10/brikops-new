import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from contractor_ops.router import get_db, get_current_user
from contractor_ops.constants import TERMINAL_TASK_STATUSES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/analytics")

ADMIN_SCORE_WEIGHTS = {
    'login_recency': 30,
    'defects_created': 15,
    'defects_closed': 15,
    'qc_checked': 15,
    'handover': 10,
    'photos': 10,
    'whatsapp': 5,
}


def _require_super_admin(user: dict):
    if user.get('platform_role') != 'super_admin':
        raise HTTPException(status_code=403, detail='Forbidden')


def _compute_admin_score(metrics: dict, period: int) -> int:
    score = 0.0
    login_days = metrics.get('login_days_ago')
    if login_days is not None:
        if login_days <= 1:
            score += ADMIN_SCORE_WEIGHTS['login_recency']
        elif login_days <= period:
            score += ADMIN_SCORE_WEIGHTS['login_recency'] * max(0, 1 - (login_days - 1) / period)

    caps = {
        'defects_created': max(3, period / 7 * 3),
        'defects_closed': max(3, period / 7 * 3),
        'qc_checked': max(5, period / 7 * 5),
        'handover': max(2, period / 7 * 2),
        'photos': max(3, period / 7 * 3),
        'whatsapp': max(2, period / 7 * 2),
    }
    for key in ['defects_created', 'defects_closed', 'qc_checked', 'handover', 'photos', 'whatsapp']:
        val = metrics.get(key, 0)
        if val > 0:
            score += ADMIN_SCORE_WEIGHTS[key] * min(1.0, val / caps[key])

    return min(100, max(0, round(score)))


def _compute_admin_status(score: int, login_days_ago) -> str:
    if login_days_ago is None:
        return 'never'
    if score >= 50 or login_days_ago < 7:
        return 'active'
    if score >= 20 or login_days_ago <= 14:
        return 'low'
    return 'dormant'


@router.get("/user-activity")
async def user_activity(
    period: int = Query(7),
    role: str = Query(None),
    org_id: str = Query(None),
    sort: str = Query('score'),
    order: str = Query('desc'),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: str = Query(None),
    user: dict = Depends(get_current_user),
):
    if period not in (7, 30, 90):
        raise HTTPException(status_code=422, detail="period must be 7, 30 or 90")
    _require_super_admin(user)
    db = get_db()
    now = datetime.now(timezone.utc)
    period_start = (now - timedelta(days=period)).isoformat()

    orgs = await db.organizations.find({}, {'_id': 0, 'id': 1, 'name': 1}).to_list(5000)
    org_name_map = {o['id']: o.get('name', '') for o in orgs}

    user_filter = {}
    if role:
        user_filter['role'] = role
    if search:
        user_filter['name'] = {'$regex': search, '$options': 'i'}

    all_users = await db.users.find(
        user_filter,
        {'_id': 0, 'id': 1, 'name': 1, 'role': 1, 'last_login_at': 1, 'login_count': 1}
    ).to_list(5000)

    if org_id:
        org_mems = await db.organization_memberships.find(
            {'org_id': org_id},
            {'_id': 0, 'user_id': 1}
        ).to_list(5000)
        org_member_ids = {m['user_id'] for m in org_mems}
        all_users = [u for u in all_users if u['id'] in org_member_ids]

    org_mems_all = await db.organization_memberships.find(
        {'user_id': {'$in': [u['id'] for u in all_users]}},
        {'_id': 0, 'user_id': 1, 'org_id': 1}
    ).to_list(5000) if all_users else []
    user_org_map = {m['user_id']: m['org_id'] for m in org_mems_all}

    sort_key_mongo = {
        'name': ('name', ''),
        'login_count': ('login_count', 0),
        'last_login': ('last_login_at', ''),
        'role': ('role', ''),
    }

    if sort in sort_key_mongo:
        field, default = sort_key_mongo[sort]
        all_users.sort(key=lambda u: u.get(field) or default, reverse=(order == 'desc'))

    if sort == 'score':
        for u in all_users:
            lla = u.get('last_login_at')
            if lla:
                try:
                    ld = (now - datetime.fromisoformat(lla.replace('Z', '+00:00'))).days
                    u['_login_score'] = ADMIN_SCORE_WEIGHTS['login_recency'] * max(0, 1 - max(0, ld - 1) / period) if ld <= period else 0
                    if ld <= 1:
                        u['_login_score'] = ADMIN_SCORE_WEIGHTS['login_recency']
                except Exception:
                    u['_login_score'] = 0
            else:
                u['_login_score'] = 0
        all_users.sort(key=lambda u: u['_login_score'], reverse=(order == 'desc'))

    total_count = len(all_users)
    if not all_users:
        return {
            'users': [],
            'total_count': 0,
            'page': page,
            'limit': limit,
            'orgs': [{'id': o['id'], 'name': o.get('name', '')} for o in orgs],
        }

    start = (page - 1) * limit
    page_users = all_users[start:start + limit]

    page_user_ids = [u['id'] for u in page_users]
    user_map = {u['id']: u for u in page_users}

    defects_created_agg = await db.tasks.aggregate([
        {'$match': {'created_by': {'$in': page_user_ids}, 'created_at': {'$gte': period_start}}},
        {'$group': {'_id': '$created_by', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    defects_created = {r['_id']: r['count'] for r in defects_created_agg}

    defects_closed_agg = await db.task_status_history.aggregate([
        {'$match': {
            'changed_by': {'$in': page_user_ids},
            'new_status': {'$in': list(TERMINAL_TASK_STATUSES)},
            'created_at': {'$gte': period_start},
        }},
        {'$group': {'_id': '$changed_by', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    defects_closed = {r['_id']: r['count'] for r in defects_closed_agg}

    qc_agg = await db.qc_items.aggregate([
        {'$match': {
            'updated_by': {'$in': page_user_ids},
            'status': {'$in': ['pass', 'fail']},
            'updated_at': {'$gte': period_start},
        }},
        {'$group': {'_id': '$updated_by', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    qc_checked = {r['_id']: r['count'] for r in qc_agg}

    handover_agg = await db.handover_protocols.aggregate([
        {'$match': {
            'updated_at': {'$gte': period_start},
            'updated_by': {'$in': page_user_ids},
        }},
        {'$group': {'_id': '$updated_by', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    handover_counts = {r['_id']: r['count'] for r in handover_agg}

    photos_agg = await db.task_updates.aggregate([
        {'$match': {
            'user_id': {'$in': page_user_ids},
            'attachment_url': {'$exists': True, '$ne': None},
            'created_at': {'$gte': period_start},
        }},
        {'$group': {'_id': '$user_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    photos = {r['_id']: r['count'] for r in photos_agg}

    wa_agg = await db.notification_jobs.aggregate([
        {'$match': {
            'channel': 'whatsapp',
            'status': 'sent',
            'created_at': {'$gte': period_start},
            'triggered_by': {'$in': page_user_ids},
        }},
        {'$group': {'_id': '$triggered_by', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    wa_counts = {r['_id']: r['count'] for r in wa_agg}

    results = []
    for uid in page_user_ids:
        u = user_map[uid]
        login_days_ago = None
        last_login = u.get('last_login_at')
        if last_login:
            try:
                login_dt = datetime.fromisoformat(last_login.replace('Z', '+00:00'))
                login_days_ago = max(0, (now - login_dt).days)
            except Exception:
                pass

        metrics = {
            'login_days_ago': login_days_ago,
            'defects_created': defects_created.get(uid, 0),
            'defects_closed': defects_closed.get(uid, 0),
            'qc_checked': qc_checked.get(uid, 0),
            'handover': handover_counts.get(uid, 0),
            'photos': photos.get(uid, 0),
            'whatsapp': wa_counts.get(uid, 0),
        }

        activity_score = _compute_admin_score(metrics, period)
        status = _compute_admin_status(activity_score, login_days_ago)

        oid = user_org_map.get(uid, '')
        results.append({
            'user_id': uid,
            'name': u.get('name', ''),
            'role': u.get('role', ''),
            'org_id': oid,
            'org_name': org_name_map.get(oid, ''),
            'last_login': u.get('last_login_at'),
            'login_count': u.get('login_count', 0),
            'activity_score': activity_score,
            'status': status,
            'metrics': {
                'defects_created': metrics['defects_created'],
                'defects_closed': metrics['defects_closed'],
                'qc_checked': metrics['qc_checked'],
                'handover': metrics['handover'],
                'photos': metrics['photos'],
                'whatsapp': metrics['whatsapp'],
            },
        })

    if sort == 'score':
        results.sort(key=lambda r: r['activity_score'], reverse=(order == 'desc'))

    return {
        'users': results,
        'total_count': total_count,
        'page': page,
        'limit': limit,
        'orgs': [{'id': o['id'], 'name': o.get('name', '')} for o in orgs],
    }


@router.get("/feature-usage")
async def feature_usage(
    period: int = Query(7),
    user: dict = Depends(get_current_user),
):
    if period not in (7, 30, 90):
        raise HTTPException(status_code=422, detail="period must be 7, 30 or 90")
    _require_super_admin(user)
    db = get_db()
    now = datetime.now(timezone.utc)
    period_start = (now - timedelta(days=period)).isoformat()
    prev_period_start = (now - timedelta(days=period * 2)).isoformat()

    active_orgs = await db.organizations.find(
        {'status': {'$ne': 'deleted'}},
        {'_id': 0, 'id': 1}
    ).to_list(5000)
    total_orgs = len(active_orgs)
    if total_orgs == 0:
        total_orgs = 1

    projects = await db.projects.find(
        {'status': {'$nin': ['archived', 'deleted']}},
        {'_id': 0, 'id': 1, 'org_id': 1}
    ).to_list(5000)
    project_org_map = {p['id']: p.get('org_id', '') for p in projects}
    project_ids = [p['id'] for p in projects]

    features = {}

    defects_curr = await db.tasks.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'created_at': {'$gte': period_start}}},
        {'$group': {
            '_id': '$project_id',
            'count': {'$sum': 1},
        }}
    ]).to_list(5000)
    defects_prev = await db.tasks.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'created_at': {'$gte': prev_period_start, '$lt': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    defects_power = await db.tasks.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'created_at': {'$gte': period_start}, 'created_by': {'$exists': True, '$ne': None}}},
        {'$group': {'_id': '$created_by', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5},
    ]).to_list(5000)
    defects_orgs = set()
    defects_total = 0
    for r in defects_curr:
        org = project_org_map.get(r['_id'], '')
        if org:
            defects_orgs.add(org)
        defects_total += r['count']
    defects_prev_total = sum(r['count'] for r in defects_prev)
    features['defects'] = {
        'name': 'ליקויים',
        'orgs_using': len(defects_orgs),
        'adoption_pct': round(len(defects_orgs) / total_orgs * 100),
        'total_actions': defects_total,
        'trend': _trend(defects_total, defects_prev_total),
        'top_power_users': [{'user_id': r['_id'], 'count': r['count'], 'name': ''} for r in defects_power],
    }

    active_run_ids_agg = await db.qc_runs.aggregate([
        {'$match': {'project_id': {'$in': project_ids}}},
        {'$project': {'_id': 0, 'id': 1}}
    ]).to_list(5000)
    active_run_ids = [r['id'] for r in active_run_ids_agg]

    qc_curr = await db.qc_items.aggregate([
        {'$match': {'status': {'$in': ['pass', 'fail']}, 'updated_at': {'$gte': period_start}, 'run_id': {'$in': active_run_ids}}},
        {'$lookup': {
            'from': 'qc_runs', 'localField': 'run_id', 'foreignField': 'id', 'as': 'run',
            'pipeline': [{'$project': {'_id': 0, 'project_id': 1}}]
        }},
        {'$unwind': '$run'},
        {'$group': {'_id': '$run.project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    qc_prev = await db.qc_items.aggregate([
        {'$match': {'status': {'$in': ['pass', 'fail']}, 'updated_at': {'$gte': prev_period_start, '$lt': period_start}, 'run_id': {'$in': active_run_ids}}},
        {'$lookup': {
            'from': 'qc_runs', 'localField': 'run_id', 'foreignField': 'id', 'as': 'run',
            'pipeline': [{'$project': {'_id': 0, 'project_id': 1}}]
        }},
        {'$unwind': '$run'},
        {'$group': {'_id': '$run.project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    qc_power = await db.qc_items.aggregate([
        {'$match': {'status': {'$in': ['pass', 'fail']}, 'updated_at': {'$gte': period_start}, 'updated_by': {'$exists': True, '$ne': None}, 'run_id': {'$in': active_run_ids}}},
        {'$group': {'_id': '$updated_by', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5},
    ]).to_list(5000)
    qc_orgs = set()
    qc_total = 0
    for r in qc_curr:
        org = project_org_map.get(r['_id'], '')
        if org:
            qc_orgs.add(org)
        qc_total += r['count']
    qc_prev_total = sum(r['count'] for r in qc_prev)
    features['qc'] = {
        'name': 'בקרת ביצוע',
        'orgs_using': len(qc_orgs),
        'adoption_pct': round(len(qc_orgs) / total_orgs * 100),
        'total_actions': qc_total,
        'trend': _trend(qc_total, qc_prev_total),
        'top_power_users': [{'user_id': r['_id'], 'count': r['count'], 'name': ''} for r in qc_power],
    }

    ho_curr = await db.handover_protocols.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'updated_at': {'$gte': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    ho_prev = await db.handover_protocols.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'updated_at': {'$gte': prev_period_start, '$lt': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    ho_power = await db.handover_protocols.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'updated_at': {'$gte': period_start}, 'updated_by': {'$exists': True, '$ne': None}}},
        {'$group': {'_id': '$updated_by', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5},
    ]).to_list(5000)
    ho_orgs = set()
    ho_total = 0
    for r in ho_curr:
        org = project_org_map.get(r['_id'], '')
        if org:
            ho_orgs.add(org)
        ho_total += r['count']
    ho_prev_total = sum(r['count'] for r in ho_prev)
    features['handover'] = {
        'name': 'מסירות',
        'orgs_using': len(ho_orgs),
        'adoption_pct': round(len(ho_orgs) / total_orgs * 100),
        'total_actions': ho_total,
        'trend': _trend(ho_total, ho_prev_total),
        'top_power_users': [{'user_id': r['_id'], 'count': r['count'], 'name': ''} for r in ho_power],
    }

    wa_curr = await db.notification_jobs.aggregate([
        {'$match': {'channel': 'whatsapp', 'status': 'sent', 'project_id': {'$in': project_ids}, 'created_at': {'$gte': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    wa_prev = await db.notification_jobs.aggregate([
        {'$match': {'channel': 'whatsapp', 'status': 'sent', 'project_id': {'$in': project_ids}, 'created_at': {'$gte': prev_period_start, '$lt': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    wa_power = await db.notification_jobs.aggregate([
        {'$match': {'channel': 'whatsapp', 'status': 'sent', 'project_id': {'$in': project_ids}, 'created_at': {'$gte': period_start}, 'triggered_by': {'$exists': True, '$ne': None}}},
        {'$group': {'_id': '$triggered_by', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5},
    ]).to_list(5000)
    wa_orgs = set()
    wa_total = 0
    for r in wa_curr:
        org = project_org_map.get(r.get('_id', ''), '')
        if org:
            wa_orgs.add(org)
        wa_total += r['count']
    wa_prev_total = sum(r['count'] for r in wa_prev)
    features['whatsapp'] = {
        'name': 'WhatsApp',
        'orgs_using': len(wa_orgs),
        'adoption_pct': round(len(wa_orgs) / total_orgs * 100),
        'total_actions': wa_total,
        'trend': _trend(wa_total, wa_prev_total),
        'top_power_users': [{'user_id': r['_id'], 'count': r['count'], 'name': ''} for r in wa_power],
    }

    plans_curr = await db.project_plans.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'uploaded_at': {'$gte': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    plans_prev = await db.project_plans.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'uploaded_at': {'$gte': prev_period_start, '$lt': period_start}}},
        {'$group': {'_id': '$project_id', 'count': {'$sum': 1}}}
    ]).to_list(5000)
    plans_power = await db.project_plans.aggregate([
        {'$match': {'project_id': {'$in': project_ids}, 'uploaded_at': {'$gte': period_start}, 'uploaded_by': {'$exists': True, '$ne': None}}},
        {'$group': {'_id': '$uploaded_by', 'count': {'$sum': 1}}},
        {'$sort': {'count': -1}},
        {'$limit': 5},
    ]).to_list(5000)
    plans_orgs = set()
    plans_total = 0
    for r in plans_curr:
        org = project_org_map.get(r['_id'], '')
        if org:
            plans_orgs.add(org)
        plans_total += r['count']
    plans_prev_total = sum(r['count'] for r in plans_prev)
    features['plans'] = {
        'name': 'תוכניות',
        'orgs_using': len(plans_orgs),
        'adoption_pct': round(len(plans_orgs) / total_orgs * 100),
        'total_actions': plans_total,
        'trend': _trend(plans_total, plans_prev_total),
        'top_power_users': [{'user_id': r['_id'], 'count': r['count'], 'name': ''} for r in plans_power],
    }

    user_ids_all = set()
    for f in features.values():
        for pu in f['top_power_users']:
            if pu['user_id']:
                user_ids_all.add(pu['user_id'])
    if user_ids_all:
        users_docs = await db.users.find(
            {'id': {'$in': list(user_ids_all)}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(5000)
        name_map = {u['id']: u.get('name', '') for u in users_docs}
        for f in features.values():
            for pu in f['top_power_users']:
                pu['name'] = name_map.get(pu['user_id'], '')

    return {'features': features, 'total_orgs': total_orgs}


def _trend(current: int, previous: int) -> str:
    if current == 0:
        return 'inactive'
    if previous == 0 and current > 0:
        return 'new'
    if current > previous * 1.2:
        return 'growing'
    if current < previous * 0.8:
        return 'declining'
    return 'stable'
