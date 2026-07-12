"""FUNCTIONAL probes for BATCH safety-ind1 (site-induction org templates).

Same in-process harness as probe_safety_w1_alerts.py: REAL FastAPI app
(httpx ASGITransport), ENABLE_SAFETY_MODULE, REAL local Mongo,
FILES_STORAGE_BACKEND=local, REAL JWTs. No WhatsApp anywhere in this batch —
creds blanked anyway as a hard guard.

Covers (plan V-map; V7 craco/greps and V8 FE-condition run separately):
  V1  owner PUT → version 1; second PUT → 2; GET round-trip equality
  V2  RBAC: owner+org_admin PUT 200; billing_admin PUT 403 (Zahi addition);
      project_manager PUT 403 / GET 200 (can_edit=false); management_team
      GET 200; contractor GET 403; unauthenticated 401; ORG ISOLATION with
      two orgs (org-B GET null → PUT separate doc; org-A untouched)
  V3  422s (Hebrew): empty list · 201 sections · empty title · whitespace
      title · empty body · body 5001 chars
  V4  Concurrency: two rapid PUTs same org → ONE doc, version +2
  V5  Hash: identical → identical; key-order variants → identical;
      single-char change → different. Snapshot unique index EXISTS, 0 docs
  V6  Starter returned as DRAFT (12 sections), returning saves NOTHING
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local — repl env may carry Atlas
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
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def sections(n, prefix="סעיף"):
    return [{"title": f"{prefix} {i + 1}", "body": f"תוכן {prefix} {i + 1}"} for i in range(n)]


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import (
        induction_content_hash, STARTER_INDUCTION_SECTIONS_HE,
    )

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org_a = f"probe-ind-orgA-{tag}"
    org_b = f"probe-ind-orgB-{tag}"
    own_id = f"probe-ind-own-{tag}"       # org-A owner (organizations.owner_user_id)
    adm_id = f"probe-ind-adm-{tag}"       # org-A org_admin, global viewer
    bill_id = f"probe-ind-bill-{tag}"     # org-A billing_admin — PUT must 403
    pm_id = f"probe-ind-pm-{tag}"         # org-A member, global project_manager
    mt_id = f"probe-ind-mt-{tag}"         # org-A member, global management_team
    con_id = f"probe-ind-con-{tag}"       # org-A member, global contractor
    own2_id = f"probe-ind-own2-{tag}"     # org-B owner

    # ---------------- seed ----------------
    await db.organizations.insert_many([
        {"id": org_a, "name": f"ארגון א {tag}", "owner_user_id": own_id},
        {"id": org_b, "name": f"ארגון ב {tag}", "owner_user_id": own2_id},
    ])
    await db.subscriptions.insert_many([
        {"org_id": org_a, "status": "active", "paid_until": paid},
        {"org_id": org_b, "status": "active", "paid_until": paid},
    ])
    users = [
        (own_id, "owner"), (adm_id, "viewer"), (bill_id, "viewer"),
        (pm_id, "project_manager"), (mt_id, "management_team"),
        (con_id, "contractor"), (own2_id, "owner"),
    ]
    await db.users.insert_many([
        {"id": uid, "role": role, "full_name": f"משתמש {role}", "user_status": "active",
         "session_version": 0, "phone_e164": f"+9725055{i:05d}", "last_login_at": now_iso}
        for i, (uid, role) in enumerate(users)
    ])
    await db.organization_memberships.insert_many([
        {"id": f"ind-om1-{tag}", "org_id": org_a, "user_id": own_id, "role": "owner"},
        {"id": f"ind-om2-{tag}", "org_id": org_a, "user_id": adm_id, "role": "org_admin"},
        {"id": f"ind-om3-{tag}", "org_id": org_a, "user_id": bill_id, "role": "billing_admin"},
        {"id": f"ind-om4-{tag}", "org_id": org_a, "user_id": pm_id, "role": "member"},
        {"id": f"ind-om5-{tag}", "org_id": org_a, "user_id": mt_id, "role": "member"},
        {"id": f"ind-om6-{tag}", "org_id": org_a, "user_id": con_id, "role": "member"},
        {"id": f"ind-om7-{tag}", "org_id": org_b, "user_id": own2_id, "role": "owner"},
    ])

    # ensure fresh index state (server startup normally does this)
    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    hdrs = {uid: h(uid, role) for uid, role in users}
    URL = "/api/safety/induction-template"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:

        # ---------------- V1 — versioned save + round-trip ----------------
        print("V1 — owner PUT → v1; second PUT → v2; GET round-trip")
        secs1 = sections(3, "בטיחות")
        r = await c.put(URL, json={"sections": secs1}, headers=hdrs[own_id])
        record("V1a owner first PUT 200 → version 1",
               r.status_code == 200 and r.json()["template"]["version"] == 1,
               f"status={r.status_code} version={r.json().get('template', {}).get('version')}")
        secs2 = sections(4, "עדכון")
        r = await c.put(URL, json={"sections": secs2}, headers=hdrs[own_id])
        record("V1b second PUT → version 2",
               r.status_code == 200 and r.json()["template"]["version"] == 2)
        r = await c.get(URL, headers=hdrs[own_id])
        got = r.json()
        record("V1c GET round-trip equality on languages.he.sections",
               r.status_code == 200 and got["template"]["languages"]["he"]["sections"] == secs2
               and got["can_edit"] is True)
        audit = await db.audit_events.find_one({"action": "induction_template_saved",
                                                "payload.org_id": org_a, "payload.version": 2})
        record("V1d audit induction_template_saved logged (org, version, count)",
               bool(audit) and audit["payload"]["sections_count"] == 4)

        # ---------------- V2 — RBAC + org isolation ----------------
        print("V2 — RBAC + org isolation")
        r = await c.put(URL, json={"sections": secs2}, headers=hdrs[adm_id])
        record("V2a org_admin PUT 200", r.status_code == 200)
        r = await c.put(URL, json={"sections": secs2}, headers=hdrs[bill_id])
        record("V2b billing_admin PUT 403 (Zahi addition)", r.status_code == 403)
        r = await c.put(URL, json={"sections": secs2}, headers=hdrs[pm_id])
        record("V2c project_manager PUT 403", r.status_code == 403)
        r = await c.get(URL, headers=hdrs[pm_id])
        record("V2d project_manager GET 200, can_edit=false, sees org template",
               r.status_code == 200 and r.json()["can_edit"] is False
               and r.json()["template"] is not None)
        r = await c.get(URL, headers=hdrs[mt_id])
        record("V2e management_team GET 200", r.status_code == 200)
        r = await c.get(URL, headers=hdrs[con_id])
        record("V2f contractor GET 403", r.status_code == 403)
        r = await c.get(URL)
        record("V2g unauthenticated 401", r.status_code == 401, f"status={r.status_code}")
        # org isolation
        r = await c.get(URL, headers=hdrs[own2_id])
        record("V2h org-B GET → template null (isolation)",
               r.status_code == 200 and r.json()["template"] is None
               and r.json()["can_edit"] is True)
        secs_b = sections(2, "ארגון-ב")
        r = await c.put(URL, json={"sections": secs_b}, headers=hdrs[own2_id])
        b_doc = r.json()["template"]
        a_doc = await db.induction_templates.find_one({"org_id": org_a}, {"_id": 0})
        record("V2i org-B PUT → separate doc v1; org-A untouched (v3)",
               r.status_code == 200 and b_doc["org_id"] == org_b and b_doc["version"] == 1
               and a_doc["version"] == 3 and a_doc["id"] != b_doc["id"])

        # ---------------- V3 — validation 422s ----------------
        print("V3 — Hebrew 422s")
        cases = [
            ("V3a empty list", {"sections": []}),
            ("V3b 201 sections", {"sections": sections(201)}),
            ("V3c empty title", {"sections": [{"title": "", "body": "תוכן"}]}),
            ("V3d whitespace title", {"sections": [{"title": "   ", "body": "תוכן"}]}),
            ("V3e empty body", {"sections": [{"title": "כותרת", "body": ""}]}),
            ("V3f body 5001 chars", {"sections": [{"title": "כותרת", "body": "א" * 5001}]}),
        ]
        for name, payload in cases:
            r = await c.put(URL, json=payload, headers=hdrs[own_id])
            detail = r.json().get("detail", "")
            has_hebrew = any("\u0590" <= ch <= "\u05EA" for ch in str(detail))
            record(f"{name} → 422 Hebrew", r.status_code == 422 and has_hebrew,
                   f"status={r.status_code} detail={str(detail)[:60]}")
        a_doc = await db.induction_templates.find_one({"org_id": org_a}, {"_id": 0})
        record("V3g rejected PUTs did NOT bump version (still 3)", a_doc["version"] == 3)

        # ---------------- V4 — concurrency ----------------
        print("V4 — two rapid PUTs, same org")
        before = a_doc["version"]
        r1, r2 = await asyncio.gather(
            c.put(URL, json={"sections": sections(5, "מרוץ-א")}, headers=hdrs[own_id]),
            c.put(URL, json={"sections": sections(5, "מרוץ-ב")}, headers=hdrs[adm_id]),
        )
        count = await db.induction_templates.count_documents({"org_id": org_a})
        after = (await db.induction_templates.find_one({"org_id": org_a}))["version"]
        record("V4a both PUTs 200, ONE doc, version +2",
               r1.status_code == 200 and r2.status_code == 200
               and count == 1 and after == before + 2,
               f"count={count} version {before}→{after}")

        # ---------------- V5 — canonical hash + snapshot infra ----------------
        print("V5 — induction_content_hash determinism + snapshot index")
        s_base = [{"title": "א", "body": "ב"}, {"title": "ג", "body": "ד"}]
        s_keyorder = [{"body": "ב", "title": "א"}, {"body": "ד", "title": "ג"}]
        h1 = induction_content_hash(s_base, "טקסט משפטי")
        h2 = induction_content_hash(s_base, "טקסט משפטי")
        h3 = induction_content_hash(s_keyorder, "טקסט משפטי")
        h4 = induction_content_hash(s_base, "טקסט משפטי.")
        h5 = induction_content_hash([{"title": "א", "body": "ב!"}, {"title": "ג", "body": "ד"}], "טקסט משפטי")
        record("V5a identical → identical", h1 == h2 and len(h1) == 64)
        record("V5b key-order variant → identical", h1 == h3)
        record("V5c single-char changes → different", h1 != h4 and h1 != h5 and h4 != h5)
        idx = await db.induction_content_snapshots.index_information()
        uidx = idx.get("uidx_ics_org_version_lang")
        snap_count = await db.induction_content_snapshots.count_documents({})
        record("V5d snapshot unique index exists, 0 docs",
               bool(uidx) and uidx.get("unique") is True and snap_count == 0,
               f"index={bool(uidx)} docs={snap_count}")
        tidx = (await db.induction_templates.index_information()).get("uidx_it_org")
        record("V5e induction_templates UNIQUE(org_id) index exists",
               bool(tidx) and tidx.get("unique") is True)

        # ---------------- V6 — starter is a DRAFT, returning ≠ saving ----------------
        print("V6 — starter draft")
        b_before = await db.induction_templates.find_one({"org_id": org_b})
        r = await c.get(f"{URL}/starter", headers=hdrs[own2_id])
        data = r.json()
        b_after = await db.induction_templates.find_one({"org_id": org_b})
        record("V6a starter 200, draft:true, 12 sections",
               r.status_code == 200 and data.get("draft") is True
               and len(data.get("sections", [])) == len(STARTER_INDUCTION_SECTIONS_HE) == 12)
        record("V6b every starter section has Hebrew title+body",
               all(s["title"].strip() and s["body"].strip()
                   and any("\u0590" <= ch <= "\u05EA" for ch in s["title"])
                   for s in data.get("sections", [])))
        record("V6c returning starter saved NOTHING (org-B doc unchanged)",
               b_before == b_after)
        r = await c.get(f"{URL}/starter", headers=hdrs[con_id])
        record("V6d contractor starter GET 403", r.status_code == 403)

    # ---------------- cleanup ----------------
    await db.organizations.delete_many({"id": {"$in": [org_a, org_b]}})
    await db.subscriptions.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.users.delete_many({"id": {"$in": [u for u, _ in users]}})
    await db.organization_memberships.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.induction_templates.delete_many({"org_id": {"$in": [org_a, org_b]}})
    await db.audit_events.delete_many({"payload.org_id": {"$in": [org_a, org_b]}})

    passed = sum(1 for _, p, _ in RESULTS if p)
    print(f"\n===== {passed}/{len(RESULTS)} PASSED =====")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
