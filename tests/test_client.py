from galim_pro.client import GalimClient


def test_task_payload_matches_browser_request():
    payload = GalimClient.task_payload()
    assert payload["page"] == 0
    assert payload["filterData"]["bySchool"] is True
    assert payload["filterData"]["completedActive"] is False
    assert payload["filterData"]["assignDateOrder"] == 1

