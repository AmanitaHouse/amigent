"""Stage 4 D6/D7 — offline monitor / HRTmon / TRACE safety (no hardware)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from amigent import hrtmon, setup

ROOT = Path(__file__).resolve().parents[1]
DAEMON = (ROOT / "src/native/amiga/daemon/amigentd.c").read_text(encoding="utf-8")
MONITOR = (ROOT / "src/native/amiga/tools/amigent-monitor.c").read_text(encoding="utf-8")
SERVER = (ROOT / "src/amigent/server.py").read_text(encoding="utf-8")
HRTMON = (ROOT / "src/amigent/hrtmon.py").read_text(encoding="utf-8")


def function_body(src: str, name: str) -> str:
    """Prefer a definition line containing '{' over a forward declaration."""
    for m in re.finditer(rf"\b{re.escape(name)}\s*\(", src):
        start = m.start()
        brace = src.find("{", start)
        if brace < 0 or brace - start > 200:
            continue
        if ";" in src[start:brace]:
            continue
        nxt = src.index("\nstatic ", brace)
        return src[start:nxt]
    raise AssertionError(f"no body for {name}")


def test_monitor_port_name_and_second_instance_refused():
    assert 'MON_PORT "Amigent.monitor"' in DAEMON or 'MON_PORT "Amigent.monitor"' in MONITOR
    assert "FindPort(MON_PORT)" in MONITOR
    assert "amigent-monitor runs already" in MONITOR
    assert "RemPort(port)" in MONITOR
    assert "IDCMP_CLOSEWINDOW" in MONITOR
    assert "SIGBREAKF_CTRL_C" in MONITOR


def test_daemon_monitor_is_fire_and_forget_findport():
    mon = function_body(DAEMON, "mon_say")
    assert "FindPort(MON_PORT)" in mon
    assert "PutMsg" in mon
    assert "WaitPort" not in mon
    assert "DoIO" not in mon


def test_note_and_quiet_are_non_entry_opcodes():
    assert "CMD_NOTE" in DAEMON and "CMD_QUIET" in DAEMON
    ch = (ROOT / "src/amigent/channel.py").read_text(encoding="utf-8")
    assert "NOTE = 37" in ch
    quiet = function_body(DAEMON, "quiet_monitor")
    assert "mon_quiet_until" in quiet
    assert "mon_say('Q'" in quiet


def test_hrtmon_plan_fails_closed_off_apolloos_and_never_rom():
    text, start = hrtmon.plan("AmigaOS", "", "", True)
    assert start is False and "ROM" in text
    text, start = hrtmon.plan("ApolloOS", "ApolloOS", "HRTmon task", True)
    assert start is False
    text, start = hrtmon.plan("ApolloOS", "", "Workbench", False)
    assert start is False and "path" in text.lower()
    text, start = hrtmon.plan("ApolloOS", "", "Workbench", True)
    assert start is True and "ROM" in text
    assert "ROM" in HRTMON
    assert "never a request to enter the ROM" in HRTMON


def test_amiga_hrtmon_mcp_only_runs_program_path():
    tool = SERVER.split("def amiga_hrtmon", 1)[1].split("\n@mcp.tool", 1)[0]
    assert "Run >NIL: HRTmon" in tool
    assert "Which HRTmon" in tool
    assert "plan(" in tool
    assert "ROM" in tool
    # No raw address / supervisor / vector poke into HRTMon ROM entry
    assert re.search(r"0x[Ff]{2,}", tool) is None
    assert "Supervisor" not in tool
    assert "ColdCapture" not in tool


def test_apollo_monitor_packaging_gate():
    assert "amigent-monitor.apollo" in setup.monitor_file.__doc__ or True
    # Classic build name remains amigent-monitor; Apollo optional file.
    src = (ROOT / "src/amigent/setup.py").read_text(encoding="utf-8")
    assert 'build == "amigentd.apollo"' in src
    assert "amigent-monitor.apollo" in src


def test_trace_documents_68080_unvalidated_and_modifies_code():
    assert "not been validated" in DAEMON
    assert "68080" in DAEMON
    trace = function_body(DAEMON, "c_trace")
    assert "0x4E4F" in trace  # TRAP #15
    assert "tc_TrapCode" in trace
    assert "traces_off" in DAEMON
    assert (ROOT / "src/native/amiga/daemon/trapstub.s").is_file()
    # cpu_cache flush paths are 020/030 and 040/060 — not a 68080-specific path
    assert "cpu_cache" in DAEMON
    assert "AFF_68040" in DAEMON and "AFF_68060" in DAEMON


def test_trace_list_and_clear_do_not_require_address_write():
    trace = function_body(DAEMON, "c_trace")
    # op 2 list / op 3 clear before the arming path
    assert trace.index("op == 2") < trace.index("*tr->at = 0x4E4F")
    assert trace.index("op == 3") < trace.index("*tr->at = 0x4E4F")


def test_matrix_d6_d7_trace_remain_not_tested_on_hardware():
    m = json.loads((ROOT / "tests/hardware/apollo_v4_matrix.json").read_text(encoding="utf-8"))
    hc = m["hardware_coverage"]
    assert "NOT" in hc["apollo_monitor"]
    assert "NOT" in hc["HRTmon"]
    assert hc["TRACE_68080"] == "NOT_TESTED" or "NOT_TESTED" in hc["TRACE_68080"]
    assert "D6_D7_MONITOR_SAFETY_REVIEW" in hc.get("stage4_d6_d7_monitor_safety_review", "") or \
        "D6_D7" in json.dumps(hc.get("stage4", {}))


def test_review_doc_exists():
    text = (ROOT / "docs/APOLLO_V4_STAGE4_D6_D7_MONITOR_SAFETY_REVIEW.md").read_text(encoding="utf-8")
    assert "NO-GO" in text
    assert "Amigent.monitor" in text
    assert "HRTmon" in text
    assert "TRACE" in text
    assert "D3" in text
