"""PowerPC boards on a 68k Amiga: the card, the kernel, the flash ROM, PPC tasks and crashes.

A CyberStorm PPC or Blizzard PPC carries a PowerPC next to a 68040 or 68060.
Two kernels drive it and cannot run side by side: PowerUP (ppc.library, from
phase5) and WarpOS (powerpc.library, from Haage & Partner). Bridges exist both
ways: ppclibemu gives a ppc.library on top of WarpOS, and powerpc.library V7
gives the WarpOS calls on top of PowerUP.

Everything here only reads. The card comes from expansion.library's board
list (read with PEEK), the kernel from exec's library list (LOADED), the
versions on disk from Version FILE, which does not open a library. WarpOS's
own tools showinfo and stat are run only while powerpc.library is in memory
already, so nothing gets loaded that was not active before. The flash ROM is
never written.

None of this has been tried on a real board yet. Product numbers follow
Linux's list of Zorro IDs; the text of the WarpOS crash window follows
powerpc.library 15; tool output follows WarpOS 4.0's showinfo and stat.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from . import amigus

PHASE5 = 8512
# phase5's products that carry a PowerPC, or share the number of one
PPC_PRODUCTS = {100: "CyberStorm PPC or CyberStorm MK III", 110: "Blizzard PPC"}
OTHER_PRODUCTS = {25: "CyberStorm MK II", 24: "Blizzard 2060", 17: "Blizzard 1230-IV/1260"}

WARPOS_LIB = "powerpc.library"
POWERUP_LIB = "ppc.library"
WARPOS_COMPAT = 7  # powerpc.library V7: the WarpOS calls on top of PowerUP

# The SCSI driver of the flash ROM names its version; a board without SCSI may not have one.
ROM_DEVICES = ("cybppc", "cyberppc", "blizzppc", "cybscsi")
# The last update phase5 put on Aminet (driver/other/Flash-300399), as versions to compare against.
LAST_FLASH = {"cyb": (44, 67), "bliz": (44, 30)}

# Patches and fixes from Aminet that explain many quirks when they run at boot
PATCHES = {
    "bk_remppclib": "a BlizKick module that keeps the ppc.library of the Blizzard PPC's flash ROM out",
    "bppcfixfix": "makes 68040/68060.library and ppc.library loadable from disk on a Blizzard PPC "
                  "after BPPCFix",
    "bppcfix": "keeps the libraries of the Blizzard PPC's flash ROM (ppc.library, 68040/68060.library) "
               "from starting",
    "initppclib": "brings the ppc.library of a Blizzard PPC back after it was kept out",
    "csppc233fix": "works around a CyberStorm PPC 233 MHz fault that sets bits of the LR register",
    "ppclibemu": "the ppc.library emulation on top of WarpOS",
}
STARTUP_FILES = ("S:Startup-Sequence", "S:User-Startup")


@dataclass
class Board:
    manufacturer: int
    product: int
    address: int
    size: int

    @property
    def name(self) -> str:
        if self.manufacturer != PHASE5:
            return f"manufacturer {self.manufacturer} product {self.product}"
        return PPC_PRODUCTS.get(self.product) or OTHER_PRODUCTS.get(self.product) \
            or f"phase5 product {self.product}"

    @property
    def ppc(self) -> bool:
        return self.manufacturer == PHASE5 and self.product in PPC_PRODUCTS


def boards(peek, expansion: int) -> list[Board] | None:
    """Every board in expansion.library's list; None if the list cannot be read."""
    try:
        nodes = amigus._list(peek, expansion + amigus.BOARD_LIST)
        if nodes is None:
            return None
        out = []
        for node in nodes:
            cd = peek(node, 40)
            out.append(Board(struct.unpack_from(">H", cd, 20)[0], cd[17],
                             struct.unpack_from(">I", cd, 32)[0], struct.unpack_from(">I", cd, 36)[0]))
        return out
    except amigus.READ_ERRORS:
        return None


def _find(libraries, name: str, kind: str = "L"):
    return next((lib for lib in libraries if lib.kind == kind and lib.name.lower() == name), None)


@dataclass
class Kernel:
    """Which PPC kernel runs, from exec's library list."""
    warpos: object = None   # memory.Library of powerpc.library, when in memory
    powerup: object = None  # memory.Library of ppc.library, when in memory

    @property
    def ppclibemu(self) -> bool:
        """ppc.library is Frank Wille's emulation on top of WarpOS."""
        return bool(self.powerup and "emulation" in self.powerup.id_string.lower())

    @property
    def warpos_compat(self) -> bool:
        """powerpc.library V7, which gives the WarpOS calls on top of PowerUP."""
        return bool(self.warpos and self.warpos.version == WARPOS_COMPAT)

    @property
    def active(self) -> str:
        """'WarpOS', 'PowerUP', 'both' (a conflict) or ''."""
        wos = bool(self.warpos) and not self.warpos_compat
        pup = bool(self.powerup) and not self.ppclibemu
        if wos and pup:
            return "both"
        if wos or self.ppclibemu:
            return "WarpOS"
        if pup or self.warpos_compat:
            return "PowerUP"
        return ""

    def lines(self) -> list[str]:
        out = []
        for lib, what in ((self.warpos, "WarpOS"), (self.powerup, "PowerUP")):
            if not lib:
                continue
            note = ""
            if lib is self.warpos and self.warpos_compat:
                note = " (V7: the WarpOS calls on top of PowerUP, not WarpOS itself)"
            elif lib is self.powerup and self.ppclibemu:
                note = " (ppclibemu: PowerUP programs on top of WarpOS)"
            out.append(f"  {what} {lib.name} {lib.version}.{lib.revision} in memory, open "
                       f"{lib.open_count}{note}" + (f": {lib.id_string}" if lib.id_string else ""))
        return out


def kernel(libraries) -> Kernel:
    return Kernel(_find(libraries, WARPOS_LIB), _find(libraries, POWERUP_LIB))


def _version(text: str) -> tuple[int, int] | None:
    m = re.search(r"\b(\d+)\.(\d+)\b", text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def rom_device(libraries, residents) -> tuple[str, tuple[int, int]] | None:
    """The flash ROM's SCSI driver and its version, from devices or resident modules."""
    for lib in libraries:
        if lib.kind == "D" and lib.name.lower().startswith(ROM_DEVICES):
            return lib.name, (lib.version, lib.revision)
    for res in residents:
        if res.name.lower().startswith(ROM_DEVICES):
            return res.name, (res.version, 0)
    return None


def rom_note(name: str, version: tuple[int, int]) -> str:
    key = "bliz" if name.lower().startswith("blizz") else "cyb"
    last = LAST_FLASH[key]
    if version[0] == last[0] and version[1] and version < last:
        return (f"older than {last[0]}.{last[1]}, the last update phase5 put on Aminet "
                "(driver/other/Flash-300399); compare before blaming a program")
    return ""


def patches(texts: dict[str, str]) -> list[str]:
    """Lines of the startup scripts that run a known PPC patch, with what it does."""
    out = []
    for path, text in texts.items():
        for number, line in enumerate(text.splitlines(), 1):
            code = line.split(";", 1)[0].strip()
            low = code.lower()
            for name, what in PATCHES.items():
                if re.search(rf"\b{name}", low):
                    out.append(f"{path} line {number}: {code} ({what})")
                    break
    return out


def conflicts(kern: Kernel, residents, cpu: str, libraries, on_disk: str = "") -> list[str]:
    """Combinations known not to work, or that explain odd behaviour."""
    out = []
    if kern.active == "both":
        out.append("ppc.library (PowerUP) and powerpc.library (WarpOS) are both in memory: the two "
                   "kernels cannot share the PowerPC. Boot with one of them only, or use "
                   "ppclibemu for PowerUP programs under WarpOS")
    rom_ppc = any(r.name.lower() == POWERUP_LIB for r in residents)
    if rom_ppc and (kern.active == "WarpOS" or "WarpOS" in on_disk):
        out.append("ppc.library is a resident module (the Blizzard PPC's flash ROM starts it): "
                   "WarpOS cannot work beside it. BPPCFix or BK_RemPPCLib in the "
                   "Startup-Sequence, or ENV:powerpc/Terminator, keep it out")
    names = {lib.name.lower(): lib for lib in libraries if lib.kind == "L"}
    if cpu.endswith("060") and "68060.library" not in names:
        out.append("68040.library is loaded on a 68060: it needs 68060.library instead"
                   if "68040.library" in names else
                   "the 68060 runs without 68060.library, which emulates the instructions the "
                   "chip does not have")
    if cpu.endswith("040") and "68060.library" in names and "68040.library" not in names:
        out.append("68060.library is loaded on a 68040: it needs 68040.library instead")
    return out


@dataclass
class Info:
    """What WarpOS's showinfo prints."""
    cpu: str = ""
    pvr: str = ""
    clock: str = ""
    bus: str = ""
    load: str = ""
    system_load: str = ""

    def line(self) -> str:
        if not self.cpu:
            return ""
        text = self.cpu + (f" (PVR {self.pvr})" if self.pvr else "")
        if self.clock and not re.fullmatch(r"0(?:\.0+)? MHz", self.clock):
            text += f", {self.clock}"
        if self.bus:
            text += f", bus {self.bus}"
        if self.load:
            text += f", CPU load {self.load}"
        return text


def _mhz(text: str) -> str:
    m = re.match(r"(\d+)(?:\.(\d+))?\s*MHz", text.strip())
    if not m:
        return text.strip()
    whole, frac = m.group(1), (m.group(2) or "").rstrip("0")
    return f"{whole}{'.' + frac[:3] if frac else ''} MHz"


def parse_showinfo(text: str) -> Info:
    info = Info()
    for line in text.splitlines():
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "cpu":
            m = re.match(r"(.*?)\s*\(PVR\s*=\s*([0-9A-Fa-f]+)\)", value)
            info.cpu, info.pvr = (m.group(1).strip(), m.group(2)) if m else (value, "")
        elif key == "cpu clock":
            info.clock = _mhz(value)
        elif key == "bus clock":
            info.bus = _mhz(value)
        elif key == "cpu load":
            info.load = value
        elif key == "system load":
            info.system_load = value
    return info


@dataclass
class PPCTask:
    name: str
    id: int
    nice: int
    cpu: float
    busy: float
    activity: float


STAT_ROW = re.compile(r"^(?P<name>.*?\S)\s+(?P<id>\d+)\s+(?P<nice>-?\d+)\s+(?P<cpu>\d+(?:\.\d+)?)\s*%?"
                      r"\s+(?P<busy>\d+(?:\.\d+)?)\s*%?\s+(?P<act>\d+(?:\.\d+)?)\s*%?\s*$")


def parse_stat(text: str) -> tuple[list[PPCTask], dict[str, str]]:
    """The PPC tasks of WarpOS's stat with their load, and the CPU and system load."""
    tasks, totals, table = [], {}, False
    for line in text.splitlines():
        if line.strip().lower().startswith("task name"):
            table = True
            continue
        m = re.match(r"\s*(CPU load|System load):\s*([\d.]+\s*%)", line)
        if m:
            totals[m.group(1)] = m.group(2).replace(" ", "")
            continue
        if table and (row := STAT_ROW.match(line.rstrip())):
            tasks.append(PPCTask(row["name"].strip(), int(row["id"]), int(row["nice"]),
                                 float(row["cpu"]), float(row["busy"]), float(row["act"])))
    return tasks, totals


def stat_ok(text: str) -> bool:
    return "task name" in text.lower() and "cpuusage" in text.lower().replace(" ", "")


def task_table(tasks: list[PPCTask], totals: dict[str, str], name: str = "") -> str:
    want = name.lower()
    rows = [t for t in tasks if not want or want in t.name.lower()]
    lines = [f"PowerPC tasks (WarpOS stat){': ' + ', '.join(f'{k} {v}' for k, v in totals.items()) if totals else ''}"]
    if not rows:
        lines.append("  none" + (f" matching {name!r}" if want else ""))
    for t in rows:
        lines.append(f"  {t.name:24} id {t.id:<5} nice {t.nice:<3} CPU {t.cpu:5.1f}%  "
                     f"busy {t.busy:5.1f}%  activity {t.activity:5.1f}%")
    return "\n".join(lines)


# ---- the crash window

WARPOS_EXCEPTION = "powerpc exception"  # 'Warp-OS - PowerPC Exception', the CON: window of crashfile
CRASH_WORDS = ("powerpc exception", "ppc exception", "ppc crash", "powerpc crash", "warp-os - powerpc",
               "warpos - powerpc")

EXCEPTIONS = {
    "data access exception": "the program read or wrote memory nothing answers at: DAR holds the "
                             "address (0 or a few bytes above it is a NULL pointer)",
    "instruction access exception": "the PowerPC jumped to an address with no code: SRR0 is where "
                                    "it tried to run (a bad function pointer or a stack overwritten)",
    "alignment exception": "a floating point or string access at an address not aligned for it "
                           "(DAR); WarpOS emulates most of these, so this one was not",
    "program exception": "an illegal or privileged instruction, or a trap: the program ran into "
                         "data, or uses an instruction this PowerPC lacks",
    "floating point unavailable": "an FPU instruction while the FPU was switched off for the task",
    "floating point": "a floating point error the program asked to be told about (FPSCR)",
    "machine check": "the hardware answered with an error: a bus or memory problem on the board, "
                     "more likely than a program bug",
    "breakpoint": "an instruction or data breakpoint, such as from WarpOS's throw or a debugger",
    "parity error": "a cache or bus parity error: hardware",
    "trap": "a trap instruction, often an assert in the program",
}

# Bits 0 and 2 of LR in PowerPC numbering (the top ones), set by the CSPPC 233 MHz fault
LR_BUG_BITS = 0xA0000000

REGISTER = re.compile(r"\b(SRR0|SRR1|MSR|HID0|PVR|DAR|DSISR|SDR1|DEC|TBU|TBL|XER|CR|FPSCR|LR|CTR)"
                      r":\s*([0-9A-Fa-f]{8})\b")
GPRS = re.compile(r"\bR(\d+)-R(\d+):\s*((?:[0-9A-Fa-f]{8}\s*){4})")
TASK = re.compile(r"Task name:\s*'([^']*)'\s*Task address:\s*([0-9A-Fa-f]{8})(?:\s*Task ID:\s*(\d+))?")
SEGMENT = re.compile(r'([0-9A-Fa-f]{8})\s*:\s*"([^"]*)"\s*Hunk\s*(\d+)\s*Offset\s*([0-9A-Fa-f]{8})')


@dataclass
class Crash:
    kind: str = ""       # 'WarpOS' or 'PowerUP' or ''
    cpu: str = ""
    exception: str = ""
    access: str = ""     # 'Access to 00000000' and the like
    task: str = ""
    task_address: str = ""
    task_id: str = ""
    registers: dict[str, str] = field(default_factory=dict)
    segments: list[str] = field(default_factory=list)

    def explain(self) -> str:
        low = self.exception.lower()
        why = next((v for k, v in EXCEPTIONS.items() if k in low), "")
        return why


def is_crash_window(title: str, text: str) -> bool:
    words = (title + "\n" + text).lower()
    if any(w in words for w in CRASH_WORDS):
        return True
    return bool(re.search(r"\bsrr0\b", words) and re.search(r"\bdsisr\b|\bsrr1\b", words))


def parse_crash(title: str, text: str) -> Crash:
    crash = Crash()
    joined = title + "\n" + text
    crash.kind = "WarpOS" if re.search(r"warp-?os", joined, re.I) else \
        ("PowerUP" if re.search(r"ppc\.library|powerup", joined, re.I) else "")
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        m = re.match(r"PowerPC\s+(\S.*)$", s)
        if m and not crash.cpu and "exception" not in s.lower():
            crash.cpu = m.group(1).strip()
            continue
        if not crash.exception and re.search(r"exception|illegal instruction|privileged instruction|"
                                             r"\btrap\b|page fault|protection violation|zero divide", s, re.I) \
                and not REGISTER.search(s):
            crash.exception = s
            continue
        if re.match(r"(?:Access to|.*- Access to)\s", s) or s.lower().startswith("the excepting instruction"):
            crash.access = (crash.access + "; " if crash.access else "") + s
    m = TASK.search(text)
    if m:
        crash.task, crash.task_address, crash.task_id = m.group(1), m.group(2), m.group(3) or ""
    for name, value in REGISTER.findall(text):
        crash.registers.setdefault(name, value.upper())
    for m in GPRS.finditer(text):
        first = int(m.group(1))
        for i, value in enumerate(m.group(3).split()):
            crash.registers[f"r{first + i}"] = value.upper()
    crash.segments = [f'{a.upper()}: "{n}" hunk {h} +${int(o, 16):X}' for a, n, h, o in SEGMENT.findall(text)]
    return crash


def describe_crash(crash: Crash, namer=None) -> list[str]:
    """The crash in words, for amiga_software_failure and amiga_run."""
    kernel_name = crash.kind or "PowerPC kernel"
    out = [f"{kernel_name} crash" + (f" on a {crash.cpu}" if crash.cpu else "")
           + (f": {crash.exception}" if crash.exception else "")]
    why = crash.explain()
    if why:
        out.append("meaning: " + why)
    if crash.access:
        out.append(crash.access)
    if crash.task:
        out.append(f"task {crash.task!r} at {crash.task_address}"
                   + (f", WarpOS task ID {crash.task_id}" if crash.task_id else ""))
    regs = crash.registers
    for reg, what in (("SRR0", "the instruction that failed"), ("LR", "the return address (the caller)"),
                      ("DAR", "the data address it accessed")):
        if reg not in regs:
            continue
        line = f"{reg} {regs[reg]}: {what}"
        if namer is not None and reg != "DAR":
            try:
                name = namer(int(regs[reg], 16))
            except Exception:  # noqa: BLE001 - naming is a bonus
                name = ""
            if name:
                line += f", {name}"
        out.append(line)
    if "r1" in regs:
        out.append(f"r1 {regs['r1']}: the stack pointer; Aminet dev/debug/checkstack walks the stack "
                   f"from it (checkpo {regs['r1']} 10 for vbcc and StormC programs)")
    if "instruction access" in crash.exception.lower() and "LR" in regs \
            and int(regs["LR"], 16) & LR_BUG_BITS:
        out.append("LR starts with a digit other than 0: on a CyberStorm PPC with a 233 MHz "
                   "PowerPC that is a known hardware fault, which Aminet driver/other/CSPPC233Fix "
                   "works around")
    if crash.segments:
        out.append("segments (SegTracker): " + "; ".join(crash.segments))
    if crash.kind == "WarpOS" and crash.task_id:
        out.append(f"the task stays crashed: WarpOS's killppc {crash.task_id} removes it "
                   "(never the mirror task of a Shell that still works on the 68k side)")
    return out


# ---- WarpOS's own tools, run only while powerpc.library is in memory

def tool_path(run, name: str, folder: str = "") -> str:
    """Where WarpOS's tool name is: in folder when given, else along the Shell's path; '' if not found."""
    if folder:
        return folder.rstrip("/") + ("" if folder.endswith(":") else "/") + name
    rc, out = run(f"Which {name}")
    line = out.strip().splitlines()[-1].strip() if out.strip() else ""
    return line if rc == 0 and ":" in line else ""


def run_tool(run, name: str, folder: str = "") -> str:
    """The output of a WarpOS tool, or '' when it is not there or failed."""
    path = tool_path(run, name, folder)
    if not path:
        return ""
    rc, out = run(f'"{path}"')
    return out if rc == 0 else ""


def warpos_running(kern: Kernel) -> bool:
    """WarpOS itself is in memory, so its tools open nothing new."""
    return bool(kern.warpos) and not kern.warpos_compat


def ppc_tasks(run, kern: Kernel, folder: str = "", name: str = "") -> str:
    """The PPC tasks with their load from WarpOS's stat, or why not; '' without WarpOS."""
    if not warpos_running(kern):
        return ""
    out = run_tool(run, "stat", folder)
    if not stat_ok(out):
        return ("PowerPC tasks: WarpOS runs, but its tool stat was not found along the path "
                "(amiga_ppc(tools=folder) names its folder)")
    tasks, totals = parse_stat(out)
    return task_table(tasks, totals, name)


# ---- amiga_ppc

def status(loaded, peek, run, read_text, processor: str = "", on_disk: str = "", folder: str = "") -> str:
    """What amiga_ppc says: the card, the 68k CPU beside it, the kernel, the flash ROM, problems.

    loaded is memory.Loaded, peek(address, size) reads memory, run(command)
    gives (rc, output), read_text(path) a file's text or None. processor is
    the 68k CPU as amiga_status says it, on_disk the PPC libraries in LIBS:.
    """
    libs, residents = loaded.libraries, loaded.residents
    expansion = _find(libs, "expansion.library")
    found = boards(peek, expansion.base) if expansion else None
    kern = kernel(libs)
    active = kern.active
    ppc_boards = [b for b in found or [] if b.ppc]
    if not ppc_boards and not active and not on_disk:
        return ("No PowerPC board found: no CyberStorm PPC or Blizzard PPC in expansion.library's "
                "list, and neither powerpc.library nor ppc.library in memory or in LIBS:."
                + ("" if found is not None else " (The board list could not be read.)"))
    lines = []
    for b in ppc_boards:
        lines.append(f"Board: {b.name} (phase5, product {b.product}) at ${b.address:08X}")
    if not ppc_boards:
        if found is None:
            lines.append("Board: expansion.library's board list could not be read")
        else:
            phase5 = [b for b in found if b.manufacturer == PHASE5]
            lines.append("Board: no PowerPC card in expansion.library's list"
                         + (" (phase5: " + ", ".join(b.name for b in phase5) + ")" if phase5 else ""))
    cpu = re.search(r"68(?:EC|LC)?0[46]0", processor or "")
    if processor:
        lines.append(f"68k CPU: {processor}")
    rom = rom_device(libs, residents)
    if rom:
        note = rom_note(*rom)
        lines.append(f"Flash ROM: {rom[0]} {rom[1][0]}.{rom[1][1]}" + (f" ({note})" if note else ""))
    elif ppc_boards:
        lines.append("Flash ROM: its version is not known (no cybppc.device or blizzppc.device in "
                     "memory; a board without SCSI may not have one)")
    lines.append("Kernel: " + {"WarpOS": "WarpOS", "PowerUP": "PowerUP", "both": "WarpOS and PowerUP at once",
                               "": "none in memory"}[active])
    lines += kern.lines()
    if on_disk:
        lines.append(f"  in LIBS: {on_disk}")
    if any(r.name.lower() == POWERUP_LIB for r in residents):
        lines.append("  ppc.library is also a resident module (from the flash ROM)")
    if warpos_running(kern):
        info = parse_showinfo(run_tool(run, "showinfo", folder))
        lines.append("PowerPC: " + (info.line() + " (WarpOS showinfo)" if info.cpu else
                                    "WarpOS's showinfo was not found or said nothing; it tells the "
                                    "PowerPC and its clock"))
    elif active == "PowerUP":
        lines.append("PowerPC: not asked (Amigent reads no PowerUP tool yet)")
    for lib in libs:
        if lib.kind == "L" and lib.name.lower() in ("68040.library", "68060.library"):
            lines.append(f"68k support: {lib.name} {lib.version}.{lib.revision} in memory"
                         + (f": {lib.id_string}" if lib.id_string else ""))
    texts = {path: text for path in STARTUP_FILES if (text := read_text(path))}
    seen = patches(texts)
    if seen:
        lines.append("Patches at boot:")
        lines += [f"  {p}" for p in seen]
    if warpos_running(kern) or "WarpOS" in on_disk:
        crashfile = (read_text("ENV:PowerPC/crashfile") or "").strip()
        if crashfile.startswith(";"):
            lines.append("WarpOS crash output: off (ENV:PowerPC/crashfile starts with ';'), so a PPC "
                         "crash shows only on the serial port (Sushi); without the ';' it opens a window")
        elif crashfile:
            lines.append(f"WarpOS crash output: {crashfile}")
    problems = conflicts(kern, residents, cpu.group(0) if cpu else "", libs, on_disk)
    if problems:
        lines.append("Known problems:")
        lines += [f"- {p}" for p in problems]
    lines.append("(read only: nothing was opened or loaded; not tried on a real PowerPC board yet)")
    return "\n".join(lines)
