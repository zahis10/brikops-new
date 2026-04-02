#!/usr/bin/env python3
"""
BrikOps — Billing Test Users Seed Script

Creates 6 test users in different billing states for end-to-end payment testing.

Usage:
MONGODB_URI="mongodb+srv://…" python3 seed_billing_test_users.py

Idempotent: skips users whose phone already exists.
Login: email + password "Test1234!"
"""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    print("ERROR: python-dateutil not installed. Run: pip install python-dateutil")
    sys.exit(1)

try:
    from pymongo import MongoClient
except ImportError:
    print("ERROR: pymongo not installed. Run: pip install pymongo python-dateutil passlib bcrypt")
    sys.exit(1)

try:
    from passlib.hash import bcrypt
    PASSWORD_HASH = bcrypt.hash("Test1234!")
except ImportError:
    print("WARNING: passlib not installed — using placeholder hash")
    PASSWORD_HASH = "$2b$12$placeholder_hash_install_passlib"

MONGODB_URI = os.environ.get("MONGODB_URI") or os.environ.get("MONGO_URL")
if not MONGODB_URI:
    print("ERROR: Set MONGODB_URI or MONGO_URL environment variable")
    sys.exit(1)

DB_NAME = os.environ.get("DB_NAME", "brikops_prod")

# ─── Helpers ───────────────────────────────────────────────

def uid():
    return str(uuid.uuid4())

def now_iso():
    return datetime.now(timezone.utc).isoformat()

now = datetime.now(timezone.utc)

# ─── Test User Definitions ─────────────────────────────────

TEST_USERS = [
    {
        "label": "trial_ending",
        "phone": "050-9991101",
        "phone_e164": "+972509991101",
        "name": "בדיקה — ניסיון נגמר",
        "email": "test_trial_ending@test.brikops.com",
        "org_name": "ארגון בדיקה 1",
        "project_name": "פרויקט בדיקה 1",
        "units": 200,
        "sub": {
            "status": "trialing",
            "plan_id": "",
            "trial_end_at": (now + timedelta(days=2)).isoformat(),
            "paid_until": None,
            "total_monthly": 0,
        },
        "description": "Trial ending in 2 days — sees warning, plan selector visible",
    },
    {
        "label": "trial_expired",
        "phone": "050-9991102",
        "phone_e164": "+972509991102",
        "name": "בדיקה — ניסיון פג",
        "email": "test_trial_expired@test.brikops.com",
        "org_name": "ארגון בדיקה 2",
        "project_name": "פרויקט בדיקה 2",
        "units": 350,
        "sub": {
            "status": "trialing",
            "plan_id": "",
            "trial_end_at": (now - timedelta(days=3)).isoformat(),
            "paid_until": None,
            "total_monthly": 0,
        },
        "description": "Trial expired 3 days ago — paywall, must choose plan & pay",
    },
    {
        "label": "active_standard",
        "phone": "050-9991103",
        "phone_e164": "+972509991103",
        "name": "בדיקה — מנוי רגיל",
        "email": "test_standard@test.brikops.com",
        "org_name": "ארגון בדיקה 3",
        "project_name": "פרויקט בדיקה 3",
        "units": 500,
        "sub": {
            "status": "active",
            "plan_id": "standard",
            "trial_end_at": (now - timedelta(days=30)).isoformat(),
            "paid_until": (now + timedelta(days=25)).isoformat(),
            "total_monthly": 10900,
        },
        "pb_override": {
            "monthly_total": 10900,
            "license_fee": 900,
            "units_fee": 10000,
            "price_per_unit": 20,
        },
        "description": "Active standard plan — full access, can view invoices",
    },
    {
        "label": "active_founder",
        "phone": "050-9991104",
        "phone_e164": "+972509991104",
        "name": "בדיקה — מנוי מייסדים",
        "email": "test_founder@test.brikops.com",
        "org_name": "ארגון בדיקה 4",
        "project_name": "פרויקט בדיקה 4",
        "units": 300,
        "sub": {
            "status": "active",
            "plan_id": "founder_6m",
            "trial_end_at": (now - timedelta(days=30)).isoformat(),
            "paid_until": (now + timedelta(days=25)).isoformat(),
            "total_monthly": 500,
            "plan_locked_until": (now + relativedelta(months=5)).isoformat(),
        },
        "pb_override": {
            "plan_id": "founder_6m",
            "monthly_total": 500,
            "license_fee": 500,
            "units_fee": 0,
            "price_per_unit": 20,
        },
        "description": "Active founder plan — sees 'current plan' badge",
    },
    {
        "label": "founder_expiring",
        "phone": "050-9991105",
        "phone_e164": "+972509991105",
        "name": "בדיקה — מייסדים נגמר",
        "email": "test_founder_exp@test.brikops.com",
        "org_name": "ארגון בדיקה 5",
        "project_name": "פרויקט בדיקה 5",
        "units": 400,
        "sub": {
            "status": "active",
            "plan_id": "founder_6m",
            "trial_end_at": (now - timedelta(days=150)).isoformat(),
            "paid_until": (now + timedelta(days=10)).isoformat(),
            "total_monthly": 500,
            "plan_locked_until": (now + timedelta(days=10)).isoformat(),
        },
        "pb_override": {
            "plan_id": "founder_6m",
            "monthly_total": 500,
            "license_fee": 500,
            "units_fee": 0,
            "price_per_unit": 20,
        },
        "description": "Founder expiring in 10 days — sees expiry warning banner",
    },
    {
        "label": "expired_sub",
        "phone": "050-9991106",
        "phone_e164": "+972509991106",
        "name": "בדיקה — מנוי פג",
        "email": "test_expired@test.brikops.com",
        "org_name": "ארגון בדיקה 6",
        "project_name": "פרויקט בדיקה 6",
        "units": 250,
        "sub": {
            "status": "past_due",
            "plan_id": "standard",
            "trial_end_at": (now - timedelta(days=60)).isoformat(),
            "paid_until": (now - timedelta(days=5)).isoformat(),
            "total_monthly": 5900,
        },
        "pb_override": {
            "monthly_total": 5900,
            "license_fee": 900,
            "units_fee": 5000,
            "price_per_unit": 20,
        },
        "description": "Expired subscription — paywall, must pay",
    },
]

def seed_user(db, config):
    phone = config["phone"]
    phone_e164 = config["phone_e164"]
    label = config["label"]

    existing = db.users.find_one({"$or": [
        {"phone": phone},
        {"phone_e164": phone_e164},
        {"email": config["email"]},
    ]})
    if existing:
        print(f"  SKIP  {label} ({phone}) — already exists")
        return False

    user_id = uid()
    org_id = uid()
    project_id = uid()
    membership_id = uid()
    proj_membership_id = uid()
    building_id = uid()
    pb_id = uid()
    sub_id = uid()
    ts = now_iso()

    db.users.insert_one({
        "id": user_id,
        "email": config["email"],
        "password_hash": PASSWORD_HASH,
        "name": config["name"],
        "phone": phone,
        "phone_e164": phone_e164,
        "role": "project_manager",
        "platform_role": "none",
        "user_status": "active",
        "company_id": None,
        "specialties": [],
        "created_at": ts,
        "updated_at": ts,
    })

    db.organizations.insert_one({
        "id": org_id,
        "name": config["org_name"],
        "owner_user_id": user_id,
        "created_at": ts,
        "updated_at": ts,
    })

    db.organization_memberships.insert_one({
        "id": membership_id,
        "org_id": org_id,
        "user_id": user_id,
        "role": "owner",
        "created_at": ts,
        "updated_at": ts,
    })

    db.projects.insert_one({
        "id": project_id,
        "org_id": org_id,
        "name": config["project_name"],
        "status": "active",
        "created_at": ts,
        "updated_at": ts,
    })

    db.project_memberships.insert_one({
        "id": proj_membership_id,
        "project_id": project_id,
        "user_id": user_id,
        "role": "project_manager",
        "status": "active",
        "created_at": ts,
    })

    db.buildings.insert_one({
        "id": building_id,
        "project_id": project_id,
        "name": "בניין 1",
        "sort_index": 0,
        "created_at": ts,
        "updated_at": ts,
    })

    unit_docs = [{
        "id": uid(),
        "project_id": project_id,
        "building_id": building_id,
        "unit_no": str(i),
        "created_at": ts,
    } for i in range(1, config["units"] + 1)]
    if unit_docs:
        db.units.insert_many(unit_docs)

    pb_plan_id = config.get("pb_override", {}).get("plan_id", "standard")
    pb_monthly = config.get("pb_override", {}).get("monthly_total",
        900 + config["units"] * 20)
    pb_license = config.get("pb_override", {}).get("license_fee", 900)
    pb_units_fee = config.get("pb_override", {}).get("units_fee",
        config["units"] * 20)
    pb_ppu = config.get("pb_override", {}).get("price_per_unit", 20)

    db.project_billing.insert_one({
        "id": pb_id,
        "project_id": project_id,
        "org_id": org_id,
        "plan_id": pb_plan_id,
        "contracted_units": config["units"],
        "observed_units": 0,
        "monthly_total": pb_monthly,
        "license_fee": pb_license,
        "units_fee": pb_units_fee,
        "price_per_unit": pb_ppu,
        "pricing_version": 2,
        "status": "active",
        "setup_state": "complete",
        "cycle_peak_units": config["units"],
        "billing_contact_note": None,
        "created_at": ts,
        "updated_at": ts,
    })

    sub_doc = {
        "id": sub_id,
        "org_id": org_id,
        "status": config["sub"]["status"],
        "plan_id": config["sub"].get("plan_id", ""),
        "trial_end_at": config["sub"].get("trial_end_at"),
        "paid_until": config["sub"].get("paid_until"),
        "total_monthly": config["sub"].get("total_monthly", 0),
        "billing_cycle": "monthly",
        "auto_renew": True,
        "grace_until": None,
        "manual_override": {},
        "created_at": ts,
        "updated_at": ts,
    }
    if config["sub"].get("plan_locked_until"):
        sub_doc["plan_locked_until"] = config["sub"]["plan_locked_until"]

    db.subscriptions.insert_one(sub_doc)

    print(f"  CREATE {label} ({phone}) — {config['description']}")
    print(f"         user={user_id[:8]}  org={org_id[:8]}  project={project_id[:8]}  units={config['units']}")
    return True

def main():
    print(f"Connecting to {DB_NAME}…")
    client = MongoClient(MONGODB_URI)
    db = client[DB_NAME]

    user_count = db.users.count_documents({})
    print(f"Connected. DB has {user_count} users.\n")

    created = 0
    skipped = 0

    print("Seeding billing test users:")
    print("=" * 60)
    for config in TEST_USERS:
        if seed_user(db, config):
            created += 1
        else:
            skipped += 1

    print("=" * 60)
    print(f"Done. Created: {created}, Skipped: {skipped}")

    if created > 0:
        print(f"\nLogin credentials:")
        print(f"  Password: Test1234!")
        print(f"\nTest users:")
        for c in TEST_USERS:
            print(f"  {c['email']:40s}  {c['label']}")

    client.close()

if __name__ == "__main__":
    main()
