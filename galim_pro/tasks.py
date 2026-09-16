from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def _first(task: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = task.get(name)
        if value not in (None, ""):
            return value
    return None


def _key_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _values(task: dict[str, Any]):
    """Yield scalar values from nested API objects with their final key name."""
    for key, value in task.items():
        if isinstance(value, dict):
            yield from _values(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield from _values(item)
        elif value not in (None, ""):
            yield _key_name(str(key)), value


def _first_nested(task: dict[str, Any], *names: str) -> Any:
    direct = _first(task, *names)
    if direct is not None and not isinstance(direct, (dict, list)):
        return direct
    wanted = {_key_name(name) for name in names}
    for key, value in _values(task):
        if key in wanted:
            return value
    return None


def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Select safe, useful fields without exposing the entire upstream payload."""
    result = {
        "id": _first_nested(task, "id", "taskId", "task_id", "assignmentId"),
        "name": _first_nested(
            task, "name", "title", "taskName", "assignmentName", "lessonName", "lesson"
        ),
        "subject": _first_nested(
            task, "subject", "subjectName", "fieldName", "courseName", "professionName"
        ),
        "assigned_at": _first_nested(
            task, "assignDate", "assignedAt", "assignmentDate", "date", "lessonDate"
        ),
        "due_at": _first_nested(task, "targetDate", "dueDate", "due_at", "deadline"),
        "status": _first_nested(task, "status", "taskStatus", "submissionStatus"),
        "url": _first_nested(task, "url", "link", "taskUrl"),
    }
    return {key: value for key, value in result.items() if value not in (None, "")}


def normalize_tasks(tasks: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    return [normalize_task(task) for task in tasks[:limit]]


def task_identity(task: dict[str, Any]) -> str:
    normalized = normalize_task(task)
    if normalized.get("id") is not None:
        return str(normalized["id"])
    encoded = json.dumps(normalized or task, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

