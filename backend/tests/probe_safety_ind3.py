"""FUNCTIONAL probes for BATCH safety-ind3 — multi-language induction
content (he/en/ru/ar/zh), Google-Translate DRAFT, conduct in the chosen
language, certificate PDF.

Same in-process harness as probe_safety_ind2_fix4.py: REAL FastAPI app,
real local Mongo, real JWTs. TRANSLATE_MOCK=1 → deterministic draft.

Covers:
  V1  Translate endpoint: mock draft (structure 1:1, persists NOTHING,
      version unchanged), unsupported target 422, no-he 409, edit gate
      403 for non-editor, unauthenticated 401.
  V2  Multi-language save: full languages map PUT → ONE version inc,
      languages_filled; empty sections REMOVE a language; he empty 422;
      unknown code 422; legacy {sections} body preserves other langs;
      GET content exposes sections_by_language.
  V3  Conduct in ru: snapshot sections = ru sections, language_read=ru;
      unfilled language 422; evidence carries ru sections.
  V4  Certificate PDF: 200 application/pdf with %PDF magic + RFC5987
      filename; non-induction 404; unsigned induction 404; outsider 403;
      unauthenticated 401.
"""
import os
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"
os.environ.setdefault("DB_NAME", "contractor_ops")
os.environ["WA_ACCESS_TOKEN"] = ""
os.environ["WA_PHONE_NUMBER_ID"] = ""
os.environ["WHATSAPP_ENABLED"] = "false"
os.environ["TRANSLATE_MOCK"] = "1"

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


def heb(s):
    return any("\u0590" <= ch <= "\u05EA" for ch in str(s))


def sections(n, prefix="סעיף"):
    return [{"title": f"{prefix} {i + 1}", "body": f"תוכן {prefix} {i + 1}"} for i in range(n)]


async def main():
    from server import app
    from contractor_ops.router import _create_token
    from contractor_ops.safety.induction import INDUCTION_TRAINING_TYPE

    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    now_iso = datetime.now(timezone.utc).isoformat()
    paid = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    tag = uuid.uuid4().hex[:8]

    org = f"probe-i3-org-{tag}"
    proj = f"probe-i3-p1-{tag}"
    pm_id = f"probe-i3-pm-{tag}"     # org_admin + project_manager — editor
    mt_id = f"probe-i3-mt-{tag}"     # management_team member — conduct, NOT editor
    out_id = f"probe-i3-out-{tag}"   # PM with NO project membership
    w1 = f"probe-i3-w1-{tag}"
    w2 = f"probe-i3-w2-{tag}"

    await db.organizations.insert_one(
        {"id": org, "name": f"ארגון {tag}", "owner_user_id": pm_id})
    await db.subscriptions.insert_one(
        {"org_id": org, "status": "active", "paid_until": paid})
    await db.users.insert_many([
        {"id": pm_id, "role": "project_manager", "full_name": "מנהל דמו",
         "user_status": "active", "session_version": 0,
         "phone_e164": "+972507710001", "last_login_at": now_iso},
        {"id": mt_id, "role": "management_team", "full_name": "חבר הנהלה",
         "user_status": "active", "session_version": 0,
         "phone_e164": "+972507710002", "last_login_at": now_iso},
        {"id": out_id, "role": "project_manager", "full_name": "זר",
         "user_status": "active", "session_version": 0,
         "phone_e164": "+972507710003", "last_login_at": now_iso},
    ])
    await db.organization_memberships.insert_one(
        {"id": f"i3-om1-{tag}", "org_id": org, "user_id": pm_id, "role": "org_admin"})
    await db.projects.insert_one(
        {"id": proj, "org_id": org, "name": f"פרויקט {tag}", "status": "active"})
    await db.project_memberships.insert_many([
        {"id": f"i3-pm1-{tag}", "project_id": proj, "user_id": pm_id, "role": "project_manager"},
        {"id": f"i3-pm2-{tag}", "project_id": proj, "user_id": mt_id, "role": "management_team"},
    ])
    await db.safety_workers.insert_many([
        {"id": w, "project_id": proj, "full_name": f"עובד {i}", "deletedAt": None,
         "created_at": now_iso}
        for i, w in enumerate([w1, w2], start=1)
    ])
    legacy_id = f"i3-legacy-{tag}"
    await db.safety_trainings.insert_one({
        "id": legacy_id, "project_id": proj, "worker_id": w2,
        "training_type": INDUCTION_TRAINING_TYPE, "trained_at": now_iso,
        "expires_at": None, "worker_signature": None, "created_at": now_iso,
        "created_by": pm_id, "deletedAt": None, "deletedBy": None,
    })

    from contractor_ops.safety.indexes import ensure_safety_indexes
    await ensure_safety_indexes(db)

    def h(uid, role="project_manager"):
        return {"Authorization": f"Bearer {_create_token(uid, role)}"}

    pm_h = h(pm_id)
    mt_h = h(mt_id, "management_team")
    out_h = h(out_id)

    TMPL = f"/api/safety/{proj}/induction-template"
    TRANSLATE = f"{TMPL}/translate"
    CONTENT = f"/api/safety/{proj}/induction/content"
    CONDUCT = f"/api/safety/{proj}/induction/conduct"
    TRAININGS = f"/api/safety/{proj}/trainings"
    CERT = f"/api/safety/{proj}/induction/certificate"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
        # ---------------- V1 — translate DRAFT ----------------
        print("V1 — translate endpoint (mock)")
        r = await c.post(TRANSLATE, json={"target_language": "ru"}, headers=pm_h)
        record("V1a no he content yet → 409 Hebrew",
               r.status_code == 409 and heb(r.json().get("detail")),
               f"status={r.status_code}")
        secs = sections(3, "בטיחות")
        r = await c.put(TMPL, json={"sections": secs}, headers=pm_h)
        assert r.status_code == 200, f"template save failed {r.text[:200]}"
        v_before = r.json()["template"]["version"]
        r = await c.post(TRANSLATE, json={"target_language": "ru"}, headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        record("V1b mock draft: 200, structure 1:1, [ru]-prefixed, draft flag",
               r.status_code == 200 and j.get("draft") is True
               and j.get("target_language") == "ru"
               and len(j.get("sections", [])) == 3
               and j["sections"][0]["title"] == "[ru] בטיחות 1"
               and j["sections"][2]["body"] == "[ru] תוכן בטיחות 3",
               f"status={r.status_code} {str(j)[:120]}")
        doc = await db.induction_templates.find_one({"org_id": org}, {"_id": 0})
        record("V1c persists NOTHING — version unchanged, no ru in doc",
               doc.get("version") == v_before
               and "ru" not in (doc.get("languages") or {}))
        r = await c.post(TRANSLATE, json={"target_language": "he"}, headers=pm_h)
        record("V1d target he → 422", r.status_code == 422)
        r = await c.post(TRANSLATE, json={"target_language": "fr"}, headers=pm_h)
        record("V1e unsupported target → 422 Hebrew",
               r.status_code == 422 and heb(str(r.json().get("detail"))))
        r = await c.post(TRANSLATE, json={"target_language": "ru"}, headers=mt_h)
        record("V1f non-editor (management_team) → 403", r.status_code == 403,
               f"status={r.status_code}")
        r = await c.post(TRANSLATE, json={"target_language": "ru"})
        record("V1g unauthenticated → 401", r.status_code == 401)

        # ---------------- V2 — multi-language save ----------------
        print("V2 — languages map save + content shape")
        ru_secs = [{"title": f"Раздел {i}", "body": f"Текст {i}"} for i in (1, 2, 3)]
        ar_secs = [{"title": "قسم 1", "body": "نص 1"}]
        lang_map = {
            "he": {"sections": secs},
            "ru": {"sections": ru_secs},
            "ar": {"sections": ar_secs},
            "en": {"sections": []},   # empty → removed
        }
        r = await c.put(TMPL, json={"languages": lang_map}, headers=pm_h)
        j = r.json() if r.status_code == 200 else {}
        tpl = j.get("template") or {}
        record("V2a full map save → 200, ONE version inc",
               r.status_code == 200 and tpl.get("version") == v_before + 1,
               f"version={tpl.get('version')} expected={v_before + 1}")
        record("V2b he+ru+ar filled; empty en absent",
               set((tpl.get("languages") or {}).keys()) == {"he", "ru", "ar"})
        r = await c.put(TMPL, json={"languages": {"he": {"sections": []},
                                                  "ru": {"sections": ru_secs}}}, headers=pm_h)
        record("V2c he empty in map → 422 Hebrew",
               r.status_code == 422 and heb(str(r.json().get("detail"))))
        r = await c.put(TMPL, json={"languages": {"he": {"sections": secs},
                                                  "fr": {"sections": ru_secs}}}, headers=pm_h)
        record("V2d unknown language code → 422", r.status_code == 422)
        # malformed sections shapes → 422, never 500 (architect hardening)
        r = await c.put(TMPL, json={"languages": {"he": {"sections": "oops"}}}, headers=pm_h)
        record("V2d1 sections=string → 422", r.status_code == 422, f"status={r.status_code}")
        r = await c.put(TMPL, json={"languages": {"he": {"sections": {"title": "x"}}}}, headers=pm_h)
        record("V2d2 sections=object → 422", r.status_code == 422, f"status={r.status_code}")
        r = await c.put(TMPL, json={"languages": {"he": {"sections": [1, "x"]}}}, headers=pm_h)
        record("V2d3 sections=list of scalars → 422", r.status_code == 422, f"status={r.status_code}")
        r = await c.put(TMPL, json={"languages": {"he": {"sections": [{"bogus": "k"}]}}}, headers=pm_h)
        record("V2d4 section item with wrong keys → 422", r.status_code == 422, f"status={r.status_code}")
        # legacy he-only body preserves the other languages
        secs2 = sections(4, "עדכון")
        r = await c.put(TMPL, json={"sections": secs2}, headers=pm_h)
        tpl2 = (r.json() or {}).get("template") or {}
        record("V2e legacy {sections} body → he updated, ru/ar PRESERVED",
               r.status_code == 200
               and len(tpl2["languages"]["he"]["sections"]) == 4
               and tpl2["languages"].get("ru", {}).get("sections") == ru_secs
               and tpl2["languages"].get("ar", {}).get("sections") == ar_secs)
        r = await c.get(CONTENT, headers=pm_h)
        jc = r.json() if r.status_code == 200 else {}
        record("V2f GET content: languages_filled + sections_by_language + legacy sections",
               r.status_code == 200
               and set(jc.get("languages_filled") or []) == {"he", "ru", "ar"}
               and jc.get("sections") == jc.get("sections_by_language", {}).get("he")
               and jc.get("sections_by_language", {}).get("ru") == ru_secs,
               f"filled={jc.get('languages_filled')}")

        # ---------------- V3 — conduct in ru ----------------
        print("V3 — conduct in a non-he language")
        exp = (date.today() + timedelta(days=300)).isoformat()
        r = await c.post(CONDUCT, data={
            "worker_id": w1, "language_choice": "ru", "expires_at": exp,
            "signer_name": "עובד 1", "signature_type": "typed", "typed_name": "עובד 1",
        }, headers=pm_h)
        ind_ru = r.json() if r.status_code == 201 else {}
        record("V3a conduct language_choice=ru → 201, language_read=ru",
               r.status_code == 201
               and (ind_ru.get("worker_signature") or {}).get("language_read") == "ru",
               f"status={r.status_code} {r.text[:150]}")
        snap = await db.induction_content_snapshots.find_one(
            {"id": (ind_ru.get("worker_signature") or {}).get("snapshot_id")}, {"_id": 0})
        record("V3b snapshot holds the RU sections (what the worker read)",
               (snap or {}).get("sections") == ru_secs
               and (snap or {}).get("language") == "ru")
        r = await c.post(CONDUCT, data={
            "worker_id": w1, "language_choice": "en",
            "signer_name": "עובד 1", "signature_type": "typed", "typed_name": "עובד 1",
        }, headers=pm_h)
        record("V3c unfilled language (en) → 422 Hebrew",
               r.status_code == 422 and heb(str(r.json().get("detail"))),
               f"status={r.status_code}")
        EV = f"/api/safety/{proj}/induction/evidence"
        r = await c.get(f"{EV}/{ind_ru.get('id')}", headers=pm_h)
        je = r.json() if r.status_code == 200 else {}
        record("V3d evidence returns the ru sections + language_read=ru",
               r.status_code == 200 and je.get("sections") == ru_secs
               and je.get("language_read") == "ru")

        # ---------------- V4 — certificate PDF ----------------
        print("V4 — certificate PDF")
        r = await c.get(f"{CERT}/{ind_ru.get('id')}", headers=pm_h)
        ct = r.headers.get("content-type", "")
        cd = r.headers.get("content-disposition", "")
        record("V4a signed induction → 200 application/pdf with %PDF magic",
               r.status_code == 200 and ct.startswith("application/pdf")
               and r.content[:4] == b"%PDF",
               f"status={r.status_code} ct={ct}")
        record("V4b RFC5987 Hebrew filename in Content-Disposition",
               "filename*=UTF-8''" in cd and "%D7" in cd, f"cd={cd[:80]}")
        # non-induction training
        r = await c.post(TRAININGS, json={
            "worker_id": w2, "training_type": "עבודה בגובה", "trained_at": now_iso,
        }, headers=pm_h)
        normal = r.json() if r.status_code == 201 else {}
        r = await c.get(f"{CERT}/{normal.get('id')}", headers=pm_h)
        record("V4c non-induction training id → 404 Hebrew",
               r.status_code == 404 and heb(str(r.json().get("detail"))))
        r = await c.get(f"{CERT}/{legacy_id}", headers=pm_h)
        record("V4d unsigned induction → 404", r.status_code == 404)
        r = await c.get(f"{CERT}/{ind_ru.get('id')}", headers=out_h)
        record("V4e no project access → 403", r.status_code == 403,
               f"status={r.status_code}")
        r = await c.get(f"{CERT}/{ind_ru.get('id')}")
        record("V4f unauthenticated → 401", r.status_code == 401)
        # conduct-capable reader (management_team) may download too
        r = await c.get(f"{CERT}/{ind_ru.get('id')}", headers=mt_h)
        record("V4g management_team project member → 200", r.status_code == 200,
               f"status={r.status_code}")

    # cleanup
    await db.organizations.delete_many({"id": org})
    await db.subscriptions.delete_many({"org_id": org})
    await db.users.delete_many({"id": {"$in": [pm_id, mt_id, out_id]}})
    await db.organization_memberships.delete_many({"org_id": org})
    await db.projects.delete_many({"id": proj})
    await db.project_memberships.delete_many({"project_id": proj})
    await db.safety_workers.delete_many({"project_id": proj})
    await db.safety_trainings.delete_many({"project_id": proj})
    await db.induction_templates.delete_many({"org_id": org})
    await db.induction_content_snapshots.delete_many({"org_id": org})
    await db.audit_events.delete_many({"payload.org_id": org})
    await db.audit_events.delete_many({"payload.project_id": proj})

    passed = sum(1 for _, p in RESULTS if p)
    print(f"\n===== {passed}/{len(RESULTS)} PASSED =====")
    if passed != len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
