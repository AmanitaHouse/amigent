"""The FPU: from AttnFlags, in crash explanations, for builds, and in a program's code (#42)."""

import struct

import pytest

import amigent.server as server
from amigent import alerts, hunks, project, system
from amigent.channel import Commands
from amigent.errors import AmigaError
from fakeamiga import FakeAmiga

# AttnFlags as exec leaves them
A1200_030_882 = 0x37   # 68010|68020|68030|68881|68882
LC040 = 0x0F           # 68010-68040, FPU40 clear
A4000_040_BARE = 0x4F  # FPU40, but 68040.library has not set the 68881/68882 bits
A4000_040 = 0x7F       # with 68040.library
A060 = 0x80FF          # 68060.library on OS 3.2, as reported for MMULib
V4_080 = 0x47F | 0x80  # 68080 with its FPU


# ---- AttnFlags in words

@pytest.mark.parametrize("flags, cpu, line", [
    (A1200_030_882, "68030", "68030 with 68882 FPU"),
    (0x17, "68030", "68030 with 68881 FPU"),
    (0x07, "68EC030", "68EC030, no FPU"),
    (LC040, "68040", "68040, no FPU"),
    (A4000_040, "68040", "68040 with FPU (FPU emulation active)"),
    (A060, "68040", "68060 with FPU (FPU emulation active)"),
    (V4_080, "68080", "68080 with FPU"),
    (0x0, "68000", "68000, no FPU"),
])
def test_attn_flags_tell_the_fpu(flags, cpu, line):
    assert system.describe_fpu(flags, cpu).line() == line


def test_a_68040_without_its_library_is_told():
    fpu = system.describe_fpu(A4000_040_BARE, "68040")
    assert fpu.present and fpu.support_missing and fpu.library == "68040.library"
    assert fpu.short() == "FPU, 68040.library missing"
    assert "68040.library is not loaded" in fpu.line()
    fpu.loaded = True  # the library list says it is there after all
    assert not fpu.support_missing and fpu.line() == "68040 with FPU (68040.library loaded)"


def test_without_attn_flags_the_cpu_text_is_used():
    assert system.describe_fpu(None, "68030", "68882").line() == "68030 with 68882 FPU"
    assert system.describe_fpu(None, "68LC040").line() == "68LC040, no FPU"
    unknown = system.describe_fpu(None, "68020")
    assert unknown.present is None and unknown.short() == "" and "unknown" in unknown.line()
    assert system.attn_flags({"attn_flags": "0x7f"}) == 0x7F
    assert system.attn_flags({"attn_flags": "nope"}) is None and system.attn_flags({}) is None


def test_cpu_text_keeps_ec_and_lc_names():
    facts = system.describe_system("Kickstart 40.68, Workbench 40.42", "System: 68LC040 (INST: CACHE)")
    assert facts["cpu"] == "68LC040" and facts["fpu"] == ""


# ---- crashes

def test_line_f_without_an_fpu_says_the_program_needs_one():
    hint = alerts.fpu_hint("0000000B", system.describe_fpu(LC040, "68LC040"))
    assert "needs an FPU this Amiga lacks" in hint and "68LC040, no FPU" in hint


def test_line_f_on_a_bare_68040_says_the_library_is_missing():
    hint = alerts.fpu_hint("8000000B", system.describe_fpu(A4000_040_BARE, "68040"))
    assert "support library is missing" in hint and "68040.library" in hint
    assert "missing" in alerts.fpu_hint(0x3D, system.describe_fpu(0x40CF, "68060"))  # integer trap, 060


def test_line_f_with_a_working_fpu_points_elsewhere():
    assert "MMU" in alerts.fpu_hint("0000000B", system.describe_fpu(A1200_030_882, "68030"))
    assert alerts.fpu_hint("81000005", system.describe_fpu(LC040)) == ""
    assert alerts.fpu_hint("00000037", system.describe_fpu(A4000_040, "68040")) == ""
    assert "68040/060 without its support library" in alerts.describe("00000037")


# ---- the fake Amiga, end to end

def amiga(flags, cpu_text, libraries=()):
    fake = FakeAmiga()
    fake.protocol = 6
    if flags is not None:
        fake.info["attn_flags"] = hex(flags)
    fake.answers.update({
        "Version": (0, "Kickstart 47.115, Workbench 47.4\n"),
        "CPU": (0, f"System: {cpu_text} (INST: CACHE)\n"),
        "Version FILE LIBS:powerpc.library": (20, ""),
        "Version FILE LIBS:ppc.library": (20, ""),
    })
    fake.loaded = ["L\texec.library\t47\t115\t40\t00000ac0\t1032\t632\texec 47.115"] + [
        f"L\t{name}\t47\t1\t1\t0a100000\t60\t60\t{name} 47.1" for name in libraries]
    return fake


@pytest.fixture
def on(machine_session):
    made = []

    def use(fake):
        made.append(fake)
        machine_session.ctl.close()
        machine_session.ctl = Commands("127.0.0.1", 1, fake.port)
        machine_session.system_seen.clear()  # another Amiga: ask again
        machine_session.fpu = None
        return fake
    yield use
    machine_session.ctl.close()
    for fake in made:
        fake.close()


def test_status_says_the_fpu_and_its_library(on):
    on(amiga(A4000_040, "68040", ["68040.library"]))
    facts = server._system_facts()
    assert facts["processor"] == "68040 with FPU (68040.library loaded)" and facts["fpu"] == "FPU"
    assert server._system_facts() == facts  # asked once per session


def test_status_on_a_bare_68040_says_what_is_missing(on):
    on(amiga(A4000_040_BARE, "68040"))
    facts = server._system_facts()
    assert facts["fpu"] == "FPU, 68040.library missing" and "not loaded" in facts["processor"]


def test_an_old_amigentd_keeps_the_cpu_text(on):
    fake = on(amiga(None, "68030 68882"))
    fake.protocol = 4  # no LOADED, no attn_flags
    assert server._system_facts()["processor"] == "68030 with 68882 FPU"


def test_gurus_explain_a_line_f_by_this_amigas_fpu(on):
    fake = on(amiga(LC040, "68LC040"))
    assert "needs an FPU this Amiga lacks" in server.amiga_gurus("0000000B")
    fake.info["last_alert"] = "0000000B"
    out = server.amiga_gurus()
    assert out.count("FPU: ") == 1 and "line F" in out


def test_gurus_on_a_bare_68040_name_the_library(on):
    on(amiga(A4000_040_BARE, "68040"))
    assert "68040.library" in server.amiga_gurus("8000000B")
    assert "\n" not in server.amiga_gurus("81000005")  # not an FPU guru: nothing added


# ---- builds

def test_build_script_has_an_fpu_option():
    script = project.files("calc")["build"]
    assert script.startswith(".KEY CPU/K,DEVPACK/K,FPU/K") and ".DEF FPU NONE" in script
    assert "-fpu=68881 -o calc main.c -lm881 -lamiga" in script
    assert "-fpu=68040 -o calc main.c -lm040 -lamiga" in script
    assert script.count('Echo "build failed"') == 3


@pytest.fixture
def jobs(monkeypatch):
    sent = []
    monkeypatch.setattr(server, "amiga_job", lambda command, wait=0: sent.append(command) or "built calc\n")
    return sent


def test_build_with_fpu_takes_the_amigas_fpu(on, jobs):
    fake = on(amiga(A1200_030_882, "68030 68882"))
    fake.add("RAM:calc/build", project.files("calc")["build"].encode())
    out = server.amiga_build("RAM:calc", fpu="auto")
    assert jobs[-1].endswith("Execute build CPU 68020 FPU 68881")
    assert out.startswith("built with FPU code (-fpu=68881, m881.lib)")
    server.amiga_build("RAM:calc")
    assert jobs[-1].endswith("Execute build")  # the default stays without FPU code


def test_build_with_fpu_on_a_68040_uses_m040(on, jobs):
    fake = on(amiga(A4000_040, "68040", ["68040.library"]))
    fake.add("RAM:calc/build", project.files("calc")["build"].encode())
    server.amiga_build("RAM:calc", fpu="auto")
    assert jobs[-1].endswith("Execute build CPU 68040 FPU 68040")


def test_build_with_fpu_is_refused_without_one(on, jobs):
    fake = on(amiga(LC040, "68LC040"))
    fake.add("RAM:calc/build", project.files("calc")["build"].encode())
    with pytest.raises(AmigaError, match="no FPU"):
        server.amiga_build("RAM:calc", fpu="68881")
    with pytest.raises(AmigaError, match="68020"):
        on(amiga(A1200_030_882, "68030 68882")).add("RAM:calc/build", project.files("calc")["build"].encode())
        server.amiga_build("RAM:calc", fpu="68881", cpu="68000")
    assert not jobs


def test_an_old_build_script_is_told_not_broken(on, jobs):
    fake = on(amiga(A1200_030_882, "68030 68882"))
    fake.add("RAM:old/build", b".KEY CPU/K,DEVPACK/K\nEcho hi\n")
    with pytest.raises(AmigaError, match="no FPU option"):
        server.amiga_build("RAM:old", fpu="auto")


# ---- FPU instructions in a program

def program(*code_hunks: bytes) -> bytes:
    """A minimal hunk file with these code hunks, a BSS hunk and a relocation."""
    count = len(code_hunks) + 1
    out = struct.pack(">IIIII", hunks.HUNK_HEADER, 0, count, 0, count - 1)
    out += b"".join(struct.pack(">I", len(c) // 4) for c in code_hunks) + struct.pack(">I", 4)
    for code in code_hunks:
        out += struct.pack(">II", hunks.HUNK_CODE, len(code) // 4) + code
        out += struct.pack(">IIII", hunks.HUNK_RELOC32, 1, count - 1, 2) + struct.pack(">I", 0)
        out += struct.pack(">IIII", hunks.HUNK_SYMBOL, 1, *struct.unpack(">I", b"main"), 0) + b"\0\0\0\0"
        out += struct.pack(">I", hunks.HUNK_END)
    out += struct.pack(">II", hunks.HUNK_BSS, 4) + struct.pack(">I", hunks.HUNK_END)
    return out


INTEGER = bytes.fromhex("70004e714e75") + b"\0\0"          # moveq #0,d0; nop; rts
FLOAT = bytes.fromhex("f2000423f200000e4e754e71")         # fmul.x fp1,fp0; fsin.x fp0; rts; nop
DATA_LIKE = bytes.fromhex("f200ffff4e754e71")             # an F-line word with nonsense after it


def test_fpu_instructions_are_found_in_code_hunks():
    use = hunks.fpu_use(program(INTEGER, FLOAT))
    assert use.instructions == 2 and use.emulated == 1 and use.code_bytes == 20
    assert use.first == ["hunk 1 +$0 fmul", "hunk 1 +$4 fsin"]
    assert "uses FPU instructions" in use.describe() and "heuristic" in use.describe()


def test_integer_code_and_stray_words_are_not_fpu_code():
    assert not hunks.fpu_use(program(INTEGER)).uses_fpu
    assert not hunks.fpu_use(program(DATA_LIKE)).uses_fpu
    with pytest.raises(hunks.NotAProgram):
        hunks.fpu_use(b"PK\3\4 not a program")


def test_run_stops_fpu_code_on_an_amiga_without_fpu(on, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_window_titles", lambda: [])
    on(amiga(LC040, "68LC040"))
    local = tmp_path / "calc"
    local.write_bytes(program(FLOAT))
    out = server.amiga_run(str(local))
    assert out.startswith("not run: calc uses FPU instructions") and "check_fpu=False" in out
    assert server.amiga_run(str(local), check_fpu=False).startswith("rc=0")
    local.write_bytes(program(INTEGER))
    assert server.amiga_run(str(local)).startswith("rc=0")


def test_run_reads_an_amiga_program_only_where_it_matters(on, monkeypatch):
    monkeypatch.setattr(server, "_window_titles", lambda: [])
    fake = on(amiga(A4000_040_BARE, "68040"))
    fake.add("Work:calc", program(FLOAT))
    out = server.amiga_run("Work:calc")
    assert out.startswith("FPU check: Work:calc uses FPU instructions") and "rc=0" in out
    reads = fake.counts.get(22, 0)
    fake2 = on(amiga(A4000_040, "68040", ["68040.library"]))
    fake2.add("Work:calc", program(FLOAT))
    assert server.amiga_run("Work:calc").startswith("rc=0")
    assert fake2.counts.get(22, 0) == 0 and reads == 1  # a working FPU: the file is not read
