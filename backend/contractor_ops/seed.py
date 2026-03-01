import asyncio
import uuid
import random
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URL, DB_NAME, APP_ID
import bcrypt

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

def _now():
    return datetime.now(timezone.utc).isoformat()

def _hash(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def _id():
    return str(uuid.uuid4())

CATEGORIES = ['electrical', 'plumbing', 'hvac', 'painting', 'flooring', 'carpentry', 'masonry', 'windows', 'doors', 'general', 'bathroom_cabinets', 'finishes', 'structural', 'aluminum', 'metalwork']
TRADE_HEBREW = {'electrical': 'חשמלאי', 'plumbing': 'אינסטלטור', 'painting': 'צבעי', 'flooring': 'רצף', 'carpentry': 'נגר'}
PRIORITIES = ['low', 'medium', 'high', 'critical']
STATUSES_SEQUENCE = ['open', 'assigned', 'in_progress', 'pending_contractor_proof', 'pending_manager_approval', 'closed']

async def seed():
    print(f"Seeding database: {DB_NAME} (APP_ID: {APP_ID})")

    await db.users.delete_many({})
    await db.companies.delete_many({})
    await db.projects.delete_many({})
    await db.buildings.delete_many({})
    await db.floors.delete_many({})
    await db.units.delete_many({})
    await db.tasks.delete_many({})
    await db.task_updates.delete_many({})
    await db.task_status_history.delete_many({})
    await db.audit_events.delete_many({})
    await db.otp_codes.delete_many({})
    await db.join_requests.delete_many({})
    await db.project_memberships.delete_many({})
    await db.notification_jobs.delete_many({})
    print("  Cleared existing data")

    companies = []
    company_trades = [
        ('אלקטרו-פרו', 'electrical'),
        ('אינסט-מובייל', 'plumbing'),
        ('צבע-מאסטר', 'painting'),
        ('ריצוף-טופ', 'flooring'),
        ('נגרות-אומן', 'carpentry'),
    ]
    for name, trade in company_trades:
        cid = _id()
        await db.companies.insert_one({
            'id': cid, 'name': name, 'trade': trade,
            'specialties': [trade, 'general'],
            'contact_name': f'מנהל {name}', 'contact_phone': '050-1234567',
            'phone_e164': f'+97250123456{company_trades.index((name, trade))}',
            'whatsapp_enabled': True, 'whatsapp_opt_in': True,
            'contact_email': f'{trade}@example.com', 'created_at': _now(),
        })
        companies.append({'id': cid, 'trade': trade})
    print(f"  Created {len(companies)} companies")

    admin_id = _id()
    pm_id = _id()
    contractor_ids = []
    viewer_id = _id()

    await db.users.insert_one({
        'id': admin_id, 'email': 'admin@contractor-ops.com', 'password_hash': _hash('admin123'),
        'name': 'מנהל מערכת', 'phone': '050-0000001', 'role': 'project_manager',
        'phone_e164': '+972500000001',
        'user_status': 'active',
        'company_id': None, 'created_at': _now(),
    })
    await db.users.insert_one({
        'id': pm_id, 'email': 'pm@contractor-ops.com', 'password_hash': _hash('pm123'),
        'name': 'מנהל פרויקט', 'phone': '050-0000002', 'role': 'project_manager',
        'phone_e164': '+972500000002',
        'user_status': 'active',
        'company_id': None, 'created_at': _now(),
    })
    for i, comp in enumerate(companies[:3]):
        cid = _id()
        await db.users.insert_one({
            'id': cid, 'email': f'contractor{i+1}@contractor-ops.com', 'password_hash': _hash('cont123'),
            'name': TRADE_HEBREW.get(comp['trade'], f'קבלן {comp["trade"]}'), 'phone': f'050-000100{i}', 'role': 'contractor',
            'company_id': comp['id'], 'specialties': [comp['trade'], 'general'],
            'phone_e164': f'+97250010{i}0{i}',
            'user_status': 'active',
            'created_at': _now(),
        })
        contractor_ids.append(cid)
    await db.users.insert_one({
        'id': viewer_id, 'email': 'viewer@contractor-ops.com', 'password_hash': _hash('view123'),
        'name': 'צופה', 'phone': '050-0000099', 'role': 'viewer',
        'phone_e164': '+972500000099',
        'user_status': 'active',
        'company_id': None, 'created_at': _now(),
    })

    mgmt_ids = []
    mgmt_users = [
        ('מנהל עבודה', 'site_manager', 'sitemanager@contractor-ops.com', '+972500000010'),
        ('מהנדס ביצוע', 'execution_engineer', 'engineer@contractor-ops.com', '+972500000011'),
        ('עוזר בטיחות', 'safety_assistant', 'safety@contractor-ops.com', '+972500000012'),
    ]
    for mname, sub_role, memail, mphone in mgmt_users:
        mid = _id()
        await db.users.insert_one({
            'id': mid, 'email': memail, 'password_hash': _hash('mgmt123'),
            'name': mname, 'phone': mphone[-10:], 'role': 'management_team',
            'phone_e164': mphone,
            'user_status': 'active',
            'company_id': None, 'created_at': _now(),
        })
        mgmt_ids.append({'id': mid, 'sub_role': sub_role})

    print(f"  Created {4 + len(contractor_ids) + len(mgmt_ids)} users (project_manager, pm, {len(contractor_ids)} contractors, {len(mgmt_ids)} management_team, viewer)")

    project_id = _id()
    await db.projects.insert_one({
        'id': project_id, 'name': 'פרויקט מגדלי הים', 'code': 'SEA-001',
        'description': 'פרויקט מגורים 2 בניינים, 120 דירות',
        'status': 'active', 'client_name': 'חברת בנייה לדוגמה',
        'start_date': '2026-01-01', 'end_date': '2027-06-30',
        'created_by': pm_id, 'created_at': _now(), 'updated_at': _now(),
    })
    print(f"  Created project: SEA-001")

    building_ids = []
    building_names = [('בניין A', 'A'), ('בניין B', 'B')]
    for bname, bcode in building_names:
        bid = _id()
        await db.buildings.insert_one({
            'id': bid, 'project_id': project_id, 'name': bname,
            'code': bcode, 'floors_count': 2, 'created_at': _now(),
        })
        building_ids.append(bid)
    print(f"  Created {len(building_ids)} buildings")

    floor_ids = []
    for bid in building_ids:
        for fn in range(1, 3):
            fid = _id()
            await db.floors.insert_one({
                'id': fid, 'building_id': bid, 'project_id': project_id,
                'name': f'קומה {fn}', 'floor_number': fn, 'created_at': _now(),
            })
            floor_ids.append({'id': fid, 'building_id': bid})
    print(f"  Created {len(floor_ids)} floors")

    unit_ids = []
    unit_counter = 1
    for floor in floor_ids:
        for u in range(5):
            uid = _id()
            await db.units.insert_one({
                'id': uid, 'floor_id': floor['id'], 'building_id': floor['building_id'],
                'project_id': project_id, 'unit_no': str(unit_counter),
                'unit_type': 'apartment', 'status': 'available', 'created_at': _now(),
            })
            unit_ids.append({'id': uid, 'floor_id': floor['id'], 'building_id': floor['building_id']})
            unit_counter += 1
    print(f"  Created {len(unit_ids)} units")

    task_titles = [
        ('תיקון שקע חשמל', 'electrical'), ('התקנת מפסק', 'electrical'),
        ('תיקון נזילה', 'plumbing'), ('התקנת ברז', 'plumbing'), ('החלפת צינור', 'plumbing'),
        ('צביעת קירות', 'painting'), ('צביעת תקרה', 'painting'),
        ('ריצוף חדר', 'flooring'), ('תיקון אריח', 'flooring'),
        ('התקנת דלת', 'doors'), ('תיקון ידית', 'doors'),
        ('החלפת חלון', 'windows'), ('תיקון תריס', 'windows'),
        ('התקנת ארון מטבח', 'carpentry'), ('תיקון מדף מטבח', 'carpentry'),
        ('התקנת מזגן', 'hvac'), ('תחזוקת מיזוג', 'hvac'),
        ('תיקון כללי', 'general'),
        ('בדיקת רטיבות', 'plumbing'), ('שיפוץ מרפסת', 'general'),
        ('התקנת תאורה', 'electrical'), ('צביעת חדר מדרגות', 'painting'),
        ('התקנת ארון אמבטיה', 'bathroom_cabinets'), ('תיקון ארון אמבטיה', 'bathroom_cabinets'),
        ('גמר טיח', 'finishes'), ('גמר צבע', 'finishes'),
        ('יציקת תקרה', 'structural'), ('תיקון עמוד', 'structural'),
        ('התקנת חלון אלומיניום', 'aluminum'), ('תיקון מסגרת אלומיניום', 'aluminum'),
        ('התקנת מעקה ברזל', 'metalwork'), ('תיקון שער מסגרות', 'metalwork'),
        ('בדיקת חשמל', 'electrical'), ('החלפת ריצוף מרפסת', 'flooring'),
    ]

    trade_to_contractor = {}
    trade_to_company = {}
    for idx, comp in enumerate(companies[:3]):
        trade_to_contractor[comp['trade']] = contractor_ids[idx]
        trade_to_company[comp['trade']] = comp['id']

    for i, (title, category) in enumerate(task_titles):
        unit = random.choice(unit_ids)
        matched_company = trade_to_company.get(category)
        matched_assignee = trade_to_contractor.get(category)
        status_idx = random.randint(0, min(4, len(STATUSES_SEQUENCE) - 1))
        status = STATUSES_SEQUENCE[status_idx]
        if not matched_assignee:
            status = 'open'
        due = (datetime.now(timezone.utc) + timedelta(days=random.randint(-5, 30))).strftime('%Y-%m-%d')

        tid = _id()
        ts = _now()
        await db.tasks.insert_one({
            'id': tid, 'project_id': project_id, 'building_id': unit['building_id'],
            'floor_id': unit['floor_id'], 'unit_id': unit['id'],
            'title': title, 'description': f'תיאור: {title}',
            'category': category, 'priority': random.choice(PRIORITIES),
            'status': status, 'company_id': matched_company, 'assignee_id': matched_assignee,
            'due_date': due, 'created_by': pm_id,
            'created_at': ts, 'updated_at': ts,
            'attachments_count': 0, 'comments_count': 0,
        })
        await db.task_status_history.insert_one({
            'id': _id(), 'task_id': tid, 'old_status': None, 'new_status': 'open',
            'changed_by': pm_id, 'note': 'Task created', 'created_at': ts,
        })
    print(f"  Created {len(task_titles)} tasks")

    ts = _now()
    await db.project_memberships.insert_one({
        'id': _id(), 'project_id': project_id, 'user_id': admin_id,
        'role': 'project_manager', 'status': 'active', 'created_at': ts,
    })
    await db.project_memberships.insert_one({
        'id': _id(), 'project_id': project_id, 'user_id': pm_id,
        'role': 'project_manager', 'status': 'active', 'created_at': ts,
    })
    for idx, cid in enumerate(contractor_ids):
        membership_doc = {
            'id': _id(), 'project_id': project_id, 'user_id': cid,
            'role': 'contractor', 'status': 'active', 'created_at': ts,
            'contractor_trade_key': companies[idx]['trade'],
        }
        await db.project_memberships.insert_one(membership_doc)
    for mgmt in mgmt_ids:
        await db.project_memberships.insert_one({
            'id': _id(), 'project_id': project_id, 'user_id': mgmt['id'],
            'role': 'management_team', 'sub_role': mgmt['sub_role'],
            'status': 'active', 'created_at': ts,
        })
    print(f"  Created {2 + len(contractor_ids) + len(mgmt_ids)} project memberships")

    print()
    print("=== Seed Complete ===")
    print(f"  DB: {DB_NAME}")
    print(f"  APP_ID: {APP_ID}")
    print(f"  Demo accounts:")
    print(f"    admin@contractor-ops.com / admin123 (project_manager)")
    print(f"    pm@contractor-ops.com / pm123 (project_manager)")
    print(f"    sitemanager@contractor-ops.com / mgmt123 (management_team - site_manager)")
    print(f"    engineer@contractor-ops.com / mgmt123 (management_team - execution_engineer)")
    print(f"    safety@contractor-ops.com / mgmt123 (management_team - safety_assistant)")
    print(f"    contractor1@contractor-ops.com / cont123 (contractor)")
    print(f"    viewer@contractor-ops.com / view123 (viewer)")

if __name__ == '__main__':
    from config import APP_MODE
    if APP_MODE == 'prod':
        print("FATAL: seed.py CANNOT run in production (APP_MODE=prod). This would DELETE ALL DATA.")
        print("Aborting.")
        sys.exit(1)
    run_seed = os.environ.get('RUN_SEED', '').lower()
    if run_seed != 'true':
        print("FATAL: seed.py requires RUN_SEED=true to run. This is a safety guard against accidental data deletion.")
        print("Usage: RUN_SEED=true python contractor_ops/seed.py")
        sys.exit(1)
    print(f"[SEED GUARD] APP_MODE={APP_MODE}, RUN_SEED={run_seed} — proceeding with seed")
    asyncio.run(seed())
