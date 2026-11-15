"""The sdist carries native sources. The wheel does not."""

import subprocess
import sys
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
    assert "src/native" not in package.split("[tool.setuptools.package-data]", 1)[1].split("[", 1)[0]


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


def test_build_log_redirection_stays_inside_one_bash_argument():
    text = (ROOT / "src/native/amiga/build-amigentd-apollo").read_text(encoding="utf-8")
    safe = "wsl.exe --exec /bin/bash -lc 'src/native/amiga/build-amigentd-apollo > /tmp/apollo.log 2>&1'"
    assert safe in text
    assert 'bash -lc "' not in text
