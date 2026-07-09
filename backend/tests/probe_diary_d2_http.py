"""FUNCTIONAL HTTP probes for diary-d2 (Work Diary frontend wiring).

Drives the REAL FastAPI app in-process (httpx ASGITransport) with
ENABLE_WORK_DIARY=true, a REAL local Mongo, REAL local object storage and a
REAL JWT minted with the app's own _create_token. Every request hits the
exact URL + method + body shape that frontend diaryService (api.js) sends,
so a PASS here means the UI's network contract is correct end-to-end.

Covered (maps to batch V-list, API side):
  V2  create today  → POST /entries {diary_date}
  V2b duplicate     → 409 (UI opens existing entry)
  V3  list ?month   → {items,total}; deep-link month filter contract
  V4  PATCH sections (work_description, workers_by_company manual row,
      materials, weather) — one debounced PATCH per section
  V5  refresh-derived → POST .../refresh-derived (null body)
  V6  sign          → multipart signer_name/signature_type/signature_image
                      → signed + worker_signature.signature_display_url;
      PATCH after sign → 409 (UI flips read-only)
  V6b addendum      → POST .../addendums {text}
  V7  RBAC          → owner GET 403 (backend d1 restricts reads to
                      PM/management_team via _check_project_access; the UI
                      shows the forbidden screen), owner POST 403
  V-late            → yesterday create ⇒ entered_late=true (badge data)

V1 (flag off ⇒ 404) is verified against the live dev server separately.
"""
import os
os.environ["ENABLE_WORK_DIARY"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local — repl env may carry Atlas
os.environ["DB_NAME"] = "contractor_ops"

import sys
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


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.utils.timezone import IL_TZ

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = uuid.uuid4().hex[:8]
    pid = f"probe-d2-{tag}"
    pm_id = f"probe-d2-pm-{tag}"
    owner_id = f"probe-d2-owner-{tag}"
    today = datetime.now(IL_TZ).strftime("%Y-%m-%d")
    month = today[:7]
    yesterday = (datetime.now(IL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    # seed: org (active subscription → paywall FULL_ACCESS) + project +
    # PM (writer) + owner via project_memberships (the collection
    # _check_project_access reads)
    org_id = f"probe-d2-org-{tag}"
    await db.organizations.insert_one({
        "id": org_id, "name": f"ארגון בדיקה {tag}", "owner_user_id": owner_id,
    })
    await db.subscriptions.insert_one({
        "org_id": org_id, "status": "active",
        # stored as ISO string — _resolve_access compares against _now() string
        "paid_until": (datetime.now(IL_TZ) + timedelta(days=30)).isoformat(),
    })
    await db.projects.insert_one({
        "id": pid, "name": f"פרויקט בדיקה d2 {tag}", "org_id": org_id,
        "deletedAt": None,
    })
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": owner_id, "role": "owner", "full_name": "יזם בדיקה",
         "user_status": "active", "session_version": 0},
    ])
    await db.organization_memberships.insert_many([
        {"id": f"om1-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
        {"id": f"om2-{tag}", "org_id": org_id, "user_id": owner_id, "role": "owner"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"m1-{tag}", "project_id": pid, "user_id": pm_id,
         "role": "project_manager"},
        {"id": f"m2-{tag}", "project_id": pid, "user_id": owner_id,
         "role": "owner"},
    ])

    pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
    ow_h = {"Authorization": f"Bearer {_create_token(owner_id, 'owner')}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe") as c:
        base = f"/api/work-diary/{pid}/entries"

        # V2 create today
        r = await c.post(base, json={"diary_date": today}, headers=pm_h)
        ok = r.status_code == 200 and r.json().get("diary_date") == today
        entry = r.json() if ok else {}
        record("V2 create today entry", ok, f"status={r.status_code}")
        eid = entry.get("id")

        # V2b duplicate → 409
        r = await c.post(base, json={"diary_date": today}, headers=pm_h)
        record("V2b duplicate create → 409", r.status_code == 409, f"status={r.status_code}")

        # V-late: yesterday ⇒ entered_late badge data
        r = await c.post(base, json={"diary_date": yesterday}, headers=pm_h)
        record("V-late yesterday ⇒ entered_late=true",
               r.status_code == 200 and r.json().get("entered_late") is True,
               f"status={r.status_code} entered_late={r.json().get('entered_late') if r.status_code==200 else '-'}")

        # V3 list ?month — exact param diaryService sends
        r = await c.get(base, params={"month": month}, headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        items = j.get("items", [])
        ok = (r.status_code == 200 and isinstance(items, list)
              and "total" in j
              and any(e.get("diary_date") == today for e in items)
              and all(e.get("diary_date", "").startswith(month) for e in items))
        record("V3 list ?month shape {items,total} + month filter", ok,
               f"status={r.status_code} n={len(items)}")

        # V4 PATCH sections (single PATCH each, as the debounced autosave sends)
        r = await c.patch(f"{base}/{eid}", json={"work_description": "יציקת תקרה קומה 3"}, headers=pm_h)
        record("V4a PATCH work_description", r.status_code == 200
               and r.json().get("work_description") == "יציקת תקרה קומה 3",
               f"status={r.status_code}")
        rows = [{"company_id": None, "company_name": "קבוצת בטון", "count": 7, "source": "manual"}]
        r = await c.patch(f"{base}/{eid}", json={"workers_by_company": rows}, headers=pm_h)
        got = (r.json().get("workers_by_company") or [{}]) if r.status_code == 200 else [{}]
        record("V4b PATCH workers_by_company manual row",
               r.status_code == 200 and got and got[0].get("count") == 7
               and got[0].get("source") == "manual", f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}", json={"materials": ["ברזל 12", "בטון ב-30"]}, headers=pm_h)
        record("V4c PATCH materials list[str]", r.status_code == 200
               and r.json().get("materials") == ["ברזל 12", "בטון ב-30"], f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}", json={"weather": {"desc": "שרב", "source": "manual"}}, headers=pm_h)
        record("V4d PATCH weather", r.status_code == 200
               and (r.json().get("weather") or {}).get("desc") == "שרב", f"status={r.status_code}")

        # V5 refresh-derived (null body, like axios.post(url, null))
        r = await c.post(f"{base}/{eid}/refresh-derived", headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        record("V5 refresh-derived keeps manual edits", r.status_code == 200
               and j.get("work_description") == "יציקת תקרה קומה 3"
               and (j.get("workers_by_company") or [{}])[0].get("source") == "manual",
               f"status={r.status_code}")

        # V7 RBAC: backend restricts even reads to PM/management_team (d1
        # _check_project_access) — owner gets 403; UI shows forbidden screen
        r = await c.get(base, params={"month": month}, headers=ow_h)
        record("V7a owner GET list → 403 (backend read restriction)",
               r.status_code == 403, f"status={r.status_code}")
        r = await c.post(base, json={"diary_date": today}, headers=ow_h)
        record("V7b owner POST create → 403", r.status_code == 403, f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}", json={"work_description": "x"}, headers=ow_h)
        record("V7c owner PATCH → 403", r.status_code == 403, f"status={r.status_code}")

        # V6 sign — multipart exactly like diaryService.signEntry FormData
        r = await c.post(
            f"{base}/{eid}/signature",
            data={"signer_name": "מנהל בדיקה", "signature_type": "drawn"},
            files={"signature_image": ("signature.png", _PNG, "image/png")},
            headers=pm_h,
        )
        j = r.json() if r.status_code == 200 else {}
        sig = j.get("worker_signature") or {}
        record("V6 sign multipart → signed + signature_display_url",
               r.status_code == 200 and j.get("status") == "signed"
               and bool(sig.get("signature_display_url")), f"status={r.status_code}")

        # V6-lock: PATCH after sign → 409 (UI flips read-only via onChanged)
        r = await c.patch(f"{base}/{eid}", json={"work_description": "אחרי חתימה"}, headers=pm_h)
        record("V6-lock PATCH after sign → 409", r.status_code == 409, f"status={r.status_code}")

        # V6b addendum
        r = await c.post(f"{base}/{eid}/addendums", json={"text": "תוספת לאחר חתימה"}, headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        adds = j.get("addendums") or []
        record("V6b addendum appended", r.status_code == 200 and adds
               and adds[-1].get("text") == "תוספת לאחר חתימה", f"status={r.status_code}")

        # deep-link miss contract: month with no entries → empty items (UI shows
        # 'לא נמצא יומן לתאריך זה')
        r = await c.get(base, params={"month": "2020-01"}, headers=pm_h)
        record("V3b empty month → items=[] (deep-link miss state)",
               r.status_code == 200 and r.json().get("items") == [], f"status={r.status_code}")

    # cleanup
    await db.projects.delete_many({"id": pid})
    await db.organizations.delete_many({"id": org_id})
    await db.subscriptions.delete_many({"org_id": org_id})
    await db.users.delete_many({"id": {"$in": [pm_id, owner_id]}})
    await db.organization_memberships.delete_many({"org_id": org_id})
    await db.project_memberships.delete_many({"project_id": pid})
    await db.work_diary_entries.delete_many({"project_id": pid})

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*50}\nTOTAL: {len(RESULTS)}  PASS: {len(RESULTS)-len(fails)}  FAIL: {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
