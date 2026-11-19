"""Host mocks for the bounded LOADED and TASKS walks.

The executable is the daemon's own text builder and list walk, compiled
with the host gcc. Forbid, Permit and AllocVec only count. A node cap
stops a cycle; the tests do not pretend a corrupt pointer is safe to read.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from amigent import diagnostics

ROOT = Path(__file__).resolve().parents[1]
DAEMON = ROOT / "src" / "native" / "amiga" / "daemon" / "amigentd.c"
PROTOCOL = ROOT / "docs" / "PROTOCOL.md"
LIMITS = {"list": 256, "hunk_per": 64, "hunk_total": 256, "resident": 256, "reply": 48 * 1024}


def _host_gcc() -> str:
    gcc = shutil.which("gcc")
    if not gcc or "m68k" in Path(gcc).name:
        pytest.skip("no host gcc")
    return gcc


def _slice(text: str, begin: str, end: str) -> str:
    at = text.index(begin)
    return text[at + len(begin):text.index(end, at)]


def _body(text: str, signature: str, end: str) -> str:
    at = text.index(signature)
    return text[at:text.index(end, at)]


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    gcc = _host_gcc()
    code = DAEMON.read_text(encoding="latin-1")
    folder = tmp_path_factory.mktemp("enum")
    src = folder / "enum_walk.c"
    src.write_text(
        (ROOT / "tests/c/enum_harness_prelude.h").read_text(encoding="utf-8")
        + _slice(code, "/* ENUM_HOST_TEXT_BEGIN */", "/* ENUM_HOST_TEXT_END */")
        + (ROOT / "tests/c/enum_harness_stubs.c").read_text(encoding="utf-8")
        + _slice(code, "/* ENUM_HOST_WALK_BEGIN */", "/* ENUM_HOST_WALK_END */")
        + (ROOT / "tests/c/enum_harness_main.c").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    text = src.read_text(encoding="utf-8")
    assert "proto/exec.h" not in text
    assert text.count("static BOOL c_loaded(") == 1
    assert text.count("static BOOL c_tasks(") == 1
    exe = folder / "enum_walk"
    done = subprocess.run(
        [gcc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2",
         "-Wno-pointer-to-int-cast", "-Wno-int-to-pointer-cast",
         "-o", str(exe), str(src)],
        capture_output=True, text=True)
    if done.returncode:
        pytest.fail(done.stderr[-4000:])
    return exe


def _run(exe, mode: str):
    done = subprocess.run([str(exe), mode], capture_output=True, timeout=15)
    if done.returncode == 77:
        pytest.skip(done.stderr.decode("ascii", "replace").strip() or "low memory unavailable")
    out = done.stdout.decode("latin-1")
    err = done.stderr.decode("latin-1", "replace")
    assert done.returncode == 0, (done.returncode, err, out[-2000:])
    head, _, body = out.partition("\n")
    facts = {}
    for part in head.split():
        key, value = part.split("=")
        facts[key] = int(value)
    body = body.replace("\r\n", "\n")
    assert facts["bytes"] == len(body.encode("latin-1"))
    assert facts["forbid_depth"] == 0
    assert facts["forbid"] == facts["permit"]
    assert facts["alloc_forbidden"] == 0
    assert facts["send_forbidden"] == 0
    return facts, body


def _lines(body: str) -> list[str]:
    return body.split("\n")[:-1] if body.endswith("\n") else body.split("\n")


def _kinds(body: str, kind: str) -> list[str]:
    return [line for line in _lines(body) if line.startswith(kind + "\t") or line == kind]


def test_compiled_limits_match_the_source(harness):
    done = subprocess.run([str(harness), "limits"], capture_output=True, text=True, timeout=15)
    assert done.returncode == 0, done.stderr
    got = dict(part.split("=") for part in done.stdout.split())
    assert {k: int(v) for k, v in got.items()} == {
        "list": LIMITS["list"],
        "hunk_per": LIMITS["hunk_per"],
        "hunk_total": LIMITS["hunk_total"],
        "resident": LIMITS["resident"],
        "reply": LIMITS["reply"],
    }
    blob = Path(harness).read_bytes()
    assert not blob.startswith(b"\x00\x00\x03\xf3")


def test_a_short_list_is_complete(harness):
    facts, body = _run(harness, "short")
    assert facts["forbid"] == 1 and facts["sends"] == 1 and facts["fault"] == 0
    assert "MORE" not in body
    assert "exec.library" in body and "trackdisk.device" in body and "potgo.resource" in body
    loaded = diagnostics.parse(_lines(body))
    assert not loaded.truncated
    assert [lib.name for lib in loaded.libraries] == [
        "exec.library", "trackdisk.device", "potgo.resource"]


def test_a_short_task_list_is_complete(harness):
    facts, body = _run(harness, "short-tasks")
    assert facts["forbid"] == 1 and "MORE" not in body
    tasks = diagnostics.parse_tasks(_lines(body))
    assert [t.state for t in tasks] == ["run", "ready", "wait"]
    assert tasks[0].name == "amigentd"


def test_a_library_cycle_stops_at_the_node_cap(harness):
    facts, body = _run(harness, "cycle-libs")
    lines = _kinds(body, "L")
    assert len(lines) == LIMITS["list"]
    assert body.endswith("MORE\n")
    assert facts["bytes"] < LIMITS["reply"]
    assert facts["forbid"] == 1
    loaded = diagnostics.parse(_lines(body))
    assert loaded.truncated
    assert {lib.name for lib in loaded.libraries} == {"alpha.library", "beta.library"}


def test_a_task_cycle_stops_and_keeps_the_running_task(harness):
    facts, body = _run(harness, "cycle-tasks")
    tasks = diagnostics.parse_tasks(_lines(body))
    assert len(tasks) == LIMITS["list"] + 1
    assert tasks[0].name == "amigentd" and tasks[0].state == "run"
    assert body.endswith("MORE\n")
    assert facts["bytes"] <= LIMITS["reply"]
    assert diagnostics.task_table(tasks, truncated=True).endswith("truncated")


def test_a_process_cycle_stops_without_inventing_hunks(harness):
    facts, body = _run(harness, "cycle-procs")
    assert body == "MORE\n"
    assert facts["forbid"] == 1
    assert _kinds(body, "H") == []


def test_allocation_failure_is_an_error_and_does_not_forbid(harness):
    facts, body = _run(harness, "alloc-fail")
    assert facts["fault"] == 103
    assert facts["sends"] == 2
    assert facts["forbid"] == 0 and facts["permit"] == 0
    assert body == ""


def test_the_reply_stops_at_the_byte_cap_on_a_complete_line(harness):
    facts, body = _run(harness, "reply-cap")
    loaded = diagnostics.parse(_lines(body))
    assert loaded.truncated
    assert 0 < len(loaded.libraries) < LIMITS["list"]
    assert all(len(lib.name) == 200 for lib in loaded.libraries)
    assert facts["bytes"] <= LIMITS["reply"]
    assert body.endswith("MORE\n")
    assert "\nMORE" in body


def test_hunks_stop_per_process_and_a_bad_hunk_does_not(harness):
    capped, cap_body = _run(harness, "hunk-cap")
    ended, end_body = _run(harness, "hunk-end")
    ok, ok_body = _run(harness, "hunk-ok")
    assert len(_kinds(cap_body, "H")) == LIMITS["hunk_per"]
    assert cap_body.endswith("MORE\n") and capped["forbid"] == 1
    assert len(_kinds(end_body, "H")) == 1 and "MORE" not in end_body
    assert len(_kinds(ok_body, "H")) == 2 and "MORE" not in ok_body
    assert ended["fault"] == 0 and ok["fault"] == 0


def test_hunks_stop_at_the_reply_total(harness):
    facts, body = _run(harness, "hunk-total")
    assert len(_kinds(body, "H")) == LIMITS["hunk_total"]
    assert body.endswith("MORE\n")
    assert facts["bytes"] <= LIMITS["reply"]


def test_residents_stop_at_the_cap_and_a_link_cycle_stops(harness):
    capped, cap_body = _run(harness, "resident-cap")
    cycled, cycle_body = _run(harness, "resident-cycle")
    assert len(_kinds(cap_body, "M")) == LIMITS["resident"]
    assert cap_body.endswith("MORE\n") and capped["forbid"] == 1
    assert _kinds(cycle_body, "M") == []
    assert cycle_body == "MORE\n"
    assert cycled["forbid"] == 1


def test_source_pairs_forbid_and_keeps_allocation_outside_it():
    code = DAEMON.read_text(encoding="latin-1")
    loaded = _body(code, "static BOOL c_loaded(", "/* T  address")
    tasks = _body(code, "static BOOL c_tasks(", "/* ENUM_HOST_WALK_END */")
    prepare = _body(code, "static BOOL enum_prepare(", "static void enum_seal(")
    adder = _body(code, "static void t_add(", "static void t_chr(")
    for body in (loaded, tasks):
        assert body.count("Forbid();") == 1
        assert body.count("Permit();") == 1
        assert body.index("enum_prepare") < body.index("Forbid();")
        assert body.index("Forbid();") < body.index("Permit();")
        assert body.index("Permit();") < body.index("enum_seal") < body.index("c_text")
        assert "l_send" not in body and "AllocVec" not in body
        assert "return" not in body.split("Forbid();", 1)[1].split("Permit();", 1)[0]
    assert "AllocVec" in prepare and "Forbid" not in prepare
    assert adder.index("t->bounded") < adder.index("AllocVec")
    assert "corrupt pointer" in code
    assert "CMD_LOADED = 40, CMD_TASKS = 41" in code
    assert "PROTOCOL_VERSION 5" in code
    for macro in (
        "ENUM_LIST_MAX 256",
        "ENUM_HUNK_PER 64",
        "ENUM_HUNK_TOTAL 256",
        "ENUM_RESIDENT_MAX 256",
        "ENUM_REPLY_MAX (48 * 1024)",
    ):
        assert macro in code


def test_protocol_states_the_caps_and_the_pointer_limit():
    text = PROTOCOL.read_text(encoding="utf-8")
    assert "line `MORE`" in text
    assert "256 nodes" in text and "64 hunks" in text and "256 hunks" in text
    assert "49152" in text
    assert "does not make a corrupt pointer safe" in text
    assert "38 remains AUDIO" in text
