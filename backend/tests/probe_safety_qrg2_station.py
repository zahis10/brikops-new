"""FUNCTIONAL probes for BATCH qrg2-station — guard station v1.

Same in-process harness as probe_safety_qrg1.py: REAL FastAPI app, real
local Mongo, real JWTs. Public station endpoints hit with NO auth header.

Covers the spec's V1 list:
  S1 lifecycle — ensure idempotent (2x ensure -> same token); rotate ->
     old station meta/check -> neutral 404; revoke -> 404; re-ensure after
     revoke works; single-active enforced.
  S2 PARITY — same worker token via public /api/gate and via station
     /check -> identical green/red decision (green + blocked + expired).
  S3 guest — unsigned -> red reason; signed today -> green; wrong-day -> red.
  S4 cross-project IDOR — foreign worker token / foreign worker_id /
     other-project search ALL neutral-invalid or absent.
  S5 search — 1 char -> []; regex metachars safe; <=8 items; items carry
     ONLY the three allowed fields.
  S6 photos — photo_display_url present for a worker WITH a photo; the raw
     storage ref NEVER appears in any station response.
  S7 logging — station checks write gate_scan_log rows with
     scanned_via/station_token_id; existing (public-gate) rows keep their
     shape (no station keys).
  S8 throttles — bad-token spray from one IP -> 404s then 429 (IP
     backstop); >30 rapid station requests -> NO global-limiter 429
     (middleware exemption B4 proven).
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_ENABLED"] = "false"

import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


STATION_ALLOWED_CHECK_KEYS = {"result", "kind", "name", "photo_display_url", "reasons"}
SEARCH_ITEM_KEYS = {"worker_id", "name", "photo_display_url"}
INVALID_BODY = {"result": "invalid", "reasons": ["קוד לא תקף"]}


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-st-org-{tag}"
    proj = f"probe-st-p1-{tag}"      # the station's project
    proj2 = f"probe-st-p2-{tag}"     # FOREIGN project (IDOR checks)
    pm_id = f"probe-st-pm-{tag}"

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_one(
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97250{int(tag[:6], 16) % 9000000 + 1000000}",
         "last_login_at": now_iso})
    await db.organization_memberships.insert_one(
        {"id": f"st-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_many([
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"},
        {"id": proj2, "org_id": org, "name": f"פרויקט זר {tag}", "status": "active"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"st-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"st-pm2-{tag}", "project_id": proj2, "user_id": pm_id, "role": "project_manager"},
    ])

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
    WORKERS = f"/api/safety/{proj}/workers"
    TMPL = f"/api/safety/{proj}/induction-template"
    CONDUCT = f"/api/safety/{proj}/induction/conduct"
    ST_ADMIN = f"/api/safety/{proj}/gate-station"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe",
                                 timeout=60) as c:
        # every public station call carries a per-section XFF so the per-IP
        # backstop (120/min) never bleeds between sections.
        def ip(n):
            return {"x-forwarded-for": f"10.9.{n}.7"}

        # ============ S1 — station lifecycle ============
        print("S1 — lifecycle")
        r1 = await c.post(f"{ST_ADMIN}/ensure", headers=pm_h)
        r2 = await c.post(f"{ST_ADMIN}/ensure", headers=pm_h)
        st_url1 = r1.json().get("station_url", "")
        record("S1a ensure -> 200 + /station/ url",
               r1.status_code == 200 and "/station/" in st_url1, f"{r1.status_code}")
        record("S1b ensure idempotent (same url back)",
               r2.status_code == 200 and r2.json().get("station_url") == st_url1)
        st_tok1 = st_url1.rsplit("/", 1)[-1]
        record("S1c station token >=32 chars", len(st_tok1) >= 32, f"len={len(st_tok1)}")

        rm = await c.get(f"/api/station/{st_tok1}/meta", headers=ip(1))
        record("S1d meta -> 200 + project_name (no auth)",
               rm.status_code == 200 and rm.json().get("project_name") == f"פרויקט {tag}",
               rm.text[:120])
        record("S1e meta has noindex header",
               rm.headers.get("x-robots-tag") == "noindex, nofollow")

        r = await c.get(f"{ST_ADMIN}", headers=pm_h)
        record("S1f GET status -> exists true", r.status_code == 200
               and r.json().get("exists") is True and r.json().get("station_url") == st_url1)

        rr = await c.post(f"{ST_ADMIN}/rotate", headers=pm_h)
        st_tok2 = rr.json().get("station_url", "").rsplit("/", 1)[-1]
        record("S1g rotate -> 200 + NEW token", rr.status_code == 200
               and st_tok2 and st_tok2 != st_tok1)
        rm_old = await c.get(f"/api/station/{st_tok1}/meta", headers=ip(1))
        rc_old = await c.get(f"/api/station/{st_tok1}/check",
                             params={"code": "x" * 32}, headers=ip(1))
        record("S1h old token meta+check -> neutral 404",
               rm_old.status_code == 404 and rc_old.status_code == 404
               and rm_old.json().get("detail") == "עמדה לא תקפה")
        rm_new = await c.get(f"/api/station/{st_tok2}/meta", headers=ip(1))
        record("S1i new token meta -> 200", rm_new.status_code == 200)
        n_active = await db.gate_station_tokens.count_documents(
            {"project_id": proj, "status": "active"})
        record("S1j single active station per project", n_active == 1, f"n={n_active}")

        rv = await c.post(f"{ST_ADMIN}/revoke", headers=pm_h)
        rm2 = await c.get(f"/api/station/{st_tok2}/meta", headers=ip(1))
        r = await c.get(f"{ST_ADMIN}", headers=pm_h)
        record("S1k revoke -> revoked; meta 404; status exists=false",
               rv.status_code == 200 and rm2.status_code == 404
               and r.json().get("exists") is False)
        r3 = await c.post(f"{ST_ADMIN}/ensure", headers=pm_h)
        st_tok = r3.json().get("station_url", "").rsplit("/", 1)[-1]
        record("S1l re-ensure after revoke -> fresh working token",
               r3.status_code == 200 and st_tok not in (st_tok1, st_tok2)
               and (await c.get(f"/api/station/{st_tok}/meta", headers=ip(1))).status_code == 200)
        st_doc = await db.gate_station_tokens.find_one(
            {"token": st_tok, "status": "active"}, {"_id": 0})

        # QR PNG (authed)
        r = await c.get(f"{ST_ADMIN}/qr.png", headers=pm_h)
        record("S1m station qr.png -> real PNG",
               r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n")

        # ============ seed workers ============
        r = await c.post(WORKERS, json={
            "full_name": f"עובד ירוק {tag}", "phone": "0507700011",
            "photo_ref": f"safety/{proj}/photo-{tag}.jpg",
        }, headers=pm_h)
        assert r.status_code == 201, f"create worker failed {r.status_code} {r.text[:300]}"
        w_green = r.json()["id"]
        wet_green = await db.worker_entry_tokens.find_one(
            {"project_id": proj, "worker_id": w_green, "status": "active"}, {"_id": 0})

        r = await c.put(TMPL, json={"sections": [{"title": "סעיף", "body": "תוכן"}]},
                        headers=pm_h)
        assert r.status_code == 200, r.text[:200]
        exp_far = (date.today() + timedelta(days=200)).isoformat()
        r = await c.post(CONDUCT, data={
            "worker_id": w_green, "language_choice": "he", "expires_at": exp_far,
            "signer_name": "עובד", "signature_type": "typed", "typed_name": "עובד",
        }, headers=pm_h)
        assert r.status_code == 201, f"conduct failed {r.status_code} {r.text[:300]}"

        # blocked worker
        r = await c.post(WORKERS, json={"full_name": f"עובד חסום {tag}"}, headers=pm_h)
        w_blocked = r.json()["id"]
        await c.patch(f"{WORKERS}/{w_blocked}/block",
                      json={"is_blocked": True, "reason": "הפרה"}, headers=pm_h)
        wet_blocked = await db.worker_entry_tokens.find_one(
            {"project_id": proj, "worker_id": w_blocked, "status": "active"}, {"_id": 0})

        # expired-induction worker
        r = await c.post(WORKERS, json={"full_name": f"עובד פג {tag}"}, headers=pm_h)
        w_exp = r.json()["id"]
        exp_past = (date.today() - timedelta(days=5)).isoformat()
        await db.safety_trainings.insert_one({
            "id": f"st-tr-exp-{tag}", "project_id": proj, "worker_id": w_exp,
            "training_type": INDUCTION_TRAINING_TYPE, "trained_at": now_iso,
            "expires_at": exp_past, "worker_signature": "x",
            "created_at": now_iso, "created_by": pm_id, "deletedAt": None,
        })
        wet_exp = await db.worker_entry_tokens.find_one(
            {"project_id": proj, "worker_id": w_exp, "status": "active"}, {"_id": 0})

        # FOREIGN project worker (IDOR)
        r = await c.post(f"/api/safety/{proj2}/workers",
                         json={"full_name": f"עובד זר {tag}"}, headers=pm_h)
        w_foreign = r.json()["id"]
        wet_foreign = await db.worker_entry_tokens.find_one(
            {"project_id": proj2, "worker_id": w_foreign, "status": "active"}, {"_id": 0})

        async def st_check(code, n=2):
            return await c.get(f"/api/station/{st_tok}/check",
                               params={"code": code}, headers=ip(n))

        # ============ S2 — worker parity ============
        print("S2 — worker parity (public gate vs station)")
        for label, wet, worker_name in (
            ("green", wet_green, f"עובד ירוק {tag}"),
            ("blocked", wet_blocked, f"עובד חסום {tag}"),
            ("expired", wet_exp, f"עובד פג {tag}"),
        ):
            rg = await c.get(f"/api/gate/{wet['token']}")
            rs = await st_check(wet["token"])
            g, s = rg.json(), rs.json()
            same = ((g.get("state") == "green") == (s.get("result") == "green"))
            record(f"S2 {label}: gate={g.get('state')} station={s.get('result')} — parity",
                   rg.status_code == 200 and rs.status_code == 200 and same,
                   f"gate={g.get('state')}/{g.get('reason')} st={s.get('result')}")
            record(f"S2 {label}: station payload keys minimal + kind=worker",
                   set(s.keys()) <= STATION_ALLOWED_CHECK_KEYS
                   and s.get("kind") == "worker" and s.get("name") == worker_name,
                   str(sorted(s.keys())))
        # station accepts the FULL gate URL too
        rs = await st_check(f"https://example.com/gate/{wet_green['token']}")
        record("S2d full gate URL scanned -> same green",
               rs.json().get("result") == "green")
        # red reasons are Hebrew
        rs = await st_check(wet_blocked["token"])
        record("S2e blocked reasons Hebrew",
               rs.json().get("result") == "red"
               and any("חסום" in x for x in rs.json().get("reasons", [])),
               str(rs.json().get("reasons")))
        rs = await st_check(wet_exp["token"])
        record("S2f expired reason carries the date",
               rs.json().get("result") == "red"
               and any(exp_past in x for x in rs.json().get("reasons", [])),
               str(rs.json().get("reasons")))

        # ============ S3 — guest ============
        print("S3 — guest passes")
        r = await c.post(f"/api/safety/{proj}/guest-passes",
                         json={"guest_name": f"אורח {tag}", "guest_company": "חברה"},
                         headers=pm_h)
        assert r.status_code == 201, r.text[:300]
        gp_unsigned = r.json()
        rs = await st_check(gp_unsigned["token"], n=3)
        j = rs.json()
        record("S3a unsigned guest -> red + briefing reason",
               j.get("result") == "red" and j.get("kind") == "guest"
               and "תדריך" in " ".join(j.get("reasons", [])), str(j)[:150])

        # signed-today guest: sign directly in db (the PNG sign flow is
        # covered by probe_safety_qrg_guest.py)
        await db.guest_entry_passes.update_one(
            {"id": gp_unsigned["id"]},
            {"$set": {"briefing.signed": True, "briefing.signed_at": now_iso}})
        rs = await st_check(gp_unsigned["token"], n=3)
        j = rs.json()
        record("S3b signed today -> GREEN + guest name",
               j.get("result") == "green" and j.get("kind") == "guest"
               and j.get("name") == f"אורח {tag}", str(j)[:150])

        # wrong-day pass (tomorrow), signed
        tomorrow = (date.today() + timedelta(days=2)).isoformat()
        r = await c.post(f"/api/safety/{proj}/guest-passes",
                         json={"guest_name": "אורח מחר", "guest_company": "יועץ",
                               "valid_on": tomorrow},
                         headers=pm_h)
        gp_tmrw = r.json()
        await db.guest_entry_passes.update_one(
            {"id": gp_tmrw["id"]}, {"$set": {"briefing.signed": True}})
        rs = await st_check(gp_tmrw["token"], n=3)
        j = rs.json()
        record("S3c wrong-day -> red date reason",
               j.get("result") == "red"
               and "בתוקף" in " ".join(j.get("reasons", [])), str(j)[:150])

        # ============ S4 — cross-project IDOR ============
        print("S4 — cross-project neutrality")
        rs = await st_check(wet_foreign["token"], n=4)
        record("S4a foreign worker token -> SAME neutral invalid",
               rs.status_code == 200 and rs.json() == INVALID_BODY, rs.text[:120])
        r = await c.get(f"/api/station/{st_tok}/check-worker",
                        params={"worker_id": w_foreign}, headers=ip(4))
        record("S4b foreign worker_id via check-worker -> neutral invalid",
               r.json() == INVALID_BODY, r.text[:120])
        r = await c.get(f"/api/station/{st_tok}/search",
                        params={"q": "עובד זר"}, headers=ip(4))
        record("S4c search never returns other-project workers",
               r.status_code == 200 and r.json().get("items") == [])
        rs = await st_check("totally-bogus-token-" + "z" * 20, n=4)
        record("S4d unknown token -> byte-identical neutral invalid",
               rs.json() == INVALID_BODY)

        # ============ S5 — search contract ============
        print("S5 — manual search")
        r = await c.get(f"/api/station/{st_tok}/search", params={"q": "ע"}, headers=ip(5))
        record("S5a 1-char query -> []", r.json().get("items") == [])
        r = await c.get(f"/api/station/{st_tok}/search",
                        params={"q": "עובד .*(["}, headers=ip(5))
        record("S5b regex metachars safe (200, no crash)",
               r.status_code == 200 and r.json().get("items") == [], r.text[:100])
        # >8 matches -> capped at 8
        many = [{"id": f"st-many-{i}-{tag}", "project_id": proj,
                 "full_name": f"רבים בדיקה {i}", "deletedAt": None,
                 "created_at": now_iso} for i in range(10)]
        await db.safety_workers.insert_many(many)
        r = await c.get(f"/api/station/{st_tok}/search",
                        params={"q": "רבים בדיקה"}, headers=ip(5))
        items = r.json().get("items", [])
        record("S5c <=8 items cap", len(items) == 8, f"n={len(items)}")
        record("S5d items carry ONLY worker_id/name/photo_display_url",
               all(set(it.keys()) == SEARCH_ITEM_KEYS for it in items),
               str(sorted(items[0].keys())) if items else "no items")
        r = await c.get(f"/api/station/{st_tok}/search",
                        params={"q": f"עובד ירוק {tag}"}, headers=ip(5))
        hit = (r.json().get("items") or [{}])[0]
        record("S5e finds the green worker by name", hit.get("worker_id") == w_green)

        # manual check-worker parity for the green worker
        r = await c.get(f"/api/station/{st_tok}/check-worker",
                        params={"worker_id": w_green}, headers=ip(5))
        j = r.json()
        record("S5f check-worker(green) -> green, same shape",
               j.get("result") == "green" and j.get("kind") == "worker"
               and set(j.keys()) <= STATION_ALLOWED_CHECK_KEYS, str(j)[:150])

        # ============ S6 — photos ============
        print("S6 — photo privacy")
        raw_ref = f"safety/{proj}/photo-{tag}.jpg"
        rs = await st_check(wet_green["token"], n=6)
        j = rs.json()
        record("S6a green worker WITH photo -> photo_display_url present",
               j.get("result") == "green" and bool(j.get("photo_display_url")),
               str(j.get("photo_display_url"))[:80])
        # In FILES_STORAGE_BACKEND=local, generate_url returns local keys
        # as-is, so display URL == ref for local refs. The privacy contract
        # is: the ref surfaces ONLY through the photo_display_url field —
        # nowhere else in the JSON — and s3:// refs are NEVER leaked raw
        # (no creds here -> fail-soft None).
        r_search = await c.get(f"/api/station/{st_tok}/search",
                               params={"q": f"עובד ירוק {tag}"}, headers=ip(6))
        stripped = (rs.text + r_search.text).replace(
            j.get("photo_display_url") or "\x00", "")
        record("S6b raw ref appears ONLY as the photo_display_url value",
               raw_ref not in stripped, "")
        s3_ref = f"s3://safety/{proj}/s3-{tag}.jpg"
        await db.safety_workers.insert_one({
            "id": f"st-s3w-{tag}", "project_id": proj,
            "full_name": f"עובד ענן {tag}", "photo_ref": s3_ref,
            "deletedAt": None, "created_at": now_iso})
        r = await c.get(f"/api/station/{st_tok}/check-worker",
                        params={"worker_id": f"st-s3w-{tag}"}, headers=ip(6))
        record("S6c s3 ref NEVER leaked raw (fail-soft, no presign creds)",
               s3_ref not in r.text and r.json().get("photo_display_url") != s3_ref,
               str(r.json().get("photo_display_url"))[:80])

        # ============ S7 — scan logging ============
        print("S7 — scan log rows")
        st_rows = [x async for x in db.gate_scan_log.find(
            {"project_id": proj, "scanned_via": {"$in": ["station", "station-manual"]}},
            {"_id": 0})]
        record("S7a station rows written with scanned_via + station_token_id",
               len(st_rows) >= 5 and all(x.get("station_token_id") for x in st_rows),
               f"n={len(st_rows)}")
        record("S7b manual checks logged as station-manual",
               any(x.get("scanned_via") == "station-manual" for x in st_rows))
        # a PUBLIC gate hit still writes the byte-compatible row (no station keys)
        await c.get(f"/api/gate/{wet_green['token']}")
        pub_row = await db.gate_scan_log.find_one(
            {"project_id": proj, "worker_id": w_green,
             "scanned_via": {"$exists": False}}, {"_id": 0}, sort=[("ts", -1)])
        record("S7c public gate rows unchanged (no station keys)",
               bool(pub_row) and "station_token_id" not in pub_row
               and set(pub_row.keys()) <= {"id", "project_id", "worker_id",
                                           "token_id", "ts", "result", "reasons"},
               str(sorted(pub_row.keys())) if pub_row else "missing")

        # ============ S8 — throttles + B4 exemption ============
        print("S8 — throttles")
        # B4: >30 rapid station hits from ONE ip must NOT hit the global
        # /api limiter (which fires way below our 120/min IP backstop).
        codes = []
        for _ in range(35):
            rr35 = await c.get(f"/api/station/{st_tok}/meta", headers=ip(8))
            codes.append(rr35.status_code)
        record("S8a 35 rapid station hits -> all 200 (global limiter exempt, B4)",
               all(x == 200 for x in codes), f"codes={sorted(set(codes))}")

        # IP backstop: spray bad tokens from a FRESH ip -> 404s then 429
        spray_ip = {"x-forwarded-for": "10.9.99.99"}
        statuses = []
        for i in range(125):
            rr = await c.get(f"/api/station/bad-token-{i:04d}-{'q' * 20}/meta",
                             headers=spray_ip)
            statuses.append(rr.status_code)
        record("S8b bad-token spray -> 404s then 429 (IP backstop)",
               statuses[0] == 404 and statuses[-1] == 429
               and 429 in statuses and statuses.index(429) >= 100,
               f"first429@{statuses.index(429) if 429 in statuses else 'none'}")
        record("S8c 429 body is Hebrew throttle message",
               "יותר מדי" in rr.text, rr.text[:100])

    # cleanup
    for coll, q in [
        ("organizations", {"id": org}), ("subscriptions", {"org_id": org}),
        ("users", {"id": pm_id}), ("organization_memberships", {"org_id": org}),
        ("projects", {"org_id": org}),
        ("project_memberships", {"project_id": {"$in": [proj, proj2]}}),
        ("safety_workers", {"project_id": {"$in": [proj, proj2]}}),
        ("worker_entry_tokens", {"project_id": {"$in": [proj, proj2]}}),
        ("gate_station_tokens", {"project_id": {"$in": [proj, proj2]}}),
        ("guest_entry_passes", {"project_id": proj}),
        ("gate_scan_log", {"project_id": {"$in": [proj, proj2]}}),
        ("safety_trainings", {"project_id": proj}),
        ("induction_templates", {"project_id": proj}),
        ("audit_events", {"actor_user_id": pm_id}),
    ]:
        await db[coll].delete_many(q)

    n_pass = sum(1 for _, ok in RESULTS if ok)
    print(f"\n=== qrg2-station probe: {n_pass}/{len(RESULTS)} passed ===")
    if n_pass != len(RESULTS):
        for name, ok in RESULTS:
            if not ok:
                print(f"  FAILED: {name}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
