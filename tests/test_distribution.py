"""The sdist carries native sources. The wheel does not.

The packaged files in src/amigent/amiga/bin are what a wheel, a source
distribution, and scripts/make_release.py ship.
"""

import hashlib
import importlib.util
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "build" / "egg-info" / "amigent.egg-info" / "SOURCES.txt"

NATIVE = (
    "src/native/amiga/daemon/amigentd.c",
    "src/native/amiga/daemon/hookstub.s",
    "src/native/amiga/Makefile.apollo",
    "src/native/amiga/build-amigentd",
    "src/native/amiga/build-amigentd-apollo",
    "src/native/amiga/platform/apollo/apollo.c",
    "src/native/amiga/platform/apollo/apollo.h",
    "src/native/amiga/platform/apollo/apollo_start.s",
    "src/native/amiga/tools/amigent-monitor.c",
    "src/native/amiga/tools/amigent-status.c",
)
DOCS = ("docs/GUIDE.md", "docs/PROTOCOL.md", "docs/FAQ.md", "CHANGELOG.md", "README.md")
TESTS = (
    "tests/conftest.py",
    "tests/hygiene.py",
    "tests/fakeamiga.py",
    "tests/test_security_contract.py",
    "tests/native/amiga/pointer-test.c",
    "tests/c/zharness_main.c",
    "tests/c/admit_harness.c",
)
SCRIPTS = ("scripts/repo_hygiene.py", "scripts/make_release.py")


def test_manifest_states_the_sdist_policy():
    text = (ROOT / "MANIFEST.in").read_text(encoding="utf-8")
    for line in (
        "graft docs",
        "graft scripts",
        "graft tests",
        "graft src/native",
        "prune build",
        "prune dist",
        "global-exclude *.o",
        "global-exclude a.out",
        "global-exclude apollo_audio.s",
        "global-exclude audio_diag.c",
        "global-exclude audio_diag.h",
        "exclude src/amigent/amiga/bin/amigentd.080",
    ):
        assert line in text.splitlines(), line
    package = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'amigent = ["web/*", "web/locales/*", "macos/*", "amiga/*", "amiga/bin/*"]' in package
    data = package.split("[tool.setuptools.package-data]", 1)[1].split("[", 1)[0]
    assert "src/native" not in data
    assert 'packages = ["amigent"]' in package
    assert 'amigent = "src/amigent"' in package
    assert 'where = ["src"]' not in package


def test_sdist_list_has_native_sources_and_not_the_wheel_extras():
    try:
        import setuptools  # noqa: F401
    except ImportError:
        pytest.skip("setuptools is not installed")
    from setuptools import find_packages
    done = subprocess.run(
        [sys.executable, "setup.py", "egg_info"],
        cwd=ROOT, check=True, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    listed = set(SOURCES.read_text(encoding="utf-8").splitlines())
    for rel in NATIVE + DOCS + TESTS + SCRIPTS:
        assert rel in listed, rel
    assert "src/amigent/amiga/bin/amigentd.080" not in listed
    assert "src/amigent/amiga/bin/amigentd.apollo" in listed
    assert not any(rel == "a.out" or rel.endswith("/a.out") for rel in listed)
    assert not any("apollo_audio.s" in rel or "audio_diag" in rel for rel in listed)
    assert not any(rel.startswith("build/") or rel.startswith("dist/") for rel in listed)
    assert find_packages(where=str(ROOT / "src")) == ["amigent"]


APPROVED = {
    "amigentd.apollo": (108300, "f8f54dbd6d7302786a9de450abdd97f4dd3c84b711c3f77939263a4d6d8db6d4"),
    "amigent-monitor": (22604, "bcadce2fbae29c2c5b25db398739d50e2a07dd388c9690b5033130d92bb79acf"),
}
CLASSIC = {
    "amigentd": (87396, "1b469f0668c6dda42276ca23937bc9ccf450733cb50ee076d6cbe9f3dc914a92"),
    "amigentd.000": (92564, "8f08ce1fdd7e5caaf3e35252f95c1d69ba16267ff2bebb5900024346765bc49a"),
}
DIAGNOSTIC = (113324, "b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3")
EXCLUDED = (
    "amigentd.080",
    "apollo_audio.s",
    "audio_diag.c",
    "audio_diag.h",
    "audio_session.c",
    "audio_session.h",
    "audio_session.o",
    "audiodiag.py",
    "audiosession.py",
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_release():
    spec = importlib.util.spec_from_file_location(
        "make_release", ROOT / "scripts" / "make_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert_native(data: bytes, name: str) -> None:
    size, digest = {**APPROVED, **CLASSIC}[name]
    assert len(data) == size, name
    assert _sha256(data) == digest, name
    assert len(data) != DIAGNOSTIC[0]
    assert _sha256(data) != DIAGNOSTIC[1]


def test_packaged_natives_match_the_approved_files():
    bin_dir = ROOT / "src" / "amigent" / "amiga" / "bin"
    for name in APPROVED:
        _assert_native((bin_dir / name).read_bytes(), name)
    for name in CLASSIC:
        _assert_native((bin_dir / name).read_bytes(), name)
    for path in bin_dir.iterdir():
        data = path.read_bytes()
        assert len(data) != DIAGNOSTIC[0], path.name
        assert _sha256(data) != DIAGNOSTIC[1], path.name
        if path.name in EXCLUDED:
            assert path.name == "amigentd.080"


def test_release_files_selects_the_packaged_apollo_daemon_and_monitor():
    module = _make_release()
    files = module.release_files()
    bin_dir = ROOT / "src" / "amigent" / "amiga" / "bin"
    assert files["amigentd.apollo"] == bin_dir / "amigentd.apollo"
    assert files["amigent-monitor"] == bin_dir / "amigent-monitor"
    assert "amigentd.080" not in files
    for name in (*APPROVED, *CLASSIC):
        _assert_native(files[name].read_bytes(), name)
    readme = module.aminet_readme()
    assert "\nVersion:      1.3.1rc1\n" in readme
    assert module.__version__ == "1.3.1rc1"


def test_release_files_reads_the_package_directory_not_build(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    root = tmp_path / "root"
    (root / "src" / "amigent" / "amiga").mkdir(parents=True)
    (root / "LICENSE").write_bytes(b"lic")
    for name in ("amigentd", "amigentd.info", "amigent-status", "amigent-status.info",
                 "amigent-monitor", "amigent-monitor.info", "amigentd.000", "amigentd.apollo"):
        (bin_dir / name).write_bytes(f"pkg-{name}".encode())
    decoy = tmp_path / "build"
    (decoy / "monitor").mkdir(parents=True)
    (decoy / "apollo").mkdir()
    (decoy / "monitor" / "amigent-monitor").write_bytes(b"old-monitor")
    (decoy / "apollo" / "amigentd.apollo").write_bytes(b"old-apollo")
    files = _make_release().release_files(bin_dir, root)
    assert files["amigent-monitor"].read_bytes() == b"pkg-amigent-monitor"
    assert files["amigentd.apollo"].read_bytes() == b"pkg-amigentd.apollo"
    assert files["amigentd.apollo.info"] == bin_dir / "amigentd.info"
    assert "amigentd.080" not in files


def _archive_names(path: Path) -> dict[str, bytes]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return {name: archive.read(name) for name in archive.namelist()}
    with tarfile.open(path) as archive:
        found = {}
        for member in archive.getmembers():
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            found[member.name] = b"" if extracted is None else extracted.read()
        return found


def _declared_version(names: dict[str, bytes]) -> str:
    metas = [data for name, data in names.items()
             if name.endswith("/METADATA") or name.endswith("/PKG-INFO")]
    assert len(metas) == 1, [name for name in names if name.endswith("METADATA") or name.endswith("PKG-INFO")]
    for line in metas[0].decode("utf-8").splitlines():
        if line.startswith("Version:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("package metadata has no Version field")


def _native_member(names: dict[str, bytes], filename: str) -> bytes:
    matches = [data for name, data in names.items() if name.endswith(f"amiga/bin/{filename}")]
    assert len(matches) == 1, filename
    return matches[0]


def test_wheel_and_sdist_carry_the_approved_natives(tmp_path):
    try:
        import pip  # noqa: F401
        import setuptools  # noqa: F401
    except ImportError:
        pytest.skip("pip and setuptools are required to build")
    wheel_dir = tmp_path / "wheel"
    sdist_dir = tmp_path / "sdist"
    wheel_dir.mkdir()
    env = os.environ.copy()
    env["PYTHONPYCACHEPREFIX"] = str(tmp_path / "pycache")
    wheel = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
         "--no-index", "-w", str(wheel_dir), str(ROOT)],
        cwd=ROOT, capture_output=True, text=True, env=env)
    assert wheel.returncode == 0, wheel.stderr
    built = list(wheel_dir.glob("*.whl"))
    assert len(built) == 1, built
    sdist = subprocess.run(
        [sys.executable, "setup.py", "sdist", "--dist-dir", str(sdist_dir)],
        cwd=ROOT, capture_output=True, text=True, env=env)
    assert sdist.returncode == 0, sdist.stderr
    packed = list(sdist_dir.glob("*.tar.gz"))
    assert len(packed) == 1, packed
    for archive in (built[0], packed[0]):
        members = _archive_names(archive)
        for name in (*APPROVED, *CLASSIC):
            _assert_native(_native_member(members, name), name)
        assert _declared_version(members) == "1.3.1rc1"
        if archive.suffix == ".whl":
            assert not any("/native/" in name or name.startswith("native/") for name in members)
            assert archive.name.startswith("amigent-1.3.1rc1-")
        else:
            assert any(name.endswith("src/native/amiga/daemon/amigentd.c") for name in members)
            assert any(name.endswith("src/native/amiga/tools/amigent-monitor.c") for name in members)
            assert archive.name.startswith("amigent-1.3.1rc1.")
        joined = "\n".join(members)
        for banned in EXCLUDED:
            assert banned not in joined, (archive.name, banned)
        assert not any(len(data) == DIAGNOSTIC[0] or _sha256(data) == DIAGNOSTIC[1]
                       for data in members.values())
    target = tmp_path / "installed"
    installed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--target", str(target),
         "--no-deps", "--no-index", str(built[0])],
        capture_output=True, text=True, env=env)
    assert installed.returncode == 0, installed.stderr
    env["PYTHONPATH"] = str(target)
    env["AMIGENT_EXPECT"] = str((target / "amigent" / "amiga").resolve())
    probe = subprocess.run(
        [sys.executable, "-c",
         "import hashlib\n"
         "from amigent.paths import AMIGA\n"
         "from amigent.setup import binary_path, select_build\n"
         "assert select_build(0, {'os': 'ApolloOS'}) == 'amigentd.apollo'\n"
         "assert select_build(5, {'os': 'ApolloOS'}) == 'amigentd.000'\n"
         "assert select_build(0, {'exec_version': '47.96', 'attn_flags': '1024'}) == 'amigentd'\n"
         "apollo = binary_path('amigentd.apollo').read_bytes()\n"
         "monitor = (AMIGA / 'bin' / 'amigent-monitor').read_bytes()\n"
         "classic = binary_path('amigentd').read_bytes()\n"
         "plain = binary_path('amigentd.000').read_bytes()\n"
         "print(len(apollo), hashlib.sha256(apollo).hexdigest())\n"
         "print(len(monitor), hashlib.sha256(monitor).hexdigest())\n"
         "print(len(classic), hashlib.sha256(classic).hexdigest())\n"
         "print(len(plain), hashlib.sha256(plain).hexdigest())\n"
         "import os\n"
         "from pathlib import Path\n"
         "from amigent import __version__\n"
         "print(__version__)\n"
         "print(Path(AMIGA).resolve() == Path(os.environ['AMIGENT_EXPECT']).resolve())\n"],
        capture_output=True, text=True, env=env)
    assert probe.returncode == 0, probe.stderr
    lines = probe.stdout.splitlines()
    assert lines[0] == f"{APPROVED['amigentd.apollo'][0]} {APPROVED['amigentd.apollo'][1]}"
    assert lines[1] == f"{APPROVED['amigent-monitor'][0]} {APPROVED['amigent-monitor'][1]}"
    assert lines[2] == f"{CLASSIC['amigentd'][0]} {CLASSIC['amigentd'][1]}"
    assert lines[3] == f"{CLASSIC['amigentd.000'][0]} {CLASSIC['amigentd.000'][1]}"
    assert lines[4] == "1.3.1rc1"
    assert lines[5] == "True"


def test_editable_install_reads_the_corrected_source_tree(tmp_path):
    """An editable install into an isolated prefix reads the source binaries."""
    try:
        import pip  # noqa: F401
    except ImportError:
        pytest.skip("pip is required")
    prefix = tmp_path / "prefix"
    installed = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(ROOT),
         "--prefix", str(prefix), "--no-deps", "--no-build-isolation", "--no-index"],
        cwd=tmp_path, capture_output=True, text=True)
    assert installed.returncode == 0, installed.stderr
    sites = list(prefix.glob("lib/python*/site-packages"))
    assert len(sites) == 1, sites
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONSAFEPATH"] = "1"
    env["AMIGENT_SITE"] = str(sites[0])
    probe = subprocess.run(
        [sys.executable, "-c",
         "import hashlib, os, site\n"
         "from pathlib import Path\n"
         "site.addsitedir(os.environ['AMIGENT_SITE'])\n"
         "from amigent.paths import AMIGA\n"
         "from amigent.setup import binary_path\n"
         "apollo = binary_path('amigentd.apollo')\n"
         "monitor = AMIGA / 'bin' / 'amigent-monitor'\n"
         "print(apollo.resolve())\n"
         "print(len(apollo.read_bytes()), hashlib.sha256(apollo.read_bytes()).hexdigest())\n"
         "print(len(monitor.read_bytes()), hashlib.sha256(monitor.read_bytes()).hexdigest())\n"
         "from amigent import __version__\n"
         "print(__version__)\n"],
        cwd=tmp_path, env=env, capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr
    lines = probe.stdout.splitlines()
    expected = (ROOT / "src" / "amigent" / "amiga" / "bin" / "amigentd.apollo").resolve()
    assert Path(lines[0]) == expected
    assert lines[1] == f"{APPROVED['amigentd.apollo'][0]} {APPROVED['amigentd.apollo'][1]}"
    assert lines[2] == f"{APPROVED['amigent-monitor'][0]} {APPROVED['amigent-monitor'][1]}"
    assert lines[3] == "1.3.1rc1"


def test_build_log_redirection_stays_inside_one_bash_argument():
    text = (ROOT / "src/native/amiga/build-amigentd-apollo").read_text(encoding="utf-8")
    safe = "wsl.exe --exec /bin/bash -lc 'src/native/amiga/build-amigentd-apollo > /tmp/apollo.log 2>&1'"
    assert safe in text
    assert 'bash -lc "' not in text
