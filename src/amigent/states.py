"""Before and after: memory, open libraries and tasks, to find what a program leaves behind.

`amiga_state("save")` keeps free memory, the largest free block, every
library's and device's open count, the running tasks and the public ports.
`amiga_state("compare")` later says what changed: memory not given back, a
library still open, a task or a port that stayed. Run a program in between and
quit it, and what is left is what it leaked.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import memory


def take(sysinfo: dict, loaded: "memory.Loaded | None", tasks: list | None) -> dict:
    state = {"at": time.time(),
             "memory": {k: int(sysinfo[k]) for k in ("chip_free", "fast_free", "chip_largest",
                                                     "fast_largest") if k in sysinfo},
             "ports": sorted(p for p in sysinfo.get("ports", "").split("|") if p)}
    if loaded is not None:
        state["open"] = {f"{memory.KINDS[lib.kind]} {lib.name}": lib.open_count
                         for lib in loaded.libraries}
    if tasks is not None:
        state["tasks"] = sorted({t.label for t in tasks})
    else:
        state["tasks"] = sorted(t for t in sysinfo.get("tasks", "").split("|") if t)
    return state


def _kb(n: int) -> str:
    return f"{n / 1024:+.1f} KB" if abs(n) >= 1024 else f"{n:+d} bytes"


def compare(before: dict, after: dict) -> str:
    lines = []
    mb, ma = before.get("memory", {}), after.get("memory", {})
    for key, label in (("chip_free", "Chip RAM free"), ("fast_free", "Fast RAM free"),
                       ("chip_largest", "largest Chip block"), ("fast_largest", "largest Fast block")):
        if key in mb and key in ma and mb[key] != ma[key]:
            lines.append(f"{label}: {_kb(ma[key] - mb[key])}")
    ob, oa = before.get("open", {}), after.get("open", {})
    for name in sorted(set(ob) | set(oa)):
        if name not in ob:
            lines.append(f"{name}: loaded since, open {oa[name]}")
        elif name not in oa:
            lines.append(f"{name}: gone since (was open {ob[name]})")
        elif ob[name] != oa[name]:
            lines.append(f"{name}: open count {ob[name]} -> {oa[name]}")
    for key, label in (("tasks", "task"), ("ports", "port")):
        b, a = set(before.get(key, [])), set(after.get(key, []))
        lines += [f"new {label}: {x}" for x in sorted(a - b)]
        lines += [f"{label} gone: {x}" for x in sorted(b - a)]
    took = after.get("at", 0) - before.get("at", 0)
    head = f"since the save {int(took)} s ago:"
    return head + ("\n" + "\n".join(lines) if lines else " nothing changed")


class Store:
    def __init__(self, folder: Path):
        self.folder = folder

    def path(self, amiga: str, name: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in f"{amiga}-{name}")
        return self.folder / f"{safe}.json"

    def save(self, amiga: str, name: str, state: dict) -> Path:
        p = self.path(amiga, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state))
        return p

    def load(self, amiga: str, name: str) -> dict:
        try:
            return json.loads(self.path(amiga, name).read_text())
        except (OSError, ValueError):
            return {}
