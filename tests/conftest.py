import atexit
import os
import shutil
import tempfile

# Before anything of Amigent is imported: the settings folder of this test run is a
# throwaway one. Each test still gets its own (private_config), but a thread that
# outlives its test falls back to this folder and never to the real settings.
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="amigent-tests-")
os.environ.pop("AMIGENT_HOST", None)
atexit.register(shutil.rmtree, os.environ["XDG_CONFIG_HOME"], ignore_errors=True)

import pytest  # noqa: E402


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


@pytest.fixture(autouse=True)
def machine_session(private_config, monkeypatch):
    from amigent import server
    from amigent.sessions import MachineSession, Sessions, bound
    monkeypatch.setattr(server, "sessions", Sessions())
    with bound(MachineSession("test")) as session:
        ctl, screen = session.ctl, session.screen
        yield session
        if ctl.backend is None or hasattr(ctl.backend, "close"):
            ctl.close()
        screen.close()
        session.lookout._pool.shutdown(wait=True)
