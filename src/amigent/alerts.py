"""Guru meditation codes in words, after exec/alerts.h.

An alert is 32 bits: the top bit says the Amiga could not go on (dead end), the
next seven name the part of the system, the next byte a general kind of error,
and the low 16 bits the specific one. Codes from CPU exceptions have no part
and are just the exception number. The second number of a guru is the task or
the address that caused it.
"""

from __future__ import annotations

DEADEND = 0x80000000

SUBSYSTEMS = {
    0x01: "exec.library", 0x02: "graphics.library", 0x03: "layers.library",
    0x04: "intuition.library", 0x05: "math libraries", 0x07: "dos.library",
    0x08: "ramlib", 0x09: "icon.library", 0x0A: "expansion.library",
    0x0B: "diskfont.library", 0x0C: "utility.library", 0x0D: "keymap.library",
    0x10: "audio.device", 0x11: "console.device", 0x12: "gameport.device",
    0x13: "keyboard.device", 0x14: "trackdisk.device", 0x15: "timer.device",
    0x20: "cia.resource", 0x21: "disk.resource", 0x22: "misc.resource",
    0x30: "bootstrap", 0x31: "Workbench", 0x32: "DiskCopy", 0x33: "gadtools.library",
    0x34: "utility.library", 0x35: "an unknown part",
}

GENERAL = {
    0x01: "out of memory", 0x02: "MakeLibrary() failed", 0x03: "a library did not open",
    0x04: "a device did not open", 0x05: "a resource did not open", 0x06: "I/O error",
    0x07: "no free signal", 0x08: "bad parameter", 0x09: "a library closed twice or wrongly",
    0x0A: "a device closed twice or wrongly", 0x0B: "a process could not be created",
}

# Only the specific codes a user meets in practice; the rest gets its part and kind.
SPECIFIC = {
    0x01000001: "an exception vector's checksum is wrong",
    0x01000002: "ExecBase's checksum is wrong",
    0x01000003: "a library's checksum is wrong",
    0x01000005: "the memory list is corrupt (a program wrote over memory it did not own)",
    0x01000006: "no memory for interrupt servers",
    0x01000007: "InitStruct() of an APTR source",
    0x01000008: "a semaphore is in an illegal state",
    0x01000009: "memory was freed twice",
    0x0100000A: "an exception without a handler (often a crashed program)",
    0x0100000B: "an IORequest was used twice",
    0x0100000C: "the memory list is insane",
    0x0100000D: "an IORequest was used after its device was closed",
    0x0100000E: "a stack ran out of its bounds (stack overflow)",
    0x0100000F: "FreeMem() of an address that was never allocated",
    0x01000010: "a bad semaphore",
    0x02010000: "graphics ran out of memory",
    0x04000001: "a gadget of unknown type",
    0x04010002: "intuition could not create a message port",
    0x04010007: "a screen could not be opened",
    0x0401000B: "a window could not be opened",
    0x0400000C: "intuition is in a bad state",
    0x0400000D: "intuition got an unknown message",
    0x0400000F: "intuition could not open console.device",
    0x07010001: "no memory when dos started",
    0x07000002: "EndTask() did not end the task",
    0x07000003: "a DOS packet did not get through",
    0x07000004: "an unexpected packet",
    0x07000005: "FreeVec() of something that was not AllocVec()ed",
    0x07000006: "a disk block is out of sequence",
    0x07000007: "a disk's bitmap is corrupt",
    0x07000008: "a disk key is already free",
    0x07000009: "a disk block's checksum is wrong",
    0x0700000A: "a disk error",
    0x0700000B: "a disk key is out of range",
    0x0700000C: "a bad overlay",
    0x0700000D: "a bad init function in a resident module",
    0x0700000E: "a file was closed twice",
    0x14000001: "trackdisk: seek error during calibration",
    0x15000001: "timer: bad request",
}

CPU = {
    0x02: "bus error (access to an address nothing answers)",
    0x03: "address error (a word or long at an odd address on a 68000)",
    0x04: "illegal instruction (the CPU ran into data, or a CPU too old for the program)",
    0x05: "division by zero",
    0x06: "CHK instruction",
    0x07: "TRAPV instruction",
    0x08: "privilege violation (a user program used a supervisor instruction)",
    0x09: "trace",
    0x0A: "line A emulator (unimplemented instruction)",
    0x0B: "line F emulator (an FPU or MMU instruction the CPU does not have)",
    0x0E: "format error",
    0x0F: "uninitialized interrupt",
    0x18: "spurious interrupt",
}


def describe(code: int | str, where: int | str | None = None) -> str:
    """'8100000C' -> 'exec.library: the memory list is insane; dead end (the Amiga had to stop)'."""
    if isinstance(code, str):
        code = int(code.strip().lstrip("#$").split(".")[0], 16)
    if isinstance(where, str):
        try:
            where = int(where.strip().lstrip("#$"), 16)
        except ValueError:
            where = None
    deadend = bool(code & DEADEND)
    sub = (code >> 24) & 0x7F
    general = (code >> 16) & 0xFF
    plain = code & 0x7FFFFFFF
    if sub == 0 and general == 0 and (code & 0xFFFF) in CPU:
        text = "CPU exception: " + CPU[code & 0xFFFF]
        deadend = True  # a CPU guru always stops the Amiga
    else:
        part = SUBSYSTEMS.get(sub, f"part {sub:02X}")
        if plain in SPECIFIC:
            text = f"{part}: {SPECIFIC[plain]}"
        elif general in GENERAL:
            text = f"{part}: {GENERAL[general]}"
        elif general & 0x80 == 0 and general:
            text = f"{part}: error {general:02X}.{code & 0xFFFF:04X}"
        else:
            text = f"{part}: error {code & 0xFFFF:04X}"
        # AG_OpenLib and friends name what did not open: AO_xxx = $8000 + its part
        if general in (0x03, 0x04, 0x05) and code & 0xFF00 == 0x8000 and code & 0x7F in SUBSYSTEMS:
            text += f" ({SUBSYSTEMS[code & 0x7F]})"
    text += "; dead end (the Amiga had to stop)" if deadend else "; recoverable"
    if where:
        text += f"; caused by the task or at the address {where:08X}"
    return text


def gurudat(text: str) -> dict[int, str]:
    """MCP's S:MCP.gurudat: 'XXXXXXXX description' per line."""
    out = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and len(parts[0]) == 8:
            try:
                out[int(parts[0], 16)] = parts[1].strip()
            except ValueError:
                pass
    return out


def history(text: str, extra: dict[int, str] | None = None) -> list[str]:
    """Each line of a guru log that holds a guru code, with the code in words."""
    import re

    out = []
    for line in text.splitlines():
        m = re.search(r"\b([0-9A-Fa-f]{8})(?:\.([0-9A-Fa-f]{8}))?\b", line)
        if not m:
            continue
        code = int(m.group(1), 16)
        words = describe(code, m.group(2))
        known = (extra or {}).get(code) or (extra or {}).get(code & 0x7FFFFFFF)
        out.append(f"{line.strip()}  ->  {words}" + (f" (MCP: {known})" if known else ""))
    return out
