import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from galim_pro.mqtt import (
    ATTRIBUTES_TOPIC,
    AVAILABILITY_TOPIC,
    BUTTON_DISCOVERY_TOPIC,
    DISCOVERY_TOPIC,
    LAST_CHECK_ATTRIBUTES_TOPIC,
    LAST_CHECK_DISCOVERY_TOPIC,
    LAST_CHECK_STATE_TOPIC,
    NEXT_CHECK_DISCOVERY_TOPIC,
    NEXT_CHECK_STATE_TOPIC,
    STATE_TOPIC,
    GalimMqttPublisher,
)


class RecordingClient:
    def __init__(self):
        self.messages = []

    def publish(self, topic, payload, *, retain):
        self.messages.append((topic, payload, retain))


def _publisher():
    publisher = object.__new__(GalimMqttPublisher)
    publisher.client = RecordingClient()
    return publisher


def test_discovery_publishes_existing_and_check_timestamp_entities():
    publisher = _publisher()

    publisher.publish_discovery()

    messages = {topic: (payload, retain) for topic, payload, retain in publisher.client.messages}
    assert set(messages) == {
        DISCOVERY_TOPIC,
        BUTTON_DISCOVERY_TOPIC,
        LAST_CHECK_DISCOVERY_TOPIC,
        NEXT_CHECK_DISCOVERY_TOPIC,
        AVAILABILITY_TOPIC,
    }

    homework = json.loads(messages[DISCOVERY_TOPIC][0])
    assert homework["unique_id"] == "galim_pro_homework"
    assert homework["state_topic"] == STATE_TOPIC
    assert homework["json_attributes_topic"] == ATTRIBUTES_TOPIC

    button = json.loads(messages[BUTTON_DISCOVERY_TOPIC][0])
    assert button["unique_id"] == "galim_pro_check_homework"

    last_check = json.loads(messages[LAST_CHECK_DISCOVERY_TOPIC][0])
    assert last_check["name"] == "Galim Pro Last Homework Check"
    assert last_check["unique_id"] == "galim_pro_last_homework_check"
    assert last_check["device_class"] == "timestamp"
    assert last_check["state_topic"] == LAST_CHECK_STATE_TOPIC
    assert last_check["json_attributes_topic"] == LAST_CHECK_ATTRIBUTES_TOPIC

    next_check = json.loads(messages[NEXT_CHECK_DISCOVERY_TOPIC][0])
    assert next_check["name"] == "Galim Pro Next Homework Check"
    assert next_check["unique_id"] == "galim_pro_next_homework_check"
    assert next_check["device_class"] == "timestamp"
    assert next_check["state_topic"] == NEXT_CHECK_STATE_TOPIC
    assert all(retain is True for _payload, retain in messages.values())


def test_last_check_publishes_timestamp_and_safe_operational_attributes():
    publisher = _publisher()
    completed_at = datetime(2026, 9, 14, 8, 54, 12, tzinfo=ZoneInfo("Asia/Jerusalem"))

    publisher.publish_last_check(
        completed_at,
        source="manual",
        success=True,
        tasks_published=7,
        new_tasks=2,
    )

    assert publisher.client.messages[0] == (
        LAST_CHECK_STATE_TOPIC,
        "2026-09-14T08:54:12+03:00",
        True,
    )
    attributes = json.loads(publisher.client.messages[1][1])
    assert attributes == {
        "source": "manual",
        "success": True,
        "tasks_published": 7,
        "new_tasks": 2,
    }


def test_last_check_includes_only_caller_supplied_safe_error_summary():
    publisher = _publisher()
    completed_at = datetime(2026, 9, 14, 8, 54, tzinfo=ZoneInfo("Asia/Jerusalem"))

    publisher.publish_last_check(
        completed_at,
        source="scheduled",
        success=False,
        tasks_published=0,
        new_tasks=0,
        error_summary="Galim API request failed",
    )

    attributes = json.loads(publisher.client.messages[1][1])
    assert attributes["error_summary"] == "Galim API request failed"


def test_next_check_publishes_timezone_aware_iso_timestamp():
    publisher = _publisher()
    scheduled_at = datetime(2026, 9, 15, 13, 0, tzinfo=ZoneInfo("Asia/Jerusalem"))

    publisher.publish_next_check(scheduled_at)

    assert publisher.client.messages == [
        (NEXT_CHECK_STATE_TOPIC, "2026-09-15T13:00:00+03:00", True)
    ]


def test_timestamp_sensor_rejects_naive_datetime():
    publisher = _publisher()

    with pytest.raises(ValueError, match="timezone-aware"):
        publisher.publish_next_check(datetime(2026, 9, 15, 13, 0))
