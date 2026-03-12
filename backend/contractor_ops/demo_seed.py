import uuid
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

DEMO_REVIEWER_ACCOUNTS = [
    {
        'email': 'demo-pm@brikops.com',
        'name': 'מנהל פרויקט (דמו)',
        'role': 'project_manager',
        'phone_e164': '+972540000901',
    },
    {
        'email': 'demo-team@brikops.com',
        'name': 'צוות ניהולי (דמו)',
        'role': 'management_team',
        'phone_e164': '+972540000902',
    },
    {
        'email': 'demo-contractor@brikops.com',
        'name': 'קבלן (דמו)',
        'role': 'contractor',
        'phone_e164': '+972540000903',
    },
    {
        'email': 'demo-viewer@brikops.com',
        'name': 'צופה (דמו)',
        'role': 'viewer',
        'phone_e164': '+972540000904',
    },
]

DEMO_ORG_NAME = 'חברת הדגמה'
DEMO_COMPED_UNTIL = '2030-12-31T23:59:59+00:00'

DEMO_PROJECT_NAME = 'פרויקט מגדלי הדמו'

DEMO_COMPANIES = [
    {
        'name': 'חשמל כהן',
        'trade': 'electrical',
        'contact_name': 'יוסי כהן',
        'contact_phone': '050-1111111',
        'phone_e164': '+972501111111',
    },
    {
        'name': 'אינסטלציה לוי',
        'trade': 'plumbing',
        'contact_name': 'דוד לוי',
        'contact_phone': '050-2222222',
        'phone_e164': '+972502222222',
    },
    {
        'name': 'ריצוף אברהם',
        'trade': 'flooring',
        'contact_name': 'משה אברהם',
        'contact_phone': '050-3333333',
        'phone_e164': '+972503333333',
    },
]

DEMO_DEFECTS = [
    {'title': 'תיקון שקע חשמל בסלון', 'desc': 'שקע חשמל לא תקין — אין מתח', 'cat': 'electrical', 'pri': 'high', 'status': 'open'},
    {'title': 'נזילה מצינור מים חמים', 'desc': 'נזילה קלה מתחת לכיור במטבח', 'cat': 'plumbing', 'pri': 'critical', 'status': 'open'},
    {'title': 'אריח רצפה שבור במסדרון', 'desc': 'אריח סדוק בכניסה לדירה', 'cat': 'flooring', 'pri': 'medium', 'status': 'open'},
    {'title': 'צביעת קיר חדר שינה', 'desc': 'כתמי רטיבות על הקיר — יש לצבוע מחדש', 'cat': 'painting', 'pri': 'low', 'status': 'open'},
    {'title': 'התקנת מפסק תאורה', 'desc': 'מפסק חסר בחדר ילדים', 'cat': 'electrical', 'pri': 'medium', 'status': 'open'},
    {'title': 'תיקון ברז מטבח', 'desc': 'הברז מטפטף ללא הפסקה', 'cat': 'plumbing', 'pri': 'high', 'status': 'assigned'},
    {'title': 'החלפת אריחים בחדר רחצה', 'desc': 'שלושה אריחים סדוקים בקיר המקלחת', 'cat': 'flooring', 'pri': 'high', 'status': 'assigned'},
    {'title': 'בדיקת הארקת חשמל', 'desc': 'בדיקת תקינות הארקה בלוח הדירה', 'cat': 'electrical', 'pri': 'critical', 'status': 'assigned'},
    {'title': 'תיקון צנרת ביוב', 'desc': 'חסימה חלקית בצנרת הראשית', 'cat': 'plumbing', 'pri': 'high', 'status': 'in_progress'},
    {'title': 'ריצוף מרפסת שמש', 'desc': 'השלמת ריצוף מרפסת — 12 מ"ר', 'cat': 'flooring', 'pri': 'medium', 'status': 'in_progress'},
    {'title': 'התקנת נקודות חשמל נוספות', 'desc': 'הוספת 3 שקעים בסלון לפי תכנית', 'cat': 'electrical', 'pri': 'medium', 'status': 'in_progress'},
    {'title': 'תיקון נזילה בתקרה', 'desc': 'נזילה מהקומה העליונה — דורש בדיקת איטום', 'cat': 'plumbing', 'pri': 'critical', 'status': 'pending_contractor_proof'},
    {'title': 'החלפת ריצוף כניסה', 'desc': 'ריצוף ישן לא תואם — הוחלף בהצלחה', 'cat': 'flooring', 'pri': 'medium', 'status': 'pending_manager_approval'},
    {'title': 'תיקון תאורת חדר מדרגות', 'desc': 'החלפת גוף תאורה וכבלים', 'cat': 'electrical', 'pri': 'high', 'status': 'pending_manager_approval'},
    {'title': 'תיקון שיפוע ניקוז מקלחת', 'desc': 'תוקן שיפוע ניקוז ונבדק — תקין', 'cat': 'plumbing', 'pri': 'high', 'status': 'closed'},
    {'title': 'השלמת ריצוף חדר שינה ראשי', 'desc': 'ריצוף הושלם ונבדק — ללא ליקויים', 'cat': 'flooring', 'pri': 'medium', 'status': 'closed'},
]

DEMO_BUILDINGS = [
    {'name': 'בניין A', 'code': 'DEMO-A'},
    {'name': 'בניין B', 'code': 'DEMO-B'},
]

QC_STAGE_IDS = [
    'stage_ceiling_prep', 'stage_blocks_row1', 'stage_plumbing',
    'stage_electrical', 'stage_plaster', 'stage_waterproof', 'stage_acoustic',
]

QC_STAGE_ITEMS = {
    'stage_ceiling_prep': ['cp_1', 'cp_2', 'cp_3', 'cp_4', 'cp_5', 'cp_6', 'cp_7'],
    'stage_blocks_row1': ['br_pw1', 'br_pw2', 'br_1', 'br_2', 'br_3', 'br_4', 'br_5', 'br_6'],
    'stage_plumbing': ['pl_pw1', 'pl_pw2', 'pl_1', 'pl_2', 'pl_3', 'pl_4', 'pl_5', 'pl_6', 'pl_7', 'pl_8'],
    'stage_electrical': ['el_pw1', 'el_pw2', 'el_1', 'el_2', 'el_3', 'el_4', 'el_5', 'el_6'],
    'stage_plaster': ['pt_pw1', 'pt_pw2', 'pt_1', 'pt_2', 'pt_3', 'pt_4', 'pt_5', 'pt_6', 'pt_7'],
    'stage_waterproof': ['wp_1', 'wp_2', 'wp_3', 'wp_4', 'wp_5', 'wp_6', 'wp_7', 'wp_8'],
    'stage_acoustic': ['ac_1', 'ac_2', 'ac_3', 'ac_4', 'ac_5'],
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _uid():
    return str(uuid.uuid4())


async def ensure_demo_reviewer_accounts(db, password: str, reset_passwords: bool = False):
    import bcrypt as _bcrypt

    created = 0
    updated = 0
    user_map = {}

    for acct in DEMO_REVIEWER_ACCOUNTS:
        existing = await db.users.find_one(
            {'email': acct['email']},
            {'_id': 0, 'id': 1, 'password_hash': 1, 'is_demo': 1},
        )

        if existing:
            user_map[acct['email']] = existing['id']
            updates = {}
            if not existing.get('is_demo'):
                updates['is_demo'] = True
            if reset_passwords:
                pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
                updates['password_hash'] = pw_hash
            if updates:
                updates['updated_at'] = _now()
                await db.users.update_one({'id': existing['id']}, {'$set': updates})
                updated += 1
        else:
            user_id = str(uuid.uuid4())
            pw_hash = _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()
            await db.users.insert_one({
                'id': user_id,
                'email': acct['email'],
                'password_hash': pw_hash,
                'name': acct['name'],
                'role': acct['role'],
                'phone_e164': acct['phone_e164'],
                'user_status': 'active',
                'is_demo': True,
                'company_id': None,
                'preferred_language': 'he',
                'created_at': _now(),
            })
            user_map[acct['email']] = user_id
            created += 1

    if created or updated:
        logger.info(f"[DEMO] Ensured {len(DEMO_REVIEWER_ACCOUNTS)} demo reviewer accounts (created={created} updated={updated})")
    else:
        logger.info(f"[DEMO] All {len(DEMO_REVIEWER_ACCOUNTS)} demo reviewer accounts already exist")

    return user_map


async def ensure_demo_org(db, user_map: dict):
    ts = _now()
    pm_email = 'demo-pm@brikops.com'
    pm_user_id = user_map.get(pm_email)
    if not pm_user_id:
        logger.warning("[DEMO] demo-pm user not found in user_map — skipping org creation")
        return None

    org = await db.organizations.find_one({'is_demo': True}, {'_id': 0})

    if not org:
        org_id = str(uuid.uuid4())
        org = {
            'id': org_id,
            'name': DEMO_ORG_NAME,
            'owner_user_id': pm_user_id,
            'owner_set_at': ts,
            'is_demo': True,
            'created_at': ts,
        }
        await db.organizations.insert_one(org)
        logger.info(f"[DEMO] Created demo org '{DEMO_ORG_NAME}' id={org_id}")
    else:
        org_id = org['id']
        updates = {}
        if not org.get('is_demo'):
            updates['is_demo'] = True
        if org.get('owner_user_id') != pm_user_id:
            updates['owner_user_id'] = pm_user_id
            updates['owner_set_at'] = ts
        if updates:
            await db.organizations.update_one({'id': org_id}, {'$set': updates})

    members_ensured = 0
    role_map = {
        'demo-pm@brikops.com': 'owner',
        'demo-team@brikops.com': 'org_admin',
        'demo-contractor@brikops.com': 'member',
        'demo-viewer@brikops.com': 'member',
    }
    for email, user_id in user_map.items():
        existing_membership = await db.organization_memberships.find_one(
            {'org_id': org_id, 'user_id': user_id},
            {'_id': 0, 'id': 1},
        )
        if not existing_membership:
            await db.organization_memberships.insert_one({
                'id': str(uuid.uuid4()),
                'org_id': org_id,
                'user_id': user_id,
                'role': role_map.get(email, 'member'),
                'is_demo': True,
                'created_at': ts,
            })
            members_ensured += 1

    sub = await db.subscriptions.find_one({'org_id': org_id}, {'_id': 0})
    if not sub:
        await db.subscriptions.insert_one({
            'id': str(uuid.uuid4()),
            'org_id': org_id,
            'status': 'active',
            'trial_end_at': None,
            'paid_until': DEMO_COMPED_UNTIL,
            'grace_until': None,
            'manual_override': {
                'is_comped': True,
                'comped_until': DEMO_COMPED_UNTIL,
                'is_suspended': False,
                'note': 'Demo/reviewer org — auto-comped',
                'by_user_id': 'system',
                'at': ts,
            },
            'is_demo': True,
            'created_at': ts,
            'updated_at': ts,
        })
        logger.info(f"[DEMO] Created demo subscription for org {org_id} (comped until 2030-12-31)")
    else:
        mo = sub.get('manual_override') or {}
        if not mo.get('is_comped') or mo.get('comped_until') != DEMO_COMPED_UNTIL:
            await db.subscriptions.update_one(
                {'org_id': org_id},
                {'$set': {
                    'status': 'active',
                    'paid_until': DEMO_COMPED_UNTIL,
                    'manual_override.is_comped': True,
                    'manual_override.comped_until': DEMO_COMPED_UNTIL,
                    'manual_override.is_suspended': False,
                    'manual_override.note': 'Demo/reviewer org — auto-comped',
                    'manual_override.by_user_id': 'system',
                    'manual_override.at': ts,
                    'updated_at': ts,
                }},
            )
            logger.info(f"[DEMO] Updated demo subscription for org {org_id} — ensured is_comped until 2030-12-31")

    logger.info(f"[DEMO] Ensured demo org + {members_ensured} new memberships + subscription")
    return org_id


async def _find_or_create(db, collection_name, query, doc):
    coll = db[collection_name]
    existing = await coll.find_one(query, {'_id': 0, 'id': 1})
    if existing:
        return existing['id'], False
    await coll.insert_one(doc)
    return doc['id'], True


async def ensure_demo_data(db, user_map: dict, org_id: str):
    if not org_id:
        logger.warning("[DEMO-DATA] No demo org_id — skipping demo data seeding")
        return

    pm_id = user_map.get('demo-pm@brikops.com')
    team_id = user_map.get('demo-team@brikops.com')
    contractor_id = user_map.get('demo-contractor@brikops.com')
    viewer_id = user_map.get('demo-viewer@brikops.com')

    if not pm_id:
        logger.warning("[DEMO-DATA] demo-pm user not found — skipping demo data seeding")
        return

    ts = _now()
    counts = {'projects': 0, 'buildings': 0, 'floors': 0, 'units': 0,
              'companies': 0, 'memberships': 0, 'defects': 0,
              'qc_runs': 0, 'qc_items': 0, 'billing': 0}

    project_id, created = await _find_or_create(
        db, 'projects',
        {'is_demo': True, 'org_id': org_id},
        {
            'id': _uid(),
            'name': DEMO_PROJECT_NAME,
            'code': 'DEMO-001',
            'description': 'פרויקט הדגמה — 2 בניינים, 30 דירות',
            'status': 'active',
            'client_name': DEMO_ORG_NAME,
            'org_id': org_id,
            'start_date': '2026-01-01',
            'end_date': '2027-06-30',
            'created_by': pm_id,
            'setup_complete': True,
            'onboarding_complete': True,
            'is_demo': True,
            'created_at': ts,
            'updated_at': ts,
        },
    )
    if created:
        counts['projects'] = 1

    company_ids = {}
    for comp_def in DEMO_COMPANIES:
        comp_id, c = await _find_or_create(
            db, 'companies',
            {'is_demo': True, 'trade': comp_def['trade']},
            {
                'id': _uid(),
                'name': comp_def['name'],
                'trade': comp_def['trade'],
                'contact_name': comp_def['contact_name'],
                'contact_phone': comp_def['contact_phone'],
                'phone_e164': comp_def['phone_e164'],
                'is_demo': True,
                'created_at': ts,
            },
        )
        company_ids[comp_def['trade']] = comp_id
        if c:
            counts['companies'] += 1

    membership_defs = [
        {'user_id': pm_id, 'role': 'project_manager', 'extra': {}},
        {'user_id': team_id, 'role': 'management_team', 'extra': {'sub_role': 'site_manager'}} if team_id else None,
        {'user_id': contractor_id, 'role': 'contractor', 'extra': {
            'contractor_trade_key': 'electrical',
            'company_id': company_ids.get('electrical'),
        }} if contractor_id else None,
        {'user_id': viewer_id, 'role': 'viewer', 'extra': {}} if viewer_id else None,
    ]
    for mdef in membership_defs:
        if not mdef:
            continue
        _, c = await _find_or_create(
            db, 'project_memberships',
            {'project_id': project_id, 'user_id': mdef['user_id']},
            {
                'id': _uid(),
                'project_id': project_id,
                'user_id': mdef['user_id'],
                'role': mdef['role'],
                'status': 'active',
                'is_demo': True,
                'created_at': ts,
                **mdef['extra'],
            },
        )
        if c:
            counts['memberships'] += 1

    for trade, comp_id in company_ids.items():
        contractor_user = await db.users.find_one(
            {'is_demo': True, 'role': 'contractor'},
            {'_id': 0, 'id': 1, 'company_id': 1},
        )
        if contractor_user and not contractor_user.get('company_id'):
            await db.users.update_one(
                {'id': contractor_user['id']},
                {'$set': {'company_id': company_ids.get('electrical')}},
            )

    building_ids = []
    for bdef in DEMO_BUILDINGS:
        bid, c = await _find_or_create(
            db, 'buildings',
            {'project_id': project_id, 'is_demo': True, 'code': bdef['code']},
            {
                'id': _uid(),
                'project_id': project_id,
                'name': bdef['name'],
                'code': bdef['code'],
                'floors_count': 3,
                'is_demo': True,
                'created_at': ts,
            },
        )
        building_ids.append(bid)
        if c:
            counts['buildings'] += 1

    floor_map = {}
    for b_idx, bid in enumerate(building_ids):
        for fn in range(1, 4):
            floor_name = f'קומה {fn}'
            fid, c = await _find_or_create(
                db, 'floors',
                {'building_id': bid, 'is_demo': True, 'floor_number': fn},
                {
                    'id': _uid(),
                    'building_id': bid,
                    'project_id': project_id,
                    'name': floor_name,
                    'floor_number': fn,
                    'sort_index': fn * 1000,
                    'kind': 'residential',
                    'is_demo': True,
                    'created_at': ts,
                },
            )
            floor_map[(b_idx, fn)] = {'id': fid, 'building_id': bid}
            if c:
                counts['floors'] += 1

    unit_list = []
    unit_counter = 1
    for b_idx in range(len(building_ids)):
        for fn in range(1, 4):
            floor_info = floor_map[(b_idx, fn)]
            for u in range(1, 6):
                unit_no = str(unit_counter)
                uid, c = await _find_or_create(
                    db, 'units',
                    {'floor_id': floor_info['id'], 'is_demo': True, 'unit_no': unit_no},
                    {
                        'id': _uid(),
                        'floor_id': floor_info['id'],
                        'building_id': floor_info['building_id'],
                        'project_id': project_id,
                        'unit_no': unit_no,
                        'unit_type': 'apartment',
                        'status': 'available',
                        'sort_index': u * 10,
                        'is_demo': True,
                        'created_at': ts,
                    },
                )
                unit_list.append({
                    'id': uid,
                    'floor_id': floor_info['id'],
                    'building_id': floor_info['building_id'],
                })
                if c:
                    counts['units'] += 1
                unit_counter += 1

    trade_to_company = company_ids
    existing_demo_defects = await db.tasks.count_documents({'project_id': project_id, 'is_demo': True})
    if existing_demo_defects == 0:
        for i, ddef in enumerate(DEMO_DEFECTS):
            unit = unit_list[i % len(unit_list)]
            matched_company = trade_to_company.get(ddef['cat'])
            status = ddef['status']

            assignee_id = None
            task_company_id = None
            if status in ('assigned', 'in_progress', 'pending_contractor_proof',
                          'pending_manager_approval', 'closed'):
                task_company_id = matched_company
                if ddef['cat'] == 'electrical' and contractor_id:
                    assignee_id = contractor_id

            days_offset = (i * 3) - 20
            due = (datetime.now(timezone.utc) + timedelta(days=days_offset + 30)).strftime('%Y-%m-%d')

            tid = _uid()
            await db.tasks.insert_one({
                'id': tid,
                'project_id': project_id,
                'building_id': unit['building_id'],
                'floor_id': unit['floor_id'],
                'unit_id': unit['id'],
                'title': ddef['title'],
                'description': ddef['desc'],
                'category': ddef['cat'],
                'priority': ddef['pri'],
                'status': status,
                'company_id': task_company_id,
                'assignee_id': assignee_id,
                'due_date': due,
                'created_by': pm_id,
                'created_at': ts,
                'updated_at': ts,
                'short_ref': tid[:8],
                'display_number': i + 1,
                'attachments_count': 0,
                'comments_count': 0,
                'is_demo': True,
            })
            counts['defects'] += 1

            await db.task_status_history.insert_one({
                'id': _uid(),
                'task_id': tid,
                'old_status': None,
                'new_status': 'open',
                'changed_by': pm_id,
                'note': 'נוצר ע"י מערכת הדגמה',
                'is_demo': True,
                'created_at': ts,
            })

    qc_floors = [
        floor_map[(0, 1)],
        floor_map[(0, 2)],
        floor_map[(1, 1)],
    ]
    qc_stage_configs = [
        {
            'stage_ceiling_prep': 'approved',
            'stage_blocks_row1': 'approved',
            'stage_plumbing': 'pending_review',
            'stage_electrical': 'draft',
            'stage_plaster': 'draft',
            'stage_waterproof': 'draft',
            'stage_acoustic': 'draft',
        },
        {
            'stage_ceiling_prep': 'approved',
            'stage_blocks_row1': 'pending_review',
            'stage_plumbing': 'draft',
            'stage_electrical': 'draft',
            'stage_plaster': 'draft',
            'stage_waterproof': 'draft',
            'stage_acoustic': 'draft',
        },
        {
            'stage_ceiling_prep': 'approved',
            'stage_blocks_row1': 'approved',
            'stage_plumbing': 'approved',
            'stage_electrical': 'approved',
            'stage_plaster': 'pending_review',
            'stage_waterproof': 'draft',
            'stage_acoustic': 'draft',
        },
    ]

    for qi, qc_floor in enumerate(qc_floors):
        existing_run = await db.qc_runs.find_one(
            {'floor_id': qc_floor['id'], 'is_demo': True},
            {'_id': 0, 'id': 1},
        )
        if existing_run:
            continue

        stage_config = qc_stage_configs[qi]
        stage_actors = {}
        for sid, s_status in stage_config.items():
            actor_data = {}
            if s_status in ('pending_review', 'approved'):
                actor_data['submitted_by'] = pm_id
                actor_data['submitted_at'] = ts
            if s_status == 'approved':
                actor_data['approved_by'] = pm_id
                actor_data['approved_at'] = ts
            stage_actors[sid] = actor_data

        run_id = _uid()
        await db.qc_runs.insert_one({
            'id': run_id,
            'project_id': project_id,
            'building_id': qc_floor['building_id'],
            'floor_id': qc_floor['id'],
            'template_id': 'tpl_floor_execution_v1',
            'stage_statuses': stage_config,
            'stage_actors': stage_actors,
            'is_demo': True,
            'created_at': ts,
        })
        counts['qc_runs'] += 1

        for sid, s_status in stage_config.items():
            items_for_stage = QC_STAGE_ITEMS.get(sid, [])
            for item_id in items_for_stage:
                if s_status == 'approved':
                    item_status = 'pass'
                elif s_status == 'pending_review':
                    item_status = 'pass'
                else:
                    item_status = 'pending'

                await db.qc_items.insert_one({
                    'id': _uid(),
                    'run_id': run_id,
                    'stage_id': sid,
                    'item_id': item_id,
                    'status': item_status,
                    'note': '',
                    'photos': [],
                    'is_demo': True,
                    'updated_at': ts,
                })
                counts['qc_items'] += 1

    existing_billing = await db.project_billing.find_one(
        {'project_id': project_id, 'is_demo': True},
        {'_id': 0, 'id': 1},
    )
    if not existing_billing:
        from contractor_ops.billing_plans import get_plan, snapshot_pricing
        plan = await get_plan('plan_pro')
        if plan:
            pricing = snapshot_pricing(plan, 30)
            await db.project_billing.insert_one({
                'id': _uid(),
                'project_id': project_id,
                'org_id': org_id,
                'plan_id': 'plan_pro',
                'contracted_units': 30,
                'observed_units': 30,
                'tier_code': pricing['tier_code'],
                'project_fee_snapshot': pricing['project_fee_snapshot'],
                'tier_fee_snapshot': pricing['tier_fee_snapshot'],
                'pricing_version': pricing['pricing_version'],
                'monthly_total': pricing['monthly_total'],
                'status': 'active',
                'setup_state': 'ready',
                'cycle_peak_units': 30,
                'is_demo': True,
                'created_at': ts,
                'updated_at': ts,
            })
            counts['billing'] = 1
            logger.info(f"[DEMO-DATA] Billing: plan_pro, 30 units, {pricing['monthly_total']} ILS/mo")
        else:
            logger.warning("[DEMO-DATA] plan_pro not found — skipping billing seed (plans may not be seeded yet)")

    total_created = sum(counts.values())
    if total_created > 0:
        logger.info(
            f"[DEMO-DATA] Seeded: {counts['projects']} project, {counts['buildings']} buildings, "
            f"{counts['floors']} floors, {counts['units']} units, {counts['defects']} defects, "
            f"{counts['companies']} companies, {counts['qc_runs']} QC runs, "
            f"{counts['qc_items']} QC items, {counts['memberships']} memberships, "
            f"{counts['billing']} billing"
        )
    else:
        logger.info("[DEMO-DATA] All demo data already exists — no changes")
