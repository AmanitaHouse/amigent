"""Compatible daemon selection and update protection.

These tests use the packaged files and stand-ins. They do not contact an Amiga.
"""

from amigent import setup
from amigent.client import ExecResult
from amigent.daemons import (
    AFF_FPGA, APOLLO_MARK, CPU_68000, CPU_68010, CPU_68020, CPU_68030, CPU_68040, CPU_68060,
    CPU_68080, EXPERIMENTAL, Machine, available_names, choose, consider_replacement,
    cpu_is_68080, detect_cpu, embedded_version, identify,
)
from amigent.errors import AmigaError
from amigent.paths import AMIGA

BIN = AMIGA / "bin"


def _answers(table):
    def run(command):
        for prefix, code in table:
            if command.startswith(prefix):
                return code
        return 10
    return run


def test_cpu_checks_stop_at_the_first_cpu_the_machine_lacks():
    assert detect_cpu(_answers([("CPU CHECK 68020", 5), ("CPU CHECK 68010", 5)])) == CPU_68000
    assert detect_cpu(_answers([("CPU CHECK 68020", 5), ("CPU CHECK 68010", 0)])) == CPU_68010
    assert detect_cpu(_answers([("CPU CHECK 68020", 0), ("CPU CHECK 68030", 5)])) == CPU_68020
    assert detect_cpu(_answers([
        ("CPU CHECK 68020", 0), ("CPU CHECK 68030", 0), ("CPU CHECK 68040", 0), ("CPU CHECK 68060", 5),
    ])) == CPU_68040
    assert detect_cpu(_answers([("CPU CHECK 68020", 20)])) is None


def test_each_cpu_gets_a_verified_compatible_daemon():
    present = available_names(BIN)
    assert choose(Machine(CPU_68000, False), present).name == "amigentd.000"
    assert choose(Machine(CPU_68010, False), present).name == "amigentd.000"
    for cpu in (CPU_68020, CPU_68030, CPU_68040, CPU_68060):
        assert choose(Machine(cpu, False), present).name == "amigentd"
    assert choose(Machine(CPU_68080, False), present).name == "amigentd"
    assert choose(Machine(CPU_68080, True), present).name == "amigentd.apollo"
    assert choose(Machine(None, None), present).name == "amigentd.000"
    experimental = identify((BIN / "amigentd.080").read_bytes(), BIN)
    assert experimental is not None and experimental.status == EXPERIMENTAL
    assert choose(Machine(CPU_68080, False), present).name != "amigentd.080"


def test_apolloos_without_core_evidence_keeps_the_general_daemon():
    assert not cpu_is_68080({"os": "ApolloOS"})
    assert cpu_is_68080({"cpu": "68080"})
    assert cpu_is_68080({"attn_flags": hex(AFF_FPGA)})
    assert cpu_is_68080({}, "ApolloOS\n68080\n")
    assert not cpu_is_68080({}, "ApolloOS\n")
    present = available_names(BIN)
    assert choose(Machine(CPU_68020, True), present).name == "amigentd"
    assert choose(Machine(CPU_68080, True), present).name == "amigentd.apollo"


def test_updates_keep_specialised_unknown_and_skip_identical(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    binary = package / "bin"
    binary.mkdir(parents=True)
    classic = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 classic"
    apollo = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 " + APOLLO_MARK
    older = b"$VER: amigentd 1.3.0 (1.1.2020)\x00 classic"
    same = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 custom"
    newer = b"$VER: amigentd 1.5.0 (1.1.2027)\x00 classic"
    experimental = b"$VER: amigentd 1.4.0 (1.1.2026)\x00 experimental-080"
    (binary / "amigentd").write_bytes(classic)
    (binary / "amigentd.apollo").write_bytes(apollo)
    (binary / "amigentd.080").write_bytes(experimental)
    monkeypatch.setattr(setup, "AMIGA", package)

    assert consider_replacement(older, apollo, "amigentd.apollo", binary)[0]
    keep, reason = consider_replacement(apollo, classic, "amigentd", binary)
    assert not keep and "Apollo" in reason
    keep, reason = consider_replacement(same, classic, "amigentd", binary)
    assert not keep and "same version" in reason
    keep, reason = consider_replacement(newer, classic, "amigentd", binary)
    assert not keep and "newer" in reason
    keep, reason = consider_replacement(classic, classic, "amigentd", binary)
    assert not keep and "same executable" in reason
    assert consider_replacement(experimental, classic, "amigentd", binary)[0]
    assert embedded_version(older) == (1, 3, 0)


class Channel:
    protocol = 6

    def __init__(self, info, installed):
        self.info = info
        self.files = {"C:amigentd": installed}

    def connect(self):
        pass

    def close(self):
        pass

    def sysinfo(self):
        return self.info

    def read_file(self, path):
        if path not in self.files:
            raise AmigaError("object not found")
        return self.files[path]

    def write_file(self, path, data):
        self.files[path] = data

    def exec(self, command):
        if command.startswith("CPU") or command.startswith("Version FULL"):
            return ExecResult(0, "")
        if command.startswith("Version"):
            return ExecResult(0, "amigentd 1.4.0\n")
        return ExecResult(0, "")


def test_update_keeps_installed_apollo_when_the_package_lacks_one(tmp_path, monkeypatch):
    package = tmp_path / "amiga"
    binary = package / "bin"
    binary.mkdir(parents=True)
    (binary / "amigentd").write_bytes((BIN / "amigentd").read_bytes())
    (binary / "amigentd.000").write_bytes((BIN / "amigentd.000").read_bytes())
    installed = (BIN / "amigentd.apollo").read_bytes()
    monkeypatch.setattr(setup, "AMIGA", package)
    monkeypatch.setattr(setup.time, "sleep", lambda _seconds: None)
    channel = Channel({"os": "ApolloOS", "exec_version": "51.1", "attn_flags": "0x400"}, installed)
    monkeypatch.setattr(setup, "AmigaChannel", lambda host, timeout=30: channel)
    assert setup.update("192.0.2.1", None) == 0
    assert channel.files["C:amigentd"] == installed
    assert "C:amigentd.new" not in channel.files
