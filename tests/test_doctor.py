"""amigent-doctor's command line, without dialing an Amiga."""

import sys

from amigent import doctor


def test_help_exits_successfully(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["amigent-doctor", "--help"])
    assert doctor.main() == 0
    assert "Check the link" in capsys.readouterr().out


def test_short_help_exits_successfully(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["amigent-doctor", "-h"])
    assert doctor.main() == 0
    assert capsys.readouterr().out


def test_an_extra_argument_is_usage(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["amigent-doctor", "one", "two"])
    assert doctor.main() == 2


def test_no_amiga_is_usage_and_does_not_dial(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["amigent-doctor"])
    assert doctor.main() == 2
