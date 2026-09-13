from galim_pro.state import SeenTasks


def test_seen_tasks_detects_only_new_items(tmp_path):
    state = SeenTasks(tmp_path / "seen.json")
    first = [{"id": 1, "name": "Math"}]
    assert state.update(first) == first
    assert state.update(first) == []

    second = first + [{"id": 2, "name": "Science"}]
    assert state.update(second) == [second[1]]


def test_seen_tasks_persists(tmp_path):
    path = tmp_path / "seen.json"
    SeenTasks(path).update([{"id": "abc"}])
    restored = SeenTasks(path)
    assert restored.is_empty is False
    assert restored.update([{"id": "abc"}]) == []


def test_empty_first_poll_is_still_initialized(tmp_path):
    path = tmp_path / "seen.json"
    state = SeenTasks(path)
    assert state.initialized is False
    state.update([])
    assert state.initialized is True

    restored = SeenTasks(path)
    assert restored.initialized is True
