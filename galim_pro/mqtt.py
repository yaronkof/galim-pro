from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt

from .tasks import normalize_tasks

LOGGER = logging.getLogger(__name__)

DISCOVERY_TOPIC = "homeassistant/sensor/galim_pro_homework/config"
STATE_TOPIC = "galim_pro/homework/state"
ATTRIBUTES_TOPIC = "galim_pro/homework/attributes"
LAST_CHECK_DISCOVERY_TOPIC = "homeassistant/sensor/galim_pro_last_homework_check/config"
LAST_CHECK_STATE_TOPIC = "galim_pro/homework/last_check/state"
LAST_CHECK_ATTRIBUTES_TOPIC = "galim_pro/homework/last_check/attributes"
NEXT_CHECK_DISCOVERY_TOPIC = "homeassistant/sensor/galim_pro_next_homework_check/config"
NEXT_CHECK_STATE_TOPIC = "galim_pro/homework/next_check/state"
AVAILABILITY_TOPIC = "galim_pro/status"
EVENT_TOPIC = "galim_pro/homework/new"
CHECK_COMMAND_TOPIC = "galim_pro/homework/check"
BUTTON_DISCOVERY_TOPIC = "homeassistant/button/galim_pro_check_homework/config"


class GalimMqttPublisher:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        username: str = "",
        password: str = "",
    ) -> None:
        self._check_callback: Callable[[], None] | None = None
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="galim_pro_monitor",
        )
        if username:
            self.client.username_pw_set(username, password)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code == 0:
            client.subscribe(CHECK_COMMAND_TOPIC)
            client.publish(AVAILABILITY_TOPIC, "online", retain=True)
        else:
            LOGGER.error("MQTT connection failed with reason code %s", reason_code)

    def _on_message(self, _client, _userdata, message) -> None:
        if message.topic != CHECK_COMMAND_TOPIC or message.payload != b"CHECK":
            return
        LOGGER.info("Received a manual homework check request")
        if self._check_callback:
            self._check_callback()

    def set_check_callback(self, callback: Callable[[], None]) -> None:
        self._check_callback = callback

    def publish_discovery(self) -> None:
        device = {
            "identifiers": ["galim_pro_monitor"],
            "name": "Galim Pro",
            "manufacturer": "Galim (unofficial)",
            "model": "Homework Monitor",
        }
        sensor_payload = {
            "name": "Galim Pro Homework",
            "unique_id": "galim_pro_homework",
            "state_topic": STATE_TOPIC,
            "json_attributes_topic": ATTRIBUTES_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "icon": "mdi:book-open-page-variant",
            "unit_of_measurement": "tasks",
            "device": device,
        }
        button_payload = {
            "name": "Check Homework",
            "unique_id": "galim_pro_check_homework",
            "command_topic": CHECK_COMMAND_TOPIC,
            "payload_press": "CHECK",
            "availability_topic": AVAILABILITY_TOPIC,
            "icon": "mdi:refresh",
            "device": device,
        }
        last_check_payload = {
            "name": "Galim Pro Last Homework Check",
            "unique_id": "galim_pro_last_homework_check",
            "state_topic": LAST_CHECK_STATE_TOPIC,
            "json_attributes_topic": LAST_CHECK_ATTRIBUTES_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "device_class": "timestamp",
            "icon": "mdi:clock-check-outline",
            "device": device,
        }
        next_check_payload = {
            "name": "Galim Pro Next Homework Check",
            "unique_id": "galim_pro_next_homework_check",
            "state_topic": NEXT_CHECK_STATE_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "device_class": "timestamp",
            "icon": "mdi:clock-outline",
            "device": device,
        }
        self.client.publish(DISCOVERY_TOPIC, json.dumps(sensor_payload), retain=True)
        self.client.publish(
            BUTTON_DISCOVERY_TOPIC,
            json.dumps(button_payload),
            retain=True,
        )
        self.client.publish(
            LAST_CHECK_DISCOVERY_TOPIC,
            json.dumps(last_check_payload),
            retain=True,
        )
        self.client.publish(
            NEXT_CHECK_DISCOVERY_TOPIC,
            json.dumps(next_check_payload),
            retain=True,
        )
        self.client.publish(AVAILABILITY_TOPIC, "online", retain=True)

    def publish_tasks(self, tasks: list[dict]) -> None:
        now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        attributes = {
            "items": normalize_tasks(tasks),
            "total_items": len(tasks),
            "last_update": now,
        }
        self.client.publish(STATE_TOPIC, str(len(tasks)), retain=True)
        self.client.publish(
            ATTRIBUTES_TOPIC,
            json.dumps(attributes, ensure_ascii=False, default=str),
            retain=True,
        )
        self.client.publish(AVAILABILITY_TOPIC, "online", retain=True)

    def publish_new_tasks(self, tasks: list[dict]) -> None:
        if not tasks:
            return
        self.client.publish(
            EVENT_TOPIC,
            json.dumps({"items": normalize_tasks(tasks)}, ensure_ascii=False, default=str),
            retain=False,
        )

    def publish_last_check(
        self,
        completed_at: datetime,
        *,
        source: str,
        success: bool,
        tasks_published: int,
        new_tasks: int,
        error_summary: str | None = None,
    ) -> None:
        state = _timestamp_state(completed_at)
        attributes = {
            "source": source,
            "success": success,
            "tasks_published": tasks_published,
            "new_tasks": new_tasks,
        }
        if error_summary:
            attributes["error_summary"] = error_summary
        self.client.publish(LAST_CHECK_STATE_TOPIC, state, retain=True)
        self.client.publish(
            LAST_CHECK_ATTRIBUTES_TOPIC,
            json.dumps(attributes),
            retain=True,
        )

    def publish_next_check(self, scheduled_at: datetime) -> None:
        self.client.publish(
            NEXT_CHECK_STATE_TOPIC,
            _timestamp_state(scheduled_at),
            retain=True,
        )

    def publish_unavailable(self) -> None:
        self.client.publish(AVAILABILITY_TOPIC, "offline", retain=True)

    def close(self) -> None:
        try:
            self.client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
        finally:
            self.client.loop_stop()
            self.client.disconnect()


def _timestamp_state(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("MQTT timestamp states must be timezone-aware")
    return value.isoformat(timespec="seconds")
