import json
import threading
import urllib.request

from amigent import fleet
from amigent.amigactl import AmigaError, ExecResult


class FakeCommands:
    """Stands in for a command channel; 'Dead' never answers."""

    log: list = []

    def __init__(self, host):
        self.host = host

    def exec(self, command, cd=None, timeout=None):
        if self.host == "Dead":
            raise AmigaError("cannot reach amigentd")
        FakeCommands.log.append((self.host, command))
        return ExecResult(0 if command != "Fail" else 10, f"{self.host}: {command}\n")

    def stat(self, path):
        return {"type": "file"}

    def flush(self, volumes):
        FakeCommands.log.append((self.host, "flush " + " ".join(volumes)))

    def close(self):
        pass


class OfflineScreen:
    """A screen that never opens a socket. Fleet tests must not dial a name."""

    def __init__(self, host, port=6801, timeout=30.0, key=None):
        self.host = host
        self.port = port
        self.listeners: list = []

    def capture(self, *args, **kwargs):
        raise OSError("offline")

    def close(self):
        pass


def make_fleet(monkeypatch, *names):
    FakeCommands.log = []
    monkeypatch.setattr(fleet, "Commands", FakeCommands)
    monkeypatch.setattr("amigent.viewer.Amigentd", OfflineScreen)
    return fleet.Fleet([{"name": n, "host": f"10.0.0.{i}"} for i, n in enumerate(names, 1)])


def _fleet_threads() -> list[threading.Thread]:
    return [thread for thread in threading.enumerate() if thread.name.startswith("amigent-fleet")]


def test_one_command_for_the_whole_fleet(monkeypatch):
    f = make_fleet(monkeypatch, "A500", "A1200", "Dead")
    result = {r["name"]: r for r in f.run("Version")}
    assert result["A500"] == {"id": 0, "name": "A500", "ok": True, "rc": 0, "output": "A500: Version\n"}
    assert result["A1200"]["ok"] and result["A1200"]["rc"] == 0
    assert not result["Dead"]["ok"] and "reach" in result["Dead"]["error"]
    assert [r["name"] for r in f.run("Fail", [1])] == ["A1200"]


def test_restart_writes_the_disks_first(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    assert f.restart(0)["ok"]
    assert FakeCommands.log == [("A1200", "flush SYS:"), ("A1200", "Run >NIL: C:Reboot")]


def test_run_needs_the_token_and_one_line(monkeypatch):
    f = make_fleet(monkeypatch, "A1200")
    try:
        base = f.start(0).split("?")[0].rstrip("/")

        def post(path, body, token=f.token):
            request = urllib.request.Request(f"{base}{path}?t={token}", data=json.dumps(body).encode(),
                                             method="POST")
            try:
                with urllib.request.urlopen(request, timeout=10) as reply:
                    return reply.status, json.loads(reply.read())
            except urllib.error.HTTPError as e:
                return e.code, None

        assert post("/api/run", {"command": "Version"}, token="wrong")[0] == 403
        assert post("/api/run", {"command": "Version\nFormat DF0:"})[0] == 400
        status, result = post("/api/run", {"command": "Version"})
        assert status == 200 and result[0]["output"] == "A1200: Version\n"
    finally:
        f.stop()
    assert _fleet_threads() == []


def test_watchers_stop_before_the_test_returns(monkeypatch):
    f = make_fleet(monkeypatch, "A500", "A1200")
    f.start(0)
    assert len(_fleet_threads()) == 3  # the page, and one watcher per Amiga
    f.stop()
    assert _fleet_threads() == []
    f.stop()  # a second stop is the end of the overview, not a new start
