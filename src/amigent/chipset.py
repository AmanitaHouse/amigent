"""The custom chips of an emulated Amiga: Paula's audio channels, the copper,
sprites and DMA, read through WinUAE's GDB server.

On a real Amiga most of these registers can only be written; the emulator
keeps their values and hands them out at $DFF000 as memory.
"""

from __future__ import annotations

import struct

PAL_CLOCK = 3546895  # Paula's clock on a PAL Amiga; an NTSC one runs at 3579545

NAMES = {
    0x000: "BLTDDAT", 0x002: "DMACONR", 0x004: "VPOSR", 0x006: "VHPOSR", 0x00A: "JOY0DAT",
    0x00C: "JOY1DAT", 0x010: "ADKCONR", 0x01C: "INTENAR", 0x01E: "INTREQR", 0x07C: "DENISEID",
    0x080: "COP1LCH", 0x082: "COP1LCL", 0x084: "COP2LCH", 0x086: "COP2LCL",
    0x08E: "DIWSTRT", 0x090: "DIWSTOP", 0x092: "DDFSTRT", 0x094: "DDFSTOP", 0x096: "DMACON",
    0x09A: "INTENA", 0x09C: "INTREQ", 0x09E: "ADKCON",
    0x100: "BPLCON0", 0x102: "BPLCON1", 0x104: "BPLCON2", 0x106: "BPLCON3", 0x108: "BPL1MOD",
    0x10A: "BPL2MOD", 0x10C: "BPLCON4", 0x1FC: "FMODE",
}
for _ch in range(4):
    base = 0x0A0 + _ch * 0x10
    NAMES.update({base: f"AUD{_ch}LCH", base + 2: f"AUD{_ch}LCL", base + 4: f"AUD{_ch}LEN",
                  base + 6: f"AUD{_ch}PER", base + 8: f"AUD{_ch}VOL", base + 10: f"AUD{_ch}DAT"})
for _i in range(8):
    NAMES.update({0x0E0 + _i * 4: f"BPL{_i + 1}PTH", 0x0E2 + _i * 4: f"BPL{_i + 1}PTL",
                  0x120 + _i * 4: f"SPR{_i}PTH", 0x122 + _i * 4: f"SPR{_i}PTL"})

DMA_BITS = [(9, "master"), (8, "bitplanes"), (7, "copper"), (6, "blitter"), (5, "sprites"),
            (4, "disk"), (0, "audio 0"), (1, "audio 1"), (2, "audio 2"), (3, "audio 3")]


def word(regs: bytes, offset: int) -> int:
    return struct.unpack(">H", regs[offset:offset + 2])[0] if offset + 2 <= len(regs) else 0


def long(regs: bytes, offset: int) -> int:
    return (word(regs, offset) << 16 | word(regs, offset + 2)) & 0x1FFFFE


def registers(regs: bytes) -> str:
    return "\n".join(f"$DFF{off:03X} {name:9} = ${word(regs, off):04X}"
                     for off, name in sorted(NAMES.items()))


def dma(regs: bytes) -> str:
    value = word(regs, 0x002)
    on = [name for bit, name in DMA_BITS if value & (1 << bit)]
    return f"DMACONR ${value:04X}: " + (", ".join(on) if on else "nothing on")


def paula(regs: bytes, clock: int = PAL_CLOCK) -> str:
    on = word(regs, 0x002)
    lines = []
    for ch in range(4):
        base = 0x0A0 + ch * 0x10
        period, volume = word(regs, base + 6), word(regs, base + 8) & 0x7F
        rate = clock // period if period else 0
        playing = bool(on & 0x200 and on & (1 << ch))
        lines.append(f"channel {ch}: {'playing' if playing else 'off    '}  sample at ${long(regs, base):06X}, "
                     f"{word(regs, base + 4) * 2} bytes, period {period} ({rate} Hz), volume {volume}/64")
    return "\n".join(lines)


def sprites(regs: bytes) -> str:
    return "\n".join(f"sprite {i}: data at ${long(regs, 0x120 + i * 4):06X}" for i in range(8))


def copper(data: bytes, address: int) -> str:
    """A copper list: MOVE, WAIT and SKIP, up to its end (WAIT $FFFF,$FFFE)."""
    lines = []
    for at in range(0, len(data) - 3, 4):
        a, b = struct.unpack(">HH", data[at:at + 4])
        here = f"${address + at:06X}  {a:04X} {b:04X}  "
        if not a & 1:
            name = NAMES.get(a & 0x1FE, f"${0xDFF000 + (a & 0x1FE):06X}")
            lines.append(here + f"MOVE  ${b:04X} -> {name}")
        else:
            kind = "SKIP" if b & 1 else "WAIT"
            lines.append(here + f"{kind}  line {a >> 8}, column {(a & 0xFE) >> 1 << 2}")
            if a == 0xFFFF and b == 0xFFFE:
                lines[-1] += "  (end)"
                break
    return "\n".join(lines)
