"""The Apollo makefile writes under build/apollo and does not install by default."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "src" / "native" / "amiga"
MAKEFILE = NATIVE / "Makefile.apollo"
SCRIPT = NATIVE / "build-amigentd-apollo"
APOLLO = NATIVE / "platform" / "apollo"

PRODUCT = (
    "apollo.c",
    "apollo.h",
    "apollo_detect.c",
    "apollo_probe.c",
    "apollo_runtime.c",
    "apollo_start.s",
    "ammx.s",
    "div64.c",
    "gcc_support.c",
)
EXCLUDED = ("apollo_audio.s", "audio_diag.c", "audio_diag.h")


def test_apollo_product_sources_are_present_and_experimental_files_are_not():
    for name in PRODUCT:
        assert (APOLLO / name).is_file(), name
    for name in EXCLUDED:
        assert not (APOLLO / name).exists(), name
        assert not (NATIVE / name).exists(), name


def test_apollo_build_writes_under_build_and_install_is_explicit():
    text = MAKEFILE.read_text(encoding="utf-8")
    assert "ROOT := $(abspath $(HERE)/../../..)" in text
    assert "BUILD := $(ROOT)/build/apollo" in text
    assert "APOLLO := $(HERE)/platform/apollo" in text
    assert "DAEMON := $(HERE)/daemon" in text
    assert "-DAMIGENT_APOLLO" in text
    assert "-m68080" in text
    assert "OBJ_NAMES := amigentd.o apollo.o apollo_detect.o gcc_support.o div64.o ammx.o apollo_runtime.o" in text
    assert "all: $(BUILD)/amigentd.apollo $(BUILD)/amigent-apollo-probe" in text
    assert "install: $(BIN)/amigentd.apollo $(BIN)/amigent-apollo-probe" in text
    assert "apollo_audio" not in text
    assert "audio_diag" not in text
    for line in text.splitlines():
        if not line.startswith("\t"):
            continue
        if "$(CC)" in line or "$(VASM)" in line:
            assert "-o $@" in line, line
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'exec make -f "$HERE/Makefile.apollo" "$@"' in script
    assert "install" in script
