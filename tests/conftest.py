import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYCACHE = ROOT / "build" / "pycache"

# PYTHONPYCACHEPREFIX is read only while Python is starting. Assigning
# os.environ here does not move bytecode. sys.pycache_prefix does, for
# imports that have not run yet. This file's own bytecode was placed
# before the first line, so the runner exports the variable first.
if not sys.pycache_prefix:
    sys.pycache_prefix = str(PYCACHE)

from hygiene import combine_exit, drift, main_worktree, remember  # noqa: E402


def pytest_sessionstart(session):
    """Record the checkout, dirt and all, before any test writes a file."""
    roots = [ROOT]
    other = main_worktree(ROOT)
    if other is not None:
        roots.append(other)
    remember(roots)


def pytest_sessionfinish(session, exitstatus):
    """Fail when the tree drifted, whether or not any particular test ran.

    This is the session gate. It does not depend on
    ``test_suite_left_no_artifacts`` being collected or ordered last.
    A command that never reaches this hook is covered by ``guarded``.
    """
    problems = drift()
    if problems:
        sys.stderr.write("unexpected repository artifacts:\n" + "\n".join(problems) + "\n")
    session.exitstatus = combine_exit(session.exitstatus or exitstatus or 0, problems)


@pytest.fixture(autouse=True)
def private_config(tmp_path, monkeypatch):
    """Every test gets an empty config folder, and never searches the real network."""
    from amigent import machines, paths, secret, tls

    folder = tmp_path / "config"
    monkeypatch.setattr(paths, "FOLDER", folder)  # the roll call
    monkeypatch.setattr(secret, "FOLDER", folder)
    monkeypatch.setattr(tls, "FOLDER", folder)
    monkeypatch.setattr(machines, "scan", lambda: [])
    monkeypatch.delenv("AMIGENT_HOST", raising=False)
    machines._searched.clear()
    return folder
