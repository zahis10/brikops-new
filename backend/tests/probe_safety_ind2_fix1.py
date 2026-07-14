"""FUNCTIONAL probes for BATCH safety-ind2-fix1 — ONE org key for the
induction feature (project-scoped editor pair).

Same in-process harness as probe_safety_ind2.py: REAL FastAPI app,
real local Mongo, real JWTs.

Covers:
  V1  THE BUG — cross-org demo pattern: editor user's own org (via
      get_user_org) is org A, but the PROJECT belongs to org B.
      BEFORE: PUT via the org-level route saves under org A → conduct
      content GET 404 (the staging symptom). AFTER: PUT via the NEW
      project-scoped route saves under org B → conduct content 200 with
      the SAME sections, and conduct itself succeeds end-to-end.
  V2  can_edit matrix on the project-scoped GET: project-org owner true;
      project-org org_admin true; billing_admin false; PM (plain member)
      false; contractor 403; PUT 403 Hebrew for non-managers; owner with
      NO project membership can still GET (can_edit path) and PUT.
  V3  Parity: project-scoped PUT validation (empty sections 422, long
      title 422) + atomic $inc version + audit event; org-level endpoints
      still behave (probe_safety_ind1 run separately).
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
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def heb(s):
    return any("\u0590" <= ch <= "\u05EA" for ch in str(s))


def sections(n, prefix="סעיף"):
    return [{"title": f"{prefix} {i + 1}", "body": f"תוכן {prefix} {i + 1}"} for i in range(n)]


async def main():
    from server import app
    from contractor_ops.router import _create_token

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org_a = f"probe-if1-orgA-{tag}"   # editor user's OWN org (get_user_org)
    org_b = f"probe-if1-orgB-{tag}"   # the PROJECT's org
    proj = f"probe-if1-p1-{tag}"      # belongs to org B

    ed_id = f"probe-if1-ed-{tag}"      # PM: org_admin in A, owner of B — THE bug persona
    ownb_id = f"probe-if1-ownb-{tag}"  # plain owner of org B, NO project membership
    adm_id = f"probe-if1-adm-{tag}"    # org_admin in org B
    bil_id = f"probe-if1-bil-{tag}"    # billing_admin in org B
    pm_id = f"probe-if1-pm-{tag}"      # PM, plain member of B + project member
    con_id = f"probe-if1-con-{tag}"    # contractor, project member
    sup_id = f"probe-if1-sup-{tag}"    # platform super_admin, NO memberships at all
    w1 = f"probe-if1-w1-{tag}"

    await db.organizations.insert_many([
        {"id": org_a, "name": f"ארגון א {tag}", "owner_user_id": f"nobody-{tag}"},
        {"id": org_b, "name": f"ארגון ב {tag}", "owner_user_id": ownb_id},
    ])
    await db.subscriptions.insert_many([
        {"org_id": org_a, "status": "active", "paid_until": paid},
        {"org_id": org_b, "status": "active", "paid_until": paid},
    ])
    users = [
        (ed_id, "project_manager"), (ownb_id, "project_manager"),
        (adm_id, "project_manager"), (bil_id, "project_manager"),
        (pm_id, "project_manager"), (con_id, "contractor"),
    ]
    await db.users.insert_many([
        {"id": uid, "role": role, "full_name": f"משתמש {i}", "user_status": "active",
         "session_version": 0, "phone_e164": f"+9725077{i:05d}", "last_login_at": now_iso}
        for i, (uid, role) in enumerate(users)
    ])
    await db.users.insert_one(
        {"id": sup_id, "role": "project_manager", "platform_role": "super_admin",
         "full_name": "אדמין פלטפורמה", "user_status": "active", "session_version": 0,
         "phone_e164": "+97250799999", "last_login_at": now_iso})
    # ed: FIRST membership row points at org A → get_user_org resolves A.
    # ed is ALSO org_admin of B — but the old org-level route never sees B.
    await db.organization_memberships.insert_many([
        {"id": f"if1-om1-{tag}", "org_id": org_a, "user_id": ed_id, "role": "org_admin"},
        {"id": f"if1-om2-{tag}", "org_id": org_b, "user_id": ed_id, "role": "org_admin"},
        {"id": f"if1-om3-{tag}", "org_id": org_b, "user_id": adm_id, "role": "org_admin"},
        {"id": f"if1-om4-{tag}", "org_id": org_b, "user_id": bil_id, "role": "billing_admin"},
        {"id": f"if1-om5-{tag}", "org_id": org_b, "user_id": pm_id, "role": "member"},
        {"id": f"if1-om6-{tag}", "org_id": org_b, "user_id": con_id, "role": "member"},
    ])
    await db.projects.insert_one(
        {"id": proj, "org_id": org_b, "name": f"פרויקט הדמו {tag}", "status": "active"})
    await db.project_memberships.insert_many([
        {"id": f"if1-pm1-{tag}", "project_id": proj, "user_id": ed_id, "role": "project_manager"},
        {"id": f"if1-pm2-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"if1-pm3-{tag}", "project_id": proj, "user_id": con_id, "role": "contractor"},
        {"id": f"if1-pm4-{tag}", "project_id": proj, "user_id": adm_id, "role": "project_manager"},
        {"id": f"if1-pm5-{tag}", "project_id": proj, "user_id": bil_id, "role": "project_manager"},
    ])
    await db.safety_workers.insert_one(
        {"id": w1, "project_id": proj, "full_name": "עובד דמו", "deletedAt": None,
         "created_at": now_iso})

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    hdrs = {uid: h(uid, role) for uid, role in users}

    OLD = "/api/safety/induction-template"
    NEW = f"/api/safety/{proj}/induction-template"
    CONTENT = f"/api/safety/{proj}/induction/content"
    CONDUCT = f"/api/safety/{proj}/induction/conduct"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:

        # ---------------- V1 — the bug: BEFORE then AFTER ----------------
        print("V1 — cross-org bug: BEFORE (org-level save) vs AFTER (project-scoped)")
        secs_before = sections(2, "לפני")
        r = await c.put(OLD, json={"sections": secs_before}, headers=hdrs[ed_id])
        saved_a = await db.induction_templates.find_one({"org_id": org_a})
        saved_b = await db.induction_templates.find_one({"org_id": org_b})
        record("V1a BEFORE: org-level PUT saved under the USER's org (A), NOT the project's (B)",
               r.status_code == 200 and bool(saved_a) and not saved_b)
        r = await c.get(CONTENT, headers=hdrs[ed_id])
        record("V1b BEFORE: conduct content GET → 404 despite the save (THE staging symptom)",
               r.status_code == 404)

        secs_after = sections(3, "אחרי")
        r = await c.put(NEW, json={"sections": secs_after}, headers=hdrs[ed_id])
        j = r.json() if r.status_code == 200 else {}
        saved_b = await db.induction_templates.find_one({"org_id": org_b}, {"_id": 0})
        record("V1c AFTER: project-scoped PUT 200, saved under the PROJECT's org (B), can_edit true",
               r.status_code == 200 and bool(saved_b)
               and j.get("can_edit") is True
               and (j.get("template") or {}).get("org_id") == org_b,
               f"status={r.status_code}")
        r = await c.get(CONTENT, headers=hdrs[ed_id])
        jc = r.json() if r.status_code == 200 else {}
        record("V1d AFTER: conduct content GET 200 with the SAME sections (ONE doc)",
               r.status_code == 200 and jc.get("sections") == secs_after)
        r = await c.post(CONDUCT, data={"worker_id": w1, "language_choice": "he",
                                        "signer_name": "עובד דמו",
                                        "signature_type": "typed", "typed_name": "עובד דמו"},
                         headers=hdrs[ed_id])
        record("V1e AFTER: conduct ceremony end-to-end 201", r.status_code == 201,
               f"status={r.status_code} {r.text[:100]}")

        # ---------------- V2 — can_edit matrix ----------------
        print("V2 — can_edit matrix + gates on the project-scoped pair")
        r = await c.get(NEW, headers=hdrs[ownb_id])
        record("V2a project-org OWNER (no project membership) GET 200 can_edit=true",
               r.status_code == 200 and r.json().get("can_edit") is True)
        r = await c.put(NEW, json={"sections": sections(1, "בעלים")}, headers=hdrs[ownb_id])
        record("V2b owner PUT 200 (no project membership needed)", r.status_code == 200)
        r = await c.get(NEW, headers=hdrs[adm_id])
        record("V2c org_admin GET can_edit=true",
               r.status_code == 200 and r.json().get("can_edit") is True)
        r = await c.get(NEW, headers=hdrs[bil_id])
        record("V2d billing_admin GET can_edit=false (D1 exclusion)",
               r.status_code == 200 and r.json().get("can_edit") is False)
        r = await c.get(NEW, headers=hdrs[pm_id])
        record("V2e plain PM member GET 200 can_edit=false",
               r.status_code == 200 and r.json().get("can_edit") is False)
        r = await c.put(NEW, json={"sections": sections(1, "פורץ")}, headers=hdrs[pm_id])
        record("V2f plain PM PUT → 403 עברית",
               r.status_code == 403 and heb(r.json().get("detail")))
        r = await c.put(NEW, json={"sections": sections(1, "חיוב")}, headers=hdrs[bil_id])
        record("V2g billing_admin PUT → 403", r.status_code == 403)
        r = await c.get(NEW, headers=hdrs[con_id])
        record("V2h contractor GET → 403", r.status_code == 403)
        r = await c.get(NEW)
        record("V2i unauthenticated → 401", r.status_code == 401)
        r = await c.get("/api/safety/no-such-project/induction-template",
                        headers=hdrs[ownb_id])
        record("V2j unknown project → 403/404 (no data leak)",
               r.status_code in (403, 404), f"status={r.status_code}")

        # ---------------- V3 — parity ----------------
        print("V3 — validation + version parity on the new PUT")
        r = await c.put(NEW, json={"sections": []}, headers=hdrs[ownb_id])
        record("V3a empty sections → 422 עברית",
               r.status_code == 422 and heb(r.json().get("detail")))
        r = await c.put(NEW, json={"sections": [{"title": "א" * 201, "body": "ב"}]},
                        headers=hdrs[ownb_id])
        record("V3b title > 200 → 422", r.status_code == 422)
        doc1 = await db.induction_templates.find_one({"org_id": org_b}, {"_id": 0})
        r = await c.put(NEW, json={"sections": sections(2, "גרסה")}, headers=hdrs[ownb_id])
        doc2 = await db.induction_templates.find_one({"org_id": org_b}, {"_id": 0})
        record("V3c $inc version (+1), same doc id",
               r.status_code == 200 and doc2["version"] == doc1["version"] + 1
               and doc2["id"] == doc1["id"])
        audit = await db.audit_events.find_one(
            {"action": "induction_template_saved", "payload.org_id": org_b})
        record("V3d audit induction_template_saved under org B", bool(audit))

        # ---------------- V4 — fix2: super_admin bypass ----------------
        print("V4 — fix2: super_admin bypass (house access rule)")
        sup_h = h(sup_id, "project_manager")
        r = await c.get(NEW, headers=sup_h)
        record("V4a super_admin (no memberships) GET 200 can_edit=true",
               r.status_code == 200 and r.json().get("can_edit") is True,
               f"status={r.status_code}")
        secs_sup = sections(2, "אדמין")
        r = await c.put(NEW, json={"sections": secs_sup}, headers=sup_h)
        doc_sup = await db.induction_templates.find_one({"org_id": org_b}, {"_id": 0})
        record("V4b super_admin PUT 200, saved under the PROJECT's org (B)",
               r.status_code == 200 and doc_sup
               and doc_sup["languages"]["he"]["sections"] == secs_sup,
               f"status={r.status_code}")
        r = await c.get(CONTENT, headers=hdrs[ed_id])
        record("V4c conduct content returns the super_admin-saved sections (same key)",
               r.status_code == 200 and r.json().get("sections") == secs_sup)
        r = await c.get(NEW, headers=hdrs[bil_id])
        record("V4d non-admin matrix unchanged: billing_admin still can_edit=false",
               r.status_code == 200 and r.json().get("can_edit") is False)
        r = await c.get("/api/safety/no-such-project/induction-template", headers=sup_h)
        record("V4e super_admin on unknown project → 403/404 (contract locked)",
               r.status_code in (403, 404), f"status={r.status_code}")

    # cleanup
    await db.organizations.delete_many({"id": {"$in": [org_a, org_b]}})
    await db.subscriptions.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.users.delete_many({"id": {"$in": [u for u, _ in users] + [sup_id]}})
    await db.organization_memberships.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.projects.delete_many({"id": proj})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.safety_workers.delete_many({"project_id": proj})
    await db.safety_trainings.delete_many({"project_id": proj})
    await db.induction_templates.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.induction_content_snapshots.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.audit_events.delete_many({"payload.org_id": {"$in": [org_a, org_b]}})
    await db.audit_events.delete_many({"payload.project_id": proj})

    passed = sum(1 for _, p, _ in RESULTS if p)
    print(f"\n===== {passed}/{len(RESULTS)} PASSED =====")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
