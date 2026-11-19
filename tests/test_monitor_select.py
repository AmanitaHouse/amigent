"""Which packaged monitor is copied, and under which installed name."""

from pathlib import Path

import pytest

from amigent.paths import AMIGA
from amigent.setup import install, monitor_file, select_build

ROOT = Path(__file__).resolve().parents[1]


def general_monitor():
    return (AMIGA / "bin" / "amigent-monitor").read_bytes()


def apollo_monitor():
    return (AMIGA / "bin" / "amigent-monitor.apollo").read_bytes()


class Link:
    def __init__(self, cpu_rc=0, probe_rc=5):
        self.files = {}
        self.commands = []
        self.cpu_rc = cpu_rc
        self.probe_rc = probe_rc

    def put(self, path, data):
        self.files[path] = data

    def run(self, command):
        self.commands.append(command)
        if command.startswith("CPU CHECK"):
            return self.cpu_rc
        if command == "T:amigent-apollo-probe":
            return self.probe_rc
        return 0


def test_only_the_apollo_daemon_selects_the_68080_monitor():
    assert monitor_file(select_build(0, {"os": "ApolloOS"})) == "amigent-monitor.apollo"
    assert monitor_file(select_build(0, {"exec_version": "51.3", "attn_flags": str(1 << 10)})) == "amigent-monitor.apollo"
    assert monitor_file(select_build(0, {}, "exec.library 51.3\nApolloOS\n")) == "amigent-monitor.apollo"
    assert monitor_file(select_build(0)) == "amigent-monitor"
    assert monitor_file(select_build(0, {"os": "AmigaOS", "cpu": "68080"})) == "amigent-monitor"
    assert monitor_file(select_build(0, {"exec_version": "47.96", "attn_flags": "1024"})) == "amigent-monitor"
    assert monitor_file(select_build(0, {"exec_version": "51.3", "attn_flags": "0"})) == "amigent-monitor"
    assert monitor_file(select_build(5, {"os": "ApolloOS"})) == "amigent-monitor"
    assert monitor_file("amigentd") == "amigent-monitor"
    assert monitor_file("amigentd.000") == "amigent-monitor"
    assert monitor_file("") == "amigent-monitor"
    assert monitor_file("unknown") == "amigent-monitor"
    assert monitor_file("amigent-monitor.apollo") == "amigent-monitor"


def test_install_on_apolloos_stores_the_apollo_monitor_under_the_usual_name():
    link = Link(probe_rc=0)
    install(link, "SYS:amigent", "key", None, False)
    assert link.files["C:amigentd.new"] == (AMIGA / "bin" / "amigentd.apollo").read_bytes()
    assert link.files["SYS:amigent/amigent-monitor"] == apollo_monitor()
    assert "SYS:amigent/amigent-monitor.apollo" not in link.files
    assert link.files["SYS:amigent/amigent-monitor.info"] == (AMIGA / "bin" / "amigent-monitor.info").read_bytes()


def test_install_on_amigaos_keeps_the_general_monitor():
    link = Link(probe_rc=5)
    install(link, "SYS:amigent", "key", None, False)
    assert link.files["C:amigentd.new"] == (AMIGA / "bin" / "amigentd").read_bytes()
    assert link.files["SYS:amigent/amigent-monitor"] == general_monitor()
    assert apollo_monitor() not in link.files.values()


def test_install_on_a_68000_keeps_the_general_monitor():
    link = Link(cpu_rc=5, probe_rc=0)
    install(link, "SYS:amigent", "key", None, False)
    assert link.files["C:amigentd.new"] == (AMIGA / "bin" / "amigentd.000").read_bytes()
    assert link.files["SYS:amigent/amigent-monitor"] == general_monitor()
    assert "T:amigent-apollo-probe" not in link.commands
    assert apollo_monitor() not in link.files.values()


def test_install_on_an_unknown_cpu_copies_nothing():
    link = Link(cpu_rc=20, probe_rc=0)
    with pytest.raises(SystemExit):
        install(link, "SYS:amigent", "key", None, False)
    assert link.files == {}
    assert apollo_monitor() not in link.files.values()


def test_a_failed_probe_does_not_select_the_68080_monitor():
    link = Link(probe_rc=20)
    install(link, "SYS:amigent", "key", None, False)
    assert link.files["C:amigentd.new"] == (AMIGA / "bin" / "amigentd").read_bytes()
    assert link.files["SYS:amigent/amigent-monitor"] == general_monitor()


def test_install_without_the_apollo_monitor_copies_no_daemon(monkeypatch, tmp_path):
    probe = (AMIGA / "bin" / "amigent-apollo-probe").read_bytes()
    daemon = (AMIGA / "bin" / "amigentd.apollo").read_bytes()
    monkeypatch.setattr("amigent.setup.AMIGA", tmp_path)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "amigent-apollo-probe").write_bytes(probe)
    (tmp_path / "bin" / "amigentd.apollo").write_bytes(daemon)
    link = Link(probe_rc=0)
    with pytest.raises(SystemExit, match="amigent-monitor.apollo"):
        install(link, "SYS:amigent", "key", None, False)
    assert "C:amigentd.new" not in link.files
    assert not any(path.endswith("amigent-monitor") for path in link.files)


def test_the_amiga_updater_follows_the_probe_and_keeps_the_daemon_choice():
    lines = (ROOT / "src" / "amigent" / "amiga" / "Amigent-Update").read_text(encoding="iso-8859-1").splitlines()
    assert "Set build amigentd.apollo" not in lines
    cpu = lines.index("CPU CHECK 68020 >NIL:")
    warned = lines.index("If WARN", cpu)
    classic = lines.index("  Set build amigentd.000", warned)
    otherwise = lines.index("Else", classic)
    probe = lines.index("    amigent-apollo-probe >NIL:", otherwise)
    opened = lines.index("    If NOT WARN", probe)
    chosen = lines.index("        Set monitor amigent-monitor.apollo", opened)
    copied = lines.index('    Copy $monitor "$home/amigent-monitor" QUIET', chosen)
    assert lines.index("Set build amigentd") < lines.index("Set monitor amigent-monitor") < cpu
    assert classic < otherwise < probe < opened < chosen < copied
    assert "Copy $build C:amigentd.new QUIET" in lines
    assert "Copy amigent-monitor \"$home/\"" not in "\n".join(lines)
