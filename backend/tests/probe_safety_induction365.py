"""FUNCTIONAL probes for BATCH induction-365-enforce — annual cap on the
induction conduct expiry + B3 PATCH bypass closure.

Same in-process harness as probe_safety_ind2_fix4.py: REAL FastAPI app,
real local Mongo, real JWTs.

Covers (V1 of the batch):
  a. conduct expires_at = today+400 → 422 "מוגבל לשנה"; nothing stored.
  b. conduct expires_at = today / yesterday → 422 "עתידי"; nothing stored.
  c. conduct expires_at = today+300 → 201; stored == today+300.
  d. conduct expires_at = today+365 (boundary) → 201; stored == today+365.
  e. conduct with NO expires_at → 201; stored == today+365 (default == cap).
  f. malformed "2026-13-40" → 422 "לא תקין".
  B3: PATCH induction with expires_at (today+400 AND today+200) → 422
      "נקבע רק בתהליך ההדרכה"; PATCH other field on induction → 200;
      PATCH expires_at on a NON-induction training → 200.
  REGRESSION: POST /trainings with the induction type → still 422;
      green-worker gate check works for a fresh in-bounds conduct.
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_ENABLED"] = "false"

import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def sections(n, prefix="סעיף"):
    return [{"title": f"{prefix} {i + 1}", "body": f"תוכן {prefix} {i + 1}"} for i in range(n)]


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-i365-org-{tag}"
    proj = f"probe-i365-p1-{tag}"
    pm_id = f"probe-i365-pm-{tag}"
    w1 = f"probe-i365-w1-{tag}"   # rejection cases (nothing must be stored)
    w2 = f"probe-i365-w2-{tag}"   # accepted conducts + gate check
    w3 = f"probe-i365-w3-{tag}"   # non-induction PATCH regression

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_one(
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": "+972507711001", "last_login_at": now_iso})
    await db.organization_memberships.insert_one(
        {"id": f"i365-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_one(
        {"id": f"i365-pm1-{tag}", "project_id": proj, "user_id": pm_id,
         "role": "project_manager"})
    await db.safety_workers.insert_many([
        {"id": w, "project_id": proj, "full_name": f"עובד {i}", "deletedAt": None,
         "created_at": now_iso}
        for i, w in enumerate([w1, w2, w3], start=1)
    ])

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}

    TMPL = f"/api/safety/{proj}/induction-template"
    CONDUCT = f"/api/safety/{proj}/induction/conduct"
    TRAININGS = f"/api/safety/{proj}/trainings"
    WORKERS = f"/api/safety/{proj}/workers"

    today = date.today()
    cap = (today + timedelta(days=365)).isoformat()

    def conduct_data(worker, expires=None):
        d = {"worker_id": worker, "language_choice": "he",
             "signer_name": "עובד", "signature_type": "typed", "typed_name": "עובד"}
        if expires is not None:
            d["expires_at"] = expires
        return d

    async def stored_count(worker):
        return await db.safety_trainings.count_documents(
            {"project_id": proj, "worker_id": worker, "deletedAt": None})

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe",
                                 timeout=60) as c:
        r = await c.put(TMPL, json={"sections": sections(2, "בטיחות")}, headers=pm_h)
        assert r.status_code == 200, f"template save failed {r.status_code} {r.text[:200]}"

        # ---- a. today+400 → 422 "מוגבל לשנה", nothing stored ----
        r = await c.post(CONDUCT, data=conduct_data(
            w1, (today + timedelta(days=400)).isoformat()), headers=pm_h)
        record("a. today+400 → 422 מוגבל לשנה",
               r.status_code == 422 and "מוגבל לשנה" in str(r.json().get("detail")),
               f"status={r.status_code} {r.text[:120]}")
        record("a2. cap date echoed in detail", cap in str(r.json().get("detail")))
        record("a3. nothing stored", await stored_count(w1) == 0)

        # ---- b. today / yesterday → 422 "עתידי", nothing stored ----
        r = await c.post(CONDUCT, data=conduct_data(w1, today.isoformat()), headers=pm_h)
        record("b1. today → 422 עתידי",
               r.status_code == 422 and "עתידי" in str(r.json().get("detail")),
               f"status={r.status_code} {r.text[:120]}")
        r = await c.post(CONDUCT, data=conduct_data(
            w1, (today - timedelta(days=1)).isoformat()), headers=pm_h)
        record("b2. yesterday → 422 עתידי",
               r.status_code == 422 and "עתידי" in str(r.json().get("detail")))
        record("b3. nothing stored", await stored_count(w1) == 0)

        # ---- f. malformed → 422 "לא תקין" ----
        r = await c.post(CONDUCT, data=conduct_data(w1, "2026-13-40"), headers=pm_h)
        record("f. malformed 2026-13-40 → 422 לא תקין",
               r.status_code == 422 and "לא תקין" in str(r.json().get("detail")),
               f"status={r.status_code} {r.text[:120]}")
        record("f2. nothing stored after all rejections", await stored_count(w1) == 0)

        # ---- c. today+300 → 201, stored == today+300 ----
        exp300 = (today + timedelta(days=300)).isoformat()
        r = await c.post(CONDUCT, data=conduct_data(w2, exp300), headers=pm_h)
        record("c. today+300 → 201 stored==today+300",
               r.status_code == 201 and r.json().get("expires_at") == exp300,
               f"status={r.status_code} {r.text[:120]}")
        ind_300 = r.json() if r.status_code == 201 else {}

        # ---- d. today+365 boundary → 201, stored == cap ----
        r = await c.post(CONDUCT, data=conduct_data(w2, cap), headers=pm_h)
        record("d. today+365 boundary → 201 stored==cap",
               r.status_code == 201 and r.json().get("expires_at") == cap,
               f"status={r.status_code} {r.text[:120]}")

        # ---- e. NO expires_at → 201, stored == cap (default == cap) ----
        r = await c.post(CONDUCT, data=conduct_data(w2), headers=pm_h)
        record("e. omitted → 201 default==cap",
               r.status_code == 201 and r.json().get("expires_at") == cap,
               f"status={r.status_code} {r.text[:120]}")

        # ---- B3: PATCH induction expires_at → 422; other fields → OK ----
        ind_id = ind_300.get("id")
        r = await c.patch(f"{TRAININGS}/{ind_id}", json={
            "expires_at": (today + timedelta(days=400)).isoformat()}, headers=pm_h)
        record("B3a. PATCH induction expires_at today+400 → 422 נקבע רק בתהליך",
               r.status_code == 422 and "נקבע רק בתהליך ההדרכה" in str(r.json().get("detail")),
               f"status={r.status_code} {r.text[:120]}")
        r = await c.patch(f"{TRAININGS}/{ind_id}", json={
            "expires_at": (today + timedelta(days=200)).isoformat()}, headers=pm_h)
        record("B3b. PATCH induction expires_at today+200 (in-bounds) → still 422",
               r.status_code == 422 and "נקבע רק בתהליך ההדרכה" in str(r.json().get("detail")))
        doc = await db.safety_trainings.find_one({"id": ind_id})
        record("B3c. stored expires_at unchanged (== today+300)",
               (doc or {}).get("expires_at") == exp300)
        r = await c.patch(f"{TRAININGS}/{ind_id}", json={"location": "אתר צפון"},
                          headers=pm_h)
        record("B3d. PATCH other field on induction → 200",
               r.status_code == 200 and r.json().get("location") == "אתר צפון",
               f"status={r.status_code} {r.text[:120]}")

        # non-induction training: expires_at PATCH still works
        r = await c.post(TRAININGS, json={
            "worker_id": w3, "training_type": "עבודה בגובה",
            "trained_at": now_iso,
            "expires_at": (today + timedelta(days=100)).isoformat(),
        }, headers=pm_h)
        assert r.status_code == 201, f"generic create failed {r.status_code} {r.text[:200]}"
        gen_id = r.json()["id"]
        new_exp = (today + timedelta(days=500)).isoformat()
        r = await c.patch(f"{TRAININGS}/{gen_id}", json={"expires_at": new_exp},
                          headers=pm_h)
        record("B3e. PATCH expires_at on NON-induction training → 200",
               r.status_code == 200 and r.json().get("expires_at") == new_exp,
               f"status={r.status_code} {r.text[:120]}")

        # ---- REGRESSION: generic POST /trainings induction type still 422 ----
        r = await c.post(TRAININGS, json={
            "worker_id": w1, "training_type": INDUCTION_TRAINING_TYPE,
            "trained_at": now_iso,
        }, headers=pm_h)
        record("R1. POST /trainings induction type → still 422",
               r.status_code == 422 and "נוצרת רק דרך" in str(r.json().get("detail")),
               f"status={r.status_code} {r.text[:120]}")

        # ---- REGRESSION: fresh in-bounds conduct → worker shows validity ----
        r = await c.get(WORKERS, headers=pm_h)
        items = {it["id"]: it for it in r.json().get("items", [])}
        record("R2. green worker — induction_valid_until == cap (max over conducts)",
               r.status_code == 200 and items.get(w2, {}).get("induction_valid_until") == cap,
               f"got={items.get(w2, {}).get('induction_valid_until')}")

    # cleanup
    await db.organizations.delete_many({"id": org})
    await db.subscriptions.delete_many({"org_id": org})
    await db.users.delete_many({"id": pm_id})
    await db.organization_memberships.delete_many({"org_id": org})
    await db.projects.delete_many({"id": proj})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.safety_workers.delete_many({"project_id": proj})
    await db.safety_trainings.delete_many({"project_id": proj})
    await db.induction_templates.delete_many({"org_id": org})
    await db.induction_content_snapshots.delete_many({"org_id": org})
    await db.audit_events.delete_many({"payload.org_id": org})
    await db.audit_events.delete_many({"payload.project_id": proj})

    passed = sum(1 for _, p in RESULTS if p)
    print(f"\n===== {passed}/{len(RESULTS)} PASSED =====")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
