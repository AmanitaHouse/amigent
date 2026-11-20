"""The fork package carries its own protocol-6 Apollo daemon and the 68000 probe.

These tests drive installer selection and open the wheel and source
distribution. They do not contact an Amiga. A matching daemon hash is the
smoke-tested executable, not a test that AUDIO has been heard on hardware.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from amigent import setup
from amigent.client import ExecResult
from amigent.errors import AmigaError
from amigent.paths import AMIGA
from amigent.serve import FILES

ROOT = Path(__file__).resolve().parent.parent
BIN = AMIGA / "bin"
HUNK = b"\x00\x00\x03\xf3"
DAEMON = (131292, "1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca")
PROBE = (3224, "96ca1b389980b5a94ce0fc94c67c8eeafa7dd2455df497f52532e15409ba0265")
MONITOR = (22816, "e06222ce73f62a1ec6cab7a370e3e6154f1c396160a4813d29ad7fd7cdb9626e")
CLASSIC = {
    "amigentd": (108896, "563f19c2662a8c7e8df2f3b95aa01d224a4e8b8ba5e04178cd8492a3a6d3ecee"),
    "amigentd.000": (114768, "9b7df1aeb80a0d0e566c4128f2be840734906c223055f0efbe941f12549468f4"),
    "amigent-monitor": (17180, "b897cfdf9c5bc91777c2a87a876dfa10268e602e0e81e8027d7e862f3c917b68"),
    "amigentd.080": (108896, "8022366042e0c6e970f84acd16d65231d4fa0fb8d25c83f48c0a6221cb414339"),
}
EXCLUDED = ("amigentd.080", "private/", ".git/", ".githooks/", "build/apollo")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _packaged(name: str) -> bytes:
    return (BIN / name).read_bytes()


def test_the_packaged_daemon_is_the_rebuilt_protocol6_executable():
    size, digest = DAEMON
    data = _packaged("amigentd.apollo")
    assert len(data) == size and _sha(data) == digest and data.startswith(HUNK)
    probe = _packaged("amigent-apollo-probe")
    assert len(probe) == PROBE[0] and _sha(probe) == PROBE[1] and probe.startswith(HUNK)
    monitor = _packaged("amigent-monitor.apollo")
    assert len(monitor) == MONITOR[0] and _sha(monitor) == MONITOR[1] and monitor.startswith(HUNK)
    staged = ROOT / "build" / "apollo-fork"
    if (staged / "amigentd.apollo").is_file():
        assert (staged / "amigentd.apollo").read_bytes() == data
        assert (staged / "amigent-apollo-probe").read_bytes() == probe
    source = (ROOT / "amiga" / "amigentd.c").read_text(encoding="utf-8")
    assert 't_pair(&t, "audio", 1)' in source
    assert 't_pair(&t, "pip", 0)' in source
    assert 't_pair(&t, "pip", 1)' not in source
    for name, (classic_size, classic_digest) in CLASSIC.items():
        classic = _packaged(name)
        assert len(classic) == classic_size and _sha(classic) == classic_digest
    assert FILES == ("amigentd", "amigentd.000")
    assert "does not serve amigentd.apollo" in (ROOT / "src" / "amigent" / "serve.py").read_text(encoding="utf-8")


class SetupLink:
    def __init__(self, cpu=0, probe=0):
        self.cpu = cpu
        self.probe = probe
        self.files = {}

    def run(self, command):
        if command.startswith("CPU"):
            return self.cpu
        if "amigent-apollo-probe" in command and not command.startswith("Protect"):
            return self.probe
        return 0

    def put(self, name, data):
        self.files[name] = data


def _install(cpu=0, probe=0):
    link = SetupLink(cpu, probe)
    setup.install(link, "SYS:amigent", "secret", None, False)
    return link


def test_setup_on_apolloos_copies_the_daemon_and_the_apollo_monitor():
    link = _install(0, 0)
    assert link.files["C:amigentd.new"] == _packaged("amigentd.apollo")
    assert link.files["T:amigent-apollo-probe"] == _packaged("amigent-apollo-probe")
    assert link.files["SYS:amigent/amigent-monitor"] == _packaged("amigent-monitor.apollo")
    assert b"amigent-monitor.apollo" not in link.files["T:amigent-setup"]


def test_setup_on_amigaos_and_a_68000_keeps_the_classic_daemons():
    amiga = _install(0, 5)
    assert amiga.files["C:amigentd.new"] == _packaged("amigentd")
    assert amiga.files["SYS:amigent/amigent-monitor"] == _packaged("amigent-monitor")
    plain = _install(5, 0)
    assert plain.files["C:amigentd.new"] == _packaged("amigentd.000")
    assert "T:amigent-apollo-probe" not in plain.files


def test_a_missing_probe_or_daemon_does_not_replace_a_classic_choice(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    shutil.copytree(AMIGA, package)
    (package / "bin" / "amigentd.apollo").unlink()
    (package / "bin" / "amigent-apollo-probe").unlink()
    monkeypatch.setattr(setup, "AMIGA", package)
    link = _install(0, 0)
    assert link.files["C:amigentd.new"] == (package / "bin" / "amigentd").read_bytes()
    assert "T:amigent-apollo-probe" not in link.files
    (package / "bin" / "amigent-apollo-probe").write_bytes(b"probe")
    link = _install(0, 0)  # the probe says Apollo, but no Apollo daemon is packaged
    assert link.files["C:amigentd.new"] == (package / "bin" / "amigentd").read_bytes()
    assert link.files["SYS:amigent/amigent-monitor"] == (package / "bin" / "amigent-monitor").read_bytes()
    assert link.files["T:amigent-apollo-probe"] == b"probe"


class UpdateChannel:
    protocol = 6

    def __init__(self, host, timeout=30, info=None, version="", probe="AmigaOS\n", fail_probe=False):
        self.info = info
        self.version = version
        self.probe = probe
        self.fail_probe = fail_probe
        self.files = {"C:amigentd": b"old"}
        self.commands = []
        self.written = []

    def connect(self):
        pass

    def close(self):
        pass

    def sysinfo(self):
        if self.info is None:
            raise AttributeError("no sysinfo")
        return self.info

    def read_file(self, path):
        if path not in self.files:
            raise AmigaError("object not found")
        return self.files[path]

    def write_file(self, path, data):
        self.written.append(path)
        self.files[path] = data

    def exec(self, command):
        self.commands.append(command)
        if command.startswith("CPU"):
            return ExecResult(0, "")
        if command.startswith("Version FULL"):
            return ExecResult(0, self.version)
        if command.startswith("T:amigent-apollo-probe"):
            if self.fail_probe:
                raise AmigaError("probe failed")
            return ExecResult(0, self.probe)
        if command.startswith("Version"):
            return ExecResult(0, "amigentd 1.4.0\n")
        if command.startswith("Run >NIL: rx T:amigent-update.rexx"):
            self.files["C:amigentd"] = self.files.pop("C:amigentd.new")
            self.files["T:amigent-update.done"] = b"new\n"
        return ExecResult(0, "")


def _update(monkeypatch, **kwargs):
    monkeypatch.setattr(setup.time, "sleep", lambda s: None)
    channel = UpdateChannel("192.0.2.1", **kwargs)
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    assert setup.update("192.0.2.1", None) == 0
    return channel


def test_update_keeps_classic_bytes_on_vampire_amigaos(monkeypatch):
    channel = _update(monkeypatch, info={"os": "AmigaOS", "exec_version": "47.4", "attn_flags": "0x400"})
    assert channel.files["C:amigentd"] == _packaged("amigentd")
    assert channel.files["SYS:amigent/amigent-monitor"] == _packaged("amigent-monitor")
    assert "T:amigent-apollo-probe" not in channel.files


def test_update_on_apolloos_copies_the_packaged_daemon_and_monitor(monkeypatch):
    channel = _update(monkeypatch, info={"os": "ApolloOS", "exec_version": "51.1", "attn_flags": "0x400"})
    assert channel.files["C:amigentd"] == _packaged("amigentd.apollo")
    assert channel.files["SYS:amigent/amigent-monitor"] == _packaged("amigent-monitor.apollo")
    assert "T:amigent-apollo-probe" not in channel.files


def test_apolloos_without_the_optional_monitor_keeps_the_classic_one(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    shutil.copytree(AMIGA, package)
    (package / "bin" / "amigent-monitor.apollo").unlink()
    monkeypatch.setattr(setup, "AMIGA", package)
    link = _install(0, 0)
    assert link.files["C:amigentd.new"] == (package / "bin" / "amigentd.apollo").read_bytes()
    assert link.files["SYS:amigent/amigent-monitor"] == (package / "bin" / "amigent-monitor").read_bytes()
    channel = _update(monkeypatch, info={"os": "ApolloOS", "exec_version": "51.1", "attn_flags": "0x400"})
    assert channel.files["C:amigentd"] == (package / "bin" / "amigentd.apollo").read_bytes()
    assert channel.files["SYS:amigent/amigent-monitor"] == (package / "bin" / "amigent-monitor").read_bytes()


def test_update_leaves_an_apollo_installation_that_already_matches(monkeypatch):
    channel = UpdateChannel("192.0.2.1", info={"os": "ApolloOS", "exec_version": "51.1", "attn_flags": "0x400"})
    channel.files["C:amigentd"] = _packaged("amigentd.apollo")
    channel.files["SYS:amigent/amigent-monitor"] = _packaged("amigent-monitor.apollo")
    monkeypatch.setattr(setup.time, "sleep", lambda s: None)
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    assert setup.update("192.0.2.1", None) == 0
    assert "SYS:amigent/amigent-monitor" not in channel.written
    assert "C:amigentd.new" not in channel.files


def test_update_falls_back_when_the_probe_fails(monkeypatch):
    channel = _update(monkeypatch, info={}, fail_probe=True)
    assert channel.files["C:amigentd"] == _packaged("amigentd")


def _names_ending(names, filename):
    return [name for name in names if name.replace("\\", "/").endswith("/" + filename)]


def test_wheel_and_sdist_carry_this_daemon(tmp_path):
    out = tmp_path / "dist"
    work = tmp_path / "work"
    out.mkdir()
    script = tmp_path / "build_dist.py"
    script.write_text(
        "import os\n"
        "import setuptools\n"
        "from setuptools.command.build import build as build_command\n"
        "original = build_command.initialize_options\n"
        "def initialize(self):\n"
        "    original(self)\n"
        "    self.build_base = os.environ['AMIGENT_BUILD_BASE']\n"
        "build_command.initialize_options = initialize\n"
        "from setuptools.build_meta import build_sdist, build_wheel\n"
        "out = os.environ['AMIGENT_DIST_DIR']\n"
        "print('WHEEL ' + build_wheel(out))\n"
        "print('SDIST ' + build_sdist(out))\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=ROOT, check=True, capture_output=True, text=True,
        env={**os.environ, "AMIGENT_DIST_DIR": str(out), "AMIGENT_BUILD_BASE": str(work)},
    )
    produced = dict(line.split(" ", 1) for line in completed.stdout.splitlines() if line.startswith(("WHEEL ", "SDIST ")))
    wheel = out / produced["WHEEL"]
    sdist = out / produced["SDIST"]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        daemon = archive.read(_names_ending(names, "amigentd.apollo")[0])
        probe = archive.read(_names_ending(names, "amigent-apollo-probe")[0])
        assert len(daemon) == DAEMON[0] and _sha(daemon) == DAEMON[1]
        assert len(probe) == PROBE[0] and _sha(probe) == PROBE[1]
        for name in ("amigentd", "amigentd.000", "amigent-monitor", "amigent-monitor.apollo"):
            assert archive.read(_names_ending(names, name)[0]) == _packaged(name)
        folded = "\n".join(names)
        for banned in EXCLUDED:
            assert banned not in folded
    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        daemon = archive.extractfile(_names_ending(names, "amigentd.apollo")[0]).read()
        probe = archive.extractfile(_names_ending(names, "amigent-apollo-probe")[0]).read()
        assert _sha(daemon) == DAEMON[1] and _sha(probe) == PROBE[1]
        monitor = archive.extractfile(_names_ending(names, "amigent-monitor.apollo")[0]).read()
        assert monitor == _packaged("amigent-monitor.apollo")
        assert any(name.endswith("amiga/amigentd.c") for name in names)
        assert any(name.endswith("amiga/apollo/apollo.c") for name in names)
        folded = "\n".join(names)
        for banned in EXCLUDED:
            assert banned not in folded
