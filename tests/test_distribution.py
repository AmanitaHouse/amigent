"""The sdist carries the native sources. The wheel carries only the packaged binaries.

Native sources live in src/native and tests/native. The files a wheel, a source
distribution and scripts/make_release.py ship are in src/amigent/amiga/bin. The
exact bytes of the Apollo daemon, probe and monitor are pinned in
test_apollo_distribution.py, so this file does not repeat those hashes.
"""

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "src" / "amigent" / "amiga" / "bin"

NATIVE = (
    "src/native/amiga/daemon/amigentd.c",
    "src/native/amiga/daemon/hookstub.s",
    "src/native/amiga/daemon/trapstub.s",
    "src/native/amiga/Makefile.apollo",
    "src/native/amiga/build-amigentd",
    "src/native/amiga/build-amigentd-apollo",
    "src/native/amiga/examples/repair.d/example.repair.txt",
    "src/native/amiga/platform/apollo/apollo.c",
    "src/native/amiga/platform/apollo/apollo.h",
    "src/native/amiga/platform/apollo/apollo_mmio.c",
    "src/native/amiga/platform/apollo/apollo_start.s",
    "src/native/amiga/tools/amigent-monitor.c",
    "src/native/amiga/tools/amigent-status.c",
    "tests/native/amiga/kprintf-test.c",
    "tests/native/amiga/pointer-test.c",
    "tests/native/amiga/trace-test.c",
)
SUPPORT = (
    "scripts/repo_hygiene.py",
    "scripts/make_release.py",
    "tests/hygiene.py",
    "tests/test_repo_hygiene.py",
    "docs/GUIDE.md",
    "docs/PROTOCOL.md",
    "README.md",
    "CHANGELOG.md",
)
PACKAGED = (
    "amigentd",
    "amigentd.000",
    "amigentd.apollo",
    "amigent-apollo-probe",
    "amigent-monitor",
    "amigent-monitor.apollo",
)
OLD_FLAT = ("amiga/amigentd.c", "amiga/hookstub.s", "amiga/apollo/", "amiga/Makefile.apollo")


def _relative(name: str) -> str:
    """The archive member without its leading project-version directory."""
    return name.replace("\\", "/").split("/", 1)[-1]


def test_native_sources_sit_in_the_native_tree_and_the_flat_folder_is_gone():
    for rel in NATIVE:
        assert (ROOT / rel).is_file(), rel
    assert not (ROOT / "amiga").exists()


def test_manifest_and_package_data_state_the_distribution_policy():
    lines = (ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    for line in (
        "graft docs",
        "graft scripts",
        "graft tests",
        "graft src/native",
        "prune build",
        "prune dist",
        "global-exclude *.o",
        "global-exclude a.out",
        "exclude src/amigent/amiga/bin/amigentd.080",
    ):
        assert line in lines, line
    assert "graft amiga" not in lines
    package = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    data = package.split("[tool.setuptools.package-data]", 1)[1].split("\n[", 1)[0]
    assert "amiga/bin/*" in data
    assert "native" not in data
    excluded = package.split("[tool.setuptools.exclude-package-data]", 1)[1].split("\n[", 1)[0]
    assert "amiga/bin/amigentd.080" in excluded


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    try:
        import setuptools  # noqa: F401
    except ImportError:
        pytest.skip("setuptools is not installed")
    base = tmp_path_factory.mktemp("dist")
    out = base / "dist"
    out.mkdir()
    script = base / "build_dist.py"
    script.write_text(
        "import os\n"
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
        env={**os.environ, "AMIGENT_DIST_DIR": str(out), "AMIGENT_BUILD_BASE": str(base / "work")},
    )
    produced = dict(line.split(" ", 1) for line in completed.stdout.splitlines()
                    if line.startswith(("WHEEL ", "SDIST ")))
    return out / produced["WHEEL"], out / produced["SDIST"]


def test_sdist_carries_native_sources_tests_and_hygiene_tooling(built):
    _, sdist = built
    with tarfile.open(sdist, "r:gz") as archive:
        members = {_relative(m.name): m for m in archive.getmembers() if m.isfile()}
        for rel in NATIVE + SUPPORT:
            assert rel in members, rel
        assert not any(rel.startswith(OLD_FLAT) for rel in members)
        assert "src/amigent/amiga/bin/amigentd.080" not in members
        for name in PACKAGED:
            packed = archive.extractfile(members[f"src/amigent/amiga/bin/{name}"]).read()
            assert packed == (BIN / name).read_bytes(), name
        assert not any(rel == "a.out" or rel.endswith("/a.out") or rel.endswith(".o") for rel in members)
        assert not any(rel.startswith(("build/", "dist/")) for rel in members)


def test_wheel_carries_the_packaged_binaries_and_no_native_sources(built):
    wheel, _ = built
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for name in PACKAGED:
            assert archive.read(f"amigent/amiga/bin/{name}") == (BIN / name).read_bytes(), name
        assert "amigent/amiga/bin/amigentd.080" not in names
        for name in names:
            assert not name.startswith(("native/", "src/", "tests/", "scripts/")), name
            assert "/native/" not in name, name
            assert not name.endswith((".c", ".s", "Makefile.apollo")), name
