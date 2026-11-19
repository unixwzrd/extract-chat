"""Display-only time conversion; source epochs and UTC filenames stay intact."""

from datetime import datetime, timedelta, timezone, tzinfo
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def resolve_timezone(name: str = "local") -> tzinfo | None:
    if name == "local":
        return None
    if name in {"UTC", "GMT"}:
        return timezone.utc
    fixed = re.fullmatch(r"(?:UTC|GMT)([+-])(\d{2}):(\d{2})", name)
    if fixed:
        hours, minutes = int(fixed[2]), int(fixed[3])
        if hours < 24 and minutes < 60:
            offset = timedelta(hours=hours, minutes=minutes) * (1 if fixed[1] == "+" else -1)
            return timezone(offset, name)
        raise ValueError("Time-zone offsets must be less than 24 hours, with minutes between 00 and 59.")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, OSError, ValueError) as error:
        raise ValueError(f"Unknown time zone {name!r}. Use an installed IANA name such as America/Chicago, UTC, or UTC+05:30.") from error


def display_timestamp(timestamp: float | datetime, zone: str = "local") -> str:
    target = resolve_timezone(zone)
    value = timestamp if isinstance(timestamp, datetime) else datetime.fromtimestamp(float(timestamp), timezone.utc)
    # astimezone() applies local DST rules for this timestamp, not today's offset.
    value = value.astimezone(target) if target is not None else value.astimezone()
    offset = value.strftime("%z")
    offset = offset[:3] + ":" + offset[3:] if len(offset) == 5 else offset
    stamp = value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return f"{stamp} {value.tzname() or zone} (UTC{offset})"
