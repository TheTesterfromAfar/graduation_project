"""Timezone helpers. The database stores naive UTC; people see local time."""
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_FORMAT = "%Y-%m-%d %H:%M"


@lru_cache(maxsize=8)
def load_timezone(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        # Mongolia has been UTC+8 year-round since 2017, so this fallback is exact for the default.
        return timezone(timedelta(hours=8)) if name == "Asia/Ulaanbaatar" else timezone.utc


def to_local(value, tz_name):
    """Naive-UTC datetime -> aware local datetime."""
    return value.replace(tzinfo=timezone.utc).astimezone(load_timezone(tz_name))


def format_local(value, tz_name, fmt=DEFAULT_FORMAT):
    if value is None:
        return ""
    return to_local(value, tz_name).strftime(fmt)


def local_day_start_utc(day, tz_name):
    """Start of a local calendar day, as naive UTC (for comparing with stored timestamps)."""
    start = datetime.combine(day, time.min, tzinfo=load_timezone(tz_name))
    return start.astimezone(timezone.utc).replace(tzinfo=None)
