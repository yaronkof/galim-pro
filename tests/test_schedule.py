from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from galim_pro.monitor import GalimMonitor


def _monitor_with_schedule(*values):
    monitor = object.__new__(GalimMonitor)
    monitor.settings = SimpleNamespace(schedules=values)
    monitor.timezone = ZoneInfo("Asia/Jerusalem")
    return monitor


def test_next_poll_uses_same_day_when_time_is_upcoming():
    monitor = _monitor_with_schedule("13:00", "15:00", "19:00")
    now = datetime(2026, 9, 13, 14, 0, tzinfo=monitor.timezone)
    assert monitor.next_poll_at(now) == datetime(
        2026, 9, 13, 15, 0, tzinfo=monitor.timezone
    )


def test_next_poll_rolls_to_tomorrow_after_last_time():
    monitor = _monitor_with_schedule("13:00", "15:00", "19:00")
    now = datetime(2026, 9, 13, 21, 0, tzinfo=monitor.timezone)
    assert monitor.next_poll_at(now) == datetime(
        2026, 9, 14, 13, 0, tzinfo=monitor.timezone
    )
