"""Stage 4 — POKE payload wall-clock deadline (offline; no hardware)."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DAEMON = (ROOT / "src/native/amiga/daemon/amigentd.c").read_text(encoding="utf-8")


def function_body(src: str, name: str) -> str:
    for m in re.finditer(rf"\b{re.escape(name)}\s*\(", src):
        start = m.start()
        brace = src.find("{", start)
        if brace < 0 or brace - start > 200 or ";" in src[start:brace]:
            continue
        return src[start : src.index("\nstatic ", brace)]
    raise AssertionError(name)


def test_poke_deadline_is_wall_clock_not_per_fragment():
    assert "POKE_DEADLINE_MS" in DAEMON
    assert "IO_SECONDS * 1000" in DAEMON or "(IO_SECONDS * 1000UL)" in DAEMON
    wait = function_body(DAEMON, "l_wait_until")
    assert "deadline_ms - now_ms()" in wait or "(deadline_ms - now_ms())" in wait
    assert "WaitSelect" in wait
    # Remaining time shrinks; a successful fragment must not add IO_SECONDS anew
    assert "IO_SECONDS" not in wait.split("deadline_ms", 1)[1]


def test_l_recv_until_and_skip_until_use_deadline_helper():
    recv = function_body(DAEMON, "l_recv_until")
    skip = function_body(DAEMON, "l_skip_until")
    assert "l_wait_until" in recv
    assert "l_recv_until" in skip
    assert "l_wait(l," not in recv  # must not fall back to resetting per-wait


def test_c_poke_sets_deadline_once_before_payload_io():
    poke = function_body(DAEMON, "c_poke")
    assert "deadline = now_ms() + POKE_DEADLINE_MS" in poke
    assert poke.index("deadline = now_ms()") < poke.index("l_skip_until")
    assert poke.index("deadline = now_ms()") < poke.index("l_recv_until")
    # No unbounded per-fragment IO_SECONDS skip/recv on the payload path
    assert "l_skip(l, n, IO_SECONDS)" not in poke
    assert "l_recv(l, data, n, IO_SECONDS)" not in poke


def test_oversized_still_closes_without_skip_or_alloc():
    poke = function_body(DAEMON, "c_poke")
    over = poke.split("n > PEEK_MAX", 1)[1].split("deadline =", 1)[0]
    assert "return FALSE" in over
    assert "l_skip" not in over and "AllocVec" not in over


def test_allowpoke_mmio_ram_use_skip_until_then_fail():
    poke = function_body(DAEMON, "c_poke")
    for marker in ("!allow_poke", "apollo_mmio_hit", "!peek_allowed"):
        assert "l_skip_until" in poke.split(marker, 1)[1][:200]


def test_incomplete_recv_until_frees_and_closes():
    poke = function_body(DAEMON, "c_poke")
    fail = poke.split("l_recv_until", 1)[1].split("mon_say", 1)[0]
    assert "FreeVec(data)" in fail and "return FALSE" in fail
    assert "CopyMem" not in fail


def test_rejected_paths_never_reach_copymem_before_gates():
    poke = function_body(DAEMON, "c_poke")
    assert poke.rindex("l_recv_until") < poke.index("CopyMem(data, (APTR)at, n)")
    assert poke.index("!allow_poke") < poke.index("CopyMem(data, (APTR)at, n)")


def test_maximum_payload_still_peek_max():
    assert "PEEK_MAX" in DAEMON
    assert re.search(r"#define PEEK_MAX 65536", DAEMON)
    poke = function_body(DAEMON, "c_poke")
    assert "n > PEEK_MAX" in poke


def test_total_deadline_equals_io_seconds_wall_clock():
    # Documented maximum enforceable POKE payload duration: IO_SECONDS seconds.
    assert "#define IO_SECONDS 30" in DAEMON
    assert "POKE_DEADLINE_MS (IO_SECONDS * 1000UL)" in DAEMON
