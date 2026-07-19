"""FUNCTIONAL probes for BATCH safety-ind2-fix4 — induction polish:
worker-row induction status, evidence endpoint, born-signed enforcement.

Same in-process harness as probe_safety_ind2_fix1.py: REAL FastAPI app,
real local Mongo, real JWTs.

Covers:
  V1  list_workers adds induction_valid_until — max expires_at over SIGNED
      induction trainings; null when none; unsigned/deleted/other-type rows
      ignored; PII posture unchanged (no id_number_hash in list).
  V2  Born-signed guards: POST trainings with the induction type (exact and
      padded) → 422 Hebrew; other types → 201; sign_training on a legacy
      unsigned induction row → 422; on a normal training → works; PATCH
      rename to/from the induction type → 422; unrelated PATCH → 200.
  V3  Evidence endpoint: conduct (he + "other"/interpreter) → GET evidence
      returns snapshot-identical sections (content_hash match), correct
      attestation/interpreter/signature fields; non-induction id → 404;
      unsigned induction → 404; no project access → 403.
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


def heb(s):
    return any("\u0590" <= ch <= "\u05EA" for ch in str(s))


def sections(n, prefix="סעיף"):
    return [{"title": f"{prefix} {i + 1}", "body": f"תוכן {prefix} {i + 1}"} for i in range(n)]


GUARD_MSG = "הדרכת אתר נוצרת רק דרך תהליך ההדרכה"


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-if4-org-{tag}"
    proj = f"probe-if4-p1-{tag}"
    pm_id = f"probe-if4-pm-{tag}"       # project_manager — full safety writer
    out_id = f"probe-if4-out-{tag}"     # PM with NO project membership
    w1 = f"probe-if4-w1-{tag}"          # gets a signed induction
    w2 = f"probe-if4-w2-{tag}"          # no induction at all
    w3 = f"probe-if4-w3-{tag}"          # legacy UNSIGNED induction row

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": "+972507700001", "last_login_at": now_iso},
        {"id": out_id, "role": "project_manager", "full_name": "זר",
         "user_status": "active", "session_version": 0,
         "phone_e164": "+972507700002", "last_login_at": now_iso},
    ])
    await db.organization_memberships.insert_one(
        {"id": f"if4-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_one(
        {"id": f"if4-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"})
    await db.safety_workers.insert_many([
        {"id": w, "project_id": proj, "full_name": f"עובד {i}", "deletedAt": None,
         "created_at": now_iso}
        for i, w in enumerate([w1, w2, w3], start=1)
    ])
    # legacy UNSIGNED induction row for w3 (pre-guard data)
    legacy_id = f"if4-legacy-{tag}"
    await db.safety_trainings.insert_one({
        "id": legacy_id, "project_id": proj, "worker_id": w3,
        "training_type": INDUCTION_TRAINING_TYPE, "trained_at": now_iso,
        "expires_at": None, "worker_signature": None, "created_at": now_iso,
        "created_by": pm_id, "deletedAt": None, "deletedBy": None,
    })

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role="project_manager"):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    pm_h = h(pm_id)
    out_h = h(out_id)

    TMPL = f"/api/safety/{proj}/induction-template"
    CONDUCT = f"/api/safety/{proj}/induction/conduct"
    TRAININGS = f"/api/safety/{proj}/trainings"
    WORKERS = f"/api/safety/{proj}/workers"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
        # setup: template + one conducted (signed) induction for w1
        secs = sections(3, "בטיחות")
        r = await c.put(TMPL, json={"sections": secs}, headers=pm_h)
        assert r.status_code == 200, f"template save failed {r.status_code} {r.text[:200]}"
        exp_far = (date.today() + timedelta(days=300)).isoformat()
        r = await c.post(CONDUCT, data={
            "worker_id": w1, "language_choice": "he", "expires_at": exp_far,
            "signer_name": "עובד 1", "signature_type": "typed", "typed_name": "עובד 1",
        }, headers=pm_h)
        assert r.status_code == 201, f"conduct failed {r.status_code} {r.text[:200]}"
        ind1 = r.json()

        # ---------------- V1 — induction_valid_until on list_workers ----------------
        print("V1 — list_workers induction_valid_until")
        r = await c.get(WORKERS, headers=pm_h)
        items = {it["id"]: it for it in r.json().get("items", [])}
        record("V1a signed induction worker → induction_valid_until == expires_at",
               r.status_code == 200 and items.get(w1, {}).get("induction_valid_until") == exp_far,
               f"got={items.get(w1, {}).get('induction_valid_until')}")
        record("V1b worker without induction → null",
               w2 in items and items[w2].get("induction_valid_until") is None)
        record("V1c legacy UNSIGNED induction row does NOT count (w3 → null)",
               w3 in items and items[w3].get("induction_valid_until") is None)
        record("V1d PII posture unchanged — no id_number_hash in list rows",
               all("id_number_hash" not in it for it in items.values()))
        # max semantics: second, later conduct wins
        # induction-365-enforce: 400d would now (correctly) 422 — MAX semantics
        # only needs a LATER in-bounds date than exp_far (300d).
        exp_farther = (date.today() + timedelta(days=350)).isoformat()
        r = await c.post(CONDUCT, data={
            "worker_id": w1, "language_choice": "he", "expires_at": exp_farther,
            "signer_name": "עובד 1", "signature_type": "typed", "typed_name": "עובד 1",
        }, headers=pm_h)
        ind2 = r.json()
        r = await c.get(WORKERS, headers=pm_h)
        items = {it["id"]: it for it in r.json().get("items", [])}
        record("V1e MAX expires_at over multiple signed inductions",
               items.get(w1, {}).get("induction_valid_until") == exp_farther)

        # ---------------- V2 — born-signed guards ----------------
        print("V2 — born-signed enforcement")
        base = {"worker_id": w2, "trained_at": now_iso}
        r = await c.post(TRAININGS, json={**base, "training_type": INDUCTION_TRAINING_TYPE}, headers=pm_h)
        record("V2a create with induction type → 422 Hebrew guard",
               r.status_code == 422 and GUARD_MSG in str(r.json().get("detail")))
        r = await c.post(TRAININGS, json={**base, "training_type": f"  {INDUCTION_TRAINING_TYPE} "}, headers=pm_h)
        record("V2b padded type → 422 (trim applied)", r.status_code == 422)
        r = await c.post(TRAININGS, json={**base, "training_type": "עבודה בגובה"}, headers=pm_h)
        normal = r.json() if r.status_code == 201 else {}
        record("V2c other type → 201 unchanged", r.status_code == 201)
        r = await c.post(f"{TRAININGS}/{legacy_id}/signature",
                         data={"signer_name": "עובד 3", "signature_type": "typed", "typed_name": "עובד 3"},
                         headers=pm_h)
        record("V2d sign legacy unsigned induction → 422 guard",
               r.status_code == 422 and GUARD_MSG in str(r.json().get("detail")))
        r = await c.post(f"{TRAININGS}/{normal.get('id')}/signature",
                         data={"signer_name": "עובד 2", "signature_type": "typed", "typed_name": "עובד 2"},
                         headers=pm_h)
        record("V2e sign normal training → 200 works", r.status_code == 200,
               f"status={r.status_code} {r.text[:100]}")
        r = await c.patch(f"{TRAININGS}/{normal.get('id')}",
                          json={"training_type": INDUCTION_TRAINING_TYPE}, headers=pm_h)
        record("V2f PATCH rename TO induction type → 422", r.status_code == 422)
        r = await c.patch(f"{TRAININGS}/{legacy_id}",
                          json={"training_type": "עבודה בגובה"}, headers=pm_h)
        record("V2g PATCH rename FROM induction type → 422", r.status_code == 422)
        r = await c.patch(f"{TRAININGS}/{normal.get('id')}",
                          json={"instructor_name": "מדריך"}, headers=pm_h)
        record("V2h unrelated PATCH still 200", r.status_code == 200)

        # ---------------- V3 — evidence endpoint ----------------
        print("V3 — evidence endpoint")
        EV = f"/api/safety/{proj}/induction/evidence"
        r = await c.get(f"{EV}/{ind1['id']}", headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        snap = await db.induction_content_snapshots.find_one(
            {"id": ind1["worker_signature"]["snapshot_id"]}, {"_id": 0})
        record("V3a evidence 200: sections identical to the snapshot",
               r.status_code == 200 and j.get("sections") == (snap or {}).get("sections"),
               f"status={r.status_code}")
        record("V3b content_hash matches the signature's stored hash",
               j.get("content_hash") == ind1["worker_signature"]["content_hash"]
               and j.get("content_hash") == (snap or {}).get("content_hash"))
        record("V3c attestation + signer fields present and correct",
               heb(j.get("attestation_text"))
               and j.get("signer_name") == "עובד 1"
               and j.get("signature_type") == "typed"
               and j.get("typed_name") == "עובד 1"
               and j.get("language_read") == "he"
               and j.get("via_interpreter") is False)
        # interpreter case ("other")
        r = await c.post(CONDUCT, data={
            "worker_id": w2, "language_choice": "other", "worker_language": "רוסית",
            "interpreter_name": "מתורגמן דמו",
            "signer_name": "עובד 2", "signature_type": "typed", "typed_name": "עובד 2",
        }, headers=pm_h)
        ind_other = r.json() if r.status_code == 201 else {}
        r = await c.get(f"{EV}/{ind_other.get('id')}", headers=pm_h)
        jo = r.json() if r.status_code == 200 else {}
        record("V3d interpreter case: via_interpreter true, names/languages carried",
               r.status_code == 200 and jo.get("via_interpreter") is True
               and jo.get("interpreter_name") == "מתורגמן דמו"
               and jo.get("worker_language") == "רוסית"
               and "מתורגמן דמו" in str(jo.get("attestation_text")),
               f"status={r.status_code}")
        r = await c.get(f"{EV}/{normal.get('id')}", headers=pm_h)
        record("V3e non-induction training id → 404 Hebrew",
               r.status_code == 404 and heb(r.json().get("detail")))
        r = await c.get(f"{EV}/{legacy_id}", headers=pm_h)
        record("V3f unsigned induction → 404", r.status_code == 404)
        r = await c.get(f"{EV}/{ind1['id']}", headers=out_h)
        record("V3g no project access → 403", r.status_code == 403,
               f"status={r.status_code}")
        r = await c.get(f"{EV}/{ind1['id']}")
        record("V3h unauthenticated → 401", r.status_code == 401)

    # cleanup
    await db.organizations.delete_many({"id": org})
    await db.subscriptions.delete_many({"org_id": org})
    await db.users.delete_many({"id": {"$in": [pm_id, out_id]}})
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
