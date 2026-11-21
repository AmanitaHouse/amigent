"""Stage 4 D3 — offline POKE fail-closed / resource / MMIO write-refuse (no hardware)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from amigent import channel
from amigent.channel import feature_opcode
from amigent.errors import AmigaError

ROOT = Path(__file__).resolve().parents[1]
DAEMON = (ROOT / "src/native/amiga/daemon/amigentd.c").read_text(encoding="utf-8")
MMIO = (ROOT / "src/native/amiga/platform/apollo/apollo_mmio.c").read_text(encoding="utf-8")
SERVER = (ROOT / "src/amigent/server.py").read_text(encoding="utf-8")


def function_body(src: str, name: str) -> str:
    marker = f"{name}("
    start = src.index(marker)
    nxt = src.index("\nstatic ", start + len(marker))
    return src[start:nxt]


def mmio_windows():
    body = MMIO.split("win[][2] = {", 1)[1].split("};", 1)[0]
    return [
        (int(a, 16), int(b, 16))
        for a, b in re.findall(r"0x([0-9A-Fa-f]+)UL\s*,\s*0x([0-9A-Fa-f]+)UL", body)
    ]


def mmio_hit(at: int, n: int, windows) -> bool:
    at &= 0xFFFFFFFF
    n &= 0xFFFFFFFF
    if n == 0 or (at + n) & 0xFFFFFFFF < at:
        return True
    end = (at + n) & 0xFFFFFFFF
    return any(at < stop and end > start for start, stop in windows)


def test_c_poke_bounds_then_allowpoke_before_allocvec_before_copymem():
    poke = function_body(DAEMON, "c_poke")
    assert "PEEK_MAX" in poke
    assert "!n || n > PEEK_MAX" in poke or "n > PEEK_MAX" in poke
    assert "!allow_poke" in poke
    assert "AllocVec" in poke
    assert "apollo_mmio_hit(at, n)" in poke
    assert "CopyMem(data, (APTR)at, n)" in poke
    assert poke.index("PEEK_MAX") < poke.index("!allow_poke")
    assert poke.index("!allow_poke") < poke.index("AllocVec")
    assert poke.index("AllocVec") < poke.index("CopyMem(data, (APTR)at, n)")
    assert poke.index("apollo_mmio_hit") < poke.index("CopyMem(data, (APTR)at, n)")
    assert poke.index("peek_allowed") < poke.index("CopyMem(data, (APTR)at, n)")


def test_c_poke_refuse_allowpoke_skips_wire_without_alloc():
    poke = function_body(DAEMON, "c_poke")
    refuse = poke.split("if (!allow_poke)", 1)[1].split("if (!(data = AllocVec", 1)[0]
    assert "l_skip" in refuse
    assert "AllocVec" not in refuse
    assert "CopyMem" not in refuse
    assert "c_fail" in refuse


def test_c_poke_oversized_or_zero_skips_before_alloc():
    poke = function_body(DAEMON, "c_poke")
    bound = poke.split("PEEK_MAX", 1)[1].split("if (!allow_poke)", 1)[0]
    assert "l_skip" in bound
    assert "AllocVec" not in bound


def test_c_poke_alloc_failure_skips_and_faults():
    poke = function_body(DAEMON, "c_poke")
    fail = poke.split("if (!(data = AllocVec", 1)[1].split("if (!l_recv", 1)[0]
    assert "l_skip" in fail
    assert "ERROR_NO_FREE_STORE" in fail


def test_c_poke_l_recv_failure_frees_temp():
    poke = function_body(DAEMON, "c_poke")
    recv_fail = poke.split("if (!l_recv(l, data, n, IO_SECONDS))", 1)[1].split("#ifdef", 1)[0]
    assert "FreeVec(data)" in recv_fail
    assert "CopyMem" not in recv_fail


def test_c_poke_mmio_and_rom_refuse_free_after_recv():
    poke = function_body(DAEMON, "c_poke")
    for marker in ("apollo_mmio_hit(at, n)", "at >= 0xF80000UL"):
        block = poke.split(marker, 1)[1].split("}", 1)[0]
        assert "FreeVec(data)" in block
        assert "CopyMem" not in block


def test_c_poke_refuses_rom_even_with_allowpoke_path():
    poke = function_body(DAEMON, "c_poke")
    assert "at >= 0xF80000UL" in poke
    assert poke.index("!allow_poke") < poke.index("at >= 0xF80000UL")
    assert poke.index("at >= 0xF80000UL") < poke.index("CopyMem(data, (APTR)at, n)")


def test_d2_protected_addresses_are_mmio_hits_for_writes():
    windows = mmio_windows()
    for at, n in ((0xDFF3FC, 2), (0xDFF1F4, 2), (0xDFF400, 2), (0xDFF3FC, 4)):
        assert mmio_hit(at, n, windows)


def test_zero_length_is_mmio_hit_and_daemon_bounds_n():
    windows = mmio_windows()
    assert mmio_hit(0x200000, 0, windows)
    poke = function_body(DAEMON, "c_poke")
    assert "!n || n > PEEK_MAX" in poke or "n > PEEK_MAX" in poke


def test_wraparound_hit_refuses_write_window_bypass():
    windows = mmio_windows()
    assert mmio_hit(0xFFFFFFFE, 4, windows)
    assert mmio_hit(0xDFF1F2, 4, windows)


def test_client_poke_is_protocol6_only_and_size_bounded():
    src = Path(channel.__file__).read_text(encoding="utf-8")
    poke = src.split("def poke(self", 1)[1].split("\n    def ", 1)[0]
    assert "_need6" in poke
    assert "PEEK_MAX" in poke
    assert channel.POKE == 42


def test_client_rejects_empty_and_oversized_poke_payload():
    class Dummy(channel.AmigaChannel):
        def __init__(self):
            pass

        def _need6(self, _what):
            return None

        def _one(self, *_a, **_k):
            raise AssertionError("must not send")

    d = Dummy()
    with pytest.raises(AmigaError):
        d.poke(0x200000, b"")
    with pytest.raises(AmigaError):
        d.poke(0x200000, b"\0" * (channel.PEEK_MAX + 1))


def test_feature_opcode_exposes_poke_without_checking_sysinfo_flag():
    assert feature_opcode(6, "POKE", {"poke": "0"}) == 42
    assert feature_opcode(6, "POKE", {}) == 42
    assert feature_opcode(5, "POKE", {"poke": "1"}) is None


def test_sysinfo_advertises_poke_from_allow_poke_flag():
    assert 't_pair(&t, "poke", allow_poke)' in DAEMON
    assert "ALLOWPOKE/S" in DAEMON


def test_cmd_poke_dispatch_has_no_inline_write():
    dispatch = DAEMON.split("case CMD_POKE:", 1)[1].split("case CMD_", 1)[0]
    assert "c_poke(" in dispatch
    assert "CopyMem" not in dispatch


def test_mcp_memory_write_documents_allowpoke_and_uses_ctl_poke():
    assert "ALLOWPOKE" in SERVER.split("def amiga_memory_write", 1)[1].split("def amiga_", 1)[0]
    tool = SERVER.split("def amiga_memory_write", 1)[1].split("\n@mcp.tool", 1)[0]
    assert "ctl.poke" in tool
    assert "ctl.peek" in tool


def test_allow_poke_only_set_from_startup_flags():
    assigns = re.findall(r"allow_poke\s*=\s*[^;]+;", DAEMON)
    assert any("TRUE" in a or "args[" in a for a in assigns)
    joined = " ".join(assigns).lower()
    assert "tls" not in joined
    assert "authed" not in joined


def test_l_recv_uses_bounded_io_seconds():
    assert "#define IO_SECONDS 30" in DAEMON
    poke = function_body(DAEMON, "c_poke")
    assert "IO_SECONDS" in poke
    recv = function_body(DAEMON, "l_recv")
    assert "l_wait" in recv


def test_d2_address_class_rules_still_forbid_rom_as_test_ram():
    text = (ROOT / "docs/APOLLO_V4_STAGE4_SAFETY_ASSESSMENT.md").read_text(encoding="utf-8")
    assert "test-owned allocated RAM" in text
    assert "mandatory NO-GO" in text or "mandatory **NO-GO**" in text


def test_matrix_records_d3_offline_without_claiming_hw_poke():
    m = json.loads((ROOT / "tests/hardware/apollo_v4_matrix.json").read_text(encoding="utf-8"))
    hc = m["hardware_coverage"]
    assert hc["POKE_ALLOWPOKE"] == "NOT_TESTED"
    assert "offline" in hc["stage4_d3_status"]
    assert "D3_POKE_SAFETY_REVIEW" in hc["stage4_d3_poke_safety_review"]
    assert hc["stage4"]["d3_hardware"] == "NO_GO_not_authorised"
