from __future__ import annotations

import requests

TASKS_URL = "https://lms.galim.org.il/personal_api/tasks"


class GalimApiError(RuntimeError):
    """Raised when Galim's task API cannot return a usable response."""


class GalimSessionExpired(GalimApiError):
    """Raised when the LMS session must be renewed."""


class GalimClient:
    def __init__(self, sid: str, *, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.cookies.set("SID", sid, domain="lms.galim.org.il")
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://lms.galim.org.il",
                "Referer": "https://lms.galim.org.il/personal?lang=he",
            }
        )

    @staticmethod
    def task_payload(page: int = 0) -> dict:
        return {
            "page": page,
            "filterData": {
                "bySchool": True,
                "completedActive": False,
                "selfActive": False,
                "orderBy": "assignDateOrder",
                "class": -1,
                "field": -1,
                "checkType": -1,
                "unit_type": -1,
                "grade_display": -1,
                "targetDateOrder": False,
                "newSubmittedOrder": False,
                "assignDateOrder": 1,
                "nameOrder": False,
            },
        }

    def fetch_tasks(self) -> list[dict]:
        try:
            response = self.session.post(
                TASKS_URL,
                json=self.task_payload(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise GalimApiError(f"Tasks request failed: {exc}") from exc

        if response.status_code in {401, 403}:
            raise GalimSessionExpired(f"Tasks request returned HTTP {response.status_code}")
        if response.status_code >= 400:
            raise GalimApiError(f"Tasks request returned HTTP {response.status_code}")

        content_type = response.headers.get("content-type", "").lower()
        if "json" not in content_type:
            raise GalimSessionExpired("Tasks endpoint returned a non-JSON login response")
        try:
            body = response.json()
        except ValueError as exc:
            raise GalimApiError("Tasks endpoint returned invalid JSON") from exc
        if not isinstance(body, dict) or not isinstance(body.get("tasks"), list):
            raise GalimApiError("Tasks endpoint response has no tasks list")
        return [task for task in body["tasks"] if isinstance(task, dict)]

    def close(self) -> None:
        self.session.close()

