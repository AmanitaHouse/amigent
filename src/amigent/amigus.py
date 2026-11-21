"""The AmiGUS sound card: is it there, which driver holds which part, output levels.

Everything here only reads. The reservation state comes from amigus.library's
own records, read with PEEK, so nothing is reserved to find out. Layouts are
those of the public AmiGUS sources (amigus.library 1.x, header amigus/amigus.h
and the library's private header):

  struct AmiGUS_Base: struct Library, UWORD, seglist, SignalSemaphore, SysBase,
    then SysBase, DOSBase, ExpansionBase, CardResource and the list of cards.
  struct AmiGUS_Private: Node (14 bytes), the public struct AmiGUS (40 bytes),
    then for PCM, wavetable and codec: owner pointer, owner data, handler, data.

The owner pointer of a Zorro II card points to cd_Driver of the part's
ConfigDev, that of an AmiGUS mini to the owner data next to it. Each pointer is
checked before its owner is believed.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field

from .errors import AmigaError

MANUFACTURER = 2782
PRODUCTS = {16: "PCM", 17: "wavetable", 18: "codec"}
PARTS = ("PCM", "wavetable", "codec")
TYPES = {0x7000: "AmiGUS (Zorro II)", 0x7001: "AmiGUS mini (PCMCIA)"}
LIBRARY = "amigus.library"
AHI_DRIVER = "amigus.audio"  # its library node says AmiGUS.audio
MHI_DRIVER = "mhiamigus.library"

PUBLIC = 14         # struct AmiGUS inside struct AmiGUS_Private
PART = 54           # first struct AmiGUS_Part
PART_SIZE = 16
PRIVATE_SIZE = PART + 3 * PART_SIZE
CD_DRIVER = 44      # cd_Driver in struct ConfigDev
CD_SIZE = 48        # as far as we read it
BOARD_LIST = 60     # the board list in ExpansionBase (private, unchanged since 1.3)
MOST = 64           # list entries to follow at most
READ_ERRORS = (AmigaError, struct.error, IndexError, ValueError)

AHI_HELD = ("PCM is held by the AHI driver: restart without AHI to use it, and never run "
            "Avail FLUSH while the driver is loaded.")


def _long(data: bytes, at: int) -> int:
    return struct.unpack_from(">I", data, at)[0]


def _word(data: bytes, at: int) -> int:
    return struct.unpack_from(">H", data, at)[0]


@dataclass
class Board:
    address: int
    product: int
    board: int
    driver: int


@dataclass
class Card:
    address: int
    type_id: int
    type_name: str
    hardware: int
    firmware: int
    date: str
    bases: tuple[int, int, int]
    owners: list[int | None] = field(default_factory=list)  # None: could not be read

    @property
    def public(self) -> int:
        return self.address + PUBLIC

    @property
    def kind(self) -> str:
        return TYPES.get(self.type_id) or self.type_name or f"AmiGUS type ${self.type_id:04X}"


def _list(peek, header: int):
    """The nodes of an exec list at header, or None if it does not look like one."""
    head = peek(header, 12)
    if _long(head, 4) != 0:  # lh_Tail is always zero
        return None
    nodes, node = [], _long(head, 0)
    while len(nodes) < MOST:
        if node == header + 4:  # back at the list's tail: the end
            return nodes
        if not node or node & 1:
            return None
        nodes.append(node)
        node = _long(peek(node, 4), 0)
    return None


def boards(peek, expansion: int) -> list[Board] | None:
    """The AmiGUS boards in expansion.library's list; None if that cannot be read."""
    try:
        nodes = _list(peek, expansion + BOARD_LIST)
        if nodes is None:
            return None
        out = []
        for node in nodes:
            cd = peek(node, CD_SIZE)
            if _word(cd, 20) == MANUFACTURER:
                out.append(Board(node, cd[17], _long(cd, 32), _long(cd, CD_DRIVER)))
        return out
    except READ_ERRORS:  # a refused PEEK: the list is not where we think
        return None


def _base_fields(peek, lib, sysbase: int, dos: int, expansion: int) -> int | None:
    """Where SysBase, DOSBase and ExpansionBase follow each other in amigus.library's base."""
    want = struct.pack(">III", sysbase, dos, expansion)
    data = peek(lib.base, max(64, min(lib.pos_size or 256, 512)))
    at = data.find(want)
    while at != -1 and at % 2:
        at = data.find(want, at + 1)
    return None if at == -1 else at


def _owner_pointer_ok(peek, card_at: int, part: int, pointer: int) -> bool:
    if pointer == card_at + PART + part * PART_SIZE + 4:  # AmiGUS mini: the owner data beside it
        return True
    try:
        cd = peek(pointer - CD_DRIVER, CD_SIZE)  # Zorro II: cd_Driver of the part's board
    except READ_ERRORS:
        return False
    return _word(cd, 20) == MANUFACTURER and cd[17] == 16 + part


def cards(peek, lib, sysbase: int, dos: int, expansion: int) -> list[Card] | None:
    """The cards amigus.library found, with the owner of each part; None: unknown layout."""
    try:
        at = _base_fields(peek, lib, sysbase, dos, expansion)
        if at is None:
            return None
        nodes = _list(peek, lib.base + at + 16)  # after CardResource
        if nodes is None:
            return None
        out = []
        for node in nodes:
            p = peek(node, PRIVATE_SIZE)
            type_id = _word(p, PUBLIC + 32)
            if type_id not in TYPES:
                return None
            name = ""
            if _long(p, PUBLIC + 28):
                try:
                    name = peek(_long(p, PUBLIC + 28), 48).split(b"\0", 1)[0].decode("iso-8859-1")
                except READ_ERRORS:
                    name = ""
            year, month, day, hour, minute = _word(p, PUBLIC + 34), *p[PUBLIC + 36:PUBLIC + 40]
            card = Card(node, type_id, name, _long(p, PUBLIC + 20), _long(p, PUBLIC + 24),
                        f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}" if year else "",
                        (_long(p, PUBLIC), _long(p, PUBLIC + 4), _long(p, PUBLIC + 8)))
            for part in range(3):
                pointer = _long(p, PART + part * PART_SIZE)
                if not pointer or not _owner_pointer_ok(peek, node, part, pointer):
                    card.owners.append(None)
                    continue
                try:
                    card.owners.append(_long(peek(pointer, 4), 0))
                except READ_ERRORS:
                    card.owners.append(None)
            out.append(card)
        return out
    except READ_ERRORS:
        return None


def _find(loaded, name: str):
    return next((lib for lib in loaded.libraries if lib.name.lower() == name), None)


def owner_name(owner: int, card: Card, loaded, tasks, part: int) -> str:
    for lib in loaded.libraries:
        if lib.base == owner:
            return ("the AHI driver " + lib.name) if lib.name.lower() == AHI_DRIVER else lib.name
    for t in tasks:
        if t.address == owner:
            return f"the task {t.label}"
    if owner == card.public:
        return "a program that gave the card itself as owner (PlayWAV and PlayMP3 do)"
    text = f"owner ${owner:08X}, not a library or task amigentd knows"
    if part == 2 and _find(loaded, MHI_DRIVER):
        text += f"; {MHI_DRIVER} is loaded and reserves the codec with a handle of its own"
    return text


def _version(lib) -> str:
    return f"{lib.version}.{lib.revision}, open {lib.open_count}"


def status(loaded, tasks, peek, sysbase: int) -> str:
    """What amiga_amigus_status says."""
    lib = _find(loaded, LIBRARY)
    ahi = _find(loaded, AHI_DRIVER)
    mhi = _find(loaded, MHI_DRIVER)
    dos = _find(loaded, "dos.library")
    expansion = _find(loaded, "expansion.library")
    zorro = boards(peek, expansion.base) if expansion else None
    found = cards(peek, lib, sysbase, dos.base if dos else 0, expansion.base if expansion else 0) \
        if lib else None

    if not lib and not zorro and not ahi:
        why = "no Zorro board from manufacturer 2782" if zorro is not None else \
            "the board list of expansion.library could not be read"
        return (f"No AmiGUS found: {why}, and amigus.library is not loaded (an AmiGUS mini in "
                "the PCMCIA slot shows only through amigus.library, which the AmiGUS drivers load).")

    lines = []
    if lib and found is not None and not found and not zorro:
        lines.append("No AmiGUS: amigus.library is loaded but found no card.")
    for i, card in enumerate(found or []):
        lines.append(f"{card.kind}{f' {i + 1}' if len(found) > 1 else ''}: firmware {card.date or '?'} "
                     f"(revision {card.firmware:X}, hardware {card.hardware:X}), PCM at ${card.bases[0]:08X}")
        for part, owner in enumerate(card.owners):
            if owner is None:
                state = "unknown (its record did not check out)"
            elif not owner:
                state = "free"
            else:
                state = "reserved by " + owner_name(owner, card, loaded, tasks, part)
            lines.append(f"  {PARTS[part]:10} {state}")
    if zorro:
        lines.append("Zorro boards: " + ", ".join(
            f"{PRODUCTS.get(b.product, f'product {b.product}')} at ${b.board:08X}" for b in zorro))
    if lib:
        lines.append(f"{lib.name} {_version(lib)}")
        if found is None:
            lines.append(f"  its card list is not laid out as this Amigent knows ({lib.name} "
                         f"{lib.version}.{lib.revision}): reservations unknown")
    else:
        lines.append("amigus.library is not loaded: nothing has reserved a part through it")
    lines.append(f"AHI driver {ahi.name} {_version(ahi)}" if ahi else "AHI driver AmiGUS.audio is not loaded")
    lines.append(f"MHI driver {mhi.name} {_version(mhi)}" if mhi else "MHI driver mhiamigus.library is not loaded")
    held = any(c.owners and c.owners[0] and ahi and c.owners[0] == ahi.base for c in found or [])
    if held or (ahi and found is None):
        lines.append(("Warning: " if held else "Probably: ") + AHI_HELD
                     + (" It keeps PCM from when it is loaded until it is expunged, even while no "
                        "program has it open." if held else ""))
    lines.append("(read from amigus.library's records; nothing was reserved)")
    return "\n".join(lines)


# ---- output levels, read by amigent-levels on the Amiga

def parse_levels(text: str) -> tuple[dict, list[tuple[int, int]]]:
    info, samples = {}, []
    for line in text.splitlines():
        p = line.strip().split("\t")
        if p[0] == "S" and len(p) >= 3:
            try:
                samples.append((int(p[1]), int(p[2])))
            except ValueError:
                pass
        elif p[0] in ("CARD", "MODE", "TICKS", "ERROR") and len(p) >= 2:
            info[p[0]] = "\t".join(p[1:])
    return info, samples


def _db(value: int) -> str:
    return f"{20 * math.log10(value / 32767):6.1f} dBFS" if value > 0 else "  silent "


QUIET = 33  # about -60 dBFS: a channel above this carries sound


def levels(text: str, seconds: float, hz: int, peak: bool) -> str:
    info, samples = parse_levels(text)
    if "ERROR" in info:
        return info["ERROR"]
    if not samples:
        return "amigent-levels gave no samples:\n" + text.strip()
    left = [abs(s[0]) for s in samples]
    right = [abs(s[1]) for s in samples]
    ticks = info.get("TICKS", "")
    took = f", {int(ticks) / 50:.1f} s on the Amiga" if ticks.isdigit() else ""
    card = info.get("CARD", "AmiGUS").split("\t")
    name = card[0] + (f" (PCM part at ${card[1].upper()})" if len(card) > 1 else "")
    out = [f"{name}: {len(samples)} samples at {hz} Hz{took}, "
           f"{'peak' if peak else 'average'} of each interval, of full scale 32767"]
    for name, vals in (("left", left), ("right", right)):
        out.append(f"{name:5} max {max(vals):5} {_db(max(vals))}, mean {sum(vals) // len(vals):5} "
                   f"{_db(sum(vals) // len(vals))}, {'sound' if max(vals) > QUIET else 'silent'}")
    out.append("series in % of full scale (left/right):")
    row = [f"{a * 100 // 32767}/{b * 100 // 32767}" for a, b in zip(left, right)]
    for i in range(0, len(row), 20):
        out.append(f"  {i / hz:5.1f} s  " + " ".join(row[i:i + 20]))
    if "MODE" in info:
        out.append(info["MODE"])
    return "\n".join(out)
