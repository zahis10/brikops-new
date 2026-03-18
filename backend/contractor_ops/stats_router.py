from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from contractor_ops.router import (
    get_db, get_current_user,
    _check_project_access, _check_project_read_access,
    _get_project_membership, _get_project_role,
    _enrich_memberships,
    PHONE_VISIBLE_ROLES, logger,
)
from contractor_ops.tasks_router import _build_bucket_maps
from contractor_ops.bucket_utils import compute_task_bucket, BUCKET_LABELS, CATEGORY_TO_BUCKET

router = APIRouter(prefix="/api")


@router.get("/projects/{project_id}/memberships")
async def list_project_memberships(project_id: str, user: dict = Depends(get_current_user)):
    await _check_project_read_access(user, project_id)
    requester_membership = await _get_project_membership(user, project_id)
    requester_role = requester_membership.get('role', 'none')
    can_see_phone = requester_role in PHONE_VISIBLE_ROLES
    return await _enrich_memberships(project_id, can_see_phone)


@router.get("/my-memberships")
async def get_my_memberships(user: dict = Depends(get_current_user)):
    db = get_db()
    memberships = await db.project_memberships.find({'user_id': user['id']}, {'_id': 0}).to_list(1000)
    return memberships


# ── Project stats (KPI) ──
@router.get("/projects/{project_id}/stats")
async def get_project_stats(project_id: str, user: dict = Depends(get_current_user)):
    from datetime import datetime, timezone
    db = get_db()
    await _check_project_access(user, project_id)
    now = datetime.now(timezone.utc)
    buildings_count = await db.buildings.count_documents({'project_id': project_id, 'archived': {'$ne': True}})
    floors_count = await db.floors.count_documents({'project_id': project_id, 'archived': {'$ne': True}})
    units_count = await db.units.count_documents({'project_id': project_id, 'archived': {'$ne': True}})
    team_count = await db.project_memberships.count_documents({'project_id': project_id})
    invites_count = await db.invites.count_documents({'project_id': project_id, 'status': 'pending'})
    invites_count += await db.team_invites.count_documents({'project_id': project_id, 'status': 'pending'})
    companies_count = await db.project_companies.count_documents({'project_id': project_id})
    open_defects = await db.tasks.count_documents({'project_id': project_id, 'status': {'$nin': ['closed']}})
    critical_defects = await db.tasks.count_documents({'project_id': project_id, 'priority': 'critical', 'status': {'$nin': ['closed']}})
    now_str = now.strftime('%Y-%m-%d')
    overdue_defects = await db.tasks.count_documents({'project_id': project_id, 'due_date': {'$lt': now_str, '$ne': None}, 'status': {'$nin': ['closed']}})
    building_defects_agg = await db.tasks.aggregate([
        {'$match': {'project_id': project_id, 'building_id': {'$ne': None}}},
        {'$group': {
            '_id': '$building_id',
            'open': {'$sum': {'$cond': [{'$ne': ['$status', 'closed']}, 1, 0]}},
            'critical': {'$sum': {'$cond': [{'$and': [{'$eq': ['$priority', 'critical']}, {'$ne': ['$status', 'closed']}]}, 1, 0]}},
            'closed': {'$sum': {'$cond': [{'$eq': ['$status', 'closed']}, 1, 0]}},
            'total': {'$sum': 1},
        }}
    ]).to_list(500)
    per_building = {r['_id']: {'open': r['open'], 'critical': r['critical'], 'closed': r['closed'], 'total': r['total']} for r in building_defects_agg}
    return {
        'buildings': buildings_count,
        'floors': floors_count,
        'units': units_count,
        'team_members': team_count,
        'pending_invites': invites_count,
        'companies': companies_count,
        'open_defects': open_defects,
        'critical_defects': critical_defects,
        'overdue_defects': overdue_defects,
        'per_building_defects': per_building,
    }


@router.get("/projects/{project_id}/dashboard")
async def get_project_dashboard(project_id: str, user: dict = Depends(get_current_user)):
    import time as _t
    _t0 = _t.perf_counter()
    db = get_db()
    await _check_project_read_access(user, project_id)
    role = await _get_project_role(user, project_id)
    _t_auth = _t.perf_counter()
    is_pm_or_owner = role in ('project_manager', 'owner')
    now = datetime.utcnow()
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    base_filter = {'project_id': project_id}
    active_statuses = ['open', 'assigned', 'in_progress', 'pending_contractor_proof',
                       'returned_to_contractor', 'reopened']
    in_progress_statuses = ['in_progress', 'pending_contractor_proof',
                            'pending_manager_approval', 'returned_to_contractor']
    approval_statuses = ['pending_manager_approval', 'waiting_verify']

    tasks = await db.tasks.find(
        base_filter,
        {'_id': 0, 'id': 1, 'title': 1, 'status': 1, 'assignee_id': 1, 'company_id': 1,
         'building_id': 1, 'floor_id': 1, 'unit_id': 1,
         'created_at': 1, 'updated_at': 1, 'due_date': 1, 'category': 1, 'priority': 1}
    ).to_list(50000)
    _t_tasks = _t.perf_counter()

    open_count = 0
    in_progress_count = 0
    closed_count = 0
    closed_last7 = 0
    open_last7 = 0
    pending_approval_count = 0
    overdue_count = 0
    now_iso = now.isoformat()
    pending_approval_tasks = []
    stuck_map = {}
    building_load = {}
    contractor_map = {}
    assignee_company_map = {}

    by_status = {}
    by_category = {}

    for t in tasks:
        s = t.get('status', '')
        tid = t.get('id', '')
        by_status[s] = by_status.get(s, 0) + 1
        cat = t.get('category', 'general')
        by_category[cat] = by_category.get(cat, 0) + 1
        if s in active_statuses:
            open_count += 1
        if s in in_progress_statuses:
            in_progress_count += 1
        if s == 'closed':
            closed_count += 1
            if t.get('updated_at', '') >= seven_days_ago:
                closed_last7 += 1
        if t.get('created_at', '') >= seven_days_ago and s in active_statuses:
            open_last7 += 1
        if s in approval_statuses:
            pending_approval_count += 1
            pending_approval_tasks.append({
                'id': tid, 'title': t.get('title', ''),
                'status': s, 'updated_at': t.get('updated_at', ''),
                'building_id': t.get('building_id'), 'unit_id': t.get('unit_id'),
            })
        if t.get('due_date') and t['due_date'] < now_iso and s not in ('closed',):
            overdue_count += 1

        cid = t.get('company_id') or ''
        aid = t.get('assignee_id')
        group_key = cid or aid
        if group_key and s in active_statuses:
            updated = t.get('updated_at', '')
            if group_key not in stuck_map:
                stuck_map[group_key] = []
            stuck_map[group_key].append({
                'id': tid, 'title': t.get('title', ''),
                'status': s, 'updated_at': updated,
            })
        if group_key and cid:
            assignee_company_map[group_key] = cid

        bid = t.get('building_id')
        if bid and s in active_statuses:
            building_load[bid] = building_load.get(bid, 0) + 1

        if group_key:
            if group_key not in contractor_map:
                contractor_map[group_key] = {'open': 0, 'closed': 0, 'rework': 0, 'response_times': []}
            if s in active_statuses:
                contractor_map[group_key]['open'] += 1
            if s == 'closed':
                contractor_map[group_key]['closed'] += 1
            if s == 'returned_to_contractor':
                contractor_map[group_key]['rework'] += 1

    _t_loop = _t.perf_counter()

    team_count = await db.project_memberships.count_documents({'project_id': project_id})

    sla_response_7d = 0
    sla_close_7d = 0
    sla_response_30d = 0
    sla_close_30d = 0
    try:
        response_pipeline_7d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'in_progress',
                        'created_at': {'$gte': seven_days_ago}}},
            {'$group': {'_id': '$task_id', 'first_response': {'$min': '$created_at'}}}
        ]
        response_results_7d = await db.task_status_history.aggregate(response_pipeline_7d).to_list(10000)

        task_created_map = {t['id']: t.get('created_at', '') for t in tasks}
        response_deltas_7d = []
        for r in response_results_7d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('first_response'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['first_response'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        response_deltas_7d.append(delta_h)
                except Exception:
                    pass
        if response_deltas_7d:
            sla_response_7d = round(sum(response_deltas_7d) / len(response_deltas_7d), 1)

        close_pipeline_7d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'closed',
                        'created_at': {'$gte': seven_days_ago}}},
            {'$group': {'_id': '$task_id', 'closed_at': {'$min': '$created_at'}}}
        ]
        close_results_7d = await db.task_status_history.aggregate(close_pipeline_7d).to_list(10000)
        close_deltas_7d = []
        for r in close_results_7d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('closed_at'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['closed_at'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        close_deltas_7d.append(delta_h)
                except Exception:
                    pass
        if close_deltas_7d:
            sla_close_7d = round(sum(close_deltas_7d) / len(close_deltas_7d), 1)

        response_pipeline_30d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'in_progress',
                        'created_at': {'$gte': thirty_days_ago}}},
            {'$group': {'_id': '$task_id', 'first_response': {'$min': '$created_at'}}}
        ]
        response_results_30d = await db.task_status_history.aggregate(response_pipeline_30d).to_list(10000)
        response_deltas_30d = []
        for r in response_results_30d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('first_response'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['first_response'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        response_deltas_30d.append(delta_h)
                except Exception:
                    pass
        if response_deltas_30d:
            sla_response_30d = round(sum(response_deltas_30d) / len(response_deltas_30d), 1)

        close_pipeline_30d = [
            {'$match': {'task_id': {'$in': [t['id'] for t in tasks]},
                        'new_status': 'closed',
                        'created_at': {'$gte': thirty_days_ago}}},
            {'$group': {'_id': '$task_id', 'closed_at': {'$min': '$created_at'}}}
        ]
        close_results_30d = await db.task_status_history.aggregate(close_pipeline_30d).to_list(10000)
        close_deltas_30d = []
        for r in close_results_30d:
            created = task_created_map.get(r['_id'], '')
            if created and r.get('closed_at'):
                try:
                    c = datetime.fromisoformat(created.replace('Z', '+00:00').replace('+00:00', ''))
                    f = datetime.fromisoformat(r['closed_at'].replace('Z', '+00:00').replace('+00:00', ''))
                    delta_h = (f - c).total_seconds() / 3600
                    if delta_h >= 0:
                        close_deltas_30d.append(delta_h)
                except Exception:
                    pass
        if close_deltas_30d:
            sla_close_30d = round(sum(close_deltas_30d) / len(close_deltas_30d), 1)
    except Exception as e:
        logger.warning(f"[DASHBOARD] SLA calculation error: {e}")
    _t_sla = _t.perf_counter()

    stuck_threshold = (now - timedelta(hours=48)).isoformat()
    stuck_contractors = []
    contractor_ids = list(set(list(stuck_map.keys()) + list(contractor_map.keys())))
    name_docs = {}
    if contractor_ids:
        users_list = await db.users.find(
            {'id': {'$in': contractor_ids}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(1000)
        name_docs = {u['id']: u.get('name', '') for u in users_list}
        missing_ids = [cid for cid in contractor_ids if cid not in name_docs]
        if missing_ids:
            companies_list = await db.companies.find(
                {'id': {'$in': missing_ids}},
                {'_id': 0, 'id': 1, 'name': 1}
            ).to_list(500)
            for c in companies_list:
                name_docs[c['id']] = c.get('name', '')

    for gk, task_list in stuck_map.items():
        stuck_tasks = [t for t in task_list if t.get('updated_at', '') < stuck_threshold]
        if stuck_tasks:
            stuck_tasks.sort(key=lambda x: x.get('updated_at', ''))
            stuck_contractors.append({
                'contractor_id': gk,
                'company_id': assignee_company_map.get(gk, gk),
                'contractor_name': name_docs.get(gk, ''),
                'stuck_count': len(stuck_tasks),
                'tasks': stuck_tasks[:5],
            })
    stuck_contractors.sort(key=lambda x: x['stuck_count'], reverse=True)

    building_ids = list(building_load.keys())
    building_names = {}
    if building_ids:
        bldgs = await db.buildings.find(
            {'id': {'$in': building_ids}},
            {'_id': 0, 'id': 1, 'name': 1}
        ).to_list(500)
        building_names = {b['id']: b.get('name', '') for b in bldgs}

    load_by_building = []
    for bid, count in sorted(building_load.items(), key=lambda x: x[1], reverse=True)[:10]:
        load_by_building.append({
            'building_id': bid,
            'building_name': building_names.get(bid, bid),
            'open_count': count,
        })

    contractor_quality = []
    for gk, stats in contractor_map.items():
        total = stats['open'] + stats['closed']
        if total == 0:
            continue
        contractor_quality.append({
            'contractor_id': gk,
            'company_id': assignee_company_map.get(gk, gk),
            'contractor_name': name_docs.get(gk, ''),
            'open': stats['open'],
            'closed': stats['closed'],
            'rework': stats['rework'],
        })
    contractor_quality.sort(key=lambda x: x['open'], reverse=True)

    result = {
        'kpis': {
            'open_total': int(open_count or 0),
            'open_last7': int(open_last7 or 0),
            'in_progress': int(in_progress_count or 0),
            'closed_total': int(closed_count or 0),
            'closed_last7': int(closed_last7 or 0),
            'pending_approval': int(pending_approval_count or 0),
            'overdue': int(overdue_count or 0),
            'team_count': int(team_count or 0),
            'sla_response_7d': float(sla_response_7d or 0),
            'sla_close_7d': float(sla_close_7d or 0),
            'sla_response_30d': float(sla_response_30d or 0),
            'sla_close_30d': float(sla_close_30d or 0),
        },
        'pending_approvals': pending_approval_tasks[:20] if is_pm_or_owner else [],
        'stuck_contractors': stuck_contractors[:10] if stuck_contractors else [],
        'load_by_building': load_by_building if load_by_building else [],
        'contractor_quality': contractor_quality[:20] if contractor_quality else [],
        'role': role or 'viewer',
        'total_tasks': int(len(tasks) or 0),
        'by_status': by_status or {},
        'by_category': by_category or {},
    }
    _t_end = _t.perf_counter()
    logger.info(
        f"[DASHBOARD-PERF] project={project_id[:8]} total={round((_t_end-_t0)*1000)}ms "
        f"auth={round((_t_auth-_t0)*1000)}ms tasks_query={round((_t_tasks-_t_auth)*1000)}ms "
        f"loop={round((_t_loop-_t_tasks)*1000)}ms sla={round((_t_sla-_t_loop)*1000)}ms "
        f"enrichment={round((_t_end-_t_sla)*1000)}ms task_count={len(tasks)}"
    )
    return result


@router.get("/projects/{project_id}/tasks/contractor-summary")
async def get_contractor_summary(
    project_id: str,
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_access(user, project_id)

    task_query = {'project_id': project_id}
    if status:
        task_query['status'] = status

    tasks = await db.tasks.find(task_query, {'assignee_id': 1, '_id': 0}).to_list(10000)

    unassigned_count = 0
    by_assignee = {}
    for t in tasks:
        aid = t.get('assignee_id')
        if not aid:
            unassigned_count += 1
        else:
            by_assignee[aid] = by_assignee.get(aid, 0) + 1

    contractors = []
    if by_assignee:
        user_docs = await db.users.find(
            {'id': {'$in': list(by_assignee.keys())}},
            {'_id': 0, 'id': 1, 'name': 1, 'specialties': 1, 'company_id': 1}
        ).to_list(1000)
        user_map = {u['id']: {'name': u.get('name', ''), 'specialty': (u.get('specialties') or [None])[0]} for u in user_docs}
        for uid, count in by_assignee.items():
            contractors.append({
                'id': uid,
                'name': user_map.get(uid, {}).get('name', uid),
                'specialty': user_map.get(uid, {}).get('specialty'),
                'count': count,
            })
        contractors.sort(key=lambda c: c['count'], reverse=True)

    return {
        'total': len(tasks),
        'unassigned': unassigned_count,
        'contractors': contractors,
    }


@router.get("/projects/{project_id}/task-buckets")
async def get_task_buckets(
    project_id: str,
    status: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    db = get_db()
    await _check_project_read_access(user, project_id)

    is_contractor = user['role'] == 'contractor'
    my_trade_bucket = None
    if not is_contractor:
        proj_role = await _get_project_role(user, project_id)
        if proj_role == 'contractor':
            is_contractor = True
    if is_contractor:
        my_membership = await db.project_memberships.find_one(
            {'user_id': user['id'], 'project_id': project_id}, {'_id': 0}
        )
        if my_membership and my_membership.get('contractor_trade_key'):
            my_trade_bucket = CATEGORY_TO_BUCKET.get(
                my_membership['contractor_trade_key'], my_membership['contractor_trade_key']
            )

    base_query = {'project_id': project_id}
    if is_contractor:
        base_query['assignee_id'] = user['id']

    status_count_query = dict(base_query)
    status_pipeline = [
        {'$match': status_count_query},
        {'$group': {'_id': '$status', 'count': {'$sum': 1}}},
    ]
    status_agg = await db.tasks.aggregate(status_pipeline).to_list(100)
    status_counts = {doc['_id']: doc['count'] for doc in status_agg if doc['_id']}

    task_query = dict(base_query)
    if status:
        task_query['status'] = status

    bucket_projection = {'_id': 0, 'id': 1, 'assignee_id': 1, 'company_id': 1, 'category': 1}
    tasks = await db.tasks.find(task_query, bucket_projection).to_list(10000)
    contractor_map, company_map, membership_trade_map = await _build_bucket_maps(db, project_id)

    bucket_counts = {}
    bucket_meta = {}
    total = len(tasks)
    for t in tasks:
        info = compute_task_bucket(t, contractor_map, company_map, membership_trade_map)
        bk = info['bucket_key']
        bucket_counts[bk] = bucket_counts.get(bk, 0) + 1
        if bk not in bucket_meta:
            bucket_meta[bk] = {'label_he': info['label_he'], 'source': info['source']}

    if is_contractor and my_trade_bucket:
        filtered_counts = {}
        filtered_meta = {}
        if my_trade_bucket in bucket_counts:
            filtered_counts[my_trade_bucket] = bucket_counts[my_trade_bucket]
            filtered_meta[my_trade_bucket] = bucket_meta[my_trade_bucket]
        else:
            filtered_counts[my_trade_bucket] = 0
            filtered_meta[my_trade_bucket] = {
                'label_he': BUCKET_LABELS.get(my_trade_bucket, my_trade_bucket),
                'source': 'membership',
            }
        bucket_counts = filtered_counts
        bucket_meta = filtered_meta
        total = sum(filtered_counts.values())
    else:
        contractor_memberships = await db.project_memberships.find(
            {'project_id': project_id, 'role': 'contractor', 'contractor_trade_key': {'$exists': True, '$ne': None}},
            {'_id': 0, 'contractor_trade_key': 1}
        ).to_list(10000)
        for m in contractor_memberships:
            trade = m['contractor_trade_key']
            bk = CATEGORY_TO_BUCKET.get(trade, trade)
            if bk not in bucket_counts:
                bucket_counts[bk] = 0
                bucket_meta[bk] = {'label_he': BUCKET_LABELS.get(bk, bk), 'source': 'membership'}

    buckets = []
    for bk, count in bucket_counts.items():
        buckets.append({
            'bucket_key': bk,
            'label_he': bucket_meta[bk]['label_he'],
            'count': count,
            'source': bucket_meta[bk]['source'],
        })
    buckets.sort(key=lambda b: b['count'], reverse=True)

    return {
        'total': total,
        'buckets': buckets,
        'status_counts': status_counts,
    }
