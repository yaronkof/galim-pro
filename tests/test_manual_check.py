from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from galim_pro.client import GalimApiError
from galim_pro.monitor import CheckResult, GalimMonitor


def test_manual_check_wakes_monitor():
    monitor = object.__new__(GalimMonitor)
    import threading

    monitor.wake_event = threading.Event()
    monitor.request_check()
    assert monitor.wake_event.is_set()


class RecordingPublisher:
    def __init__(self):
        self.last_checks = []
        self.unavailable_count = 0

    def publish_last_check(self, completed_at, **attributes):
        self.last_checks.append((completed_at, attributes))

    def publish_unavailable(self):
        self.unavailable_count += 1


@pytest.mark.parametrize("source", ["manual", "scheduled"])
def test_completed_check_publishes_source_and_counts(source):
    monitor = object.__new__(GalimMonitor)
    monitor.timezone = ZoneInfo("Asia/Jerusalem")
    monitor.publisher = RecordingPublisher()
    monitor.poll_once = lambda: CheckResult(tasks_published=5, new_tasks=2)

    monitor.run_check(source)

    completed_at, attributes = monitor.publisher.last_checks[0]
    assert completed_at.tzinfo == monitor.timezone
    assert attributes == {
        "source": source,
        "success": True,
        "tasks_published": 5,
        "new_tasks": 2,
        "error_summary": None,
    }


def test_failed_check_publishes_generic_error_without_exception_details(caplog):
    monitor = object.__new__(GalimMonitor)
    monitor.timezone = ZoneInfo("Asia/Jerusalem")
    monitor.publisher = RecordingPublisher()

    def fail():
        raise GalimApiError("private upstream response must not be published")

    monitor.poll_once = fail
    monitor.run_check("scheduled")

    _completed_at, attributes = monitor.publisher.last_checks[0]
    assert attributes["success"] is False
    assert attributes["tasks_published"] == 0
    assert attributes["new_tasks"] == 0
    assert attributes["error_summary"] == "Galim API request failed"
    assert "private" not in str(attributes)
    assert "private" not in caplog.text
    assert monitor.publisher.unavailable_count == 1


class StopEvent:
    def __init__(self):
        self.stopped = False

    def is_set(self):
        return self.stopped


class OneCheckWakeEvent:
    def __init__(self, stop_event, manual):
        self.stop_event = stop_event
        self.manual = manual
        self.wait_count = 0

    def wait(self, _timeout):
        self.wait_count += 1
        if self.wait_count == 1:
            return self.manual
        self.stop_event.stopped = True
        return True

    def clear(self):
        pass


class RunPublisher:
    def publish_discovery(self):
        pass


@pytest.mark.parametrize(
    ("manual", "expected_source", "expected_schedule_publications"),
    [(True, "manual", 1), (False, "scheduled", 2)],
)
def test_run_distinguishes_source_and_only_scheduled_checks_advance_schedule(
    manual, expected_source, expected_schedule_publications
):
    monitor = object.__new__(GalimMonitor)
    monitor.timezone = ZoneInfo("Asia/Jerusalem")
    monitor.publisher = RunPublisher()
    monitor.stop_event = StopEvent()
    monitor.wake_event = OneCheckWakeEvent(monitor.stop_event, manual)
    sources = []
    schedule_publications = []
    monitor.run_check = sources.append

    def publish_next_check():
        next_poll = datetime.now(monitor.timezone) + timedelta(hours=1)
        schedule_publications.append(next_poll)
        return next_poll

    monitor.publish_next_check = publish_next_check

    monitor.run()

    assert sources == [expected_source]
    assert len(schedule_publications) == expected_schedule_publications
