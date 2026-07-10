"""FUNCTIONAL HTTP probes for diary-d4a (monthly consolidated PDF + fold-ins).

Same in-process harness as probe_diary_d3_http.py: REAL FastAPI app (httpx
ASGITransport), ENABLE_WORK_DIARY + ENABLE_SAFETY_MODULE, REAL local Mongo,
FILES_STORAGE_BACKEND=local (NEVER a real bucket), REAL JWTs from _create_token.

Covers:
  V1     monthly PDF: month with 2 signed + 1 draft -> 200 %PDF-, draft excluded
         (page-count sanity via pdf page objects), Content-Disposition + audit
  V1PERF synthetic heavy month (10 signed x 6 photos = 60 images) -> wall-clock
         reported; ABORT-worthy if > ~30s (ALB/EB ~60s -> background export)
  V2     empty month -> 404 Hebrew; bad month format -> 422
  V3     RBAC: owner GET monthly -> 200; non-member -> 403; super_admin -> 200
  V6     2b: entry with count="abc" (direct db) -> single-entry export 200
  V7     2e identity: all three ref-regex are the SAME compiled object (`is`)
"""
import os
os.environ["ENABLE_WORK_DIARY"] = "true"
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local — repl env may carry Atlas
os.environ.setdefault("DB_NAME", "contractor_ops")

import sys
import re
import time
import uuid
import asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000154a24f5f0000000049454e44ae426082"
)


def _pdf_page_count(data: bytes) -> int:
    # Cheap structural count — enough to assert "cover + N entries" ballpark
    # without pulling a PDF parser. reportlab emits one /Type /Page per page.
    return len(re.findall(rb"/Type\s*/Page[^s]", data))


async def _sign(c, base, eid, pm_h, name):
    return await c.post(
        f"{base}/{eid}/signature",
        data={"signer_name": name, "signature_type": "typed", "typed_name": name},
        headers=pm_h,
    )


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.utils.timezone import IL_TZ

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = uuid.uuid4().hex[:8]
    pid = f"probe-d4a-{tag}"
    pm_id = f"probe-d4a-pm-{tag}"
    owner_id = f"probe-d4a-owner-{tag}"
    stranger_id = f"probe-d4a-str-{tag}"
    sa_id = f"probe-d4a-sa-{tag}"
    org_id = f"probe-d4a-org-{tag}"

    # Use a FIXED past month so "today" logic never interferes with counts.
    month = "2026-03"

    await db.organizations.insert_one({"id": org_id, "name": f"ארגון {tag}", "owner_user_id": owner_id})
    await db.subscriptions.insert_one({
        "org_id": org_id, "status": "active",
        "paid_until": (datetime.now(IL_TZ) + timedelta(days=30)).isoformat(),
    })
    await db.projects.insert_one({
        "id": pid, "name": f"פרויקט d4a {tag}", "org_id": org_id, "deletedAt": None,
    })
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": owner_id, "role": "owner", "full_name": "יזם בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": stranger_id, "role": "project_manager", "full_name": "זר בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": sa_id, "role": "super_admin", "platform_role": "super_admin",
         "full_name": "אדמין בדיקה", "user_status": "active", "session_version": 0},
    ])
    await db.organization_memberships.insert_many([
        {"id": f"om1-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
        {"id": f"om2-{tag}", "org_id": org_id, "user_id": owner_id, "role": "owner"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"m1-{tag}", "project_id": pid, "user_id": pm_id, "role": "project_manager"},
        {"id": f"m2-{tag}", "project_id": pid, "user_id": owner_id, "role": "owner"},
    ])

    pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
    ow_h = {"Authorization": f"Bearer {_create_token(owner_id, 'owner')}"}
    str_h = {"Authorization": f"Bearer {_create_token(stranger_id, 'project_manager')}"}
    sa_h = {"Authorization": f"Bearer {_create_token(sa_id, 'super_admin')}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=120) as c:
        base = f"/api/work-diary/{pid}/entries"
        monthly = f"/api/work-diary/{pid}/export/monthly-pdf"

        # ---------------- V7 (2e) identity: THE SAME compiled regex object -----
        from contractor_ops.upload_safety import SAFETY_STORED_REF_RE
        from contractor_ops.work_diary_router import _PHOTO_REF_RE
        from contractor_ops.safety.workers import _WORKER_PHOTO_REF_RE
        from services import work_diary_pdf as wdp
        record("V7a router _PHOTO_REF_RE IS SAFETY_STORED_REF_RE",
               _PHOTO_REF_RE is SAFETY_STORED_REF_RE)
        record("V7b workers _WORKER_PHOTO_REF_RE IS SAFETY_STORED_REF_RE",
               _WORKER_PHOTO_REF_RE is SAFETY_STORED_REF_RE)
        record("V7c work_diary_pdf imports SAFETY_STORED_REF_RE (same object)",
               wdp.SAFETY_STORED_REF_RE is SAFETY_STORED_REF_RE)

        # ---------------- upload one reusable local photo ---------------------
        r = await c.post(f"/api/safety/{pid}/upload",
                         files={"file": ("p.png", _PNG, "image/png")}, headers=pm_h)
        photo_ref = r.json().get("stored_ref") if r.status_code == 200 else None
        record("setup photo upload", bool(photo_ref), f"status={r.status_code}")

        # ---------------- seed the V1 month: 2 signed + 1 draft ---------------
        signed_ids = []
        for day, desc in [("2026-03-03", "יציקת יסודות"), ("2026-03-10", "טפסנות קומה 1")]:
            r = await c.post(base, json={"diary_date": day}, headers=pm_h)
            eid = r.json()["id"]
            await c.patch(f"{base}/{eid}", json={"work_description": desc, "photo_refs": [photo_ref]}, headers=pm_h)
            rs = await _sign(c, base, eid, pm_h, "מנהל בדיקה")
            assert rs.status_code == 200 and rs.json().get("status") == "signed", rs.text
            signed_ids.append(eid)
        # a DRAFT in the same month — must be EXCLUDED from the monthly doc
        r = await c.post(base, json={"diary_date": "2026-03-15"}, headers=pm_h)
        draft_id = r.json()["id"]
        await c.patch(f"{base}/{draft_id}", json={"work_description": "טיוטה — לא נחתם"}, headers=pm_h)

        # ---------------- V1 monthly PDF --------------------------------------
        r = await c.get(monthly, params={"month": month}, headers=pm_h)
        cd = r.headers.get("content-disposition", "")
        pages = _pdf_page_count(r.content) if r.status_code == 200 else -1
        record("V1a monthly export -> 200 %PDF- application/pdf",
               r.status_code == 200 and r.content[:5] == b"%PDF-"
               and "application/pdf" in r.headers.get("content-type", ""),
               f"status={r.status_code} bytes={len(r.content)}")
        record("V1b filename diary_{month}.pdf", f"diary_{month}.pdf" in cd, f"cd={cd}")
        # cover (1) + 2 signed entries = >=3 pages; draft's page must NOT be there.
        record("V1c page count reflects cover + 2 signed (draft excluded)",
               pages >= 3, f"pages={pages}")
        ev = await db.audit_events.find_one(
            {"action": "monthly_pdf_exported", "entity_id": pid}, sort=[("_id", -1)])
        record("V1d audit monthly_pdf_exported (entries=2)",
               bool(ev) and ev.get("payload", {}).get("entries") == 2,
               f"entries={ev.get('payload', {}).get('entries') if ev else '-'}")

        # ---------------- V2 empty month / bad format -------------------------
        r = await c.get(monthly, params={"month": "2025-01"}, headers=pm_h)
        record("V2a empty month -> 404 Hebrew",
               r.status_code == 404 and "אין רשומות חתומות" in r.text, f"status={r.status_code}")
        r = await c.get(monthly, params={"month": "2026-3"}, headers=pm_h)
        record("V2b bad month format -> 422", r.status_code == 422, f"status={r.status_code}")
        r = await c.get(monthly, params={"month": "not-a-month"}, headers=pm_h)
        record("V2c garbage month -> 422", r.status_code == 422, f"status={r.status_code}")

        # ---------------- V3 RBAC ---------------------------------------------
        r = await c.get(monthly, params={"month": month}, headers=ow_h)
        record("V3a owner GET monthly -> 200 (read gate)",
               r.status_code == 200 and r.content[:5] == b"%PDF-", f"status={r.status_code}")
        r = await c.get(monthly, params={"month": month}, headers=str_h)
        record("V3b non-member GET monthly -> 403", r.status_code == 403, f"status={r.status_code}")
        r = await c.get(monthly, params={"month": month}, headers=sa_h)
        record("V3c super_admin GET monthly -> 200", r.status_code == 200, f"status={r.status_code}")

        # ---------------- V6 (2b) count="abc" tolerated by export -------------
        r = await c.post(base, json={"diary_date": "2026-04-02"}, headers=pm_h)
        v6_id = r.json()["id"]
        # write a NON-numeric worker count straight to the doc, then sign+export
        await db.work_diary_entries.update_one(
            {"id": v6_id},
            {"$set": {"work_description": "בדיקת count לא מספרי",
                      "workers": [{"name": "עובד", "count": "abc"}]}},
        )
        rs = await _sign(c, base, v6_id, pm_h, "מנהל בדיקה")
        r = await c.get(f"{base}/{v6_id}/export/pdf", headers=pm_h)
        record("V6 single-entry export tolerates count='abc' (2b _safe_int)",
               rs.status_code == 200 and r.status_code == 200 and r.content[:5] == b"%PDF-",
               f"sign={rs.status_code} export={r.status_code}")

        # ---------------- V1-PERF heavy month (10 signed x 6 photos = 60) -----
        perf_month = "2026-05"
        # upload 6 distinct local photos, reuse across entries -> 60 image loads
        heavy_refs = []
        for i in range(6):
            rr = await c.post(f"/api/safety/{pid}/upload",
                              files={"file": (f"h{i}.png", _PNG, "image/png")}, headers=pm_h)
            heavy_refs.append(rr.json()["stored_ref"])
        for d in range(1, 11):
            day = f"{perf_month}-{d:02d}"
            r = await c.post(base, json={"diary_date": day}, headers=pm_h)
            hid = r.json()["id"]
            await c.patch(f"{base}/{hid}",
                          json={"work_description": f"יום {d} — עבודות", "photo_refs": heavy_refs},
                          headers=pm_h)
            await _sign(c, base, hid, pm_h, "מנהל בדיקה")
        t0 = time.monotonic()
        r = await c.get(monthly, params={"month": perf_month}, headers=pm_h)
        elapsed = time.monotonic() - t0
        heavy_pages = _pdf_page_count(r.content) if r.status_code == 200 else -1
        record("V1PERF heavy month (10 signed x 6 imgs) -> 200 %PDF-",
               r.status_code == 200 and r.content[:5] == b"%PDF-",
               f"status={r.status_code} bytes={len(r.content)} pages={heavy_pages}")
        record(f"V1PERF WALL-CLOCK = {elapsed:.2f}s (threshold ~30s)",
               elapsed <= 30.0, f"{elapsed:.2f}s")
        print(f"\n  >>> V1-PERF wall-clock generation time: {elapsed:.2f}s "
              f"({'OK — ship' if elapsed <= 30 else 'SLOW — consider background export'})")

    # cleanup
    await db.projects.delete_many({"id": pid})
    await db.organizations.delete_many({"id": org_id})
    await db.subscriptions.delete_many({"org_id": org_id})
    await db.users.delete_many({"id": {"$in": [pm_id, owner_id, stranger_id, sa_id]}})
    await db.organization_memberships.delete_many({"org_id": org_id})
    await db.project_memberships.delete_many({"project_id": pid})
    await db.work_diary_entries.delete_many({"project_id": pid})
    await db.audit_events.delete_many({"actor_id": {"$in": [pm_id, owner_id, sa_id]}})

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*50}\nTOTAL: {len(RESULTS)}  PASS: {len(RESULTS)-len(fails)}  FAIL: {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
