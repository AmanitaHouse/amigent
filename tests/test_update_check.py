"""The check for a newer Amigent and the update of PC and Amigas, without a network."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from amigent import update


def pypi(*versions, yanked=(), empty=()):
    releases = {}
    for v in versions:
        files = [] if v in empty else [{"filename": f"amigent-{v}.tar.gz", "yanked": v in yanked}]
        releases[v] = files
    return json.dumps({"info": {"version": versions[-1]}, "releases": releases}).encode()


RELEASE = json.dumps({"body": "Intro line.\n\n## Faster\n\n- **ZZ9000:** reads the [card](https://x) fast.\n"
                              "- `amiga_cpu` measures.\n* star bullet\nplain text\n"}).encode()


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(update, "FOLDER", tmp_path)
    monkeypatch.setattr(update, "__version__", "1.4.0")
    monkeypatch.delenv("AMIGENT_NO_UPDATE_CHECK", raising=False)
    asked = []

    def answers(pypi_body, release=RELEASE):
        def get(url):
            asked.append(url)
            if isinstance(pypi_body, Exception):
                raise pypi_body
            return pypi_body if "pypi.org" in url else release
        monkeypatch.setattr(update, "_get", get)
    return SimpleNamespace(path=tmp_path, asked=asked, answers=answers)


def test_versions_compare_as_numbers_and_skip_pre_releases():
    assert update.newer("1.10.0", "1.9.3")
    assert not update.newer("1.4.0", "1.4.0")
    assert not update.newer("1.5.0rc1", "1.4.0")
    assert update.newer("1.4.1", "1.4")
    assert not update.newer("2.0.0", "1.5.0.dev1")  # a development build is never told


def test_the_newest_installable_release_counts():
    answer = json.loads(pypi("1.3.0", "1.4.0", "1.5.0rc1", "1.4.1", "1.6.0", yanked=("1.6.0",)))
    assert update.latest_from_pypi(answer) == "1.4.1"
    assert update.latest_from_pypi(json.loads(pypi("1.4.0", "1.5.0", empty=("1.5.0",)))) == "1.4.0"
    assert update.latest_from_pypi({}) == ""


def test_a_newer_version_is_offered_with_its_notes(home):
    home.answers(pypi("1.3.0", "1.4.0", "1.5.0"))
    found = update.offer(update.refresh())
    assert found["version"] == "1.5.0" and found["current"] == "1.4.0"
    assert found["notes"] == "- ZZ9000: reads the card fast.\n- amiga_cpu measures.\n- star bullet"
    assert found["page"].endswith("/tag/v1.5.0")


def test_pypi_is_asked_at_most_once_a_day(home):
    home.answers(pypi("1.5.0"))
    update.refresh()
    update.refresh()
    assert sum("pypi.org" in u for u in home.asked) == 1
    update.refresh(force=True)
    assert sum("pypi.org" in u for u in home.asked) == 2


def test_the_same_version_or_an_older_one_is_not_offered(home):
    home.answers(pypi("1.3.0", "1.4.0"))
    assert update.offer(update.refresh()) is None
    assert not any("api.github.com" in u for u in home.asked)  # no notes asked for nothing


def test_offline_stays_quiet_and_waits_a_day(home):
    home.answers(OSError("no route to host"))
    state = update.refresh()
    assert update.offer(state) is None and state["checked"] > 0
    update.refresh()
    assert len(home.asked) == 1


def test_a_skipped_version_is_not_offered_but_the_next_one_is(home):
    home.answers(pypi("1.5.0"))
    update.refresh()
    update.skip("1.5.0")
    assert update.offer() is None
    home.answers(pypi("1.5.0", "1.5.1"))
    assert update.offer(update.refresh(force=True))["version"] == "1.5.1"


def test_it_can_be_switched_off(home, monkeypatch):
    home.answers(pypi("1.5.0"))
    update.refresh()
    update.set_enabled(False)
    assert update.offer() is None and not update.enabled()
    update.refresh_in_background()  # does not even start
    update.set_enabled(True)
    assert update.offer()["version"] == "1.5.0"
    monkeypatch.setenv("AMIGENT_NO_UPDATE_CHECK", "1")
    assert update.offer() is None


def test_the_check_sends_nothing_but_the_question(home, monkeypatch):
    seen = []

    class Answer:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            return pypi("1.4.0")

    def urlopen(request, timeout):
        seen.append((request.full_url, dict(request.header_items()), request.data, timeout))
        return Answer()

    monkeypatch.setattr(update.urllib.request, "urlopen", urlopen)
    update.refresh(force=True)
    url, headers, data, timeout = seen[0]
    assert url == update.PYPI and data is None and timeout <= 5
    assert set(headers) == {"User-agent", "Accept"} and headers["User-agent"] == "amigent/1.4.0"


def test_this_checkout_is_a_source_install():
    assert update.how_installed() == "source"
    assert update.command("source") == []
    assert update.command("pipx") == ["pipx", "upgrade", "amigent"]


class Runs:
    """Stands in for subprocess.run: records the commands, answers as told."""

    def __init__(self, answers):
        self.answers, self.commands = answers, []

    def __call__(self, cmd, **kw):
        self.commands.append(cmd)
        for match, rc, out in self.answers:
            if match in " ".join(cmd):
                return subprocess.CompletedProcess(cmd, rc, out, "")
        return subprocess.CompletedProcess(cmd, 0, "", "")


def pipx_install(monkeypatch, now="1.5.0"):
    monkeypatch.setattr(update, "how_installed", lambda: "pipx")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/pipx" if name == "pipx" else None)
    monkeypatch.setattr(update, "installed_version", lambda python=None: now)


def test_apply_updates_the_pc_first_then_each_amiga(home, monkeypatch):
    pipx_install(monkeypatch)
    runs = Runs([("A500", 1, "amigentd at A500 not answering\n")])
    said = []
    assert update.apply(["A1200", "A500"], say=said.append, run=runs)
    assert runs.commands[0] == ["/usr/bin/pipx", "upgrade", "amigent"]
    assert [c[3] for c in runs.commands[1:]] == ["A1200", "A500"]
    assert all(c[1:3] == ["-m", "amigent.setup"] and c[-1] == "--update" for c in runs.commands[1:])
    assert "now has Amigent 1.5.0" in said[1]
    assert said[-1] == "A500: amigentd at A500 not answering (skipped)"


def test_apply_stops_when_the_pc_update_fails_or_changes_nothing(home, monkeypatch):
    pipx_install(monkeypatch)
    runs = Runs([("upgrade", 1, "pipx: no network")])
    said = []
    assert not update.apply(["A1200"], say=said.append, run=runs)
    assert len(runs.commands) == 1 and "failed (1)" in said[-1]
    pipx_install(monkeypatch, now="1.4.0")
    runs = Runs([])
    assert not update.apply(["A1200"], say=said.append, run=runs)
    assert len(runs.commands) == 1 and "nothing changed" in said[-1]


def test_apply_never_touches_a_source_checkout(home):
    runs = Runs([])
    said = []
    assert not update.apply(["A1200"], say=said.append, run=runs)
    assert runs.commands == [] and "git pull" in said[0]


def test_the_agent_is_told_once_and_asked_to_check_with_the_user(home, monkeypatch):
    from amigent import server
    home.answers(pypi("1.5.0"))
    update.refresh()
    monkeypatch.setattr(server, "_update_told", "")
    monkeypatch.setattr(update, "refresh_in_background", lambda then=None: None)
    first = server._update_note()
    assert "Amigent 1.5.0 is out" in first and "once they agree" in first
    assert server._update_note() == ""


def test_amiga_update_only_looks_unless_told_to_apply(home, monkeypatch):
    from amigent import server
    home.answers(pypi("1.5.0"))
    monkeypatch.setattr(server.machines, "load", lambda: [{"name": "A1200", "host": "10.0.0.2"}])
    applied = []
    monkeypatch.setattr(update, "apply", lambda *a, **k: applied.append(a) or True)
    said = server.amiga_update()
    assert "1.5.0 is out" in said and "amigent-setup --update for A1200" in said and "Ask the user" in said
    assert applied == []
    said = server.amiga_update(skip=True)
    assert "not be offered again" in said and update.offer() is None


def test_the_viewer_answers_later_skip_and_now(home, monkeypatch):
    from amigent import viewer as viewer_module
    home.answers(pypi("1.5.0"))
    update.refresh()
    v = viewer_module.Viewer.__new__(viewer_module.Viewer)
    v.host = "A1200"
    started, quit_after = [], []
    monkeypatch.setattr(update, "start_for_viewer", started.append)
    monkeypatch.setattr(update, "how_installed", lambda: "pipx")
    monkeypatch.setattr(viewer_module.threading, "Timer", lambda s, f: SimpleNamespace(start=lambda: quit_after.append(s)))
    assert v.update_action("later") == {}
    assert v.update_action("now") == {"restarting": True}
    assert started == ["A1200"] and quit_after == [1.5]
    assert v.update_action("skip") == {} and update.offer() is None
    with pytest.raises(ValueError):
        v.update_action("now")  # nothing left to update to


def test_the_last_update_from_the_page_is_told_once(home):
    update._change(last_run="This computer now has Amigent 1.5.0.", last_ok=True)
    assert update.last_run() == {"ok": True, "text": "This computer now has Amigent 1.5.0."}
    assert update.last_run() is None
