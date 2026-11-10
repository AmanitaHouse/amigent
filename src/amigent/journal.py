"""The last things the agent did on each Amiga, kept on the PC.

When an Amiga crashes, the Amiga forgets; the PC doesn't. After a restart or a
guru, amiga_status shows the last tool calls before the Amiga went away, so the
agent (and the user) see what led there: the program started, the file
written, the key pressed.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

KEEP = 40


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name or "amiga")[:60]


class Journal:
    def __init__(self, folder: Path | None = None):
        self.folder = folder  # None: secret.FOLDER/journal, looked up at each call

    def _file(self, amiga: str) -> Path:
        if self.folder is None:
            from . import secret
            return secret.FOLDER / "journal" / f"{_safe(amiga)}.jsonl"
        return self.folder / f"{_safe(amiga)}.jsonl"

    def add(self, amiga: str, line: str, ok: bool = True, now: float | None = None) -> None:
        """One tool call; never raises, a lost line only costs the next postmortem."""
        entry = {"at": time.time() if now is None else now, "did": line}
        if not ok:
            entry["failed"] = True
        path = self._file(amiga)
        try:
            lines = path.read_text().splitlines()[-(KEEP - 1):] if path.exists() else []
            lines.append(json.dumps(entry))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n")
        except OSError:
            pass

    def recent(self, amiga: str, before: float | None = None, most: int = 8) -> list[dict]:
        """The last calls, oldest first; with before, only those up to that time."""
        try:
            entries = [json.loads(x) for x in self._file(amiga).read_text().splitlines() if x]
        except (OSError, ValueError):
            return []
        if before is not None:
            entries = [e for e in entries if e.get("at", 0) <= before]
        return entries[-most:]


def describe(entries: list[dict], now: float | None = None) -> list[str]:
    """['3 min ago: start HiP', ...] for amiga_status."""
    from .uptime import duration

    now = time.time() if now is None else now
    return [f"{duration(now - e.get('at', now))} ago: {e.get('did', '?')}"
            + (" (failed)" if e.get("failed") else "") for e in entries]
