"""Installations that can be taken back.

begin takes stock of the folders an installer may touch (TREE: name, size,
date, and a CRC for the folders it copies whole) and copies aside, on the
Amiga itself, what undo will need. Since 1.5.0 it does not copy the whole
system by default:

- the folders the caller names are copied whole;
- the system folders (C:, LIBS:, DEVS:, ...) are only recorded, without CRCs,
  which costs one listing and no reading of the files. Of them only the files
  the installation is known to touch are copied: those the caller names
  (touch), S:Startup-Sequence and S:User-Startup, which installers edit
  most, and the files amiga_aminet_install or amiga_put are about to
  overwrite while the installation is open (copied the moment before);
- full=True copies the system folders whole, as before 1.5.0.

A record alone can't bring back the old content of a file, so end names every
system file that changed or went without a copy, and undo removes what came,
restores what it has a copy of, and names the rest.

The copying runs as a background job with progress (amiga_jobs,
amiga_job_output, amiga_break). Its script writes the marker "complete" into
the store as its last line, and only when every copy went well: a backup
without the marker is never used. Before anything is copied comes an estimate
(files, bytes, time, learnt from what copying took on this Amiga before),
with a warning above LIMIT_FILES, LIMIT_BYTES or LIMIT_SECONDS, and a check
of the free space on the drive of the store.

end takes stock again: what came, what changed, what went. The copies of
unchanged files go, the rest stays for undo; the new files go into the
program store and a repair module puts them back after a reinstall of the
system. Records from before 1.5.0 (copied is None) had every folder copied
whole, and undo treats them so.

The record lives on the PC (JSON per Amiga and installation) and as text next
to the copies on the Amiga.
"""

from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from . import secret, roster
from .errors import AmigaError

SYSTEM = ["C:", "LIBS:", "DEVS:", "S:", "L:", "ENVARC:", "SYS:WBStartup", "SYS:Classes"]
CRC_LIMIT = 4 * 2**20  # files above this are compared by size and date only: CRC costs disk time
ALWAYS = ["S:Startup-Sequence", "S:User-Startup"]  # what installers edit most: always copied
# Above any of these begin warns and asks before copying.
LIMIT_FILES = 2000
LIMIT_BYTES = 32 * 2**20
LIMIT_SECONDS = 300
# Guesses for a copy on the Amiga, until one was measured there (rate_file).
COPY_KBS = 300.0
PER_FILE = 0.04  # seconds of Copy's own work per file
ENTRY_BYTES = 80  # a TREE line over the network


def safe(path: str) -> str:
    """A folder name for an Amiga path: 'SYS:WBStartup' -> 'SYS_WBStartup'."""
    return path.replace(":", "_").replace("/", "_").strip("_") or "root"


def join(folder: str, name: str) -> str:
    return folder + name if folder.endswith((":", "/")) else f"{folder}/{name}"


def name_ok(name: str) -> str:
    name = name.strip()
    if not name or any(c in name for c in ':/"*?#') or len(name) > 60:
        raise AmigaError("an installation needs a plain name, e.g. 'protracker'")
    return name


@dataclass
class Record:
    name: str
    home: str  # where on the Amiga copies, apps and repair modules live
    paths: list[str]
    started: str = ""
    before: dict = field(default_factory=dict)  # path -> {relative name: entry}
    missing: list[str] = field(default_factory=list)  # paths that did not exist before
    added: list[str] = field(default_factory=list)  # full Amiga paths
    changed: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    done: bool = False
    undone: bool = False
    # 1.5.0: what was copied aside, as full Amiga paths (a folder stands for all
    # below it). None in records of older versions, which copied every path.
    copied: list[str] | None = None
    nocrc: list[str] = field(default_factory=list)  # paths recorded without CRCs
    aliases: dict = field(default_factory=dict)  # "LIBS:" -> its folders, when it has several
    full: bool = False
    backup: str = ""  # "running", "complete" or "failed"; "" in older records: complete
    job: int = 0
    unrestorable: list[str] = field(default_factory=list)  # changed or went without a copy
    estimate: dict = field(default_factory=dict)

    @property
    def store(self) -> str:
        return join(join(self.home, "undo"), self.name)

    @property
    def marker(self) -> str:
        """Written last by the backup job: without it the copies are not complete."""
        return join(self.store, "complete")

    def backup_of(self, path: str) -> str:
        return join(self.store, safe(path))

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=1, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "Record":
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in json.loads(text).items() if k in known})

    def locate(self, full: str) -> tuple[str, str] | None:
        """(recorded path, name below it) of a full Amiga path, None outside of
        them. An assign of several folders (LIBS:) is looked up in each; the
        first folder that has the name wins."""
        low = full.lower()
        found = []
        for path in self.paths:
            if low == path.lower():
                found.append((path, ""))
            elif low.startswith(join(path, "").lower()):
                found.append((path, full[len(join(path, "")):]))
        for name, dirs in self.aliases.items():
            prefix = join(name, "")
            if low.startswith(prefix.lower()) and low != prefix.lower():
                found += [(d, full[len(prefix):]) for d in dirs if d in self.paths]
        if not found:
            return None
        for path, rel in found:
            if not rel or rel in self.before.get(path, {}):
                return path, rel
        return found[0]

    def covers(self, copies: list[str] | None, full: str) -> bool:
        """Whether copies (full paths, a folder for all below it) hold full."""
        where = self.locate(full)
        if where is None:
            return False
        path, rel = where
        if copies is None:  # before 1.5.0 every existing path was copied whole
            return path not in self.missing
        rel = rel.lower()
        for c in copies:
            spot = self.locate(c)
            if spot is None or spot[0] != path:
                continue
            base = spot[1].lower()
            if not base or rel == base or rel.startswith(base + "/"):
                return True
        return False

    def has_copy(self, full: str) -> bool:
        """Whether the backup holds full as it was before the installation."""
        return self.covers(self.copied, full)

    def is_dir(self, full: str) -> bool:
        path, rel = self.locate(full)
        return not rel or self.before.get(path, {}).get(rel, {}).get("type") == "DIR"

    def dest_of(self, full: str) -> str:
        """Where the copy of full goes, and where undo finds it."""
        path, rel = self.locate(full)
        return join(self.backup_of(path), rel) if rel else self.backup_of(path)


def folder_for(amiga: str) -> Path:
    return secret.FOLDER / "installs" / secret.safe(roster.identity(amiga) or "Amiga")


def load(amiga: str, name: str) -> Record:
    path = folder_for(amiga) / f"{name_ok(name)}.json"
    try:
        return Record.from_json(path.read_text(encoding="utf-8"))
    except OSError:
        raise AmigaError(f"no installation {name!r} recorded for this Amiga") from None


def save(amiga: str, record: Record) -> Path:
    folder = folder_for(amiga)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{record.name}.json"
    path.write_text(record.to_json(), encoding="utf-8")
    return path


def listing(amiga: str) -> list[Record]:
    out = []
    for path in sorted(folder_for(amiga).glob("*.json")):
        try:
            out.append(Record.from_json(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            continue
    return out


# ---- how long copying takes on this Amiga

def rate_file(amiga: str) -> Path:
    return folder_for(amiga) / "backup-rate.txt"


def factor(amiga: str) -> float:
    """How much longer (or shorter) copying took here than the guess, 1.0 until measured."""
    try:
        return max(0.05, min(50.0, float(rate_file(amiga).read_text().strip())))
    except (OSError, ValueError):
        return 1.0


def learn(amiga: str, guessed: float, took: float) -> None:
    """A backup that was guessed at guessed seconds took took seconds."""
    if guessed < 2 or took <= 0:
        return  # too short to say anything
    old = factor(amiga)
    new = took / guessed if not rate_file(amiga).exists() else 0.5 * old + 0.5 * took / guessed
    rate_file(amiga).parent.mkdir(parents=True, exist_ok=True)
    rate_file(amiga).write_text(f"{max(0.05, min(50.0, new)):.3f}\n")


def parse_assign(output: str) -> list[str]:
    """The directories of an "Assign NAME: EXISTS" answer: the first after the
    name, more after a plus sign (a multi-directory assign such as LIBS:)."""
    dirs = []
    for line in output.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] == "+":
            dirs.append(parts[1].strip())
        elif len(parts) == 2 and not dirs:
            dirs.append(parts[1].strip())
    return dirs


def expand(ctl, paths: list[str]) -> list[str]:
    """Watched paths with multi-directory assigns spread out over their folders,
    each folder once (LIBS: on AmiKit also holds SYS:Classes, say)."""
    return expand_map(ctl, paths)[0]


def expand_map(ctl, paths: list[str]) -> tuple[list[str], dict]:
    """expand(), and which assigns stood for several folders."""
    out: list[str] = []
    aliases: dict = {}
    seen: set[str] = set()
    for path in paths:
        targets = [path]
        if path.endswith(":") and "/" not in path:
            try:
                found = ctl.exec(f"Assign {path} EXISTS", timeout=15)
                dirs = parse_assign(found.output) if found.rc == 0 else []
                if len(dirs) > 1:
                    targets = dirs
                    aliases[path] = dirs
            except AmigaError:
                pass
        for t in targets:
            if t.upper() not in seen:
                seen.add(t.upper())
                out.append(t)
    return out, aliases


def snapshot(ctl, path: str, crc: bool = True) -> dict | None:
    """{relative name: entry} of everything below path; None when path isn't there."""
    try:
        entries = ctl.tree(path, crc=crc)
    except AmigaError as e:
        if e.code is None:
            raise
        return None
    return {e["name"]: e for e in entries if e["type"] in ("FILE", "DIR")}


def differs(a: dict, b: dict) -> bool:
    if a["type"] != b["type"]:
        return True
    if a["type"] == "DIR":
        return False
    if a["size"] != b["size"]:
        return True
    if a.get("crc") is not None and b.get("crc") is not None and a["size"] <= CRC_LIMIT:
        return a["crc"] != b["crc"]
    return a["date"] != b["date"]


def compare(before: dict | None, after: dict | None) -> tuple[list[str], list[str], list[str]]:
    """Relative names: added, changed, removed."""
    before, after = before or {}, after or {}
    added = sorted(n for n in after if n not in before)
    removed = sorted(n for n in before if n not in after)
    changed = sorted(n for n in after if n in before and differs(before[n], after[n]))
    return added, changed, removed


# ---- the backup

def plan(record: Record, named: list[str], touch: list[str]) -> list[str]:
    """What to copy aside: the named folders whole, the system folders whole
    with record.full, otherwise of them only touch and ALWAYS (when there)."""
    out: list[str] = []
    wanted = {n.lower() for n in named}
    for name, dirs in record.aliases.items():
        if name.lower() in wanted:
            wanted |= {d.lower() for d in dirs}

    def add(full: str) -> None:
        if not record.covers(out, full):
            out.append(full)

    for path in record.paths:
        if path not in record.missing and (record.full or path.lower() in wanted):
            add(path)
    for full in touch + ALWAYS:
        where = record.locate(full)
        if where is None or (where[0] in record.missing):
            if full in touch:
                raise AmigaError(f"touch: {full} is not in any recorded folder; name its folder "
                                 "in folders instead")
            continue
        path, rel = where
        if rel and rel in record.before.get(path, {}):
            add(join(path, rel))
        elif full in touch and not rel:
            add(path)
    return out


def files_below(record: Record, full: str) -> list[dict]:
    """The recorded file entries a copy of full takes along."""
    path, rel = record.locate(full)
    entries = record.before.get(path, {})
    if not rel:
        return [e for e in entries.values() if e["type"] == "FILE"]
    if entries.get(rel, {}).get("type") == "FILE":
        return [entries[rel]]
    prefix = rel + "/"
    return [e for n, e in entries.items() if e["type"] == "FILE" and n.startswith(prefix)]


def estimate(record: Record, copies: list[str], factor: float = 1.0, listed: float = 0.0,
             line_kbs: float = 0.0) -> dict:
    """Files, bytes and seconds of the copies. factor: what copying took on
    this Amiga against the guess before. listed: the seconds the listing of
    the record took (it is listed once more at the end), else guessed from
    line_kbs."""
    found = [e for c in copies for e in files_below(record, c)]
    nbytes = sum(int(e.get("size", 0)) for e in found)
    copy = (len(found) * PER_FILE + nbytes / 1024 / COPY_KBS) * factor
    entries = sum(len(v) for v in record.before.values())
    listing = listed or (entries * ENTRY_BYTES / 1024 / line_kbs if line_kbs else 0.0)
    return {"files": len(found), "bytes": nbytes, "seconds": round(copy, 1), "entries": entries,
            "listing": round(listing, 1), "items": len(copies)}


def over_limit(est: dict) -> list[str]:
    out = []
    if est["files"] > LIMIT_FILES:
        out.append(f"{est['files']} files (more than {LIMIT_FILES})")
    if est["bytes"] > LIMIT_BYTES:
        out.append(f"{size_text(est['bytes'])} (more than {size_text(LIMIT_BYTES)})")
    if est["seconds"] > LIMIT_SECONDS:
        out.append(f"about {time_text(est['seconds'])} (more than {time_text(LIMIT_SECONDS)})")
    return out


def size_text(n: float) -> str:
    if n < 1024:
        return f"{n:.0f} bytes"
    if n < 2**20:
        return f"{n / 1024:.1f} KB"
    return f"{n / 2**20:.1f} MB"


def time_text(s: float) -> str:
    return f"{s:.0f} s" if s < 90 else f"{s / 60:.0f} min"


def describe(est: dict) -> str:
    return (f"to copy: {est['files']} files, {size_text(est['bytes'])} ({est['items']} "
            f"folders or files), about {time_text(est['seconds'])} on the Amiga; the record "
            f"of {est['entries']} entries is listed again at the end"
            + (f" (about {time_text(est['listing'])})" if est.get("listing") else ""))


def needed_space(est: dict, blocksize: int = 512) -> int:
    """Bytes the copies take on the target drive: the data, two blocks per file, 1 MB to spare."""
    return est["bytes"] + est["files"] * 2 * max(blocksize, 512) + 2**20


def _makedirs(base: str, rel: str) -> list[str]:
    """MakeDir lines for rel below base, one level at a time (no MakeDir ALL before OS 3.2)."""
    parts = [p for p in rel.split("/") if p]
    return [f'MakeDir >NIL: "{join(base, "/".join(parts[:i]))}"' for i in range(1, len(parts) + 1)]


def _parent(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def begin_script(record: Record) -> str:
    """AmigaDOS that copies aside what record.copied names (CLONE keeps dates
    and bits), with a line of progress per item. A copy that fails or
    is broken skips to the end, past the marker; the marker comes last."""
    copies = record.copied if record.copied is not None else \
        [p for p in record.paths if p not in record.missing]
    lines = ["FailAt 21", f'MakeDir >NIL: "{record.home}"', f'MakeDir >NIL: "{join(record.home, "undo")}"',
             f'MakeDir >NIL: "{record.store}"', f'Delete >NIL: "{record.marker}" QUIET']
    for i, full in enumerate(copies, 1):
        path, rel = record.locate(full)
        folder = record.is_dir(full)
        lines.append(f'Echo "Amigent backup {i}/{len(copies)}: {full}"')
        lines.append(f'MakeDir >NIL: "{record.backup_of(path)}"')
        lines += _makedirs(record.backup_of(path), rel if folder else _parent(rel))
        # QUIET: a line per file would be read over the network at every look at the job
        flags = "ALL CLONE NOREQ QUIET" if folder else "CLONE NOREQ QUIET"
        lines += [f'Copy "{full}" "{record.dest_of(full)}" {flags}', "If WARN", "  Skip failed", "EndIf"]
    lines += [f'Echo >"{join(record.store, "begun")}" "{record.started}"',
              f'Echo >"{record.marker}" "{record.started}"',
              'Echo "Amigent backup complete"', "Quit 0",
              "Lab failed", 'Echo "Amigent backup stopped or failed: not complete, it will not be used"',
              "Quit 20"]
    return "\n".join(lines) + "\n"


def guard_script(record: Record, fulls: list[str]) -> str:
    """Copies single files aside the moment before something overwrites them."""
    lines = ["FailAt 21", f'MakeDir >NIL: "{record.store}"']
    for full in fulls:
        path, rel = record.locate(full)
        lines.append(f'MakeDir >NIL: "{record.backup_of(path)}"')
        lines += _makedirs(record.backup_of(path), _parent(rel))
        lines.append(f'Copy "{full}" "{record.dest_of(full)}" CLONE NOREQ QUIET')
    return "\n".join(lines) + "\n"


def to_guard(record: Record, fulls: list[str]) -> list[str]:
    """Of the paths something is about to write, the recorded files that have no copy yet."""
    out = []
    for full in fulls:
        where = record.locate(full)
        if where is None:
            continue
        path, rel = where
        if record.before.get(path, {}).get(rel, {}).get("type") == "FILE" \
                and not record.has_copy(full) and join(path, rel) not in out:
            out.append(join(path, rel))
    return out


def prune_script(record: Record) -> str:
    """Deletes the copies that are no longer needed: everything but changed and removed."""
    keep = set(record.changed) | set(record.removed)
    lines = ["FailAt 21"]
    for path, entries in record.before.items():
        for rel, entry in sorted(entries.items(), key=lambda kv: -kv[0].count("/")):
            full = join(path, rel)
            if entry["type"] == "FILE" and full not in keep and record.has_copy(full):
                lines.append(f'Delete >NIL: "{join(record.backup_of(path), rel)}" QUIET')
    return "\n".join(lines) + "\n"


def _kept(record: Record, entries: dict[str, dict]) -> tuple[list[str], list[str]]:
    """What the repair module keeps: whole folders that came, and single files
    (new or changed) outside of them."""
    dirs = sorted(f for f in record.added if entries.get(f, {}).get("type") == "DIR")
    top = [d for d in dirs if not any(d != o and d.startswith(join(o, "")) for o in dirs)]
    inside = lambda f: any(f.startswith(join(d, "")) for d in top)
    singles = [f for f in record.added + record.changed
               if entries.get(f, {}).get("type") == "FILE" and not inside(f)]
    return top, singles


def apps_script(record: Record, entries: dict[str, dict]) -> str:
    """Copies of what came and changed into the program store, for the repair module."""
    lines = ["FailAt 21", f'MakeDir >NIL: "{join(record.home, "apps")}"']
    base = join(join(record.home, "apps"), record.name)
    lines.append(f'MakeDir >NIL: "{base}"')
    top, singles = _kept(record, entries)
    for full in top:
        lines.append(f'Copy "{full}" "{join(base, safe(full))}" ALL CLONE QUIET')
    for full in singles:
        lines.append(f'Copy "{full}" "{join(base, safe(full))}" CLONE QUIET')
    return "\n".join(lines) + "\n"


def repair_module(record: Record, entries: dict[str, dict]) -> str:
    """A repair module: folders that came are put back when missing, files when
    missing or of another size (an older version came back, say)."""
    base = join(join(record.home, "apps"), record.name)
    top, singles = _kept(record, entries)
    lines = [f"; {record.name}: written by Amigent on {time.strftime('%Y-%m-%d')} after the "
             "installation: what it added and changed", ""]
    for full in top:
        lines += [f'If NOT EXISTS "{full}"',
                  f'  Copy "{join(base, safe(full))}" "{full}" ALL CLONE QUIET',
                  "EndIf"]
    for full in singles:
        size = entries[full].get("size", 0)
        # A variable name ends at a hyphen in AmigaDOS: "amigentsize", not "amigent-size".
        lines += ["SetEnv amigentsize 0",
                  f'If EXISTS "{full}"',
                  f'  List >ENV:amigentsize "{full}" LFORMAT "%L" NOHEAD',
                  "EndIf",
                  f"If NOT $amigentsize EQ {size} VAL",
                  f'  Copy "{join(base, safe(full))}" "{full}" CLONE QUIET',
                  "EndIf"]
    if singles:
        lines += ["UnSetEnv amigentsize"]
    return "\n".join(lines) + "\n"


def undo_script(record: Record, dirs_added: list[str]) -> str:
    """Removes what came (files first, then folders, deepest first) and copies
    back what changed or went, as far as the backup has it."""
    lines = ["FailAt 21"]
    for full in sorted((f for f in record.added if f not in dirs_added), key=lambda f: -f.count("/")):
        lines.append(f'Delete >NIL: "{full}" QUIET')
    for full in sorted(dirs_added, key=lambda f: -f.count("/")):
        lines.append(f'Delete >NIL: "{full}" QUIET')
    for full in record.changed + record.removed:
        if not record.has_copy(full):
            continue  # undo names it as not restorable
        for path in record.paths:
            prefix = join(path, "")
            if full.startswith(prefix) or full == path:
                rel = full[len(prefix):]
                lines.append(f'Copy "{join(record.backup_of(path), rel)}" "{full}" CLONE QUIET')
                break
    return "\n".join(lines) + "\n"
