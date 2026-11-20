"""Protocol 6 stays upstream's, and the Apollo additions sit at 48 and 49."""

import os
import re
import sys
from pathlib import Path

import pytest

from amigent import channel, chipset, doctor, gdb, hrtmon, journal, memory, pack, project, screendiff, server, setup, states, viewer
from amigent.system import exec_coldreboot

ROOT = Path(__file__).resolve().parents[1]
DAEMON = (ROOT / "src" / "native" / "amiga" / "daemon" / "amigentd.c").read_text(encoding="utf-8")
MMIO = (ROOT / "src" / "native" / "amiga" / "platform" / "apollo" / "apollo_mmio.c").read_text(encoding="utf-8")
PROTOCOL = (ROOT / "docs" / "PROTOCOL.md").read_text(encoding="utf-8")

UPSTREAM = {
    37: "NOTE", 38: "LOADED", 39: "PEEK", 40: "TASKS", 41: "TASKCTL",
    42: "POKE", 43: "TRACE", 44: "LOCKS", 45: "CPU", 46: "DRAG", 47: "QUIET",
}
APOLLO = {48: "AUDIO", 49: "PIP"}


def daemon_commands() -> dict[int, str]:
    block = DAEMON.split("enum {", 1)[1].split("};", 1)[0]
    block = re.sub(r"/\*.*?\*/", "", block, flags=re.S)
    found: dict[int, str] = {}
    number = None
    for raw in block.split(","):
        name = raw.strip().split()[0] if raw.strip() else ""
        if not name.startswith("CMD_"):
            continue
        if "=" in raw:
            number = int(raw.split("=", 1)[1].strip().rstrip(","), 0)
        elif number is None:
            continue
        else:
            number += 1
        found[number] = name.removeprefix("CMD_")
    return found


def function_body(source: str, name: str) -> str:
    marker = f"{name}("
    start = source.index(marker)
    nxt = source.index("\nstatic ", start + len(marker))
    return source[start:nxt]


def mmio_windows() -> list[tuple[int, int]]:
    body = MMIO.split("win[][2] = {", 1)[1].split("};", 1)[0]
    return [(int(a, 16), int(b, 16)) for a, b in re.findall(
        r"0x([0-9A-Fa-f]+)UL\s*,\s*0x([0-9A-Fa-f]+)UL", body)]


def mmio_hit(at: int, n: int, windows) -> bool:
    """The same overlap rule as apollo_mmio_hit: any shared byte, including a wrap."""
    at &= 0xFFFFFFFF
    n &= 0xFFFFFFFF
    if n == 0 or (at + n) & 0xFFFFFFFF < at:
        return True
    end = (at + n) & 0xFFFFFFFF
    return any(at < stop and end > start for start, stop in windows)


def test_opcode_map_has_no_audio_or_pip_collision():
    commands = daemon_commands()
    assert {n: commands[n] for n in UPSTREAM} == UPSTREAM
    assert {n: commands[n] for n in APOLLO} == APOLLO
    assert commands[38] != "AUDIO" and commands[39] != "PIP"
    assert channel.AUDIO == 48 and channel.PIP == 49
    assert channel.LOADED == 38 and channel.PEEK == 39
    text = PROTOCOL
    assert "| 48 | AUDIO |" in text and "| 49 | PIP |" in text
    sysinfo = DAEMON.split("c_sysinfo", 1)[1].split("static void t_bytes", 1)[0]
    assert "modules" not in sysinfo and "tasklist" not in sysinfo
    assert 't_pair(&t, "loaded", 1)' in DAEMON
    assert 't_pair(&t, "audio", 1)' in DAEMON and 't_pair(&t, "pip", 0)' in DAEMON
    assert 't_pair(&t, "pip", 1)' not in DAEMON


def test_audio_and_pip_requests_consume_only_their_header():
    # The command header is 10 bytes: cmd, arg, x, y, w, h. AUDIO and PIP carry nothing after it.
    assert channel.audio_request(1, 200) == channel.struct.pack(">BBHHHH", 48, 1, 0, 200, 0, 0)
    assert channel.audio_request(2, 0) == channel.struct.pack(">BBHHHH", 48, 2, 0, 0, 0, 0)
    assert channel.pip_request() == channel.struct.pack(">BBHHHH", 49, 0, 0, 0, 0, 0)
    assert len(channel.audio_request()) == 10 and len(channel.pip_request()) == 10
    # A streamed reply is 8 bytes then samples. A PIP reply is 12 bytes then RGB.
    # Neither reply is a LOADED or PEEK body.
    assert channel.PEEK == 39 and channel.LOADED == 38
    assert channel.AUDIO != channel.LOADED and channel.PIP != channel.PEEK


def test_capabilities_follow_upstream_names():
    assert channel.apollo_commands({"audio": "1", "pip": "1"}) == {"AUDIO", "PIP"}
    assert channel.apollo_commands({"audio": "1", "pip": "0"}) == {"AUDIO"}
    assert channel.apollo_commands({"modules": "1", "tasklist": "1", "loaded": "1"}) == set()
    assert channel.apollo_commands({}) == set()
    assert "def amiga_jobs" in Path(server.__file__).read_text(encoding="utf-8")
    for name in ("amiga_listen", "amiga_hrtmon", "amiga_memory", "amiga_memory_write",
                 "amiga_emulator", "amiga_gurus", "amiga_state", "amiga_screen_diff",
                 "amiga_jobs", "amiga_loaded", "amiga_trace", "amiga_create_project"):
        assert hasattr(server, name)
    assert journal and memory and gdb and chipset and states and screendiff and project


def test_apollo_mmio_reads_are_refused_when_they_touch_a_window():
    windows = mmio_windows()
    assert windows  # derived from the platform table, not an empty exclusion
    assert mmio_hit(0xDFF1E6, 2, windows)
    assert mmio_hit(0xDFF1E4, 4, windows)  # crosses the start of BPLHMOD
    assert not mmio_hit(0xDFF1E0, 4, windows)
    assert mmio_hit(0xDFF3FC, 2, windows)
    assert mmio_hit(0xFFFFFFFE, 4, windows)  # wraps
    assert mmio_hit(0x2000, 0, windows)
    assert "apollo_mmio_hit(at, n)" in DAEMON
    peek = function_body(DAEMON, "c_peek")
    poke = function_body(DAEMON, "c_poke")
    assert "apollo_mmio_hit" in peek and "apollo_mmio_hit" in poke
    assert poke.index("!allow_poke") < poke.index("apollo_mmio_hit")
    assert "ALLOWPOKE" in poke
    assert "APoke is not this command" in poke


def test_tls_only_stays_closed_when_the_listener_did_not_start():
    assert "locked = tls_only && !setup_mode" in DAEMON
    assert "tls_only && tls_open" not in DAEMON
    assert "PLAIN_CLOSED" in Path(channel.__file__).read_text(encoding="utf-8")


def test_fast_cpu_waits_for_a_raw_sample(tmp_path):
    policy = pack.Policy("test", "10.0.0.9", mode="auto", path=tmp_path / "link.json")
    policy.rates = {"deflate_fast": pack.FAST_CPU, "deflate_best": 400, "inflate": 500}
    assert policy.line_kbs is None
    assert policy.level() == 0 and policy.upload() is False
    policy.note(1024 * 1024, 1.0)
    assert policy.line_kbs == 1024.0


def test_failed_link_note_deletes_the_part_file(tmp_path, monkeypatch):
    path = tmp_path / "link.json"
    policy = pack.Policy("test", "10.0.0.9", path=path)
    real = Path.write_text

    def fail(self, *args, **kwargs):
        if self.name.endswith(".part"):
            real(self, *args, **kwargs)
            raise OSError("disk")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail)
    policy.note(1000, 1.0)
    assert not path.with_name(f"{path.name}.{os.getpid()}.part").exists()


def test_doctor_help_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["amigent-doctor", "--help"])
    assert doctor.main() == 0
    assert "check_14" in Path(doctor.__file__).read_text(encoding="utf-8")
    out = capsys.readouterr().out
    assert "Usage:" in out


def test_missing_chip_is_not_zero():
    assert viewer.reported_bytes({}, "chip_free") is None
    assert viewer.reported_bytes({"chip_free": ""}, "chip_free") is None
    assert viewer.reported_bytes({"chip_free": "0"}, "chip_free") == 0
    assert viewer.status_free_bytes(None, 4096) == 4096
    assert viewer.connection_reason("timed out while not answering: secret path") == viewer.DID_NOT_ANSWER
    assert viewer.connection_reason("tile at 1,2: bad packed data") == ""


def test_reset_chord_is_refused_below_exec_36():
    assert exec_coldreboot("35.0") is False
    assert exec_coldreboot("36.1") is True
    text = Path(viewer.__file__).read_text(encoding="utf-8")
    assert "exec_coldreboot" in text
    assert "CHORD_MS" in DAEMON and "5000" in DAEMON


def test_install_selection(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    binary = package / "bin"
    binary.mkdir(parents=True)
    (binary / "amigentd").write_bytes(b"classic")
    (binary / "amigentd.000").write_bytes(b"sixty-eight-thousand")
    monkeypatch.setattr(setup, "AMIGA", package)

    class Link:
        def __init__(self, code):
            self.code = code
            self.puts = []

        def run(self, cmd):
            if cmd.startswith("CPU"):
                return self.code
            if cmd.startswith("T:amigent-apollo-probe") and "Protect" not in cmd:
                return 0
            return 10

        def put(self, name, data):
            self.puts.append(name)

    assert setup.select_build(5, {"os": "ApolloOS"}) == "amigentd.000"
    # ApolloOS alone does not prove the 68080 core; the FPGA attention bit does.
    assert setup.select_build(0, {"os": "ApolloOS"}) == "amigentd"
    assert setup.select_build(0, {}) == "amigentd"
    assert setup.select_build(20, {}) == "amigentd.000"  # an unknown CPU takes only the 68000 build
    (binary / "amigentd.000").rename(binary / "amigentd.000.hold")
    with pytest.raises(SystemExit):
        setup.select_build(20, {})
    (binary / "amigentd.000.hold").rename(binary / "amigentd.000")
    assert setup.amigentd_build(Link(5)) == "amigentd.000"
    assert setup.amigentd_build(Link(0)) == "amigentd"
    (binary / "amigent-apollo-probe").write_bytes(b"probe")
    assert setup.amigentd_build(Link(0)) == "amigentd"  # no Apollo daemon packaged: stay classic
    (binary / "amigentd.apollo").write_bytes(b"apollo")
    chosen = setup.amigentd_build(Link(0))
    assert chosen == "amigentd.apollo"
    assert setup.select_build(0, {"os": "ApolloOS", "attn_flags": "0x400"}) == "amigentd.apollo"
    assert setup.monitor_file(chosen) == "amigent-monitor"
    with pytest.raises(SystemExit):
        setup.binary_path("amigent-monitor.apollo")
    (binary / "amigent-monitor.apollo").write_bytes(b"monitor")
    assert setup.monitor_file(chosen) == "amigent-monitor.apollo"
    assert setup.binary_path("amigent-monitor.apollo").read_bytes() == b"monitor"


def test_hrtmon_never_selects_the_rom_monitor():
    text, start = hrtmon.plan("AmigaOS", "", "", True)
    assert start is False and "ROM" in text
    text, start = hrtmon.plan("ApolloOS", "", "HRTmon", True)
    assert start is False
    text, start = hrtmon.plan("ApolloOS", "", "Workbench", True)
    assert start is True and "ROM" in text


def test_russian_catalog_is_json():
    import json
    catalog = ROOT / "src" / "amigent" / "web" / "locales" / "ru.json"
    data = json.loads(catalog.read_text(encoding="utf-8-sig"))
    assert data["offline"]
    english = json.loads((catalog.parent / "en.json").read_text(encoding="utf-8"))
    assert "status_graphics" in english and "mem_fast_only" in english


def test_trace_is_present_and_not_claimed_for_the_68080():
    assert "trapstub" in DAEMON
    assert "68080" in DAEMON and "not been validated" in DAEMON
    assert (ROOT / "src" / "native" / "amiga" / "daemon" / "trapstub.s").is_file()
