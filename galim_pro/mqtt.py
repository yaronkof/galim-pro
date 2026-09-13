from __future__ import annotations

from datetime import datetime, timezone
import json
import logging

import paho.mqtt.client as mqtt

from .tasks import normalize_tasks

LOGGER = logging.getLogger(__name__)

DISCOVERY_TOPIC = "homeassistant/sensor/galim_pro_homework/config"
STATE_TOPIC = "galim_pro/homework/state"
ATTRIBUTES_TOPIC = "galim_pro/homework/attributes"
AVAILABILITY_TOPIC = "galim_pro/status"
EVENT_TOPIC = "galim_pro/homework/new"


class GalimMqttPublisher:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        username: str = "",
        password: str = "",
    ) -> None:
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="galim_pro_monitor",
        )
        if username:
            self.client.username_pw_set(username, password)
        self.client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
        self.client.connect(host, port, keepalive=60)
        self.client.loop_start()

    def publish_discovery(self) -> None:
        payload = {
            "name": "Galim Pro Homework",
            "unique_id": "galim_pro_homework",
            "state_topic": STATE_TOPIC,
            "json_attributes_topic": ATTRIBUTES_TOPIC,
            "availability_topic": AVAILABILITY_TOPIC,
            "icon": "mdi:book-open-page-variant",
            "unit_of_measurement": "tasks",
            "device": {
                "identifiers": ["galim_pro_monitor"],
                "name": "Galim Pro",
                "manufacturer": "Galim (unofficial)",
                "model": "Homework Monitor",
            },
        }
        self.client.publish(DISCOVERY_TOPIC, json.dumps(payload), retain=True)
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

    def publish_unavailable(self) -> None:
        self.client.publish(AVAILABILITY_TOPIC, "offline", retain=True)

    def close(self) -> None:
        try:
            self.client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
        finally:
            self.client.loop_stop()
            self.client.disconnect()

