"""FUNCTIONAL probes for diary-d4b (IMS weather auto-fill, forecast-only s1).

Same in-process harness as probe_diary_d4a.py: REAL FastAPI app (httpx
ASGITransport), ENABLE_WORK_DIARY + ENABLE_SAFETY_MODULE, REAL local Mongo,
FILES_STORAGE_BACKEND=local (NEVER a real bucket), REAL JWTs from _create_token.

NO real IMS HTTP anywhere — the fetcher is monkeypatched to the committed W0
fixture (backend/tests/fixtures/ims_isr_cities_2026-07-11.xml) with a call
counter, so cache behavior is provable.

Covers:
  V1  parser unit tests on the committed fixture (Tel Aviv 402 / 2026-07-11
      -> exact value dict; unknown city/date -> None; malformed -> None)
  V2  cache-first: 2 calls same (city, date) -> exactly ONE fetch; bad city
      code -> None with ZERO fetches
  V3  fail-soft: fetcher raising -> get_daily_weather None; entry CREATE with
      city set + fetcher down -> 200, weather stays None (never 500)
  V4  derive semantics over HTTP: PUT city -> create -> weather derived
      ("תחזית: …", source=derived); manual PATCH -> refresh keeps manual;
      derived + refresh with fetcher down -> KEEPS old derived (no wipe)
  V5  RBAC: non-member PM PUT -> 403; owner (reader) PUT -> 403; unknown code
      -> 422; null clears; audit diary_weather_city_set written
  V6  list envelope carries weather_city
  V7  single-entry PDF renders with derived weather -> 200 %PDF-
"""
import os
os.environ["ENABLE_WORK_DIARY"] = "true"
os.environ["ENABLE_SAFETY_MODULE"] = "true"
os.environ["FILES_STORAGE_BACKEND"] = "local"
os.environ["MONGO_URL"] = "mongodb://localhost:27017"  # force local — repl env may carry Atlas
os.environ.setdefault("DB_NAME", "contractor_ops")

import sys
import uuid
import asyncio
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

RESULTS = []
FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "fixtures", "ims_isr_cities_2026-07-11.xml")
FIX_DATE = "2026-07-11"


def record(name, passed, detail=""):
    RESULTS.append((name, passed, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


async def main():
    from server import app  # noqa: import after env flags
    from contractor_ops.router import _create_token
    from contractor_ops.utils.timezone import IL_TZ
    from services import weather_il
    from services.weather_il import parse_city_forecast, get_daily_weather

    raw = open(FIXTURE, "rb").read()
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

    # ================= V1 — pure parser on the committed fixture ============
    v = parse_city_forecast(raw, "402", FIX_DATE)
    record("V1a Tel Aviv 402/2026-07-11 exact value",
           v == {"desc": "תחזית: מעונן חלקית", "temp_min": 24, "temp_max": 30,
                 "rain_mm": None, "source": "derived"}, f"got={v}")
    record("V1b unknown city -> None", parse_city_forecast(raw, "999", FIX_DATE) is None)
    record("V1c date outside window -> None",
           parse_city_forecast(raw, "402", "2030-01-01") is None)
    record("V1d malformed bytes -> None (never raises)",
           parse_city_forecast(b"<broken", "402", FIX_DATE) is None)
    record("V1e utf-8 decode NOT used (raw ISO-8859-8 bytes parse ok)",
           parse_city_forecast(raw, "510", FIX_DATE) is not None)

    # ================= V2 — cache-first with a counted fake fetcher =========
    calls = {"n": 0}

    async def counted_fetch():
        calls["n"] += 1
        return raw

    async def broken_fetch():
        calls["n"] += 1
        raise RuntimeError("IMS down (simulated)")

    orig_fetch = weather_il._fetch_feed_bytes
    weather_il._fetch_feed_bytes = counted_fetch
    await db.weather_cache.delete_many({"date": FIX_DATE})
    try:
        r1 = await get_daily_weather(db, "402", FIX_DATE)
        r2 = await get_daily_weather(db, "402", FIX_DATE)  # second project, same city/day
        record("V2a two calls same (city,date) -> ONE fetch (cache hit)",
               r1 == r2 and r1 is not None and calls["n"] == 1, f"fetches={calls['n']}")
        before = calls["n"]
        r3 = await get_daily_weather(db, "999", FIX_DATE)
        record("V2b unknown city code -> None, ZERO fetches",
               r3 is None and calls["n"] == before, f"fetches={calls['n']}")
        r4 = await get_daily_weather(db, "402", "not-a-date")
        record("V2c bad date format -> None, ZERO fetches",
               r4 is None and calls["n"] == before)

        # ============= V3 — fail-soft when the fetcher is down ==============
        weather_il._fetch_feed_bytes = broken_fetch
        await db.weather_cache.delete_many({"date": FIX_DATE})
        r5 = await get_daily_weather(db, "402", FIX_DATE)
        record("V3a fetcher raises -> None (never raises)", r5 is None)

        # ================= HTTP harness =====================================
        tag = uuid.uuid4().hex[:8]
        pid = f"probe-d4b-{tag}"
        pm_id = f"probe-d4b-pm-{tag}"
        owner_id = f"probe-d4b-owner-{tag}"
        stranger_id = f"probe-d4b-str-{tag}"
        org_id = f"probe-d4b-org-{tag}"

        await db.organizations.insert_one({"id": org_id, "name": f"ארגון {tag}", "owner_user_id": owner_id})
        await db.subscriptions.insert_one({
            "org_id": org_id, "status": "active",
            "paid_until": (datetime.now(IL_TZ) + timedelta(days=30)).isoformat(),
        })
        await db.projects.insert_one({
            "id": pid, "name": f"פרויקט d4b {tag}", "org_id": org_id, "deletedAt": None,
        })
        await db.users.insert_many([
            {"id": pm_id, "role": "project_manager", "full_name": "מנהל בדיקה",
             "user_status": "active", "session_version": 0},
            {"id": owner_id, "role": "owner", "full_name": "יזם בדיקה",
             "user_status": "active", "session_version": 0},
            {"id": stranger_id, "role": "project_manager", "full_name": "זר בדיקה",
             "user_status": "active", "session_version": 0},
        ])
        await db.organization_memberships.insert_many([
            {"id": f"om1-{tag}", "org_id": org_id, "user_id": pm_id, "role": "member"},
            {"id": f"om2-{tag}", "org_id": org_id, "user_id": owner_id, "role": "owner"},
        ])
        await db.project_memberships.insert_many([
            {"id": f"m1-{tag}", "project_id": pid, "user_id": pm_id, "role": "project_manager"},
            {"id": f"m2-{tag}", "project_id": pid, "user_id": owner_id, "role": "owner"},
        ])

        pm_h = {"Authorization": f"Bearer {_create_token(pm_id, 'project_manager')}"}
        ow_h = {"Authorization": f"Bearer {_create_token(owner_id, 'owner')}"}
        str_h = {"Authorization": f"Bearer {_create_token(stranger_id, 'project_manager')}"}

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://probe", timeout=60) as c:
            base = f"/api/work-diary/{pid}/entries"
            wc = f"/api/work-diary/{pid}/weather-city"

            # ---------- V5 RBAC + validation FIRST (no city set yet) ----------
            r = await c.put(wc, json={"weather_city": "402"}, headers=str_h)
            record("V5a non-member PM PUT -> 403", r.status_code == 403, f"status={r.status_code}")
            r = await c.put(wc, json={"weather_city": "402"}, headers=ow_h)
            record("V5b owner (reader) PUT -> 403", r.status_code == 403, f"status={r.status_code}")
            r = await c.put(wc, json={"weather_city": "9999"}, headers=pm_h)
            record("V5c unknown code -> 422 Hebrew",
                   r.status_code == 422 and "קוד עיר לא מוכר" in r.text, f"status={r.status_code}")

            # ---------- V3b create with city set + fetcher DOWN -> fail-soft --
            weather_il._fetch_feed_bytes = broken_fetch
            await db.weather_cache.delete_many({"date": FIX_DATE})
            r = await c.put(wc, json={"weather_city": "402"}, headers=pm_h)
            record("V5d writer PUT valid city -> 200 + echo",
                   r.status_code == 200 and r.json().get("weather_city") == "402",
                   f"status={r.status_code}")
            ev = await db.audit_events.find_one(
                {"action": "diary_weather_city_set", "entity_id": pid}, sort=[("_id", -1)])
            record("V5e audit diary_weather_city_set written",
                   bool(ev) and ev.get("payload", {}).get("weather_city") == "402")

            r = await c.post(base, json={"diary_date": FIX_DATE}, headers=pm_h)
            eid = r.json().get("id")
            record("V3b create with fetcher DOWN -> 200, weather None (fail-soft)",
                   r.status_code == 200 and r.json().get("weather") is None,
                   f"status={r.status_code} weather={r.json().get('weather')}")

            # ---------- V4 refresh derives once the feed is back --------------
            weather_il._fetch_feed_bytes = counted_fetch
            r = await c.post(f"{base}/{eid}/refresh-derived", headers=pm_h)
            w = r.json().get("weather") or {}
            record("V4a refresh (feed back) -> derived forecast",
                   r.status_code == 200 and w.get("source") == "derived"
                   and w.get("desc", "").startswith("תחזית:")
                   and w.get("temp_min") == 24 and w.get("temp_max") == 30
                   and w.get("rain_mm") is None,
                   f"weather={w}")

            # derived + fetcher DOWN + empty cache -> refresh KEEPS old derived
            weather_il._fetch_feed_bytes = broken_fetch
            await db.weather_cache.delete_many({"date": FIX_DATE})
            r = await c.post(f"{base}/{eid}/refresh-derived", headers=pm_h)
            w2 = r.json().get("weather") or {}
            record("V4b refresh with fetch-fail KEEPS existing derived (no wipe)",
                   r.status_code == 200 and w2.get("source") == "derived"
                   and w2.get("desc") == w.get("desc"), f"weather={w2}")

            # manual overwrite survives refresh (manual is NEVER overwritten)
            weather_il._fetch_feed_bytes = counted_fetch
            r = await c.patch(f"{base}/{eid}",
                              json={"weather": {"desc": "שרב", "source": "manual"}}, headers=pm_h)
            record("V4c manual PATCH weather -> 200", r.status_code == 200)
            r = await c.post(f"{base}/{eid}/refresh-derived", headers=pm_h)
            w3 = r.json().get("weather") or {}
            record("V4d refresh does NOT overwrite manual weather",
                   r.status_code == 200 and w3.get("source") == "manual"
                   and w3.get("desc") == "שרב", f"weather={w3}")

            # ---------- V6 list envelope carries weather_city -----------------
            r = await c.get(base, params={"month": FIX_DATE[:7]}, headers=pm_h)
            record("V6a list envelope weather_city == '402'",
                   r.status_code == 200 and r.json().get("weather_city") == "402")
            r = await c.put(wc, json={"weather_city": None}, headers=pm_h)
            r2 = await c.get(base, params={"month": FIX_DATE[:7]}, headers=pm_h)
            record("V6b null clears -> envelope weather_city None",
                   r.status_code == 200 and r2.json().get("weather_city") is None)
            # restore for PDF check
            await c.put(wc, json={"weather_city": "402"}, headers=pm_h)

            # ---------- V7 PDF renders with derived weather -------------------
            # fresh entry with derived weather, sign, export
            await db.work_diary_entries.delete_many({"id": eid})
            r = await c.post(base, json={"diary_date": FIX_DATE}, headers=pm_h)
            eid2 = r.json()["id"]
            wnew = r.json().get("weather") or {}
            record("V7a create with city+cache -> weather derived at create",
                   wnew.get("source") == "derived", f"weather={wnew}")
            await c.patch(f"{base}/{eid2}", json={"work_description": "בדיקת PDF מזג אוויר"}, headers=pm_h)
            rs = await c.post(f"{base}/{eid2}/signature",
                              data={"signer_name": "מנהל בדיקה", "signature_type": "typed",
                                    "typed_name": "מנהל בדיקה"}, headers=pm_h)
            r = await c.get(f"{base}/{eid2}/export/pdf", headers=pm_h)
            record("V7b signed entry PDF with derived weather -> 200 %PDF-",
                   rs.status_code == 200 and r.status_code == 200 and r.content[:5] == b"%PDF-",
                   f"sign={rs.status_code} export={r.status_code}")

        # cleanup
        await db.projects.delete_many({"id": pid})
        await db.organizations.delete_many({"id": org_id})
        await db.subscriptions.delete_many({"org_id": org_id})
        await db.users.delete_many({"id": {"$in": [pm_id, owner_id, stranger_id]}})
        await db.organization_memberships.delete_many({"org_id": org_id})
        await db.project_memberships.delete_many({"project_id": pid})
        await db.work_diary_entries.delete_many({"project_id": pid})
        await db.work_diary_settings.delete_many({"project_id": pid})
        await db.audit_events.delete_many({"actor_id": {"$in": [pm_id, owner_id]}})
        await db.weather_cache.delete_many({"date": FIX_DATE})
    finally:
        weather_il._fetch_feed_bytes = orig_fetch

    fails = [r for r in RESULTS if not r[1]]
    print(f"\n{'='*50}\nTOTAL: {len(RESULTS)}  PASS: {len(RESULTS)-len(fails)}  FAIL: {len(fails)}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
