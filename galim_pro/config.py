from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _integer(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _schedules() -> tuple[str, ...]:
    values = tuple(
        value.strip()
        for value in os.getenv("SCHEDULES", "13:00,15:00,19:00").split(",")
        if value.strip()
    )
    if not values:
        raise ValueError("SCHEDULES must contain at least one HH:MM time")
    for value in values:
        try:
            datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError(f"Invalid SCHEDULES time {value!r}; expected HH:MM") from exc
    return values


@dataclass(frozen=True)
class Settings:
    galim_username: str
    galim_password: str
    mqtt_host: str
    mqtt_port: int
    mqtt_username: str
    mqtt_password: str
    schedules: tuple[str, ...]
    timezone: str
    seed_quietly: bool
    headless: bool
    data_dir: Path
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        settings = cls(
            galim_username=os.getenv("GALIM_USERNAME", "").strip(),
            galim_password=os.getenv("GALIM_PASSWORD", ""),
            mqtt_host=os.getenv("MQTT_HOST", "").strip(),
            mqtt_port=_integer("MQTT_PORT", 1883),
            mqtt_username=os.getenv("MQTT_USERNAME", "").strip(),
            mqtt_password=os.getenv("MQTT_PASSWORD", ""),
            schedules=_schedules(),
            timezone=os.getenv("TZ", "Asia/Jerusalem").strip() or "Asia/Jerusalem",
            seed_quietly=_boolean("SEED_QUIETLY", True),
            headless=_boolean("HEADLESS", True),
            data_dir=Path(os.getenv("DATA_DIR", "./data")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
        missing = [
            name
            for name, value in (
                ("GALIM_USERNAME", settings.galim_username),
                ("GALIM_PASSWORD", settings.galim_password),
                ("MQTT_HOST", settings.mqtt_host),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        return settings
