from __future__ import annotations

import hashlib
import json
from typing import Any


def _first(task: dict[str, Any], *names: str) -> Any:
    for name in names:
        value = task.get(name)
        if value not in (None, ""):
            return value
    return None


def normalize_task(task: dict[str, Any]) -> dict[str, Any]:
    """Select safe, useful fields without exposing the entire upstream payload."""
    result = {
        "id": _first(task, "id", "taskId", "task_id", "assignmentId"),
        "name": _first(task, "name", "title", "taskName", "assignmentName"),
        "subject": _first(task, "subject", "subjectName", "fieldName", "courseName"),
        "assigned_at": _first(task, "assignDate", "assignedAt", "assignmentDate", "date"),
        "due_at": _first(task, "targetDate", "dueDate", "due_at", "deadline"),
        "status": _first(task, "status", "taskStatus", "submissionStatus"),
        "url": _first(task, "url", "link", "taskUrl"),
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

