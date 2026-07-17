"""FUNCTIONAL probes for BATCH qrg1-fix1 — QR gate polish.

Same in-process harness as probe_safety_qrg1.py: REAL FastAPI app, real local
Mongo, real JWTs.

Covers V1 + V2 of the spec:
  V1  gate-scans filters: worker_id / result / date range / combined AND;
      summary counts match the filtered rows; result=junk -> 422;
      date_from=junk -> 422; contractor still 403; no-params call returns
      the old keys + summary (backward compat).
  V2  throttle key derivation: different x-forwarded-for values do NOT share
      a bucket; same value shares; no header falls back to client.host.
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WHATSAPP_ENABLED"] = "false"

import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


async def main():
    from server import app
    from contractor_ops.router import _create_token

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    paid = (now + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-qf1-org-{tag}"
    proj = f"probe-qf1-p1-{tag}"
    pm_id = f"probe-qf1-pm-{tag}"
    con_id = f"probe-qf1-con-{tag}"

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97250{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso},
        {"id": con_id, "role": "contractor", "full_name": "קבלן",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97252{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso},
    ])
    await db.organization_memberships.insert_one(
        {"id": f"qf1-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_many([
        {"id": f"qf1-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"qf1-pm2-{tag}", "project_id": proj, "user_id": con_id, "role": "contractor"},
    ])

    # Two workers + a deterministic seeded scan log:
    #   w1: 2 green today, 1 red 3 days ago
    #   w2: 1 green 10 days ago, 1 invalid today
    w1 = f"qf1-w1-{tag}"
    w2 = f"qf1-w2-{tag}"
    await db.safety_workers.insert_many([
        {"id": w1, "project_id": proj, "full_name": "עובד אחד",
         "deletedAt": None, "created_at": now_iso},
        {"id": w2, "project_id": proj, "full_name": "עובד שניים",
         "deletedAt": None, "created_at": now_iso},
    ])
    day = lambda n: (now - timedelta(days=n)).isoformat()  # noqa: E731
    seed = [
        {"id": f"qf1-s1-{tag}", "project_id": proj, "worker_id": w1, "result": "green", "ts": day(0)},
        {"id": f"qf1-s2-{tag}", "project_id": proj, "worker_id": w1, "result": "green", "ts": day(0)},
        {"id": f"qf1-s3-{tag}", "project_id": proj, "worker_id": w1, "result": "red", "ts": day(3)},
        {"id": f"qf1-s4-{tag}", "project_id": proj, "worker_id": w2, "result": "green", "ts": day(10)},
        {"id": f"qf1-s5-{tag}", "project_id": proj, "worker_id": w2, "result": "invalid", "ts": day(0)},
    ]
    await db.gate_scan_log.insert_many([dict(s) for s in seed])

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role="project_manager"):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    pm_h = h(pm_id)
    con_h = h(con_id, "contractor")
    SCANS = f"/api/safety/{proj}/gate-scans"
    today = now.date().isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
        print("V1 — gate-scans filters + summary")

        # backward compat: no params
        r = await c.get(SCANS, headers=pm_h)
        j = r.json()
        record("V1a no-params → 200, old keys + additive summary",
               r.status_code == 200
               and all(k in j for k in ("items", "total", "limit", "offset", "summary")),
               f"{r.status_code} keys={sorted(j.keys()) if r.status_code==200 else r.text[:100]}")
        record("V1b unfiltered totals: total=5, summary matches seed",
               j.get("total") == 5 and j.get("summary") == {"green": 3, "red": 1, "invalid": 1, "total": 5},
               f"total={j.get('total')} summary={j.get('summary')}")
        record("V1c worker names resolved on rows",
               any(it.get("worker_name") == "עובד אחד" for it in j.get("items", [])))

        # worker filter
        r = await c.get(SCANS, params={"worker_id": w1}, headers=pm_h)
        j = r.json()
        record("V1d worker_id filter → only his rows",
               r.status_code == 200 and j["total"] == 3
               and all(it["worker_id"] == w1 for it in j["items"]),
               f"total={j.get('total')}")
        record("V1e worker-filtered summary {green:2,red:1,invalid:0,total:3}",
               j.get("summary") == {"green": 2, "red": 1, "invalid": 0, "total": 3},
               f"{j.get('summary')}")

        # result filter
        r = await c.get(SCANS, params={"result": "red"}, headers=pm_h)
        j = r.json()
        record("V1f result=red → only red rows",
               r.status_code == 200 and j["total"] == 1
               and all(it["result"] == "red" for it in j["items"]))

        # date range: last 2 days → excludes the 3- and 10-day-old rows
        dfrom = (now - timedelta(days=2)).date().isoformat()
        r = await c.get(SCANS, params={"date_from": dfrom, "date_to": today}, headers=pm_h)
        j = r.json()
        record("V1g date range excludes outside days (3 today-rows only)",
               r.status_code == 200 and j["total"] == 3
               and j["summary"] == {"green": 2, "red": 0, "invalid": 1, "total": 3},
               f"total={j.get('total')} summary={j.get('summary')}")

        # each side independent
        r = await c.get(SCANS, params={"date_to": (now - timedelta(days=5)).date().isoformat()}, headers=pm_h)
        j = r.json()
        record("V1h date_to alone → only the 10-day-old row",
               r.status_code == 200 and j["total"] == 1
               and j["items"][0]["worker_id"] == w2, f"total={j.get('total')}")

        # combined AND
        r = await c.get(SCANS, params={"worker_id": w1, "result": "green",
                                       "date_from": dfrom}, headers=pm_h)
        j = r.json()
        record("V1i combined worker+result+date AND correctly (2 rows)",
               r.status_code == 200 and j["total"] == 2
               and j["summary"]["total"] == 2 and j["summary"]["green"] == 2,
               f"total={j.get('total')}")

        # validation
        r = await c.get(SCANS, params={"result": "junk"}, headers=pm_h)
        record("V1j result=junk → 422 Hebrew detail",
               r.status_code == 422 and "תוצאה" in r.text, f"{r.status_code}")
        r = await c.get(SCANS, params={"date_from": "17-07-2026"}, headers=pm_h)
        record("V1k date_from=junk → 422 Hebrew detail",
               r.status_code == 422 and "תאריך" in r.text, f"{r.status_code}")
        r = await c.get(SCANS, params={"date_to": "junk"}, headers=pm_h)
        record("V1l date_to=junk → 422", r.status_code == 422, f"{r.status_code}")

        # RBAC unchanged
        r = await c.get(SCANS, headers=con_h)
        record("V1m contractor still 403", r.status_code == 403, f"{r.status_code}")

        # index exists
        idx = await db.gate_scan_log.index_information()
        record("V1n idx_gsl_project_worker_ts exists",
               "idx_gsl_project_worker_ts" in idx)

        # ============== V2 — throttle key derivation ==============
        print("V2 — throttle key (x-forwarded-for)")
        from contractor_ops.safety import gate_public
        gate_public._hits.clear()
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})

        # Bypass the app-wide limiter noise: unit-test the derivation via the
        # endpoint by watching which bucket each request lands in.
        tok = "qf1-not-a-real-token-000000000000"
        await c.get(f"/api/gate/{tok}", headers={"x-forwarded-for": "1.1.1.1"})
        await c.get(f"/api/gate/{tok}", headers={"x-forwarded-for": "2.2.2.2"})
        await c.get(f"/api/gate/{tok}", headers={"x-forwarded-for": "1.1.1.1"})
        buckets = dict(gate_public._hits)  # ip -> (window_start, count)
        record("V2a different XFF values → separate buckets",
               "1.1.1.1" in buckets and "2.2.2.2" in buckets
               and buckets["2.2.2.2"][1] == 1,
               f"keys={sorted(buckets.keys())}")
        record("V2b same XFF value shares one bucket (count=2)",
               buckets.get("1.1.1.1", (0, 0))[1] == 2,
               f"count={buckets.get('1.1.1.1', (0, 0))[1]}")
        gate_public._hits.clear()
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})
        await c.get(f"/api/gate/{tok}")  # no header → client.host fallback
        fb = dict(gate_public._hits)
        record("V2c no header → falls back to client.host bucket",
               len(fb) == 1 and "1.1.1.1" not in fb, f"keys={sorted(fb.keys())}")
        gate_public._hits.clear()
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})
        # V2d — multi-hop XFF chain must normalize to FIRST ip (matches server.py)
        await c.get(f"/api/gate/{tok}",
                    headers={"x-forwarded-for": "1.1.1.1, 10.0.0.1, 10.0.0.2"})
        await c.get(f"/api/gate/{tok}",
                    headers={"x-forwarded-for": "1.1.1.1, 99.9.9.9"})
        ch = dict(gate_public._hits)
        record("V2d comma-chain XFF → first IP bucket, chain variance ignored",
               ch.get("1.1.1.1", (0, 0))[1] == 2 and len(ch) == 1,
               f"keys={sorted(ch.keys())} count={ch.get('1.1.1.1', (0, 0))[1]}")
        gate_public._hits.clear()
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})

    # cleanup probe artifacts
    await db.gate_scan_log.delete_many({"id": {"$regex": f"^qf1-s"}})
    await db.safety_workers.delete_many({"id": {"$in": [w1, w2]}})
    await db.users.delete_many({"id": {"$in": [pm_id, con_id]}})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.organization_memberships.delete_many({"org_id": org})
    await db.projects.delete_many({"id": proj})
    await db.subscriptions.delete_many({"org_id": org})
    await db.organizations.delete_many({"id": org})

    failed = [n for n, p in RESULTS if not p]
    print(f"\n{'=' * 60}\nTOTAL: {len(RESULTS)}  PASS: {len(RESULTS) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", *failed, sep="\n  - ")
        sys.exit(1)
    print("ALL GREEN")


if __name__ == "__main__":
    asyncio.run(main())
