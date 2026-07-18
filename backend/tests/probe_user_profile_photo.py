"""FUNCTIONAL HTTP probes — BATCH visual-user-panel (user profile photo).

Drives the REAL FastAPI app in-process (httpx ASGITransport) with a REAL
local Mongo, REAL local object storage and a REAL JWT minted with the
app's own _create_token. Verifies the full contract of:
  POST   /api/auth/me/photo   (upload → re-encode → store)
  DELETE /api/auth/me/photo
  GET    /api/auth/me         (profile_photo_display_url)

Covered (spec V1):
  - valid jpg 2000x1500 → 200 + photo_display_url; /auth/me shows field;
    stored bytes are JPEG with max side ≤512 (re-encode PROVEN by
    decoding the stored file);
  - png + webp → 200;
  - oversized (>5MB) → 413;
  - .txt / wrong content-type → 422;
  - corrupt image bytes with image/jpeg content-type → 422 Hebrew;
  - unauthenticated → 401;
  - raw stored ref never in any response JSON;
  - DELETE → 204, /auth/me field null; DELETE again → 404;
  - second upload replaces the ref (different key).
"""
import os
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local
os.environ["DB_NAME"] = "contractor_ops"
os.environ["TRANSLATE_MOCK"] = "1"
os.environ["WHATSAPP_ACCESS_TOKEN"] = ""
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = ""

import io
import sys
import uuid
import asyncio
import json as _json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from PIL import Image
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def make_image_bytes(fmt, size=(2000, 1500), color=(180, 90, 20)):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    tag = uuid.uuid4().hex[:8]
    uid = f"probe-photo-{tag}"

    org_id = f"probe-photo-org-{tag}"
    await db.organizations.insert_one({
        "id": org_id, "name": f"ארגון בדיקה {tag}", "owner_user_id": uid,
    })
    await db.subscriptions.insert_one({
        "org_id": org_id, "status": "active",
        "paid_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    })
    await db.users.insert_one({
        "id": uid, "role": "project_manager", "name": "מנהל תמונה",
        "user_status": "active", "session_version": 0,
    })
    await db.organization_memberships.insert_one({
        "id": f"om-{tag}", "org_id": org_id, "user_id": uid, "role": "member",
    })

    h = {"Authorization": f"Bearer {_create_token(uid, 'project_manager')}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe") as c:

        # 1. valid jpg 2000x1500 → 200 + photo_display_url
        jpg = make_image_bytes("JPEG")
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("me.jpg", jpg, "image/jpeg")}, headers=h)
        ok = r.status_code == 200 and bool(r.json().get("photo_display_url"))
        record("upload valid jpg 2000x1500 → 200 + photo_display_url", ok,
               f"status={r.status_code} body={r.text[:120]}")

        # raw ref never in response
        doc = await db.users.find_one({"id": uid}, {"_id": 0, "profile_photo_ref": 1})
        ref1 = (doc or {}).get("profile_photo_ref", "")
        record("stored ref persisted in users doc", bool(ref1), f"ref={'<set>' if ref1 else '<missing>'}")
        # Raw-ref secrecy: in S3 mode the ref is "s3://<key>" and must never
        # appear in responses (only presigned URLs). In LOCAL mode the ref
        # IS the public serving path (/api/uploads/...) by design — identical
        # to the worker-photo pattern — so the invariant is: no "s3://" ref
        # shape ever leaks, and the ref round-trips through generate_url.
        record('no "s3://" ref shape in upload response', "s3://" not in r.text)

        # /auth/me → display url present, raw ref absent
        r = await c.get("/api/auth/me", headers=h)
        me = r.json()
        record("/auth/me → profile_photo_display_url present",
               r.status_code == 200 and bool(me.get("profile_photo_display_url")),
               f"status={r.status_code}")
        record('no "s3://" ref shape in /auth/me JSON', "s3://" not in _json.dumps(me))

        # stored bytes: decode → JPEG, max side ≤512 (re-encode proven)
        # local mode ref = "/api/uploads/<key>"
        key = ref1.replace("/api/uploads/", "", 1)
        from services.object_storage import _LOCAL_UPLOADS_ROOT
        stored_path = _LOCAL_UPLOADS_ROOT / key
        try:
            simg = Image.open(stored_path)
            simg.load()
            ok = simg.format == "JPEG" and max(simg.width, simg.height) <= 512
            record("stored bytes JPEG + max side ≤512 (decoded)",
                   ok, f"format={simg.format} size={simg.width}x{simg.height}")
        except Exception as e:
            record("stored bytes JPEG + max side ≤512 (decoded)", False, str(e))

        # FIX1: EXIF Orientation=6 (iPhone-style) must be APPLIED to the
        # pixels before stripping — stored image comes out portrait.
        buf = io.BytesIO()
        oimg = Image.new("RGB", (800, 600), (30, 120, 200))
        ex = Image.Exif()
        ex[0x0112] = 6
        oimg.save(buf, format="JPEG", exif=ex)
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("rot.jpg", buf.getvalue(), "image/jpeg")}, headers=h)
        okrot = False
        detail = f"status={r.status_code}"
        if r.status_code == 200:
            doc = await db.users.find_one({"id": uid}, {"_id": 0, "profile_photo_ref": 1})
            rkey = (doc or {}).get("profile_photo_ref", "").replace("/api/uploads/", "", 1)
            from services.object_storage import _LOCAL_UPLOADS_ROOT as _ROOT
            try:
                simg2 = Image.open(_ROOT / rkey)
                simg2.load()
                orient = simg2.getexif().get(0x0112)
                okrot = (simg2.height > simg2.width) and orient in (None, 1)
                detail = f"size={simg2.width}x{simg2.height} orientation_tag={orient}"
            except Exception as e:
                detail = str(e)
        record("EXIF Orientation=6 applied → stored portrait, no tag", okrot, detail)

        # 2. png + webp → 200
        png = make_image_bytes("PNG", size=(800, 600))
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("me.png", png, "image/png")}, headers=h)
        record("upload png → 200", r.status_code == 200, f"status={r.status_code}")

        webp = make_image_bytes("WEBP", size=(700, 900))
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("me.webp", webp, "image/webp")}, headers=h)
        record("upload webp → 200", r.status_code == 200, f"status={r.status_code}")

        # second upload replaces the ref (different key)
        doc = await db.users.find_one({"id": uid}, {"_id": 0, "profile_photo_ref": 1})
        ref2 = (doc or {}).get("profile_photo_ref", "")
        record("re-upload replaces ref (different key)", bool(ref2) and ref2 != ref1)

        # 3. oversized > 5MB → 413
        big = b"\xff\xd8\xff" + b"\x00" * (5 * 1024 * 1024 + 10)
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("big.jpg", big, "image/jpeg")}, headers=h)
        record("oversized >5MB → 413", r.status_code == 413,
               f"status={r.status_code} detail={r.json().get('detail', '')[:60]}")

        # 4. .txt / wrong content-type → 422
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("notes.txt", b"hello", "text/plain")}, headers=h)
        record(".txt upload → 422", r.status_code == 422, f"status={r.status_code}")

        r = await c.post("/api/auth/me/photo",
                         files={"file": ("me.jpg", jpg, "application/pdf")}, headers=h)
        record("wrong content-type → 422", r.status_code == 422, f"status={r.status_code}")

        # 5. corrupt bytes with image/jpeg type → 422 Hebrew
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("bad.jpg", b"\xff\xd8\xffnot-an-image", "image/jpeg")},
                         headers=h)
        record('corrupt bytes → 422 "פורמט תמונה לא נתמך"',
               r.status_code == 422 and r.json().get("detail") == "פורמט תמונה לא נתמך",
               f"status={r.status_code} detail={r.json().get('detail', '')}")

        # 6. unauthenticated → 401
        r = await c.post("/api/auth/me/photo",
                         files={"file": ("me.jpg", jpg, "image/jpeg")})
        record("unauthenticated upload → 401", r.status_code == 401, f"status={r.status_code}")
        r = await c.delete("/api/auth/me/photo")
        record("unauthenticated delete → 401", r.status_code == 401, f"status={r.status_code}")

        # 7. DELETE → 204; /auth/me field null; DELETE again → 404
        r = await c.delete("/api/auth/me/photo", headers=h)
        record("DELETE photo → 204", r.status_code == 204, f"status={r.status_code}")

        r = await c.get("/api/auth/me", headers=h)
        record("/auth/me after delete → field null",
               r.status_code == 200 and r.json().get("profile_photo_display_url") is None)

        r = await c.delete("/api/auth/me/photo", headers=h)
        record('DELETE again → 404 "אין תמונת פרופיל"',
               r.status_code == 404 and r.json().get("detail") == "אין תמונת פרופיל",
               f"status={r.status_code}")

        # audit events written
        n = await db.audit_events.count_documents(
            {"action": "user_profile_photo_change", "entity_id": uid})
        record("audit events written (set x4 + clear)", n == 5, f"count={n}")

        # SECRECY HARD GUARD: if generate_url() falls back to the raw
        # s3:// ref (presign failure path), the helper must return None —
        # never leak the key.
        import services.object_storage as _os_mod
        _orig_gen = _os_mod.generate_url
        try:
            _os_mod.generate_url = lambda ref: f"s3://fake-bucket/{ref}"
            from contractor_ops.auth_router import _profile_photo_display
            leaked = _profile_photo_display("users/x/profile-abc.jpg")
            record("presign-failure fallback (s3:// ref) → None, never leaked",
                   leaked is None, f"got={leaked!r}")
            # end-to-end: upload a photo again, then /auth/me under the
            # broken presigner must return null, not the raw ref
            r = await c.post("/api/auth/me/photo", headers=h,
                             files={"file": ("a.jpg", make_image_bytes("JPEG", (300, 300)), "image/jpeg")})
            up_url = r.json().get("photo_display_url") if r.status_code == 200 else "ERR"
            record("upload under presign-failure → photo_display_url null",
                   r.status_code == 200 and up_url is None, f"got={up_url!r}")
            r = await c.get("/api/auth/me", headers=h)
            me_url = r.json().get("profile_photo_display_url")
            record("/auth/me under presign-failure → field null",
                   me_url is None, f"got={me_url!r}")
        finally:
            _os_mod.generate_url = _orig_gen

    # cleanup
    await db.users.delete_one({"id": uid})
    await db.organizations.delete_one({"id": org_id})
    await db.subscriptions.delete_one({"org_id": org_id})
    await db.organization_memberships.delete_many({"org_id": org_id})
    await db.audit_events.delete_many({"entity_id": uid})

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*60}\nRESULT: {len(RESULTS)-len(failed)}/{len(RESULTS)} passed")
    if failed:
        print("FAILED:")
        for name, _, detail in failed:
            print(f"  - {name} ({detail})")
        sys.exit(1)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
