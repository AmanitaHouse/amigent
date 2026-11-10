"""What is loaded on the Amiga, what an address belongs to, and 68k code in words.

amigentd 1.4.0 (protocol 6) lists libraries, devices and resources with version,
open count and base; the hunks of the programs that run; and the resident
modules (LOADED). It reads memory too, only RAM that exec manages and the
Kickstart ROM (PEEK). From that the PC names an address: a program's hunk and
offset, a library function (through its jump table), a resident module; and
disassembles code with the library function names of `jsr -n(a6)` calls.
"""

from __future__ import annotations

import json
import re
import struct
from dataclasses import dataclass, field
from importlib import resources

ROM = (0xF80000, 0x1000000)


@dataclass
class Library:
    kind: str  # L, D or R
    name: str
    version: int
    revision: int
    open_count: int
    base: int
    neg_size: int
    pos_size: int
    id_string: str = ""


@dataclass
class Hunk:
    task: str
    command: str
    number: int
    start: int
    size: int


@dataclass
class Resident:
    name: str
    version: int
    start: int
    end: int


@dataclass
class Loaded:
    libraries: list[Library] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)
    residents: list[Resident] = field(default_factory=list)


def parse(lines: list[str]) -> Loaded:
    out = Loaded()
    for line in lines:
        p = line.split("\t")
        try:
            if p[0] in ("L", "D", "R") and len(p) >= 8:
                out.libraries.append(Library(p[0], p[1], int(p[2]), int(p[3]), int(p[4]),
                                             int(p[5], 16), int(p[6]), int(p[7]),
                                             p[8].strip() if len(p) > 8 else ""))
            elif p[0] == "H" and len(p) >= 6:
                out.hunks.append(Hunk(p[1], p[2], int(p[3]), int(p[4], 16), int(p[5])))
            elif p[0] == "M" and len(p) >= 5:
                out.residents.append(Resident(p[1], int(p[2]), int(p[3], 16), int(p[4], 16)))
        except ValueError:
            continue
    return out


KINDS = {"L": "library", "D": "device", "R": "resource"}


def listing(loaded: Loaded, kind: str = "all", name: str = "") -> str:
    """A table for the agent: libraries, devices, resources, programs, residents."""
    want = name.lower()
    lines = []
    codes = {"all": "LDR", "libraries": "L", "devices": "D", "resources": "R"}.get(kind, "")
    if codes:
        for lib in sorted(loaded.libraries, key=lambda x: (x.kind, x.name.lower())):
            if lib.kind not in codes:
                continue
            if want and want not in lib.name.lower():
                continue
            ver = f"{lib.version}.{lib.revision}" if lib.version or lib.revision else "-"
            lines.append(f"{KINDS[lib.kind]:8} {lib.name:28} {ver:>8}  open {lib.open_count:<3} "
                         f"base {lib.base:08X}  {lib.id_string}".rstrip())
    if kind in ("all", "programs"):
        seen = {}
        for h in loaded.hunks:
            key = (h.task, h.command)
            seen.setdefault(key, []).append(h)
        for (task, command), hunks in seen.items():
            label = command or task
            if want and want not in label.lower() and want not in task.lower():
                continue
            total = sum(h.size for h in hunks)
            first = hunks[0].start
            lines.append(f"program  {label:28} {len(hunks):>3} hunks {total:>8} bytes  "
                         f"first at {first:08X}  task {task}")
    if kind in ("all", "residents"):
        for r in loaded.residents:
            if want and want not in r.name.lower():
                continue
            lines.append(f"resident {r.name:28} {r.version:>8}  {r.start:08X}-{r.end:08X}")
    return "\n".join(lines) or "nothing matches"


_LVO: dict | None = None


def lvo_tables() -> dict[str, dict[int, str]]:
    """Function names by negative offset for 76 libraries, devices and resources (NDK 3.9)."""
    global _LVO
    if _LVO is None:
        raw = json.loads(resources.files("amigent").joinpath("lvo.json").read_text())
        _LVO = {name: {int(k): v for k, v in table.items()} for name, table in raw.items()}
    return _LVO


def function(library: str, offset: int) -> str:
    """'Forbid' for exec.library and -132 (or 132)."""
    table = lvo_tables().get(library.lower()) or lvo_tables().get(library.lower() + ".library") or {}
    return table.get(abs(offset), "")


class Namer:
    """Names addresses from LOADED, reading jump tables through peek as needed."""

    def __init__(self, loaded: Loaded, peek=None):
        self.loaded = loaded
        self.peek = peek  # peek(address, size) -> bytes
        self._jumps: dict[str, list[tuple[int, int]]] = {}

    def jump_table(self, lib: Library) -> list[tuple[int, int]]:
        """(target, LVO) for each JMP in a library's jump table."""
        if lib.name in self._jumps:
            return self._jumps[lib.name]
        out = []
        if self.peek and 6 <= lib.neg_size <= 0x8000:
            try:
                data = self.peek(lib.base - lib.neg_size, lib.neg_size)
            except Exception:  # noqa: BLE001 - a name is a nicety
                data = b""
            for lvo in range(6, lib.neg_size + 1, 6):
                at = lib.neg_size - lvo
                if at + 6 <= len(data) and data[at:at + 2] == b"\x4e\xf9":
                    out.append((struct.unpack(">I", data[at + 2:at + 6])[0], lvo))
        self._jumps[lib.name] = out
        return out

    def name(self, address: int, search_functions: bool = True) -> str:
        a = address & 0xFFFFFFFF
        for h in self.loaded.hunks:
            if h.start <= a < h.start + h.size:
                who = h.command or h.task
                return f"{who} hunk {h.number} +${a - h.start:X}"
        for lib in self.loaded.libraries:
            if lib.base - lib.neg_size <= a < lib.base:
                lvo = lib.base - a
                fn = function(lib.name, (lvo + 5) // 6 * 6)
                return f"{lib.name} jump table, LVO -{(lvo + 5) // 6 * 6}" + (f" {fn}" if fn else "")
            if lib.base <= a < lib.base + max(lib.pos_size, 1):
                return f"{lib.name} base +${a - lib.base:X}"
        if search_functions:
            best = None
            for lib in self.loaded.libraries:
                for target, lvo in self.jump_table(lib):
                    if target <= a < target + 0x10000 and (best is None or target > best[0]):
                        best = (target, lvo, lib)
            if best:
                target, lvo, lib = best
                fn = function(lib.name, lvo) or f"LVO -{lvo}"
                return f"{lib.name} {fn} +${a - target:X}"
        inside = [r for r in self.loaded.residents if r.start <= a < r.end]
        if inside:
            r = max(inside, key=lambda r: r.start)
            return f"{r.name} (resident) +${a - r.start:X}"
        if ROM[0] <= a < ROM[1]:
            before = [r for r in self.loaded.residents if ROM[0] <= r.start <= a]
            if before:
                r = max(before, key=lambda r: r.start)
                return f"Kickstart ROM, after {r.name} +${a - r.start:X}?"
            return "Kickstart ROM"
        return ""


def hexdump(data: bytes, address: int) -> str:
    lines = []
    for at in range(0, len(data), 16):
        chunk = data[at:at + 16]
        hexes = " ".join(chunk[i:i + 4].hex() for i in range(0, len(chunk), 4))
        text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{address + at:08X}  {hexes:<35}  {text}")
    return "\n".join(lines)


_A6_CALL = re.compile(r"^-?(\$?[0-9a-fx]+)\(a6\)$", re.I)


def _offset(text: str) -> int | None:
    m = _A6_CALL.match(text.replace(" ", ""))
    if not m:
        return None
    v = m.group(1).lstrip("$")
    try:
        n = int(v, 16) if v.startswith(("0x", "0X")) or m.group(1).startswith("$") else int(v)
    except ValueError:
        return None
    return n


def disassemble(data: bytes, address: int, a6: str = "", namer: Namer | None = None,
                cpu: str = "68040") -> str:
    """68k code with capstone; `jsr -n(a6)` named for the library a6 holds.

    a6 names that library ('dos' or 'dos.library'); without it, 'movea.l 4.w,a6'
    in the code switches to exec, and calls show the likely names of the
    common libraries.
    """
    try:
        import capstone
    except ImportError:
        return ("(no disassembler: pip install capstone)\n" + hexdump(data, address))
    modes = {"68000": capstone.CS_MODE_M68K_000, "68010": capstone.CS_MODE_M68K_010,
             "68020": capstone.CS_MODE_M68K_020, "68030": capstone.CS_MODE_M68K_030,
             "68040": capstone.CS_MODE_M68K_040, "68060": capstone.CS_MODE_M68K_060}
    md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | modes.get(cpu, modes["68040"]))
    base_lib = a6.lower() if a6 else ""
    if base_lib and not base_lib.endswith((".library", ".device", ".resource")):
        base_lib += ".library"
    lines = []
    pos = 0
    while pos < len(data):
        for ins in md.disasm(data[pos:], address + pos):
            comment = ""
            ops = ins.op_str.lower()
            if ins.mnemonic in ("movea.l", "move.l") and ops.replace(" ", "") in ("$4.w,a6", "($4).w,a6", "$4,a6"):
                base_lib = "exec.library"
                comment = "a6 = SysBase"
            elif re.search(r",\s*a6$", ops):
                base_lib = ""  # some other library base now; calls get the likely names
            if ins.mnemonic in ("jsr", "jmp") and "(a6)" in ops:
                off = _offset(ops)
                if off is not None:
                    if base_lib:
                        fn = function(base_lib, off)
                        comment = f"{base_lib.split('.')[0]} {fn}" if fn else f"{base_lib} LVO -{off}"
                    else:
                        guess = [f"{lib.split('.')[0]} {lvo_tables()[lib][abs(off)]}"
                                 for lib in ("exec.library", "dos.library", "intuition.library",
                                             "graphics.library")
                                 if abs(off) in lvo_tables().get(lib, {})]
                        comment = "LVO -%d: %s" % (abs(off), ", ".join(guess)) if guess else ""
            elif namer and ins.mnemonic in ("jsr", "jmp", "bsr", "bsr.w", "bsr.l", "bra", "bra.w"):
                m = re.search(r"\$([0-9a-f]{4,8})", ops)
                if m:
                    where = namer.name(int(m.group(1), 16), search_functions=False)
                    if where:
                        comment = where
            hexes = ins.bytes.hex()
            lines.append(f"{ins.address:08X}  {hexes:<20} {ins.mnemonic:9} {ins.op_str}"
                         + (f"   ; {comment}" if comment else ""))
            pos = ins.address - address + ins.size
        if pos < len(data):
            word = data[pos:pos + 2]
            lines.append(f"{address + pos:08X}  {word.hex():<20} dc.w      ${word.hex()}")
            pos += 2
    return "\n".join(lines)


def resolve(text: str, namer: Namer) -> int:
    """'$0A12B4C0', '0x...', '12345', 'dos.library' (its base) or 'dos.library/Write'
    (where Write's code starts, from the jump table)."""
    t = text.strip()
    if "/" in t:
        lib_name, fn = t.split("/", 1)
        lib = _find_lib(namer.loaded, lib_name)
        want = fn.strip().lower()
        table = lvo_tables().get(lib.name.lower(), {})
        lvo = next((o for o, n in table.items() if n.lower() == want), None)
        if lvo is None:
            raise ValueError(f"{lib.name} has no function {fn} in the NDK 3.9 tables")
        for target, at in namer.jump_table(lib):
            if at == lvo:
                return target
        raise ValueError(f"{lib.name}'s jump table could not be read at LVO -{lvo}")
    if re.fullmatch(r"[A-Za-z][\w.-]*\.(library|device|resource)", t):
        return _find_lib(namer.loaded, t).base
    if t.startswith("$"):
        return int(t[1:], 16)
    if t.lower().startswith("0x"):
        return int(t, 16)
    if re.fullmatch(r"[0-9a-fA-F]{6,8}", t):  # 00F80000 is an address, not a number
        return int(t, 16)
    return int(t) if t.isdigit() else int(t, 16)


def _find_lib(loaded: Loaded, name: str) -> Library:
    n = name.strip().lower()
    for lib in loaded.libraries:
        if lib.name.lower() in (n, n + ".library"):
            return lib
    raise ValueError(f"{name} is not loaded")
