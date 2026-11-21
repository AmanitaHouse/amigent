"""Compatible daemon selection and update protection.

These tests use the packaged files and stand-ins. They do not contact an Amiga.
"""

from amigent import setup
from amigent.client import ExecResult
from amigent.daemons import (
    CPU_68000, CPU_68010, CPU_68020, CPU_68030, CPU_68040, CPU_68060, CPU_68080,
    EXPERIMENTAL, Machine, available_names, choose, consider_replacement, detect_cpu,
    embedded_version, identify,
)
from amigent.errors import AmigaError
from amigent.paths import AMIGA

BIN = AMIGA / "bin"


def _answers(table):
    def run(command):
        for prefix, code in table:
            if command.startswith(prefix):
                return code
        return 10
    return run


def test_one_cpu_check_is_all_a_choice_needs():
    asked = []

    def run(command):
        asked.append(command)
        return {"CPU CHECK 68020": answer}.get(command, 10)

    for answer, cpu in ((5, CPU_68000), (0, CPU_68020), (20, None)):
        asked.clear()
        assert detect_cpu(run) == cpu
        assert asked == ["CPU CHECK 68020"]
    # the builds part at the 68020 only: every CPU on either side gets the same file
    present = available_names(BIN)
    assert {choose(Machine(c), present).name for c in (CPU_68000, CPU_68010)} == {"amigentd.000"}
    assert {choose(Machine(c), present).name
            for c in (CPU_68020, CPU_68030, CPU_68040, CPU_68060, CPU_68080)} == {"amigentd"}


def test_the_build_date_breaks_a_tie_and_force_overrides(tmp_path, monkeypatch):
    from amigent.daemons import embedded_date

    binary = tmp_path / "bin"
    binary.mkdir()
    packaged = b"$VER: amigentd 1.5.0 (21.11.2026)\x00 rebuilt"
    (binary / "amigentd").write_bytes(packaged)
    earlier = b"$VER: amigentd 1.5.0 (19.11.2026)\x00 first build"
    later = b"$VER: amigentd 1.5.0 (2.12.2026)\x00 own build"
    assert embedded_date(packaged) == (2026, 11, 21) and embedded_date(b"no version") is None
    replace, reason = consider_replacement(earlier, packaged, "amigentd", binary)
    assert replace and reason == ""
    keep, reason = consider_replacement(later, packaged, "amigentd", binary)
    assert not keep and "later date" in reason and "--force" in reason

    package = tmp_path
    (package / "amigent-update.rexx").write_bytes(b"/* stand-in */")
    monkeypatch.setattr(setup, "AMIGA", package)
    monkeypatch.setattr(setup.time, "sleep", lambda _seconds: None)
    channel = Channel(later)
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    monkeypatch.setattr(setup, "update_folders", lambda *a: None)
    monkeypatch.setattr(setup, "UPDATE_WAIT", 0)
    assert setup.update("192.0.2.1", None) == 0
    assert "C:amigentd.new" not in channel.files
    setup.update("192.0.2.1", None, force=True)
    assert channel.files["C:amigentd.new"] == packaged


def test_a_dead_line_while_reading_c_amigentd_is_not_a_missing_file(monkeypatch, capsys):
    class Dead(Channel):
        def read_file(self, path):
            raise AmigaError("connection closed by amigentd")

    monkeypatch.setattr(setup, "update_windows", lambda *a: None)
    channel = Dead(b"$VER: amigentd 1.4.0 (1.1.2026)")
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    monkeypatch.setattr(setup, "update_folders", lambda *a: (_ for _ in ()).throw(AssertionError("no")))
    assert setup.update("192.0.2.1", None) == 1
    assert "connection closed by amigentd" in capsys.readouterr().out
    assert "C:amigentd.new" not in channel.files


def test_a_fresh_install_with_an_unknown_cpu_says_why_it_takes_the_68000_build(capsys):
    class Link:
        def run(self, command):
            return 20

    assert setup.amigentd_build(Link()) == "amigentd.000"
    out = capsys.readouterr().out
    assert "68000 build" in out and "C:CPU" in out


def test_each_cpu_gets_a_verified_compatible_daemon():
    present = available_names(BIN)
    assert choose(Machine(CPU_68000), present).name == "amigentd.000"
    assert choose(Machine(CPU_68010), present).name == "amigentd.000"
    for cpu in (CPU_68020, CPU_68030, CPU_68040, CPU_68060, CPU_68080):
        assert choose(Machine(cpu), present).name == "amigentd"
    assert choose(Machine(None), present).name == "amigentd.000"
    assert "amigentd.080" in present
    experimental = identify((BIN / "amigentd.080").read_bytes(), BIN)
    assert experimental is not None and experimental.status == EXPERIMENTAL
    assert choose(Machine(CPU_68080), present).name != "amigentd.080"


def test_a_missing_preferred_build_falls_back_and_an_empty_set_does_not():
    assert choose(Machine(CPU_68020), {"amigentd.000"}).name == "amigentd.000"
    assert choose(Machine(CPU_68000), {"amigentd"}) is None
    assert choose(Machine(None), set()) is None


def test_installer_falls_back_or_stops_when_files_are_missing(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    binary = package / "bin"
    binary.mkdir(parents=True)
    (binary / "amigentd.000").write_bytes(b"sixty-eight-thousand")
    monkeypatch.setattr(setup, "AMIGA", package)
    assert setup._chosen(Machine(CPU_68020)) == "amigentd.000"
    assert setup._chosen(Machine(None)) == "amigentd.000"
    (binary / "amigentd.000").unlink()
    try:
        setup._chosen(Machine(CPU_68020))
    except SystemExit as stopped:
        assert "no compatible" in str(stopped)
    else:
        raise AssertionError("a machine with no compatible daemon was given a build")


def test_updates_keep_unknown_or_newer_and_skip_identical_bytes(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    binary = package / "bin"
    binary.mkdir(parents=True)
    classic = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 classic"
    older = b"$VER: amigentd 1.3.0 (1.1.2020)\x00 classic"
    same = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 custom"
    newer = b"$VER: amigentd 1.5.0 (1.1.2027)\x00 classic"
    experimental = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 experimental-080"
    (binary / "amigentd").write_bytes(classic)
    (binary / "amigentd.080").write_bytes(experimental)
    monkeypatch.setattr(setup, "AMIGA", package)

    replace, reason = consider_replacement(older, classic, "amigentd", binary)
    assert replace and reason == ""
    keep, reason = consider_replacement(same, classic, "amigentd", binary)
    assert not keep and "same version" in reason
    keep, reason = consider_replacement(newer, classic, "amigentd", binary)
    assert not keep and "newer" in reason
    keep, reason = consider_replacement(classic, classic, "amigentd", binary)
    assert not keep and "same executable" in reason
    keep, reason = consider_replacement(None, classic, "amigentd", binary)
    assert not keep and "no C:amigentd" in reason
    replace, reason = consider_replacement(experimental, classic, "amigentd", binary)
    assert replace and reason == ""
    assert embedded_version(older) == (1, 3, 0)


class Channel:
    protocol = 4

    def __init__(self, installed, cpu_rc=0):
        self.files = {"C:amigentd": installed}
        self.cpu_rc = cpu_rc
        self.written = []

    def connect(self):
        pass

    def close(self):
        pass

    def read_file(self, path):
        if path not in self.files:
            raise AmigaError("object not found")
        return self.files[path]

    def write_file(self, path, data):
        self.written.append(path)
        self.files[path] = data

    def exec(self, command):
        if command.startswith("CPU"):
            return ExecResult(self.cpu_rc, "")
        if command.startswith("Version"):
            return ExecResult(0, "amigentd 1.4.0\n")
        return ExecResult(0, "")


def test_update_keeps_a_newer_unknown_daemon(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    binary = package / "bin"
    binary.mkdir(parents=True)
    (binary / "amigentd").write_bytes(b"$VER: amigentd 1.4.0 (1.1.2026)\x00 classic")
    (binary / "amigentd.000").write_bytes(b"sixty-eight-thousand")
    installed = b"$VER: amigentd 1.5.0 (1.1.2027)\x00 custom"
    monkeypatch.setattr(setup, "AMIGA", package)
    monkeypatch.setattr(setup.time, "sleep", lambda _seconds: None)
    channel = Channel(installed)
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    folders = []
    monkeypatch.setattr(setup, "update_folders", lambda ch, home, spare, daemon: folders.append(daemon))
    assert setup.update("192.0.2.1", None) == 0
    assert channel.files["C:amigentd"] == installed
    assert "C:amigentd.new" not in channel.files
    assert folders == [installed]  # the scripts are still renewed, next to the amigentd that runs
