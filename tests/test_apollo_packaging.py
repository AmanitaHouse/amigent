"""The Apollo probe and daemon ship in the package. PIP does not.

The installer and updater are driven here, and the wheel and source
distribution are opened. Nothing in this file contacts an Amiga, and a
matching archive does not show that AUDIO has been heard on hardware.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest
from hygiene import inventory, unexpected

from amigent import setup
from amigent.client import ExecResult
from amigent.errors import AmigaError
from amigent.paths import AMIGA
from amigent.serve import FILES

ROOT = Path(__file__).resolve().parent.parent
BIN = AMIGA / "bin"
HUNK = b"\x00\x00\x03\xf3"

# ApolloCrossDev GCC-6.50-Stable rebuild of current src/native sources (1.5.0 $VER).
# Historical HW-smoke 63db83ff…/128744 is SUPERSEDED, not packaged here.
APOLLO = {
    "amigentd.apollo": (132140, "0f1405a1d3494e1bebf6185030139c7858d5636a22cd565a8b432143c90c735d"),
    "amigent-apollo-probe": (3108, "ea78c8c508e2e3c12b719ac20ebf175a4805d34a3458e6a4882118ad417d2bb7"),
    "amigent-monitor.apollo": (22804, "e80c0456d63d435a57febd722caabdf7f1017c99985efa2e016d7f3c9a97bc96"),
}
CLASSIC = {
    "amigentd": (118268, "6d5f6d0e9e91b37eeb75c1d5fd379781826e587d82bd93fbf414656bd5d8466a"),
    "amigentd.000": (124332, "e3feca2da7655ce4d29fa59c38a8a94e554e66af5dae99b060c3df85f1f85104"),
    "amigent-monitor": (18376, "78b49713d9529bbe5804f02525f50bfc3e6431011ed9be0ae39c28643759b80e"),
    "amigentd.080": (108896, "8022366042e0c6e970f84acd16d65231d4fa0fb8d25c83f48c0a6221cb414339"),
}
EXCLUDED = ("amigentd.080", "private/", ".git/", ".githooks/", "ammx.s", "build/apollo")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _packaged(name: str) -> bytes:
    return (BIN / name).read_bytes()


def test_the_packaged_apollo_executables_match_the_staged_build():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'amigent = ["amiga/bin/amigentd.080"]' in pyproject
    assert "amigentd.apollo" not in pyproject.split("exclude-package-data", 1)[1]
    for name, (size, digest) in APOLLO.items():
        data = _packaged(name)
        assert len(data) == size and _sha(data) == digest
        assert data.startswith(HUNK)
        staged = ROOT / "build" / "apollo" / name
        if staged.is_file():
            assert staged.read_bytes() == data
    daemon = _packaged("amigentd.apollo")
    assert b"arne.audio" in daemon and b"ApolloOS" in daemon
    # Opcode 49 / PIP picture supply is not implemented; a reserved SYSINFO key
    # token may still appear in the validated binary string table.
    assert b"pip=1" not in daemon
    probe = _packaged("amigent-apollo-probe")
    assert b"ApolloOS" in probe and b"AmigaOS" in probe and b"arne.audio" not in probe
    assert b"68080" in probe  # AFF_FPGA core line; exit 0 only with ApolloOS + that bit
    monitor = _packaged("amigent-monitor.apollo")
    assert b"$VER: amigent-monitor 1.5.0" in monitor
    for name, (size, digest) in CLASSIC.items():
        data = _packaged(name)
        assert len(data) == size and _sha(data) == digest and data.startswith(HUNK)
    assert FILES == ("amigentd", "amigentd.000")


class SetupLink:
    """The SETUP connection: CPU and the probe return codes, everything else succeeds."""

    def __init__(self, cpu=0, probe=0, probe_present=True):
        self.cpu = cpu
        self.probe = probe
        self.probe_present = probe_present
        self.files = {}
        self.commands = []

    def run(self, command):
        self.commands.append(command)
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


def test_setup_copies_the_apollo_daemon_when_the_probe_says_so():
    link = _install(cpu=0, probe=0)
    assert link.files["C:amigentd.new"] == _packaged("amigentd.apollo")
    assert link.files["T:amigent-apollo-probe"] == _packaged("amigent-apollo-probe")
    assert link.files["SYS:amigent/amigent-monitor"] == _packaged("amigent-monitor.apollo")
    assert b"pip" not in link.files.get("T:amigent-setup", b"")


def test_setup_keeps_the_classic_daemon_when_the_probe_says_amigaos():
    link = _install(cpu=0, probe=5)
    assert link.files["C:amigentd.new"] == _packaged("amigentd")
    assert link.files["T:amigent-apollo-probe"] == _packaged("amigent-apollo-probe")
    assert link.files["SYS:amigent/amigent-monitor"] == _packaged("amigent-monitor")


def test_setup_on_a_68000_never_asks_the_probe():
    link = _install(cpu=5, probe=0)
    assert link.files["C:amigentd.new"] == _packaged("amigentd.000")
    assert "T:amigent-apollo-probe" not in link.files


def test_setup_falls_back_when_the_optional_files_are_absent(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    shutil.copytree(AMIGA, package)
    (package / "bin" / "amigentd.apollo").unlink()
    (package / "bin" / "amigent-apollo-probe").unlink()
    monkeypatch.setattr(setup, "AMIGA", package)
    link = _install(cpu=0, probe=0)
    assert link.files["C:amigentd.new"] == (package / "bin" / "amigentd").read_bytes()
    assert "T:amigent-apollo-probe" not in link.files

    # 1.5.0: without the Apollo daemon the probe is never sent, even when a probe file exists.
    (package / "bin" / "amigent-apollo-probe").write_bytes(b"probe")
    link = _install(cpu=0, probe=0)
    assert link.files["C:amigentd.new"] == (package / "bin" / "amigentd").read_bytes()
    assert "T:amigent-apollo-probe" not in link.files


class UpdateChannel:
    protocol = 6

    def __init__(self, host, timeout=30, info=None, version="", probe="AmigaOS\n", fail_probe=False):
        self.host = host
        self.info = info
        self.version = version
        self.probe = probe
        self.fail_probe = fail_probe
        self.files = {}
        self.commands = []

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
    channel.files["C:amigentd"] = b"old"
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    assert setup.update("192.0.2.1", None) == 0
    return channel


def test_update_on_vampire_amigaos_keeps_the_classic_daemon(monkeypatch):
    channel = _update(monkeypatch, info={"os": "AmigaOS", "exec_version": "47.4", "attn_flags": "0x400"})
    assert channel.files["C:amigentd"] == _packaged("amigentd")
    assert "T:amigent-apollo-probe" not in channel.files


def test_update_falls_back_when_the_probe_is_unsuccessful(monkeypatch):
    refused = _update(monkeypatch, info={}, probe="AmigaOS\n")
    assert refused.files["C:amigentd"] == _packaged("amigentd")
    assert refused.files["T:amigent-apollo-probe"] == _packaged("amigent-apollo-probe")

    failed = _update(monkeypatch, info={}, fail_probe=True)
    assert failed.files["C:amigentd"] == _packaged("amigentd")


_TOP_IGNORED = frozenset({".git", "build", "dist", "private", "bootstrap", "inventory", ".pytest_cache"})
_NATIVE_SDIST_FILES = (
    "src/native/amiga/daemon/amigentd.c",
    "src/native/amiga/apollo/apollo_audio.c",
    "src/native/amiga/apollo/apollo_mmio.c",
    "src/native/amiga/Makefile.apollo",
)


def _names_ending(names, filename):
    return [name for name in names if name.replace("\\", "/").endswith("/" + filename)]


def _stage_source(source_root: Path, dest: Path) -> Path:
    source_root = source_root.resolve()

    def _ignore(dirpath: str, names: list[str]) -> set[str]:
        here = Path(dirpath).resolve()
        ignored = {name for name in names if name in {"__pycache__", ".pytest_cache"} or name.endswith(".egg-info")}
        if here == source_root:
            ignored.update(name for name in names if name in _TOP_IGNORED)
        return ignored

    shutil.copytree(source_root, dest, ignore=_ignore)
    return dest


def _build_distributions(
    source_root: Path, out_dir: Path, work_dir: Path, *, extra_env: dict[str, str] | None = None
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    script = work_dir / "build_dist.py"
    script.write_text(
        "import os\n"
        "import setuptools\n"
        "from setuptools.command.build import build as build_command\n"
        "from setuptools.command.sdist import sdist as sdist_command\n"
        "original = build_command.initialize_options\n"
        "def initialize(self):\n"
        "    original(self)\n"
        "    self.build_base = os.environ['AMIGENT_BUILD_BASE']\n"
        "build_command.initialize_options = initialize\n"
        "if os.environ.get('AMIGENT_FAIL_AFTER_EGG_INFO') == '1':\n"
        "    def fail_sdist(self):\n"
        "        raise RuntimeError('simulated sdist failure after egg_info')\n"
        "    sdist_command.make_distribution = fail_sdist\n"
        "from setuptools.build_meta import build_sdist, build_wheel\n"
        "out = os.environ['AMIGENT_DIST_DIR']\n"
        "print('WHEEL ' + build_wheel(out))\n"
        "print('SDIST ' + build_sdist(out))\n",
        encoding="utf-8",
    )
    env = {**os.environ, "AMIGENT_DIST_DIR": str(out_dir), "AMIGENT_BUILD_BASE": str(work_dir)}
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=source_root, check=False, capture_output=True, text=True, env=env,
    )
    if completed.returncode:
        raise AssertionError(
            f"in-process wheel/sdist build failed ({completed.returncode})\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    produced = dict(
        line.split(" ", 1)
        for line in completed.stdout.splitlines()
        if line.startswith(("WHEEL ", "SDIST "))
    )
    return out_dir / produced["WHEEL"], out_dir / produced["SDIST"]


def _verify_distributions(wheel: Path, sdist: Path, bin_dir: Path = BIN) -> tuple[list[str], list[str]]:
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        for name, (size, digest) in APOLLO.items():
            matches = _names_ending(wheel_names, name)
            assert len(matches) == 1, f"expected 1 {name} in wheel, got {matches}"
            data = archive.read(matches[0])
            assert len(data) == size and _sha(data) == digest and data.startswith(HUNK), f"bad {name} in wheel"
        for name in ("amigentd", "amigentd.000", "amigent-monitor"):
            matches = _names_ending(wheel_names, name)
            assert len(matches) == 1, f"expected 1 {name} in wheel, got {matches}"
            assert archive.read(matches[0]) == (bin_dir / name).read_bytes()
        meta = archive.read(_names_ending(wheel_names, "METADATA")[0]).decode("utf-8")
        requires = [line for line in meta.splitlines() if line.startswith("Requires-Dist:")]
        assert requires and all("apollo" not in line.lower() for line in requires)
        folded = "\n".join(name.replace("\\", "/") for name in wheel_names)
        for banned in EXCLUDED:
            assert banned not in folded
        assert "src/native/" not in folded
    with tarfile.open(sdist, "r:gz") as archive:
        sdist_names = archive.getnames()
        for name, (size, digest) in APOLLO.items():
            matches = _names_ending(sdist_names, name)
            assert len(matches) == 1, f"expected 1 {name} in sdist, got {matches}"
            data = archive.extractfile(matches[0]).read()
            assert len(data) == size and _sha(data) == digest and data.startswith(HUNK), f"bad {name} in sdist"
        for name in ("amigentd", "amigentd.000", "amigent-monitor"):
            matches = _names_ending(sdist_names, name)
            assert len(matches) == 1, f"expected 1 {name} in sdist, got {matches}"
            assert archive.extractfile(matches[0]).read() == (bin_dir / name).read_bytes()
        folded = "\n".join(name.replace("\\", "/") for name in sdist_names)
        for banned in EXCLUDED:
            assert banned not in folded
        assert any(name.endswith("pyproject.toml") for name in sdist_names)
        for native_rel in _NATIVE_SDIST_FILES:
            assert _names_ending(sdist_names, native_rel), f"missing native source {native_rel} in sdist"
        assert _names_ending(sdist_names, "src/amigent.egg-info/PKG-INFO")
        assert _names_ending(sdist_names, "src/amigent.egg-info/SOURCES.txt")
    return wheel_names, sdist_names


def test_wheel_and_sdist_carry_the_apollo_executables(tmp_path):
    before = inventory(ROOT)
    staged = _stage_source(ROOT, tmp_path / "source")
    assert not list(staged.rglob("*.egg-info"))
    wheel, sdist = _build_distributions(staged, tmp_path / "dist", tmp_path / "work")
    assert unexpected(before, inventory(ROOT)) == []
    assert list(staged.rglob("*.egg-info")) == [staged / "src" / "amigent.egg-info"]
    _verify_distributions(wheel, sdist)


def test_packaging_build_is_repeatable_and_ignores_residual_artifacts(tmp_path):
    before = inventory(ROOT)
    dirty = _stage_source(ROOT, tmp_path / "dirty_source")
    (dirty / "src" / "amigent.egg-info").mkdir(parents=True)
    (dirty / "src" / "amigent.egg-info" / "STALE.txt").write_text("stale\n", encoding="utf-8")
    (dirty / "build").mkdir()
    (dirty / "build" / "stale.bin").write_bytes(b"stale")
    (dirty / "dist").mkdir()
    (dirty / "dist" / "stale.whl").write_bytes(b"stale")
    (dirty / "src" / "amigent" / "__pycache__").mkdir()
    (dirty / "src" / "amigent" / "__pycache__" / "stale.pyc").write_bytes(b"stale")

    for run in ("run1", "run2"):
        staged = _stage_source(dirty, tmp_path / run / "source")
        assert not list(staged.rglob("*.egg-info"))
        wheel, sdist = _build_distributions(staged, tmp_path / run / "dist", tmp_path / run / "work")
        wheel_names, sdist_names = _verify_distributions(wheel, sdist)
        archived = "\n".join(wheel_names + sdist_names)
        for stale in ("STALE.txt", "stale.bin", "stale.whl", "stale.pyc"):
            assert stale not in archived
    assert unexpected(before, inventory(ROOT)) == []


def test_packaging_failure_detects_bad_apollo_binary_and_leaves_source_clean(tmp_path):
    before = inventory(ROOT)

    missing_src = _stage_source(ROOT, tmp_path / "missing_src")
    (missing_src / "src" / "amigent" / "amiga" / "bin" / "amigentd.apollo").unlink()
    wheel, sdist = _build_distributions(missing_src, tmp_path / "missing_dist", tmp_path / "missing_work")
    with pytest.raises(AssertionError, match="amigentd.apollo"):
        _verify_distributions(wheel, sdist)

    bad_src = _stage_source(ROOT, tmp_path / "bad_src")
    (bad_src / "src" / "amigent" / "amiga" / "bin" / "amigentd.apollo").write_bytes(b"wrong-apollo-bytes")
    wheel, sdist = _build_distributions(bad_src, tmp_path / "bad_dist", tmp_path / "bad_work")
    with pytest.raises(AssertionError, match="amigentd.apollo"):
        _verify_distributions(wheel, sdist)

    broken_src = _stage_source(ROOT, tmp_path / "broken_src")
    with pytest.raises(AssertionError, match="in-process wheel/sdist build failed"):
        _build_distributions(
            broken_src,
            tmp_path / "broken_dist",
            tmp_path / "broken_work",
            extra_env={"AMIGENT_FAIL_AFTER_EGG_INFO": "1"},
        )
    assert (broken_src / "src" / "amigent.egg-info").is_dir()
    assert unexpected(before, inventory(ROOT)) == []
