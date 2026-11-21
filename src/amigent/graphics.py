"""Graphics boards: which card, chip and driver, Picasso96 or CyberGraphX, the 3D
libraries, and the Picasso96 screen modes with their colour depths.

Everything is told from what amigentd already answers: LOADED for the drivers in
memory, PEEK for expansion.library's board list, Version FILE for libraries on
disk, and the file DEVS:Picasso96Settings. No new daemon command.

Zorro IDs are those of Linux's include/uapi/linux/zorro_ids.h; the ZZ9000's are
from its driver sources (manufacturer $6D6E, product 3 in Zorro II, 4 in Zorro III).

DEVS:Picasso96Settings is an IFF FORM P96S. After the header chunks (ANNO, STHD)
come per board a monitor (MNTR), the board's name (BDNM), and per resolution an
RSHD (the mode's name such as 'VideoCore:640x480' from byte 14 on) followed by
one MIHD per colour depth: ULONG flags (bit 0: the mode is switched on), UWORD
width, UWORD height, UBYTE depth in bits, then the timing. Switching a depth on
or off flips bit 0 of its MIHD and nothing else; the file keeps its size.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

SETTINGS = "DEVS:Picasso96Settings"
UNDO = SETTINGS + ".amigent-undo"      # the file as it was before the last change
ORIGINAL = SETTINGS + ".amigent-orig"  # as it was before Amigent changed it the first time

ZORRO_II, ZORRO_III = "Zorro II", "Zorro III"
ERT_TYPEMASK, ERT_ZORROII, ERT_ZORROIII = 0xC0, 0xC0, 0x80
CD_SIZE = 48
BOARD_LIST = 60  # the board list in ExpansionBase, as amigus.py reads it
ZZ9000_MANUFACTURER = 0x6D6E

# (manufacturer, product) -> (board, chip); only the boards that carry a screen.
ZORRO_BOARDS = {
    (0x0877, 0x01): ("Domino", "Tseng ET4000"),
    (0x0877, 0x02): ("Domino", "Tseng ET4000"),
    (0x0877, 0x0B): ("Picasso II", "Cirrus Logic GD5426/28"),
    (0x0877, 0x0C): ("Picasso II", "Cirrus Logic GD5426/28"),
    (0x0877, 0x0D): ("Picasso II", "Cirrus Logic GD5426/28"),
    (0x0877, 0x15): ("Picasso IV", "Cirrus Logic GD5446"),
    (0x0877, 0x16): ("Picasso IV", "Cirrus Logic GD5446"),
    (0x0877, 0x17): ("Picasso IV", "Cirrus Logic GD5446"),
    (0x0877, 0x18): ("Picasso IV", "Cirrus Logic GD5446"),
    (0x2140, 0x22): ("CyberVision 64", "S3 Trio64/Vision864"),
    (0x2140, 0x32): ("CyberVision 64/3D (prototype)", "S3 ViRGE"),
    (0x2140, 0x43): ("CyberVision 64/3D", "S3 ViRGE"),
    (0x4754, 0x06): ("Retina", "NCR 77C22E"),
    (0x4754, 0x10): ("Retina Z3", "NCR 77C32BLT"),
    (0x4754, 0x13): ("Altais", "NCR 77C32BLT"),
    (0x0845, 0x01): ("Visiona", "Inmos G300"),
    (0x0845, 0x02): ("Visiona", "Inmos G300"),
    (0x0845, 0x03): ("Merlin", "Tseng ET4000W32"),
    (0x0845, 0x04): ("Merlin", "Tseng ET4000W32"),
    (0x0845, 0xC9): ("Merlin", "Tseng ET4000W32"),
    (0x0893, 0x05): ("Piccolo", "Cirrus Logic GD5426"),
    (0x0893, 0x06): ("Piccolo", "Cirrus Logic GD5426"),
    (0x0893, 0x0A): ("Piccolo SD64", "Cirrus Logic GD5434"),
    (0x0893, 0x0B): ("Piccolo SD64", "Cirrus Logic GD5434"),
    (0x0891, 0x01): ("EGS 28/24 Spectrum", "Cirrus Logic GD5428"),
    (0x0891, 0x02): ("EGS 28/24 Spectrum", "Cirrus Logic GD5428"),
    (0x0861, 0x20): ("Rainbow II", ""),
    (0x0861, 0x21): ("Rainbow III", ""),
    (0x082C, 0x21): ("Graffiti", ""),
    (0x082C, 0x22): ("Graffiti", ""),
    (0x085E, 0x00): ("GDA-1", ""),
    (0x085E, 0x01): ("GDA-1", ""),
    (ZZ9000_MANUFACTURER, 0x03): ("ZZ9000", "Xilinx Zynq (ARM)"),
    (ZZ9000_MANUFACTURER, 0x04): ("ZZ9000", "Xilinx Zynq (ARM)"),
}

# Driver files, lower case -> (board, where its screen memory sits). A card behind
# "local" is read at CPU speed; "Zorro" ones depend on the slot.
CARDS = {
    "videocore.card": ("PiStorm (Raspberry Pi VideoCore)", "local"),
    "emu68-vc4.card": ("PiStorm (Raspberry Pi VideoCore)", "local"),  # the name AmiKit ships
    "uaegfx.card": ("UAE graphics card (emulator)", "local"),
    "zz9000.card": ("ZZ9000", "Zorro"),
    "picassoiv.card": ("Picasso IV", "Zorro"),
    "picassoii.card": ("Picasso II", "Zorro"),
    "piccolo.card": ("Piccolo", "Zorro"),
    "piccolosd64.card": ("Piccolo SD64", "Zorro"),
    "spectrum.card": ("EGS 28/24 Spectrum", "Zorro"),
    "domino.card": ("Domino", "Zorro"),
    "merlin.card": ("Merlin", "Zorro"),
    "retinaz3.card": ("Retina Z3", "Zorro"),
    "altais.card": ("Altais", "Zorro"),
    "cybervision.card": ("CyberVision 64", "Zorro"),
    "cvision3d.card": ("CyberVision 64/3D", "Zorro"),
    "cvisionppc.card": ("CyberVisionPPC", "local"),
    "bvisionppc.card": ("BlizzardVisionPPC", "local"),
    "saga.card": ("Vampire SAGA", "local"),
    "mediator.card": ("PCI card through a Mediator", "Zorro"),
}
CHIPS = {
    "s3vision864.chip": "S3 Vision864", "s3trio64.chip": "S3 Trio64", "s3virge.chip": "S3 ViRGE",
    "cirrusgd5426.chip": "Cirrus Logic GD5426", "cirrusgd5428.chip": "Cirrus Logic GD5428",
    "cirrusgd5434.chip": "Cirrus Logic GD5434", "cirrusgd5446.chip": "Cirrus Logic GD5446",
    "cirrusgd542x.chip": "Cirrus Logic GD542x", "tseng.chip": "Tseng ET4000",
    "et4000w32.chip": "Tseng ET4000W32", "ncr77c32blt.chip": "NCR 77C32BLT",
    "permedia2.chip": "3Dlabs Permedia 2", "voodoo.chip": "3dfx Voodoo",
}
# Boards this was tried with (PiStorm, WinUAE); the rest comes from the Zorro ID table
# and the driver names only, and is said so in docs/GUIDE.md.
TESTED = {"PiStorm (Raspberry Pi VideoCore)", "UAE graphics card (emulator)"}

DEPTH_NAMES = {8: "8 bit (256 colours)", 15: "15 bit", 16: "16 bit", 24: "24 bit", 32: "32 bit"}


@dataclass
class ZorroBoard:
    manufacturer: int
    product: int
    bus: str
    address: int
    size: int

    @property
    def known(self) -> tuple[str, str] | None:
        return ZORRO_BOARDS.get((self.manufacturer, self.product))


@dataclass
class Info:
    system: str = ""             # Picasso96, CyberGraphX or ""
    system_version: str = ""
    cards: list = field(default_factory=list)   # (file name, version, board, place)
    chips: list = field(default_factory=list)   # (file name, version, chip)
    boards: list = field(default_factory=list)  # ZorroBoard with a known screen board
    boards_read: bool = True     # False: the board list could not be read
    loaded_known: bool = True    # False: amigentd before 1.4.0, no LOADED
    threed: list = field(default_factory=list)  # "Warp3D.library 4.2 (in memory)" and the like

    @property
    def zz9000(self) -> bool:
        return any(b.manufacturer == ZZ9000_MANUFACTURER for b in self.boards) or \
            any(c[0].lower() == "zz9000.card" for c in self.cards)

    @property
    def slow_bus(self) -> bool:
        """The screen sits on a Zorro II card that amigentd reads over the bus.

        A ZZ9000 sends only what changed through its own encoder, and a card on a
        local bus (PiStorm, CPU slot, emulator) is fast, so neither counts.
        """
        if self.zz9000 or any(c[3] == "local" for c in self.cards):
            return False
        return bool(self.boards) and all(b.bus == ZORRO_II for b in self.boards)


def _long(data: bytes, at: int) -> int:
    return struct.unpack_from(">I", data, at)[0]


def zorro_boards(peek, expansion: int) -> list[ZorroBoard] | None:
    """Every board in expansion.library's list; None if the list cannot be read."""
    from .amigus import READ_ERRORS, _list
    try:
        nodes = _list(peek, expansion + BOARD_LIST)
        if nodes is None:
            return None
        out = []
        for node in nodes:
            cd = peek(node, CD_SIZE)
            kind = cd[16] & ERT_TYPEMASK
            bus = ZORRO_II if kind == ERT_ZORROII else ZORRO_III if kind == ERT_ZORROIII else "?"
            out.append(ZorroBoard(struct.unpack_from(">H", cd, 20)[0], cd[17], bus,
                                  _long(cd, 32), _long(cd, 36)))
        return out
    except READ_ERRORS:
        return None


def _lib(loaded, name: str):
    return next((lib for lib in loaded.libraries if lib.name.lower() == name.lower()), None)


def _ver(lib) -> str:
    return f"{lib.version}.{lib.revision}"


THREED_FILES = ("LIBS:Warp3D.library", "LIBS:minigl.library")
THREED_LOADED = ("warp3d.library", "minigl.library", "mesa.library", "stormmesa.library")


def detect(loaded, peek=None, run=None, listdir=None) -> Info:
    """What graphics there is. loaded: memory.Loaded or None (old amigentd);
    peek(address, n); run(command) -> (rc, output); listdir(path) -> entries."""
    info = Info()
    libs = loaded.libraries if loaded else []
    info.loaded_known = loaded is not None
    rtg, api, cgx = _lib(loaded, "rtg.library") if loaded else None, \
        _lib(loaded, "Picasso96API.library") if loaded else None, \
        _lib(loaded, "cybergraphics.library") if loaded else None
    if rtg or api:
        info.system = "Picasso96"
        info.system_version = ", ".join(f"{lib.name} {_ver(lib)}" for lib in (rtg, api) if lib)
    elif cgx:
        info.system = "CyberGraphX"
        info.system_version = f"cybergraphics.library {_ver(cgx)}" + (
            f" ({cgx.id_string})" if cgx.id_string else "")
    for lib in libs:
        low = lib.name.lower()
        if low.endswith(".card"):
            board, place = CARDS.get(low, ("", ""))
            info.cards.append((lib.name, _ver(lib), board, place))
        elif low.endswith(".chip"):
            info.chips.append((lib.name, _ver(lib), CHIPS.get(low, "")))
        elif low in THREED_LOADED or low.startswith("w3d_") or low.startswith("w3dn_"):
            text = f"{lib.name} {_ver(lib)} (in memory)"
            if "wazp3d" in lib.id_string.lower():
                text += ", Wazp3D (Warp3D in software)"
            info.threed.append(text)
    expansion = _lib(loaded, "expansion.library") if loaded else None
    if peek and expansion:
        found = zorro_boards(peek, expansion.base)
        info.boards_read = found is not None
        info.boards = [b for b in found or [] if b.known]
    else:
        info.boards_read = False
    in_memory = {t.split()[0].lower() for t in info.threed}
    if run:
        for path in THREED_FILES:
            name = path.split(":", 1)[1]
            if name.lower() in in_memory:
                continue
            rc, out = run(f"Version FILE {path}")
            line = out.strip().splitlines()[-1].strip() if out.strip() else ""
            if rc == 0 and line:
                info.threed.append(f"{line} (in {path.split(':')[0]}:, not loaded)")
    if listdir:
        try:
            drivers = sorted({e["name"].rsplit("/", 1)[-1] for e in listdir("LIBS:Warp3D")
                              if e.get("type") != "DIR" and e["name"].lower().endswith(".library")})
        except Exception:  # noqa: BLE001 - no LIBS:Warp3D is the usual answer
            drivers = []
        if drivers:
            info.threed.append("Warp3D drivers in LIBS:Warp3D: " + ", ".join(drivers))
    return info


def describe(info: Info) -> str:
    """What amiga_graphics says."""
    lines = []
    if not info.loaded_known:
        lines.append("amigentd before 1.4.0 has no LOADED: drivers in memory unknown; "
                     "only the files are read.")
    if info.system:
        lines.append(f"RTG system: {info.system} ({info.system_version})")
    elif info.loaded_known:
        lines.append("RTG system: none loaded (neither rtg.library nor cybergraphics.library "
                     "is in memory): chipset screens only")
    for name, version, board, place in info.cards:
        where = {"local": "on a fast local bus", "Zorro": "in a Zorro slot"}.get(place, "")
        lines.append(f"driver {name} {version}" + (f": {board}" if board else "")
                     + (f", {where}" if where else ""))
    for name, version, chip in info.chips:
        lines.append(f"chip driver {name} {version}" + (f": {chip}" if chip else ""))
    for b in info.boards:
        board, chip = b.known
        lines.append(f"Zorro board: {board}" + (f" ({chip})" if chip else "")
                     + f", {b.bus}, at ${b.address:08X}, {b.size // 1024} KB")
    if not info.boards_read and info.loaded_known:
        lines.append("the board list of expansion.library could not be read")
    if info.system == "CyberGraphX":
        lines.append("CyberGraphX: recognised only (not tested with Amigent); screen modes are managed for Picasso96.")
    names = {c[2] for c in info.cards if c[2]} | {b.known[0] for b in info.boards}
    untested = sorted(n for n in names if n not in TESTED)
    if untested:
        lines.append("Not tested with Amigent: " + ", ".join(untested)
                     + "; the names come from the Zorro ID table and the driver names.")
    if info.zz9000:
        lines.append("Screen reads: the ZZ9000's own encoder sends only the changed tiles.")
    elif info.slow_bus:
        lines.append("Screen reads: the card sits on Zorro II, so every look reads its memory over "
                     "the slow bus; the remote desktop asks for smaller pieces and looks less often, "
                     "and a region or changed=True keeps amiga_screenshot quick.")
    lines.append("3D: " + ("; ".join(info.threed) if info.threed else
                           "no Warp3D or MiniGL found (not in memory, not in LIBS:)"))
    return "\n".join(lines)


# ---- DEVS:Picasso96Settings

@dataclass
class Depth:
    bits: int
    on: bool
    offset: int  # of the MIHD's flags in the file


@dataclass
class Mode:
    board: str
    name: str   # 'VideoCore:640x480'
    width: int
    height: int
    depths: list = field(default_factory=list)

    @property
    def size(self) -> str:
        return f"{self.width}x{self.height}"


class SettingsError(ValueError):
    pass


def parse_settings(data: bytes) -> list[Mode]:
    if len(data) < 12 or data[:4] != b"FORM" or data[8:12] != b"P96S":
        raise SettingsError("not a Picasso96 settings file (no FORM P96S)")
    end = min(len(data), 8 + _long(data, 4))
    pos, board, modes, mode = 12, "", [], None
    while pos + 8 <= end:
        cid, size = data[pos:pos + 4], _long(data, pos + 4)
        body = pos + 8
        if body + size > end:
            raise SettingsError(f"chunk {cid!r} at {pos} runs past the end of the file")
        chunk = data[body:body + size]
        if cid == b"BDNM":
            board = chunk.split(b"\0", 1)[0].decode("iso-8859-1")
        elif cid == b"RSHD" and size >= 14:
            name = chunk[14:].split(b"\0", 1)[0].decode("iso-8859-1")
            w, h = struct.unpack_from(">HH", chunk, 4)
            mode = Mode(board, name, w, h)
            modes.append(mode)
        elif cid == b"MIHD" and size >= 9 and mode is not None:
            mode.depths.append(Depth(chunk[8], bool(_long(chunk, 0) & 1), body))
        pos = body + size + (size & 1)
    return modes


def listing(modes: list[Mode], board: str = "") -> str:
    if not modes:
        return "Picasso96 settings hold no screen modes."
    lines, last = [], None
    for m in modes:
        if board and board.lower() not in m.board.lower():
            continue
        if m.board != last:
            lines.append(f"board {m.board or '?'} (on: x, off: -)")
            last = m.board
        cells = " ".join(f"{d.bits:>2}{'x' if d.on else '-'}" for d in m.depths)
        label = m.name.split(":", 1)[-1]
        lines.append(f"  {label:18} {cells}" + ("" if label == m.size else f"  ({m.size})"))
    return "\n".join(lines) if lines else f"no board matches {board!r}"


def _select(modes: list[Mode], which: str) -> list[Mode]:
    """'640x480', 'VideoCore:640x480', several by comma, or 'all'."""
    wanted = [w.strip().lower() for w in which.split(",") if w.strip()]
    if not wanted:
        raise SettingsError("modes: e.g. 640x480, several by comma, or all")
    if wanted == ["all"]:
        return list(modes)
    out = []
    for w in wanted:
        hits = [m for m in modes if w in (m.name.lower(), m.size, m.name.split(":", 1)[-1].lower())]
        if not hits:
            raise SettingsError(f"no screen mode {w!r} in the settings; amiga_screen_modes lists them")
        out.extend(h for h in hits if h not in out)
    return out


def change(data: bytes, modes_text: str, depth: int, on: bool) -> tuple[bytes, list[str]]:
    """The settings with depth (0: every depth) of those modes on or off, and what changed."""
    modes = parse_settings(data)
    out, changed = bytearray(data), []
    for m in _select(modes, modes_text):
        for d in m.depths:
            if depth and d.bits != depth:
                continue
            if d.on != on:
                flags = _long(out, d.offset)
                struct.pack_into(">I", out, d.offset, (flags | 1) if on else (flags & ~1))
                changed.append(f"{m.name} {d.bits} bit")
    return bytes(out), changed


NEED = re.compile(r"^\s*(\d+)\s*[x×]\s*(\d+)(?:\s*[x×]\s*(\d+))?\s*$", re.I)


def explain(modes: list[Mode], need: str) -> str:
    """Why a program may not get WIDTHxHEIGHT[xDEPTH], or that it is there."""
    m = NEED.match(need)
    if not m:
        raise SettingsError("need: WIDTHxHEIGHT or WIDTHxHEIGHTxDEPTH, e.g. 640x480x32")
    w, h, bits = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    if bits == 15 and not any(d.bits == 15 for x in modes for d in x.depths):
        bits = 16  # these settings keep 15 and 16 bit under one switch
    same = [x for x in modes if x.width == w and x.height == h]
    want = f"{w}x{h}" + (f" in {bits} bit" if bits else "")
    if not same:
        near = sorted({x.size for x in modes}, key=lambda s: abs(int(s.split('x')[0]) - w)
                      + abs(int(s.split('x')[1]) - h))[:3]
        return (f"{want}: there is no such resolution in the Picasso96 settings"
                + (f"; nearest: {', '.join(near)}" if near else "")
                + ". Add it with Picasso96Mode (Picasso96Prefs); Amigent only switches depths of existing modes.")
    lines = []
    for x in same:
        depths = [d for d in x.depths if not bits or d.bits == bits]
        if not depths:
            have = ", ".join(str(d.bits) for d in x.depths)
            lines.append(f"{x.name}: has no {bits} bit entry (it has {have} bit)")
            continue
        off = [d for d in depths if not d.on]
        on = [d for d in depths if d.on]
        if on:
            lines.append(f"{x.name}: switched on in {', '.join(str(d.bits) for d in on)} bit")
        if off:
            lines.append(f"{x.name}: switched off in {', '.join(str(d.bits) for d in off)} bit; "
                         f"amiga_screen_modes(action='on', modes='{x.size}'"
                         + (f", depth={bits}" if bits else "") + ", confirm=True) turns it on")
    return f"{want}:\n" + "\n".join(lines)
