"""The helper programs go onto every Amiga, a 68000 too: no 68020 instructions.

amigent-monitor 1.4.0 was a 68020 build and stopped an A500 with an illegal
instruction (#41). This looks at the code hunks for the 68020 instructions
vbcc emits most (EXTB.L and the long MULS/MULU/DIVS/DIVU on a data register).
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[1] / "src" / "amigent" / "amiga" / "bin"
HELPERS = ("amigent-monitor", "amigent-status", "amigent-levels")


def code_hunks(data: bytes) -> list[bytes]:
    """The code hunks of an AmigaDOS load file."""
    longs = lambda at, n: struct.unpack_from(f">{n}L", data, at)  # noqa: E731
    assert longs(0, 1)[0] == 0x3F3, "not a load file"
    at = 4
    while longs(at, 1)[0]:  # resident library names: none expected, but skip them
        at += 4 + 4 * longs(at, 1)[0]
    at += 4
    _, first, last = longs(at, 3)
    at += 12 + 4 * (last - first + 1)
    code = []
    while at + 4 <= len(data):
        kind = longs(at, 1)[0] & 0x3FFFFFFF
        at += 4
        if kind in (0x3E9, 0x3EA):  # CODE, DATA
            n = longs(at, 1)[0] & 0x3FFFFFFF
            if kind == 0x3E9:
                code.append(data[at + 4:at + 4 + 4 * n])
            at += 4 + 4 * n
        elif kind in (0x3EB, 0x3F1):  # BSS (size only), DEBUG
            at += 4 + (4 * longs(at, 1)[0] if kind == 0x3F1 else 0)
        elif kind in (0x3EC, 0x3F7):  # RELOC32, its short form
            short = kind == 0x3F7
            while True:
                n = (struct.unpack_from(">H", data, at)[0] if short else longs(at, 1)[0])
                if not n:
                    at += 2 if short else 4
                    break
                at += (2 + 2 + 2 * n) if short else (8 + 4 * n)
            if short and at % 4:
                at += 2
        elif kind == 0x3F0:  # SYMBOL
            while longs(at, 1)[0]:
                at += 4 + 4 * longs(at, 1)[0] + 4
            at += 4
        elif kind == 0x3F2:  # END
            continue
        else:
            raise AssertionError(f"hunk type {kind:#x} not handled")
    return code


def is_68020_only(w: int, x: int) -> bool:
    if 0x49C0 <= w <= 0x49C7:  # EXTB.L Dn
        return True
    # MULx.L / DIVx.L <ea>,Dn: second word with no register in bits 0-2 but Dl in 12-14
    return (w & 0xFFF8) in (0x4C00, 0x4C40) and (x & 0x83F8) == 0


@pytest.mark.parametrize("name", HELPERS)
def test_helpers_run_on_a_68000(name):
    hits = 0
    for code in code_hunks((BIN / name).read_bytes()):
        for at in range(0, len(code) - 3, 2):
            w, x = struct.unpack_from(">HH", code, at)
            hits += is_68020_only(w, x)
    assert hits == 0, f"{name} looks like a 68020 build ({hits} 68020 instructions)"


def test_the_check_would_see_a_68020_build():
    code = struct.pack(">HH", 0x49C0, 0) + struct.pack(">HH", 0x4C00, 0x1000)
    assert sum(is_68020_only(*struct.unpack_from(">HH", code, a)) for a in range(0, 6, 2)) == 2


def test_amigentd_has_one_version_string_only():
    """Version reads the first $VER: in a file; a second one would hide the real one."""
    from pathlib import Path
    folder = Path(__file__).resolve().parents[1] / "src" / "amigent" / "amiga" / "bin"
    for name in ("amigentd", "amigentd.000"):
        binary = (folder / name).read_bytes()
        assert binary.count(b"$VER: ") == 1, name
