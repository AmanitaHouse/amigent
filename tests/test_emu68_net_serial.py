"""#20 the Pi's network for Emu68, #21 the Pi's serial debug log; with fakes only."""

import json
import struct
import time

import pytest

import amigent.server as server
from amigent import emu68net, memory, serial_log
from amigent.channel import AmigaChannel
from amigent.client import ExecResult
from amigent.errors import AmigaError

from fakeamiga import FakeAmiga


# ---------------------------------------------------------------- serial recorder

class FakePort:
    """pyserial's Serial as far as the recorder uses it: read(n), close()."""

    def __init__(self, chunks=(), fail_after=None, pause=0.0):
        self.chunks, self.fail_after, self.pause = list(chunks), fail_after, pause
        self.reads, self.closed, self.written = 0, False, []
        self.port = "FAKE0"

    def read(self, n):
        self.reads += 1
        if self.fail_after is not None and self.reads > self.fail_after:
            raise OSError("device disconnected")
        if self.chunks:
            return self.chunks.pop(0)
        time.sleep(self.pause)
        return b""

    def write(self, data):  # never called: the recorder only reads
        self.written.append(data)

    def close(self):
        self.closed = True


class Clock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_recorder_stamps_whole_lines_and_waits_for_the_rest(tmp_path):
    clock = Clock()
    port = FakePort([b"Emu68 start\r\nJIT: unit at 00f8", b"0000\nhalf", b""])
    rec = serial_log.Recorder(port, tmp_path / "s.log", name="FAKE0", clock=clock)
    rec.target.parent.mkdir(parents=True, exist_ok=True)
    rec.tick()
    rec.tick()
    lines = [r for r in (tmp_path / "s.log").read_text().splitlines()]
    assert [r[24:] for r in lines] == ["Emu68 start", "JIT: unit at 00f80000"]
    assert lines[0][:4] == time.strftime("%Y", time.localtime(clock.t))
    clock.t += serial_log.FLUSH_AFTER + 0.1
    rec.tick()  # quiet long enough: the half line goes out on its own
    assert (tmp_path / "s.log").read_text().splitlines()[-1].endswith(" half")
    assert rec.lines == 3 and port.written == []


def test_recorder_notes_a_pulled_adapter_and_stops(tmp_path):
    rec = serial_log.Recorder(FakePort(fail_after=0), tmp_path / "s.log", name="FAKE0")
    rec.target.parent.mkdir(parents=True, exist_ok=True)
    rec.tick()
    assert "device disconnected" in rec.error
    assert "the serial port failed" in (tmp_path / "s.log").read_text()
    assert not rec.running


def test_start_and_stop_in_the_server_thread(monkeypatch):
    port = FakePort([b"hello\n"], pause=0.01)
    rec = serial_log.start("test", "FAKE0", opener=lambda device, baud: port)
    deadline = time.monotonic() + 5
    while rec.lines < 1 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert serial_log.status("test")["recording"] is True
    assert serial_log.start("test", "FAKE0", opener=lambda d, b: FakePort()) is rec  # one per Amiga
    assert serial_log.stop("test") and port.closed
    assert serial_log.status("test")["recording"] is False
    assert serial_log.tail("test")[-1].endswith(" hello")


def test_without_pyserial_the_message_says_how_to_get_it(monkeypatch):
    import builtins
    real = builtins.__import__

    def no_serial(name, *a, **k):
        if name == "serial" or name.startswith("serial."):
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_serial)
    with pytest.raises(RuntimeError, match=r"amigent\[serial\]"):
        serial_log.open_port("COM5")
    assert serial_log.ports() == []
    with pytest.raises(AmigaError, match=r"amigent\[serial\]"):
        server.amiga_serial_log("start")
    monkeypatch.setattr(serial_log, "_has_pyserial", lambda: True)
    with pytest.raises(RuntimeError, match="no serial port found"):
        serial_log.pick_port("")


def test_tail_before_a_moment_and_read_since(tmp_path):
    target = serial_log.log_file("test")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("2026-11-21 10:00:00.000 one\n--- 2026-11-21 10:00:01 amigent: x ---\n"
                      "2026-11-21 10:00:02.000 two\n2026-11-21 10:05:00.000 after\n")
    moment = time.mktime(time.strptime("2026-11-21 10:01:00", serial_log.STAMP))
    assert serial_log.tail("test", before=moment) == ["2026-11-21 10:00:00.000 one", "2026-11-21 10:00:02.000 two"]
    assert serial_log.tail("test", 2)[-1].endswith("after")
    size, text = serial_log.read_since("test", 0)
    assert size == target.stat().st_size and "two" in text
    assert serial_log.read_since("test", size) == (size, "")
    assert serial_log.read_since("test", size + 99)[1].startswith("2026")  # shorter: from the start


def _recorded(text):
    target = serial_log.log_file("test")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def test_debug_log_adds_the_serial_line_and_works_when_the_amiga_is_frozen(monkeypatch):
    _recorded("2026-11-21 10:00:00.000 [JIT] unit 00f80000\n")

    class Ctl:
        def debug_log(self, since):
            return 5, b"kprintf"
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server._session(), "ctl", Ctl())
    text = server.amiga_debug_log()
    assert text.startswith("kprintf\n--- the Pi's serial line") and "unit 00f80000" in text
    assert server.amiga_debug_log() == "kprintf"  # the serial part only once

    def gone(f):
        raise AmigaError("cannot reach amigentd")
    monkeypatch.setattr(server, "_with_ctl", gone)
    _recorded("2026-11-21 10:00:00.000 [JIT] unit 00f80000\n2026-11-21 10:00:09.000 last words\n")
    text = server.amiga_debug_log()
    assert "does not answer" in text and "last words" in text


def test_debug_log_without_a_record_is_unchanged(monkeypatch):
    class Ctl:
        def debug_log(self, since):
            return 0, b""
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server._session(), "ctl", Ctl())
    assert server.amiga_debug_log() == "no new debug output"


def test_status_gives_the_last_serial_lines_when_the_amiga_is_away(monkeypatch):
    def gone(f):
        raise AmigaError("cannot reach amigentd at the Amiga")
    monkeypatch.setattr(server, "_with_ctl", gone)
    with pytest.raises(AmigaError) as plain:
        server.amiga_status()
    assert "serial" not in str(plain.value)
    _recorded("2026-11-21 10:00:00.000 Exception: data abort at 0x1234\n")
    with pytest.raises(AmigaError, match="data abort at 0x1234"):
        server.amiga_status()


# ---------------------------------------------------------------- Emu68's debug range

def test_range_program_is_a_hunk_with_movec_to_the_debug_registers():
    data = serial_log.range_program(0x00F80000, 0x00FFFFFF, verbose=2, disassemble=True)
    header = struct.unpack(">6I", data[:24])
    assert header == (0x3F3, 0, 1, 0, 0, (len(data) - 36) // 4)
    assert struct.unpack(">II", data[24:32]) == (0x3E9, header[5]) and data[-4:] == b"\0\0\3\xf2"
    code = data[32:-4]
    assert code[4:8] == bytes.fromhex("4BFA000E") and 6 + 0x0E == 20
    assert code[20:22] == bytes.fromhex("203C")  # lea's target: the supervisor part
    assert code[8:12] == bytes.fromhex("4EAEFFE2") and code[12:16] == bytes.fromhex("4EAEFD84")
    assert bytes.fromhex("00F80000 4E7B00EE".replace(" ", "")) in code
    assert bytes.fromhex("00FFFFFF 4E7B00EF".replace(" ", "")) in code
    assert bytes.fromhex("00000006 4E7B00ED".replace(" ", "")) in code  # verbose 2 | disasm 4
    assert code.rstrip(b"\0").endswith(bytes.fromhex("4E73"))
    with pytest.raises(ValueError):
        serial_log.range_program(5, 4)
    with pytest.raises(ValueError):
        serial_log.control(4, False)


def test_narrow_needs_emu68_and_confirm(monkeypatch):
    runs = []

    class Ctl:
        def write_file(self, path, data):
            runs.append(("write", path, data))

        def exec(self, command, timeout=None, cd=None):
            runs.append(("exec", command))
            return ExecResult(0, "")
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server._session(), "ctl", Ctl())
    monkeypatch.setattr(server, "_is_emu68", lambda: False)
    with pytest.raises(AmigaError, match="only on Emu68"):
        server.amiga_serial_log("narrow", low="$F80000", high="$FFFFFF", confirm=True)
    monkeypatch.setattr(server, "_is_emu68", lambda: True)
    assert server.amiga_serial_log("narrow", low="$F80000", high="0xFFFFFF").startswith("nothing changed")
    assert runs == []
    said = server.amiga_serial_log("narrow", low="$F80000", high="FFFFFF", confirm=True)
    assert "$00F80000..$00FFFFFF" in said and runs[-1] == ("exec", "RAM:amigent-emu68dbg")
    assert runs[0][2] == serial_log.range_program(0xF80000, 0xFFFFFF, 1, False)
    server.amiga_serial_log("wide", confirm=True)
    assert runs[-2][2] == serial_log.range_program(0, 0xFFFFFFFF, 0, False)
    with pytest.raises(AmigaError, match="hex"):
        server.amiga_serial_log("narrow", low="zz", high="1", confirm=True)


def test_is_emu68_reads_the_resource(monkeypatch):
    emu = ["R\tdevicetree.resource\t1\t0\t0\t0a200000\t0\t0\t"]
    monkeypatch.setattr(server, "_loaded", lambda: memory.parse(emu))
    assert server._is_emu68() is True
    monkeypatch.setattr(server, "_loaded", lambda: memory.parse([]))
    assert server._is_emu68() is False


def test_cli_lists_ports_without_pyserial(monkeypatch, capsys):
    monkeypatch.setattr(serial_log, "ports", lambda: [])
    monkeypatch.setattr(serial_log, "_has_pyserial", lambda: False)
    assert serial_log.main(["--list"]) == 0
    assert "pyserial" in capsys.readouterr().out


# ---------------------------------------------------------------- the Pi's network

SHOW_BEFORE = "Interface 'plip' (plip.device unit 0)\n  Address 10.0.0.50 mask 255.255.255.0\n  Gateway 10.0.0.1\n"
SHOW_AFTER = SHOW_BEFORE + "Interface 'pieth' (genet.device unit 0)\n  Address 10.0.0.77 mask 255.255.255.0\n"


class NetAmiga:
    """A command channel over an in-memory disk with Roadshow, enough for emu68net."""

    def __init__(self, drivers=("wifipi.device",), stack="Roadshow"):
        self.files = {"DEVS:NetInterfaces/plip": b"device=plip.device\nunit=0\nconfigure=dhcp\n"}
        if stack == "Roadshow":
            self.files["C:AddNetInterface"] = b"x"
        for d in drivers:
            self.files[f"DEVS:Networks/{d}"] = b"x"
        self.dirs = {"DEVS:NetInterfaces", "DEVS:Networks"}
        self.commands, self.up = [], False

    def stat(self, path):
        if path in self.files:
            return {"type": "file", "size": len(self.files[path])}
        if path in self.dirs:
            return {"type": "dir"}
        raise AmigaError("object not found", code=205)

    def list_dir(self, path):
        prefix = path.rstrip("/") + "/"
        return [{"name": p[len(prefix):], "type": "FILE"} for p in self.files
                if p.startswith(prefix) and "/" not in p[len(prefix):]]

    def read_file(self, path):
        try:
            return self.files[path]
        except KeyError:
            raise AmigaError("object not found", code=205) from None

    def write_file(self, path, data, append=False):
        self.files[path] = data

    def delete(self, path):
        if path not in self.files:
            raise AmigaError("object not found", code=205)
        del self.files[path]

    def makedir(self, path):
        self.dirs.add(path)

    def exec(self, command, timeout=None, cd=None):
        self.commands.append(command)
        if command.startswith("Version"):
            return ExecResult(0, "wifipi.device 0.3\n")
        if command == "ShowNetStatus":
            return ExecResult(0, SHOW_AFTER if self.up else SHOW_BEFORE)
        if command.startswith("AddNetInterface"):
            self.up = True
        return ExecResult(0, "")


@pytest.fixture
def net(monkeypatch):
    amiga = NetAmiga(drivers=("genet.device", "wifipi.device"))
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server._session(), "ctl", amiga)
    monkeypatch.setattr(server, "_is_emu68", lambda: True)
    monkeypatch.setattr(server, "_home", lambda: "SYS:amigent")
    monkeypatch.setattr(server.machines, "local_networks", lambda: [])
    monkeypatch.setattr(server.machines, "address", lambda host: "10.0.0.50")
    moves = []
    monkeypatch.setattr(server.machines, "move", lambda host, new: moves.append(new))
    monkeypatch.setattr(server._session(), "refresh_address", lambda: None)
    monkeypatch.setattr(server, "_pinet_channel", lambda address: Through(amiga, address))
    amiga.moves = moves
    return amiga


class Through:
    """The same Amiga reached at the new address."""

    def __init__(self, amiga, address):
        self.amiga, self.address = amiga, address
        assert address == "10.0.0.77"

    def __getattr__(self, name):
        return getattr(self.amiga, name)

    def close(self):
        pass


def test_report_names_the_missing_driver_and_where_it_comes_from():
    amiga = NetAmiga(drivers=("wifipi.device",))
    facts = emu68net.report(amiga, emu68=True, link={"line_kbs": 17})
    assert facts["ethernet"]["installed"] is False
    assert "emu68-genet" in facts["ethernet"]["missing"]
    assert facts["wifi"]["installed"] is True and facts["wifi"]["version"] == "wifipi.device 0.3"
    assert facts["stack"]["name"] == "Roadshow"
    assert facts["interfaces"] == [{"name": "plip", "device": "plip.device", "unit": "0", "configure": "dhcp"}]
    assert facts["addresses_now"] == ["10.0.0.50", "10.0.0.1"]
    assert facts["link"] == {"line_kbs": 17}
    assert not any(c.startswith(("AddNet", "Configure", "Run")) for c in amiga.commands)


def test_other_stacks_are_reported_not_set_up():
    amiga = NetAmiga(stack="AmiTCP")
    del amiga.files["DEVS:NetInterfaces/plip"]
    amiga.dirs.discard("DEVS:NetInterfaces")
    amiga.dirs.add("AmiTCP:")
    facts = emu68net.report(amiga, emu68=True)
    assert facts["stack"]["name"] == "AmiTCP" and facts["stack"]["can_set_up"] is False


def test_addresses_and_new_address():
    found = emu68net.addresses("addr 10.0.0.5 mask 255.255.255.0 lo 127.0.0.1 0.0.0.0 999.1.1.1")
    assert found == ["10.0.0.5"]
    import ipaddress
    lan = [ipaddress.ip_network("192.168.1.0/24")]
    assert emu68net.new_address(["10.0.0.5"], ["10.0.0.5", "172.16.0.9", "192.168.1.9"], "10.0.0.5", lan) == "192.168.1.9"
    assert emu68net.new_address(["10.0.0.5"], ["10.0.0.5"], "10.0.0.5") == ""


def test_probation_script_restores_without_network_and_deletes_nothing_old():
    record = emu68net.Record("ethernet", "pieth", "SYS:amigent", "10.0.0.50", probation=60)
    script = emu68net.probation_script(record)
    assert "Wait 60 SECS" in script and emu68net.CONFIRM_FLAG in script
    assert "ConfigureNetInterface >NIL: pieth STATE=DOWN" in script
    assert "DEVS:NetInterfaces" not in script  # on probation nothing of the system changed
    undo = emu68net.undo_script(record)
    deleted = [line for line in undo.splitlines() if "Delete" in line and "NetInterfaces" in line]
    assert deleted and all("NetInterfaces/pieth" in line for line in deleted)


def test_setup_without_confirm_changes_nothing(net):
    before = dict(net.files)
    said = server.amiga_pi_network("setup", "ethernet")
    assert said.startswith("nothing changed") and "confirm=True" in said
    assert net.files == before
    assert not any(c.startswith(("AddNet", "Run")) for c in net.commands)


def test_setup_on_probation_then_kept_then_undone(net, monkeypatch):
    monkeypatch.setattr(emu68net, "speed", lambda ctl: 17.0 if not isinstance(ctl, Through) else 1700.0)
    said = server.amiga_pi_network("setup", "ethernet", confirm=True, probation=60)
    assert said.startswith("kept: pieth answers at 10.0.0.77"), said
    assert "17.0 KB/s before, 1700.0 KB/s now" in said
    staged = "SYS:amigent/net/pieth"
    assert b"device=genet.device" in net.files[staged]
    run = net.commands.index('Run >NIL: Execute "SYS:amigent/net/probation"')
    add = net.commands.index(f'AddNetInterface "{staged}"')
    assert run < add  # the way back is running before anything comes up
    assert net.files[emu68net.CONFIRM_FLAG] == b"1\n"
    assert net.files["DEVS:NetInterfaces/pieth"] == net.files[staged]
    assert net.files["DEVS:NetInterfaces/plip"].startswith(b"device=plip.device")  # the old one stays
    assert "pi-network.repair" in "".join(net.files)
    assert net.moves == ["10.0.0.77"]
    record = emu68net.load(server._amiga())
    assert record.state == "kept" and record.before == ["plip"]
    on_amiga = json.loads(net.files["SYS:amigent/net/record.json"])
    assert on_amiga["interface"] == "pieth"
    assert "set up already" in server.amiga_pi_network("setup", "ethernet", confirm=True)

    monkeypatch.setattr(server.machines, "address", lambda host: "10.0.0.77")
    said = server.amiga_pi_network("undo")
    assert "DEVS:NetInterfaces/pieth removed" in said and "10.0.0.50 again" in said
    undo = net.files["RAM:amigent-pinet-undo.script"].decode()
    assert "STATE=DOWN" in undo and "plip" not in undo
    assert net.moves[-1] == "10.0.0.50"
    assert emu68net.load(server._amiga()).state == "undone"


def test_too_late_confirmation_keeps_nothing(net, monkeypatch):
    monkeypatch.setattr(emu68net, "speed", lambda ctl: 0.0)
    record = emu68net.Record("wifi", "piwifi", "SYS:amigent", "10.0.0.50", new_address="10.0.0.77")
    emu68net.save(server._amiga(), record)
    net.files[record.log] = b"restored: no confirmation within 90 s, piwifi is down again\n"
    said = server.amiga_pi_network("confirm")
    assert said.startswith("too late") and "DEVS:NetInterfaces/piwifi" not in net.files
    assert net.moves == []


def test_setup_refuses_what_it_should(net, monkeypatch):
    del net.files["DEVS:Networks/genet.device"]
    with pytest.raises(AmigaError, match="emu68-genet"):
        server.amiga_pi_network("setup", "ethernet", confirm=True)
    net.files["DEVS:NetInterfaces/piwifi"] = b"device=wifipi.device\n"
    with pytest.raises(AmigaError, match="not Amigent's"):
        server.amiga_pi_network("setup", "wifi", confirm=True)
    assert net.files["DEVS:NetInterfaces/piwifi"] == b"device=wifipi.device\n"
    monkeypatch.setattr(server, "_is_emu68", lambda: False)
    with pytest.raises(AmigaError, match="Emu68"):
        server.amiga_pi_network("setup", "wifi", confirm=True)
    with pytest.raises(AmigaError, match="'ethernet' or 'wifi'"):
        emu68net.kind("token ring")
    assert not any(c.startswith(("AddNet", "Run")) for c in net.commands)


def test_report_through_the_tool(net):
    facts = json.loads(server.amiga_pi_network())
    assert facts["emu68"] is True and facts["ethernet"]["installed"] is True


def test_channel_dials_the_given_address():
    fake = FakeAmiga()
    try:
        fake.files["RAM:x"] = b"hi"
        chan = AmigaChannel("not-registered.invalid", fake.port, timeout=5, address="127.0.0.1")
        chan.connect()
        assert chan.read_file("RAM:x") == b"hi"
        chan.close()
    finally:
        fake.close()
