"""PowerPC boards (#23, #24): card, kernel, flash ROM, PPC tasks, crash windows, WarpOS builds.

No PowerPC board was at hand: the board list, LOADED, WarpOS's tools and its
crash window are all fakes, laid out after expansion.library, WarpOS 4.0's
showinfo and stat, and the format strings of powerpc.library 15.
"""

import struct

import pytest

import amigent.server as server
from amigent import hunks, memory, ppc, project, screentext
from amigent.channel import Commands
from amigent.errors import AmigaError
from fakeamiga import FakeAmiga

EXPANSION, BOARD1, BOARD2 = 0x3000, 0x9000, 0x9100


class Memory:
    """Sparse RAM: a PEEK outside what was written fails like amigentd refusing it."""

    def __init__(self):
        self.ram = bytearray(0x10000)
        self.used = bytearray(0x10000)

    def put(self, at, data):
        self.ram[at:at + len(data)] = data
        self.used[at:at + len(data)] = b"\1" * len(data)

    def long(self, at, value):
        self.put(at, struct.pack(">I", value))

    def peek(self, at, n):
        if at < 0 or at + n > len(self.ram) or not all(self.used[at:at + n]):
            raise AmigaError("only RAM exec manages and the Kickstart ROM", code=1)
        return bytes(self.ram[at:at + n])

    def boards(self, *boards):
        """expansion.library's board list with ConfigDevs (manufacturer, product, address)."""
        header = EXPANSION + 60
        nodes = [BOARD1 + i * 0x100 for i in range(len(boards))]
        chain = [header] + nodes + [header + 4]
        self.long(header, chain[1])
        self.long(header + 4, 0)
        self.long(header + 8, chain[-2])
        for i, (node, (manufacturer, product, address)) in enumerate(zip(nodes, boards), 1):
            cd = bytearray(48)
            struct.pack_into(">II", cd, 0, chain[i + 1], chain[i - 1])
            cd[17] = product
            struct.pack_into(">H", cd, 20, manufacturer)
            struct.pack_into(">II", cd, 32, address, 0x80000)
            self.put(node, bytes(cd))


def lib(name, version, revision=0, kind="L", id_string="", base=0x5000):
    return memory.Library(kind, name, version, revision, 1, base, 60, 60, id_string)


def loaded(*libs, residents=()):
    return memory.Loaded(libraries=[lib("expansion.library", 47, base=EXPANSION), *libs],
                         residents=[memory.Resident(n, v, 0xF00000, 0xF00100) for n, v in residents])


WARPOS = lib("powerpc.library", 17, 10, id_string="powerpc.library 17.10 (12.02.2016)")
POWERUP = lib("ppc.library", 46, 30, id_string="ppc.library 46.30 (1.4.99)")
PPCLIBEMU = lib("ppc.library", 46, 13, id_string="ppc.library 46.13 (11.04.99) Emulation v0.6")
WARPOS_V7 = lib("powerpc.library", 7, 2, id_string="powerpc.library 7.2 (25.3.98)")

SHOWINFO = """CPU:                   PPC 604E   (PVR = 00090202)
CPU clock:             233.000000 MHz
Bus clock:             66.666666 MHz
Instruction Cache:     ON and UNLOCKED
Data Cache:            ON and UNLOCKED
Page table location:   0FF00000
Page table size:       512 KBytes
Time base content:     00000012 3456789A
CPU load:              12.50%
System load:           25.00%
"""

STAT = """Task statistics:

Task name                 ID     NICE  CPUusage  Busy      Activity
Enterprise                100    0       0.10%     0.20%     1.00%
hello                     104    0      85.25%    99.00%    50.00%
WarpRace PPC Task         107    -5      3.00 %    4.00 %    5.00 %

CPU load:        88.35%
System load:    120.00%
"""

CRASH = """Warp-OS                                              1998 by Sam Jordan
PowerPC 604E
Data access exception (load operation)
Access to 00000004
Task name: 'hello'  Task address: 0A12B000  Task ID: 104
SRR0: 0A1C2F40    SRR1:  0000B030     MSR:   0000B030    HID0: 8000C084
PVR:  00090202    DAR:   00000004     DSISR: 40000000    SDR1: 0FFE0003
DEC:  00001234    TBU:   00000012     TBL:   3456789A    XER:  00000000
CR:   24000000    FPSCR: 00000000     LR:    0A1C2E10    CTR:  00000000
R0-R3:   0A1C2E10 0A3FFE80 0A200000 00000000   IBAT0: 00000000 00000000
R4-R7:   00000001 00000002 00000003 00000004   IBAT1: 00000000 00000000
Segment statistics
0A1C2F40 : "hello" Hunk 1 Offset 00000140
"""


# ---- the board

def test_a_cyberstorm_ppc_is_found_in_the_board_list():
    mem = Memory()
    mem.boards((ppc.PHASE5, 100, 0xF0000000), (2782, 16, 0x00E90000))
    found = ppc.boards(mem.peek, EXPANSION)
    assert [b.ppc for b in found] == [True, False]
    assert found[0].name == "CyberStorm PPC or CyberStorm MK III" and found[0].address == 0xF0000000
    assert ppc.Board(ppc.PHASE5, 110, 0, 0).name == "Blizzard PPC"
    assert ppc.Board(ppc.PHASE5, 25, 0, 0).name == "CyberStorm MK II"
    assert not ppc.Board(ppc.PHASE5, 25, 0, 0).ppc


def test_an_unreadable_board_list_is_none():
    assert ppc.boards(Memory().peek, EXPANSION) is None


# ---- the kernel

@pytest.mark.parametrize("libs, active", [
    ([WARPOS], "WarpOS"),
    ([POWERUP], "PowerUP"),
    ([WARPOS, POWERUP], "both"),
    ([WARPOS, PPCLIBEMU], "WarpOS"),     # ppclibemu: ppc.library on top of WarpOS
    ([WARPOS_V7, POWERUP], "PowerUP"),   # powerpc.library V7 on top of PowerUP
    ([], ""),
])
def test_the_active_kernel_is_told(libs, active):
    assert ppc.kernel(libs).active == active


def test_ppclibemu_and_v7_are_named_for_what_they_are():
    text = "\n".join(ppc.kernel([WARPOS, PPCLIBEMU]).lines())
    assert "ppclibemu" in text and "17.10" in text
    assert "V7: the WarpOS calls on top of PowerUP" in "\n".join(ppc.kernel([WARPOS_V7]).lines())
    assert not ppc.warpos_running(ppc.kernel([WARPOS_V7])) and ppc.warpos_running(ppc.kernel([WARPOS]))


def test_known_conflicts():
    both = ppc.conflicts(ppc.kernel([WARPOS, POWERUP]), [], "68060", [lib("68060.library", 46)])
    assert len(both) == 1 and "cannot share the PowerPC" in both[0]
    rom = ppc.conflicts(ppc.kernel([]), [memory.Resident("ppc.library", 46, 0, 0)], "68040",
                        [lib("68040.library", 46)], on_disk="WarpOS powerpc.library 17.10")
    assert len(rom) == 1 and "BPPCFix" in rom[0]
    missing = ppc.conflicts(ppc.kernel([WARPOS]), [], "68060", [lib("68040.library", 46)])
    assert len(missing) == 1 and "68040.library is loaded on a 68060" in missing[0]
    bare = ppc.conflicts(ppc.kernel([WARPOS]), [], "68060", [])
    assert len(bare) == 1 and "without 68060.library" in bare[0]
    assert ppc.conflicts(ppc.kernel([WARPOS, PPCLIBEMU]), [], "68060", [lib("68060.library", 46)]) == []


def test_the_flash_rom_version_and_old_ones():
    rom = ppc.rom_device([lib("cybppc.device", 44, 60, kind="D")], [])
    assert rom == ("cybppc.device", (44, 60)) and "44.67" in ppc.rom_note(*rom)
    assert ppc.rom_note("cybppc.device", (44, 71)) == ""
    assert "44.30" in ppc.rom_note("blizzppc.device", (44, 20))
    assert ppc.rom_device([], [memory.Resident("blizzppc.device", 44, 0, 0)])[0] == "blizzppc.device"
    assert ppc.rom_device([lib("scsi.device", 47, kind="D")], []) is None


def test_patches_in_the_startup_scripts_are_named():
    seen = ppc.patches({"S:Startup-Sequence": "C:SetPatch QUIET\nC:BlizKick MODULE BK_RemPPCLib\n"
                                              "; CSPPC233Fix_wos commented out\n",
                        "S:User-Startup": "Run >NIL: C:CSPPC233Fix_wos\nC:BPPCFixFix\n"})
    assert len(seen) == 3
    assert seen[0].startswith("S:Startup-Sequence line 2") and "BlizKick module" in seen[0]
    assert "LR register" in seen[1] and "BPPCFix" in seen[2] and "loadable from disk" in seen[2]


# ---- WarpOS's tools

def test_showinfo_tells_cpu_and_clock():
    info = ppc.parse_showinfo(SHOWINFO)
    assert info.line() == "PPC 604E (PVR 00090202), 233 MHz, bus 66.666 MHz, CPU load 12.50%"
    assert "MHz" not in ppc.parse_showinfo("CPU: PPC 603E (PVR = 00060101)\nCPU clock: 0.000000 MHz\n").line()


def test_stat_gives_the_ppc_tasks_with_their_load():
    tasks, totals = ppc.parse_stat(STAT)
    assert [t.name for t in tasks] == ["Enterprise", "hello", "WarpRace PPC Task"]
    assert tasks[1].cpu == 85.25 and tasks[2].nice == -5 and tasks[2].activity == 5.0
    assert totals == {"CPU load": "88.35%", "System load": "120.00%"}
    table = ppc.task_table(tasks, totals, "hello")
    assert "hello" in table and "Enterprise" not in table and "CPU  85.2%" in table
    assert ppc.stat_ok(STAT) and not ppc.stat_ok("usage: stat FILE")


def runner(answers):
    calls = []

    def run(command):
        calls.append(command)
        return answers.get(command, (5, ""))
    return run, calls


def test_tools_run_only_while_warpos_is_in_memory():
    run, calls = runner({"Which stat": (0, "SYS:WarpOS/Tools/stat\n"),
                         '"SYS:WarpOS/Tools/stat"': (0, STAT)})
    assert ppc.ppc_tasks(run, ppc.kernel([POWERUP])) == "" and calls == []
    assert "hello" in ppc.ppc_tasks(run, ppc.kernel([WARPOS]))
    run, calls = runner({'"Work:WarpOS/stat"': (0, STAT)})
    assert "Enterprise" in ppc.ppc_tasks(run, ppc.kernel([WARPOS]), "Work:WarpOS")
    assert calls == ['"Work:WarpOS/stat"']
    run, _ = runner({"Which stat": (0, "C:stat\n"), '"C:stat"': (0, "a different stat\n")})
    assert "was not found" in ppc.ppc_tasks(run, ppc.kernel([WARPOS]))


# ---- the crash window

def test_a_warpos_crash_window_is_read():
    assert ppc.is_crash_window("Warp-OS - PowerPC Exception", CRASH)
    assert not ppc.is_crash_window("Shell", "1.SYS:> dir")
    crash = ppc.parse_crash("Warp-OS - PowerPC Exception", CRASH)
    assert crash.kind == "WarpOS" and crash.cpu == "604E"
    assert crash.exception == "Data access exception (load operation)"
    assert crash.task == "hello" and crash.task_id == "104" and crash.access == "Access to 00000004"
    assert crash.registers["SRR0"] == "0A1C2F40" and crash.registers["DAR"] == "00000004"
    assert crash.registers["r1"] == "0A3FFE80" and crash.registers["r7"] == "00000004"
    assert crash.segments == ['0A1C2F40: "hello" hunk 1 +$140']


def test_a_crash_is_explained_like_a_guru():
    crash = ppc.parse_crash("Warp-OS - PowerPC Exception", CRASH)
    names = {0x0A1C2F40: "hello hunk 1 +$140", 0x0A1C2E10: "hello hunk 1 +$10"}
    text = "\n".join(ppc.describe_crash(crash, names.get))
    assert "WarpOS crash on a 604E: Data access exception" in text
    assert "NULL pointer" in text and "SRR0 0A1C2F40: the instruction that failed, hello hunk 1 +$140" in text
    assert "LR 0A1C2E10: the return address (the caller), hello hunk 1 +$10" in text
    assert "checkpo 0A3FFE80 10" in text and "killppc 104" in text
    assert "CSPPC233Fix" not in text


def test_the_csppc_lr_fault_is_pointed_out():
    text = CRASH.replace("Data access exception (load operation)", "Instruction access exception") \
        .replace("LR:    0A1C2E10", "LR:    8A1C2E10")
    out = "\n".join(ppc.describe_crash(ppc.parse_crash("Warp-OS - PowerPC Exception", text)))
    assert "jumped to an address with no code" in out and "CSPPC233Fix" in out


# ---- amiga_ppc on a fake Amiga

def warp_amiga(*libs, residents=(), on_disk=True):
    fake = FakeAmiga()
    fake.protocol = 6
    fake.info["attn_flags"] = "0x80ff"  # 68060 with 68060.library
    fake.answers.update({
        "Version": (0, "Kickstart 47.115, Workbench 47.4\n"),
        "CPU": (0, "System: 68060 (INST: CACHE)\n"),
        "Version FILE LIBS:powerpc.library": (0, "powerpc.library 17.10\n") if on_disk else (20, ""),
        "Version FILE LIBS:ppc.library": (20, ""),
        "Which showinfo": (0, "SYS:WarpOS/Tools/showinfo\n"),
        '"SYS:WarpOS/Tools/showinfo"': (0, SHOWINFO),
        "Which stat": (0, "SYS:WarpOS/Tools/stat\n"),
        '"SYS:WarpOS/Tools/stat"': (0, STAT),
    })
    fake.loaded = ["L\texec.library\t47\t115\t40\t00000ac0\t1032\t632\texec 47.115",
                   f"L\texpansion.library\t47\t1\t5\t{EXPANSION:08x}\t100\t200\t",
                   "L\t68060.library\t46\t3\t1\t0a100000\t60\t60\t68060.library 46.3"] + [
        f"{x.kind}\t{x.name}\t{x.version}\t{x.revision}\t1\t0a110000\t60\t60\t{x.id_string}" for x in libs] + [
        f"M\t{n}\t{v}\tf00000\tf00100" for n, v in residents]
    fake.add("S:User-Startup", b"C:CSPPC233Fix_wos\n")
    fake.add("ENV:PowerPC/crashfile", b";CON:0/20/680/500/Warp-OS - PowerPC Exception/AUTO/CLOSE/WAIT\n")
    return fake


@pytest.fixture
def on(machine_session):
    made = []

    def use(fake):
        made.append(fake)
        machine_session.ctl.close()
        machine_session.ctl = Commands("127.0.0.1", 1, fake.port)
        machine_session.system_seen.clear()
        machine_session.fpu = None
        return fake
    yield use
    machine_session.ctl.close()
    for fake in made:
        fake.close()


def test_amiga_ppc_status_with_warpos(on):
    on(warp_amiga(WARPOS, lib("cybppc.device", 44, 71, kind="D")))
    out = server.amiga_ppc()
    assert "Kernel: WarpOS" in out and "powerpc.library 17.10 in memory" in out
    assert "68k CPU: 68060 with FPU (68060.library loaded)" in out
    assert "PowerPC: PPC 604E (PVR 00090202), 233 MHz" in out
    assert "Flash ROM: cybppc.device 44.71" in out
    assert "CSPPC233Fix" in out and "crash output: off" in out
    assert "read only" in out
    assert "board list could not be read" in out  # this fake has no PEEK


def test_amiga_ppc_status_with_powerup_runs_no_warpos_tool(on, monkeypatch):
    on(warp_amiga(POWERUP, residents=[("ppc.library", 46)], on_disk=False))
    ran, real = [], server._run_rc
    monkeypatch.setattr(server, "_run_rc", lambda c: ran.append(c) or real(c))
    out = server.amiga_ppc()
    assert "Kernel: PowerUP" in out and "resident module" in out and "PPC 604E" not in out
    assert not any("showinfo" in c or "stat" in c for c in ran)


def test_amiga_ppc_without_a_board(on):
    on(warp_amiga(on_disk=False))
    assert server.amiga_ppc().startswith("No PowerPC board found")


def test_amiga_tasks_adds_the_ppc_tasks(on, monkeypatch):
    on(warp_amiga(WARPOS))
    monkeypatch.setattr(server, "_tasks", lambda: [])
    out = server.amiga_tasks()
    assert "PowerPC tasks (WarpOS stat)" in out and "hello" in out
    assert "WarpRace" not in server.amiga_tasks("hello")
    assert "hello" in server.amiga_ppc("tasks")


def test_amiga_tasks_stays_as_it_was_without_warpos(on, monkeypatch):
    on(warp_amiga(on_disk=False))
    monkeypatch.setattr(server, "_tasks", lambda: [])
    assert "PowerPC" not in server.amiga_tasks()
    assert server.amiga_ppc("tasks").startswith("WarpOS is not in memory")


class CrashScreen:
    def __init__(self):
        self.clicks = []

    def ui_tree(self):
        return [{"kind": "window", "id": "w1", "title": "Warp-OS - PowerPC Exception"},
                {"kind": "gadget", "window": "w1", "id": "0", "type": "sys", "label": "close",
                 "x": 2, "y": 22, "w": 16, "h": 10}]

    def click(self, x, y, button, double):
        self.clicks.append((x, y))


def crash_text():
    rows = [screentext.Row(0, 30 + i * 8, 600, 8, line) for i, line in enumerate(CRASH.splitlines())]
    return screentext.ScreenText(recording=True, windows=[
        screentext.Window("w1", 0, 20, 680, 500, "a", "Warp-OS - PowerPC Exception", rows)])


def test_software_failure_reads_and_closes_a_ppc_crash_window(monkeypatch):
    screen = CrashScreen()
    monkeypatch.setattr(server._session(), "screen", screen)
    monkeypatch.setattr(server, "_screen_text", crash_text)
    monkeypatch.setattr(server, "_namer", lambda: (_ for _ in ()).throw(AmigaError("no LOADED")))
    out = server.amiga_software_failure()
    assert "PowerPC crash window 'Warp-OS - PowerPC Exception'" in out and "NULL pointer" in out
    assert server.amiga_ppc("crash") == out and not screen.clicks
    done = server.amiga_software_failure("dismiss")
    assert screen.clicks == [(10, 27)] and "closed the crash window" in done


def test_run_explains_a_ppc_crash_window(on, monkeypatch):
    fake = on(warp_amiga(WARPOS))
    fake.answers["Work:hello"] = (20, "")
    titles = iter([["Shell"], ["Shell", "Warp-OS - PowerPC Exception"]])
    monkeypatch.setattr(server, "_window_titles", lambda: next(titles))
    monkeypatch.setattr(server, "_screen_text", crash_text)
    monkeypatch.setattr(server, "_namer", lambda: (_ for _ in ()).throw(AmigaError("no LOADED")))
    monkeypatch.setattr(server, "_fpu_check", lambda *a: ("", False))
    out = server.amiga_run("Work:hello")
    assert "Data access exception" in out and "amiga_software_failure('dismiss')" in out


# ---- WarpOS builds

def ehf(ppc_code: bytes = b"\x60\x00\x00\x00") -> bytes:
    """A WarpOS program: a 68k stub hunk, then a PowerPC code hunk."""
    out = struct.pack(">IIIII", hunks.HUNK_HEADER, 0, 2, 0, 1) + struct.pack(">II", 1, 1)
    out += struct.pack(">II", hunks.HUNK_CODE, 1) + bytes.fromhex("4e754e71") + struct.pack(">I", hunks.HUNK_END)
    out += struct.pack(">II", hunks.HUNK_PPC_CODE, 1) + ppc_code + struct.pack(">I", hunks.HUNK_END)
    return out


def test_ppc_code_hunks_are_seen_and_not_taken_for_68k_code():
    data = ehf()
    assert hunks.ppc_hunks(data) == 1
    assert [n for n, _ in hunks.code_hunks(data)] == [0]
    assert not hunks.fpu_use(data).uses_fpu


def test_build_script_has_a_warpos_target():
    script = project.files("hello")["build"]
    assert script.startswith(".KEY CPU/K,DEVPACK/K,FPU/K,TARGET/K") and ".DEF TARGET 68K" in script
    assert "VBCC:bin/vc +VBCC:config/warpos -c99 -O1 -o hello main.c -lamiga" in script
    assert "Assign vlibwos: VBCC:targets/ppc-warpos/lib" in script
    assert "If NOT EXISTS VBCC:config/warpos" in script and 'Echo "built hello for WarpOS"' in script
    # the 68k build is still what it was
    assert "VBCC:bin/vc +VBCC:config/aos68k -c99 -O1 -g -cpu=<CPU> -o hello main.c -lamiga" in script


@pytest.fixture
def jobs(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "amiga_job", lambda command, wait=0: sent.append(command) or "built calc for WarpOS\n")
    return sent


def test_build_for_warpos(on, jobs):
    fake = on(warp_amiga(WARPOS))
    fake.add("RAM:calc/build", project.files("calc")["build"].encode())
    out = server.amiga_build("RAM:calc", target="warpos")
    assert jobs[-1].endswith("Execute build TARGET WARPOS")
    assert out.startswith("built with PowerPC code for WarpOS") and "cannot run it" not in out


def test_build_for_warpos_on_an_amiga_without_it_says_so(on, jobs):
    fake = on(warp_amiga(on_disk=False))
    fake.add("RAM:calc/build", project.files("calc")["build"].encode())
    assert "cannot run it" in server.amiga_build("RAM:calc", target="WarpOS")


def test_build_for_warpos_refuses_what_does_not_fit(on, jobs):
    fake = on(warp_amiga(WARPOS))
    fake.add("RAM:old/build", b".KEY CPU/K,DEVPACK/K,FPU/K\nEcho hi\n")
    with pytest.raises(AmigaError, match="no WarpOS target"):
        server.amiga_build("RAM:old", target="warpos")
    with pytest.raises(AmigaError, match="68k builds"):
        server.amiga_build("RAM:old", target="warpos", fpu="auto")
    with pytest.raises(AmigaError, match="target"):
        server.amiga_build("RAM:old", target="powerup")
    assert not jobs


def test_run_warns_of_a_warpos_program_without_warpos(on, tmp_path):
    on(warp_amiga(on_disk=False))
    program = tmp_path / "hello"
    program.write_bytes(ehf())
    assert "WarpOS program" in server._ppc_program_note(program)
    plain = tmp_path / "plain"
    plain.write_bytes(b"not a program")
    assert server._ppc_program_note(plain) == ""
