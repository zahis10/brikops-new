"""FUNCTIONAL probes for safety-p3c (training renewal + worker signature).

Verification-only. Drives the REAL safety_router coroutines against a REAL
local Mongo (mongodb://localhost:27017 / contractor_ops) with REAL local
object-storage (FILES_STORAGE_BACKEND=local → save_bytes writes a file and
returns the storage ref; generate_url echoes it).

Harness scaffolding that is NOT under test is patched to no-op and disclosed:
  _check_project_access (project RBAC), check_upload_rate_limit,
  check_upload_bytes, check_storage_quota, record_upload (quota/rate-limit).
validate_upload (PNG extension/mime validation) is kept REAL.
"""
import os
os.environ.setdefault("FILES_STORAGE_BACKEND", "local")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "contractor_ops")

import io
import sys
import uuid
import asyncio
from unittest.mock import patch, AsyncMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motor.motor_asyncio import AsyncIOMotorClient
from starlette.datastructures import UploadFile, Headers
from fastapi import HTTPException

from contractor_ops import safety_router as sr
from contractor_ops import router as cr
# Batch refactor-safety-split (Option A amendment, patch targets only): the
# trainings coroutines now live in contractor_ops.safety.trainings — patches
# must target the module where the functions are DEFINED, not the facade.
from contractor_ops.safety import trainings as st

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


# minimal valid 1x1 PNG
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


PM = {"id": "probe-pm", "role": "project_manager"}


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    pid = f"probe-p3c-{uuid.uuid4().hex[:8]}"
    wid = f"w-{uuid.uuid4().hex[:8]}"

    await db.safety_workers.insert_one({
        "id": wid, "project_id": pid, "full_name": "עובד בדיקה", "deletedAt": None,
    })

    patches = [
        patch.object(st, "get_db", return_value=db),
        patch.object(cr, "get_db", return_value=db),  # _audit() resolves get_db in router module
        patch.object(st, "_check_project_access", new=AsyncMock()),
        patch.object(st, "check_upload_rate_limit", new=lambda *a, **k: None),
        patch.object(st, "check_upload_bytes", new=lambda *a, **k: None),
        patch.object(st, "check_storage_quota", new=AsyncMock()),
        patch.object(st, "record_upload", new=AsyncMock()),
    ]
    for p in patches:
        p.start()

    try:
        # ---- create a training via the REAL endpoint ----
        created = await sr.create_training(
            pid,
            sr.SafetyTrainingCreate(worker_id=wid, training_type="עבודה בגובה", trained_at="2026-01-10"),
            user=PM,
        )
        tid = created.id
        raw = await db.safety_trainings.find_one({"id": tid})
        record("create sets worker_signature=None",
               raw.get("worker_signature") is None,
               f"worker_signature={raw.get('worker_signature')!r}")

        # ================= P1: canvas signature =================
        resp = await sr.sign_training(
            pid, tid, signer_name="דני", signature_type="canvas",
            typed_name=None, signature_image=_png_upload(), user=PM,
        )
        sig = resp.worker_signature or {}
        stored = (await db.safety_trainings.find_one({"id": tid})).get("worker_signature") or {}
        p1a = resp is not None and bool(sig.get("signature_display_url"))
        p1b = bool(stored.get("signature_ref")) and not stored["signature_ref"].startswith("http")
        p1c = "signature_display_url" not in stored  # display url NOT persisted, computed per-GET
        record("P1 canvas → response carries signature_display_url", p1a,
               f"display_url={sig.get('signature_display_url')!r}")
        record("P1 Mongo stores storage REF/KEY only (no presigned http)", p1b,
               f"stored ref={stored.get('signature_ref')!r}")
        record("P1 signature_display_url NOT persisted in Mongo", p1c,
               f"persisted keys={sorted(stored.keys())}")

        # ================= P2: re-sign → 409 =================
        try:
            await sr.sign_training(
                pid, tid, signer_name="דני2", signature_type="canvas",
                typed_name=None, signature_image=_png_upload(), user=PM,
            )
            record("P2 re-sign → 409", False, "no exception raised")
        except HTTPException as e:
            record("P2 re-sign → 409 'ההדרכה כבר חתומה'",
                   e.status_code == 409 and "כבר חתומה" in str(e.detail),
                   f"{e.status_code} {e.detail}")

        # ================= P3: legacy row WITHOUT the key =================
        lid = f"legacy-{uuid.uuid4().hex[:8]}"
        legacy = {
            "id": lid, "project_id": pid, "worker_id": wid,
            "training_type": "ריענון", "trained_at": "2026-02-01",
            "created_at": sr._now(), "created_by": PM["id"],
            "deletedAt": None, "deletedBy": None,
        }  # NOTE: intentionally NO 'worker_signature' key
        await db.safety_trainings.insert_one(legacy)
        assert "worker_signature" not in (await db.safety_trainings.find_one({"id": lid}))
        try:
            r3 = await sr.sign_training(
                pid, lid, signer_name="לגסי", signature_type="canvas",
                typed_name=None, signature_image=_png_upload(), user=PM,
            )
            record("P3 legacy row (missing key) → 200 (claim filter matches)",
                   bool((r3.worker_signature or {}).get("signature_ref")),
                   "signed ok")
        except HTTPException as e:
            record("P3 legacy row → 200", False, f"{e.status_code} {e.detail}")

        # ================= P4: typed signature =================
        t4 = await sr.create_training(
            pid, sr.SafetyTrainingCreate(worker_id=wid, training_type="עזרה ראשונה", trained_at="2026-03-01"),
            user=PM,
        )
        r4 = await sr.sign_training(
            pid, t4.id, signer_name="מנהל", signature_type="typed",
            typed_name="ישראל ישראלי", signature_image=None, user=PM,
        )
        s4 = r4.worker_signature or {}
        record("P4 typed → typed_name set, signature_ref None",
               s4.get("signature_type") == "typed" and s4.get("typed_name") == "ישראל ישראלי"
               and s4.get("signature_ref") is None,
               f"type={s4.get('signature_type')} typed_name={s4.get('typed_name')!r} ref={s4.get('signature_ref')!r}")

        # ================= P5: PATCH ignores worker_signature =================
        before5 = (await db.safety_trainings.find_one({"id": tid})).get("worker_signature")
        # FastAPI would build SafetyTrainingUpdate from the JSON body; extra keys dropped.
        payload5 = sr.SafetyTrainingUpdate(**{"training_type": "מעודכן", "worker_signature": {"name": "HACK"}})
        dumped = payload5.model_dump(exclude_unset=True)
        r5 = await sr.update_training(pid, tid, payload5, user=PM)
        after5 = (await db.safety_trainings.find_one({"id": tid})).get("worker_signature")
        record("P5 PATCH body worker_signature dropped by model + DB unchanged",
               "worker_signature" not in dumped and after5 == before5 and r5.training_type == "מעודכן",
               f"dumped_keys={sorted(dumped.keys())} unchanged={after5==before5}")

    finally:
        # cleanup probe rows
        await db.safety_trainings.delete_many({"project_id": pid})
        await db.safety_workers.delete_many({"project_id": pid})
        for p in patches:
            p.stop()

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"RESULT: {passed}/{len(RESULTS)} probes passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
