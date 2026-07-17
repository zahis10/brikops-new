"""FUNCTIONAL probes for BATCH qrg-share-fix — public pass-page QR + gate_url.

Same in-process harness as probe_safety_qrg_guest.py: REAL FastAPI app,
real local Mongo, real JWTs.

Covers the spec's V1/V2 list:
  V1 public GET /api/gate/{token}/qr.png:
    - worker token → 200 image/png, real PNG magic bytes
    - guest token → 200 image/png
    - revoked token → 404 neutral "קוד לא תקף"
    - unknown token → 404 neutral; short token → 404 (len pre-check)
    - X-Robots-Tag noindex + Cache-Control private headers present
    - response is bytes only (no JSON body / no data fields)
    - QR decodes/encodes the gate URL of the SAME token (zero info gain)
  V2 guest list items include gate_url, still NO raw token field,
    existing keys unchanged.
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
    from contractor_ops.safety.gate import _gate_url

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    paid = (now + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-qs-org-{tag}"
    proj = f"probe-qs-p1-{tag}"
    pm_id = f"probe-qs-pm-{tag}"

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_one(
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97250{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso})
    await db.organization_memberships.insert_one(
        {"id": f"qs-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_one(
        {"id": f"qs-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"})
    w1 = f"qs-w1-{tag}"
    await db.safety_workers.insert_one(
        {"id": w1, "project_id": proj, "full_name": "עובד אחד",
         "deletedAt": None, "created_at": now_iso})

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    # The GLOBAL per-IP limiter (server.py, Mongo-backed otp_rate_limits) is
    # 30 req/min for anonymous — clear its window so probe runs are isolated.
    async def clear_ip_window():
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})
    await clear_ip_window()

    pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
        print("V1 — public qr.png (worker token)")
        r = await c.post(f"/api/safety/{proj}/workers/{w1}/entry-token", headers=pm_h)
        wj = r.json()
        wtok = wj["token"]
        record("entry-token ensure returns token + gate_url",
               r.status_code == 200 and len(wtok) >= 32 and wj.get("gate_url"),
               f"{r.status_code}")

        r = await c.get(f"/api/gate/{wtok}/qr.png")
        record("worker token → 200 image/png with PNG magic",
               r.status_code == 200
               and r.headers.get("content-type") == "image/png"
               and r.content.startswith(b"\x89PNG\r\n\x1a\n"),
               f"{r.status_code} ct={r.headers.get('content-type')}")
        record("noindex + private cache headers",
               "noindex" in (r.headers.get("x-robots-tag") or "")
               and (r.headers.get("cache-control") or "").startswith("private"),
               f"xrt={r.headers.get('x-robots-tag')} cc={r.headers.get('cache-control')}")
        record("bytes only — body is not JSON / carries no fields",
               b'{' != r.content[:1] and b"worker" not in r.content
               and b"guest" not in r.content, f"len={len(r.content)}")
        # zero info gain — the QR encodes exactly the gate URL of THIS token
        try:
            from PIL import Image
            import io as _io
            import qrcode  # noqa: F401 — encode-side check below
            # decode not available (no pyzbar) — assert equal bytes with a
            # locally-encoded QR of the same URL instead (same lib, same input).
            from contractor_ops.safety.gate import _qr_png_bytes
            record("QR bytes == locally encoded QR of _gate_url(token) (zero info gain)",
                   r.content == _qr_png_bytes(_gate_url(wtok)))
        except Exception as e:
            record("QR zero-info-gain check", False, str(e))

        print("V1 — public qr.png (guest token)")
        r = await c.post(f"/api/safety/{proj}/guest-passes", headers=pm_h,
                         json={"guest_name": "אורח בדיקה", "guest_company": "אדריכל"})
        gj = r.json()
        gtok, gid = gj["token"], gj["id"]
        r = await c.get(f"/api/gate/{gtok}/qr.png")
        record("guest token → 200 image/png",
               r.status_code == 200 and r.content.startswith(b"\x89PNG"),
               str(r.status_code))

        print("V1 — negatives")
        r = await c.get(f"/api/gate/{'x'*40}/qr.png")
        record("unknown token → 404 neutral",
               r.status_code == 404 and "קוד לא תקף" in r.json().get("detail", ""),
               f"{r.status_code} {r.text[:60]}")
        r = await c.get("/api/gate/short/qr.png")
        record("short token (len pre-check) → 404 neutral", r.status_code == 404,
               str(r.status_code))
        # revoke guest pass → its qr.png must 404 (same neutral body)
        await c.post(f"/api/safety/{proj}/guest-passes/{gid}/revoke", headers=pm_h)
        r = await c.get(f"/api/gate/{gtok}/qr.png")
        record("revoked guest token → 404 neutral", r.status_code == 404,
               str(r.status_code))

        print("V1 — throttle applies to qr.png")
        # Two layers protect this path: the gate module throttle (60/min) and
        # the global anonymous per-IP limiter (30/min, Mongo). Assert the
        # GATE throttle directly (unit-level, deterministic) AND that a burst
        # over HTTP gets a 429 from whichever layer fires first.
        from contractor_ops.safety import gate_public
        from fastapi import HTTPException as _HTTPExc
        gate_public._hits.clear()
        gate_throttled = False
        try:
            for _ in range(gate_public.GATE_RATE_LIMIT + 1):
                gate_public._check_throttle("probe-ip")
        except _HTTPExc as e:
            gate_throttled = (e.status_code == 429)
        record("gate _check_throttle → 429 past limit", gate_throttled)
        gate_public._hits.clear()
        throttled = False
        for i in range(gate_public.GATE_RATE_LIMIT + 2):
            r = await c.get(f"/api/gate/{wtok}/qr.png")
            if r.status_code == 429:
                throttled = True
                break
        record("HTTP burst → 429 within limit+2 requests", throttled,
               f"last={r.status_code}")
        gate_public._hits.clear()
        await clear_ip_window()

        print("V2 — guest list gate_url")
        r = await c.get(f"/api/safety/{proj}/guest-passes", headers=pm_h)
        items = r.json()["items"]
        it = next(i for i in items if i["id"] == gid)
        record("list item includes gate_url == _gate_url(token)",
               it.get("gate_url") == _gate_url(gtok), str(it.get("gate_url"))[:60])
        record("list item still has NO raw token field", "token" not in it,
               str(sorted(it.keys())))
        expected_keys = {"id", "guest_name", "guest_company", "valid_on", "status",
                         "signed", "signed_at", "qr_display_url", "gate_url", "created_at"}
        record("existing keys unchanged (only gate_url added)",
               set(it.keys()) == expected_keys, str(sorted(it.keys())))

    # cleanup
    await db.organizations.delete_many({"id": org})
    await db.subscriptions.delete_many({"org_id": org})
    await db.users.delete_many({"id": pm_id})
    await db.organization_memberships.delete_many({"org_id": org})
    await db.projects.delete_many({"id": proj})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.safety_workers.delete_many({"project_id": proj})
    await db.worker_entry_tokens.delete_many({"project_id": proj})
    await db.guest_entry_passes.delete_many({"project_id": proj})
    await db.gate_scan_log.delete_many({"project_id": proj})
    await db.audit_log.delete_many({"actor_user_id": pm_id})

    passed = sum(1 for _, p in RESULTS if p)
    print(f"\n{passed}/{len(RESULTS)} probes passed")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
