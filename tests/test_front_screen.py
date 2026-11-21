"""1.5.0 (#44): the screen really on display, pictures of screens behind, and
memory read by a running program's hunk."""

import threading

import pytest
from PIL import Image

import amigent.server as server
from amigent import memory
from amigent.amigentd import Amigentd, AmigentdError
from amigent.errors import AmigaError

from fakeamiga import FakeAmiga

KNOWN = 0x8000  # SCREENS: the display bits are filled in
WB, PT = 0x0A001000, 0x0A002000


def screen(handle, title, w, h, front=False, rtg=False, chip=False, foreign=False, known=True):
    return {"handle": handle, "title": title, "width": w, "height": h, "depth": 8, "front": front,
            "workbench": title == "Workbench", "rtg": rtg, "ham": False, "display": known,
            "chip_shown": chip if known else None, "in_view": chip if known else None,
            "foreign_view": foreign if known else None}


# ---- what the reply says about the display


def test_an_old_amigentd_says_nothing_about_the_display():
    assert server.display_note([screen(WB, "Workbench", 1920, 1080, front=True, rtg=True, known=False),
                                screen(PT, "Tracker", 640, 256, known=False)]) == ""


def test_a_card_workbench_with_a_chipset_screen_behind_names_both():
    note = server.display_note([screen(WB, "Workbench", 1920, 1080, front=True, rtg=True),
                                screen(PT, "Tracker", 640, 256, chip=True)])
    assert "chipset output shows 'Tracker' (640x256, chipset, 0x0a002000)" in note
    assert "amiga_screenshot(screen='0x0a002000')" in note


def test_a_card_workbench_alone_needs_no_note():
    assert server.display_note([screen(WB, "Workbench", 1920, 1080, front=True, rtg=True)]) == ""


def test_a_chipset_screen_in_front_names_what_the_card_still_shows():
    note = server.display_note([screen(PT, "Tracker", 640, 256, front=True, chip=True),
                                screen(WB, "Workbench", 1920, 1080, rtg=True)])
    assert "graphics card" in note and "'Workbench' (1920x1080" in note
    assert "chipset output" not in note


def test_a_view_of_its_own_is_said_instead_of_the_workbench():
    note = server.display_note([screen(PT, "Tracker", 640, 256, front=True, foreign=True)])
    assert "no Intuition screen" in note and "LoadView" in note and "'Tracker'" in note
    note = server.display_note([screen(WB, "Workbench", 1920, 1080, front=True, rtg=True, foreign=True)])
    assert "chipset output shows a display that is no Intuition screen" in note


def test_a_front_screen_outside_the_view_is_said():
    note = server.display_note([screen(PT, "Tracker", 640, 256, front=True),
                                screen(WB, "Workbench", 640, 256, chip=True)])
    assert "front screen is not in the chipset's view" in note and "'Workbench'" in note


# ---- the screen client against a pretend amigentd


@pytest.fixture
def amiga():
    fake = FakeAmiga(Image.new("RGB", (320, 128), (170, 170, 170)))
    yield fake
    fake.close()


def two_screens(fake, flags_front=1 | 2 | 4 | KNOWN, flags_back=16 | 32 | KNOWN):
    fake.screen_list = [
        {"handle": WB, "title": "Workbench", "flags": flags_front, "picture": fake.picture},
        {"handle": PT, "title": "Tracker", "flags": flags_back,
         "picture": Image.new("RGB", (640, 256), (0, 0, 200))},
    ]


def test_screens_carry_the_display_bits(amiga):
    two_screens(amiga, flags_front=1 | 2 | 4 | KNOWN | 0x4000)
    found = Amigentd("127.0.0.1", amiga.port, timeout=5).screens()
    assert found[0]["rtg"] and found[0]["display"] and found[0]["foreign_view"]
    assert found[1]["chip_shown"] and found[1]["in_view"] and not found[1]["front"]


def test_a_screen_behind_is_read_without_moving_it(amiga):
    two_screens(amiga)
    client = Amigentd("127.0.0.1", amiga.port, timeout=5)
    back = client.screens()[1]
    image = client.capture_screen(back)
    assert image.size == (640, 256) and image.getpixel((10, 10)) == (0, 0, 200)
    assert amiga.counts.get(12) == 2  # aimed, then back to the front; nothing came forward
    front = client.capture_rgb(0, 0, 32, 32)
    assert front.getpixel((1, 1)) == (170, 170, 170)


def test_an_old_amigentd_is_never_asked_to_aim(amiga):
    client = Amigentd("127.0.0.1", amiga.port, timeout=5)
    back = dict(client.screens()[0], front=False)
    assert back["display"] is False and back["chip_shown"] is None
    with pytest.raises(AmigentdError, match="only picture the front screen"):
        client.capture_screen(back)
    assert 12 not in amiga.counts  # SCREEN_FRONT with the aim bit would bring it forward


def tools(monkeypatch, fake):
    client = Amigentd("127.0.0.1", fake.port, timeout=5)
    monkeypatch.setattr(server._session(), "screen", client)
    monkeypatch.setattr(server._session(), "last_shot", None)
    monkeypatch.setattr(server, "_paused_note", lambda: "")
    monkeypatch.setattr(server, "_exclusive", lambda name=None: threading.Lock())
    return client


def test_amiga_screenshot_takes_a_screen_behind_by_title(amiga, monkeypatch):
    two_screens(amiga)
    tools(monkeypatch, amiga)
    note, picture = server.amiga_screenshot(screen="Tracker")
    assert "'Tracker' 640x256, behind the front one" in note and picture.data
    with pytest.raises(AmigaError, match="0 screens match"):
        server.amiga_screenshot(screen="nothing like it")


def test_amiga_screenshot_of_the_front_says_what_else_is_on_display(amiga, monkeypatch):
    two_screens(amiga)
    tools(monkeypatch, amiga)
    note = server.amiga_screenshot()[0]
    assert note.startswith("screen 320x128") and "chipset output shows 'Tracker'" in note
    assert "chipset-output 'Tracker'" in server.amiga_screens()


def test_amiga_screenshot_on_an_old_amigentd_is_as_before(amiga, monkeypatch):
    tools(monkeypatch, amiga)
    note = server.amiga_screenshot()[0]
    assert note.startswith("screen 320x128") and "\n" not in note


# ---- memory by task and hunk

LOADED = [
    "L\texec.library\t47\t99\t40\t00000ac0\t1032\t632\texec 47.99",
    "H\tProTracker\tSYS:Utilities/ProTracker/ProTracker\t0\t0a300004\t1000",
    "H\tProTracker\tSYS:Utilities/ProTracker/ProTracker\t1\t0a400004\t512",
    "H\tShell Process\tC:Twin\t0\t0a500004\t100",
    "H\tShell Process\tC:Twin\t0\t0a600004\t100",
]
TASKS = [
    "T\t0a010000\tProTracker\tSYS:Utilities/ProTracker/ProTracker\tprocess\t0\twait\t8192\t400\t0\t0",
    "T\t0a020000\tShell Process\tC:Twin\tprocess\t0\twait\t4096\t300\t0\t0",
]


class Ctl:
    def __init__(self):
        self.peeks = []

    def loaded(self):
        return LOADED

    def tasks(self):
        return TASKS

    def peek(self, at, n):
        self.peeks.append((at, n))
        return bytes(range(256)) * (n // 256) + bytes(range(n % 256))


@pytest.fixture
def ctl(monkeypatch):
    fake = Ctl()
    monkeypatch.setattr(server._session(), "ctl", fake)
    monkeypatch.setattr(server, "_with_ctl", lambda f: f())
    return fake


def test_hunk_text_and_offsets_parse():
    assert memory.split_hunk("ProTracker:hunk1+$120") == ("ProTracker", 1, 0x120)
    assert memory.split_hunk("ProTracker hunk 1 +$120") == ("ProTracker", 1, 0x120)
    assert memory.split_hunk("$0A12B4C0") is None
    assert [memory.parse_offset(v) for v in ("$120", "0x120", "288", 288, "")] == [288, 288, 288, 288, 0]
    with pytest.raises(ValueError):
        memory.parse_offset("12z")


def test_hunks_are_grouped_per_program():
    loaded = memory.parse(LOADED)
    assert [len(g) for g in memory.programs(loaded)] == [2, 1, 1]
    assert memory.find_hunk(loaded, "protracker", 1).start == 0x0A400004
    with pytest.raises(ValueError, match="hunks 0 to 1, no hunk 2"):
        memory.find_hunk(loaded, "ProTracker", 2)
    with pytest.raises(ValueError, match="2 running programs match"):
        memory.find_hunk(loaded, "Twin", 0)


def test_amiga_memory_reads_by_hunk_text(ctl):
    out = server.amiga_memory("ProTracker:hunk1+$120", size=16)
    assert out.startswith("$0A400124 (SYS:Utilities/ProTracker/ProTracker hunk 1 +$120)")
    assert ctl.peeks == [(0x0A400124, 16)]


def test_amiga_memory_reads_by_task_hunk_and_offset(ctl):
    server.amiga_memory(task="ProTracker", hunk=1, offset="$120", size=16)
    server.amiga_memory(task="$0A010000", hunk=0, offset="16", size=4)
    assert ctl.peeks == [(0x0A400124, 16), (0x0A300014, 4)]


def test_amiga_memory_stays_inside_the_hunk(ctl):
    out = server.amiga_memory(task="ProTracker", hunk=1, offset="$1F0", size=256)
    assert ctl.peeks == [(0x0A4001F4, 16)] and "16 bytes, up to the end of hunk 1" in out
    with pytest.raises(AmigaError, match=r"\$200 bytes; offset \$200 is outside it"):
        server.amiga_memory(task="ProTracker", hunk=1, offset="$200")
    with pytest.raises(AmigaError, match="outside it"):
        server.amiga_memory("ProTracker hunk 1 +$400")


def test_amiga_memory_says_what_is_missing(ctl):
    with pytest.raises(AmigaError, match="go together"):
        server.amiga_memory(task="ProTracker")
    with pytest.raises(AmigaError, match="not both"):
        server.amiga_memory("$0A400004", task="ProTracker", hunk=0)
    with pytest.raises(AmigaError, match="counts from a hunk"):
        server.amiga_memory("$0A400004", offset="$10")
    with pytest.raises(AmigaError, match="give the task's address"):
        server.amiga_memory(task="Twin", hunk=0)
    with pytest.raises(AmigaError, match="no task at"):
        server.amiga_memory(task="$0A0F0000", hunk=0)
    assert ctl.peeks == []
