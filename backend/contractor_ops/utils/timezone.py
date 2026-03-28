try:
    import zoneinfo
    IL_TZ = zoneinfo.ZoneInfo("Asia/Jerusalem")
except ImportError:
    from dateutil import tz as _tz
    IL_TZ = _tz.gettz("Asia/Jerusalem")

def israel_today() -> str:
    from datetime import datetime
    return datetime.now(IL_TZ).strftime("%Y-%m-%d")

def israel_day_start_utc(date_str: str) -> str:
    from datetime import datetime, timezone
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    local_start = dt.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=IL_TZ)
    return local_start.astimezone(timezone.utc).isoformat()
