"""FUNCTIONAL probes for BATCH qrg1-entry-gate — worker entry QR gate.

Same in-process harness as probe_safety_ind2_fix4.py: REAL FastAPI app,
real local Mongo, real JWTs. Public gate endpoint hit with NO auth header.

Covers V1-V7 of the spec:
  V1  Token: created on worker create; unique idx; >=32 url-safe chars;
      ensure-on-demand for a pre-existing worker; revoked on worker delete
      -> page invalid.
  V2  Status matrix (public, no auth): green / red-induction (none+expired) /
      red-blocked / invalid (bad+revoked+deleted-worker, SAME neutral body) /
      yellow warnings. NEGATIVE assertions: no phone / id fields in payload.
  V3  Scan log row per hit incl. invalid; admin list gated (contractor 403,
      PM 200, outsider 403).
  V4  Block flow: PATCH toggles + audit event + gate red instantly; unblock
      restores green; contractor cannot block (403).
  V5  Rotation: new token works, old token invalid; QR PNG regenerated.
  V6  WA auto-send: flag off (default) -> ZERO calls to _send_wa_template;
      flag on -> wiring produces named params + https header image.
  V7  Throttle: burst > 60 -> 429; noindex header present on responses.
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_ENABLED"] = "false"
os.environ.pop("WA_ENTRY_QR_ENABLED", None)  # default off — V6 zero-calls

import sys
import re
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


PII_KEYS = ("phone", "id_number", "id_number_hash", "notes", "company_id")


def no_pii(payload: dict) -> bool:
    return not any(k in payload for k in PII_KEYS)


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE
    from contractor_ops.safety import gate as gate_mod
    from contractor_ops.safety import gate_public

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-qrg-org-{tag}"
    proj = f"probe-qrg-p1-{tag}"
    pm_id = f"probe-qrg-pm-{tag}"
    con_id = f"probe-qrg-con-{tag}"   # contractor — must be 403 on admin gate APIs
    out_id = f"probe-qrg-out-{tag}"   # PM with NO project membership

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
        {"id": out_id, "role": "project_manager", "full_name": "זר",
         "user_status": "active", "session_version": 0,
         "phone_e164": f"+97253{int(tag[:6],16)%9000000+1000000}", "last_login_at": now_iso},
    ])
    await db.organization_memberships.insert_one(
        {"id": f"qrg-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_many([
        {"id": f"qrg-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"qrg-pm2-{tag}", "project_id": proj, "user_id": con_id, "role": "contractor"},
    ])

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role="project_manager"):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    pm_h = h(pm_id)
    con_h = h(con_id, "contractor")
    out_h = h(out_id)

    WORKERS = f"/api/safety/{proj}/workers"
    TMPL = f"/api/safety/{proj}/induction-template"
    CONDUCT = f"/api/safety/{proj}/induction/conduct"

    # V6 instrumentation — count every _send_wa_template call.
    import contractor_ops.reminder_service as rs
    wa_calls = []
    real_send = rs._send_wa_template

    async def spy_send(*a, **kw):
        wa_calls.append((a, kw))
        return {"success": True, "dry_run": True, "provider_message_id": "spy"}
    rs._send_wa_template = spy_send

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:

        async def gate(token, headers=None):
            return await c.get(f"/api/gate/{token}", headers=headers or {})

        # =========== V1 — token lifecycle ===========
        print("V1 — token lifecycle")
        r = await c.post(WORKERS, json={
            "full_name": f"עובד ראשי {tag}", "phone": "0507700009",
        }, headers=pm_h)
        assert r.status_code == 201, f"create worker failed {r.status_code} {r.text[:300]}"
        w1 = r.json()["id"]
        tok1 = await db.worker_entry_tokens.find_one(
            {"project_id": proj, "worker_id": w1, "status": "active"}, {"_id": 0})
        record("V1a token auto-created on worker create", bool(tok1))
        record("V1b token >=32 url-safe chars",
               bool(tok1) and len(tok1["token"]) >= 32
               and re.fullmatch(r"[A-Za-z0-9_-]+", tok1["token"]) is not None,
               f"len={len(tok1['token']) if tok1 else 0}")
        record("V1c token doc has org/project/worker + qr_ref",
               bool(tok1) and tok1.get("org_id") == org and tok1.get("qr_ref"))

        # unique index on token
        dup_err = None
        try:
            await db.worker_entry_tokens.insert_one(
                {"id": "dup", "token": tok1["token"], "status": "active"})
        except Exception as e:
            dup_err = e
        record("V1d unique index rejects duplicate token", dup_err is not None)

        # ensure-on-demand for a PRE-EXISTING worker (inserted directly)
        w_pre = f"qrg-pre-{tag}"
        await db.safety_workers.insert_one(
            {"id": w_pre, "project_id": proj, "full_name": "עובד ותיק",
             "deletedAt": None, "created_at": now_iso})
        r = await c.post(f"{WORKERS}/{w_pre}/entry-token", headers=pm_h)
        record("V1e ensure-on-demand for pre-existing worker → 200 + token + gate_url",
               r.status_code == 200 and r.json().get("token") and "/gate/" in r.json().get("gate_url", ""),
               f"{r.status_code}")
        pre_token = r.json().get("token")
        r2 = await c.post(f"{WORKERS}/{w_pre}/entry-token", headers=pm_h)
        record("V1f ensure is idempotent (same token back)",
               r2.status_code == 200 and r2.json().get("token") == pre_token)

        # revoke on delete → invalid
        r = await c.request("DELETE", f"{WORKERS}/{w_pre}",
                            json={"reason": "בדיקה"}, headers=pm_h)
        record("V1g worker delete accepted", r.status_code in (200, 204), f"{r.status_code}")
        rg = await gate(pre_token)
        record("V1h deleted worker's token → neutral invalid",
               rg.status_code == 200 and rg.json() == {"state": "invalid"}, rg.text[:120])

        # =========== V2 — status matrix (public) ===========
        print("V2 — status matrix")
        token1 = tok1["token"]
        rg = await gate(token1)
        j = rg.json()
        record("V2a no induction → red-induction",
               rg.status_code == 200 and j.get("state") == "red" and j.get("reason") == "induction", str(j)[:150])
        record("V2b red payload has NO phone/id fields", no_pii(j))

        # signed induction via real conduct flow
        r = await c.put(TMPL, json={"sections": [
            {"title": "סעיף 1", "body": "תוכן"}]}, headers=pm_h)
        assert r.status_code == 200, r.text[:200]
        exp_far = (date.today() + timedelta(days=200)).isoformat()
        r = await c.post(CONDUCT, data={
            "worker_id": w1, "language_choice": "he", "expires_at": exp_far,
            "signer_name": "עובד", "signature_type": "typed", "typed_name": "עובד",
        }, headers=pm_h)
        assert r.status_code == 201, f"conduct failed {r.status_code} {r.text[:300]}"

        rg = await gate(token1)
        j = rg.json()
        record("V2c signed induction → green with first name + validity",
               j.get("state") == "green" and j.get("induction_valid_until") == exp_far
               and j.get("first_name") == "עובד", str(j)[:200])
        record("V2d green payload has NO phone/id fields + first name only",
               no_pii(j) and "full_name" not in j and j.get("warnings") == [])

        # yellow warning: another training type, expired
        await db.safety_trainings.insert_one({
            "id": f"qrg-tr-exp-{tag}", "project_id": proj, "worker_id": w1,
            "training_type": "עבודה בגובה", "trained_at": now_iso,
            "expires_at": (date.today() - timedelta(days=3)).isoformat(),
            "worker_signature": "x", "created_at": now_iso, "created_by": pm_id,
            "deletedAt": None,
        })
        rg = await gate(token1)
        j = rg.json()
        record("V2e expired other training → green + yellow warning",
               j.get("state") == "green" and j.get("warnings")
               and j["warnings"][0]["type"] == "עבודה בגובה", str(j.get("warnings"))[:150])

        # expired induction → red with expired_at
        w2r = await c.post(WORKERS, json={"full_name": "עובד שני"}, headers=pm_h)
        w2 = w2r.json()["id"]
        tok2 = await db.worker_entry_tokens.find_one(
            {"project_id": proj, "worker_id": w2, "status": "active"}, {"_id": 0})
        exp_past = (date.today() - timedelta(days=5)).isoformat()
        await db.safety_trainings.insert_one({
            "id": f"qrg-tr-ind-exp-{tag}", "project_id": proj, "worker_id": w2,
            "training_type": INDUCTION_TRAINING_TYPE, "trained_at": now_iso,
            "expires_at": exp_past, "worker_signature": "x",
            "created_at": now_iso, "created_by": pm_id, "deletedAt": None,
        })
        rg = await gate(tok2["token"])
        j = rg.json()
        record("V2f expired induction → red-induction with expired_at",
               j.get("state") == "red" and j.get("reason") == "induction"
               and j.get("expired_at") == exp_past, str(j)[:150])

        rg = await gate("definitely-not-a-real-token-1234567890")
        record("V2g bad token → SAME neutral invalid body",
               rg.json() == {"state": "invalid"})

        # =========== V3 — scan log + gating ===========
        print("V3 — scan log")
        n_logs = await db.gate_scan_log.count_documents({"project_id": proj})
        record("V3a scan log rows written for project hits", n_logs >= 4, f"n={n_logs}")
        inv_logs = await db.gate_scan_log.count_documents(
            {"project_id": None, "result": "invalid"})
        record("V3b invalid hits logged too", inv_logs >= 1, f"n={inv_logs}")
        r = await c.get(f"/api/safety/{proj}/gate-scans", headers=pm_h)
        j = r.json()
        record("V3c PM list 200 + worker names resolved",
               r.status_code == 200 and j.get("total", 0) >= 4
               and any(it.get("worker_name") for it in j.get("items", [])), f"{r.status_code}")
        r = await c.get(f"/api/safety/{proj}/gate-scans", headers=con_h)
        record("V3d contractor 403", r.status_code == 403, f"{r.status_code}")
        r = await c.get(f"/api/safety/{proj}/gate-scans", headers=out_h)
        record("V3e outsider PM 403", r.status_code == 403, f"{r.status_code}")

        # =========== V4 — block flow ===========
        print("V4 — block flow")
        r = await c.patch(f"{WORKERS}/{w1}/block",
                          json={"is_blocked": True, "reason": "הפרת בטיחות"}, headers=pm_h)
        record("V4a PATCH block → 200", r.status_code == 200, f"{r.status_code} {r.text[:150]}")
        rg = await gate(token1)
        j = rg.json()
        record("V4b gate red-blocked instantly",
               j.get("state") == "red" and j.get("reason") == "blocked", str(j)[:120])
        ev = await db.audit_events.find_one(
            {"entity_id": w1, "action": "worker_block_change"}, {"_id": 0})
        record("V4c audit event worker_block_change written", bool(ev))
        r = await c.patch(f"{WORKERS}/{w1}/block", json={"is_blocked": False}, headers=pm_h)
        rg = await gate(token1)
        record("V4d unblock restores green",
               r.status_code == 200 and rg.json().get("state") == "green")
        r = await c.patch(f"{WORKERS}/{w1}/block", json={"is_blocked": True}, headers=con_h)
        record("V4e contractor cannot block (403)", r.status_code == 403, f"{r.status_code}")

        # =========== V5 — rotation ===========
        print("V5 — rotation")
        r = await c.post(f"{WORKERS}/{w1}/entry-token/rotate", headers=pm_h)
        new_token = r.json().get("token")
        record("V5a rotate → 200 + new token differs",
               r.status_code == 200 and new_token and new_token != token1)
        rg_new = await gate(new_token)
        rg_old = await gate(token1)
        record("V5b new token works (green)", rg_new.json().get("state") == "green")
        record("V5c old token → neutral invalid", rg_old.json() == {"state": "invalid"})
        new_doc = await db.worker_entry_tokens.find_one({"token": new_token}, {"_id": 0})
        record("V5d rotated doc: rotated_from + fresh qr_ref",
               bool(new_doc) and new_doc.get("rotated_from") == tok1["id"]
               and new_doc.get("qr_ref") and new_doc["qr_ref"] != tok1.get("qr_ref"))
        r = await c.get(f"{WORKERS}/{w1}/entry-qr.png", headers=pm_h)
        record("V5e QR PNG endpoint returns a real PNG",
               r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"
               and r.headers.get("content-type") == "image/png")

        # =========== V6 — WA auto-send flag ===========
        print("V6 — WA auto-send")
        record("V6a flag OFF (default) → ZERO _send_wa_template calls so far",
               len(wa_calls) == 0, f"calls={len(wa_calls)}")
        import config as cfg
        old_flag = cfg.WA_ENTRY_QR_ENABLED
        cfg.WA_ENTRY_QR_ENABLED = True
        try:
            r = await c.post(WORKERS, json={
                "full_name": f"עובד ווטסאפ {tag}", "phone": "0501112233",
            }, headers=pm_h)
            record("V6b worker creation still 201 with flag on", r.status_code == 201)
            record("V6c exactly one send attempted", len(wa_calls) == 1, f"calls={len(wa_calls)}")
            if wa_calls:
                a, kw = wa_calls[0]
                body = a[2] if len(a) > 2 else kw.get("body_params")
                names = {p.get("parameter_name") for p in (body or [])}
                hdr = kw.get("header_image_url")
                record("V6d named params worker_name+project_name; E.164 phone",
                       names == {"worker_name", "project_name"}
                       and a[0].startswith("+9725"), f"names={names} to={a[0]}")
                record("V6e header_image_url wired (https or None-if-local-storage)",
                       "header_image_url" in kw and (hdr is None or hdr.startswith("https://")),
                       f"hdr={str(hdr)[:60]}")
            else:
                record("V6d named params", False, "no call captured")
                record("V6e header image", False, "no call captured")
        finally:
            cfg.WA_ENTRY_QR_ENABLED = old_flag
            rs._send_wa_template = real_send

        # =========== V7 — throttle + noindex ===========
        print("V7 — throttle + noindex")
        rg = await gate(new_token)
        record("V7a X-Robots-Tag noindex present",
               "noindex" in rg.headers.get("x-robots-tag", ""))
        # Two throttle layers protect /api/gate: the app-wide unauthenticated
        # per-IP limiter (30/min, Mongo-backed) fires FIRST, and the module's
        # own in-memory 60/min throttle is defense-in-depth behind it.
        gate_public._hits.clear()
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})
        statuses = []
        for _ in range(40):
            resp = await gate("burst-token-not-real-000000000000")
            statuses.append(resp.status_code)
        record("V7b burst → 429 (normal pace unaffected)",
               statuses[0] == 200 and 429 in statuses,
               f"first429={statuses.index(429) if 429 in statuses else None}")
        # local module throttle unit check: 61st call within the window → 429
        gate_public._hits.clear()
        local_429 = None
        try:
            for _ in range(61):
                gate_public._check_throttle("10.9.9.9")
        except Exception as e:
            local_429 = getattr(e, "status_code", None)
        record("V7c module throttle: 61st hit in window → 429", local_429 == 429)
        gate_public._hits.clear()
        await db.otp_rate_limits.delete_many({"kind": "global_ip"})

    # ---------------------------------------------------------------
    print("V9 — token concurrency (single-active-token invariant)")
    from contractor_ops.safety import gate as gate_mod
    cw_id = f"probe-qrg-cw-{tag}"
    # 10 concurrent ensures on a worker with no token → exactly 1 active
    await asyncio.gather(*[
        gate_mod.ensure_entry_token(db, proj, cw_id) for _ in range(10)
    ])
    n_active = await db.worker_entry_tokens.count_documents(
        {"project_id": proj, "worker_id": cw_id, "status": "active"})
    record("V9a 10 concurrent ensures → exactly 1 active token", n_active == 1,
           f"active={n_active}")
    # 10 concurrent rotates → still exactly 1 active
    await asyncio.gather(*[
        gate_mod.rotate_entry_token(db, proj, cw_id) for _ in range(10)
    ])
    n_active = await db.worker_entry_tokens.count_documents(
        {"project_id": proj, "worker_id": cw_id, "status": "active"})
    n_total = await db.worker_entry_tokens.count_documents(
        {"project_id": proj, "worker_id": cw_id})
    record("V9b 10 concurrent rotates → exactly 1 active token", n_active == 1,
           f"active={n_active} total={n_total}")
    idx = await db.worker_entry_tokens.index_information()
    record("V9c partial unique index uidx_wet_active exists",
           "uidx_wet_active" in idx and idx["uidx_wet_active"].get("unique") is True)

    # signature sanity: existing callers unaffected (default None)
    import inspect
    sig = inspect.signature(real_send)
    record("V6f _send_wa_template signature: header_image_url default None",
           sig.parameters["header_image_url"].default is None)

    failed = [n for n, p in RESULTS if not p]
    print(f"\n{'=' * 60}\nTOTAL: {len(RESULTS)}  PASS: {len(RESULTS) - len(failed)}  FAIL: {len(failed)}")
    if failed:
        print("FAILED:", *failed, sep="\n  - ")
        sys.exit(1)
    print("ALL GREEN")


if __name__ == "__main__":
    asyncio.run(main())
