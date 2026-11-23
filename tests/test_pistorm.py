"""The classic PiStorm emulator on its Pi, with a fake ssh: no real SSH here."""
import shlex

import pytest

from amigent import pistorm, roster, server
from amigent.errors import AmigaError

CFG = "/home/pi/pistorm/default.cfg"


class FakePi:
    """Answers the scripts pistorm.Pi sends, by what they contain."""

    def __init__(self, *, unit="", running=True, out="/home/pi/pistorm/emu.log", cfg_arg=None,
                 throttled="throttled=0x0", parent="", unitfiles=None):
        self.files = {CFG: "cpu_type 68020\n", "/home/pi/pistorm/a314.cfg": "cpu_type 68000\n"}
        self.unit, self.running, self.out, self.cfg_arg = unit, running, out, cfg_arg
        self.throttled, self.parent = throttled, parent
        self.unitfiles = unitfiles if unitfiles is not None else ([unit] if unit else [])
        self.calls = []
        self.fail_login = False

    def __call__(self, target, command, stdin=None, timeout=30):
        assert command.startswith("sh -c ")
        script = shlex.split(command)[2]
        self.calls.append((target, script, stdin))
        if self.fail_login:
            return 255, "", "Permission denied (publickey)."
        if "pgrep -x emulator | head -n 1)\necho \"pid=" in script:
            return 0, self._probe(), ""
        if "tee --" in script:
            path = shlex.split(script.split("tee --")[1].split(">")[0])[0]
            backup = shlex.split(script.split("cp -p --")[1].split("&&")[0])[1]
            self.files[backup] = self.files[path]
            self.files[path] = stdin.decode()
            return 0, "", ""
        if "cp -p --" in script:
            source, target_ = shlex.split(script.split("cp -p --")[1])[:2]
            self.files[target_] = self.files[source]
            return 0, "", ""
        if script.startswith("cat --"):
            path = shlex.split(script)[2]
            if path not in self.files:
                return 1, "", f"cat: {path}: No such file"
            return 0, self.files[path], ""
        if "systemctl restart" in script:
            return 0, "", ""
        if "systemctl is-active" in script:
            return 0, "active\n", ""
        if "journalctl" in script:
            return 0, "Nov 21 emulator[42]: [CPU] started\n", ""
        if script.startswith("tail -n"):
            return 0, "log line\n", ""
        if "setsid nohup" in script:
            return 0, "started=77\n", ""
        raise AssertionError(script)

    def _probe(self):
        lines = []
        if self.running:
            argv = ["./emulator"] + (["--config-file", self.cfg_arg] if self.cfg_arg else [])
            lines += ["pid=42", "cwd=/home/pi/pistorm", "cmd=" + "\x1f".join(argv) + "\x1f",
                      "user=root", f"out={self.out}", f"unit={self.unit}"]
            if self.parent:
                lines.append("parent=" + self.parent)
        else:
            lines.append("pid=")
        for u in self.unitfiles:
            lines += [f"unitfile={u}",
                      f"show:{u}:ExecStart={{ path=/home/pi/pistorm/emulator ; argv[]=/home/pi/pistorm/emulator "
                      "--config a314.cfg ; ignore_errors=no ; start_time=[n/a] }",
                      f"show:{u}:WorkingDirectory=/home/pi/pistorm", f"show:{u}:ActiveState=active",
                      f"show:{u}:UnitFileState=enabled"]
        lines += ["temp=temp=51.0'C", self.throttled, "zone=51000"]
        return "\n".join(lines) + "\n"


@pytest.fixture
def amiga():
    entry = roster.remember("A2000", "192.0.2.40")
    pistorm.set_pi(entry["id"], "pi@192.0.2.41")
    return entry


@pytest.fixture
def fake(monkeypatch):
    fake = FakePi()
    monkeypatch.setattr(pistorm, "ssh_runner", fake)
    return fake


def test_pi_address_is_kept_with_the_entry_and_validated(amiga):
    assert roster.find(amiga["id"])["pi"] == "pi@192.0.2.41"
    assert pistorm.pi_of("A2000") == "pi@192.0.2.41"
    for bad in ("-oProxyCommand=x", "pi@-x", "a b", "user name@host"):
        with pytest.raises(roster.RegistryError):
            pistorm.set_pi("A2000", bad)
    pistorm.set_pi("A2000", "")
    assert "pi" not in roster.find(amiga["id"])
    with pytest.raises(pistorm.PiError, match="No Pi is set"):
        pistorm.pi_of("A2000")


def test_ssh_runner_uses_batch_mode_and_no_password(monkeypatch):
    seen = {}

    class Done:
        returncode, stdout, stderr = 0, b"ok", b""

    def run(argv, **kw):
        seen["argv"] = argv
        return Done()
    monkeypatch.setattr(pistorm.subprocess, "run", run)
    assert pistorm.ssh_runner("pi@192.0.2.41", "true") == (0, "ok", "")
    argv = seen["argv"]
    assert argv[0] == "ssh" and "BatchMode=yes" in argv
    assert argv[argv.index("--") + 1] == "pi@192.0.2.41"
    assert not any("password" in a.lower() for a in argv)


def test_status_reports_process_config_temperature_and_power(amiga, fake):
    fake.throttled = "throttled=0x50005"
    text = pistorm.Pi("A2000").status()
    assert "running, pid 42" in text and CFG in text
    assert "51.0 °C" in text
    assert "under-voltage now" in text and "under-voltage has occurred since boot" in text
    assert fake.calls[0][0] == "pi@192.0.2.41"


def test_decode_throttled():
    assert pistorm.decode_throttled("throttled=0x0") == (0, [])
    value, flags = pistorm.decode_throttled("throttled=0x80008")
    assert value == 0x80008 and flags == ["soft temperature limit now", "soft temperature limit has occurred"]
    assert pistorm.decode_throttled("") == (None, [])


def test_config_comes_from_command_line_unit_or_default(amiga, fake):
    assert pistorm.Pi("A2000").read_config() == (CFG, "cpu_type 68020\n")
    fake.cfg_arg = "a314.cfg"
    assert pistorm.Pi("A2000").read_config()[0] == "/home/pi/pistorm/a314.cfg"
    fake.cfg_arg, fake.running, fake.unitfiles = None, False, ["pistorm.service"]
    assert pistorm.Pi("A2000").read_config()[0] == "/home/pi/pistorm/a314.cfg"
    fake.unitfiles = []
    with pytest.raises(pistorm.PiError, match="could not be found out"):
        pistorm.Pi("A2000").read_config()
    with pytest.raises(pistorm.PiError, match=".cfg"):
        pistorm.Pi("A2000").read_config("/etc/passwd")


def test_set_config_previews_then_writes_with_a_copy_and_undo_restores(amiga, fake):
    board = pistorm.Pi("A2000")
    preview = board.write_config("cpu_type 68030\n")
    assert "-cpu_type 68020" in preview and "+cpu_type 68030" in preview and "Nothing changed" in preview
    assert fake.files[CFG] == "cpu_type 68020\n"
    done = board.write_config("cpu_type 68030", confirm=True)
    assert fake.files[CFG] == "cpu_type 68030\n"
    backups = [p for p in fake.files if p.startswith(CFG + ".amigent-")]
    assert len(backups) == 1 and fake.files[backups[0]] == "cpu_type 68020\n" and backups[0] in done
    assert "would copy" in board.undo()
    assert fake.files[CFG] == "cpu_type 68030\n"
    board.undo(confirm=True)
    assert fake.files[CFG] == "cpu_type 68020\n"
    with pytest.raises(pistorm.PiError, match="no change"):
        board.undo(confirm=True)


def test_undo_refuses_when_the_file_changed_since(amiga, fake):
    board = pistorm.Pi("A2000")
    board.write_config("cpu_type 68030\n", confirm=True)
    fake.files[CFG] = "edited by hand\n"
    with pytest.raises(pistorm.PiError, match="changed again"):
        board.undo(confirm=True)
    assert fake.files[CFG] == "edited by hand\n"


def test_restart_uses_the_unit_when_there_is_one(amiga, fake):
    fake.unit = "pistorm.service"
    fake.unitfiles = ["pistorm.service"]
    assert "systemctl restart pistorm.service" in pistorm.Pi("A2000").restart()
    assert not any("systemctl restart" in c[1] for c in fake.calls)
    assert "active" in pistorm.Pi("A2000").restart(confirm=True)
    assert any("sudo -n systemctl restart pistorm.service" in c[1] for c in fake.calls)


def test_restart_without_unit_relaunches_the_same_command(amiga, fake):
    result = pistorm.Pi("A2000").restart(confirm=True)
    assert "pid 77" in result
    script = next(c[1] for c in fake.calls if "setsid nohup" in c[1])
    assert "kill 42" in script and "cd /home/pi/pistorm" in script and "./emulator" in script


def test_restart_refuses_when_nothing_tells_how_it_is_started(amiga, fake):
    fake.running = False
    with pytest.raises(pistorm.PiError, match="not known"):
        pistorm.Pi("A2000").restart(confirm=True)


def test_log_from_journal_file_or_explained(amiga, fake):
    fake.unit = "pistorm.service"
    assert "[CPU] started" in pistorm.Pi("A2000").log(20)
    fake.unit, fake.unitfiles = "", []
    assert pistorm.Pi("A2000").log() == "log line\n"
    fake.out = "/dev/pts/0"
    with pytest.raises(pistorm.PiError, match="not into a file"):
        pistorm.Pi("A2000").log()


def test_failed_login_says_to_use_your_own_key(amiga, fake):
    fake.fail_login = True
    with pytest.raises(pistorm.PiError, match="own key"):
        pistorm.Pi("A2000").status()


def test_mcp_tool_is_read_only_without_confirm(amiga, fake):
    assert "running" in server.amiga_pistorm(machine="A2000")
    server.amiga_pistorm("set_config", text="cpu_type 68040\n", machine="A2000")
    assert fake.files[CFG] == "cpu_type 68020\n"
    server.amiga_pistorm("set_config", text="cpu_type 68040\n", confirm=True, machine="A2000")
    assert fake.files[CFG] == "cpu_type 68040\n"
    server.amiga_pistorm("undo", confirm=True, machine="A2000")
    assert fake.files[CFG] == "cpu_type 68020\n"
    assert "confirm=True" in server.amiga_pistorm("set_pi", pi="192.0.2.50", machine="A2000")
    assert roster.find("A2000")["pi"] == "pi@192.0.2.41"
    server.amiga_pistorm("set_pi", pi="192.0.2.50", confirm=True, machine="A2000")
    assert roster.find("A2000")["pi"] == "192.0.2.50"
    with pytest.raises(AmigaError, match="action must be"):
        server.amiga_pistorm("format", machine="A2000")


def test_fleet_command_line_sets_and_lists_the_pi(amiga, monkeypatch, capsys):
    from amigent import fleet
    monkeypatch.setattr("sys.argv", ["amigent-fleet", "--pi", "A2000", "pi@192.0.2.60"])
    fleet.main()
    assert roster.find("A2000")["pi"] == "pi@192.0.2.60"
    monkeypatch.setattr("sys.argv", ["amigent-fleet", "--list"])
    fleet.main()
    assert "pi pi@192.0.2.60" in capsys.readouterr().out
