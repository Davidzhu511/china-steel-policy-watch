from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def should_run(event_name: str, schedule: str, now: datetime | None = None) -> bool:
    if event_name in {"workflow_dispatch", "push"}:
        return True
    local_now = (now or datetime.now(ZoneInfo("Europe/Berlin"))).astimezone(
        ZoneInfo("Europe/Berlin")
    )
    offset_hours = int((local_now.utcoffset().total_seconds() if local_now.utcoffset() else 0) / 3600)
    if schedule == "50 5 * * *":
        return offset_hours == 2
    if schedule == "50 6 * * *":
        return offset_hours == 1
    return False
