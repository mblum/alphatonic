from alphatonic.progress import silent, track


def test_silent_progress_accepts_any_use():
    with silent("task", 3) as advance:
        advance()
        advance(2, description="later")
        advance(0, description="only a new description")


def test_track_yields_every_item_and_advances_once_each():
    events = []

    class Task:
        def __init__(self, description, total):
            events.append(("start", description, total))

        def __enter__(self):
            return lambda steps=1, *, description=None: events.append(("advance", steps))

        def __exit__(self, *exc):
            events.append(("stop",))

    assert list(track([10, 20, 30], "counting", Task)) == [10, 20, 30]
    assert events == [("start", "counting", 3)] + [("advance", 1)] * 3 + [("stop",)]


def test_track_defaults_to_silence():
    assert list(track(range(4), "quiet")) == [0, 1, 2, 3]
