"""FUNCTIONAL HTTP probes for diary-d3 (PDF export + photos + read-widen + paywall tuple).

Same harness as probe_diary_d2_http.py: REAL FastAPI app in-process (httpx
ASGITransport), ENABLE_WORK_DIARY=true, REAL local Mongo, REAL local object
storage, REAL JWTs from the app's own _create_token.

Covered (maps to batch V-list):
  V1  photos — POST /api/safety/{pid}/upload (the reused endpoint; keys land
      under safety/{project_id}/), PATCH photo_refs, GET returns the
      photo_display_urls PARALLEL list (same length as photo_refs)
  V2  PDF export — GET .../export/pdf → 200 application/pdf, %PDF- magic,
      Content-Disposition diary_{date}.pdf; works on DRAFT (watermarked
      inside the doc); audit event "pdf_exported" recorded
  V3  read-widen — owner GET list / GET entry / export PDF → 200;
      owner POST/PATCH/sign STILL 403 (writes untouched);
      non-member → 403; contractor member → 403 (not in DIARY_READERS)
  V4  signed export — after multipart sign, export still 200 + %PDF-
  V5  paywall tuple — _resolve_request_org_id('/api/work-diary/{pid}/...')
      resolves the org via projects.org_id (direct unit call — the exact
      tuple added at router.py _ORG_URL_PATTERNS)
  V6  expired-subscription org — PM POST create → 402 (mutations blocked;
      GET stays open by design: _check_paywall returns early on GET)

reportlab Image(BytesIO) idiom sandbox transcript (Zahi amendment #4) is in
review.txt — corrupt bytes raise UnidentifiedImageError at CONSTRUCTION.
"""
import os
import re
os.environ["ENABLE_WORK_DIARY"] = "true"
# The diary photo picker reuses POST /api/safety/{pid}/upload — that router is
# feature-gated (never imported when off), so the probe must enable it too.
os.environ["ENABLE_SAFETY_MODULE"] = "true"
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
    from contractor_ops.router import _create_token, _resolve_request_org_id

    from contractor_ops.utils.timezone import IL_TZ

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = uuid.uuid4().hex[:8]
    pid = f"probe-d3-{tag}"
    pm_id = f"probe-d3-pm-{tag}"
    owner_id = f"probe-d3-owner-{tag}"
    contractor_id = f"probe-d3-con-{tag}"
    stranger_id = f"probe-d3-str-{tag}"
    sa_id = f"probe-d3-sa-{tag}"
    today = datetime.now(IL_TZ).strftime("%Y-%m-%d")
    month = today[:7]

    org_id = f"probe-d3-org-{tag}"
    await db.organizations.insert_one({
        "id": org_id, "name": f"ארגון בדיקה {tag}", "owner_user_id": owner_id,
    })
    await db.subscriptions.insert_one({
        "org_id": org_id, "status": "active",
        "paid_until": (datetime.now(IL_TZ) + timedelta(days=30)).isoformat(),
    })
    await db.projects.insert_one({
        "id": pid, "name": f"פרויקט בדיקה d3 {tag}", "org_id": org_id,
        "deletedAt": None,
    })
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": owner_id, "role": "owner", "full_name": "יזם בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": contractor_id, "role": "contractor", "full_name": "קבלן בדיקה",
         "user_status": "active", "session_version": 0},
        {"id": stranger_id, "role": "project_manager", "full_name": "זר בדיקה",
         "user_status": "active", "session_version": 0},
        # _is_super_admin() checks platform_role, not role
        {"id": sa_id, "role": "super_admin", "platform_role": "super_admin",
         "full_name": "אדמין בדיקה", "user_status": "active", "session_version": 0},
    ])
    await db.organization_memberships.insert_many([
        {"id": f"om1-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
        {"id": f"om2-{tag}", "org_id": org_id, "user_id": owner_id, "role": "owner"},
        {"id": f"om3-{tag}", "org_id": org_id, "user_id": contractor_id, "role": "member"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"m1-{tag}", "project_id": pid, "user_id": pm_id, "role": "project_manager"},
        {"id": f"m2-{tag}", "project_id": pid, "user_id": owner_id, "role": "owner"},
        {"id": f"m3-{tag}", "project_id": pid, "user_id": contractor_id, "role": "contractor"},
    ])

    pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
    ow_h = {"Authorization": f"Bearer {_create_token(owner_id, 'owner')}"}
    con_h = {"Authorization": f"Bearer {_create_token(contractor_id, 'contractor')}"}
    str_h = {"Authorization": f"Bearer {_create_token(stranger_id, 'project_manager')}"}
    sa_h = {"Authorization": f"Bearer {_create_token(sa_id, 'super_admin')}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe") as c:
        base = f"/api/work-diary/{pid}/entries"

        # seed entry (draft)
        r = await c.post(base, json={"diary_date": today}, headers=pm_h)
        assert r.status_code == 200, f"seed create failed: {r.status_code} {r.text}"
        eid = r.json()["id"]
        await c.patch(f"{base}/{eid}", json={"work_description": "יציקת תקרה קומה 3"}, headers=pm_h)

        # ---------------- V1 photos ----------------
        r = await c.post(
            f"/api/safety/{pid}/upload",
            files={"file": ("photo.png", _PNG, "image/png")},
            headers=pm_h,
        )
        j = r.json() if r.status_code == 200 else {}
        ref = j.get("stored_ref") or ""
        record("V1a photo upload via /api/safety/{pid}/upload",
               r.status_code == 200 and bool(ref), f"status={r.status_code}")
        # local backend returns the ref prefixed /api/uploads/<key>; S3 returns
        # the bare key — either way the KEY lives under safety/{project_id}/
        record("V1b stored_ref key lands under safety/{project_id}/",
               f"safety/{pid}/" in ref, f"ref={ref[:48]}")

        r = await c.patch(f"{base}/{eid}", json={"photo_refs": [ref]}, headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        urls = j.get("photo_display_urls")
        record("V1c PATCH photo_refs → photo_display_urls parallel list",
               r.status_code == 200 and j.get("photo_refs") == [ref]
               and isinstance(urls, list) and len(urls) == 1 and bool(urls[0]),
               f"status={r.status_code} urls={urls if not urls else 'len'+str(len(urls))}")

        r = await c.get(f"{base}/{eid}", headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        record("V1d GET entry keeps parallel photo_display_urls",
               r.status_code == 200
               and len(j.get("photo_display_urls") or []) == len(j.get("photo_refs") or [])
               == 1, f"status={r.status_code}")

        # photo_display_urls must NEVER persist (per-GET only)
        raw = await db.work_diary_entries.find_one({"id": eid}, {"_id": 0})
        record("V1e photo_display_urls not persisted at rest",
               "photo_display_urls" not in (raw or {}), "")

        # V1f-h SSRF gate (architect review): photo_refs reaching the PDF
        # loader may be HTTP-fetched, so writes must reject anything that is
        # not a safety/{THIS project}/ storage key.
        r = await c.patch(f"{base}/{eid}",
                          json={"photo_refs": ["http://169.254.169.254/latest/meta-data"]},
                          headers=pm_h)
        record("V1f SSRF: http:// photo_ref rejected 422", r.status_code == 422,
               f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}",
                          json={"photo_refs": [f"safety/other-project/{uuid.uuid4().hex}.png"]},
                          headers=pm_h)
        record("V1g cross-project photo_ref rejected 422", r.status_code == 422,
               f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}",
                          json={"photo_refs": [ref] * 13}, headers=pm_h)
        record("V1h >12 photo_refs rejected 422", r.status_code == 422,
               f"status={r.status_code}")
        # entry unchanged after rejections
        r = await c.get(f"{base}/{eid}", headers=pm_h)
        record("V1i photo_refs untouched after rejected PATCHes",
               r.status_code == 200 and r.json().get("photo_refs") == [ref],
               f"refs={r.json().get('photo_refs') if r.status_code==200 else '-'}")

        # ---------------- V1 (fix2) direct validator: BOTH backend shapes ------
        # S3 mode → "s3://safety/{pid}/..", local mode → "/api/uploads/safety/..".
        # The write-time gate (_validate_photo_refs) AND the PDF loader's mirror
        # regex must ACCEPT both real shapes yet still REJECT schemes / a bucket
        # segment / cross-project. (d3 probes ran local-only, so s3:// never hit.)
        from contractor_ops.work_diary_router import _validate_photo_refs
        from fastapi import HTTPException as _HX
        _pdf_re = re.compile(  # mirror of _safe_ref built inside work_diary_pdf.build
            r"^(?:/api/uploads/|s3://)?safety/([A-Za-z0-9_-]+)/[A-Za-z0-9][A-Za-z0-9.+_-]*$")

        def _router_accepts(refs):
            try:
                _validate_photo_refs(pid, refs)
                return True
            except _HX:
                return False

        def _pdf_accepts(s):
            m = _pdf_re.match(s or "")
            return bool(m) and m.group(1) == pid and ".." not in (s or "")

        _uu = uuid.uuid4().hex
        _acc = [f"s3://safety/{pid}/{_uu}.jpg",
                f"/api/uploads/safety/{pid}/{_uu}.jpg",
                f"safety/{pid}/{_uu}.jpg"]
        _rej = ["http://169.254.169.254/latest/meta-data",
                "https://evil/x.jpg",
                f"s3://mybucket/safety/{pid}/{_uu}.jpg",   # bucket segment, not our shape
                f"s3://safety/other-{pid}/{_uu}.jpg"]      # cross-project
        record("V1j router validator ACCEPTS s3/local/bare shapes",
               all(_router_accepts([s]) for s in _acc),
               f"acc={[_router_accepts([s]) for s in _acc]}")
        record("V1k router validator REJECTS scheme/bucket/cross-project",
               all(not _router_accepts([s]) for s in _rej),
               f"rej={[_router_accepts([s]) for s in _rej]}")
        record("V1l PDF-loader regex ACCEPTS s3/local/bare shapes",
               all(_pdf_accepts(s) for s in _acc),
               f"acc={[_pdf_accepts(s) for s in _acc]}")
        record("V1m PDF-loader regex REJECTS scheme/bucket/cross-project",
               all(not _pdf_accepts(s) for s in _rej),
               f"rej={[_pdf_accepts(s) for s in _rej]}")

        # ---------------- V2 (fix2) HTTP: real s3:// ref round-trips -----------
        _s3ref = f"s3://safety/{pid}/{uuid.uuid4().hex}.jpg"
        r = await c.patch(f"{base}/{eid}", json={"photo_refs": [_s3ref]}, headers=pm_h)
        record("V2fix2a PATCH s3:// photo_ref → 200 stored verbatim",
               r.status_code == 200 and r.json().get("photo_refs") == [_s3ref],
               f"status={r.status_code} refs={r.json().get('photo_refs') if r.status_code==200 else '-'}")
        # regression: the d3 negatives still reject after the widen
        r = await c.patch(f"{base}/{eid}",
                          json={"photo_refs": ["http://169.254.169.254/latest/meta-data"]},
                          headers=pm_h)
        record("V2fix2b http:// still 422", r.status_code == 422, f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}",
                          json={"photo_refs": [f"s3://safety/other-{pid}/{_uu}.jpg"]},
                          headers=pm_h)
        record("V2fix2c s3:// cross-project still 422", r.status_code == 422, f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}", json={"photo_refs": [_s3ref] * 13}, headers=pm_h)
        record("V2fix2d >12 s3:// refs still 422", r.status_code == 422, f"status={r.status_code}")
        # restore the real (loadable) local ref so downstream PDF checks pass
        r = await c.patch(f"{base}/{eid}", json={"photo_refs": [ref]}, headers=pm_h)
        record("V2fix2e restore loadable ref → 200",
               r.status_code == 200 and r.json().get("photo_refs") == [ref],
               f"status={r.status_code}")

        # ---------------- V3 (fix2) PDF fail-soft on missing s3 object ---------
        # A valid-SHAPE s3:// ref whose object does not exist must be SKIPPED by
        # the loader — the signed PDF still builds (no 500). Verified via the
        # export endpoint after briefly setting a shape-valid, unloadable ref.
        r = await c.patch(f"{base}/{eid}",
                          json={"photo_refs": [f"s3://safety/{pid}/{uuid.uuid4().hex}.jpg"]},
                          headers=pm_h)
        _ok_patch = r.status_code == 200
        r = await c.get(f"{base}/{eid}/export/pdf", headers=pm_h)
        record("V3fix2 PDF builds fail-soft with unloadable s3:// ref",
               _ok_patch and r.status_code == 200 and r.content[:5] == b"%PDF-",
               f"patch={_ok_patch} status={r.status_code} bytes={len(r.content)}")
        # restore loadable ref for the remaining d3 checks
        await c.patch(f"{base}/{eid}", json={"photo_refs": [ref]}, headers=pm_h)

        # ---------------- V2 PDF export (draft) ----------------
        r = await c.get(f"{base}/{eid}/export/pdf", headers=pm_h)
        cd = r.headers.get("content-disposition", "")
        record("V2a DRAFT export → 200 %PDF- application/pdf",
               r.status_code == 200 and r.content[:5] == b"%PDF-"
               and "application/pdf" in r.headers.get("content-type", ""),
               f"status={r.status_code} bytes={len(r.content)}")
        record("V2b Content-Disposition diary_{date}.pdf",
               f"diary_{today}.pdf" in cd, f"cd={cd}")
        ev = await db.audit_events.find_one(
            {"entity_id": eid, "action": "pdf_exported"}, {"_id": 0})
        record("V2c audit event pdf_exported recorded", bool(ev),
               f"actor={ev.get('actor_id') if ev else '-'}")

        # ---------------- V3 read-widen ----------------
        r = await c.get(base, params={"month": month}, headers=ow_h)
        record("V3a owner GET list → 200 (read-widen)",
               r.status_code == 200 and any(e.get("id") == eid for e in r.json().get("items", [])),
               f"status={r.status_code}")
        r = await c.get(f"{base}/{eid}", headers=ow_h)
        record("V3b owner GET entry → 200", r.status_code == 200, f"status={r.status_code}")
        r = await c.get(f"{base}/{eid}/export/pdf", headers=ow_h)
        record("V3c owner export PDF → 200 %PDF-",
               r.status_code == 200 and r.content[:5] == b"%PDF-", f"status={r.status_code}")

        r = await c.post(base, json={"diary_date": "2026-01-01"}, headers=ow_h)
        record("V3d owner POST create STILL 403", r.status_code == 403, f"status={r.status_code}")
        r = await c.patch(f"{base}/{eid}", json={"work_description": "x"}, headers=ow_h)
        record("V3e owner PATCH STILL 403", r.status_code == 403, f"status={r.status_code}")
        r = await c.post(f"{base}/{eid}/signature",
                         data={"signer_name": "יזם", "signature_type": "typed", "typed_name": "יזם"},
                         headers=ow_h)
        record("V3f owner sign STILL 403", r.status_code == 403, f"status={r.status_code}")

        r = await c.get(base, params={"month": month}, headers=con_h)
        record("V3g contractor member GET → 403 (not a diary reader)",
               r.status_code == 403, f"status={r.status_code}")
        r = await c.get(base, params={"month": month}, headers=str_h)
        record("V3h non-member GET → 403", r.status_code == 403, f"status={r.status_code}")
        r = await c.get(f"{base}/{eid}/export/pdf", headers=str_h)
        record("V3i non-member export → 403", r.status_code == 403, f"status={r.status_code}")
        r = await c.get(base, params={"month": month}, headers=sa_h)
        record("V3j super_admin GET → 200 (bypass)", r.status_code == 200, f"status={r.status_code}")

        # ---------------- V4 signed export ----------------
        r = await c.post(
            f"{base}/{eid}/signature",
            data={"signer_name": "מנהל בדיקה", "signature_type": "canvas"},
            files={"signature_image": ("signature.png", _PNG, "image/png")},
            headers=pm_h,
        )
        record("V4a sign (canvas multipart) → signed",
               r.status_code == 200 and r.json().get("status") == "signed",
               f"status={r.status_code}")
        r = await c.get(f"{base}/{eid}/export/pdf", headers=pm_h)
        record("V4b SIGNED export → 200 %PDF-",
               r.status_code == 200 and r.content[:5] == b"%PDF-",
               f"status={r.status_code} bytes={len(r.content)}")

        # ---------------- V5 paywall tuple (direct unit call) ----------------
        resolved = await _resolve_request_org_id(f"/api/work-diary/{pid}/entries", db)
        record("V5 _resolve_request_org_id(work-diary path) → org_id",
               resolved == org_id, f"resolved={resolved}")

        # ---------------- V6 expired org → mutations 402 ----------------
        org2 = f"probe-d3-org2-{tag}"
        pid2 = f"probe-d3-p2-{tag}"
        pm2 = f"probe-d3-pm2-{tag}"
        await db.organizations.insert_one({"id": org2, "name": "ארגון פג", "owner_user_id": pm2})
        await db.subscriptions.insert_one({
            "org_id": org2, "status": "expired",
            "paid_until": (datetime.now(IL_TZ) - timedelta(days=10)).isoformat(),
        })
        await db.projects.insert_one({"id": pid2, "name": "פרויקט פג", "org_id": org2, "deletedAt": None})
        await db.users.insert_one({"id": pm2, "role": "project_manager", "full_name": "מנהל פג",
                                   "user_status": "active", "session_version": 0})
        await db.organization_memberships.insert_one(
            {"id": f"om9-{tag}", "org_id": org2, "user_id": pm2, "role": "member"})
        await db.project_memberships.insert_one(
            {"id": f"m9-{tag}", "project_id": pid2, "user_id": pm2, "role": "project_manager"})
        pm2_h = {"Authorization": f"Bearer {_create_token(pm2, 'project_manager')}"}
        r = await c.post(f"/api/work-diary/{pid2}/entries", json={"diary_date": today}, headers=pm2_h)
        record("V6 expired-org PM POST create → 402 (paywall)",
               r.status_code == 402, f"status={r.status_code}")

    # cleanup
    await db.projects.delete_many({"id": {"$in": [pid, pid2]}})
    await db.organizations.delete_many({"id": {"$in": [org_id, org2]}})
    await db.subscriptions.delete_many({"org_id": {"$in": [org_id, org2]}})
    await db.users.delete_many({"id": {"$in": [pm_id, owner_id, contractor_id, stranger_id, sa_id, pm2]}})
    await db.organization_memberships.delete_many({"org_id": {"$in": [org_id, org2]}})
    await db.project_memberships.delete_many({"project_id": {"$in": [pid, pid2]}})
    await db.work_diary_entries.delete_many({"project_id": {"$in": [pid, pid2]}})
    await db.audit_events.delete_many({"entity_id": eid})

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*50}\nTOTAL: {len(RESULTS)}  PASS: {len(RESULTS)-len(fails)}  FAIL: {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
