"""Stage 4 D2 — offline MMIO PEEK refusal proof (no hardware access)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from amigent import channel

ROOT = Path(__file__).resolve().parents[1]
DAEMON = (ROOT / "src/native/amiga/daemon/amigentd.c").read_text(encoding="utf-8")
MMIO = (ROOT / "src/native/amiga/platform/apollo/apollo_mmio.c").read_text(encoding="utf-8")


def function_body(src: str, name: str) -> str:
    marker = f"{name}("
    start = src.index(marker)
    nxt = src.index("\nstatic ", start + len(marker))
    return src[start:nxt]


def mmio_windows() -> list[tuple[int, int]]:
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

# Frozen D2 cases — must match docs/APOLLO_V4_STAGE4_D2_ADDRESS_SAFETY_REVIEW.md
D2_PROTECTED = [
    ("D2-P1", 0x00DFF3FC, 2, (0x00DFF3EA, 0x00DFF3FE)),  # VREG_BOARD in system window
    ("D2-P2", 0x00DFF1F4, 2, (0x00DFF1F4, 0x00DFF1F6)),  # GFXMODE
    ("D2-P3", 0x00DFF400, 2, (0x00DFF400, 0x00DFF500)),  # ARNE channel page
]
D2_CONTROL = [
    ("D2-C1", 0x00F80000, 4),  # Kickstart ROM — peek_allowed ROM window
    ("D2-C2", 0x00000004, 4),  # ExecBase vector slot — end < 0x400
]

REFUSE_TEXT = "that range includes Apollo registers that a read can change"


def test_all_eight_mmio_windows_are_present():
    windows = mmio_windows()
    assert len(windows) == 8
    assert windows == [
        (0x00DFF1E6, 0x00DFF1E8),
        (0x00DFF1EC, 0x00DFF1F0),
        (0x00DFF1F4, 0x00DFF1F6),
        (0x00DFF254, 0x00DFF258),
        (0x00DFF3B0, 0x00DFF3C4),
        (0x00DFF3D0, 0x00DFF3E4),
        (0x00DFF3EA, 0x00DFF3FE),
        (0x00DFF400, 0x00DFF500),
    ]


@pytest.mark.parametrize("tid,at,n,window", D2_PROTECTED)
def test_d2_protected_addresses_hit_named_windows(tid, at, n, window):
    windows = mmio_windows()
    assert window in windows
    assert mmio_hit(at, n, windows), tid
    start, stop = window
    assert start <= at < stop
    assert at + n <= stop or at < stop  # overlap rule covers partial


@pytest.mark.parametrize("tid,at,n", D2_CONTROL)
def test_d2_control_addresses_miss_all_mmio_windows(tid, at, n):
    windows = mmio_windows()
    assert not mmio_hit(at, n, windows), tid


def test_c_peek_refuses_mmio_before_any_memory_copy():
    peek = function_body(DAEMON, "c_peek")
    # Order: parse hex → apollo_mmio_hit → peek_allowed → t_add (CopyMem of target)
    assert "apollo_mmio_hit(at, n)" in peek
    assert REFUSE_TEXT in peek
    hit_at = peek.index("apollo_mmio_hit(at, n)")
    t_add_at = peek.index("t_add(&t, (const void *)at, n)")
    assert hit_at < t_add_at
    # Refusal returns c_fail; t_add is not on that path
    refuse = peek[hit_at:t_add_at]
    assert "c_fail" in refuse
    assert "t_add" not in refuse


def test_peek_allowed_also_gates_mmio_before_memheader_walk():
    body = function_body(DAEMON, "peek_allowed")
    assert "apollo_mmio_hit(at, n)" in body
    assert body.index("apollo_mmio_hit") < body.index("Forbid")
    assert body.index("apollo_mmio_hit") < body.index("MemList")


def test_wraparound_and_zero_length_are_hits():
    windows = mmio_windows()
    assert mmio_hit(0xFFFFFFFE, 4, windows)
    assert mmio_hit(0xDFF3FC, 0, windows)
    # Overlap from just before a window
    assert mmio_hit(0xDFF1F2, 4, windows)  # crosses GFXMODE
    assert not mmio_hit(0xDFF1F0, 4, windows)


def test_c_poke_requires_allowpoke_and_still_refuses_mmio():
    poke = function_body(DAEMON, "c_poke")
    assert poke.index("!allow_poke") < poke.index("apollo_mmio_hit")
    assert "ALLOWPOKE" in poke
    assert "CopyMem(data, (APTR)at, n)" in poke
    # CopyMem only after both gates
    assert poke.rindex("apollo_mmio_hit") < poke.index("CopyMem(data, (APTR)at, n)")


def test_cmd_peek_dispatch_uses_c_peek_only():
    # mon_say before c_peek must not dereference the request address
    dispatch = DAEMON.split("case CMD_PEEK:", 1)[1].split("case CMD_", 1)[0]
    assert 'mon_say(\'C\', "read memory", NULL)' in dispatch
    assert "c_peek(" in dispatch
    assert "t_add" not in dispatch


def test_client_peek_is_protocol6_only_and_bounded():
    assert channel.PEEK == 39
    assert channel.PEEK_MAX == 65536
    src = Path(channel.__file__).read_text(encoding="utf-8")
    peek = src.split("def peek(self", 1)[1].split("\n    def ", 1)[0]
    assert "_need6" in peek
    assert "PEEK_MAX" in peek


# Exact Stage 3B/4 hardware-tested stream-safe fork daemon (not necessarily
# the packaged bytes on every documentation branch tip).
D2_CANDIDATE_SIZE = 129944
D2_CANDIDATE_SHA256 = (
    "004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c"
)


def test_d2_candidate_identity_is_frozen():
    assert D2_CANDIDATE_SIZE == 129944
    assert D2_CANDIDATE_SHA256.startswith("00443719")


def test_tree_apollo_binary_embeds_mmio_window_constants():
    import struct

    blob = (ROOT / "src/amigent/amiga/bin/amigentd.apollo").read_bytes()
    assert len(blob) > 100000  # apollo daemon present
    for start, _ in mmio_windows():
        assert struct.pack(">I", start) in blob


def test_refuse_message_constant_matches_daemon():
    assert REFUSE_TEXT in DAEMON
    assert REFUSE_TEXT in function_body(DAEMON, "c_peek")
