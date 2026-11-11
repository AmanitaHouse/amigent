"""The ProTracker session's wishes for 1.4.0: hunks, stack, locks, CPU, dragging."""

from amigent import memory, probes


def loaded():
    return memory.parse([
        "H\tProTracker\tSYS:Utilities/ProTracker/ProTracker41\t0\t00100000\t4096",
        "H\tProTracker\tSYS:Utilities/ProTracker/ProTracker41\t1\t00200000\t512",
        "H\tProTracker\tSYS:Utilities/ProTracker/ProTracker41\t4\t00300000\t8192",
        "L\texec.library\t47\t115\t50\t00000800\t6\t600",
    ])


def test_listing_shows_every_hunk_of_a_named_program():
    text = memory.listing(loaded(), "programs", "protracker")
    assert "hunk 4   00300000-00301FFF     8192 bytes" in text
    assert text.count("hunk ") >= 3


def test_resolve_hunk_forms():
    namer = memory.Namer(loaded())
    for form in ("ProTracker41 hunk 4 +$10", "ProTracker41:hunk4+0x10", "protracker hunk 4 +10",
                 "SYS:Utilities/ProTracker/ProTracker41:hunk 4+10"):
        assert memory.resolve(form, namer) == 0x300010, form
    assert memory.resolve("ProTracker41 hunk 1", namer) == 0x200000


def test_called_before():
    assert memory.called_before(bytes.fromhex("0000 0000 4e95"))  # jsr (a5)
    assert memory.called_before(bytes.fromhex("0000 4eae ff3a"))  # jsr -198(a6)
    assert memory.called_before(bytes.fromhex("4eb9 0010 0000"))  # jsr abs.l
    assert memory.called_before(bytes.fromhex("0000 0000 6112"))  # bsr.s
    assert not memory.called_before(bytes.fromhex("0000 0000 4e75"))  # rts
    assert not memory.called_before(bytes.fromhex("0000 0000 6100"))


def test_backtrace_keeps_only_return_addresses():
    namer = memory.Namer(loaded())
    stack = bytes.fromhex("00100020 00100040 12345678 00300010")
    calls = {0x100020: bytes.fromhex("0000 4eae ff3a"), 0x100040: bytes.fromhex("0000 0000 4e75"),
             0x300010: bytes.fromhex("0000 0000 0000")}
    out = memory.backtrace(stack, 0x8000, namer, lambda addrs: [calls.get(a) for a in addrs])
    assert len(out) == 1 and "00100020" in out[0] and "hunk 0 +$20" in out[0]


def test_signal_names():
    assert memory.signal_names(0x1100) == "$00001100 (dos, Ctrl-C)"
    assert memory.signal_names(0) == "none"


def test_task_table_marks_programs_that_run_twice():
    tasks = memory.parse_tasks([
        "T\t00010000\tProTracker\tSYS:Utilities/ProTracker/ProTracker41\tprocess\t0\twait\t8000\t100\t0\t0",
        "T\t00020000\tProTracker\tProTracker41\tprocess\t0\twait\t8000\t100\t0\t0",
        "T\t00030000\tShell Process\tRun\tprocess\t0\twait\t8000\t100\t0\t0",
        "T\t00040000\tShell Process\tRun\tprocess\t0\twait\t8000\t100\t0\t0",
    ])
    text = memory.task_table(tasks)
    assert text.count("runs 2 times!") == 2
    assert "Run  runs" not in text


def test_locks():
    text = probes.locks([
        "K\tlayerinfo\t00400000\tWorkbench\t-\t0\t-1\t",
        "K\twindow\t00500000\tAmigent Monitor\t00600000 amigent-monitor\t1\t1\t00700000 input.device",
        "K\twindow\t00510000\tShell\t-\t0\t-1\t",
    ])
    assert text.startswith("1 lock(s) with tasks waiting")
    assert "held by 00600000 amigent-monitor, nested 1; waiting: 00700000 input.device" in text
    assert "free" in text


def test_cpu():
    text = probes.cpu(["N\t500\t10\t400\t0\t1234\t99", "C\t00010000\t75\tProTracker", "C\t00020000\t25\tinput.device"],
                      {0x10000: "ProTracker41"})
    lines = text.splitlines()
    assert "idle 80.0 %" in lines[0] and "1234" in lines[0]
    assert lines[1].startswith(" 15.0 %") and "ProTracker41" in lines[1]


def test_drag():
    rows = []
    left = 100
    for i in range(16):
        x = 200 + (i + 1) * 8 * (1 if i < 8 else -1)
        if i % 4 != 3:
            left += 8 if i < 8 else -8
        rows.append(f"D\t{i}\t{x}\t50\t300\t{20000 if i == 5 else 16000}\t{left}\t40\t{x}\t50")
    text = probes.drag(rows, 8)
    assert "16 steps of 8 px" in text
    assert "max 20.0 ms" in text
    assert "did not move: 4 of 15" in text


def test_drag_never_moved():
    rows = [f"D\t{i}\t{i * 8}\t0\t100\t16000\t100\t40\t{i * 8}\t0" for i in range(16)]
    assert "never moved" in probes.drag(rows, 8)


def test_what_moved(monkeypatch):
    from amigent import server
    before = [{"kind": "window", "id": "1", "title": "Shell", "x": 0, "y": 0, "w": 100, "h": 50},
              {"kind": "window", "id": "2", "title": "Monitor", "x": 200, "y": 0, "w": 100, "h": 50}]
    after = [dict(before[0]), dict(before[1], x=250)]
    monkeypatch.setattr(server, "_window_boxes", lambda: after)
    said = server._what_moved(before, 10, 5)
    assert "window 'Monitor' moved from 200,0 to 250,0" in said
    assert "start point was on 'Shell'" in said
    monkeypatch.setattr(server, "_window_boxes", lambda: [dict(w) for w in before])
    assert server._what_moved(before, 10, 5) == "; no window moved (the start point was on 'Shell')"
