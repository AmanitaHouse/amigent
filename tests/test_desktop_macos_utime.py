"""Regression tests for replacing external `touch` with `os.utime()` on macOS app install."""

from __future__ import annotations

import json
import os

import pytest


def _setup_mac_env(monkeypatch, tmp_path, *, touch_on_path: bool = True):
    from amigent import desktop

    app = tmp_path / "Amigent.app"
    cfg = tmp_path / "app.json"
    monkeypatch.setattr(desktop.sys, "platform", "darwin")
    monkeypatch.setattr(desktop, "MAC_APP", app)
    monkeypatch.setattr(desktop, "MAC_CONFIG", cfg)
    monkeypatch.setattr(desktop, "MAC_RELEASE", tmp_path / "none.zip")
    monkeypatch.setattr(
        desktop.shutil,
        "which",
        lambda name: "/usr/bin/touch" if (touch_on_path and name == "touch") else None,
    )
    return desktop, app, cfg


def test_mac_install_uses_os_utime_without_launching_touch(monkeypatch, tmp_path):
    desktop, app, cfg = _setup_mac_env(monkeypatch, tmp_path, touch_on_path=True)
    real_utime = os.utime
    utime_calls = []
    subproc_calls = []

    def record_utime(path, times=None, *args, **kwargs):
        real_utime(path, (1_000_000_000, 1_000_000_000))
        utime_calls.append((path, times))
        return real_utime(path, times, *args, **kwargs)

    def fail_subprocess(cmd, *args, **kwargs):
        subproc_calls.append(list(cmd))
        raise AssertionError(f"unexpected subprocess call: {cmd!r}")

    monkeypatch.setattr(desktop.os, "utime", record_utime)
    monkeypatch.setattr(desktop.subprocess, "run", fail_subprocess)

    made = desktop.install("A1200")
    assert made == [str(app)]
    assert utime_calls == [(app, None)]
    assert app.stat().st_mtime > 1_000_000_000
    assert subproc_calls == []
    assert desktop.installed() is True
    assert (app / "Contents" / "MacOS" / "Amigent").is_file()
    assert (app / "Contents" / "Info.plist").is_file()
    assert (app / "Contents" / "Resources" / "amigent.icns").is_file()
    assert json.loads(cfg.read_text())["args"] == ["A1200"]


def test_mac_install_skips_utime_when_app_bundle_missing(monkeypatch, tmp_path):
    desktop, app, _cfg = _setup_mac_env(monkeypatch, tmp_path, touch_on_path=True)
    utime_calls = []

    monkeypatch.setattr(desktop, "build_mac_app", lambda folder, host="": app)
    monkeypatch.setattr(desktop.os, "utime", lambda path, times=None: utime_calls.append((path, times)))

    made = desktop.install("A1200")
    assert made == [str(app)]
    assert utime_calls == []
    assert not app.exists()


def test_mac_install_propagates_utime_permission_error(monkeypatch, tmp_path):
    desktop, _app, _cfg = _setup_mac_env(monkeypatch, tmp_path, touch_on_path=True)

    def deny_utime(path, times=None):
        raise PermissionError("read-only app bundle")

    monkeypatch.setattr(desktop.os, "utime", deny_utime)

    with pytest.raises(PermissionError, match="read-only app bundle"):
        desktop.install("A1200")


def test_mac_install_repeated_install_has_no_side_effects(monkeypatch, tmp_path):
    desktop, app, cfg = _setup_mac_env(monkeypatch, tmp_path, touch_on_path=True)
    real_utime = os.utime
    utime_calls = []

    def record_utime(path, times=None, *args, **kwargs):
        utime_calls.append((path, times))
        return real_utime(path, times, *args, **kwargs)

    monkeypatch.setattr(desktop.os, "utime", record_utime)
    monkeypatch.setattr(
        desktop.subprocess,
        "run",
        lambda cmd, *a, **kw: (_ for _ in ()).throw(AssertionError(f"unexpected subprocess: {cmd!r}")),
    )

    assert desktop.install("A1200") == [str(app)]
    assert desktop.install("A1200") == [str(app)]
    assert utime_calls == [(app, None), (app, None)]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["Amigent.app", "app.json"]
    assert desktop.uninstall() == [str(app), str(cfg)]
    assert not app.exists() and not cfg.exists()


def test_linux_and_windows_install_paths_unaffected(monkeypatch, tmp_path):
    from amigent import desktop

    utime_calls = []
    monkeypatch.setattr(desktop.os, "utime", lambda path, times=None: utime_calls.append((path, times)))
    monkeypatch.setattr(desktop, "_wsl", lambda: False)

    # Linux: still refuses with the existing guidance and never touches macOS utime path.
    monkeypatch.setattr(desktop.sys, "platform", "linux")
    with pytest.raises(SystemExit, match="Windows and macOS"):
        desktop.install("A1200")
    assert utime_calls == []

    # Windows: still runs the PowerShell shortcut/registry installer and never calls os.utime.
    monkeypatch.setattr(desktop.sys, "platform", "win32")
    local_dir = tmp_path / "local" / "amigent"
    ps_calls = []

    def fake_powershell(script):
        ps_calls.append(script)
        if "GetFolderPath('LocalApplicationData')" in script:
            return r"C:\Users\Test\AppData\Local"
        return "Installed apps: Amigent"

    monkeypatch.setattr(desktop, "_powershell", fake_powershell)
    monkeypatch.setattr(desktop, "_local", lambda _p: local_dir)

    installed = desktop.install("A1200")
    assert installed == ["Installed apps: Amigent"]
    assert len(ps_calls) == 2
    assert (local_dir / "Amigent.pyw").is_file()
    assert (local_dir / "Uninstall Amigent.pyw").is_file()
    assert (local_dir / "amigent.ico").is_file()
    assert utime_calls == []
