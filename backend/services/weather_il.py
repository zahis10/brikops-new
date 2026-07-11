"""
IL weather (batch diary-d4b) — IMS city FORECAST auto-fill for the work diary.

W0 DECISION (locked 2026-07-11): source = isr_cities.xml morning forecast
(15 cities, ISO-8859-8, issue ~04:40 IL, temp min/max + weather code, NO rain
amounts) + strategy s1 FORECAST-ONLY. The desc is SELF-DESCRIBING
("תחזית: <official Hebrew code desc>") — signed records always tell the
reader it was a forecast (no silent partials, ever). Envista observed-upgrade
is OUT of this batch entirely (no token handling anywhere).

Hard rules honored here:
  - Parse BYTES with xml.etree (encoding declared ISO-8859-8 in the prolog);
    NEVER .decode('utf-8').
  - Cache-first (Mongo weather_cache, unique (city_code, date)) — a second
    project in the same city/day makes ZERO HTTP calls.
  - Fetch: ONE attempt, total timeout ≤2.5s, cache-busting param (the feed is
    CDN-served with max-age=14d) AND the response must actually cover the
    requested date — else None.
  - rain_mm is ALWAYS None (feed has no amounts; the Hebrew desc carries rain).
  - get_daily_weather NEVER raises — any failure → None → the diary section
    stays fully manual (fail-soft; create latency budget respected).

Single source of truth for the city list + code map (country-packs
discipline) — the FE copy in diaryLabels.js mirrors IL_WEATHER_CITIES.
"""
import logging
import re
import time
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)

IMS_CITIES_URL = "https://ims.gov.il/sites/default/files/ims_data/xml_files/isr_cities.xml"

# (code, Hebrew label) — hardcoded from the W0 fixture (15 locations).
IL_WEATHER_CITIES = [
    ("520", "אילת"),
    ("114", "אשדוד"),
    ("513", "באר שבע"),
    ("203", "בית שאן"),
    ("115", "חיפה"),
    ("202", "טבריה"),
    ("510", "ירושלים"),
    ("204", "לוד"),
    ("106", "מצפה רמון"),
    ("207", "נצרת"),
    ("105", "עין גדי"),
    ("209", "עפולה"),
    ("507", "צפת"),
    ("201", "קצרין"),
    ("402", "תל אביב - יפו"),
]
CITY_CODES = {c for c, _ in IL_WEATHER_CITIES}

# The 23 official IMS Hebrew weather-code descriptions — hardcoded from the
# W0 fixture backend/tests/fixtures/ims_weather_codes_he.json.
WEATHER_CODE_HE = {
    "1250": "בהיר",
    "1220": "מעונן חלקית",
    "1230": "מעונן",
    "1570": "אביך",
    "1010": "סופות חול",
    "1160": "ערפל",
    "1310": "חם",
    "1580": "חם מאד",
    "1270": "הביל",
    "1320": "קר",
    "1590": "קר מאד",
    "1300": "קרה",
    "1530": "מעונן חלקית, יתכן גשם",
    "1540": "מעונן, יתכן גשם",
    "1560": "מעונן עם גשם קל",
    "1140": "גשום",
    "1020": "סופות רעמים",
    "1510": "סוער",
    "1260": "רוחות חזקות",
    "1080": "שלג מעורב בגשם",
    "1070": "שלג קל",
    "1060": "שלג",
    "1520": "שלג כבד",
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_city_forecast(raw_bytes: bytes, city_code: str, date: str):
    """
    Pure parser (unit-tested on the committed W0 fixture). Returns the diary
    weather value dict for (city_code, date), or None if the city/date is not
    covered or the payload is malformed. NEVER raises.

    Feed shape: <IsraelCitiesWeatherForecastMorning> → <Location> →
    <LocationMetaData><LocationId> + <LocationData> → <TimeUnitData> →
    <Date> + <Element><ElementName>/<ElementValue>.
    ET.fromstring gets BYTES — the prolog declares ISO-8859-8.
    """
    try:
        root = ET.fromstring(raw_bytes)
        for loc in root.findall("Location"):
            meta = loc.find("LocationMetaData")
            if meta is None:
                continue
            if (meta.findtext("LocationId") or "").strip() != str(city_code):
                continue
            ld = loc.find("LocationData")
            if ld is None:
                return None
            for tud in ld.findall("TimeUnitData"):
                if (tud.findtext("Date") or "").strip() != date:
                    continue
                vals = {}
                for el in tud.findall("Element"):
                    name = (el.findtext("ElementName") or "").strip()
                    vals[name] = (el.findtext("ElementValue") or "").strip()
                code = vals.get("Weather code")
                desc_he = WEATHER_CODE_HE.get(code)
                if not desc_he:
                    return None
                try:
                    temp_min = int(vals["Minimum temperature"])
                    temp_max = int(vals["Maximum temperature"])
                except (KeyError, ValueError):
                    return None
                return {
                    "desc": f"תחזית: {desc_he}",
                    "temp_min": temp_min,
                    "temp_max": temp_max,
                    "rain_mm": None,   # feed carries no amounts — always None
                    "source": "derived",
                }
            return None  # city found, requested date not in the feed window
        return None  # city not in the feed
    except Exception as e:
        logger.warning(f"[WEATHER] parse failed (fail-soft): {e}")
        return None


async def _fetch_feed_bytes() -> bytes:
    """ONE attempt, total timeout 2.5s, cache-busting param (CDN max-age=14d)."""
    import aiohttp
    timeout = aiohttp.ClientTimeout(total=2.5)
    url = f"{IMS_CITIES_URL}?t={int(time.time())}"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"IMS feed HTTP {resp.status}")
            return await resp.read()


async def get_daily_weather(db, city_code: str, date: str):
    """
    Cache-first daily forecast for the diary. Returns the weather value dict
    (source=="derived") or None on ANY failure/miss. NEVER raises.
    """
    try:
        if city_code not in CITY_CODES or not _DATE_RE.fullmatch(date or ""):
            return None

        cached = await db.weather_cache.find_one(
            {"city_code": city_code, "date": date}, {"_id": 0, "value": 1})
        if cached and cached.get("value"):
            return cached["value"]

        raw = await _fetch_feed_bytes()
        value = parse_city_forecast(raw, city_code, date)
        if value is None:
            return None

        await db.weather_cache.update_one(
            {"city_code": city_code, "date": date},
            {"$set": {"value": value, "fetched_at": time.time()},
             "$setOnInsert": {"city_code": city_code, "date": date}},
            upsert=True,
        )
        return value
    except Exception as e:
        logger.warning(f"[WEATHER] get_daily_weather failed (fail-soft): {e}")
        return None
