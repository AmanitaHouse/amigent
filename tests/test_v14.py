"""1.4.0: guru codes in words, the journal and postmortem, numbered jobs, what is
loaded, memory and code, and the emulator's GDB server."""

import socket
import struct
import threading
import time

import pytest

import amigent.server as server
from amigent import alerts, gdb, journal, memory, uptime
from amigent.channel import LOADED, PEEK, AmigaChannel
from amigent.errors import AmigaError

# ---- guru codes


def test_known_gurus_are_named():
    assert alerts.describe("8100000C").startswith("exec.library: the memory list is insane; dead end")
    assert "memory was freed twice; recoverable" in alerts.describe("01000009")
    assert alerts.describe("00000004").startswith("CPU exception: illegal instruction")
    assert "line F" in alerts.describe(0x8000000B)
    assert "(dos.library)" in alerts.describe("83038007")


def test_the_second_number_is_said():
    assert "0C1234A0" in alerts.describe("81000005", "0c1234a0")


def test_unknown_codes_keep_their_part():
    text = alerts.describe("84ABCDEF")
    assert text.startswith("intuition.library:") and "dead end" in text


def test_uptime_note_names_the_guru():
    said = uptime.notes({"last_alert": "8100000c", "last_alert_where": "0c1234a0"}, None, 0)
    assert "guru 8100000C.0C1234A0" in said[0] and "memory list is insane" in said[0]


# ---- journal and postmortem


def test_journal_keeps_the_last_calls(tmp_path):
    j = journal.Journal(tmp_path)
    for i in range(50):
        j.add("A1200", f"exec {i}", now=1000 + i)
    last = j.recent("A1200", most=100)
    assert len(last) == journal.KEEP and last[-1]["did"] == "exec 49"
    assert [e["did"] for e in j.recent("A1200", before=1020, most=2)] == ["exec 19", "exec 20"]
    j.add("A1200", "start HiP", ok=False, now=2000)
    assert journal.describe(j.recent("A1200", most=1), now=2060) == ["60 s ago: start HiP (failed)"]


def test_seen_keeps_the_tasks(tmp_path):
    seen = uptime.Seen(tmp_path / "u.json")
    seen.check("A1200", {"uptime": "100", "daemon_uptime": "90"}, now=1000, tasks="HiP|Workbench")
    assert seen.previous("A1200")["tasks"] == "HiP|Workbench"


def test_postmortem_says_what_ran_and_what_was_done(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "diary", journal.Journal(tmp_path))
    monkeypatch.setattr(server, "_amiga_name", lambda: "A1200")
    now = time.time()
    server.diary.add("A1200", "start GLQuake", now=now - 600)
    server.diary.add("A1200", "key esc", now=now - 590)
    out = server._postmortem({"tasks": "GLQuake|Workbench|input.device"}, {"uptime": "60"},
                             "Workbench|input.device")
    assert out["running_then_not_now"] == ["glquake"]
    assert [x.split(": ", 1)[1] for x in out["last_actions"]] == ["start GLQuake", "key esc"]


def test_looking_around_is_not_journaled():
    assert {"amiga_status", "amiga_screenshot", "amiga_loaded"} <= server.UNJOURNALED
    assert "amiga_start" not in server.UNJOURNALED


# ---- numbered jobs


def test_job_result_says_a_bad_return_code():
    assert server._job_result(3, "0\n", b"done\n") == "done\n"
    assert server._job_result(3, "20\n", b"oops\n") == "oops\n[job 3 ended with rc 20]"


def test_job_numbers_continue_after_those_in_ram(monkeypatch):
    class Ctl:
        def list_dir(self, path):
            return [{"name": "amigent-job-4.cmd"}, {"name": "amigent-job-9.out"},
                    {"name": "amigent-job-2.cmd"}]
    monkeypatch.setattr(server, "ctl", Ctl())
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server, "_job_numbers", [])
    assert server._known_jobs() == [2, 4]
    assert server._next_job() == 5 and server._next_job() == 6


# ---- loaded, names, memory, code

LOADED_LINES = [
    "L\texec.library\t47\t99\t40\t00000ac0\t1032\t632\texec 47.99 (1.1.2026)\r",
    "L\tdos.library\t47\t5\t30\t0a100000\t984\t300\tdos 47.5",
    "D\ttimer.device\t47\t1\t12\t0a200000\t60\t120\t",
    "R\tciaa.resource\t0\t0\t0\t00bfe001\t0\t0\t",
    "H\tShell Process\tWork:C/dmatest\t0\t0a300004\t1000",
    "H\tShell Process\tWork:C/dmatest\t1\t0a400004\t200",
    "M\texec.library\t47\t00f800b6\t00f84000",
    "M\tdos.library\t47\t00f90000\t00fa0000",
]


def test_loaded_lines_parse_and_list():
    loaded = memory.parse(LOADED_LINES)
    assert len(loaded.libraries) == 4 and len(loaded.hunks) == 2 and len(loaded.residents) == 2
    text = memory.listing(loaded)
    assert "library  dos.library" in text and "47.5" in text and "open 30" in text
    assert "program  Work:C/dmatest" in text and "2 hunks" in text
    assert memory.listing(loaded, "devices") .startswith("device   timer.device")
    assert "dos.library" not in memory.listing(loaded, "devices")
    assert memory.listing(loaded, "libraries", "exec").count("\n") == 0


def jump_table(lib_size, entries):
    """neg_size bytes ending at the base: JMP abs.l for each (lvo, target)."""
    data = bytearray(lib_size)
    for lvo, target in entries:
        at = lib_size - lvo
        data[at:at + 6] = b"\x4e\xf9" + struct.pack(">I", target)
    return bytes(data)


def test_addresses_get_names():
    loaded = memory.parse(LOADED_LINES)
    dos = jump_table(984, [(48, 0x0A150000), (42, 0x0A150400)])  # Write, Read

    def peek(at, n):
        return dos if at == 0x0A100000 - 984 else bytes(n)
    namer = memory.Namer(loaded, peek)
    assert namer.name(0x0A300010) == "Work:C/dmatest hunk 0 +$C"
    assert namer.name(0x0A100000 - 48) == "dos.library jump table, LVO -48 Write"
    assert namer.name(0x0A150010) == "dos.library Write +$10"
    assert namer.name(0x0A150410) == "dos.library Read +$10"
    assert namer.name(0x00F80200) == "exec.library (resident) +$14A"
    assert memory.resolve("dos.library/Write", namer) == 0x0A150000
    assert memory.resolve("dos.library", namer) == 0x0A100000
    assert memory.resolve("$0a300010", namer) == memory.resolve("0A300010", namer) == 0x0A300010
    assert memory.resolve("00F80000", namer) == 0xF80000


def test_library_calls_are_named_in_code():
    pytest.importorskip("capstone")
    code = bytes.fromhex("2c7800044eaeff7c2c79000012344eaeffd04e75")
    text = memory.disassemble(code, 0x0A000000)
    assert "a6 = SysBase" in text and "exec Forbid" in text
    assert "dos Write" in text.splitlines()[3]  # a6 unknown again: the likely names
    assert "dos Write" in memory.disassemble(bytes.fromhex("4eaeffd0"), 0, a6="dos")


def test_lvo_tables_cover_the_common_libraries():
    t = memory.lvo_tables()
    assert t["exec.library"][132] == "Forbid" and t["dos.library"][48] == "Write"
    assert t["intuition.library"][204] == "OpenWindow" and len(t) > 60


def test_channel_asks_for_loaded_and_memory(monkeypatch):
    ch = AmigaChannel("127.0.0.1")
    ch._sock, ch.protocol = object(), 6
    sent = []
    monkeypatch.setattr(ch, "_one", lambda req: sent.append(req) or b"\x4e\x75")
    monkeypatch.setattr(ch, "_text", lambda cmd, path="": sent.append(cmd) or LOADED_LINES)
    assert ch.loaded() == LOADED_LINES and sent[0] == LOADED
    assert ch.peek(0x0A000000, 2) == b"\x4e\x75"
    assert sent[1].cmd == PEEK and sent[1].path == "0a000000" and (sent[1].w, sent[1].h) == (0, 2)
    with pytest.raises(AmigaError):
        ch.peek(0, 0)
    ch.protocol = 5
    with pytest.raises(AmigaError, match="1.4.0"):
        ch.loaded()


# ---- the emulator's GDB server


class FakeGdb:
    """Enough of WinUAE's GDB server: ?, g, m, c, Ctrl-C, qRcmd."""

    def __init__(self):
        self.mem = {0x1000: bytes.fromhex("4e714e75")}
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.monitors = []
        threading.Thread(target=self._serve, daemon=True).start()

    def _reply(self, conn, text):
        conn.sendall(gdb.frame(text))

    def _serve(self):
        conn, _ = self.listener.accept()
        buf = b""
        while True:
            data = conn.recv(4096)
            if not data:
                return
            buf += data
            while buf:
                if buf[:1] == b"\x03":
                    buf = buf[1:]
                    self._reply(conn, "S05")
                    continue
                if buf[:1] in (b"+", b"-"):
                    buf = buf[1:]
                    continue
                if b"#" not in buf or len(buf) < buf.index(b"#") + 3:
                    break
                end = buf.index(b"#")
                packet = buf[1:end].decode()
                buf = buf[end + 3:]
                conn.sendall(b"+")
                if packet == "?":
                    self._reply(conn, "S05")
                elif packet == "g":
                    regs = [i for i in range(16)] + [0x2000, 0x1000]
                    self._reply(conn, "".join(f"{r:08x}" for r in regs))
                elif packet.startswith("m"):
                    at, n = (int(x, 16) for x in packet[1:].split(","))
                    self._reply(conn, self.mem.get(at, bytes(n))[:n].hex())
                elif packet == "c":
                    pass
                elif packet.startswith("qRcmd,"):
                    cmd = bytes.fromhex(packet[6:]).decode()
                    self.monitors.append(cmd)
                    if cmd.startswith("checkpoint"):
                        self._reply(conn, "O" + "saved\n".encode().hex())
                        self._reply(conn, "OK")
                    else:
                        self._reply(conn, "")


def test_gdb_reads_registers_memory_and_saves_the_machine():
    fake = FakeGdb()
    emu = gdb.Gdb(f"127.0.0.1:{fake.port}")
    regs = emu.registers()
    assert regs["pc"] == 0x1000 and regs["a7"] == 15 and emu.running
    assert emu.read(0x1000, 4) == bytes.fromhex("4e714e75")
    assert emu.checkpoint("save", "C:\\state.uss") == "saved\n"
    assert fake.monitors == ["checkpoint save C:\\state.uss"]
    with pytest.raises(gdb.GdbError, match="does not know"):
        emu.monitor("tasks")
    assert emu.pause() == "S05" and not emu.running
    emu.close()


def test_rsp_details():
    assert gdb.frame("g") == b"$g#67"
    assert gdb.unescape(b"0*\"") == b"0" * 6  # run length: '"' is 34, so 5 more
    assert gdb.unescape(b"}\x03") == b"#"
    with pytest.raises(gdb.GdbError):
        gdb.parse_address("2345")


def test_no_emulator_set_says_how(monkeypatch):
    monkeypatch.setattr(server, "HOST", "")
    monkeypatch.delenv("AMIGENT_GDB", raising=False)
    with pytest.raises(AmigaError, match="amigas.json"):
        server._emulator()


def test_windows_paths_for_winuae():
    assert server._host_path("/mnt/c/Users/x/state.uss") == "C:\\Users\\x\\state.uss"
    assert server._host_path("D:\\a.uss") == "D:\\a.uss"
