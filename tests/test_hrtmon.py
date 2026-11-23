"""amiga_hrtmon loads HRTmon and never enters it. Nothing here talks to an Amiga."""

import pytest

from amigent import hrtmon, server
from amigent.client import ExecResult
from amigent.errors import AmigaError


class _Ctl:
    def __init__(self, which=0, run_rc=0, fail=""):
        self.which = which
        self.run_rc = run_rc
        self.fail = fail
        self.commands = []

    def exec(self, command, timeout=30):
        self.commands.append(command)
        if self.fail and command.startswith(self.fail):
            raise AmigaError(f"{command} was not answered")
        if command.startswith("Which"):
            return ExecResult(self.which, "")
        return ExecResult(self.run_rc, "")


def _ask(monkeypatch, ctl):
    monkeypatch.setattr(server._session(), "ctl", ctl)
    monkeypatch.setattr(server, "_with_ctl", lambda fn: fn())
    return server.amiga_hrtmon()


def test_it_loads_hrtmon_and_says_not_to_enter_it(monkeypatch):
    ctl = _Ctl()
    assert _ask(monkeypatch, ctl) == hrtmon.LOADED
    assert ctl.commands == ["Which >NIL: HRTmon", "Run >NIL: HRTmon"]
    assert "Do not enter it" in hrtmon.LOADED and "halts the whole system" in hrtmon.LOADED


def test_a_missing_hrtmon_says_where_it_comes_from(monkeypatch):
    ctl = _Ctl(which=5)
    text = _ask(monkeypatch, ctl)
    assert text == hrtmon.MISSING and "dev/debug/HRTmon" in text
    assert ctl.commands == ["Which >NIL: HRTmon"]


def test_a_failed_run_is_not_reported_as_loaded(monkeypatch):
    failed = _Ctl(run_rc=20)
    with pytest.raises(AmigaError, match="did not load"):
        _ask(monkeypatch, failed)
    broken = _Ctl(fail="Run")
    with pytest.raises(AmigaError, match="was not answered"):
        _ask(monkeypatch, broken)


def test_the_description_warns_the_agent_off_entering_it():
    doc = server.amiga_hrtmon.__doc__
    assert "never enter it" in doc and "Amigent loses this Amiga" in doc
    assert "dev/debug/HRTmon" in doc
