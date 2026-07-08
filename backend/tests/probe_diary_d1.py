"""FUNCTIONAL probes for diary-d1 (Work Diary backend) — V1..V6.

Verification-only. Drives the REAL work_diary_router coroutines against a
REAL local Mongo (mongodb://localhost:27017 / contractor_ops) with REAL
local object-storage (FILES_STORAGE_BACKEND=local → save_bytes writes a
file and returns the storage ref; generate_url echoes it).

Harness scaffolding that is NOT under test is patched to no-op and disclosed:
  _check_project_access (project RBAC), check_upload_rate_limit,
  check_upload_bytes, check_storage_quota, record_upload (quota/rate-limit).
validate_upload (PNG extension/mime validation) is kept REAL.
require_roles is a FastAPI Depends factory — coroutines are called directly
with user=PM (project_manager), matching the p3c harness convention.

V7 (flag off/on boot + unique-index dup insert) lives in
probe_diary_d1_boot.py (fresh interpreter per flag value required).
"""
import os
os.environ.setdefault("FILES_STORAGE_BACKEND", "local")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "contractor_ops")

import io
import sys
import uuid
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from starlette.datastructures import UploadFile, Headers
from fastapi import HTTPException

from contractor_ops import work_diary_router as wd
from contractor_ops import router as cr
from contractor_ops.schemas import WorkDiaryCreate, WorkDiaryUpdate, WorkDiaryAddendumCreate
from contractor_ops.utils.timezone import IL_TZ

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000154a24f5f0000000049454e44ae426082"
)


def _png_upload():
    return UploadFile(
        file=io.BytesIO(_PNG),
        filename="sig.png",
        headers=Headers({"content-type": "image/png"}),
    )


PM = {"id": "probe-diary-pm", "role": "project_manager"}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pid = f"probe-d1-{uuid.uuid4().hex[:8]}"       # seeded safety data
    pid_empty = f"probe-d1e-{uuid.uuid4().hex[:8]}"  # empty-safety project
    today = datetime.now(IL_TZ).strftime("%Y-%m-%d")
    yesterday = (datetime.now(IL_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")

    # ---- seed safety data for pid (today's events) ----
    cid = f"c-{uuid.uuid4().hex[:8]}"
    wid = f"w-{uuid.uuid4().hex[:8]}"
    await db.project_companies.insert_one(
        {"id": cid, "project_id": pid, "name": "חברת בדיקה", "deletedAt": None})
    await db.safety_workers.insert_many([
        {"id": wid, "project_id": pid, "full_name": "עובד אחד", "company_id": cid, "deletedAt": None},
        {"id": f"w-{uuid.uuid4().hex[:8]}", "project_id": pid, "full_name": "עובד שניים",
         "company_id": None, "deletedAt": None},
    ])
    await db.safety_equipment.insert_many([
        {"id": f"eq-{uuid.uuid4().hex[:8]}", "project_id": pid, "internal_code": "EQ-1",
         "category": "מלגזה", "status": "active", "deletedAt": None},
        {"id": f"eq-{uuid.uuid4().hex[:8]}", "project_id": pid, "internal_code": "EQ-2",
         "category": "עגורן", "status": "decommissioned", "deletedAt": None},
    ])
    await db.safety_incidents.insert_one(
        {"id": f"inc-{uuid.uuid4().hex[:8]}", "project_id": pid, "incident_type": "near_miss",
         "description": "כמעט נפילה", "occurred_at": today, "deletedAt": None})
    await db.safety_tours.insert_one(
        {"id": f"tr-{uuid.uuid4().hex[:8]}", "project_id": pid, "tour_type": "weekly",
         "status": "completed", "tour_date": today, "deletedAt": None})
    await db.safety_documents.insert_many([
        {"id": f"d-{uuid.uuid4().hex[:8]}", "project_id": pid, "kind": "defect",
         "status": "open", "created_at": f"{today}T08:00:00+00:00", "updated_at": None, "deletedAt": None},
        {"id": f"d-{uuid.uuid4().hex[:8]}", "project_id": pid, "kind": "defect",
         "status": "resolved", "created_at": "2026-06-01T08:00:00+00:00",
         "updated_at": f"{today}T09:00:00+00:00", "deletedAt": None},
    ])
    await db.safety_trainings.insert_one(
        {"id": f"t-{uuid.uuid4().hex[:8]}", "project_id": pid, "worker_id": wid,
         "training_type": "עבודה בגובה", "trained_at": today, "deletedAt": None})

    patches = [
        patch.object(wd, "get_db", return_value=db),
        patch.object(cr, "get_db", return_value=db),  # _audit() resolves get_db in router module
        patch.object(wd, "_check_project_access", new=AsyncMock()),
        patch.object(wd, "check_upload_rate_limit", new=lambda *a, **k: None),
        patch.object(wd, "check_upload_bytes", new=lambda *a, **k: None),
        patch.object(wd, "check_storage_quota", new=AsyncMock()),
        patch.object(wd, "record_upload", new=AsyncMock()),
    ]
    for p in patches:
        p.start()

    try:
        # ================= V1: derivation =================
        e1 = await wd.create_diary_entry(pid, WorkDiaryCreate(diary_date=today), user=PM)
        v1_workers = e1.workers_by_company
        v1a = (sum(w["count"] for w in v1_workers) == 2
               and any(w["company_name"] == "חברת בדיקה" and w["count"] == 1 for w in v1_workers)
               and any(w["company_name"] == "ללא חברה" and w["count"] == 1 for w in v1_workers)
               and all(w["source"] == "derived" for w in v1_workers))
        record("V1 workers_by_company derived (2 workers, named + ללא חברה)", v1a,
               f"{v1_workers}")
        v1b = (len(e1.equipment_list) == 1 and e1.equipment_list[0]["internal_code"] == "EQ-1"
               and e1.equipment_list[0]["source"] == "derived")
        record("V1 equipment_list = active only (EQ-1, not decommissioned EQ-2)", v1b,
               f"{e1.equipment_list}")
        v1c = len(e1.subcontractors) == 1 and e1.subcontractors[0]["name"] == "חברת בדיקה"
        record("V1 subcontractors derived from project_companies", v1c, f"{e1.subcontractors}")
        v1d = len(e1.incidents_summary) == 1 and e1.incidents_summary[0]["incident_type"] == "near_miss"
        record("V1 incidents_summary: today's incident present", v1d, f"{e1.incidents_summary}")
        v1e = len(e1.tours_summary) == 1 and e1.tours_summary[0]["tour_type"] == "weekly"
        record("V1 tours_summary: today's tour present", v1e, f"{e1.tours_summary}")
        v1f = e1.defect_counts == {"opened": 1, "closed": 1, "source": "derived"}
        record("V1 defect_counts opened=1 closed=1 (documented heuristic)", v1f,
               f"{e1.defect_counts}")
        v1g = (len(e1.trainings_summary) == 1
               and e1.trainings_summary[0]["worker_name"] == "עובד אחד")
        record("V1 trainings_summary with resolved worker_name", v1g, f"{e1.trainings_summary}")

        # empty-safety project → all sections empty, entry valid (decision 9)
        e_empty = await wd.create_diary_entry(
            pid_empty, WorkDiaryCreate(diary_date=today), user=PM)
        v1h = (e_empty.workers_by_company == [] and e_empty.equipment_list == []
               and e_empty.subcontractors == [] and e_empty.incidents_summary == []
               and e_empty.tours_summary == [] and e_empty.trainings_summary == []
               and e_empty.defect_counts == {"opened": 0, "closed": 0, "source": "derived"}
               and e_empty.status == "draft")
        record("V1 empty-safety project → empty sections, valid entry (decision 9)", v1h,
               f"defect_counts={e_empty.defect_counts}")

        # no_work=true → skips derivation, description auto-filled
        e_nw = await wd.create_diary_entry(
            pid, WorkDiaryCreate(diary_date=yesterday, no_work=True, no_work_reason="גשם"),
            user=PM)
        v1i = (e_nw.no_work is True and e_nw.work_description == "לא בוצעה עבודה — גשם"
               and e_nw.workers_by_company == [] and e_nw.defect_counts is None)
        record("V1 no_work=true → derivation skipped, auto description", v1i,
               f"desc={e_nw.work_description!r}")

        # ================= V2: uniqueness =================
        try:
            await wd.create_diary_entry(pid, WorkDiaryCreate(diary_date=today), user=PM)
            record("V2 duplicate date → 409", False, "no exception raised")
        except HTTPException as ex:
            record("V2 duplicate date → 409", ex.status_code == 409 and "כבר קיים" in ex.detail,
                   f"{ex.status_code} {ex.detail}")
        v2b = e_empty.diary_date == today and e_empty.project_id == pid_empty
        record("V2 different projects, same date → both fine (index scope)", v2b,
               f"pid={e1.project_id[:14]}…, pid_empty={e_empty.project_id[:14]}…")

        # ================= V3: entered_late =================
        record("V3 create for yesterday → entered_late=true", e_nw.entered_late is True,
               f"entered_late={e_nw.entered_late}")
        record("V3 create for today → entered_late=false", e1.entered_late is False,
               f"entered_late={e1.entered_late}")
        # PATCH cannot flip it: field absent from WorkDiaryUpdate (extra ignored by model)
        upd_model = WorkDiaryUpdate(**{"entered_late": True, "work_description": "עבודות בטון"})
        v3c = "entered_late" not in upd_model.model_dump(exclude_unset=True)
        patched = await wd.update_diary_entry(pid, e1.id, upd_model, user=PM)
        record("V3 PATCH cannot flip entered_late (field ignored by model)",
               v3c and patched["entered_late"] is False,
               f"model keys={sorted(upd_model.model_dump(exclude_unset=True))}, "
               f"after={patched['entered_late']}")

        # ================= V4: draft PATCH / signed PATCH / refresh =================
        record("V4 draft PATCH works (work_description set)",
               patched["work_description"] == "עבודות בטון" and patched["updated_at"] is not None,
               f"desc={patched['work_description']!r}")

        # refresh-derived: manual item survives, derived count updates
        manual_item = {"company_name": "קבלן ידני", "count": 5, "source": "manual"}
        cur = await db.work_diary_entries.find_one({"id": e1.id}, {"_id": 0})
        await wd.update_diary_entry(
            pid, e1.id,
            WorkDiaryUpdate(workers_by_company=cur["workers_by_company"] + [manual_item]),
            user=PM)
        await db.safety_workers.insert_one(  # new worker appears after creation
            {"id": f"w-{uuid.uuid4().hex[:8]}", "project_id": pid, "full_name": "עובד שלוש",
             "company_id": cid, "deletedAt": None})
        refreshed = await wd.refresh_derived_sections(pid, e1.id, user=PM)
        r_workers = refreshed["workers_by_company"]
        v4b = (any(w.get("source") == "manual" and w["company_name"] == "קבלן ידני" for w in r_workers)
               and sum(w["count"] for w in r_workers if w["source"] == "derived") == 3)
        record("V4 refresh-derived: manual item survives, derived count 2→3", v4b,
               f"{r_workers}")
        v4c = refreshed["work_description"] == "עבודות בטון"
        record("V4 refresh-derived leaves manual free-text untouched", v4c,
               f"desc={refreshed['work_description']!r}")

        # ================= V5: signature =================
        # sign without work_description (no_work=false) → 422
        try:
            await wd.sign_diary_entry(
                pid_empty, e_empty.id, signer_name="מנהל", signature_type="canvas",
                typed_name=None, signature_image=_png_upload(), user=PM)
            record("V5 sign without work_description → 422", False, "no exception")
        except HTTPException as ex:
            record("V5 sign without work_description → 422",
                   ex.status_code == 422 and "תיאור עבודות" in ex.detail,
                   f"{ex.status_code} {ex.detail}")

        signed = await wd.sign_diary_entry(
            pid, e1.id, signer_name="דני מנהל", signature_type="canvas",
            typed_name=None, signature_image=_png_upload(), user=PM)
        stored = (await db.work_diary_entries.find_one({"id": e1.id})).get("worker_signature") or {}
        sig = signed.get("worker_signature") or {}
        # storage ref may carry a backend scheme prefix (e.g. s3://diaries/…);
        # the invariant (same as p3c) is: NOT a presigned http URL, key under
        # diaries/, and display_url never persisted.
        v5b = (bool(stored.get("signature_ref"))
               and not stored["signature_ref"].startswith("http")
               and "diaries/" in stored["signature_ref"]
               and "signature_display_url" not in stored)
        record("V5 canvas sign: key-only at rest (diaries/… ref, no display_url persisted)",
               v5b, f"ref={stored.get('signature_ref')!r}")
        record("V5 response + GET carry signature_display_url (per-GET presign)",
               bool(sig.get("signature_display_url"))
               and signed["status"] == "signed" and signed["signed_at"] is not None,
               f"display_url={str(sig.get('signature_display_url'))[:60]!r}")

        try:
            await wd.sign_diary_entry(
                pid, e1.id, signer_name="שני", signature_type="canvas",
                typed_name=None, signature_image=_png_upload(), user=PM)
            record("V5 second sign → 409", False, "no exception")
        except HTTPException as ex:
            record("V5 second sign → 409", ex.status_code == 409 and "כבר חתום" in ex.detail,
                   f"{ex.status_code} {ex.detail}")

        # atomic claim: pre-set signature on a DRAFT (race simulation) → 409
        await wd.update_diary_entry(pid_empty, e_empty.id,
                                    WorkDiaryUpdate(work_description="עבודה"), user=PM)
        await db.work_diary_entries.update_one(
            {"id": e_empty.id}, {"$set": {"worker_signature": {"name": "racer"}}})
        try:
            await wd.sign_diary_entry(
                pid_empty, e_empty.id, signer_name="מאחר", signature_type="typed",
                typed_name="מאחר", signature_image=None, user=PM)
            record("V5 atomic claim race (pre-set signature, draft) → 409", False, "no exception")
        except HTTPException as ex:
            record("V5 atomic claim race (pre-set signature, draft) → 409",
                   ex.status_code == 409, f"{ex.status_code} {ex.detail}")
        # ALSO assert the DB-level atomic filter itself claims nothing:
        upd = await db.work_diary_entries.update_one(
            {"id": e_empty.id, "project_id": pid_empty, "deletedAt": None,
             "status": "draft", "worker_signature": None},
            {"$set": {"status": "signed"}})
        record("V5 atomic filter matches 0 docs once signature exists",
               upd.modified_count == 0, f"modified={upd.modified_count}")

        # signed PATCH → 409 Hebrew (V4 requirement, needs a signed entry)
        try:
            await wd.update_diary_entry(pid, e1.id,
                                        WorkDiaryUpdate(work_description="שינוי אסור"), user=PM)
            record("V4 signed PATCH → 409 Hebrew", False, "no exception")
        except HTTPException as ex:
            record("V4 signed PATCH → 409 Hebrew",
                   ex.status_code == 409 and "תוספת בלבד" in ex.detail,
                   f"{ex.status_code} {ex.detail}")
        # refresh-derived on signed → 409 too
        try:
            await wd.refresh_derived_sections(pid, e1.id, user=PM)
            record("V4 refresh-derived on signed → 409", False, "no exception")
        except HTTPException as ex:
            record("V4 refresh-derived on signed → 409", ex.status_code == 409,
                   f"{ex.status_code} {ex.detail}")

        # ================= V6: addendum =================
        before = await db.work_diary_entries.find_one({"id": e1.id}, {"_id": 0})
        with_add = await wd.add_diary_addendum(
            pid, e1.id, WorkDiaryAddendumCreate(text="תוספת: הושלם קיר תומך"), user=PM)
        after = await db.work_diary_entries.find_one({"id": e1.id}, {"_id": 0})
        v6a = (len(with_add["addendums"]) == 1
               and with_add["addendums"][0]["text"] == "תוספת: הושלם קיר תומך"
               and with_add["addendums"][0]["created_by"] == PM["id"])
        record("V6 addendum on signed appends", v6a, f"{with_add['addendums']}")
        unchanged = all(
            before[k] == after[k] for k in before
            if k not in ("addendums",))
        record("V6 addendum never mutates sections (all other fields byte-equal)",
               unchanged, "diff keys=" + str(
                   [k for k in before if k != "addendums" and before[k] != after[k]]))
        try:
            # draft entry (e_nw is still draft)
            await wd.add_diary_addendum(
                pid, e_nw.id, WorkDiaryAddendumCreate(text="טיוטה"), user=PM)
            record("V6 addendum on draft → 409", False, "no exception")
        except HTTPException as ex:
            record("V6 addendum on draft → 409",
                   ex.status_code == 409 and "טיוטה" in ex.detail,
                   f"{ex.status_code} {ex.detail}")

        # ============ V5b: sign-vs-PATCH / sign-vs-refresh race closure ============
        # Deterministic race simulation: _get_entry_or_404 returns a STALE draft
        # snapshot while the DB doc is already signed → the atomic draft filter
        # (status:"draft" in update_one) must reject with 409, not mutate.
        e_race = await wd.create_diary_entry(
            pid, WorkDiaryCreate(diary_date="2026-01-05"), user=PM)
        stale_draft = await db.work_diary_entries.find_one({"id": e_race.id}, {"_id": 0})
        await db.work_diary_entries.update_one(
            {"id": e_race.id}, {"$set": {"status": "signed"}})  # concurrent signer won
        race_patch = patch.object(wd, "_get_entry_or_404", new=AsyncMock(return_value=dict(stale_draft)))
        race_patch.start()
        try:
            try:
                await wd.update_diary_entry(
                    pid, e_race.id, WorkDiaryUpdate(work_description="race"), user=PM)
                record("V5b race: PATCH after concurrent sign → 409 (atomic filter)", False,
                       "no exception")
            except HTTPException as ex:
                record("V5b race: PATCH after concurrent sign → 409 (atomic filter)",
                       ex.status_code == 409 and "תוספת בלבד" in ex.detail,
                       f"{ex.status_code} {ex.detail}")
            try:
                await wd.refresh_derived_sections(pid, e_race.id, user=PM)
                record("V5b race: refresh-derived after concurrent sign → 409", False,
                       "no exception")
            except HTTPException as ex:
                record("V5b race: refresh-derived after concurrent sign → 409",
                       ex.status_code == 409, f"{ex.status_code} {ex.detail}")
        finally:
            race_patch.stop()
        raw_race = await db.work_diary_entries.find_one({"id": e_race.id}, {"_id": 0})
        record("V5b race: signed doc NOT mutated by racing PATCH/refresh",
               raw_race["work_description"] is None and raw_race["updated_at"] is None,
               f"desc={raw_race['work_description']!r} updated_at={raw_race['updated_at']!r}")

    finally:
        for p in patches:
            p.stop()
        # cleanup probe data
        for coll in ("work_diary_entries", "safety_workers", "safety_equipment",
                     "safety_incidents", "safety_tours", "safety_documents",
                     "safety_trainings", "project_companies"):
            await db[coll].delete_many({"project_id": {"$in": [pid, pid_empty]}})
        await db.audit_log.delete_many({"payload.project_id": {"$in": [pid, pid_empty]}})

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*60}\nTOTAL: {len(RESULTS)} probes, {len(RESULTS)-len(failed)} PASS, {len(failed)} FAIL")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
