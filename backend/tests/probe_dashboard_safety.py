"""FUNCTIONAL HTTP probes — BATCH visual-dashboard (safety block in dashboard).

Drives the REAL FastAPI app in-process (httpx ASGITransport) with a REAL
local Mongo and a REAL JWT minted with the app's own _create_token.
Verifies GET /api/projects/{id}/dashboard:
  - PM → safety {open_incidents:1, expiring_certs_7:1, expiring_certs_30:1,
    gate_entries_today:3, last_tour_days:3}
  - contractor → safety: None
  - monkeypatched safety query failure → 200 with safety: None (fail-soft)
  - all pre-existing payload keys still present
"""
import os
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local
os.environ["DB_NAME"] = "contractor_ops"
os.environ["TRANSLATE_MOCK"] = "1"
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = ""

import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.utils.timezone import israel_today

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = uuid.uuid4().hex[:8]
    pm_id = f"probe-dsafe-pm-{tag}"
    con_id = f"probe-dsafe-con-{tag}"
    org_id = f"probe-dsafe-org-{tag}"
    project_id = f"probe-dsafe-proj-{tag}"

    now = datetime.now(timezone.utc)
    today = date.fromisoformat(israel_today())

    await db.organizations.insert_one({
        "id": org_id, "name": f"ארגון דשבורד {tag}", "owner_user_id": pm_id,
    })
    await db.subscriptions.insert_one({
        "org_id": org_id, "status": "active",
        "paid_until": (now + timedelta(days=30)).isoformat(),
    })
    await db.projects.insert_one({
        "id": project_id, "org_id": org_id, "name": f"פרויקט דשבורד {tag}",
    })
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "name": "מנהל דשבורד",
         "user_status": "active", "session_version": 0},
        {"id": con_id, "role": "contractor", "name": "קבלן דשבורד",
         "user_status": "active", "session_version": 0},
    ])
    await db.organization_memberships.insert_many([
        {"id": f"om-pm-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
        {"id": f"om-con-{tag}", "org_id": org_id, "user_id": con_id, "role": "member"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"pm-m-{tag}", "project_id": project_id, "user_id": pm_id,
         "role": "project_manager"},
        {"id": f"con-m-{tag}", "project_id": project_id, "user_id": con_id,
         "role": "contractor"},
    ])

    # --- safety seed --------------------------------------------------------
    # incidents: 1 reported (open) + 1 closed
    await db.safety_incidents.insert_many([
        {"id": f"inc-open-{tag}", "project_id": project_id, "status": "reported",
         "occurred_at": now.isoformat(), "deletedAt": None},
        {"id": f"inc-closed-{tag}", "project_id": project_id, "status": "closed",
         "occurred_at": now.isoformat(), "deletedAt": None},
    ])
    # trainings: expiring in 3 / 20 / 400 days + one expired (-5), distinct
    # (worker, type) pairs so newest-per-group keeps each one
    def training(days, wtag, ttype):
        return {
            "id": f"tr-{wtag}-{tag}", "project_id": project_id,
            "worker_id": f"w-{wtag}-{tag}", "training_type": ttype,
            "trained_at": (now - timedelta(days=30)).isoformat(),
            "created_at": (now - timedelta(days=30)).isoformat(),
            "expires_at": (today + timedelta(days=days)).isoformat(),
            "deletedAt": None,
        }
    await db.safety_trainings.insert_many([
        training(3, "a", "height"),
        training(20, "b", "height"),
        training(400, "c", "height"),
        training(-5, "d", "height"),
        training(4, "f", "height"),   # soft-deleted worker → excluded
    ])
    # worker docs: w-a is a legacy doc with NO deletedAt field (must count as
    # active); w-f is soft-deleted (its expiring cert must be excluded)
    await db.safety_workers.insert_many([
        {"id": f"w-a-{tag}", "project_id": project_id, "name": "עובד פעיל"},
        {"id": f"w-f-{tag}", "project_id": project_id, "name": "עובד מחוק",
         "deletedAt": now.isoformat()},
    ])
    # gate scans: 3 green today + 1 green yesterday + 1 red today
    def scan(result, ts):
        return {"id": str(uuid.uuid4()), "project_id": project_id,
                "worker_id": f"w-a-{tag}", "token_id": None, "ts": ts.isoformat(),
                "result": result, "reasons": []}
    await db.gate_scan_log.insert_many([
        scan("green", now),
        scan("green", now - timedelta(minutes=5)),
        scan("green", now - timedelta(minutes=10)),
        scan("green", now - timedelta(days=1)),
        scan("red", now),
    ])
    # tour: completed (pending_signature) submitted 3 days ago
    await db.safety_tours.insert_one({
        "id": f"tour-{tag}", "project_id": project_id, "status": "pending_signature",
        "tour_date": (today - timedelta(days=3)).isoformat(),
        "submitted_at": (now - timedelta(days=3)).isoformat(),
        "signed_at": None, "items": [], "deletedAt": None,
    })

    h_pm = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
    h_con = {"Authorization": f"Bearer {_create_token(con_id, 'contractor')}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe") as c:
        url = f"/api/projects/{project_id}/dashboard"

        # 1. PM → seeded safety counts
        r = await c.get(url, headers=h_pm)
        record("PM dashboard → 200", r.status_code == 200, f"status={r.status_code} {r.text[:150]}")
        body = r.json() if r.status_code == 200 else {}
        s = body.get("safety")
        record("PM safety block present", isinstance(s, dict), f"safety={s}")
        expected = {"open_incidents": 1, "expiring_certs_7": 1,
                    "expiring_certs_30": 1, "gate_entries_today": 3,
                    "last_tour_days": 3}
        for k, v in expected.items():
            record(f"safety.{k} == {v}", isinstance(s, dict) and s.get(k) == v,
                   f"got={None if not isinstance(s, dict) else s.get(k)}")

        # 2. all pre-existing payload keys unchanged/present
        for k in ["kpis", "pending_approvals", "stuck_contractors",
                  "load_by_building", "contractor_quality", "role",
                  "total_tasks", "by_status", "by_category"]:
            record(f"existing key '{k}' present", k in body)
        kpi_keys = {"open_total", "open_last7", "in_progress", "closed_total",
                    "closed_last7", "pending_approval", "overdue", "team_count",
                    "sla_response_7d", "sla_close_7d", "sla_response_30d",
                    "sla_close_30d"}
        record("kpis keys unchanged", kpi_keys == set((body.get("kpis") or {}).keys()),
               f"got={sorted((body.get('kpis') or {}).keys())}")

        # 3. contractor → safety None
        r = await c.get(url, headers=h_con)
        record("contractor dashboard → 200", r.status_code == 200, f"status={r.status_code}")
        record("contractor safety is None",
               r.status_code == 200 and r.json().get("safety") is None,
               f"safety={r.json().get('safety') if r.status_code == 200 else '?'}")

        # 4. fail-soft: monkeypatch israel_today (imported inside the try) to raise
        import contractor_ops.utils.timezone as tzmod
        orig = tzmod.israel_today

        def boom():
            raise RuntimeError("probe-forced safety failure")
        tzmod.israel_today = boom
        try:
            r = await c.get(url, headers=h_pm)
            record("fail-soft: dashboard still 200", r.status_code == 200,
                   f"status={r.status_code}")
            record("fail-soft: safety is None",
                   r.status_code == 200 and r.json().get("safety") is None,
                   f"safety={r.json().get('safety') if r.status_code == 200 else '?'}")
            record("fail-soft: kpis still served",
                   r.status_code == 200 and isinstance(r.json().get("kpis"), dict))
        finally:
            tzmod.israel_today = orig

        # 5. sanity: PM again after restore → safety back
        r = await c.get(url, headers=h_pm)
        record("after restore: safety back for PM",
               r.status_code == 200 and isinstance(r.json().get("safety"), dict))

    # cleanup
    await db.organizations.delete_many({"id": org_id})
    await db.subscriptions.delete_many({"org_id": org_id})
    await db.projects.delete_many({"id": project_id})
    await db.users.delete_many({"id": {"$in": [pm_id, con_id]}})
    await db.organization_memberships.delete_many({"org_id": org_id})
    await db.project_memberships.delete_many({"project_id": project_id})
    for coll in ["safety_incidents", "safety_trainings", "gate_scan_log", "safety_tours", "safety_workers"]:
        await db[coll].delete_many({"project_id": project_id})

    passed = sum(1 for _, p, _ in RESULTS if p)
    print(f"\n{passed}/{len(RESULTS)} passed")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
