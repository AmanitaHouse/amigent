"""Emu68 on a Raspberry Pi (#16, #17): what runs, its health, JIT settings at run time."""

import json

import pytest

import amigent.server as server
from amigent import emu68, notes
from amigent.channel import Commands
from amigent.errors import AmigaError
from fakeamiga import FakeAmiga

# Emu68's own start values: insn depth 256 (0), inline range 8191, loop count 8,
# soft flush on; CCR scan depth 20; soft flush limit 500.
JITCTRL = (0 << 24) | (8191 << 8) | (8 << 4) | 1
JITCTRL2 = 20 << 3

PI_LINES = {
    "idstring": "Emu68 1.0.4 (13.06.2026) git:abcdef0",
    "version": "1.0.4", "git": "abcdef0123456789", "variant": "pistorm32lite",
    "model": "Raspberry Pi 4 Model B Rev 1.4",
    "bootargs": "vc4.mem=16 sd.unit0=ro",
    "board_revision": "00c03114", "temp": "52500", "temp_max": "85000",
    "arm_clock": "1500000000", "arm_clock_measured": "1500000000", "arm_clock_max": "1500000000",
    "core_volt": "850000", "throttled": "00000000", "mailbox": "resource",
}


def pi(throttled="00000000"):
    fake = FakeAmiga()
    fake.protocol = 6
    fake.info.update(emu68="1", uptime="100", self="Work:amigent/amigentd")
    fake.emu68 = {0xEA: 500, 0xEB: JITCTRL, 0x1E0: JITCTRL2}
    fake.emu68_lines = dict(PI_LINES, throttled=throttled)
    return fake


@pytest.fixture
def on(machine_session):
    made = []

    def use(fake):
        made.append(fake)
        machine_session.ctl.close()
        machine_session.ctl = Commands("127.0.0.1", 1, fake.port)
        return fake
    yield use
    machine_session.ctl.close()
    for fake in made:
        fake.close()


# ---- the module

def info(**more):
    lines = {"emu68": "1", "jit_sfthresh": "500", "jitctrl": f"{JITCTRL:08x}", "jitctrl2": f"{JITCTRL2:08x}"}
    lines.update(more)
    return lines


def test_settings_decode_emu68s_start_values():
    s = emu68.settings(info())
    assert s["insn_depth"] == 256 and s["inline_range"] == 8191 and s["loop_count"] == 8
    assert s["soft_flush"] == 1 and s["ccr_depth"] == 20 and s["soft_flush_limit"] == 500
    assert s["chip_slowdown"] == 0 and s["chip_slowdown_spacing"] == 1 and s["blitter_wait"] == 0


def test_fields_touch_only_the_documented_bits():
    items = emu68.fields(emu68.requested({"sc": "on", "scs": 3, "dbf": 1, "bw": "yes", "icnt": 256, "lcnt": 16}))
    by_reg = {r: (v, m) for r, v, m in items}
    v, m = by_reg[0x1E0]
    assert v == 1 | 2 | (2 << 8) | (1 << 11) and m == 1 | 2 | (7 << 8) | (1 << 11)
    v, m = by_reg[0xEB]
    assert v == 0 and m == (0xFF << 24) | (0xF << 4)  # 256 and 16 are stored as 0
    for reg, value, mask in emu68.restore_fields({0xEA: 1, 0xEB: 0xFFFFFFFF, 0x1E0: 0xFFFFFFFF}):
        assert mask & ~{0xEA: 0xFFFFFFFF, 0xEB: 0xFFFFFFF1, 0x1E0: 0xFFB}[reg] == 0


def test_requested_checks_names_and_ranges():
    with pytest.raises(ValueError, match="unknown"):
        emu68.requested({"debug": 1})
    with pytest.raises(ValueError, match="from 1 to 8"):
        emu68.requested({"chip_slowdown_spacing": 9})
    with pytest.raises(ValueError, match="takes a number"):
        emu68.requested({"ccr_depth": "on"})


def test_insn_depth_one_needs_the_ccr_optimiser_off():
    current = emu68.settings(info())
    with pytest.raises(ValueError, match="ccr_depth=0"):
        emu68.check(current, {"insn_depth": 1})
    emu68.check(current, {"insn_depth": 1, "ccr_depth": 0})


def test_board_revision_and_throttling():
    assert emu68.board(0xC03114) == ("4B", 4096)
    assert emu68.board(0xA02082) == ("3B", 1024)
    assert emu68.board(0x0010) == ("", None)
    assert emu68.throttled(0x50005) == (["under-voltage", "throttled"], ["under-voltage", "throttled"])
    warn = emu68.health_warning({"emu68": "1", "throttled": "00050000"})
    assert "since power on: under-voltage, throttled" in warn and "power supply" in warn
    assert emu68.health_warning({"emu68": "1", "throttled": "00000000"}) == ""
    assert emu68.health_warning({"emu68": "0"}) == ""


def test_mips_from_two_readings():
    a = {"cntfrq": "1000000", "cnt_hi": "0", "cnt_lo": "0", "insn_hi": "0", "insn_lo": "0", "jit_cmiss": "10"}
    b = {"cntfrq": "1000000", "cnt_hi": "0", "cnt_lo": "f4240", "insn_hi": "0", "insn_lo": "5f5e100",
         "jit_cmiss": "5010"}
    rate = emu68.mips(a, b)
    assert rate["seconds"] == 1 and rate["m68k_mips"] == 100 and rate["misses_per_second"] == 5000
    assert "translator is kept busy" in emu68.mips_line(rate)


def test_describe_without_emu68_says_so_and_nothing_else():
    assert emu68.describe({"emu68": "0"}) == emu68.NOT_EMU68
    assert "not in this amigentd build" in emu68.describe({"emu68": "0", "why": "not in this amigentd build"})


def test_describe_names_pi_options_and_health():
    text = emu68.describe(info(**PI_LINES, jit_size="33554432", jit_free="16777216", jit_count="9",
                               jit_cmiss="5", insn_hi="0", insn_lo="10"))
    assert "Emu68 1.0.4" in text and "pistorm32lite" in text
    assert "Pi: Raspberry Pi 4 Model B Rev 1.4, 4 GB RAM" in text
    assert "vc4.mem=16 (VC4 memory for P96 (MB))" in text and "sd.unit0=ro" in text
    assert "52.5 °C" in text and "ARM 1500 MHz" in text and "no under-voltage" in text
    assert "JIT cache: 16.0 of 32.0 MB used" in text and "insn_depth=256" in text


def test_notes_carry_settings():
    assert emu68.from_notes(["stack 20000", "Emu68 JIT: chip_slowdown=1 dbf_slowdown=1"]) == {
        "chip_slowdown": 1, "dbf_slowdown": 1}
    assert emu68.from_notes(["stack 20000"]) == {}


def test_saved_values_are_dropped_after_a_restart(private_config):
    saved = emu68.saved_for("A1200")
    saved.keep({0xEB: 5}, 1000.0)
    assert saved.load(1030.0) == {0xEB: 5}
    assert saved.load(5000.0) is None  # the Amiga started again meanwhile
    assert saved.load(1000.0) is None


# ---- end to end with the fake amigentd

def test_tool_on_an_amiga_without_emu68(on):
    fake = on(FakeAmiga())
    fake.protocol = 6
    fake.info["emu68"] = "0"
    assert server.amiga_emu68() == emu68.NOT_EMU68
    assert server.amiga_emu68_jit("chip_slowdown=1") == emu68.NOT_EMU68
    assert fake.emu68_sets == []


def test_tool_on_an_older_amigentd(on):
    fake = on(FakeAmiga())
    fake.protocol = 6
    with pytest.raises(AmigaError, match="amigentd 1.5.0"):
        server.amiga_emu68()


def test_tool_tells_what_runs(on):
    on(pi())
    text = server.amiga_emu68()
    assert "Emu68 1.0.4" in text and "Raspberry Pi 4" in text and "soft_flush=1" in text


def test_status_warns_of_under_voltage(on, monkeypatch):
    on(pi(throttled="00050000"))
    monkeypatch.setattr(server, "_system_facts", lambda: {})
    monkeypatch.setattr(server.others, "scan", lambda *a: [])
    report = json.loads(server.amiga_status())
    assert "under-voltage" in report["pi_warning"] and report["emu68"].startswith("Emu68 1.0.4")


def test_status_without_emu68_says_nothing_about_it(on, monkeypatch):
    fake = on(FakeAmiga())
    fake.protocol = 6
    fake.info["emu68"] = "0"
    monkeypatch.setattr(server, "_system_facts", lambda: {})
    monkeypatch.setattr(server.others, "scan", lambda *a: [])
    report = json.loads(server.amiga_status())
    assert "emu68" not in report and "pi_warning" not in report
    assert fake.counts.get(48, 0) == 0


def test_set_then_restore(on):
    fake = on(pi())
    text = server.amiga_emu68_jit("chip_slowdown=1 dbf=1 ccrd=0")
    assert "set: chip_slowdown=1 dbf_slowdown=1 ccr_depth=0" in text
    assert fake.emu68[0x1E0] == 1 | 2 and fake.emu68[0xEB] == JITCTRL
    server.amiga_emu68_jit("blitter_wait=1")  # the first values stay the ones to go back to
    assert "before the first change: chip_slowdown=0" in server.amiga_emu68_jit()
    assert "put back" in server.amiga_emu68_jit(restore=True)
    assert fake.emu68[0x1E0] == JITCTRL2 and fake.emu68[0xEB] == JITCTRL
    assert "nothing to take back" in server.amiga_emu68_jit(restore=True)


def test_refuses_what_emu68_warns_about(on):
    fake = on(pi())
    with pytest.raises(AmigaError, match="ccr_depth=0"):
        server.amiga_emu68_jit("icnt=1")
    assert fake.emu68_sets == []


def test_program_runs_between_two_settings_and_is_remembered(on, monkeypatch):
    on(pi())
    started = {}
    monkeypatch.setattr(server, "_start_job", lambda command, title="": started.update(command=command) or 7)
    monkeypatch.setattr(server, "_wait_job", lambda number, wait: "done\n")
    text = server.amiga_emu68_jit("sc=1 dbf=1", program="Games:Old/Old", remember=True)
    lines = started["command"].splitlines()[1:]
    assert started["command"].startswith("FailAt ")
    assert lines[0] == '"Work:amigent/amigentd" EMU68JIT 1e0:3:3'
    assert lines[1] == "Games:Old/Old"
    assert lines[2].startswith('"Work:amigent/amigentd" EMU68JIT ea:1f4:ffffffff,eb:')
    assert f"1e0:{JITCTRL2:x}:ffb" in lines[2]
    assert "job 7" in text and "noted for 'old'" in text
    assert notes.for_amiga(server._amiga()).get("old") == ["Emu68 JIT: chip_slowdown=1 dbf_slowdown=1"]
    # next time the note is enough
    server.amiga_emu68_jit(program="Games:Old/Old")
    assert started["command"].splitlines()[1].endswith("EMU68JIT 1e0:3:3")


def test_cpu_adds_mips_under_emu68(on, monkeypatch):
    on(pi())
    monkeypatch.setattr(server._session().ctl.__class__, "cpu",
                        lambda self, s, ms: ["N\t100\t10\t50\t0"], raising=False)
    monkeypatch.setattr(server, "_tasks", lambda: [])
    readings = iter([
        {"emu68": "1", "cntfrq": "1000000", "cnt_hi": "0", "cnt_lo": "0", "insn_hi": "0", "insn_lo": "0"},
        {"emu68": "1", "cntfrq": "1000000", "cnt_hi": "0", "cnt_lo": "f4240", "insn_hi": "0",
         "insn_lo": "5f5e100"},
    ])
    monkeypatch.setattr(server, "_emu68_info", lambda counters=False: next(readings))
    assert "Emu68: 100.0 million 68k instructions a second" in server.amiga_cpu(1)


def test_amigentd_allows_exactly_the_fields_offered_here():
    from pathlib import Path
    import re
    daemon = (Path(__file__).parent.parent / "amiga" / "amigentd.c").read_text(encoding="latin-1")
    masks = {}
    for s in emu68.SETTINGS:
        masks[s.reg] = masks.get(s.reg, 0) | s.mask
    assert int(re.search(r"E68_CTRL_MASK (0x[0-9A-F]+)UL", daemon).group(1), 16) == masks[emu68.JITCTRL]
    assert int(re.search(r"E68_CTRL2_MASK (0x[0-9A-F]+)UL", daemon).group(1), 16) == masks[emu68.JITCTRL2]
    assert masks[emu68.SFTHRESH] == 0xFFFFFFFF
    # no control register is read before Emu68 was recognised
    text = daemon[daemon.index("static void emu68_text"):]
    assert text.index("emu68_present()") < text.index("emu68_read(r)")
