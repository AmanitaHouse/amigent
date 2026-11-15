import ipaddress
import os
import sys
import tempfile
import threading
import traceback
from pathlib import Path

# Before any test module imports the server. Import reads the roster and
# AMIGENT_HOST once, and a later per-test patch cannot take that back.
# The empty folder is what monkeypatch restores between tests, so a thread
# that outlives a test still cannot see the operator's Amigas.
os.environ.pop("AMIGENT_HOST", None)
os.environ.pop("AMIGENT_KEY", None)
_OFFLINE_HOME = Path(tempfile.mkdtemp(prefix="amigent-offline-"))

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYCACHE = ROOT / "build" / "pycache"
# A real Amiga test sets this itself. The suite never sets it.
LIVE = os.environ.get("AMIGENT_LIVE") == "1"
_violations: list[str] = []

# PYTHONPYCACHEPREFIX is read only while Python is starting. Assigning
# os.environ here does not move bytecode. sys.pycache_prefix does, for
# imports that have not run yet. This file's own bytecode was placed
# before the first line, so the runner exports the variable first.
if not sys.pycache_prefix:
    sys.pycache_prefix = str(PYCACHE)

from amigent import paths, secret, tls  # noqa: E402

paths.FOLDER = _OFFLINE_HOME
secret.FOLDER = _OFFLINE_HOME
tls.FOLDER = _OFFLINE_HOME

from hygiene import combine_exit, drift, main_worktree, remember  # noqa: E402


def pytest_sessionstart(session):
    """Record the checkout, dirt and all, before any test writes a file."""
    roots = [ROOT]
    other = main_worktree(ROOT)
    if other is not None:
        roots.append(other)
    remember(roots)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live: dials a real Amiga and is skipped unless AMIGENT_LIVE=1",
    )


def pytest_runtest_setup(item):
    if item.get_closest_marker("live") is not None and not LIVE:
        pytest.skip("live machine test requires AMIGENT_LIVE=1")


def pytest_sessionfinish(session, exitstatus):
    """Fail when the tree drifted, whether or not any particular test ran.

    This is the session gate. It does not depend on
    ``test_suite_left_no_artifacts`` being collected or ordered last.
    A command that never reaches this hook is covered by ``guarded``.
    A connection or subnet sweep outside loopback fails the run as well.
    """
    problems = drift()
    if problems:
        sys.stderr.write("unexpected repository artifacts:\n" + "\n".join(problems) + "\n")
    if _violations:
        sys.stderr.write("offline network violations:\n" + "\n".join(_violations) + "\n")
    session.exitstatus = combine_exit(session.exitstatus or exitstatus or 0, problems + _violations)


def _loopback(host: str) -> bool:
    if host.lower() in {"localhost"}:
        return True
    try:
        return ipaddress.ip_address(host.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def _note(kind: str, host: str) -> None:
    if len(_violations) >= 8:
        return
    _violations.append(f"{kind} {host} on {threading.current_thread().name}\n"
                       + "".join(traceback.format_stack(limit=6)))


def _install_offline_guard() -> None:
    """Refuse non-loopback dials for the whole process, including after a test ends.

    Interface discovery is replaced with loopback. A UDP connect to a
    documentation address is a real socket operation and is not allowed.
    ``AMIGENT_LIVE=1`` is the opt-in for a test marked ``live``.
    """
    import socket

    from amigent import machines, net

    if LIVE:
        return
    net.interface_address = lambda: "127.0.0.1"
    real_create = socket.create_connection
    real_connect = socket.socket.connect
    real_lookup = socket.gethostbyname

    def host_of(address) -> str:
        return str(address[0] if isinstance(address, tuple) else address)

    def create_connection(address, *args, **kwargs):
        host = host_of(address)
        if not _loopback(host):
            if host:
                _note("connect", host)
            raise OSError(f"offline tests do not connect to {host or 'an empty address'}")
        return real_create(address, *args, **kwargs)

    def connect(self, address):
        host = host_of(address)
        if not _loopback(host):
            if host:
                _note("connect", host)
            raise OSError(f"offline tests do not connect to {host or 'an empty address'}")
        return real_connect(self, address)

    def gethostbyname(name):
        host = name.decode() if isinstance(name, bytes) else str(name)
        if _loopback(host) or host.lower().endswith(".invalid"):
            return real_lookup(name)
        raise OSError(f"offline tests do not resolve {host}")

    def scan():
        _note("scan", "local network")
        raise OSError("offline tests do not scan the local network")

    socket.create_connection = create_connection
    socket.socket.connect = connect
    socket.gethostbyname = gethostbyname
    machines.scan = scan


_install_offline_guard()


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
    monkeypatch.delenv("AMIGENT_KEY", raising=False)
    server = sys.modules.get("amigent.server")
    if server is not None:
        # Input tools ask the live command channel about other agents. The
        # tests replace the screen, not that channel.
        monkeypatch.setattr(server, "_others_note", lambda: "")
    machines._searched.clear()
    return folder
