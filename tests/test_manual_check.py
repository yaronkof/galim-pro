from galim_pro.monitor import GalimMonitor


def test_manual_check_wakes_monitor():
    monitor = object.__new__(GalimMonitor)
    import threading

    monitor.wake_event = threading.Event()
    monitor.request_check()
    assert monitor.wake_event.is_set()
