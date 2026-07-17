"""FUNCTIONAL probes for BATCH qrg-briefing-edit — org-editable visitor
briefing with signed-version integrity.

Same in-process harness as probe_safety_qrg_guest.py: REAL FastAPI app,
real local Mongo, real JWTs.

Covers:
  - GET default: v1 constant, is_custom=False, can_edit per role.
  - PUT (org_admin/PM) → version 2; second PUT → 3; audit rows written.
  - Public gate GET reflects override text + version.
  - Sign integrity: stale/missing briefing_version → 409, NOTHING written;
    correct version → 200 and signature records version+hash of signed text.
  - DELETE reset → back to v1 constant; DELETE again → 404.
  - Validation: <50 chars / >4000 chars → 422.
  - RBAC: contractor GET → 403; MT read OK but PUT/DELETE → 403.
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WHATSAPP_ENABLED"] = "false"

import io
import sys
import uuid
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def make_png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 30), "white").save(buf, format="PNG")
    return buf.getvalue()


CUSTOM_TEXT = (
    "תדריך בטיחות מותאם לארגון — גרסת בדיקה.\n"
    "1. חובה קסדה ונעלי בטיחות בכל שטח האתר.\n"
    "2. אין להסתובב ללא ליווי נציג האתר.\n"
    "בחתימתי אני מאשר/ת שקראתי והבנתי את ההוראות."
)


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.safety.guest import (
        GUEST_BRIEFING_TEXT_HE, GUEST_BRIEFING_VERSION,
    )

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    paid = (now + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-qb-org-{tag}"
    proj = f"probe-qb-p1-{tag}"
    pm_id = f"probe-qb-pm-{tag}"
    mt_id = f"probe-qb-mt-{tag}"
    con_id = f"probe-qb-con-{tag}"

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97250{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso},
        {"id": mt_id, "role": "management_team", "full_name": "צוות ניהול",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97253{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso},
        {"id": con_id, "role": "contractor", "full_name": "קבלן",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97252{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso},
    ])
    await db.organization_memberships.insert_one(
        {"id": f"qb-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_many([
        {"id": f"qb-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"qb-pm2-{tag}", "project_id": proj, "user_id": mt_id, "role": "management_team"},
        {"id": f"qb-pm3-{tag}", "project_id": proj, "user_id": con_id, "role": "contractor"},
    ])

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role="project_manager"):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    pm_h = h(pm_id)
    mt_h = h(mt_id, "management_team")
    con_h = h(con_id, "contractor")
    GB = f"/api/safety/{proj}/guest-briefing"
    GP = f"/api/safety/{proj}/guest-passes"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
        print("B1 — GET default")
        r = await c.get(GB, headers=pm_h)
        j = r.json()
        record("PM GET default → v1 constant, is_custom=False, can_edit=True",
               r.status_code == 200 and j.get("text") == GUEST_BRIEFING_TEXT_HE
               and j.get("version") == GUEST_BRIEFING_VERSION
               and j.get("is_custom") is False and j.get("can_edit") is True,
               f"{r.status_code} v={j.get('version')} custom={j.get('is_custom')} edit={j.get('can_edit')}")
        r = await c.get(GB, headers=mt_h)
        j = r.json()
        record("MT GET → 200 read-only (can_edit=False)",
               r.status_code == 200 and j.get("can_edit") is False, f"{r.status_code} {j.get('can_edit')}")
        r = await c.get(GB, headers=con_h)
        record("contractor GET → 403", r.status_code == 403, str(r.status_code))

        print("B2 — validation + RBAC on PUT/DELETE")
        r = await c.put(GB, headers=pm_h, json={"text": "קצר מדי"})
        record("PUT <50 chars → 422", r.status_code == 422, str(r.status_code))
        r = await c.put(GB, headers=pm_h, json={"text": "א" * 4001})
        record("PUT >4000 chars → 422", r.status_code == 422, str(r.status_code))
        r = await c.put(GB, headers=mt_h, json={"text": CUSTOM_TEXT})
        record("MT PUT → 403", r.status_code == 403, str(r.status_code))
        r = await c.delete(GB, headers=mt_h)
        record("MT DELETE → 403", r.status_code == 403, str(r.status_code))
        r = await c.delete(GB, headers=pm_h)
        record("DELETE with no override → 404", r.status_code == 404, str(r.status_code))

        print("B3 — PUT override → version 2, then 3")
        r = await c.put(GB, headers=pm_h, json={"text": CUSTOM_TEXT})
        j = r.json()
        record("PUT valid → 200 version=2 is_custom=True",
               r.status_code == 200 and j.get("version") == 2 and j.get("is_custom") is True
               and j.get("text") == CUSTOM_TEXT,
               f"{r.status_code} v={j.get('version')}")
        doc = await db.guest_briefing_texts.find_one({"org_id": org}, {"_id": 0})
        record("override doc stored (org_id, version=2, updated_by)",
               doc and doc.get("version") == 2 and doc.get("updated_by") == pm_id,
               str(doc and {k: doc.get(k) for k in ('version', 'updated_by')}))
        r = await c.put(GB, headers=pm_h, json={"text": CUSTOM_TEXT + " עדכון."})
        j = r.json()
        record("second PUT → version=3", r.status_code == 200 and j.get("version") == 3,
               f"{r.status_code} v={j.get('version')}")
        n_audit = await db.audit_events.count_documents(
            {"entity_id": org, "action": "guest_briefing_updated"})
        record("audit guest_briefing_updated ×2", n_audit == 2, f"n={n_audit}")

        print("B3b — concurrent PUTs → unique monotonic versions (atomic $inc)")
        base = CUSTOM_TEXT + " מקבילי "
        rs = await asyncio.gather(*[
            c.put(GB, headers=pm_h, json={"text": base + str(i)}) for i in range(5)
        ])
        versions = sorted(r.json().get("version") for r in rs)
        record("5 parallel PUTs → 5 UNIQUE versions 4..8",
               all(r.status_code == 200 for r in rs) and versions == [4, 5, 6, 7, 8],
               f"versions={versions}")
        doc = await db.guest_briefing_texts.find_one({"org_id": org}, {"_id": 0, "version": 1})
        record("stored doc at version 8", doc and doc.get("version") == 8, str(doc))
        # bring back to a KNOWN state (version 9) for the B4 flow below
        r = await c.put(GB, headers=pm_h, json={"text": CUSTOM_TEXT + " עדכון."})
        cur_version = r.json().get("version")
        record("re-save → version 9", cur_version == 9, f"v={cur_version}")

        print("B4 — public gate reflects override; sign integrity")
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "אורח תדריך", "guest_company": "יועץ"})
        token = r.json().get("token", "")
        pass_id = r.json().get("id")
        r = await c.get(f"/api/gate/{token}")
        j = r.json()
        cur_text = CUSTOM_TEXT + " עדכון."
        record("public GET → override text + CURRENT version=9",
               j.get("state") == "guest_briefing" and j.get("briefing_text") == cur_text
               and j.get("briefing_version") == 9,
               f"v={j.get('briefing_version')}")

        png = make_png()
        r = await c.post(f"/api/gate/{token}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "אורח תדריך", "briefing_version": "1"})
        record("sign with STALE version → 409 Hebrew",
               r.status_code == 409 and "עודכן" in (r.json().get("detail") or ""),
               f"{r.status_code} {r.json()}")
        r = await c.post(f"/api/gate/{token}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "אורח תדריך"})
        record("sign with MISSING version → 409", r.status_code == 409, str(r.status_code))
        gp_doc = await db.guest_entry_passes.find_one({"id": pass_id}, {"_id": 0})
        record("after 409s: NOTHING written (still unsigned)",
               gp_doc["briefing"]["signed"] is False
               and gp_doc["briefing"]["signature_ref"] is None,
               str(gp_doc["briefing"]))

        r = await c.post(f"/api/gate/{token}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "אורח תדריך", "briefing_version": "9"})
        record("sign with CURRENT version → 200 green",
               r.status_code == 200 and r.json().get("state") == "green",
               f"{r.status_code} {r.json()}")
        gp_doc = await db.guest_entry_passes.find_one({"id": pass_id}, {"_id": 0})
        exp_hash = hashlib.sha256(cur_text.encode("utf-8")).hexdigest()[:12]
        record("signature records version=9 + hash of SIGNED text",
               gp_doc["briefing"]["briefing_version"] == 9
               and gp_doc["briefing"]["briefing_hash"] == exp_hash,
               str({k: gp_doc['briefing'].get(k) for k in ('briefing_version', 'briefing_hash')}))

        print("B5 — reset to default")
        r = await c.delete(GB, headers=pm_h)
        j = r.json()
        record("DELETE → 200 back to v1 default",
               r.status_code == 200 and j.get("text") == GUEST_BRIEFING_TEXT_HE
               and j.get("version") == GUEST_BRIEFING_VERSION and j.get("is_custom") is False,
               f"{r.status_code} v={j.get('version')}")
        n_reset = await db.audit_events.count_documents(
            {"entity_id": org, "action": "guest_briefing_reset"})
        record("audit guest_briefing_reset ×1", n_reset == 1, f"n={n_reset}")
        r = await c.delete(GB, headers=pm_h)
        record("second DELETE → 404", r.status_code == 404, str(r.status_code))

        # New pass after reset sees v1 again; signing with v1 works.
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "אורח שני", "guest_company": "מפקח"})
        tok2 = r.json().get("token", "")
        r = await c.get(f"/api/gate/{tok2}")
        j = r.json()
        record("after reset: public GET → v1 constant",
               j.get("briefing_text") == GUEST_BRIEFING_TEXT_HE and j.get("briefing_version") == 1,
               f"v={j.get('briefing_version')}")
        r = await c.post(f"/api/gate/{tok2}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "אורח שני", "briefing_version": "1"})
        record("after reset: sign with v1 → 200", r.status_code == 200, str(r.status_code))

    # cleanup
    await db.organizations.delete_many({"id": org})
    await db.subscriptions.delete_many({"org_id": org})
    await db.users.delete_many({"id": {"$in": [pm_id, mt_id, con_id]}})
    await db.organization_memberships.delete_many({"org_id": org})
    await db.projects.delete_many({"id": proj})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.guest_entry_passes.delete_many({"project_id": proj})
    await db.guest_briefing_texts.delete_many({"org_id": org})
    await db.gate_scan_log.delete_many({"project_id": proj})
    await db.audit_events.delete_many({"entity_id": org})

    passed = sum(1 for _, p in RESULTS if p)
    print(f"\n{'='*60}\nTOTAL: {passed}/{len(RESULTS)} passed")
    if passed < len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
