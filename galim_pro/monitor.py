from __future__ import annotations

import logging
import signal
import threading
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .auth import GalimAuthenticator
from .client import GalimApiError, GalimClient, GalimSessionExpired
from .config import Settings
from .mqtt import GalimMqttPublisher
from .state import SeenTasks

LOGGER = logging.getLogger(__name__)

CheckSource = Literal["manual", "scheduled"]


@dataclass(frozen=True)
class CheckResult:
    tasks_published: int
    new_tasks: int


class GalimMonitor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.authenticator = GalimAuthenticator(
            settings.galim_username,
            settings.galim_password,
            storage_state_path=settings.data_dir / "browser_state.json",
            headless=settings.headless,
        )
        self.publisher = GalimMqttPublisher(
            settings.mqtt_host,
            settings.mqtt_port,
            username=settings.mqtt_username,
            password=settings.mqtt_password,
        )
        self.seen = SeenTasks(settings.data_dir / "seen_tasks.json")
        self.client: GalimClient | None = None
        self.stop_event = threading.Event()
        self.wake_event = threading.Event()
        self.publisher.set_check_callback(self.request_check)
        try:
            self.timezone = ZoneInfo(settings.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown timezone: {settings.timezone}") from exc

    def next_poll_at(self, now: datetime | None = None) -> datetime:
        current = now or datetime.now(self.timezone)
        if current.tzinfo is None:
            current = current.replace(tzinfo=self.timezone)
        candidates = []
        for days_ahead in (0, 1):
            date = current.date() + timedelta(days=days_ahead)
            for value in self.settings.schedules:
                hour, minute = (int(part) for part in value.split(":"))
                candidate = datetime.combine(date, time(hour, minute), self.timezone)
                if candidate > current:
                    candidates.append(candidate)
        return min(candidates)

    def _login(self, *, clear_saved_session: bool = False) -> None:
        if clear_saved_session:
            self.authenticator.clear_saved_session()
        if self.client:
            self.client.close()
        sid = self.authenticator.login()
        self.client = GalimClient(sid)
        LOGGER.info("Galim LMS session is ready")

    def poll_once(self) -> CheckResult:
        if self.client is None:
            self._login()
        assert self.client is not None
        try:
            tasks = self.client.fetch_tasks()
        except GalimSessionExpired:
            LOGGER.info("Galim session expired; authenticating again")
            self._login(clear_saved_session=True)
            assert self.client is not None
            tasks = self.client.fetch_tasks()

        first_poll = not self.seen.initialized
        new_tasks = self.seen.update(tasks)
        self.publisher.publish_tasks(tasks)
        if not (first_poll and self.settings.seed_quietly):
            self.publisher.publish_new_tasks(new_tasks)
        LOGGER.info("Published %d task(s); %d new", len(tasks), len(new_tasks))
        return CheckResult(tasks_published=len(tasks), new_tasks=len(new_tasks))

    def request_check(self) -> None:
        self.wake_event.set()

    def publish_next_check(self, now: datetime | None = None) -> datetime:
        next_poll = self.next_poll_at(now)
        self.publisher.publish_next_check(next_poll)
        return next_poll

    def run_check(self, source: CheckSource) -> None:
        success = False
        tasks_published = 0
        new_tasks = 0
        error_summary: str | None = None
        try:
            result = self.poll_once()
            success = True
            tasks_published = result.tasks_published
            new_tasks = result.new_tasks
        except GalimApiError:
            LOGGER.error("Galim API error while checking homework")
            error_summary = "Galim API request failed"
            self.publisher.publish_unavailable()
        except Exception as exc:
            LOGGER.error("Unexpected monitor failure (%s)", type(exc).__name__)
            error_summary = "Unexpected monitor failure"
            self.publisher.publish_unavailable()
        finally:
            self.publisher.publish_last_check(
                datetime.now(self.timezone),
                source=source,
                success=success,
                tasks_published=tasks_published,
                new_tasks=new_tasks,
                error_summary=error_summary,
            )

    def run(self) -> None:
        self.publisher.publish_discovery()
        next_poll = self.publish_next_check()
        LOGGER.info("Next homework poll scheduled for %s", next_poll.isoformat())
        while not self.stop_event.is_set():
            wait_seconds = max((next_poll - datetime.now(self.timezone)).total_seconds(), 0)
            manual_check = self.wake_event.wait(wait_seconds)
            self.wake_event.clear()
            if self.stop_event.is_set():
                break
            source: CheckSource = "manual" if manual_check else "scheduled"
            if manual_check:
                LOGGER.info("Running a manually requested homework check")
            self.run_check(source)
            if source == "scheduled":
                next_poll = self.publish_next_check()
                LOGGER.info("Next homework poll scheduled for %s", next_poll.isoformat())

    def stop(self, *_args) -> None:
        self.stop_event.set()
        self.wake_event.set()

    def close(self) -> None:
        if self.client:
            self.client.close()
        self.publisher.close()


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    monitor = GalimMonitor(settings)
    signal.signal(signal.SIGTERM, monitor.stop)
    signal.signal(signal.SIGINT, monitor.stop)
    try:
        monitor.run()
    finally:
        monitor.close()
