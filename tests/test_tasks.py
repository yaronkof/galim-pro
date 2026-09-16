from galim_pro.tasks import normalize_task, task_identity


def test_normalize_task_keeps_allowlisted_fields_only():
    task = {
        "taskId": 42,
        "taskName": "Fractions",
        "subjectName": "Math",
        "targetDate": "2026-09-14",
        "SID": "must-not-leak",
        "studentPhone": "must-not-leak",
    }
    assert normalize_task(task) == {
        "id": 42,
        "name": "Fractions",
        "subject": "Math",
        "due_at": "2026-09-14",
    }


def test_task_identity_prefers_upstream_id():
    assert task_identity({"id": 123, "name": "Task"}) == "123"


def test_task_identity_without_id_is_stable():
    task = {"name": "Task", "dueDate": "2026-09-14"}
    assert task_identity(task) == task_identity(dict(reversed(list(task.items()))))


def test_normalize_task_reads_safe_lesson_fields_from_nested_payload():
    task = {
        "lesson": {"lessonName": "Algebra", "subjectName": "Math"},
        "metadata": {"lessonDate": "2026-09-16"},
        "cookie": "must-not-leak",
    }
    assert normalize_task(task) == {
        "name": "Algebra",
        "subject": "Math",
        "assigned_at": "2026-09-16",
    }

