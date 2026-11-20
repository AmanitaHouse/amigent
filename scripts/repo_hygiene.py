#!/usr/bin/env python3
"""Run a command and fail if it changes a file outside build/ or dist/.

This is the supported Python test invocation. It creates the cache directory
under ``build/`` and chooses the temporary directory, then starts a new
interpreter with those locations already in the environment. Python reads
``PYTHONPYCACHEPREFIX`` only while it is starting, and ``tempfile`` keeps the
first directory it finds, so setting either one after startup does not move
output that has already been placed.

Bytecode and the pytest cache stay under ``build/``. Private temporary files
stay in ``build/tmp`` when that directory keeps Unix file modes. On a WSL
drvfs mount it does not: every file is reported as mode 0777, and the suite's
key-file check fails. In that case the temporary directory is an isolated
folder in the operating system's own temporary storage, outside the
repository. Maintained source directories are never that destination.

Usage: python scripts/repo_hygiene.py -- python -m pytest -q
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = (ROOT / "build" / "pycache").resolve()
PREFIX = str(CACHE)


def temporary_path() -> str:
    # This import happens in the first process, before the re-exec. Point
    # bytecode at build/pycache first so tests/hygiene.py is not compiled
    # beside the source.
    if not sys.pycache_prefix:
        CACHE.mkdir(parents=True, exist_ok=True)
        sys.pycache_prefix = str(CACHE)
    sys.path.insert(0, str(ROOT / "tests"))
    from hygiene import temporary_directory

    return str(temporary_directory(ROOT))


def runtime_env(temp: str) -> dict[str, str]:
    """Cache and temporary directories for an interpreter that has not started."""
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = PREFIX
    env["TMPDIR"] = temp
    env["TEMP"] = temp
    env["TMP"] = temp
    return env


def runtime_ready() -> bool:
    temp = temporary_path()
    return (
        os.environ.get("PYTHONPYCACHEPREFIX") == PREFIX
        and os.environ.get("TMPDIR") == temp
        and os.environ.get("TEMP") == temp
        and os.environ.get("TMP") == temp
    )


def main(argv: list[str]) -> int:
    # A new interpreter has to see the variables at startup. os.execv on
    # Windows does not keep this process id, so the parent waits on a child.
    if not runtime_ready():
        CACHE.mkdir(parents=True, exist_ok=True)
        return subprocess.run([sys.executable, *sys.argv], env=runtime_env(temporary_path())).returncode
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
