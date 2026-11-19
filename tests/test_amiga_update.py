"""Amigent-Update's drawer selection, run against the script itself.

The mock understands the commands in that script. It is not an Amiga.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "src" / "amigent" / "amiga" / "Amigent-Update"


class Drawer:
    def __init__(self, files, cpu_rc=0, probe_rc=5):
        self.files = set(files)
        self.cpu_rc = cpu_rc
        self.probe_rc = probe_rc


class Run:
    def __init__(self, drawer):
        self.drawer = drawer
        self.rc = 0
        self.vars = {}
        self.copies = []
        self.commands = []
        self.echoes = []
        self.active = True
        self.stack = []

    def expand(self, text):
        def value(match):
            return self.vars.get(match.group(1), "")

        text = re.sub(r"\$([A-Za-z0-9]+)", value, text)
        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            return text[1:-1]
        return text

    def condition(self, line):
        parts = line.split()
        rest = parts[1:]
        negate = rest[:1] == ["NOT"]
        if negate:
            rest = rest[1:]
        kind = rest[0]
        if kind == "WARN":
            ok = self.rc >= 5
        elif kind == "EXISTS":
            ok = self.expand(" ".join(rest[1:])) in self.drawer.files
        else:
            raise AssertionError(f"unhandled condition: {line}")
        return (not ok) if negate else ok

    def enter_if(self, line):
        parent = self.active
        taken = self.condition(line) if parent else False
        self.stack.append({"parent": parent, "taken": taken, "else": False})
        self.active = parent and taken

    def enter_else(self):
        frame = self.stack[-1]
        frame["else"] = True
        self.active = frame["parent"] and not frame["taken"]

    def end_if(self):
        frame = self.stack.pop()
        self.active = frame["parent"]

    def execute(self, line):
        self.commands.append(line)
        head, _, tail = line.partition(" ")
        if head == "FailAt":
            return
        if head == "Set":
            name, _, value = tail.partition(" ")
            self.vars[name] = self.expand(value)
            self.rc = 0
            return
        if head == "UnSet":
            self.vars.pop(tail.strip(), None)
            self.rc = 0
            return
        if head == "Echo":
            self.echoes.append(self.expand(tail))
            self.rc = 0
            return
        if head == "Copy":
            words = tail.split()
            words = [word for word in words if word != "QUIET"]
            src = self.expand(words[0])
            dest = self.expand(words[1])
            self.copies.append((src, dest))
            self.rc = 0
            return
        if line.startswith("CPU CHECK"):
            self.rc = self.drawer.cpu_rc
            return
        if line.startswith("amigent-apollo-probe"):
            self.rc = self.drawer.probe_rc
            return
        if line.startswith("Which "):
            self.rc = 0
            return
        if head in {"Run", "Wait", "Ask", "rx"}:
            self.rc = 0
            return
        raise AssertionError(f"unhandled command: {line}")


def run_update(drawer):
    lines = SCRIPT.read_text(encoding="iso-8859-1").splitlines()
    labels = {}
    for index, raw in enumerate(lines):
        stripped = raw.split(";", 1)[0].strip()
        if stripped.lower().startswith("lab "):
            labels[stripped.split()[1].lower()] = index
    run = Run(drawer)
    index = 0
    while index < len(lines):
        line = lines[index].split(";", 1)[0].strip()
        index += 1
        if not line or line.lower().startswith("lab "):
            continue
        head = line.split()[0]
        if head == "If":
            run.enter_if(line)
            continue
        if head == "Else":
            run.enter_else()
            continue
        if head == "EndIf":
            run.end_if()
            continue
        if not run.active:
            continue
        if head == "Skip":
            index = labels[line.split()[1].lower()]
            continue
        run.execute(line)
    return run


def drawer(**extra):
    files = {
        "C:amigentd",
        "amigentd",
        "amigentd.000",
        "amigentd.apollo",
        "amigent-monitor",
        "amigent-monitor.apollo",
        "amigent-apollo-probe",
        "amigent-status",
        "amigent-status.info",
        "amigent-monitor.info",
        "SYS:amigent",
    }
    files.update(extra.pop("add", ()))
    for name in extra.pop("remove", ()):
        files.discard(name)
    return Drawer(files, **extra)


def daemon_copy(run):
    return [item for item in run.copies if item[1] == "C:amigentd.new"]


def monitor_copy(run):
    return [item for item in run.copies if item[1].endswith("/amigent-monitor")]


def started_swap(run):
    return any(line.startswith("rx ") for line in run.commands)


def test_apolloos_selects_the_apollo_daemon_and_monitor():
    run = run_update(drawer(probe_rc=0))
    assert daemon_copy(run) == [("amigentd.apollo", "C:amigentd.new")]
    assert monitor_copy(run) == [("amigent-monitor.apollo", "SYS:amigent/amigent-monitor")]
    assert started_swap(run)


def test_a_positive_probe_without_the_apollo_daemon_changes_nothing():
    run = run_update(drawer(probe_rc=0, remove=("amigentd.apollo",)))
    assert run.copies == []
    assert not started_swap(run)
    assert any("amigentd.apollo is missing" in line for line in run.echoes)
    assert not any(line.startswith("rx ") or line.startswith("Run >NIL: C:amigentd") for line in run.commands)


def test_amigaos_keeps_the_classic_daemon_and_general_monitor():
    run = run_update(drawer(probe_rc=5))
    assert daemon_copy(run) == [("amigentd", "C:amigentd.new")]
    assert monitor_copy(run) == [("amigent-monitor", "SYS:amigent/amigent-monitor")]
    assert started_swap(run)


def test_a_68000_keeps_its_classic_build_even_when_the_probe_would_pass():
    run = run_update(drawer(cpu_rc=5, probe_rc=0))
    assert daemon_copy(run) == [("amigentd.000", "C:amigentd.new")]
    assert monitor_copy(run) == [("amigent-monitor", "SYS:amigent/amigent-monitor")]
    assert not any(line.startswith("amigent-apollo-probe") for line in run.commands)


def test_a_missing_probe_keeps_the_classic_daemon():
    run = run_update(drawer(remove=("amigent-apollo-probe",)))
    assert daemon_copy(run) == [("amigentd", "C:amigentd.new")]
    assert monitor_copy(run) == [("amigent-monitor", "SYS:amigent/amigent-monitor")]


def test_an_unsuccessful_probe_keeps_the_classic_daemon():
    run = run_update(drawer(probe_rc=10))
    assert daemon_copy(run) == [("amigentd", "C:amigentd.new")]
    assert monitor_copy(run) == [("amigent-monitor", "SYS:amigent/amigent-monitor")]
