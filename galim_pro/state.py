from __future__ import annotations

import json
from pathlib import Path

from .tasks import task_identity


class SeenTasks:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.initialized = self.path.exists()
        self._seen = self._load()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return set()
        return {str(item) for item in data} if isinstance(data, list) else set()

    @property
    def is_empty(self) -> bool:
        return not self._seen

    def update(self, tasks: list[dict]) -> list[dict]:
        current = {task_identity(task) for task in tasks}
        new = [task for task in tasks if task_identity(task) not in self._seen]
        self._seen = current
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(current), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.path.chmod(0o600)
        self.initialized = True
        return new
