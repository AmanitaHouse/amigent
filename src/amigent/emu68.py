"""Emu68, the 68k JIT that runs an Amiga on a Raspberry Pi (PiStorm and others).

amigentd 1.5.0 answers EMU68 (see docs/PROTOCOL.md): Emu68's own /emu68 node
in devicetree.resource, the Pi's model, boot options and health from the
firmware mailbox, and Emu68's control registers. This module turns its
key=value lines into text, and knows the JIT settings Emu68 documents as
changeable while it runs (docs/internals/ControlRegisters.md in the Emu68
sources). Settings live only in the running Pi: nothing goes to the SD card,
and a restart brings back what cmdline.txt (or PiStormBoot) sets.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from . import roster, secret

SFTHRESH, JITCTRL, JITCTRL2 = 0xEA, 0xEB, 0x1E0
REG_KEY = {SFTHRESH: "jit_sfthresh", JITCTRL: "jitctrl", JITCTRL2: "jitctrl2"}


@dataclass(frozen=True)
class Setting:
    name: str
    reg: int
    shift: int
    bits: int
    low: int
    high: int
    default: int  # EmuControl's LoadDefaults
    text: str
    zero_means: int = 0  # a field value 0 that stands for this number (256 depth, 16 loops)
    offset: int = 0  # field = value - offset (chip slowdown spacing 1-8 is stored as 0-7)

    @property
    def mask(self) -> int:
        return ((1 << self.bits) - 1) << self.shift

    def decode(self, regs: dict[int, int]) -> int:
        raw = (regs[self.reg] & self.mask) >> self.shift
        if raw == 0 and self.zero_means:
            return self.zero_means
        return raw + self.offset

    def encode(self, value: int) -> int:
        raw = value - self.offset
        if self.zero_means and value == self.zero_means:
            raw = 0
        return (raw << self.shift) & self.mask

    @property
    def boolean(self) -> bool:
        return self.bits == 1 and self.high == 1


# Only what Emu68 documents as changeable while it runs. Not offered: the debug
# registers (DBGCTRL, DBGADDRLO/HI: serial output for developers) and the CACR
# cache switch, which belongs to the OS (CacheControl) and 68040.library.
SETTINGS: tuple[Setting, ...] = (
    Setting("chip_slowdown", JITCTRL2, 0, 1, 0, 1, 0,
            "slow down code running from Chip RAM (old busy-loop timing)"),
    Setting("chip_slowdown_spacing", JITCTRL2, 8, 3, 1, 8, 1,
            "with chip_slowdown: slow down every n-th instruction only (1-8)", offset=1),
    Setting("dbf_slowdown", JITCTRL2, 1, 1, 0, 1, 0,
            "DBF busy loops in Chip RAM take as long as three Chip reads (old MOD replayers)"),
    Setting("blitter_wait", JITCTRL2, 11, 1, 0, 1, 0,
            "wait for the blitter before the CPU writes its registers (missing blitter waits)"),
    Setting("ccr_depth", JITCTRL2, 3, 5, 0, 31, 20,
            "how far the CCR optimiser looks ahead; 0 switches it off (self-modifying code)"),
    Setting("insn_depth", JITCTRL, 24, 8, 1, 256, 256,
            "most 68k instructions in one JIT unit", zero_means=256),
    Setting("inline_range", JITCTRL, 8, 16, 0, 65535, 8191,
            "branches within this many bytes are inlined; 0 switches inlining off"),
    Setting("loop_count", JITCTRL, 4, 4, 1, 16, 8,
            "how many times the JIT unrolls a loop", zero_means=16),
    Setting("soft_flush", JITCTRL, 0, 1, 0, 1, 1,
            "a cache flush marks JIT units for a checksum test instead of dropping them"),
    Setting("soft_flush_limit", SFTHRESH, 0, 32, 1, 4000, 500,
            "with soft_flush: above this many units a flush drops them all"),
)
BY_NAME = {s.name: s for s in SETTINGS}
ALIASES = {"sc": "chip_slowdown", "scs": "chip_slowdown_spacing", "cs_dist": "chip_slowdown_spacing",
           "dbf": "dbf_slowdown", "bw": "blitter_wait", "ccrd": "ccr_depth", "icnt": "insn_depth",
           "irng": "inline_range", "lcnt": "loop_count", "sf": "soft_flush", "sfl": "soft_flush_limit"}

# Emu68's cmdline.txt options (docs/Options.md) worth naming when they are set.
BOOT_OPTIONS = {
    "chip_slowdown": "JIT slows down code in Chip RAM from the start",
    "cs_dist": "chip slowdown spacing",
    "vbr_move": "VBR in Fast RAM", "nofpu": "FPU switched off", "limit_2g": "ARM memory limited to 2 GB",
    "z2_ram_size": "Zorro II RAM size", "vc4.mem": "VC4 memory for P96 (MB)",
    "sd.unit0": "SD card unit 0 access", "sd.clock": "SD clock (MHz)", "sd.low_speed": "SD at low speed",
    "one_slot": "one-slot PiStorm32 protocol", "copy_rom": "ROM copied to fast memory (KB)",
    "move_slow_to_chip": "A500 slow RAM mapped as Chip", "enable_cache": "cache on at start",
    "debug": "JIT debug output", "disassemble": "JIT disassembly",
    "async_log": "asynchronous log", "fast_serial": "fast serial log", "buptest": "bus test at start",
    "swap_df0_with_df1": "DF0 swapped with DF1", "swap_df0_with_df2": "DF0 swapped with DF2",
    "swap_df0_with_df3": "DF0 swapped with DF3", "checksum_rom": "ROM checksum fixed",
}

# Raspberry Pi board revision codes, new style (bit 23): type in bits 4-11.
PI_TYPES = {0x00: "A", 0x01: "B", 0x02: "A+", 0x03: "B+", 0x04: "2B", 0x06: "CM1", 0x08: "3B",
            0x09: "Zero", 0x0A: "CM3", 0x0C: "Zero W", 0x0D: "3B+", 0x0E: "3A+", 0x10: "CM3+",
            0x11: "4B", 0x12: "Zero 2 W", 0x13: "400", 0x14: "CM4", 0x15: "CM4S", 0x17: "5",
            0x18: "CM5", 0x19: "500", 0x1A: "CM5 Lite"}

THROTTLED_NOW = {0: "under-voltage", 1: "ARM clock capped", 2: "throttled", 3: "soft temperature limit"}
THROTTLED_SINCE = {16: "under-voltage", 17: "ARM clock capped", 18: "throttled", 19: "soft temperature limit"}

NOT_EMU68 = "not Emu68: this Amiga does not run on a Raspberry Pi with Emu68 (no /emu68 in a device tree)"


def parse(lines: list[str]) -> dict:
    return dict(line.split("=", 1) for line in lines if "=" in line)


def present(info: dict) -> bool:
    return info.get("emu68") == "1"


def _hex(info: dict, key: str) -> int | None:
    try:
        return int(info[key], 16)
    except (KeyError, ValueError):
        return None


def _int(info: dict, key: str) -> int | None:
    try:
        return int(info[key])
    except (KeyError, ValueError):
        return None


def _u64(info: dict, name: str) -> int | None:
    hi, lo = _hex(info, f"{name}_hi"), _hex(info, f"{name}_lo")
    return None if hi is None or lo is None else hi << 32 | lo


def registers(info: dict) -> dict[int, int]:
    out = {}
    for reg, key in REG_KEY.items():
        value = _hex(info, key) if reg != SFTHRESH else _int(info, key)
        if value is None:
            raise ValueError(f"amigentd did not report {key}")
        out[reg] = value
    return out


def settings(info: dict) -> dict[str, int]:
    regs = registers(info)
    return {s.name: s.decode(regs) for s in SETTINGS}


def board(revision: int) -> tuple[str, int | None]:
    """Pi type and memory in MB from a board revision code; ('', None) for old-style codes."""
    if not revision & (1 << 23):
        return "", None
    kind = PI_TYPES.get((revision >> 4) & 0xFF, f"type {(revision >> 4) & 0xFF:#x}")
    return kind, 256 << ((revision >> 20) & 7)


def throttled(value: int) -> tuple[list[str], list[str]]:
    """(now, since power on) from the firmware's get_throttled bits."""
    return ([t for b, t in THROTTLED_NOW.items() if value >> b & 1],
            [t for b, t in THROTTLED_SINCE.items() if value >> b & 1])


def health_warning(info: dict) -> str:
    """A line for amiga_status when the Pi reported under-voltage or throttling, else ''."""
    value = _hex(info, "throttled")
    if not present(info) or value is None:
        return ""
    now, since = throttled(value)
    if not now and not since:
        return ""
    parts = []
    if now:
        parts.append("now: " + ", ".join(now))
    if since:
        parts.append("since power on: " + ", ".join(since))
    weak = "under-voltage" in now + since
    return ("The Raspberry Pi reports " + "; ".join(parts) + "."
            + (" A weak power supply is a common cause of freezes under Emu68." if weak else ""))


def boot_options(bootargs: str) -> list[str]:
    out = []
    for word in bootargs.split():
        key = word.split("=", 1)[0]
        if key in BOOT_OPTIONS:
            out.append(f"{word} ({BOOT_OPTIONS[key]})")
    return out


def mips(before: dict, after: dict) -> dict | None:
    """68k and ARM instructions a second between two counter readings, and JIT misses."""
    try:
        freq = int(after["cntfrq"])
    except (KeyError, ValueError):
        return None
    c0, c1 = _u64(before, "cnt"), _u64(after, "cnt")
    i0, i1 = _u64(before, "insn"), _u64(after, "insn")
    a0, a1 = _u64(before, "arm"), _u64(after, "arm")
    if None in (c0, c1, i0, i1) or not freq or c1 <= c0:
        return None
    seconds = (c1 - c0) / freq
    out = {"seconds": seconds, "m68k_mips": (i1 - i0) / seconds / 1e6}
    if a0 is not None and a1 is not None:
        out["arm_mips"] = (a1 - a0) / seconds / 1e6
    m0, m1 = _int(before, "jit_cmiss"), _int(after, "jit_cmiss")
    if m0 is not None and m1 is not None:
        out["misses_per_second"] = ((m1 - m0) & 0xFFFFFFFF) / seconds
    return out


def mips_line(rate: dict | None) -> str:
    if not rate:
        return ""
    line = f"Emu68: {rate['m68k_mips']:.1f} million 68k instructions a second"
    if "arm_mips" in rate:
        line += f" ({rate['arm_mips']:.1f} million ARM)"
    if "misses_per_second" in rate:
        misses = rate["misses_per_second"]
        line += f"; {misses:.0f} JIT cache misses a second"
        if misses > 2000:
            line += ", the translator is kept busy (self-modifying code or a cache that flushes often)"
    return line


def describe(info: dict, extras: list[str] | None = None) -> str:
    """The text for amiga_emu68: what runs, health, counters, JIT settings."""
    if not present(info):
        why = info.get("why")
        return NOT_EMU68 + (f" ({why})" if why else "")
    out = []
    name = info.get("idstring") or ("Emu68 " + info["version"] if info.get("version") else "Emu68")
    line = name
    if info.get("version") and info["version"] not in name:
        line += f", version {info['version']}"
    if info.get("variant"):
        line += f", variant {info['variant']}"
    if info.get("git"):
        line += f", git {info['git'][:12]}"
    out.append(line)
    pi = info.get("model", "")
    revision = _hex(info, "board_revision")
    if revision is not None:
        kind, mb = board(revision)
        if not pi and kind:
            pi = f"Raspberry Pi {kind}"
        if mb:
            pi += f", {mb // 1024} GB RAM" if mb >= 1024 else f", {mb} MB RAM"
    if pi:
        out.append("Pi: " + pi)
    if info.get("bootargs") is not None:
        out.append("boot options (cmdline.txt): " + (info["bootargs"].strip() or "none"))
        named = boot_options(info["bootargs"])
        if named:
            out.extend("  " + n for n in named)
    health = []
    temp = _int(info, "temp")
    if temp is not None:
        text = f"{temp / 1000:.1f} °C"
        high = _int(info, "temp_max")
        if high:
            text += f" (firmware limit {high / 1000:.0f} °C)"
        health.append(text)
    clock = _int(info, "arm_clock_measured") or _int(info, "arm_clock")
    if clock:
        text = f"ARM {clock / 1e6:.0f} MHz"
        top = _int(info, "arm_clock_max")
        if top:
            text += f" of {top / 1e6:.0f}"
        health.append(text)
    volt = _int(info, "core_volt")
    if volt:
        health.append(f"core {volt / 1e6:.2f} V")
    value = _hex(info, "throttled")
    if value is not None:
        now, since = throttled(value)
        health.append("no under-voltage or throttling since power on" if not now and not since
                      else "; ".join(p for p in ("now " + ", ".join(now) if now else "",
                                                  "since power on " + ", ".join(since) if since else "") if p))
    if health:
        out.append("health: " + ", ".join(health))
    elif info.get("mailbox") == "none":
        out.append("health: the Pi's firmware mailbox was not found, so no temperature or clock")
    size, free, count = _int(info, "jit_size"), _int(info, "jit_free"), _int(info, "jit_count")
    if size:
        used = size - (free or 0)
        out.append(f"JIT cache: {used / 2**20:.1f} of {size / 2**20:.1f} MB used, {count} units, "
                   f"{_int(info, 'jit_cmiss')} misses so far")
    insn = _u64(info, "insn")
    if insn is not None:
        out.append(f"68k instructions since start: {insn:,}")
    try:
        now_set = settings(info)
        out.append("JIT settings: " + ", ".join(f"{k}={v}" for k, v in now_set.items()))
    except ValueError:
        pass
    out.extend(extras or [])
    return "\n".join(out)


def requested(changes: dict) -> dict[str, int]:
    """Names (or EmuControl's short forms) and values -> checked settings."""
    out = {}
    for key, value in changes.items():
        name = ALIASES.get(key.lower(), key.lower())
        if name not in BY_NAME:
            raise ValueError(f"unknown JIT setting {key!r}; known: " + ", ".join(BY_NAME))
        s = BY_NAME[name]
        if isinstance(value, bool) or (isinstance(value, str) and value.lower() in ("on", "off", "yes", "no", "true", "false")):
            value = value if isinstance(value, bool) else value.lower() in ("on", "yes", "true")
            if not s.boolean:
                raise ValueError(f"{name} takes a number from {s.low} to {s.high}")
            value = int(value)
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name} takes a number from {s.low} to {s.high}") from None
        if not s.low <= value <= s.high:
            raise ValueError(f"{name} goes from {s.low} to {s.high}, not {value}")
        out[name] = value
    return out


def check(current: dict[str, int], changes: dict[str, int]) -> None:
    """Combinations Emu68's author warned about (Emu68 issues #144 and #232)."""
    after = {**current, **changes}
    if after["insn_depth"] == 1 and after["ccr_depth"] != 0:
        raise ValueError("insn_depth=1 needs ccr_depth=0 as well (Emu68 issues 144 and 232: "
                         "WHDLoad fails otherwise); pass both")


def fields(changes: dict[str, int]) -> list[tuple[int, int, int]]:
    """Settings -> (register, value, mask) for amigentd, one per register."""
    regs: dict[int, list[int]] = {}
    for name, value in changes.items():
        s = BY_NAME[name]
        slot = regs.setdefault(s.reg, [0, 0])
        slot[0] |= s.encode(value)
        slot[1] |= s.mask
    return [(reg, v, m) for reg, (v, m) in sorted(regs.items())]


def restore_fields(before: dict[int, int]) -> list[tuple[int, int, int]]:
    """The saved registers back, only in the documented fields."""
    masks: dict[int, int] = {}
    for s in SETTINGS:
        masks[s.reg] = masks.get(s.reg, 0) | s.mask
    return [(reg, before[reg], masks[reg]) for reg in sorted(masks) if reg in before]


def cli_spec(items: list[tuple[int, int, int]]) -> str:
    """For 'amigentd EMU68JIT <spec>' in a job script."""
    return ",".join(f"{r:x}:{v:x}:{m:x}" for r, v, m in items)


# ---- what was set before, kept on the PC

class Saved:
    """The registers before the first change since the Amiga started, per Amiga."""

    def __init__(self, path: Path):
        self.path = path

    def load(self, booted: float | None) -> dict[int, int] | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if booted is not None and abs(data.get("booted", 0) - booted) > 120:
            self.clear()  # from before a restart: Emu68 starts with its own settings again
            return None
        try:
            return {int(k, 16): int(v) for k, v in data["registers"].items()}
        except (KeyError, ValueError, AttributeError):
            return None

    def keep(self, regs: dict[int, int], booted: float | None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"registers": {f"{k:x}": v for k, v in regs.items()},
                                         "booted": booted or 0, "at": time.strftime("%Y-%m-%d %H:%M:%S")},
                                        indent=1), encoding="utf-8")

    def clear(self) -> None:
        try:
            self.path.unlink()
        except OSError:
            pass


def saved_for(name: str) -> Saved:
    return Saved(secret.FOLDER / "emu68" / f"{secret.safe(roster.identity(name) or 'Amiga')}.json")


def booted_at(sysinfo: dict) -> float | None:
    try:
        return time.time() - int(sysinfo["uptime"])
    except (KeyError, ValueError):
        return None


def note_text(changes: dict[str, int]) -> str:
    return "Emu68 JIT: " + " ".join(f"{k}={v}" for k, v in changes.items())


def from_notes(found: list[str]) -> dict[str, int]:
    """The settings of the last 'Emu68 JIT:' note of a program, {} without one."""
    for text in reversed(found):
        if text.startswith("Emu68 JIT:"):
            out = {}
            for word in text.split(":", 1)[1].split():
                if "=" in word:
                    k, v = word.split("=", 1)
                    try:
                        out.update(requested({k: v}))
                    except ValueError:
                        continue
            return out
    return {}
