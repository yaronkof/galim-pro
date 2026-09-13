from __future__ import annotations

import logging
import signal
import threading

from .auth import GalimAuthenticator
from .client import GalimApiError, GalimClient, GalimSessionExpired
from .config import Settings
from .mqtt import GalimMqttPublisher
from .state import SeenTasks

LOGGER = logging.getLogger(__name__)


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

    def _login(self, *, clear_saved_session: bool = False) -> None:
        if clear_saved_session:
            self.authenticator.clear_saved_session()
        if self.client:
            self.client.close()
        sid = self.authenticator.login()
        self.client = GalimClient(sid)
        LOGGER.info("Galim LMS session is ready")

    def poll_once(self) -> None:
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

    def run(self) -> None:
        self.publisher.publish_discovery()
        interval_seconds = self.settings.poll_interval_minutes * 60
        while not self.stop_event.is_set():
            try:
                self.poll_once()
            except GalimApiError as exc:
                LOGGER.error("Galim API error: %s", exc)
                self.publisher.publish_unavailable()
            except Exception:
                LOGGER.exception("Unexpected monitor failure")
                self.publisher.publish_unavailable()
            self.stop_event.wait(interval_seconds)

    def stop(self, *_args) -> None:
        self.stop_event.set()

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
