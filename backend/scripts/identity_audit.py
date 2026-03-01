#!/usr/bin/env python3
"""Identity audit script — read-only, zero writes.
Produces a report of management users and their email/password status.
"""
import os
import sys
import json
from pymongo import MongoClient

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'contractor_ops')

MANAGEMENT_PROJECT_ROLES = {'project_manager', 'management_team'}
MANAGEMENT_ORG_ROLES = {'owner', 'org_admin', 'billing_admin'}


def run_audit():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]

    all_users = list(db.users.find({}, {'_id': 0, 'id': 1, 'name': 1, 'email': 1,
                                         'password_hash': 1, 'platform_role': 1,
                                         'user_status': 1, 'role': 1}))
    users_by_id = {u['id']: u for u in all_users}

    total = len(all_users)
    active = sum(1 for u in all_users if u.get('user_status') == 'active')
    other_status = total - active

    org_owners = set()
    for org in db.organizations.find({}, {'_id': 0, 'owner_user_id': 1}):
        if org.get('owner_user_id'):
            org_owners.add(org['owner_user_id'])

    org_members = {}
    for mem in db.organization_memberships.find({}, {'_id': 0, 'user_id': 1, 'role': 1}):
        uid = mem.get('user_id')
        role = mem.get('role')
        if uid and role:
            if uid not in org_members:
                org_members[uid] = set()
            org_members[uid].add(role)

    proj_members = {}
    for mem in db.project_memberships.find({}, {'_id': 0, 'user_id': 1, 'role': 1}):
        uid = mem.get('user_id')
        role = mem.get('role')
        if uid and role:
            if uid not in proj_members:
                proj_members[uid] = set()
            proj_members[uid].add(role)

    management_users = set()
    role_breakdown = {
        'super_admin': set(),
        'owner': set(),
        'org_admin': set(),
        'billing_admin': set(),
        'project_manager': set(),
        'management_team': set(),
    }

    for uid, u in users_by_id.items():
        if u.get('platform_role') == 'super_admin':
            management_users.add(uid)
            role_breakdown['super_admin'].add(uid)

        if uid in org_owners:
            management_users.add(uid)
            role_breakdown['owner'].add(uid)

        for org_role in (org_members.get(uid) or set()):
            if org_role in MANAGEMENT_ORG_ROLES:
                management_users.add(uid)
                if org_role in role_breakdown:
                    role_breakdown[org_role].add(uid)

        for proj_role in (proj_members.get(uid) or set()):
            if proj_role in MANAGEMENT_PROJECT_ROLES:
                management_users.add(uid)
                if proj_role in role_breakdown:
                    role_breakdown[proj_role].add(uid)

    def count_with(uids, field):
        return sum(1 for uid in uids if users_by_id.get(uid, {}).get(field))

    mgmt_total = len(management_users)
    mgmt_with_email = count_with(management_users, 'email')
    mgmt_with_pw = count_with(management_users, 'password_hash')
    mgmt_with_both = sum(1 for uid in management_users
                         if users_by_id.get(uid, {}).get('email')
                         and users_by_id.get(uid, {}).get('password_hash'))
    mgmt_missing = mgmt_total - mgmt_with_both

    contractor_uids = set()
    for uid in users_by_id:
        if uid not in management_users:
            proj_roles = proj_members.get(uid) or set()
            if 'contractor' in proj_roles:
                contractor_uids.add(uid)

    viewer_uids = set()
    for uid in users_by_id:
        if uid not in management_users and uid not in contractor_uids:
            viewer_uids.add(uid)

    print("=" * 60)
    print("BrikOps Identity Audit")
    print("=" * 60)
    print()
    print(f"Total users:                     {total}")
    print(f"  Active:                        {active}")
    print(f"  Pending/Suspended/Other:       {other_status}")
    print()
    print(f"Unique management users (would be affected by enforcement):")
    print(f"  Total (unique):                {mgmt_total}")
    print(f"  With email:                    {mgmt_with_email}  ({_pct(mgmt_with_email, mgmt_total)})")
    print(f"  With password_hash:            {mgmt_with_pw}  ({_pct(mgmt_with_pw, mgmt_total)})")
    print(f"  With both email + password:    {mgmt_with_both}  ({_pct(mgmt_with_both, mgmt_total)})")
    print(f"  Missing email OR password:     {mgmt_missing}  ({_pct(mgmt_missing, mgmt_total)}) <- would be affected")
    print()
    role_assignment_sum = sum(len(uids) for uids in role_breakdown.values())
    print(f"Role assignments (non-unique — one user may hold multiple roles):")
    print(f"  Total role assignments:        {role_assignment_sum}  (vs {mgmt_total} unique users)")
    for role_name in ['super_admin', 'owner', 'org_admin', 'billing_admin', 'project_manager', 'management_team']:
        uids = role_breakdown[role_name]
        r_total = len(uids)
        r_email = count_with(uids, 'email')
        r_pw = count_with(uids, 'password_hash')
        print(f"  {role_name:20s}  {r_total:3d} ({r_email} with email, {r_pw} with password)")
    print()
    print(f"Contractors:                     {len(contractor_uids)}  ({count_with(contractor_uids, 'email')} with email — NOT affected)")
    print(f"Viewers/Other:                   {len(viewer_uids)}")
    print("=" * 60)

    result = {
        'total_users': total,
        'active_users': active,
        'unique_management_users': {
            'total': mgmt_total,
            'with_email': mgmt_with_email,
            'with_password': mgmt_with_pw,
            'with_both': mgmt_with_both,
            'missing_either': mgmt_missing,
        },
        'role_assignments_non_unique': {
            'total_assignments': sum(len(uids) for uids in role_breakdown.values()),
            'by_role': {
                role: {
                    'users_holding_role': len(uids),
                    'with_email': count_with(uids, 'email'),
                    'with_password': count_with(uids, 'password_hash'),
                }
                for role, uids in role_breakdown.items()
            },
        },
        'contractors': {
            'total': len(contractor_uids),
            'with_email': count_with(contractor_uids, 'email'),
        },
        'viewers_other': len(viewer_uids),
    }

    out_path = os.path.join(os.path.dirname(__file__), 'identity_audit_result.json')
    with open(out_path, 'w') as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\nJSON output saved to: {out_path}")

    client.close()
    return result


def _pct(n, total):
    if total == 0:
        return "0%"
    return f"{n * 100 // total}%"


if __name__ == '__main__':
    run_audit()
