"""The reset chord compiled from amigentd.c and driven through do_input.

note_reset_chord, key and do_input are the daemon's own text. The harness
provides ColdReboot as a counter. It is the host compiler, not the Apollo
one, and it never links an Amiga reset.
"""

import itertools
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "native" / "amiga" / "daemon" / "amigentd.c"
CTRL, LAMIGA, RAMIGA = 0x63, 0x66, 0x67


def _host_gcc() -> str:
    gcc = shutil.which("gcc")
    if not gcc or "m68k" in Path(gcc).name:
        pytest.skip("no host gcc")
    return gcc


def _between(code: str, start: str, end: str) -> str:
    at = code.index(start)
    return code[at:code.index(end, at)]


def _dispatch() -> str:
    """The command enum, the chord, key() and do_input(), cut from the daemon."""
    code = SOURCE.read_text(encoding="latin-1")
    enum_at = code.index("enum {\n    CMD_INFO = 1")
    enum = code[enum_at:code.index("};", enum_at) + 2]
    decision = _between(code, "/* 0x63 control, 0x66 left Amiga", "static BOOL type_char")
    dispatch = _between(code, "static UBYTE do_input(const UBYTE *c)",
                        "/* Bytes from the screen client")
    if decision.count("ColdReboot();") != 1 or "#define CHORD_MS 5000" not in decision:
        raise AssertionError("the daemon no longer has the released chord")
    if "note_reset_chord(code, down);" not in decision:
        raise AssertionError("key() no longer reports the chord")
    if "key(x & 0x7F, c[1] & 1, y);" not in dispatch:
        raise AssertionError("RAWKEY no longer reaches key()")
    if "ReadEClock" in decision or "ReadEClock" in dispatch or "drop_client" in dispatch:
        raise AssertionError("the extract picked up more than the input path")
    if "if (is_input(c[0]))\n        return reply(do_input(c));" not in code:
        raise AssertionError("command() does not dispatch input through do_input()")
    if "acks[nacks++] = do_input(in_cmd);" not in code:
        raise AssertionError("a screen command in flight does not reach do_input()")
    return enum + "\n" + decision + "\n" + dispatch


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    gcc = _host_gcc()
    folder = tmp_path_factory.mktemp("chord")
    src = folder / "chord.c"
    src.write_text(
        (ROOT / "tests/c/chord_harness_prelude.h").read_text(encoding="utf-8")
        + _dispatch()
        + (ROOT / "tests/c/chord_harness_main.c").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # The stub is the only ColdReboot. A real exec reset is not declared.
    text = src.read_text(encoding="utf-8")
    assert text.count("ColdReboot();") == 1
    assert text.count("void ColdReboot(void)") == 1
    assert text.count("note_reset_chord(") == 2  # the daemon's definition and key()
    assert "do_input(packet)" in text
    assert "reboots++" in text
    assert "ReadEClock" not in text and "proto/exec.h" not in text
    exe = folder / "chord"
    done = subprocess.run(
        [gcc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-O2", "-o", str(exe), str(src)],
        capture_output=True, text=True)
    if done.returncode:
        pytest.fail(done.stderr[-3000:])
    return exe


def run(exe, script: str) -> list[int]:
    done = subprocess.run([str(exe)], input=script, capture_output=True, text=True)
    assert done.returncode == 0, (done.returncode, done.stderr, script)
    return [int(line) for line in done.stdout.splitlines()]


def chord(times, order=(CTRL, LAMIGA, RAMIGA), version=37) -> str:
    lines = [f"version {version}"]
    for ms, code in zip(times, order):
        lines.append(f"time {ms}")
        lines.append(f"down {code:x}")
    lines.append("count")
    return "\n".join(lines) + "\n"


def test_a_prompt_chord_in_any_order_resets_once(harness):
    prompt = (1000, 1100, 1200)
    same = (1000, 1000, 1000)
    for order in itertools.permutations((CTRL, LAMIGA, RAMIGA)):
        assert run(harness, chord(prompt, order)) == [1], order
        assert run(harness, chord(same, order)) == [1], order


def test_keys_outside_the_five_second_window_do_not_reset(harness):
    # now_ms() | 1 makes a press at 0 land at 1. 5000 ms later is still inside;
    # 5002 ms later is not. 5000 itself is inside the released comparison.
    assert run(harness, chord((0, 5000, 5000))) == [1]
    assert run(harness, chord((1, 5001, 5001))) == [1]
    assert run(harness, chord((2, 5002, 5002))) == [1]
    assert run(harness, chord((0, 5002, 5002))) == [0]
    assert run(harness, chord((1, 5002, 5002))) == [0]
    assert run(harness, chord((2, 5004, 5004))) == [0]
    assert run(harness, chord((0, 1000, 6000))) == [0]


def test_unsigned_time_wraps_on_the_same_five_second_rule(harness):
    # 4294966000 is inside 2000 across the 32-bit wrap; 4294962000 is not.
    assert run(harness, chord((4294966000, 2000, 2000))) == [1]
    assert run(harness, chord((4294962000, 2000, 2000))) == [0]


def test_stale_ctrl_after_a_disconnected_client_does_not_reset(harness):
    # drop_client does not clear the chord. A client that vanishes with Ctrl
    # down leaves that press in place, and the five-second window is what
    # stops the later Amiga keys. The same press still completes a prompt chord.
    stale = "\n".join([
        "version 37",
        "time 100",
        "down 63",
        "time 6100",
        "down 66",
        "time 6100",
        "down 67",
        "count",
    ]) + "\n"
    prompt = "\n".join([
        "version 37",
        "time 100",
        "down 63",
        "time 2000",
        "down 66",
        "time 2000",
        "down 67",
        "count",
    ]) + "\n"
    assert run(harness, stale) == [0]
    assert run(harness, prompt) == [1]


def test_a_missing_release_does_not_reset_after_the_window(harness):
    # The first three downs reset with no key-up at all. The presses stay
    # recorded. Refreshing one of them after the window, or the other two
    # more than five seconds after that, does not reset again.
    script = "\n".join([
        "version 37",
        "time 0",
        "down 63",
        "time 100",
        "down 66",
        "time 200",
        "down 67",
        "count",
        "time 8000",
        "down 63",
        "count",
        "time 14000",
        "down 66",
        "time 14000",
        "down 67",
        "count",
    ]) + "\n"
    assert run(harness, script) == [1, 1, 1]


def test_release_and_repress(harness):
    released = "\n".join([
        "version 37",
        "time 1000",
        "down 63",
        "time 1100",
        "up 63",
        "time 1200",
        "down 66",
        "time 1300",
        "down 67",
        "count",
        "time 1400",
        "down 63",
        "count",
    ]) + "\n"
    assert run(harness, released) == [0, 1]

    held_then_let_go = "\n".join([
        "version 37",
        "time 1000",
        "down 63",
        "time 1100",
        "down 66",
        "time 1200",
        "up 63",
        "time 1300",
        "down 67",
        "count",
    ]) + "\n"
    assert run(harness, held_then_let_go) == [0]


def test_an_expired_partial_chord_recovers_when_the_stale_key_is_pressed_again(harness):
    script = "\n".join([
        "version 37",
        "time 0",
        "down 63",
        "time 8000",
        "down 66",
        "time 8000",
        "down 67",
        "count",
        "time 8100",
        "down 66",
        "time 8100",
        "down 67",
        "count",
        "time 8200",
        "down 63",
        "count",
        "time 9000",
        "up 63",
        "time 9000",
        "up 66",
        "time 9000",
        "up 67",
        "time 20000",
        "down 67",
        "time 20100",
        "down 63",
        "time 20200",
        "down 66",
        "count",
    ]) + "\n"
    # The late Amiga keys do not complete the old Ctrl. Pressing them again
    # still does not. Pressing Ctrl again, while those two are inside the
    # window, does. After a release, a new chord in another order does too.
    assert run(harness, script) == [0, 0, 1, 2]


def test_other_keys_and_a_repeated_ctrl_are_not_a_chord(harness):
    repeat = "\n".join([
        "version 37",
        "time 1000",
        "down 63",
        "time 1000",
        "down 63",
        "time 1000",
        "down 63",
        "count",
        "time 1000",
        "down 45",
        "count",
    ]) + "\n"
    assert run(harness, repeat) == [0, 0]


def test_exec_older_than_36_posts_the_keys_and_does_not_reset(harness):
    # key() posts the event before the version check. The viewer's chord
    # never sends a key-up, so exec 34 and 35 receive the downs and stay up.
    for version in (34, 35):
        script = chord((1000, 1100, 1200), version=version) + "events\n"
        assert run(harness, script) == [0, 3], version
    assert run(harness, chord((1000, 1100, 1200), version=36)) == [1]
    assert run(harness, chord((1000, 1100, 1200), version=37)) == [1]


def test_the_harness_binary_is_not_an_amiga_executable(harness):
    blob = Path(harness).read_bytes()
    assert not blob.startswith(b"\x00\x00\x03\xf3")  # Amiga Hunk
    source = list(Path(harness).parent.glob("*.c"))[0].read_text(encoding="utf-8")
    assert "m68k" not in source
    assert source.count("void ColdReboot(void)") == 1
    assert source.count("ColdReboot();") == 1
    main = (ROOT / "tests/c/chord_harness_main.c").read_text(encoding="utf-8")
    assert "note_reset_chord(" not in main


def test_qualifiers_on_other_keys_do_not_reset(harness):
    # The three Amiga qualifier bits, including all of them together, are not
    # the chord. Only the raw key codes are.
    script = "\n".join([
        "version 37",
        "time 1000",
        "qual c8",
        "down 45",
        "time 1100",
        "qual c8",
        "down 40",
        "time 1200",
        "qual 1c8",
        "down 42",
        "count",
    ]) + "\n"
    assert run(harness, script) == [0]


def test_viewer_packets_on_exec_34_and_35_are_posted_and_do_not_reset(harness):
    import struct

    from amigent.amigentd import reset_chord
    from amigent.screenfeed import commands

    for version in (34, 35):
        lines = [f"version {version}"]
        ms = 1000
        for op in reset_chord():
            for cmd in commands(op, 640, 256):
                packet = struct.pack(">BBHHHH", cmd[0], cmd[1], cmd[2], cmd[3], 0, 0)
                assert len(packet) == 10
                lines.append(f"time {ms}")
                lines.append("packet " + packet.hex())
                ms += 50
        lines += ["count", "events"]
        # The three downs are delivered. ColdReboot() does not run.
        assert run(harness, "\n".join(lines) + "\n") == [0, 3], version


def test_viewer_packets_reset_through_do_input(harness):
    import struct

    from amigent.amigentd import reset_chord
    from amigent.screenfeed import commands

    lines = ["version 37"]
    ms = 1000
    for op in reset_chord():
        for cmd in commands(op, 640, 256):
            packet = struct.pack(">BBHHHH", cmd[0], cmd[1], cmd[2], cmd[3], 0, 0)
            assert len(packet) == 10
            lines.append(f"time {ms}")
            lines.append("packet " + packet.hex())
            ms += 50
    lines += ["count", "events"]
    # Three input events are posted, and the third completes one reset.
    assert run(harness, "\n".join(lines) + "\n") == [1, 3]
