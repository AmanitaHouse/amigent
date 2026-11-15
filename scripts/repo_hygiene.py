#!/usr/bin/env python3
"""Run a command and fail if it changes a file outside build/.

This is the supported Python test invocation. It creates the cache and
temporary directories, then starts a new interpreter with those locations
already in the environment. Python reads ``PYTHONPYCACHEPREFIX`` only while
it is starting, and ``tempfile`` keeps the first directory it finds, so
setting either one after startup does not move output that has already been
placed.

Usage: python scripts/repo_hygiene.py -- pytest -q
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = (ROOT / "build" / "pycache").resolve()
TEMPORARY = (ROOT / "build" / "tmp").resolve()
PREFIX = str(CACHE)
TEMP = str(TEMPORARY)


def runtime_env() -> dict[str, str]:
    """Cache and temporary directories for an interpreter that has not started."""
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = PREFIX
    env["TMPDIR"] = TEMP
    env["TEMP"] = TEMP
    env["TMP"] = TEMP
    return env


def runtime_ready() -> bool:
    return (
        os.environ.get("PYTHONPYCACHEPREFIX") == PREFIX
        and os.environ.get("TMPDIR") == TEMP
        and os.environ.get("TEMP") == TEMP
        and os.environ.get("TMP") == TEMP
    )


def main(argv: list[str]) -> int:
    # A new interpreter has to see the variables at startup. os.execv on
    # Windows does not keep this process id, so the parent waits on a child.
    if not runtime_ready():
        CACHE.mkdir(parents=True, exist_ok=True)
        TEMPORARY.mkdir(parents=True, exist_ok=True)
        return subprocess.run([sys.executable, *sys.argv], env=runtime_env()).returncode
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print("usage: python scripts/repo_hygiene.py -- <command>", file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT / "tests"))
    from hygiene import run_checked

    return run_checked(ROOT, argv, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
