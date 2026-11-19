"""Phase 10B: loaded modules, tasks and guru text. No memory opcode."""

from pathlib import Path

from amigent import alerts, diagnostics, uptime
from amigent.channel import (AUDIO, LOADED, NEWEST_PROTOCOL, PACK_PROTOCOL, PIP, TASKS,
                             diagnostic_commands, loaded_request, tasks_request)

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "src" / "native" / "amiga" / "daemon" / "amigentd.c"

LOADED_LINES = [
    "L\texec.library\t47\t7\t1\t0000f800\t1024\t2048\texec 47.7",
    "D\ttrackdisk.device\t40\t1\t2\t0000abcd\t100\t200\t",
    "H\tShell\tSYS:C/List\t0\t00020000\t4096",
    "M\tworkbench.library\t45\t00f80000\t00f90000",
    "not a row",
]

TASK_LINES = [
    "T\t0000c000\tShell\tSYS:C/List\tprocess\t0\twait\t8192\t7000\t00001000\t00000000",
    "T\t0000c100\tinput.device\t\ttask\t20\twait\t4096\t100\t00000000\t00000000",
    "T\t0000c200\tShell\tSYS:C/List\tprocess\t0\tready\t8192\t10\t00000000\t00000000",
]


def test_audio_and_pip_keep_their_numbers():
    assert (AUDIO, PIP, LOADED, TASKS) == (38, 39, 40, 41)
    assert NEWEST_PROTOCOL == PACK_PROTOCOL == 5
    assert loaded_request()[0] == 40 and tasks_request()[0] == 41
    assert loaded_request()[0] != AUDIO and tasks_request()[0] != PIP
    import amigent.channel as channel
    assert not hasattr(channel, "PEEK")
    assert not hasattr(channel, "POKE")


def test_daemon_source_assigns_no_memory_opcode():
    text = DAEMON.read_text(encoding="latin-1")
    assert "CMD_AUDIO = 38, CMD_PIP = 39" in text
    assert "CMD_LOADED = 40, CMD_TASKS = 41" in text
    assert "PROTOCOL_VERSION 5" in text
    for banned in ("CMD_PEEK", "CMD_POKE", "CMD_TRACE", "ALLOWPOKE"):
        assert banned not in text
    assert "APeek(" not in text and "APoke(" not in text


def test_flags_advertise_lists_only():
    assert diagnostic_commands({"modules": "1", "tasklist": "1", "loaded": "1"}) == frozenset(
        {"LOADED", "TASKS"})
    assert diagnostic_commands({"loaded": "1", "poke": "1"}) == frozenset()
    assert diagnostic_commands(None) == frozenset()


def test_loaded_and_task_tables():
    listed = diagnostics.listing(diagnostics.parse(LOADED_LINES), "libraries", "exec")
    assert "exec.library" in listed and "trackdisk" not in listed
    programs = diagnostics.listing(diagnostics.parse(LOADED_LINES), "programs", "list")
    assert "SYS:C/List" in programs and "hunk 0" in programs
    table = diagnostics.task_table(diagnostics.parse_tasks(TASK_LINES))
    assert "stack nearly full!" in table
    assert "runs 2 times!" in table
    assert diagnostics.task_table(diagnostics.parse_tasks(TASK_LINES), "input").startswith("0000C100")


def test_more_is_truncation_and_not_a_silent_complete_list():
    loaded = diagnostics.parse(LOADED_LINES + ["MORE"])
    assert loaded.truncated
    assert diagnostics.listing(loaded, "libraries", "exec").endswith("truncated")
    assert "exec.library" in diagnostics.listing(loaded, "libraries", "exec")
    tasks = diagnostics.parse_tasks(TASK_LINES + ["MORE"])
    assert len(tasks) == 3
    table = diagnostics.task_table(tasks, truncated=diagnostics.was_truncated(TASK_LINES + ["MORE"]))
    assert table.endswith("truncated")
    assert not diagnostics.was_truncated(LOADED_LINES)
    assert not diagnostics.parse(LOADED_LINES).truncated


def test_guru_text_names_the_code_and_where():
    words = alerts.describe("81000005", "00f00abc")
    assert words.startswith("exec.library: the memory list is corrupt")
    assert "00F00ABC" in words
    said = uptime.notes({"uptime": "60", "last_alert": "8000000b"}, None, 0.0)
    assert "8000000B" in said[0] and "CPU exception" in said[0]
    where = uptime.notes({"last_alert": "81000005", "last_alert_where": "00f00abc"}, None, 0.0)
    assert "81000005.00F00ABC" in where[0] and "memory list is corrupt" in where[0]
    assert alerts.history("Guru 81000009.00000004\nno code here")[0].count("freed twice") == 1
