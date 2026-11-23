"""#45: waiting for tasks, who holds the AmiGUS card, its output levels; with fake Amigas."""

import struct

import pytest

import amigent.server as server
from amigent import amigus, memory
from amigent.client import ExecResult
from amigent.errors import AmigaError

SYSBASE, DOS, EXPANSION, LIB, AHI, MHI = 0x1000, 0x2000, 0x3000, 0x4000, 0x5000, 0x5800
CARD, NAME, TASK = 0x6000, 0x7000, 0x8000
BOARDS = (0x9000, 0x9100, 0x9200)


class Memory:
    """Sparse RAM: PEEK outside what was written fails like amigentd refusing it."""

    def __init__(self):
        self.ram = bytearray(0x10000)
        self.used = bytearray(0x10000)
        self.put(4, struct.pack(">I", SYSBASE))

    def put(self, at, data):
        self.ram[at:at + len(data)] = data
        self.used[at:at + len(data)] = b"\1" * len(data)

    def long(self, at, value):
        self.put(at, struct.pack(">I", value))

    def peek(self, at, n):
        if at < 0 or at + n > len(self.ram) or not all(self.used[at:at + n]):
            raise AmigaError("only RAM exec manages and the Kickstart ROM, at most 64 KB", code=1)
        return bytes(self.ram[at:at + n])

    def exec_list(self, header, nodes):
        """An exec list at header with nodes (each gets ln_Succ, ln_Pred)."""
        chain = [header] + list(nodes) + [header + 4]
        self.long(header, chain[1])
        self.long(header + 4, 0)
        self.long(header + 8, chain[-2])
        for i, node in enumerate(nodes, 1):
            self.long(node, chain[i + 1])
            self.long(node + 4, chain[i - 1])


def lines(*extra):
    return [f"L\texec.library\t47\t1\t40\t{SYSBASE:08x}\t1000\t600\t",
            f"L\tdos.library\t47\t1\t30\t{DOS:08x}\t900\t300\t",
            f"L\texpansion.library\t47\t1\t5\t{EXPANSION:08x}\t100\t200\t", *extra]


AMIGUS_LIB = f"L\tamigus.library\t1\t2\t2\t{LIB:08x}\t60\t200\tamigus.library 1.02"
AHI_LIB = f"L\tAmiGUS.audio\t4\t23\t0\t{AHI:08x}\t200\t300\t"
MHI_LIB = f"L\tmhiamigus.library\t1\t0\t1\t{MHI:08x}\t100\t200\t"
TASKS = [memory.TaskInfo(TASK, "PlayMIDI", "C:PlayMidi", "process", 0, "wait", 4096, 500, 0, 0)]


def amiga(zorro=False, owners=(AHI, 0, TASK), layout=True):
    m = Memory()
    m.put(EXPANSION, bytes(100))
    if zorro:
        for b, product in zip(BOARDS, (16, 17, 18)):
            cd = bytearray(48)
            cd[17] = product
            struct.pack_into(">H", cd, 20, amigus.MANUFACTURER)
            struct.pack_into(">I", cd, 32, 0x00E90000 + product * 0x10000)
            m.put(b, bytes(cd))
    m.exec_list(EXPANSION + amigus.BOARD_LIST, BOARDS if zorro else [])
    base = bytearray(200)
    if layout:
        struct.pack_into(">IIII", base, 90, SYSBASE, DOS, EXPANSION, 0)
    m.put(LIB, bytes(base))
    if layout:
        m.exec_list(LIB + 106, [CARD])
    p = bytearray(amigus.PRIVATE_SIZE)
    struct.pack_into(">III", p, amigus.PUBLIC, 0x00600000, 0x00610000, 0x00620000)
    struct.pack_into(">II", p, amigus.PUBLIC + 20, 1, 0x20260830)
    struct.pack_into(">I", p, amigus.PUBLIC + 28, NAME)
    struct.pack_into(">HH", p, amigus.PUBLIC + 32, 0x7000 if zorro else 0x7001, 2026)
    p[amigus.PUBLIC + 36:amigus.PUBLIC + 40] = bytes([8, 30, 12, 5])
    for part, owner in enumerate(owners):
        at = amigus.PART + part * amigus.PART_SIZE
        if zorro:
            struct.pack_into(">I", p, at, BOARDS[part] + amigus.CD_DRIVER)
            m.long(BOARDS[part] + amigus.CD_DRIVER, owner)
        else:
            struct.pack_into(">II", p, at, CARD + at + 4, owner)
    m.put(CARD + 8, bytes(p[8:]))  # the node's links came with the list
    m.put(NAME, b"AmiGUS mini\0" if not zorro else b"AmiGUS\0")
    return m


def status(m, *libs, tasks=TASKS):
    return amigus.status(memory.parse(lines(*libs)), tasks, m.peek, SYSBASE)


def test_ahi_driver_holds_pcm_and_the_reply_warns():
    text = status(amiga(), AMIGUS_LIB, AHI_LIB)
    assert text.startswith("AmiGUS mini (PCMCIA): firmware 2026-08-30 12:05")
    assert "PCM        reserved by the AHI driver AmiGUS.audio" in text
    assert "wavetable  free" in text
    assert "codec      reserved by the task C:PlayMidi" in text
    assert "AHI driver AmiGUS.audio 4.23, open 0" in text
    assert amigus.AHI_HELD in text and "nothing was reserved" in text


def test_zorro_card_owners_live_in_the_boards():
    m = amiga(zorro=True, owners=(0, 0, CARD + amigus.PUBLIC))
    text = status(m, AMIGUS_LIB, MHI_LIB)
    assert "PCM        free" in text and "gave the card itself as owner" in text
    assert "Zorro boards: PCM at $00F90000, wavetable at $00FA0000, codec at $00FB0000" in text
    assert "AHI driver AmiGUS.audio is not loaded" in text and "MHI driver mhiamigus.library 1.0" in text
    assert "Warning" not in text


def test_unknown_owner_and_the_mhi_driver():
    text = status(amiga(owners=(0, 0, 0x5900)), AMIGUS_LIB, MHI_LIB)
    assert "owner $00005900, not a library or task" in text and "handle of its own" in text


def test_no_amigus_at_all():
    text = status(amiga())
    assert text.startswith("No AmiGUS found: no Zorro board from manufacturer 2782")
    assert "PCMCIA" in text


def test_library_without_a_card():
    m = amiga()
    m.exec_list(LIB + 106, [])
    assert status(m, AMIGUS_LIB).startswith("No AmiGUS: amigus.library is loaded but found no card.")


def test_a_layout_we_do_not_know_is_said_not_guessed():
    text = status(amiga(layout=False), AMIGUS_LIB, AHI_LIB)
    assert "reservations unknown" in text and "reserved by" not in text
    assert text.splitlines()[-2].startswith("Probably: PCM is held by the AHI driver")


def test_a_bad_owner_pointer_is_not_believed():
    m = amiga()
    m.long(CARD + amigus.PART, 0x00BFE001)  # PCM's owner pointer somewhere else
    assert "PCM        unknown" in status(m, AMIGUS_LIB, AHI_LIB)


def test_the_tool_reads_through_the_session(monkeypatch):
    m = amiga()
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server, "_loaded", lambda: memory.parse(lines(AMIGUS_LIB, AHI_LIB)))
    monkeypatch.setattr(server, "_tasks", lambda: TASKS)

    class Ctl:
        peek = staticmethod(m.peek)
    monkeypatch.setattr(server._session(), "ctl", Ctl())
    assert "reserved by the AHI driver" in server.amiga_amigus_status()


# ---- waiting for tasks

def task(name, command="", address=0x8000):
    return memory.TaskInfo(address, name, command, "process", 0, "wait", 4096, 100, 0, 0)


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    slept = []
    monkeypatch.setattr(server.time, "monotonic", lambda: now[0])

    def sleep(s):
        slept.append(s)
        now[0] += s
    monkeypatch.setattr(server.time, "sleep", sleep)
    return slept


def feed(monkeypatch, *rounds):
    it = iter(rounds)
    last = [[]]

    def tasks():
        last[0] = next(it, last[0])
        return last[0]
    monkeypatch.setattr(server, "_tasks", tasks)


def test_wait_until_a_program_appears(monkeypatch, clock):
    feed(monkeypatch, [], [], [task("Background CLI", "Work:Tools/Player")])
    text = server.amiga_wait_task("player", timeout=30)
    assert text.startswith("1 task(s) match 'player' after 2 s:") and "Work:Tools/Player" in text
    assert clock == [1.0, 1.5]


def test_wait_until_it_is_gone(monkeypatch, clock):
    feed(monkeypatch, [task("Shell", "C:Copy")], [task("Shell", "C:Copy")], [])
    assert server.amiga_wait_task("Copy", gone=True) == "no task matches 'Copy' any more; gone after 2 s"


def test_gone_when_it_never_ran(monkeypatch, clock):
    feed(monkeypatch, [task("input.device")])
    assert server.amiga_wait_task("Copy", gone=True) == "no task matches 'Copy': none was running"
    assert clock == []


def test_wait_task_times_out_and_says_so(monkeypatch, clock):
    feed(monkeypatch, [task("Shell", "C:Copy")])
    text = server.amiga_wait_task("copy", gone=True, timeout=5)
    assert text.startswith("timeout: 1 task(s) matching 'copy' still there after 5 s")
    assert sum(clock) == pytest.approx(5)
    assert max(clock) <= server.TASK_POLL[1]
    feed(monkeypatch, [])
    assert server.amiga_wait_task("Copy", timeout=2) == "timeout: no task matches 'Copy' after 2 s"


def test_wait_task_by_address(monkeypatch, clock):
    feed(monkeypatch, [task("Shell", "C:Copy", 0x08DBE8C0)])
    assert "C:Copy" in server.amiga_wait_task("$08DBE8C0")
    with pytest.raises(AmigaError):
        server.amiga_wait_task("  ")


def test_match_tasks_prefers_exact_names():
    tasks = [task("Shell", "C:Copy", 1), task("Shell", "C:CopyMore", 2)]
    assert [t.address for t in memory.match_tasks(tasks, "copy")] == [1]
    assert [t.address for t in memory.match_tasks(tasks, "opy")] == [1, 2]


# ---- output levels

LEVELS = ("CARD\tAmiGUS mini\t00600000\n" + "".join(f"S\t{left}\t{right}\n" for left, right in
          [(16000, 0), (-32767, 3), (100, -20)] * 10)
          + "MODE\tSCOPE mode $0000, measured with $0001, put back\nTICKS\t150\n")


def test_levels_are_summed_up():
    text = amigus.levels(LEVELS, 3, 10, True)
    assert text.startswith("AmiGUS mini (PCM part at $00600000): 30 samples at 10 Hz, 3.0 s on the Amiga, peak")
    assert "left  max 32767    0.0 dBFS" in text and ", sound" in text.splitlines()[1]
    assert text.splitlines()[2].startswith("right max    20") and text.splitlines()[2].endswith("silent")
    assert "48/0 100/0 0/0" in text and "put back" in text


def test_levels_without_a_card():
    assert amigus.levels("ERROR\tNo AmiGUS found: nothing\n", 2, 10, True) == "No AmiGUS found: nothing"


def test_the_levels_tool_copies_the_helper_once(monkeypatch, tmp_path):
    import amigent.paths as paths
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "amigent-levels").write_bytes(b"\0\0\3\363hunk")
    monkeypatch.setattr(paths, "AMIGA", tmp_path)
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())

    class Ctl:
        files, commands = {}, []

        def read_file(self, path):
            if path not in self.files:
                raise AmigaError("object not found", code=205)
            return self.files[path]

        def write_file(self, path, data):
            self.files[path] = data

        def exec(self, command, cd=None, timeout=None):
            self.commands.append((command, timeout))
            return ExecResult(0, LEVELS)
    ctl = Ctl()
    monkeypatch.setattr(server._session(), "ctl", ctl)
    assert "30 samples" in server.amiga_audio_levels(seconds=3, hz=10)
    assert "30 samples" in server.amiga_audio_levels(seconds=99, hz=0, peak=False)
    assert ctl.files == {"T:amigent-levels": b"\0\0\3\363hunk"}
    assert ctl.commands == [("T:amigent-levels SECONDS 3 HZ 10 PEAK", 33),
                            ("T:amigent-levels SECONDS 30 HZ 1", 60)]


def test_the_levels_tool_says_when_the_helper_is_missing(monkeypatch, tmp_path):
    import amigent.paths as paths
    monkeypatch.setattr(paths, "AMIGA", tmp_path)
    with pytest.raises(AmigaError, match="amigent-levels.c"):
        server.amiga_audio_levels()


def test_a_steady_level_is_called_a_held_value():
    """An AmiGUS mini kept left at 3973 in silence after playback; that is no sound."""
    held = "CARD\tAmiGUS mini\t00A00100\n" + "S\t3973\t1\n" * 20 + "TICKS\t100\n"
    text = amigus.levels(held, 2, 10, True)
    assert text.splitlines()[1].endswith("steady, probably a held value and not sound")
    assert text.splitlines()[2].endswith("silent")
    assert "measure once in silence" in text
