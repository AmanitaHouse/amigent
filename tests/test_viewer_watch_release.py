"""Screen feed must not keep a stale online flag after the last page leaves."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

from amigent.screenfeed import WATCH_RELEASE, Feed, InputQueue


def test_feed_releases_stale_online_after_watch_release(monkeypatch):
    screen = MagicMock()
    screen._sock = object()  # pretend connected
    online = {"value": None, "reasons": []}

    def on_online(flag, reason=""):
        online["value"] = flag
        online["reasons"].append((flag, reason))

    watching = {"on": False}
    feed = Feed(
        screen,
        lock=threading.Lock,
        inputs=InputQueue(),
        watching=lambda: watching["on"],
        on_online=on_online,
        alive=lambda: False,
    )
    feed.online = True  # prior page had connected

    clock = {"t": 100.0}
    monkeypatch.setattr(time, "monotonic", lambda: clock["t"])

    waits = []

    def fake_wait(seconds=None):
        waits.append(seconds)
        clock["t"] += 1.0 if seconds is None else max(float(seconds), 0.5)
        if clock["t"] > 100.0 + WATCH_RELEASE + 3:
            feed.wake.set()
            raise SystemExit

    feed.wake.wait = fake_wait  # type: ignore[method-assign]
    feed.wake.clear = lambda: None  # type: ignore[method-assign]

    try:
        feed.run()
    except SystemExit:
        pass

    assert screen.close.called or online["value"] is False
    assert online["value"] is False
    assert any(not flag and "viewer page closed" in reason for flag, reason in online["reasons"])
    assert waits  # loop actually idled
