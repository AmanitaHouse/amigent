"""Native Amiga sources live under src/native and tests/native."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_native_amiga_tree_exists():
    native = ROOT / "src/native/amiga"
    assert (native / "daemon/amigentd.c").is_file()
    assert (native / "daemon/hookstub.s").is_file()
    assert (native / "daemon/trapstub.s").is_file()
    assert (native / "tools/amigent-monitor.c").is_file()
    assert (native / "tools/amigent-status.c").is_file()
    assert (native / "tools/amigent-levels.c").is_file()
    assert (native / "apollo/apollo_detect.c").is_file()
    assert (native / "apollo/apollo_probe.c").is_file()
    assert (native / "apollo/apollo_audio.c").is_file()
    assert (native / "apollo/apollo_audio.h").is_file()
    assert (native / "apollo/apollo_mmio.c").is_file()
    assert (native / "apollo/apollo_runtime.c").is_file()
    assert (native / "apollo/apollo_start.s").is_file()
    assert (native / "apollo/div64.c").is_file()
    assert (native / "apollo/gcc_support.c").is_file()
    assert (native / "Makefile.apollo").is_file()
    assert (native / "build-amigentd-apollo").is_file()
    assert (native / "examples/repair.d/example.repair.txt").is_file()
    assert (native / "build-amigentd").is_file()
    assert not (ROOT / "amiga").exists()


def test_native_amiga_tests_exist():
    tests = ROOT / "tests/native/amiga"
    assert (tests / "pointer-test.c").is_file()
    assert (tests / "kprintf-test.c").is_file()
    assert (tests / "trace-test.c").is_file()


def test_packaged_binaries_stay_under_amigent_package():
    bins = ROOT / "src/amigent/amiga/bin"
    for name in ("amigentd", "amigentd.000", "amigent-monitor", "amigent-status", "amigent-levels"):
        assert (bins / name).is_file()


def test_build_script_defaults_to_daemon_source():
    text = (ROOT / "src/native/amiga/build-amigentd").read_text(encoding="utf-8")
    assert ".DEF SOURCE daemon/amigentd.c" in text
    assert "src/native/amiga" in text


def test_apollo_makefile_roots_at_repository():
    text = (ROOT / "src/native/amiga/Makefile.apollo").read_text(encoding="utf-8")
    assert "ROOT := $(abspath $(HERE)/../../..)" in text
    assert "APOLLO := $(HERE)/apollo" in text
    assert "CPU_FLAG ?= -m68080" in text
    assert "CC := $(PREFIX)/bin/m68k-amigaos-gcc" in text
    assert "CC ?=" not in text
    assert "PROBE_CFLAGS := -noixemul -O2 -m68000" in text


def test_apollo_makefile_compiler_selection_and_override(tmp_path):
    """Default builds select ApolloCrossDev (-m68080); CI overrides CC and CPU_FLAG (-m68020)."""
    if os.name == "nt" or not shutil.which("make"):
        pytest.skip("requires POSIX GNU make")

    makefile = ROOT / "src/native/amiga/Makefile.apollo"
    apollo_root = tmp_path / "apollo"
    apollo_cc = apollo_root / "Compilers/GCC-6.50-Stable/bin/m68k-amigaos-gcc"
    apollo_cc.parent.mkdir(parents=True)
    apollo_cc.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    apollo_cc.chmod(0o755)

    gcc16_root = tmp_path / "gcc16"
    gcc16_cc = gcc16_root / "bin/m68k-amigaos-gcc"
    gcc16_cc.parent.mkdir(parents=True)
    gcc16_cc.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    gcc16_cc.chmod(0o755)

    # 1. Default ApolloCrossDev invocation (even with ambient host CC=cc in environment):
    #    must select ApolloCrossDev compiler and -m68080 (probe stays -m68000), never host cc.
    base_env = {k: v for k, v in os.environ.items() if k not in {"CC", "PREFIX", "CPU_FLAG"}}
    default_env = {**base_env, "APOLLOCROSSDEV": str(apollo_root), "CC": "cc"}
    default_run = subprocess.run(
        ["make", "-n", "-f", str(makefile), "all"],
        capture_output=True, text=True, env=default_env,
    )
    assert default_run.returncode == 0, default_run.stderr
    lines = default_run.stdout.splitlines()
    daemon_cmds = [ln for ln in lines if "amigentd.c" in ln]
    monitor_cmds = [ln for ln in lines if "amigent-monitor.c" in ln]
    probe_cmds = [ln for ln in lines if "apollo_probe.c" in ln]
    assert daemon_cmds and daemon_cmds[0].startswith(f"{apollo_cc} ")
    assert "-m68080" in daemon_cmds[0] and "-DAMIGENT_APOLLO" in daemon_cmds[0]
    assert monitor_cmds and monitor_cmds[0].startswith(f"{apollo_cc} ") and "-m68080" in monitor_cmds[0]
    assert probe_cmds and probe_cmds[0].startswith(f"{apollo_cc} ")
    assert "-m68000" in probe_cmds[0] and "-m68080" not in probe_cmds[0]

    # 2. Missing ApolloCrossDev compiler must fail cleanly rather than falling back to host cc.
    missing_run = subprocess.run(
        ["make", "-n", "-f", str(makefile), f"PREFIX={tmp_path / 'missing'}", "all"],
        capture_output=True, text=True, env=base_env,
    )
    assert missing_run.returncode != 0
    assert "m68k-amigaos-gcc was not found" in missing_run.stderr

    # 3. Explicit CI command-line override: CC=m68k-amigaos-gcc CPU_FLAG=-m68020.
    ci_env = {**base_env, "PATH": f"{gcc16_cc.parent}:{base_env.get('PATH', '')}"}
    ci_run = subprocess.run(
        [
            "make", "-n", "-f", str(makefile),
            f"PREFIX={gcc16_root}", "CC=m68k-amigaos-gcc", "CPU_FLAG=-m68020", "all",
        ],
        capture_output=True, text=True, env=ci_env,
    )
    assert ci_run.returncode == 0, ci_run.stderr
    ci_lines = ci_run.stdout.splitlines()
    ci_daemon = [ln for ln in ci_lines if "amigentd.c" in ln]
    ci_monitor = [ln for ln in ci_lines if "amigent-monitor.c" in ln]
    ci_probe = [ln for ln in ci_lines if "apollo_probe.c" in ln]
    assert ci_daemon and ci_daemon[0].startswith("m68k-amigaos-gcc ")
    assert "-m68020" in ci_daemon[0] and "-m68080" not in ci_daemon[0]
    assert ci_monitor and ci_monitor[0].startswith("m68k-amigaos-gcc ")
    assert "-m68020" in ci_monitor[0] and "-m68080" not in ci_monitor[0]
    assert ci_probe and ci_probe[0].startswith("m68k-amigaos-gcc ")
    assert "-m68000" in ci_probe[0] and "-m68020" not in ci_probe[0] and "-m68080" not in ci_probe[0]


def test_guide_and_protocol_name_new_paths():
    guide = (ROOT / "docs/GUIDE.md").read_text(encoding="utf-8")
    protocol = (ROOT / "docs/PROTOCOL.md").read_text(encoding="utf-8")
    assert "src/native/amiga/build-amigentd" in guide
    assert "src/native/amiga/daemon/amigentd.c" in guide
    assert "src/native/amiga/daemon/trapstub.s" in protocol
    building = guide.split("## Building amigentd", 1)[1].split("## Translations", 1)[0]
    assert "src/native/amiga/daemon/amigentd.c" in building
    assert "amiga/amigentd.c" not in building
    assert "src/native/amiga/" in building


def test_amiga_workflow_uses_native_paths():
    text = (ROOT / ".github/workflows/amiga.yml").read_text(encoding="utf-8")
    assert 'paths: ["src/native/amiga/**"' in text
    assert "src/native/amiga/daemon/amigentd.c" in text
    assert "src/native/amiga/tools/amigent-status.c" in text
    assert "src/native/amiga/tools/amigent-monitor.c" in text
    assert "Makefile.apollo" in text
    assert "amigentd.apollo" in text
    assert "amigent-apollo-probe" in text
    assert "amigent-monitor.apollo" in text
    assert "amiga/amigentd.c" not in text
    assert "make -f src/native/amiga/Makefile.apollo" in text
    assert "CPU_FLAG=-m68020 clean all" in text
    assert "Makefile.apollo" in text and "install" not in text.split("make -f src/native/amiga/Makefile.apollo", 1)[1].splitlines()[0]
    assert "out-apollo-ci" in text
    assert "name: apollo-gcc16-compile-check-ci-only" in text
