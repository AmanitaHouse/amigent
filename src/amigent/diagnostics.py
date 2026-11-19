"""Read-only loaded-module and task lists from the fork's LOADED and TASKS replies.

These commands are not upstream protocol 6. AUDIO stays 38 and PIP stays 39.
There is no memory read, disassembly or register access here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Library:
    kind: str  # L, D or R
    name: str
    version: int
    revision: int
    open_count: int
    base: int
    neg_size: int
    pos_size: int
    id_string: str = ""


@dataclass
class Hunk:
    task: str
    command: str
    number: int
    start: int
    size: int


@dataclass
class Resident:
    name: str
    version: int
    start: int
    end: int


@dataclass
class Loaded:
    libraries: list[Library] = field(default_factory=list)
    hunks: list[Hunk] = field(default_factory=list)
    residents: list[Resident] = field(default_factory=list)
    truncated: bool = False


def was_truncated(lines: list[str]) -> bool:
    """True when the daemon stopped at a limit and said so with MORE."""
    return any(line.split("\t", 1)[0] == "MORE" for line in lines)


def parse(lines: list[str]) -> Loaded:
    out = Loaded(truncated=was_truncated(lines))
    for line in lines:
        p = line.split("\t")
        if p[0] == "MORE":
            continue
        try:
            if p[0] in ("L", "D", "R") and len(p) >= 8:
                out.libraries.append(Library(p[0], p[1], int(p[2]), int(p[3]), int(p[4]),
                                             int(p[5], 16), int(p[6]), int(p[7]),
                                             p[8].strip() if len(p) > 8 else ""))
            elif p[0] == "H" and len(p) >= 6:
                out.hunks.append(Hunk(p[1], p[2], int(p[3]), int(p[4], 16), int(p[5])))
            elif p[0] == "M" and len(p) >= 5:
                out.residents.append(Resident(p[1], int(p[2]), int(p[3], 16), int(p[4], 16)))
        except ValueError:
            continue
    return out


KINDS = {"L": "library", "D": "device", "R": "resource"}


def listing(loaded: Loaded, kind: str = "all", name: str = "") -> str:
    """A table for the agent: libraries, devices, resources, programs, residents."""
    want = name.lower()
    lines = []
    codes = {"all": "LDR", "libraries": "L", "devices": "D", "resources": "R"}.get(kind, "")
    if codes:
        for lib in sorted(loaded.libraries, key=lambda x: (x.kind, x.name.lower())):
            if lib.kind not in codes:
                continue
            if want and want not in lib.name.lower():
                continue
            ver = f"{lib.version}.{lib.revision}" if lib.version or lib.revision else "-"
            lines.append(f"{KINDS[lib.kind]:8} {lib.name:28} {ver:>8}  open {lib.open_count:<3} "
                         f"base {lib.base:08X}  {lib.id_string}".rstrip())
    if kind in ("all", "programs"):
        seen: dict[tuple[str, str], list[Hunk]] = {}
        for h in loaded.hunks:
            seen.setdefault((h.task, h.command), []).append(h)
        for (task, command), hunks in seen.items():
            label = command or task
            if want and want not in label.lower() and want not in task.lower():
                continue
            total = sum(h.size for h in hunks)
            first = hunks[0].start
            lines.append(f"program  {label:28} {len(hunks):>3} hunks {total:>8} bytes  "
                         f"first at {first:08X}  task {task}")
            if want:
                for h in hunks:
                    lines.append(f"           hunk {h.number:<3} {h.start:08X}-{h.start + h.size - 1:08X} "
                                 f"{h.size:>8} bytes")
    if kind in ("all", "residents"):
        for r in loaded.residents:
            if want and want not in r.name.lower():
                continue
            lines.append(f"resident {r.name:28} {r.version:>8}  {r.start:08X}-{r.end:08X}")
    text = "\n".join(lines) or "nothing matches"
    if loaded.truncated:
        text += "\ntruncated"
    return text


@dataclass
class TaskInfo:
    address: int
    name: str
    command: str
    kind: str
    pri: int
    state: str
    stack_size: int
    stack_used: int
    sig_wait: int
    sig_recvd: int

    @property
    def label(self) -> str:
        return self.command or self.name


def parse_tasks(lines: list[str]) -> list[TaskInfo]:
    out = []
    for line in lines:
        p = line.split("\t")
        if p[0] != "T" or len(p) < 11:
            continue
        try:
            out.append(TaskInfo(int(p[1], 16), p[2], p[3], p[4], int(p[5]), p[6], int(p[7]),
                                int(p[8]), int(p[9], 16), int(p[10], 16)))
        except ValueError:
            continue
    return out


def program_name(path: str) -> str:
    """'SYS:Utilities/ProTracker/ProTracker41' -> 'protracker41'."""
    word = path.strip().strip('"').split()[0] if path.strip() else ""
    return word.rsplit("/", 1)[-1].rsplit(":", 1)[-1].lower()


# Programs that run many times by nature; two of them are no surprise.
MANY = {"", "shell process", "background cli", "newshell", "run", "execute", "amigentd", "wait",
        "amigentd channel", "input.device", "cli", "initial cli", "boot shell"}


def task_table(tasks: list[TaskInfo], name: str = "", truncated: bool = False) -> str:
    want = name.lower()
    rows = []
    count: dict[str, int] = {}
    for t in tasks:
        if t.command:
            key = program_name(t.command)
            count[key] = count.get(key, 0) + 1
    for t in sorted(tasks, key=lambda t: (-t.pri, t.label.lower())):
        if want and want not in t.label.lower() and want not in t.name.lower():
            continue
        full = t.stack_used * 100 // t.stack_size if t.stack_size else 0
        warn = "  stack nearly full!" if full >= 85 else ""
        rows.append(f"{t.address:08X}  {t.pri:>4}  {t.state:5}  {t.kind:7}  stack now {t.stack_used:>6}/"
                    f"{t.stack_size:<6} ({full:>2} %)  {t.label}"
                    + (f"  [{t.name}]" if t.command and t.name != t.command else "") + warn
                    + (f"  runs {count[program_name(t.command)]} times!"
                       if t.command and program_name(t.command) not in MANY
                       and count.get(program_name(t.command), 0) > 1 else ""))
    text = "\n".join(rows) or "no such task"
    if truncated:
        text += "\ntruncated"
    return text
