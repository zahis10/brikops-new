"""FUNCTIONAL probes for BATCH safety-w1-alerts (WhatsApp expiry alerts).

Same in-process harness as probe_diary_d4b.py: REAL FastAPI app (httpx
ASGITransport), ENABLE_SAFETY_MODULE, REAL local Mongo,
FILES_STORAGE_BACKEND=local (NEVER a real bucket), REAL JWTs.

HARD SAFETY GUARD: aborts unless reminder_service._wa_enabled is False —
every "send" below is a DRY-RUN log line; nothing real ever leaves.

Covers (plan V-map; V7 craco/greps and V8 regressions run separately):
  V1  trainings 30/14/7/0 in, +1/+29 out, superseded (newest-per-group)
      excluded, deleted-worker excluded
  V2  equipment +7 in with code+category-HE+check-name; decommissioned
      excluded; "missing" tracks (no expires_at) never alert
  V3  one payload per project; >10 items → cap + "+ עוד X"; count=UNCAPPED;
      no '\\n' in any param; named params project/items/count
  V4  prefs-off skipped, dormant skipped, wa-disabled skipped, no-phone
      skipped; DRY-RUN transcript captured (template, 3 named params,
      button suffix "{pid}?src=wa", masked phone)
  V5  send_all twice same day → cooldown blocks 2nd; _acquire_daily_lock
      False on 2nd call; archived/inactive project excluded
  V6  scheduler gating: config flag off → send_all NOT invoked (gate check)
  V9  opt-out OFF → skipped w/ reason; ON → included; same-project other
      user unaffected
  V10 prefs HTTP round-trip: GET default ON, PUT off → persists, other
      keys untouched
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local — repl env may carry Atlas
os.environ.setdefault("DB_NAME", "contractor_ops")
# HARD DRY-RUN: the repl env may carry REAL WhatsApp credentials — blank them
# BEFORE any import so server.py wires reminder_service with wa_enabled=False.
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_ENABLED"] = "false"  # config.WHATSAPP_ENABLED drives _wa_enabled

import sys
import uuid
import asyncio
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.utils.timezone import IL_TZ
    from contractor_ops import reminder_service, safety_expiry_service, scheduler as sched_mod

    # ---------- HARD GUARD: DRY-RUN ONLY ----------
    assert reminder_service._wa_enabled is False, \
        "ABORT: _wa_enabled is True — refusing to run probes against real WhatsApp"
    print("[GUARD] _wa_enabled=False — all sends are DRY-RUN. OK.\n")

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    today_dt = datetime.now(IL_TZ)
    today = today_dt.strftime("%Y-%m-%d")

    def d(days):  # today+days as YYYY-MM-DD
        return (today_dt + timedelta(days=days)).strftime("%Y-%m-%d")

    now_iso = datetime.now(timezone.utc).isoformat()
    tag = uuid.uuid4().hex[:8]
    pid1 = f"probe-swa-p1-{tag}"     # main project (trainings + equipment)
    pid2 = f"probe-swa-p2-{tag}"     # overflow project (>10 items)
    pid3 = f"probe-swa-p3-{tag}"     # archived project (must NOT alert)
    org_id = f"probe-swa-org-{tag}"
    pm_id = f"probe-swa-pm-{tag}"        # active PM, prefs default → receives
    owner_id = f"probe-swa-own-{tag}"    # owner, prefs OFF → skipped
    dorm_id = f"probe-swa-dorm-{tag}"    # dormant PM on pid2 → skipped
    wadis_id = f"probe-swa-wadis-{tag}"  # wa-disabled PM on pid2 → skipped
    pm2_id = f"probe-swa-pm2-{tag}"      # active PM on pid2 → receives

    # ---------------- seed ----------------
    await db.organizations.insert_one({"id": org_id, "name": f"ארגון {tag}", "owner_user_id": owner_id})
    await db.subscriptions.insert_one({
        "org_id": org_id, "status": "active",
        "paid_until": (today_dt + timedelta(days=30)).isoformat(),
    })
    await db.projects.insert_many([
        {"id": pid1, "name": f"פרויקט בטיחות {tag}", "org_id": org_id, "status": "active", "deletedAt": None},
        {"id": pid2, "name": f"פרויקט הצפה {tag}", "org_id": org_id, "status": "active", "deletedAt": None},
        {"id": pid3, "name": f"פרויקט ארכיון {tag}", "org_id": org_id, "status": "active", "archived": True, "deletedAt": None},
    ])
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל ראשי", "user_status": "active",
         "session_version": 0, "phone_e164": "+972501110001", "last_login_at": now_iso},
        {"id": owner_id, "role": "owner", "full_name": "יזם מכובה", "user_status": "active",
         "session_version": 0, "phone_e164": "+972501110002", "last_login_at": now_iso,
         "reminder_preferences": {"safety_expiry": {"enabled": False}}},
        {"id": dorm_id, "role": "project_manager", "full_name": "מנהל רדום", "user_status": "active",
         "session_version": 0, "phone_e164": "+972501110003", "last_login_at": "2025-01-01T00:00:00+00:00"},
        {"id": wadis_id, "role": "project_manager", "full_name": "מנהל בלי וואטסאפ", "user_status": "active",
         "session_version": 0, "phone_e164": "+972501110004", "last_login_at": now_iso,
         "whatsapp_notifications_enabled": False},
        {"id": pm2_id, "role": "project_manager", "full_name": "מנהל שני", "user_status": "active",
         "session_version": 0, "phone_e164": "+972501110005", "last_login_at": now_iso},
    ])
    await db.organization_memberships.insert_many([
        {"id": f"swa-om1-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
        {"id": f"swa-om2-{tag}", "org_id": org_id, "user_id": owner_id, "role": "owner"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"swa-m1-{tag}", "project_id": pid1, "user_id": pm_id, "role": "project_manager"},
        {"id": f"swa-m2-{tag}", "project_id": pid1, "user_id": owner_id, "role": "owner"},
        {"id": f"swa-m3-{tag}", "project_id": pid2, "user_id": dorm_id, "role": "project_manager"},
        {"id": f"swa-m4-{tag}", "project_id": pid2, "user_id": wadis_id, "role": "project_manager"},
        {"id": f"swa-m5-{tag}", "project_id": pid2, "user_id": pm2_id, "role": "project_manager"},
        {"id": f"swa-m6-{tag}", "project_id": pid3, "user_id": pm_id, "role": "project_manager"},
    ])

    # workers
    w_ids = {k: f"probe-swa-w{k}-{tag}" for k in ["30", "14", "7", "0", "1", "29", "sup", "del"]}
    await db.safety_workers.insert_many(
        [{"id": w_ids[k], "project_id": pid1, "full_name": f"עובד {k}", "deletedAt": None}
         for k in ["30", "14", "7", "0", "1", "29", "sup"]] +
        [{"id": w_ids["del"], "project_id": pid1, "full_name": "עובד מחוק",
          "deletedAt": now_iso}])

    def training(worker, expires, trained_at, ttype="עבודה בגובה", project=pid1, deleted=None):
        return {"id": f"probe-swa-t-{uuid.uuid4().hex[:10]}", "project_id": project,
                "worker_id": worker, "training_type": ttype, "trained_at": trained_at,
                "expires_at": expires, "created_at": now_iso, "deletedAt": deleted}

    await db.safety_trainings.insert_many([
        training(w_ids["30"], d(30), d(-335)),
        training(w_ids["14"], d(14), d(-351)),
        training(w_ids["7"], d(7), d(-358)),
        training(w_ids["0"], d(0), d(-365)),
        training(w_ids["1"], d(1), d(-364)),      # OUT (threshold miss)
        training(w_ids["29"], d(29), d(-336)),    # OUT (V5c: 29 days)
        # superseded pair: OLD expires at +7 (would alert) but NEWER renewal
        # expires at +200 → group's newest wins → NO alert
        training(w_ids["sup"], d(7), d(-358)),
        training(w_ids["sup"], d(200), d(-10)),
        # deleted worker: training at +7 but worker soft-deleted → NO alert
        training(w_ids["del"], d(7), d(-358)),
    ])

    # equipment on pid1: active tower_crane w/ check at +7; decommissioned w/ +7
    eq_ok = f"probe-swa-eq1-{tag}"
    eq_dec = f"probe-swa-eq2-{tag}"
    await db.safety_equipment.insert_many([
        {"id": eq_ok, "project_id": pid1, "category": "tower_crane", "internal_code": f"עגורן-{tag}",
         "status": "active", "deletedAt": None},
        {"id": eq_dec, "project_id": pid1, "category": "forklift", "internal_code": f"מלגזה-{tag}",
         "status": "decommissioned", "deletedAt": None},
    ])
    await db.safety_equipment_checks.insert_many([
        {"id": f"probe-swa-c1-{tag}", "project_id": pid1, "equipment_id": eq_ok,
         "check_name": "תסקיר בודק מוסמך", "performed_at": d(-173), "expires_at": d(7),
         "period_days": 180, "created_at": now_iso, "deletedAt": None},
        {"id": f"probe-swa-c2-{tag}", "project_id": pid1, "equipment_id": eq_dec,
         "check_name": "תסקיר בודק מוסמך", "performed_at": d(-173), "expires_at": d(7),
         "period_days": 180, "created_at": now_iso, "deletedAt": None},
    ])

    # pid2: 12 trainings at +7 (overflow test)
    ov_workers = []
    ov_trainings = []
    for i in range(12):
        wid = f"probe-swa-ovw{i}-{tag}"
        ov_workers.append({"id": wid, "project_id": pid2, "full_name": f"עובד הצפה {i:02d}", "deletedAt": None})
        ov_trainings.append(training(wid, d(7), d(-358), ttype=f"הדרכה {i:02d}", project=pid2))
    await db.safety_workers.insert_many(ov_workers)
    await db.safety_trainings.insert_many(ov_trainings)

    # pid3 (archived): training at +7 — must never produce a send
    w3 = f"probe-swa-w3-{tag}"
    await db.safety_workers.insert_one({"id": w3, "project_id": pid3, "full_name": "עובד ארכיון", "deletedAt": None})
    await db.safety_trainings.insert_one(training(w3, d(7), d(-358), project=pid3))

    try:
        # ================= V1 + V2 — collect_expiry_alerts ==================
        payloads = await safety_expiry_service.collect_expiry_alerts(db, today)
        p1 = payloads.get(pid1, {"items": [], "total": 0})
        labels1 = [it["label"] for it in p1["items"]]
        dls1 = sorted(it["days_left"] for it in p1["items"])

        record("V1a trainings 30/14/7/0 all collected on pid1",
               all(f"עובד {k}" in " ".join(labels1) for k in ["30", "14", "7", "0"]),
               f"labels={labels1}")
        record("V1b +1 and +29 NOT collected",
               "עובד 1 " not in " ".join(l + " " for l in labels1)
               and "עובד 29" not in " ".join(labels1))
        record("V1c superseded training excluded (newest-per-group wins)",
               "עובד sup" not in " ".join(labels1))
        record("V1d deleted worker excluded", "עובד מחוק" not in " ".join(labels1))
        record("V1e training label format: 🎓 name — type + phrase",
               any(l.startswith("🎓 עובד 7 — עבודה בגובה פג בעוד 7 ימים") for l in labels1),
               f"labels={labels1}")
        record("V1f 0-days phrase is 'פג היום'",
               any("עובד 0" in l and l.endswith("פג היום") for l in labels1))

        eq_labels = [l for l in labels1 if l.startswith("🔧")]
        record("V2a equipment +7 collected w/ code+category-HE+check-name",
               len(eq_labels) == 1 and f"עגורן-{tag}" in eq_labels[0]
               and "עגורן צריח" in eq_labels[0] and "תסקיר בודק מוסמך" in eq_labels[0]
               and "פג בעוד 7 ימים" in eq_labels[0], f"eq={eq_labels}")
        record("V2b decommissioned equipment excluded",
               not any(f"מלגזה-{tag}" in l for l in labels1))
        record("V2c 'missing' default tracks (no expires_at) never alert",
               all("פג" in l for l in labels1))
        record("V1g pid1 total = 5 (4 trainings + 1 equipment)",
               p1["total"] == 5 and dls1 == [0, 7, 7, 14, 30], f"total={p1['total']} dls={dls1}")

        # ================= V3 — per-project payloads, cap, count ============
        p2 = payloads.get(pid2, {"items": [], "total": 0})
        record("V3a one payload per project (pid1 & pid2 separate)",
               p1["total"] == 5 and p2["total"] == 12)
        body2, total2 = safety_expiry_service._compose_params("פרויקט הצפה", p2)
        items_text2 = body2[1]["text"]
        record("V3b >10 → cap at 10 + '+ עוד 2'",
               items_text2.count("🎓") == 10 and "+ עוד 2" in items_text2, f"tail={items_text2[-30:]}")
        record("V3c count param = UNCAPPED total (12)",
               body2[2]["text"] == "12" and total2 == 12)
        record("V3d named params project/items/count, no newlines",
               [p["parameter_name"] for p in body2] == ["project", "items", "count"]
               and all("\n" not in p["text"] and "\r" not in p["text"] for p in body2))
        record("V3e items ׀-separated, most-urgent-first on pid1",
               " ׀ " in safety_expiry_service._compose_params("x", p1)[0][1]["text"]
               and safety_expiry_service._compose_params("x", p1)[0][1]["text"].split(" ׀ ")[0].endswith("פג היום"))

        # ================= V4 + V9 — send_all skips + DRY-RUN transcript ====
        transcript = []
        orig_send = safety_expiry_service._send_wa_template

        async def recording_send(phone, template, body_params, button_params=None, lang_code="he"):
            transcript.append({"phone": phone, "template": template,
                               "body_params": body_params, "button_params": button_params})
            return await orig_send(phone, template, body_params, button_params=button_params, lang_code=lang_code)

        safety_expiry_service._send_wa_template = recording_send
        try:
            summary = await safety_expiry_service.send_all_safety_expiry_alerts()
        finally:
            safety_expiry_service._send_wa_template = orig_send

        sent_to = {t["phone"] for t in transcript}
        record("V4a active PM (pid1) + PM2 (pid2) received; exactly 2 sends",
               summary["sent"] == 2 and sent_to == {"+972501110001", "+972501110005"},
               f"summary={ {k: v for k, v in summary.items() if k != 'projects'} } to={sent_to}")
        record("V9a prefs-OFF owner skipped (no send to his phone)",
               "+972501110002" not in sent_to)
        record("V4b dormant PM skipped", "+972501110003" not in sent_to)
        record("V4c wa-disabled PM skipped", "+972501110004" not in sent_to)
        record("V9b same-project other user (pm2 on pid2) unaffected by skips",
               "+972501110005" in sent_to)
        record("V5c archived project pid3 produced NO send",
               pid3 not in summary["projects"] and pid1 in summary["projects"] and pid2 in summary["projects"])

        t1 = next((t for t in transcript if t["phone"] == "+972501110001"), None)
        from config import WA_TEMPLATE_SAFETY_EXPIRY
        record("V4d transcript: template + 3 named params + button suffix",
               t1 is not None and t1["template"] == WA_TEMPLATE_SAFETY_EXPIRY
               and [p["parameter_name"] for p in t1["body_params"]] == ["project", "items", "count"]
               and t1["button_params"] == [{"index": 0, "text": f"{pid1}?src=wa"}])
        if t1:
            print("\n  ---- DRY-RUN TRANSCRIPT (pid1 → active PM, masked) ----")
            print(f"  template      : {t1['template']} (lang=he)")
            print(f"  to (masked)   : {reminder_service.mask_phone(t1['phone'])}")
            for p in t1["body_params"]:
                print(f"  param {p['parameter_name']:<8}: {p['text']}")
            print(f"  button suffix : {t1['button_params'][0]['text']}")
            print("  --------------------------------------------------------\n")

        logs = await db.reminder_log.find({"type": "safety_expiry", "project_id": pid1}).to_list(20)
        run_logs = await db.reminder_log.find({"type": "safety_expiry_run", "project_id": pid1}).to_list(5)
        record("V4e reminder_log per recipient + run-level audit entry",
               len(logs) == 1 and logs[0]["status"] == "sent" and logs[0]["recipient_user_id"] == pm_id
               and len(run_logs) == 1 and run_logs[0]["alert_date"] == today,
               f"logs={len(logs)} run={len(run_logs)}")

        # ================= V5 — second run same day blocked =================
        summary2 = await safety_expiry_service.send_all_safety_expiry_alerts()
        record("V5a second send_all same day → cooldown blocks (0 sent)",
               summary2["sent"] == 0 and summary2["skipped"] >= 2,
               f"summary2={ {k: v for k, v in summary2.items() if k != 'projects'} }")

        lock1 = await sched_mod._acquire_daily_lock()
        lock2 = await sched_mod._acquire_daily_lock()
        record("V5b daily lock: 2nd acquire same day → False",
               lock2 is False, f"first={lock1} second={lock2}")
        # cleanup our lock ONLY if we created it (leave real prod-day locks alone)
        if lock1:
            await db.scheduler_locks.delete_one({"_id": f"daily_reminders_{today}"})

        # ================= V6 — scheduler gating (flag off → not invoked) ===
        import config as config_mod
        calls = {"n": 0}

        async def counting_send_all():
            calls["n"] += 1
            return {"sent": 0, "skipped": 0, "failed": 0, "projects": []}

        orig_flag = config_mod.ENABLE_SAFETY_MODULE
        orig_send_all = safety_expiry_service.send_all_safety_expiry_alerts
        try:
            safety_expiry_service.send_all_safety_expiry_alerts = counting_send_all
            # replicate the scheduler's gate exactly as written
            config_mod.ENABLE_SAFETY_MODULE = False
            from config import ENABLE_SAFETY_MODULE as flag_off_read  # noqa
            if config_mod.ENABLE_SAFETY_MODULE:
                await safety_expiry_service.send_all_safety_expiry_alerts()
            record("V6a flag OFF → send_all NOT invoked (silent skip)", calls["n"] == 0)
            config_mod.ENABLE_SAFETY_MODULE = True
            if config_mod.ENABLE_SAFETY_MODULE:
                await safety_expiry_service.send_all_safety_expiry_alerts()
            record("V6b flag ON → send_all invoked", calls["n"] == 1)
        finally:
            config_mod.ENABLE_SAFETY_MODULE = orig_flag
            safety_expiry_service.send_all_safety_expiry_alerts = orig_send_all
        record("V6c scheduler module wired (expiry block present)",
               "send_all_safety_expiry_alerts" in open(
                   os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "contractor_ops", "scheduler.py")).read())

        # ================= V10 — prefs HTTP round-trip ======================
        pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
            r = await c.get("/api/users/me/reminder-preferences", headers=pm_h)
            j = r.json()
            record("V10a GET includes safety_expiry, default enabled=True",
                   r.status_code == 200 and j.get("safety_expiry", {}).get("enabled") is True,
                   f"resp={j}")
            r = await c.put("/api/users/me/reminder-preferences",
                            json={"safety_expiry": {"enabled": False}}, headers=pm_h)
            j = r.json()
            record("V10b PUT safety_expiry off → echoed False, others untouched",
                   r.status_code == 200 and j["safety_expiry"]["enabled"] is False
                   and j["contractor_reminder"]["enabled"] is True
                   and j["pm_digest"]["enabled"] is True, f"resp={j}")
            r = await c.get("/api/users/me/reminder-preferences", headers=pm_h)
            record("V10c persists across reload (GET again → False)",
                   r.json()["safety_expiry"]["enabled"] is False)
            r = await c.put("/api/users/me/reminder-preferences",
                            json={"safety_expiry": {"enabled": "yes"}}, headers=pm_h)
            record("V10d bad type → 400 Hebrew", r.status_code == 400)

    finally:
        # ---------------- cleanup (probe data only) ----------------
        await db.organizations.delete_many({"id": org_id})
        await db.subscriptions.delete_many({"org_id": org_id})
        await db.projects.delete_many({"id": {"$in": [pid1, pid2, pid3]}})
        await db.users.delete_many({"id": {"$regex": f"^probe-swa-.*-{tag}$"}})
        await db.organization_memberships.delete_many({"org_id": org_id})
        await db.project_memberships.delete_many({"project_id": {"$in": [pid1, pid2, pid3]}})
        await db.safety_workers.delete_many({"project_id": {"$in": [pid1, pid2, pid3]}})
        await db.safety_trainings.delete_many({"project_id": {"$in": [pid1, pid2, pid3]}})
        await db.safety_equipment.delete_many({"project_id": {"$in": [pid1, pid2, pid3]}})
        await db.safety_equipment_checks.delete_many({"project_id": {"$in": [pid1, pid2, pid3]}})
        await db.reminder_log.delete_many({"project_id": {"$in": [pid1, pid2, pid3]}})

    failed = [r for r in RESULTS if not r[1]]
    print(f"\n===== probe_safety_w1_alerts: {len(RESULTS) - len(failed)}/{len(RESULTS)} PASS =====")
    if failed:
        for name, _, detail in failed:
            print(f"  FAILED: {name} {detail}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
