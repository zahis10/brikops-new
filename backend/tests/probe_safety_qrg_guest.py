"""FUNCTIONAL probes for BATCH qrg-guest — one-day guest entry passes.

Same in-process harness as probe_safety_qrg1_fix1.py: REAL FastAPI app,
real local Mongo, real JWTs.

Covers the spec's V1 list:
  - issue pass (SAFETY_WRITERS) → 201, unsigned, token ≥32 chars, qr stored;
    contractor issuing → 403; bad date / empty name → 422.
  - public GET before sign → guest_briefing with name+company+briefing text,
    NO phone/id/signature fields (negative assertions).
  - public POST sign: valid PNG within cap → 200 signed; GET same day →
    green guest; second sign → 409; valid_on tomorrow → red guest_date;
    after revoke → neutral invalid.
  - security: >600KB → 422; non-PNG bytes → 422; unknown token → 404
    neutral; NO signature_ref in any PUBLIC response.
  - guest scans logged; list_gate_scans resolves guest names + tags rows;
    worker rows unchanged (byte-compat) and filters/summary still work.
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
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def make_png(size=None) -> bytes:
    """A real minimal PNG; optionally pad inside a private chunk to reach size."""
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (60, 30), "white").save(buf, format="PNG")
    png = buf.getvalue()
    if size and size > len(png):
        png = png + b"\x00" * (size - len(png))  # trailing junk keeps magic bytes
    return png


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.utils.timezone import israel_today

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    paid = (now + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-qg-org-{tag}"
    proj = f"probe-qg-p1-{tag}"
    pm_id = f"probe-qg-pm-{tag}"
    con_id = f"probe-qg-con-{tag}"

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
        {"id": f"qg-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_many([
        {"id": f"qg-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"qg-pm2-{tag}", "project_id": proj, "user_id": con_id, "role": "contractor"},
    ])
    # A worker + one worker scan row for byte-compat checks in the scan list.
    w1 = f"qg-w1-{tag}"
    await db.safety_workers.insert_one(
        {"id": w1, "project_id": proj, "full_name": "עובד אחד",
         "deletedAt": None, "created_at": now_iso})
    await db.gate_scan_log.insert_one(
        {"id": f"qg-s1-{tag}", "project_id": proj, "worker_id": w1,
         "result": "green", "ts": now_iso, "reasons": []})

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role="project_manager"):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    pm_h = h(pm_id)
    con_h = h(con_id, "contractor")
    GP = f"/api/safety/{proj}/guest-passes"
    today = israel_today()
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=2)).date().isoformat()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
        print("V1 — issue (authed)")
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "אורח בדיקה", "guest_company": "אדריכל"})
        j = r.json() if r.status_code == 201 else {}
        token = j.get("token", "")
        pass_id = j.get("id")
        record("issue → 201, token ≥32, valid_on=today(IL), qr url",
               r.status_code == 201 and len(token) >= 32 and j.get("valid_on") == today
               and j.get("qr_display_url"),
               f"{r.status_code} valid_on={j.get('valid_on')} tok_len={len(token)}")
        gp_doc = await db.guest_entry_passes.find_one({"id": pass_id}, {"_id": 0})
        record("pass stored unsigned + qr_ref",
               gp_doc and gp_doc["briefing"]["signed"] is False and gp_doc.get("qr_ref"),
               f"briefing={gp_doc and gp_doc.get('briefing')}")

        r = await c.post(GP, headers=con_h, json={
            "guest_name": "אורח", "guest_company": "חברה"})
        record("contractor issuing → 403", r.status_code == 403, str(r.status_code))
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "א", "guest_company": "חברה"})
        record("1-char name → 422", r.status_code == 422, str(r.status_code))
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "אורח", "guest_company": "חברה", "valid_on": "17/07/2026"})
        record("bad date → 422", r.status_code == 422, str(r.status_code))

        print("V1 — public GET before sign")
        r = await c.get(f"/api/gate/{token}")
        j = r.json()
        record("GET unsigned → guest_briefing + name/company/briefing",
               r.status_code == 200 and j.get("state") == "guest_briefing"
               and j.get("guest_name") == "אורח בדיקה" and j.get("guest_company") == "אדריכל"
               and "תדריך בטיחות למבקרים" in (j.get("briefing_text") or "")
               and j.get("briefing_version") == 1,
               f"{r.status_code} state={j.get('state')}")
        blob = str(j)
        record("no phone/id/signature fields in public payload",
               "phone" not in blob and "id_number" not in blob
               and "signature_ref" not in blob and "signature" not in blob,
               blob[:120])

        print("V1 — public sign")
        png = make_png()
        r = await c.post(f"/api/gate/{token}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "אורח בדיקה"})
        j = r.json()
        record("sign valid PNG → 200 green guest today",
               r.status_code == 200 and j.get("state") == "green"
               and j.get("reason") == "guest" and j.get("valid_on") == today,
               f"{r.status_code} {j}")
        record("sign response has NO signature_ref", "signature_ref" not in str(j))
        gp_doc = await db.guest_entry_passes.find_one({"id": pass_id}, {"_id": 0})
        b = gp_doc["briefing"]
        record("db: signed=true + signature_ref + version/hash set",
               b["signed"] is True and b["signature_ref"]
               and b["briefing_version"] == 1 and len(b["briefing_hash"]) == 12,
               f"{ {k: b[k] for k in ('signed', 'briefing_version', 'briefing_hash')} }")

        r = await c.get(f"/api/gate/{token}")
        j = r.json()
        record("GET after sign (same day) → green guest",
               j.get("state") == "green" and j.get("reason") == "guest"
               and j.get("guest_company") == "אדריכל", str(j))
        record("public green has NO signature_ref", "signature_ref" not in str(j))

        r = await c.post(f"/api/gate/{token}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "שוב"})
        record("second sign → 409 התדריך כבר נחתם",
               r.status_code == 409 and "כבר נחתם" in r.json().get("detail", ""),
               f"{r.status_code} {r.text[:80]}")

        print("V1 — wrong date / revoke / unknown")
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "אורח מחר", "guest_company": "יועץ", "valid_on": tomorrow})
        j2 = r.json()
        tok2, id2 = j2["token"], j2["id"]
        await c.post(f"/api/gate/{tok2}/guest-sign",
                     files={"signature_image": ("sig.png", png, "image/png")},
                     data={"signer_name": "אורח מחר"})
        r = await c.get(f"/api/gate/{tok2}")
        j = r.json()
        record("signed but valid_on future → red guest_date",
               j.get("state") == "red" and j.get("reason") == "guest_date"
               and j.get("valid_on") == tomorrow, str(j))

        r = await c.post(f"{GP}/{id2}/revoke", headers=pm_h)
        record("revoke → 200 status=revoked",
               r.status_code == 200 and r.json().get("status") == "revoked", str(r.status_code))
        r = await c.get(f"/api/gate/{tok2}")
        record("GET after revoke → neutral invalid",
               r.json() == {"state": "invalid"}, r.text[:80])
        r = await c.post(f"/api/gate/{tok2}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "x"})
        record("sign on revoked → 404 neutral", r.status_code == 404, str(r.status_code))

        r = await c.post(f"/api/gate/{'x'*40}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "x"})
        record("sign on unknown token → 404 neutral", r.status_code == 404, str(r.status_code))

        print("V1 — upload security")
        r = await c.post(GP, headers=pm_h, json={
            "guest_name": "אורח ג", "guest_company": "חברה"})
        tok3 = r.json()["token"]
        big = make_png(size=600 * 1024 + 100)
        r = await c.post(f"/api/gate/{tok3}/guest-sign",
                         files={"signature_image": ("sig.png", big, "image/png")},
                         data={"signer_name": "x"})
        record(">600KB → 422", r.status_code == 422, f"{r.status_code} {r.text[:80]}")
        r = await c.post(f"/api/gate/{tok3}/guest-sign",
                         files={"signature_image": ("sig.png", b"GIF89a not a png", "image/png")},
                         data={"signer_name": "x"})
        record("non-PNG bytes → 422", r.status_code == 422, str(r.status_code))
        r = await c.post(f"/api/gate/{tok3}/guest-sign",
                         files={"signature_image": ("sig.jpg", png, "image/jpeg")},
                         data={"signer_name": "x"})
        record("content-type image/jpeg → 422", r.status_code == 422, str(r.status_code))
        r = await c.post(f"/api/gate/{tok3}/guest-sign",
                         files={"signature_image": ("sig.png", png, "image/png")},
                         data={"signer_name": "  "})
        record("empty signer_name → 422", r.status_code == 422, str(r.status_code))
        gp3 = await db.guest_entry_passes.find_one({"token": tok3}, {"_id": 0})
        record("failed attempts wrote nothing", gp3["briefing"]["signed"] is False)

        print("V1 — scan log + list tagging")
        r = await c.get(f"/api/safety/{proj}/gate-scans", headers=pm_h)
        j = r.json()
        items = j["items"]
        guest_rows = [it for it in items if it.get("guest_pass_id")]
        worker_rows = [it for it in items if it.get("worker_id") == w1]
        record("guest scans logged (green + unsigned red + wrong-date red)",
               any(it["result"] == "green" and it.get("guest_name") == "אורח בדיקה"
                   and it.get("is_guest") for it in guest_rows)
               and any("guest_unsigned" in (it.get("reasons") or []) for it in guest_rows)
               and any("guest_wrong_date" in (it.get("reasons") or []) for it in guest_rows),
               f"guest_rows={len(guest_rows)}")
        record("worker rows byte-compatible (no guest keys)",
               worker_rows and all(
                   "guest_pass_id" not in it and "is_guest" not in it and "guest_name" not in it
                   for it in worker_rows),
               f"worker_rows={len(worker_rows)}")
        record("summary/filters intact",
               "summary" in j and j["summary"]["total"] == j["total"],
               f"summary={j.get('summary')}")
        r = await c.get(f"/api/safety/{proj}/gate-scans", headers=pm_h,
                        params={"result": "green"})
        record("result=green filter still works",
               r.status_code == 200 and all(it["result"] == "green" for it in r.json()["items"]))

        print("V1 — authed list")
        r = await c.get(GP, headers=pm_h)
        j = r.json()
        record("list passes: 3 items newest-first, signed flags",
               j["total"] == 3 and j["items"][0]["guest_name"] == "אורח ג"
               and any(it["signed"] for it in j["items"])
               and any(it["status"] == "revoked" for it in j["items"]),
               f"total={j.get('total')}")
        r = await c.get(GP, headers=con_h)
        record("contractor list → 403", r.status_code == 403, str(r.status_code))
        r = await c.get(f"{GP}/{pass_id}/qr.png", headers=pm_h)
        record("qr.png → 200 image/png",
               r.status_code == 200 and r.headers["content-type"] == "image/png"
               and r.content.startswith(b"\x89PNG"), str(r.status_code))

    # cleanup
    await db.organizations.delete_many({"id": org})
    await db.subscriptions.delete_many({"org_id": org})
    await db.users.delete_many({"id": {"$in": [pm_id, con_id]}})
    await db.organization_memberships.delete_many({"org_id": org})
    await db.projects.delete_many({"id": proj})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.safety_workers.delete_many({"project_id": proj})
    await db.gate_scan_log.delete_many({"project_id": proj})
    await db.guest_entry_passes.delete_many({"project_id": proj})
    await db.audit_log.delete_many({"actor_user_id": {"$in": [pm_id, con_id]}})

    passed = sum(1 for _, p in RESULTS if p)
    print(f"\n{passed}/{len(RESULTS)} probes passed")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
