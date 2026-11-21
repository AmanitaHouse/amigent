"""#22: graphics board, driver and 3D libraries; Picasso96 screen modes; a gentler
screen loop on a Zorro II card. With fake Amigas and a made-up settings file."""

import struct

import pytest

import amigent.server as server
from amigent import graphics, memory, screenfeed
from amigent.client import ExecResult
from amigent.errors import AmigaError
from test_amigus import EXPANSION, Memory, lines

BOARDS = (0x9000, 0x9100, 0x9200)
CARD_LIB, RTG_LIB, CGX_LIB, W3D_LIB = 0xA000, 0xA100, 0xA200, 0xA300


def chunk(cid: bytes, body: bytes) -> bytes:
    return cid + struct.pack(">I", len(body)) + body + (b"\0" if len(body) & 1 else b"")


def mode(board: str, w: int, h: int, on: dict) -> bytes:
    name = f"{board}:{w}x{h}".encode()
    out = chunk(b"RSHD", b"P9\x10\x00" + struct.pack(">HHHHH", w, h, 1, 0, 2) + name.ljust(22, b"\0"))
    for bits, enabled in on.items():
        out += chunk(b"MIHD", struct.pack(">IHHB", (0x100 if bits == 24 else 0) | enabled, w, h, bits)
                     + bytes([0x18, 1, 0x20]) + bytes(22))
    return out


def settings(*boards) -> bytes:
    body = b"P96S" + chunk(b"ANNO", b"p96p") + chunk(b"STHD", bytes(38))
    for name, modes in boards:
        body += chunk(b"MNTR", b"Generic".ljust(48, b"\0")) + chunk(b"BDNM", name.encode().ljust(32, b"\0"))
        for m in modes:
            body += mode(name, *m)
    return b"FORM" + struct.pack(">I", len(body)) + body


SETTINGS = settings(("VideoCore", [(640, 480, {8: 1, 16: 1, 24: 1, 32: 0}),
                                   (1920, 1080, {8: 1, 16: 1, 24: 1, 32: 0})]))


def test_modes_and_depths_are_listed():
    modes = graphics.parse_settings(SETTINGS)
    assert [(m.board, m.size) for m in modes] == [("VideoCore", "640x480"), ("VideoCore", "1920x1080")]
    text = graphics.listing(modes)
    assert "board VideoCore" in text and "640x480" in text and " 8x 16x 24x 32-" in text


def test_switching_one_depth_flips_only_its_bit():
    new, changed = graphics.change(SETTINGS, "640x480", 32, True)
    assert changed == ["VideoCore:640x480 32 bit"] and len(new) == len(SETTINGS)
    assert sum(a != b for a, b in zip(new, SETTINGS)) == 1
    again = graphics.parse_settings(new)
    assert [d.on for d in again[0].depths] == [True] * 4 and not again[1].depths[3].on
    off, changed = graphics.change(new, "all", 24, False)
    assert changed == ["VideoCore:640x480 24 bit", "VideoCore:1920x1080 24 bit"]
    flags = [struct.unpack_from(">I", off, d.offset)[0] for m in graphics.parse_settings(off)
             for d in m.depths if d.bits == 24]
    assert flags == [0x100, 0x100]  # the other flag bits stay


def test_unknown_mode_and_broken_file_are_refused():
    with pytest.raises(graphics.SettingsError, match="no screen mode '800x600'"):
        graphics.change(SETTINGS, "800x600", 0, True)
    with pytest.raises(graphics.SettingsError, match="FORM P96S"):
        graphics.parse_settings(b"FORM\0\0\0\4ILBM")
    with pytest.raises(graphics.SettingsError, match="runs past"):
        graphics.parse_settings(SETTINGS[:-10])


def test_a_missing_mode_is_explained():
    modes = graphics.parse_settings(SETTINGS)
    off = graphics.explain(modes, "640x480x32")
    assert "switched off in 32 bit" in off and "action='on', modes='640x480', depth=32" in off
    assert "switched on in 16 bit" in graphics.explain(modes, "640x480x15")
    assert "no such resolution" in graphics.explain(modes, "800x600") and "nearest: 640x480" in \
        graphics.explain(modes, "800x600")


def amiga(*boards):
    """boards: (manufacturer, product, zorro3)."""
    m = Memory()
    m.put(EXPANSION, bytes(100))
    nodes = BOARDS[:len(boards)]
    for node, (manuf, product, z3) in zip(nodes, boards):
        cd = bytearray(48)
        cd[16] = 0x80 if z3 else 0xC0
        cd[17] = product
        struct.pack_into(">H", cd, 20, manuf)
        struct.pack_into(">II", cd, 32, 0x00200000, 0x00400000)
        m.put(node, bytes(cd))
    m.exec_list(EXPANSION + graphics.BOARD_LIST, nodes)
    return m


def lib(name, version, base, id_string=""):
    return f"L\t{name}\t{version}\t1\t1\t{base:08x}\t30\t100\t{id_string}"


P96 = lib("rtg.library", 42, RTG_LIB)


def test_videocore_is_picasso96_on_a_fast_bus():
    info = graphics.detect(memory.parse(lines(P96, lib("VideoCore.card", 1, CARD_LIB))), amiga().peek)
    text = graphics.describe(info)
    assert info.system == "Picasso96" and not info.slow_bus
    assert "driver VideoCore.card 1.1: PiStorm" in text and "fast local bus" in text
    assert "Not tested" not in text and "no Warp3D or MiniGL" in text


def test_picasso_ii_on_zorro_ii_is_a_slow_bus_and_named_untested():
    m = amiga((0x0877, 0x0B, False), (0x0877, 0x0C, False), (0x0201, 0x01, False))
    info = graphics.detect(memory.parse(lines(P96, lib("PicassoII.card", 7, CARD_LIB))), m.peek)
    text = graphics.describe(info)
    assert info.slow_bus and len(info.boards) == 2  # the unknown board is not listed
    assert "Zorro board: Picasso II (Cirrus Logic GD5426/28), Zorro II" in text
    assert "Not tested with Amigent: Picasso II" in text
    assert "smaller pieces" in text


def test_zz9000_keeps_its_encoder_and_zorro_iii_is_not_slow():
    zz = graphics.detect(memory.parse(lines(P96, lib("ZZ9000.card", 1, CARD_LIB))),
                         amiga((0x6D6E, 0x03, False)).peek)
    assert zz.zz9000 and not zz.slow_bus and "own encoder" in graphics.describe(zz)
    cv = graphics.detect(memory.parse(lines(P96)), amiga((0x2140, 0x22, True)).peek)
    assert not cv.slow_bus and "CyberVision 64" in graphics.describe(cv)


def test_cybergraphx_is_recognised_only():
    loaded = memory.parse(lines(lib("cybergraphics.library", 41, CGX_LIB, "cybergraphics 41.7")))
    text = graphics.describe(graphics.detect(loaded, amiga().peek))
    assert "RTG system: CyberGraphX (cybergraphics.library 41.1 (cybergraphics 41.7))" in text
    assert "recognised only" in text


def test_chipset_only_and_an_old_daemon():
    assert "chipset screens only" in graphics.describe(graphics.detect(memory.parse(lines()), amiga().peek))
    text = graphics.describe(graphics.detect(None))
    assert "before 1.4.0" in text and "chipset screens only" not in text


def test_3d_in_memory_on_disk_and_its_drivers():
    loaded = memory.parse(lines(P96, lib("Warp3D.library", 4, W3D_LIB, "Warp3D 4.2 (Wazp3D)")))
    runs = []

    def run(command):
        runs.append(command)
        return (0, "minigl.library 30.0\n") if "minigl" in command else (20, "")
    listdir = lambda path: [{"type": "DIR", "name": "HWdrivers"},  # noqa: E731
                            {"type": "FILE", "name": "HWdrivers/W3D_Permedia2.library"}]
    text = graphics.describe(graphics.detect(loaded, amiga().peek, run, listdir))
    assert "Warp3D.library 4.1 (in memory), Wazp3D" in text
    assert "minigl.library 30.0 (in LIBS:, not loaded)" in text
    assert "W3D_Permedia2.library" in text and runs == ["Version FILE LIBS:minigl.library"]


class Ctl:
    def __init__(self, files):
        self.files = files

    def read_file(self, path):
        if path not in self.files:
            raise AmigaError("object not found", code=205)
        return self.files[path]

    def write_file(self, path, data, append=False):
        self.files[path] = data

    def exec(self, command, cd=None, timeout=None):
        return ExecResult(20, "")

    def list_dir(self, path, recursive=False):
        raise AmigaError("object not found")

    def peek(self, address, n):
        return amiga((0x0877, 0x0B, False)).peek(address, n)


@pytest.fixture
def ctl(monkeypatch):
    c = Ctl({graphics.SETTINGS: SETTINGS})
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    monkeypatch.setattr(server._session(), "ctl", c)
    return c


def test_the_tool_asks_before_it_changes_and_undoes_in_one_call(ctl):
    assert "640x480" in server.amiga_screen_modes()
    preview = server.amiga_screen_modes("on", "640x480", 32)
    assert preview.startswith("would switch on: VideoCore:640x480 32 bit") and ctl.files[graphics.SETTINGS] == SETTINGS
    done = server.amiga_screen_modes("on", "640x480", 32, confirm=True)
    assert "restart" in done and ctl.files[graphics.UNDO] == SETTINGS == ctl.files[graphics.ORIGINAL]
    changed = ctl.files[graphics.SETTINGS]
    assert graphics.parse_settings(changed)[0].depths[3].on
    server.amiga_screen_modes("off", "1920x1080", 8, confirm=True)
    assert ctl.files[graphics.ORIGINAL] == SETTINGS and ctl.files[graphics.UNDO] == changed
    assert "confirm=True" in server.amiga_screen_modes("undo")
    server.amiga_screen_modes("undo", confirm=True)
    assert ctl.files[graphics.SETTINGS] == changed
    assert server.amiga_screen_modes("on", "640x480", 32) == "nothing to change: those modes are already on"
    assert "switched on in 32 bit" in server.amiga_screen_modes(need="640x480x32")


def test_the_tool_without_picasso96(ctl):
    del ctl.files[graphics.SETTINGS]
    with pytest.raises(AmigaError, match="Picasso96 is not installed"):
        server.amiga_screen_modes()
    assert server.amiga_screen_modes  # still registered


def test_the_screenshot_note_comes_once_for_a_zorro_ii_card(ctl, monkeypatch):
    monkeypatch.setattr(server, "_loaded", lambda: memory.parse(lines(P96, lib("PicassoII.card", 7, CARD_LIB))))
    session = server._session()
    monkeypatch.setattr(session, "slow_bus_told", False)
    assert "Zorro II" in server.amiga_graphics()
    assert "Zorro II" in server._slow_bus_note((0, 0, 0, 0))
    assert server._slow_bus_note((0, 0, 0, 0)) == ""
    session.graphics = None


def test_the_screen_loop_takes_smaller_pieces_on_a_slow_bus():
    planner = screenfeed.Planner()
    assert planner.piece_tiles(False, True) == 1 << 16
    planner.slow_bus = True
    assert planner.piece_tiles(False, True) == screenfeed.SLOW_BUS_PIECE
    planner.rate = 1e9
    assert planner.piece_tiles(True, False) == screenfeed.SLOW_BUS_PIECE
