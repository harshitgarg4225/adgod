"""IST business-day boundaries. The product's money windows (today's spend, monthly cap,
daily report) follow the ad account's timezone — Asia/Kolkata — and Meta's
date_preset=today does the same. Keying anything to UTC midnight clobbers every night's
numbers between 00:00–05:30 IST."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def ist_day_start(now: datetime | None = None) -> datetime:
    """The instant the current IST calendar day began (tz-aware)."""
    now = now or datetime.now(IST)
    return datetime.combine(now.astimezone(IST).date(), time(0), tzinfo=IST)


def ist_week_start(days: int = 6, now: datetime | None = None) -> datetime:
    return ist_day_start(now) - timedelta(days=days)


def ist_month_start(now: datetime | None = None) -> datetime:
    day = ist_day_start(now)
    return day.replace(day=1)
