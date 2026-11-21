"""The code of an Amiga executable, and whether it uses FPU instructions.

An AmigaOS program is a hunk file: HUNK_HEADER, then CODE, DATA and BSS hunks
with their relocations and symbols. fpu_use() walks the code hunks word by
word and counts the instructions of coprocessor 1, the FPU (F-line words
$F200 to $F3FF). A word only counts when what follows it is a valid FPU
instruction, so stray data rarely gets in, but this is a heuristic: a code
hunk may hold data, and a program may test for an FPU first and only use
these instructions when it finds one.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

HUNK_UNIT, HUNK_NAME, HUNK_CODE, HUNK_DATA, HUNK_BSS = 0x3E7, 0x3E8, 0x3E9, 0x3EA, 0x3EB
HUNK_RELOC32, HUNK_RELOC16, HUNK_RELOC8, HUNK_EXT, HUNK_SYMBOL = 0x3EC, 0x3ED, 0x3EE, 0x3EF, 0x3F0
HUNK_DEBUG, HUNK_END, HUNK_HEADER = 0x3F1, 0x3F2, 0x3F3
HUNK_DREL32, HUNK_DREL16, HUNK_DREL8, HUNK_RELOC32SHORT = 0x3F7, 0x3F8, 0x3F9, 0x3FC
HUNK_PPC_CODE = 0x4E9  # PowerPC code in a WarpOS program (EHF, extended hunk format)

# FPU operations (cpGEN opmode, the low 7 bits of the command word)
OPS = {
    0x00: "fmove", 0x01: "fint", 0x02: "fsinh", 0x03: "fintrz", 0x04: "fsqrt", 0x06: "flognp1",
    0x08: "fetoxm1", 0x09: "ftanh", 0x0A: "fatan", 0x0C: "fasin", 0x0D: "fatanh", 0x0E: "fsin",
    0x0F: "ftan", 0x10: "fetox", 0x11: "ftwotox", 0x12: "ftentox", 0x14: "flogn", 0x15: "flog10",
    0x16: "flog2", 0x18: "fabs", 0x19: "fcosh", 0x1A: "fneg", 0x1C: "facos", 0x1D: "fcos",
    0x1E: "fgetexp", 0x1F: "fgetman", 0x20: "fdiv", 0x21: "fmod", 0x22: "fadd", 0x23: "fmul",
    0x24: "fsgldiv", 0x25: "frem", 0x26: "fscale", 0x27: "fsglmul", 0x28: "fsub",
    **{0x30 + i: "fsincos" for i in range(8)}, 0x38: "fcmp", 0x3A: "ftst",
    0x40: "fsmove", 0x41: "fssqrt", 0x44: "fdmove", 0x45: "fdsqrt", 0x58: "fsabs", 0x5A: "fsneg",
    0x5C: "fdabs", 0x5E: "fdneg", 0x60: "fsdiv", 0x62: "fsadd", 0x63: "fsmul", 0x64: "fddiv",
    0x66: "fdadd", 0x67: "fdmul", 0x68: "fssub", 0x6C: "fdsub",
}
# What the 68040's FPU does not do itself: 68040.library (FPSP) emulates it. The
# 68060 has FINT and FINTRZ, the rest needs 68060.library there too.
EMULATED = {"fint", "fintrz", "fsinh", "flognp1", "fetoxm1", "ftanh", "fatan", "fasin", "fatanh",
            "fsin", "ftan", "fetox", "ftwotox", "ftentox", "flogn", "flog10", "flog2", "fcosh",
            "facos", "fcos", "fgetexp", "fgetman", "fmod", "frem", "fscale", "fsgldiv",
            "fsglmul", "fsincos", "fmovecr"}


@dataclass
class FpuUse:
    instructions: int = 0
    emulated: int = 0  # of those, ones a 68040/060 needs its library for
    code_bytes: int = 0
    first: list[str] = field(default_factory=list)  # 'hunk 0 +$1A2 fmul'

    @property
    def uses_fpu(self) -> bool:
        return self.instructions > 0

    def describe(self) -> str:
        if not self.code_bytes:
            return "no code hunks found"
        if not self.instructions:
            return f"no FPU instructions found in {self.code_bytes} bytes of code"
        text = (f"uses FPU instructions: about {self.instructions} in {self.code_bytes} bytes of "
                f"code, such as {', '.join(self.first)}")
        if self.emulated:
            text += (f"; {self.emulated} of them a 68040/060 only runs with 68040.library or "
                     "68060.library")
        return text + " (a heuristic: a program may test for an FPU before it uses them)"


class NotAProgram(ValueError):
    pass


def code_hunks(data: bytes, ppc: list | None = None) -> list[tuple[int, bytes]]:
    """(hunk number, bytes) of each 68k code hunk of a loadable hunk file.

    ppc, when given, collects the numbers of PowerPC code hunks (WarpOS programs).
    """
    pos = 0

    def long() -> int:
        nonlocal pos
        if pos + 4 > len(data):
            raise NotAProgram("the file ends inside a hunk")
        value = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        return value

    if long() != HUNK_HEADER:
        raise NotAProgram("not an Amiga program (no HUNK_HEADER)")
    while (n := long()):  # resident library names, unused in programs
        pos += 4 * n
    long()  # table size
    first, last = long(), long()
    if last < first or last - first > 4096:
        raise NotAProgram("a hunk table that makes no sense")
    for _ in range(last - first + 1):
        if long() & 0xC0000000 == 0xC0000000:
            long()
    out, number = [], first
    while pos < len(data):
        kind = long() & 0x3FFFFFFF
        if kind in (HUNK_CODE, HUNK_DATA, HUNK_PPC_CODE):
            size = long()
            if size & 0xC0000000 == 0xC0000000:
                long()
            size = 4 * (size & 0x3FFFFFFF)
            if pos + size > len(data):
                raise NotAProgram("a hunk is longer than the file")
            if kind == HUNK_CODE:
                out.append((number, data[pos:pos + size]))
            elif kind == HUNK_PPC_CODE and ppc is not None:
                ppc.append(number)
            pos += size
        elif kind == HUNK_BSS:
            if long() & 0xC0000000 == 0xC0000000:
                long()
        elif kind in (HUNK_RELOC32, HUNK_RELOC16, HUNK_RELOC8, HUNK_DREL16, HUNK_DREL8):
            while (n := long()):
                pos += 4 * (n + 1)
        elif kind in (HUNK_RELOC32SHORT, HUNK_DREL32):  # in a program, DREL32 is the short form (V37 LoadSeg)
            while True:
                if pos + 2 > len(data):
                    raise NotAProgram("the file ends inside a relocation")
                n = struct.unpack_from(">H", data, pos)[0]
                pos += 2
                if not n:
                    break
                pos += 2 * (n + 1)
            pos += pos & 2  # back to a long
        elif kind == HUNK_SYMBOL:
            while (n := long()):
                pos += 4 * (n & 0xFFFFFF) + 4
        elif kind in (HUNK_DEBUG, HUNK_NAME):
            pos += 4 * long()
        elif kind == HUNK_END:
            number += 1
        else:
            break  # overlays, HUNK_EXT in a program, or something new: the code so far is enough
    return out


def _ea_ok(word: int, data: bool = True) -> bool:
    mode, reg = (word >> 3) & 7, word & 7
    if mode == 7:
        return reg <= (4 if data else 3)
    return True


def fpu_instruction(code: bytes, at: int) -> str:
    """The FPU instruction at an even offset, or '' when the words there are none."""
    if at + 4 > len(code):
        return ""
    word, ext = struct.unpack_from(">HH", code, at)
    if word & 0xFE00 != 0xF200:  # F-line, coprocessor 1
        return ""
    kind = (word >> 6) & 7
    if kind == 0:  # cpGEN
        opclass = ext >> 13
        if opclass == 0:
            if word & 0x3F:
                return ""
            return OPS.get(ext & 0x7F, "")
        if opclass == 2:
            if ext & 0xFC00 == 0x5C00:
                return "fmovecr" if word & 0x3F == 0 and ext & 0x7F < 0x40 else ""
            if (ext >> 10) & 7 == 7 or not _ea_ok(word):
                return ""
            return OPS.get(ext & 0x7F, "")
        if opclass == 3:
            fmt = (ext >> 10) & 7
            if fmt in (3, 7) or (ext & 0x7F) == 0:
                return "fmove" if _ea_ok(word, data=False) and (word >> 3) & 7 != 1 else ""
            return ""
        if opclass in (4, 5):
            return "fmove" if ext & 0x03FF == 0 and ext & 0x1C00 and _ea_ok(word) else ""
        if opclass in (6, 7):
            return "fmovem" if ext & 0x0700 == 0 and _ea_ok(word, data=opclass == 6) else ""
        return ""
    if kind == 1:  # FScc, FDBcc, FTRAPcc
        return "fscc" if ext & 0xFFC0 == 0 and ext < 0x20 else ""
    if kind in (2, 3):  # FBcc; FNOP is FBF.W with a zero displacement
        if word == 0xF280 and ext == 0:
            return "fnop"
        return "fbcc" if word & 0x3F < 0x20 and word & 0x3F not in (0, 0x10) else ""
    return ""  # FSAVE/FRESTORE: task switchers, not programs


def ppc_hunks(data: bytes) -> int:
    """How many PowerPC code hunks a program has: more than 0 for a WarpOS program."""
    found: list[int] = []
    code_hunks(data, found)
    return len(found)


def fpu_use(data: bytes, most: int = 4) -> FpuUse:
    """FPU instructions in a program's code hunks (see the module's note)."""
    out = FpuUse()
    for number, code in code_hunks(data):
        out.code_bytes += len(code)
        at = 0
        while at + 4 <= len(code):
            name = fpu_instruction(code, at)
            if name and name not in ("fbcc", "fnop"):
                out.instructions += 1
                out.emulated += name in EMULATED
                if len(out.first) < most:
                    out.first.append(f"hunk {number} +${at:X} {name}")
                at += 4
            else:
                at += 2
    return out
