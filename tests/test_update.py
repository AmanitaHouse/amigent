"""amigent-setup --update: swap a running amigentd by network, judge the Amiga's verdict."""

import pytest

from amigent import setup
from amigent.client import ExecResult
from amigent.errors import AmigaError
from amigent.paths import AMIGA


class Amiga:
    """Files and the update script's outcome; the script 'runs' when rx starts it."""

    def __init__(self, cpu_rc=0, outcome=b"new", installed=b"old amigentd"):
        self.files = {"C:amigentd": installed}
        self.cpu_rc = cpu_rc
        self.outcome = outcome
        self.commands = []


def channel_for(amiga):
    class Channel:
        protocol = 4

        def __init__(self, host, timeout=30):
            pass

        def connect(self):
            pass

        def close(self):
            pass

        def read_file(self, path):
            if path not in amiga.files:
                raise AmigaError("object not found")
            return amiga.files[path]

        def write_file(self, path, data):
            amiga.files[path] = data

        def exec(self, command):
            amiga.commands.append(command)
            if command.startswith("CPU CHECK"):
                return ExecResult(amiga.cpu_rc, "")
            if command.startswith("Run >NIL: rx T:amigent-update.rexx"):
                if amiga.outcome == b"new":
                    amiga.files["C:amigentd"] = amiga.files.pop("C:amigentd.new")
                amiga.files["T:amigent-update.done"] = amiga.outcome + b"\n"
            if command.startswith("Version"):
                return ExecResult(0, "amigentd 1.2.0\n")
            return ExecResult(0, "")

    return Channel


@pytest.fixture
def run(monkeypatch):
    monkeypatch.setattr(setup.time, "sleep", lambda s: None)

    def go(amiga, home=None):
        monkeypatch.setattr(setup, "AmigaChannel", channel_for(amiga))
        return setup.update("192.0.2.1", home)
    return go


def test_the_new_amigentd_replaces_the_old(run, capsys):
    amiga = Amiga()
    assert run(amiga, "Stuff:amigent") == 0
    assert amiga.files["C:amigentd"] == (AMIGA / "bin" / "amigentd").read_bytes()
    assert "Run >NIL: rx T:amigent-update.rexx Stuff:amigent" in amiga.commands
    assert 'Echo >ENVARC:amigent-home "Stuff:amigent"' in amiga.commands
    assert "Done: amigentd 1.2.0, protocol 4." in capsys.readouterr().out


def test_without_home_the_amiga_remembers_its_own(run):
    amiga = Amiga()
    assert run(amiga) == 0
    assert "Run >NIL: rx T:amigent-update.rexx" in amiga.commands
    assert not any("ENVARC" in c for c in amiga.commands)


def test_a_68000_gets_its_own_build(run):
    amiga = Amiga(cpu_rc=5)
    assert run(amiga) == 0
    assert amiga.files["C:amigentd"] == (AMIGA / "bin" / "amigentd.000").read_bytes()


def test_nothing_to_do_when_it_is_already_current(run, capsys):
    amiga = Amiga(installed=(AMIGA / "bin" / "amigentd").read_bytes())
    assert run(amiga) == 0
    assert "already" in capsys.readouterr().out
    assert not any("rx" in c for c in amiga.commands)


@pytest.mark.parametrize("outcome, code, words", [
    (b"old", 1, "runs the old one again"),
    (b"busy", 1, "did not stop"),
    (b"reboot", 0, "restart the Amiga"),
    (b"missing", 1, "did not arrive"),
])
def test_the_amiga_says_how_it_went(run, capsys, outcome, code, words):
    assert run(Amiga(outcome=outcome)) == code
    assert words in capsys.readouterr().out


def test_an_unknown_cpu_stops_before_anything_changes(run):
    amiga = Amiga(cpu_rc=20)
    assert run(amiga) == 1
    assert "C:amigentd.new" not in amiga.files


def test_a_home_that_cannot_be_written_does_not_stop_the_update(run, capsys):
    amiga = Amiga()
    original = channel_for(amiga)

    class Stubborn(original):
        def write_file(self, path, data):
            if path.startswith("Work:gone/"):
                raise AmigaError("object not found [205]")
            super().write_file(path, data)

    import amigent.setup as s
    s_channel = s.AmigaChannel
    try:
        s.AmigaChannel = Stubborn
        assert s.update("192.0.2.1", "Work:gone") == 0
    finally:
        s.AmigaChannel = s_channel
    assert amiga.files["C:amigentd"] == (AMIGA / "bin" / "amigentd").read_bytes()
    assert "not copied" in capsys.readouterr().out


def test_the_repair_scripts_are_renewed_for_their_folder(run, capsys):
    amiga = Amiga()
    amiga.files["Work:amigent/amigent-repair"] = b"; a repair script from the first installation\n"
    assert run(amiga, home="Work:amigent") == 0
    script = amiga.files["Work:amigent/amigent-repair"].decode("iso-8859-1")
    assert "Set SRC Work:amigent" in script and "SYS:amigent" not in script
    assert "Protect Work:amigent/amigent-repair +s" in amiga.commands
    assert "renewed in Work:amigent: amigent-repair" in capsys.readouterr().out


def test_the_scripts_wait_until_the_new_amigentd_runs(run):
    amiga = Amiga(outcome=b"old")
    amiga.files["SYS:amigent/amigent-repair"] = b"old script\n"
    assert run(amiga) == 1
    assert amiga.files["SYS:amigent/amigent-repair"] == b"old script\n"


def test_a_current_amigentd_still_gets_its_scripts_renewed(run):
    amiga = Amiga(installed=(AMIGA / "bin" / "amigentd").read_bytes())
    assert run(amiga) == 0
    assert b"Set SRC SYS:amigent" in amiga.files["SYS:amigent/amigent-repair"]


def test_a_spare_folder_repairs_from_itself_and_is_remembered(monkeypatch):
    monkeypatch.setattr(setup.time, "sleep", lambda s: None)
    amiga = Amiga()
    monkeypatch.setattr(setup, "AmigaChannel", channel_for(amiga))
    assert setup.update("192.0.2.1", "Work:amigent", "Backup:amigent") == 0
    assert b"Set SRC Backup:amigent" in amiga.files["Backup:amigent/amigent-repair"]
    assert amiga.files["Backup:amigent/amigentd"] == (AMIGA / "bin" / "amigentd").read_bytes()
    assert 'Echo >ENVARC:amigent-spare "Backup:amigent"' in amiga.commands
    assert "Copy >NIL: Work:amigent/amigent.key Backup:amigent/ CLONE QUIET" in amiga.commands
    assert "Copy >NIL: Work:amigent/repair.d/#? Backup:amigent/repair.d/ CLONE QUIET" in amiga.commands
    # the next update finds the spare by itself
    amiga.files["ENVARC:amigent-spare"] = b"Backup:amigent\n"
    amiga.files["ENVARC:amigent-home"] = b"Work:amigent\n"
    amiga.files["Backup:amigent/amigent-repair"] = b"stale\n"
    amiga.files["C:amigentd"] = b"old amigentd"
    assert setup.update("192.0.2.1", None) == 0
    assert b"Set SRC Backup:amigent" in amiga.files["Backup:amigent/amigent-repair"]
