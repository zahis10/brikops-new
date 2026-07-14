"""FUNCTIONAL probes for BATCH safety-ind2 (induction conduct flow).

Same in-process harness as probe_safety_ind1.py: REAL FastAPI app
(httpx ASGITransport), ENABLE_SAFETY_MODULE, REAL local Mongo,
FILES_STORAGE_BACKEND=local, REAL JWTs, WA creds blanked.

Covers (spec V-map; V9 craco/greps/regression run separately in shell):
  V1  Happy path he: conduct → training exists, type "הדרכת אתר",
      expires=today+365, signature complete (canvas ref key-at-rest,
      display url regens), snapshot row + hash recompute; SECOND conduct
      (other worker, same version) → SAME snapshot_id, still ONE row
  V2  Ruling ה-12: "other" without interpreter → 422 Hebrew; without
      worker_language → 422; with both → via_interpreter=true,
      attestation contains BOTH values, language_read=="he"
  V3  Immutability: /signature on conducted → 409; PATCH with a
      worker_signature key → NOT changed; template edit afterwards →
      old record+snapshot untouched; new conduct → new version+NEW row
  V4  No template (fresh org) → content 404 + conduct 409 Hebrew;
      FE empty-state copy present in the component source
  V5  expires_at override honored; invalid date → 422; default when omitted
  V6  RBAC: PM member 200; PM NON-member 403; MT member 200; contractor
      403; unauthenticated 401; ⭐ PM with NO organization_memberships row
      conducts successfully (project-org resolution)
  V7  Worker guards: unknown worker 404; deleted worker 404; worker of
      ANOTHER project 404
  V8  Alerts synergy: expires_at=today+7 → appears in collect_expiry_alerts
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local — repl env may carry Atlas
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_ENABLED"] = "false"

import sys
import uuid
import asyncio
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []

_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6360000002000154a24f5f0000000049454e44ae426082"
)


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def heb(s):
    return any("\u0590" <= ch <= "\u05EA" for ch in str(s))


def sections(n, prefix="סעיף"):
    return [{"title": f"{prefix} {i + 1}", "body": f"תוכן {prefix} {i + 1}"} for i in range(n)]


def sig_files():
    return {"signature_image": ("signature.png", _PNG, "image/png")}


def sig_data(worker_id, **over):
    d = {
        "worker_id": worker_id,
        "language_choice": "he",
        "signer_name": "עובד בדיקה",
        "signature_type": "canvas",
    }
    d.update(over)
    return d


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import (
        induction_content_hash, INDUCTION_LEGAL_TEXT_HE, INDUCTION_TRAINING_TYPE,
        DEFAULT_INDUCTION_VALIDITY_DAYS,
    )
    from contractor_ops.safety_expiry_service import collect_expiry_alerts

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    today = date.today()
    tag = uuid.uuid4().hex[:8]

    org_a = f"probe-ind2-orgA-{tag}"
    org_c = f"probe-ind2-orgC-{tag}"   # fresh org — NO template (V4)
    proj1 = f"probe-ind2-p1-{tag}"     # org A
    proj2 = f"probe-ind2-p2-{tag}"     # org A — cross-project worker guard
    proj3 = f"probe-ind2-p3-{tag}"     # org C

    own_id = f"probe-ind2-own-{tag}"       # org-A owner (edits template)
    pm_id = f"probe-ind2-pm-{tag}"         # PM, org member + project member
    pm_nom_id = f"probe-ind2-pmnom-{tag}"  # ⭐ PM, NO org membership row
    pm_out_id = f"probe-ind2-pmout-{tag}"  # PM, NOT a project member → 403
    mt_id = f"probe-ind2-mt-{tag}"         # management_team, project member
    con_id = f"probe-ind2-con-{tag}"       # contractor, project member
    pmc_id = f"probe-ind2-pmc-{tag}"       # PM in org C (no-template org)

    w1 = f"probe-ind2-w1-{tag}"
    w2 = f"probe-ind2-w2-{tag}"
    w3 = f"probe-ind2-w3-{tag}"        # lives in proj2
    wdel = f"probe-ind2-wdel-{tag}"    # soft-deleted
    w4 = f"probe-ind2-w4-{tag}"        # V8 alerts
    w5 = f"probe-ind2-w5-{tag}"        # V3 re-conduct after template edit
    wc = f"probe-ind2-wc-{tag}"        # org C project worker

    # ---------------- seed ----------------
    await db.organizations.insert_many([
        {"id": org_a, "name": f"ארגון א {tag}", "owner_user_id": own_id},
        {"id": org_c, "name": f"ארגון ג {tag}", "owner_user_id": pmc_id},
    ])
    await db.subscriptions.insert_many([
        {"org_id": org_a, "status": "active", "paid_until": paid},
        {"org_id": org_c, "status": "active", "paid_until": paid},
    ])
    users = [
        (own_id, "owner"), (pm_id, "project_manager"),
        (pm_nom_id, "project_manager"), (pm_out_id, "project_manager"),
        (mt_id, "management_team"), (con_id, "contractor"),
        (pmc_id, "project_manager"),
    ]
    await db.users.insert_many([
        {"id": uid, "role": role, "full_name": f"משתמש {role}", "user_status": "active",
         "session_version": 0, "phone_e164": f"+9725066{i:05d}", "last_login_at": now_iso}
        for i, (uid, role) in enumerate(users)
    ])
    # ⭐ pm_nom_id deliberately has NO organization_memberships row
    await db.organization_memberships.insert_many([
        {"id": f"ind2-om1-{tag}", "org_id": org_a, "user_id": own_id, "role": "owner"},
        {"id": f"ind2-om2-{tag}", "org_id": org_a, "user_id": pm_id, "role": "member"},
        {"id": f"ind2-om3-{tag}", "org_id": org_a, "user_id": pm_out_id, "role": "member"},
        {"id": f"ind2-om4-{tag}", "org_id": org_a, "user_id": mt_id, "role": "member"},
        {"id": f"ind2-om5-{tag}", "org_id": org_a, "user_id": con_id, "role": "member"},
        {"id": f"ind2-om6-{tag}", "org_id": org_c, "user_id": pmc_id, "role": "owner"},
    ])
    await db.projects.insert_many([
        {"id": proj1, "org_id": org_a, "name": f"פרויקט 1 {tag}", "status": "active"},
        {"id": proj2, "org_id": org_a, "name": f"פרויקט 2 {tag}", "status": "active"},
        {"id": proj3, "org_id": org_c, "name": f"פרויקט 3 {tag}", "status": "active"},
    ])
    await db.project_memberships.insert_many([
        {"id": f"ind2-pmm1-{tag}", "project_id": proj1, "user_id": pm_id, "role": "project_manager"},
        {"id": f"ind2-pmm2-{tag}", "project_id": proj1, "user_id": pm_nom_id, "role": "project_manager"},
        {"id": f"ind2-pmm3-{tag}", "project_id": proj1, "user_id": mt_id, "role": "management_team"},
        {"id": f"ind2-pmm4-{tag}", "project_id": proj1, "user_id": con_id, "role": "contractor"},
        {"id": f"ind2-pmm5-{tag}", "project_id": proj3, "user_id": pmc_id, "role": "project_manager"},
        {"id": f"ind2-pmm6-{tag}", "project_id": proj1, "user_id": own_id, "role": "project_manager"},
    ])
    workers_seed = [
        (w1, proj1, None), (w2, proj1, None), (w3, proj2, None),
        (wdel, proj1, now_iso), (w4, proj1, None), (w5, proj1, None),
        (wc, proj3, None),
    ]
    await db.safety_workers.insert_many([
        {"id": wid, "project_id": pid, "full_name": f"עובד {wid[-6:]}",
         "deletedAt": dele, "created_at": now_iso}
        for wid, pid, dele in workers_seed
    ])

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    hdrs = {uid: h(uid, role) for uid, role in users}

    CONTENT = f"/api/safety/{proj1}/induction/content"
    CONDUCT = f"/api/safety/{proj1}/induction/conduct"
    TEMPLATE = "/api/safety/induction-template"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:

        # seed template via API (owner) — v1
        secs = sections(3, "בטיחות")
        r = await c.put(TEMPLATE, json={"sections": secs}, headers=hdrs[own_id])
        assert r.status_code == 200, f"template seed failed: {r.status_code} {r.text}"

        # ---------------- V1 — happy path he ----------------
        print("V1 — happy path he + snapshot dedup")
        r = await c.get(CONTENT, headers=hdrs[pm_id])
        j = r.json()
        record("V1a content 200: sections, legal texts, 365, languages [he]",
               r.status_code == 200 and j.get("sections") == secs
               and j.get("legal_text") == INDUCTION_LEGAL_TEXT_HE
               and j.get("languages_filled") == ["he"]
               and j.get("default_validity_days") == DEFAULT_INDUCTION_VALIDITY_DAYS
               and j.get("template_version") == 1, f"status={r.status_code}")

        r = await c.post(CONDUCT, data=sig_data(w1), files=sig_files(), headers=hdrs[pm_id])
        t1 = r.json() if r.status_code == 201 else {}
        sig1 = t1.get("worker_signature") or {}
        exp_default = (today + timedelta(days=365)).isoformat()
        record("V1b conduct 201, type הדרכת אתר, expires=today+365",
               r.status_code == 201 and t1.get("training_type") == INDUCTION_TRAINING_TYPE
               and t1.get("expires_at") == exp_default, f"status={r.status_code} {r.text[:120]}")
        record("V1c signature complete: canvas ref + display url + extended fields",
               bool(sig1.get("signature_ref")) and bool(sig1.get("signature_display_url"))
               and sig1.get("language_read") == "he" and sig1.get("worker_language") == "he"
               and sig1.get("via_interpreter") is False and sig1.get("content_version") == 1
               and sig1.get("attestation_text") == INDUCTION_LEGAL_TEXT_HE
               and bool(sig1.get("snapshot_id")) and bool(sig1.get("content_hash")))
        db_row = await db.safety_trainings.find_one({"id": t1.get("id")}, {"_id": 0})
        record("V1d key-at-rest: stored signature_ref is a key, NOT a presigned URL",
               db_row and "X-Amz-" not in (db_row["worker_signature"]["signature_ref"] or "")
               and "http" not in (db_row["worker_signature"]["signature_ref"] or "")[:4])
        snap = await db.induction_content_snapshots.find_one(
            {"id": sig1.get("snapshot_id")}, {"_id": 0})
        record("V1e snapshot row: full copy + hash matches recompute",
               bool(snap) and snap["sections"] == secs
               and snap["legal_text"] == INDUCTION_LEGAL_TEXT_HE
               and snap["content_hash"] == induction_content_hash(secs, INDUCTION_LEGAL_TEXT_HE)
               and snap["content_hash"] == sig1.get("content_hash"))
        audit = await db.audit_events.find_one({"action": "induction_conducted",
                                                "entity_id": t1.get("id")})
        record("V1f audit induction_conducted (no PII beyond ids)",
               bool(audit) and audit["payload"].get("worker_id") == w1
               and audit["payload"].get("language_read") == "he")

        r = await c.post(CONDUCT, data=sig_data(w2), files=sig_files(), headers=hdrs[pm_id])
        t2 = r.json() if r.status_code == 201 else {}
        sig2 = t2.get("worker_signature") or {}
        n_snaps = await db.induction_content_snapshots.count_documents(
            {"org_id": org_a})
        record("V1g SECOND conduct → SAME snapshot_id, still ONE snapshot row",
               r.status_code == 201 and sig2.get("snapshot_id") == sig1.get("snapshot_id")
               and n_snaps == 1, f"snaps={n_snaps}")

        # ---------------- V2 — ruling ה-12 ----------------
        print("V2 — ruling ה-12 (other/interpreter)")
        r = await c.post(CONDUCT, data=sig_data(w2, language_choice="other",
                                                worker_language="טיגרינית"),
                         files=sig_files(), headers=hdrs[pm_id])
        record("V2a other without interpreter_name → 422 Hebrew",
               r.status_code == 422 and heb(r.json().get("detail")),
               f"status={r.status_code} {str(r.json().get('detail'))[:60]}")
        r = await c.post(CONDUCT, data=sig_data(w2, language_choice="other",
                                                interpreter_name="יוסי המתורגמן"),
                         files=sig_files(), headers=hdrs[pm_id])
        record("V2b other without worker_language → 422 Hebrew",
               r.status_code == 422 and heb(r.json().get("detail")))
        r = await c.post(CONDUCT, data=sig_data(w2, language_choice="other",
                                                worker_language="טיגרינית",
                                                interpreter_name="יוסי המתורגמן"),
                         files=sig_files(), headers=hdrs[pm_id])
        t3 = r.json() if r.status_code == 201 else {}
        sig3 = t3.get("worker_signature") or {}
        record("V2c other + both → via_interpreter, attestation has BOTH, language_read=he",
               r.status_code == 201 and sig3.get("via_interpreter") is True
               and "טיגרינית" in (sig3.get("attestation_text") or "")
               and "יוסי המתורגמן" in (sig3.get("attestation_text") or "")
               and sig3.get("language_read") == "he"
               and sig3.get("worker_language") == "טיגרינית"
               and sig3.get("interpreter_name") == "יוסי המתורגמן")
        record("V2d other shares the SAME he snapshot (personalization on signature only)",
               sig3.get("snapshot_id") == sig1.get("snapshot_id"))

        # ---------------- V3 — immutability ----------------
        print("V3 — immutability")
        r = await c.post(f"/api/safety/{proj1}/trainings/{t1['id']}/signature",
                         data={"signer_name": "מישהו", "signature_type": "typed",
                               "typed_name": "מישהו"},
                         headers=hdrs[pm_id])
        record("V3a /signature on conducted training → 409", r.status_code == 409)
        r = await c.patch(f"/api/safety/{proj1}/trainings/{t1['id']}",
                          json={"location": "אתר", "worker_signature": {"name": "זיוף"}},
                          headers=hdrs[pm_id])
        after = await db.safety_trainings.find_one({"id": t1["id"]}, {"_id": 0})
        record("V3b PATCH with worker_signature key → field NOT changed (model excludes)",
               r.status_code == 200 and after["worker_signature"]["name"] == "עובד בדיקה"
               and after["location"] == "אתר")
        snap_before = dict(snap)
        r = await c.put(TEMPLATE, json={"sections": sections(4, "מהדורה-2")},
                        headers=hdrs[own_id])
        assert r.status_code == 200 and r.json()["template"]["version"] == 2
        rec_after = await db.safety_trainings.find_one({"id": t1["id"]}, {"_id": 0})
        snap_after = await db.induction_content_snapshots.find_one(
            {"id": sig1["snapshot_id"]}, {"_id": 0})
        record("V3c template edit → old record + snapshot byte-identical",
               rec_after == after and snap_after == snap_before)
        r = await c.post(CONDUCT, data=sig_data(w5), files=sig_files(), headers=hdrs[pm_id])
        t4 = r.json() if r.status_code == 201 else {}
        sig4 = t4.get("worker_signature") or {}
        n_snaps = await db.induction_content_snapshots.count_documents({"org_id": org_a})
        record("V3d new conduct → version 2 + NEW snapshot row (2 total)",
               r.status_code == 201 and sig4.get("content_version") == 2
               and sig4.get("snapshot_id") != sig1.get("snapshot_id") and n_snaps == 2,
               f"snaps={n_snaps}")

        # ---------------- V4 — no template ----------------
        print("V4 — no template (fresh org)")
        r = await c.get(f"/api/safety/{proj3}/induction/content", headers=hdrs[pmc_id])
        record("V4a content → 404 Hebrew",
               r.status_code == 404 and heb(r.json().get("detail")))
        r = await c.post(f"/api/safety/{proj3}/induction/conduct",
                         data=sig_data(wc), files=sig_files(), headers=hdrs[pmc_id])
        record("V4b conduct → 409 Hebrew",
               r.status_code == 409 and heb(r.json().get("detail")))
        fe_src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "frontend/src/components/safety/SafetyInductionConduct.js"),
            encoding="utf-8").read()
        record("V4c FE empty-state copy present in component",
               "לא הוגדר תוכן הדרכת אתר — מנהל הארגון מגדיר אותו" in fe_src)

        # ---------------- V5 — expires_at ----------------
        print("V5 — expires_at override / invalid / default")
        exp_custom = (today + timedelta(days=30)).isoformat()
        r = await c.post(CONDUCT, data=sig_data(w1, expires_at=exp_custom),
                         files=sig_files(), headers=hdrs[pm_id])
        record("V5a override honored",
               r.status_code == 201 and r.json().get("expires_at") == exp_custom)
        r = await c.post(CONDUCT, data=sig_data(w1, expires_at="לא-תאריך"),
                         files=sig_files(), headers=hdrs[pm_id])
        record("V5b invalid date → 422 Hebrew",
               r.status_code == 422 and heb(r.json().get("detail")))
        record("V5c default applied when omitted (V1b already asserted)", True)

        # ---------------- V6 — RBAC ----------------
        print("V6 — RBAC")
        r = await c.get(CONTENT, headers=hdrs[pm_id])
        record("V6a PM member content 200", r.status_code == 200)
        r = await c.get(CONTENT, headers=hdrs[pm_out_id])
        record("V6b PM NON-member → 403", r.status_code == 403)
        r = await c.get(CONTENT, headers=hdrs[mt_id])
        record("V6c MT member 200", r.status_code == 200)
        r = await c.get(CONTENT, headers=hdrs[con_id])
        record("V6d contractor → 403", r.status_code == 403)
        r = await c.get(CONTENT)
        record("V6e unauthenticated → 401", r.status_code == 401)
        r = await c.post(CONDUCT, data=sig_data(w2, signature_type="typed",
                                                typed_name="עובד נוסף"),
                         headers=hdrs[pm_nom_id])
        record("V6f ⭐ PM with NO org membership row conducts OK (project-org resolution)",
               r.status_code == 201, f"status={r.status_code} {r.text[:120]}")
        r = await c.post(CONDUCT, data=sig_data(w2), files=sig_files(),
                         headers=hdrs[con_id])
        record("V6g contractor conduct → 403", r.status_code == 403)

        # ---------------- V7 — worker guards ----------------
        print("V7 — worker guards")
        r = await c.post(CONDUCT, data=sig_data("no-such-worker"),
                         files=sig_files(), headers=hdrs[pm_id])
        record("V7a unknown worker → 404", r.status_code == 404)
        r = await c.post(CONDUCT, data=sig_data(wdel), files=sig_files(), headers=hdrs[pm_id])
        record("V7b deleted worker → 404", r.status_code == 404)
        r = await c.post(CONDUCT, data=sig_data(w3), files=sig_files(), headers=hdrs[pm_id])
        record("V7c worker of ANOTHER project → 404", r.status_code == 404)

        # ---------------- V7½ — concurrency + paywall pattern regression ----
        print("V7½ — parallel first-conduct snapshot race + paywall pattern")
        r = await c.put(TEMPLATE, json={"sections": sections(2, "מהדורה-3")},
                        headers=hdrs[own_id])
        assert r.status_code == 200 and r.json()["template"]["version"] == 3
        snaps_before = await db.induction_content_snapshots.count_documents({"org_id": org_a})
        ra, rb = await asyncio.gather(
            c.post(CONDUCT, data=sig_data(w1, signature_type="typed", typed_name="א"),
                   headers=hdrs[pm_id]),
            c.post(CONDUCT, data=sig_data(w2, signature_type="typed", typed_name="ב"),
                   headers=hdrs[pm_id]),
        )
        sa = (ra.json().get("worker_signature") or {}) if ra.status_code == 201 else {}
        sb = (rb.json().get("worker_signature") or {}) if rb.status_code == 201 else {}
        snaps_after = await db.induction_content_snapshots.count_documents({"org_id": org_a})
        record("V7½a parallel conducts both 201, SAME snapshot_id, +1 row only",
               ra.status_code == 201 and rb.status_code == 201
               and sa.get("snapshot_id") == sb.get("snapshot_id")
               and snaps_after == snaps_before + 1,
               f"a={ra.status_code} b={rb.status_code} snaps {snaps_before}→{snaps_after}")
        # non-project safety path must NOT get a scoped-billing allow:
        # pm_nom has NO org membership → org-level template PUT stays blocked
        # (402 paywall — regex captures 'induction-template', projects miss).
        r = await c.put(TEMPLATE, json={"sections": sections(1)}, headers=hdrs[pm_nom_id])
        record("V7½b org-level template path: NO scoped-billing bypass (402)",
               r.status_code == 402, f"status={r.status_code}")

        # ---------------- V8 — alerts synergy ----------------
        print("V8 — alerts synergy (expires today+7)")
        exp7 = (today + timedelta(days=7)).isoformat()
        r = await c.post(CONDUCT, data=sig_data(w4, expires_at=exp7),
                         files=sig_files(), headers=hdrs[pm_id])
        assert r.status_code == 201, r.text
        payloads = await collect_expiry_alerts(db, today.isoformat())
        items = (payloads.get(proj1) or {}).get("items", [])
        hit = [i for i in items if i["kind"] == "training"
               and INDUCTION_TRAINING_TYPE in i["label"] and i["days_left"] == 7]
        record("V8a conducted induction (exp=+7) appears in collect_expiry_alerts",
               bool(hit), f"items={len(items)}")

    # ---------------- cleanup ----------------
    await db.organizations.delete_many({"id": {"$in": [org_a, org_c]}})
    await db.subscriptions.delete_many({"org_id": {"$in": [org_a, org_c]}})
    await db.users.delete_many({"id": {"$in": [u for u, _ in users]}})
    await db.organization_memberships.delete_many({"org_id": {"$in": [org_a, org_c]}})
    await db.projects.delete_many({"id": {"$in": [proj1, proj2, proj3]}})
    await db.project_memberships.delete_many({"project_id": {"$in": [proj1, proj2, proj3]}})
    await db.safety_workers.delete_many({"project_id": {"$in": [proj1, proj2, proj3]}})
    await db.safety_trainings.delete_many({"project_id": {"$in": [proj1, proj2, proj3]}})
    await db.induction_templates.delete_many({"org_id": {"$in": [org_a, org_c]}})
    await db.induction_content_snapshots.delete_many({"org_id": {"$in": [org_a, org_c]}})
    await db.audit_events.delete_many({"payload.project_id": {"$in": [proj1, proj2, proj3]}})
    await db.audit_events.delete_many({"payload.org_id": {"$in": [org_a, org_c]}})

    passed = sum(1 for _, p, _ in RESULTS if p)
    print(f"\n===== {passed}/{len(RESULTS)} PASSED =====")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
