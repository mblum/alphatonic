import pytest

from alphatonic.progress import silent, track


def test_track_order_total_and_close(progress_log):
    progress, events = progress_log
    assert list(track([3, 1, 2], "work", progress)) == [3, 1, 2]
    assert events[0] == ("open", "work", 3)
    assert sum(e[1] for e in events if e[0] == "advance") == 3
    assert events[-1] == ("close", "work")


def test_track_close_on_early_exit_and_exception(progress_log):
    progress, events = progress_log
    iterator = track([1, 2], "early", progress)
    assert next(iterator) == 1
    iterator.close()
    assert events[-1] == ("close", "early")
    with pytest.raises(RuntimeError), progress("error", 1):
        raise RuntimeError("injected")
    assert events[-1] == ("close", "error")
    with silent("silent") as advance:
        advance(0, description="updated")
