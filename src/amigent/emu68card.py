"""Emu68's boot partition on the PiStorm's SD card: read, check, change with a way back.

Emu68 boots from the FAT partition of the Pi's SD card: config.txt names the
kernel (the Emu68 file) and the Kickstart, cmdline.txt carries Emu68's options.
A wrong byte there and the Amiga does not start; nothing on the Amiga can fix
it then. So everything that writes here goes the same careful way:

- nothing is written unless the user put the marker file MARKER on the card;
- every call is a dry run that prints its plan, unless confirm=True;
- before writing, the named files go into a backup on the card and on the PC,
  each read back and compared; a failed backup stops everything;
- new files are written next to the old ones first and verified, only then
  swapped in, then verified again in place;
- only the files the plan names are touched (plus the backup folder and the
  temporary names next to them). No deletes, no raw access, no partitioning.

Works on any Card: AmigaCard goes through amigentd, FolderCard is a mounted
folder on the PC (the rescue with the card in a card reader, and the tests).

    python -m amigent.emu68card list
    python -m amigent.emu68card verify <backup folder>
    python -m amigent.emu68card restore <backup folder> <mounted card folder> [--yes]

Untested on real hardware so far: try it on a second SD card first.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import struct
import sys
import time
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .errors import AmigaError

MARKER = "amigent-write-ok.txt"  # created by the user, never by Amigent
BACKUPS = "amigent-backup"
NEW, OLD = ".amigent-new", ".amigent-old"
SMALL = 64 * 1024  # up to this, a read back compares every byte; above it size and CRC-32
MANIFEST, README = "manifest.json", "README.txt"
UNTESTED = ("Writing to the boot partition is untested on real hardware so far; "
            "try it on a second SD card with a copy of the system first.")


class CardError(AmigaError):
    """Refused or failed; nothing beyond what the message says was changed."""


# ---- the card: a folder on the PC, or a volume on the Amiga


class FolderCard:
    """The boot partition mounted on the PC, or any folder that stands in for it."""

    def __init__(self, root):
        self.root = Path(root)
        self.label = str(self.root)

    def _path(self, rel: str) -> Path:
        rel = _clean(rel)
        return self.root.joinpath(*rel.split("/"))

    def _find(self, rel: str) -> Path | None:
        """FAT ignores case; so does this."""
        here = self.root
        for part in _clean(rel).split("/"):
            try:
                names = {p.name.lower(): p for p in here.iterdir()}
            except OSError:
                return None
            here = names.get(part.lower())
            if here is None:
                return None
        return here

    def read(self, rel: str) -> bytes:
        path = self._find(rel)
        if path is None or not path.is_file():
            raise CardError(f"{rel}: not on the card")
        return path.read_bytes()

    def size(self, rel: str) -> int | None:
        path = self._find(rel)
        return path.stat().st_size if path is not None and path.is_file() else None

    def crc(self, rel: str, size: int = 0) -> int:
        return zlib.crc32(self.read(rel))

    def write(self, rel: str, data: bytes) -> None:
        path = self._path(rel)
        with open(path, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    def makedirs(self, rel: str) -> None:
        self._path(rel).mkdir(parents=True, exist_ok=True)

    def copy(self, src: str, dst: str) -> None:
        shutil.copyfile(self._find(src) or self._path(src), self._path(dst))

    def rename(self, old: str, new: str) -> None:
        if self._find(new) is not None:
            raise CardError(f"{new}: already there")
        os.rename(self._find(old) or self._path(old), self._path(new))

    def delete(self, rel: str) -> None:
        path = self._find(rel)
        if path is not None:
            path.unlink()

    def files(self) -> list[tuple[str, int]]:
        out = []
        for path in sorted(self.root.rglob("*")):
            if path.is_file():
                out.append((path.relative_to(self.root).as_posix(), path.stat().st_size))
        return out

    def free(self) -> int | None:
        try:
            return shutil.disk_usage(self.root).free
        except OSError:
            return None

    def flush(self) -> None:
        pass  # every write was fsynced


class AmigaCard:
    """The boot partition as a volume on the Amiga, through amigentd.

    call runs each step (the server passes its reconnecting _with_ctl)."""

    def __init__(self, ctl, volume: str, call=None):
        self.ctl, self.call = ctl, call or (lambda fn: fn())
        self.volume = volume if volume.endswith(":") else volume + ":"
        self.label = self.volume

    def path(self, rel: str) -> str:
        rel = _clean(rel)
        if '"' in rel:
            raise CardError(f"{rel}: a name with a quote is not handled")
        return self.volume + rel

    def read(self, rel: str) -> bytes:
        try:
            return self.call(lambda: self.ctl.read_file(self.path(rel)))
        except AmigaError as e:
            raise CardError(f"{rel}: {e}") from e

    def size(self, rel: str) -> int | None:
        try:
            entry = self.call(lambda: self.ctl.stat(self.path(rel)))
        except AmigaError:
            return None
        if str(entry.get("type", "")).lower() != "file":
            return None
        return int(entry["size"])

    def crc(self, rel: str, size: int = 0) -> int:
        return self.call(lambda: self.ctl.checksum(self.path(rel), size))

    def write(self, rel: str, data: bytes) -> None:
        self.call(lambda: self.ctl.write_file(self.path(rel), data))

    def makedirs(self, rel: str) -> None:
        done = ""
        for part in _clean(rel).split("/"):
            done = f"{done}/{part}" if done else part
            try:
                self.call(lambda: self.ctl.makedir(self.path(done)))
            except AmigaError:
                if self.call(lambda: self.ctl.stat(self.path(done))).get("type", "").lower() != "dir":
                    raise

    def copy(self, src: str, dst: str) -> None:
        """On the Amiga itself: the bytes never cross the network."""
        size = self.size(src) or 0
        result = self.call(lambda: self.ctl.exec(
            f'Copy "{self.path(src)}" TO "{self.path(dst)}" QUIET', None, 120 + size / 50000))
        if result.rc >= 10:
            raise CardError(f"Copy {src} failed (rc {result.rc}): {result.output.strip()}")

    def rename(self, old: str, new: str) -> None:
        self.call(lambda: self.ctl.rename(self.path(old), self.path(new)))

    def delete(self, rel: str) -> None:
        self.call(lambda: self.ctl.delete(self.path(rel)))

    def files(self) -> list[tuple[str, int]]:
        entries = self.call(lambda: self.ctl.walk(self.volume))
        return sorted((e["name"], int(e["size"])) for e in entries
                      if isinstance(e, dict) and str(e.get("type", "")).upper() == "FILE")

    def free(self) -> int | None:
        try:
            volumes = self.call(lambda: self.ctl.volumes())
        except AmigaError:
            return None
        for v in volumes:
            if v["name"].lower() == self.volume.lower():
                return int(v["free"])
        return None

    def flush(self) -> None:
        """Make the file system put what it holds onto the card."""
        try:
            self.call(lambda: self.ctl.flush([self.volume]))
        except AmigaError:
            pass


def _clean(rel: str) -> str:
    rel = rel.replace("\\", "/").strip("/")
    parts = rel.split("/")
    if not rel or any(p in ("", ".", "..") for p in parts) or ":" in rel:
        raise CardError(f"{rel!r}: not a plain path on the card")
    return rel


def _has(card, rel: str) -> bool:
    return card.size(rel) is not None


def _ours(rel: str) -> bool:
    return rel.lower().split("/")[0] == BACKUPS


# ---- what is on the card


VER = re.compile(rb"\$VER: Emu68 ([0-9]+\.[0-9]+(?:\.[0-9]+)?(?:-[A-Za-z0-9.]+)?)")
MODULE_VER = re.compile(rb"\$VER: (devicetree|brcm-sdhc|brcm-emmc|68040) ([0-9]+)\.([0-9]+)")
MODULE_NAMES = {"devicetree": "devicetree.resource", "brcm-sdhc": "brcm-sdhc.device",
                "brcm-emmc": "brcm-emmc.device", "68040": "68040.library"}


def unpack_kernel(data: bytes) -> bytes:
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except (OSError, EOFError):
            return b""
    return data


def kernel_version(data: bytes) -> str | None:
    """'1.0.7' from the $VER string inside an Emu68 file (packed or not)."""
    m = VER.search(unpack_kernel(data))
    return m.group(1).decode() if m else None


def embedded_modules(data: bytes) -> dict[str, tuple[int, int]]:
    """Versions of the drivers Emu68 brings in its own ROM, by their Amiga names."""
    out = {}
    for m in MODULE_VER.finditer(unpack_kernel(data)):
        out.setdefault(MODULE_NAMES[m.group(1).decode()], (int(m.group(2)), int(m.group(3))))
    return out


def version_tuple(text: str | None) -> tuple:
    if not text:
        return ()
    m = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?(?:-(.*))?", text)
    if not m:
        return ()
    major, minor, patch = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return (major, minor, patch, 0 if m.group(4) else 1, m.group(4) or "")  # a beta before its release


def variant(kernel: str, version: str | None) -> str:
    """The board a kernel file is for. The names changed with Emu68 1.1."""
    name = kernel.lower().removesuffix(".gz")
    eleven = version_tuple(version)[:2] >= (1, 1)
    if name == "emu68-pistorm32lite":
        return "pistorm32"
    if name == "emu68-pistorm-classic":
        return "pistorm-classic"
    if name == "emu68-pistorm":
        return "pistorm32" if eleven else "pistorm-classic"
    if name.startswith("emu68-raspi"):
        return "raspi"
    return "unknown"


VARIANT_TEXT = {"pistorm32": "PiStorm32-lite or PiStorm16", "pistorm-classic":
                "PiStorm with CPLD (A500, A1000, A2000)", "raspi": "bare Raspberry Pi", "unknown": "unknown"}


def config_lines(text: str, key: str) -> list[str]:
    """Values of key= (or 'initramfs ...') lines, in order, comments left out."""
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if key == "initramfs":
            if line.split()[0].lower() == "initramfs" and len(line.split()) > 1:
                out.append(line.split(None, 1)[1].strip())
        elif "=" in line and line.split("=", 1)[0].strip().lower() == key:
            out.append(line.split("=", 1)[1].strip())
    return out


def initramfs_files(value: str) -> list[str]:
    """'firmware.bin.gz,kick.rom 0x800000' -> ['firmware.bin.gz', 'kick.rom']; the ROM comes last."""
    return [p for p in value.split()[0].split(",") if p] if value.split() else []


def board_switch(text: str) -> bool:
    """config.txt picks the kernel by the board, as AmiKit's does: every kernel= line sits
    under a [gpio...] filter ([gpio24=0] PiStorm32-lite, [gpio24=1] CPLD PiStorm)."""
    section, kernels = "", 0
    for line in text.splitlines():
        bare = line.strip()
        if not bare or bare.startswith("#"):
            continue
        if bare.startswith("["):
            section = bare.lower()
        elif "=" in bare and bare.split("=", 1)[0].strip().lower() == "kernel":
            if not section.startswith("[gpio"):
                return False
            kernels += 1
    return kernels > 1


def replace_config(text: str, key: str, new: str, old: str | None = None, every: bool = False) -> str:
    """Only the value of the key line (kernel=..., or the ROM of initramfs); the rest stays byte for byte.
    old: only the kernel= line with that value; every: all initramfs lines (they name the same ROM)."""
    out, hits = [], 0
    for line in text.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        bare = body.strip()
        if bare and not bare.startswith("#"):
            if key == "initramfs" and bare.split()[0].lower() == "initramfs" and len(bare.split()) > 1:
                words = bare.split()
                files = initramfs_files(words[1])
                files[-1] = new
                indent = body[:len(body) - len(body.lstrip())]
                body = indent + " ".join([words[0], ",".join(files)] + words[2:])
                hits += 1
            elif (key != "initramfs" and "=" in bare and bare.split("=", 1)[0].strip().lower() == key
                  and (old is None or bare.split("=", 1)[1].strip().lower() == old.lower())):
                indent = body[:len(body) - len(body.lstrip())]
                body = f"{indent}{bare.split('=', 1)[0].strip()}={new}"
                hits += 1
        out.append(body + ending)
    if hits != 1 and not (every and hits > 1):
        raise CardError(f"config.txt has {hits} {key} lines; change it by hand" if hits else
                        f"config.txt has no {key} line")
    return "".join(out)


_KNOWN: dict[tuple, object] = {}  # (card, file, size, crc) -> what was read out of it


def _about(card, rel: str, fn):
    """fn(bytes) of a file, remembered by its size and CRC: the Amiga computes a CRC in a
    moment, while sending a 2 MB kernel over a slow network takes minutes."""
    size = card.size(rel)
    key = (card.label, rel.lower(), size, card.crc(rel, size or 0))
    if key not in _KNOWN:
        _KNOWN[key] = fn(card.read(rel))
    return _KNOWN[key]


def _rom_text(data: bytes) -> str:
    try:
        what, notes = check_kickstart(data, fix_checksum=True)
        return what + "".join(f"; {n}" for n in notes)
    except CardError as e:
        return f"error: {e}"


@dataclass
class Boot:
    """The boot partition as Emu68 sees it."""
    config: str = ""
    cmdline: str = ""
    kernel: str = ""
    version: str | None = None
    kernels: dict[str, str | None] = field(default_factory=dict)  # several, when the board picks one
    roms: int = 1  # initramfs lines, all naming the same files
    variant: str = "unknown"
    rom: str = ""
    firmware: list[str] = field(default_factory=list)  # FPGA files before the ROM: shown, never written
    overlays: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    pistormboot: list[str] = field(default_factory=list)
    marker: bool = False


def read_boot(card, files: list[tuple[str, int]] | None = None, kernel_bytes: bool = True) -> Boot:
    boot = Boot()
    try:
        boot.config = card.read("config.txt").decode("latin-1")
    except CardError:
        boot.problems.append("config.txt is missing: this is not an Emu68 boot partition")
        return boot
    kernels = list(dict.fromkeys(config_lines(boot.config, "kernel")))
    several = len({k.lower() for k in kernels}) > 1
    if several and not board_switch(boot.config):
        boot.problems.append(f"config.txt names several kernels ({', '.join(kernels)}), by Pi model; "
                             "Amigent changes only cards with one, or with one per board")
    boot.kernel = kernels[0] if kernels else ""
    if several and kernel_bytes:
        for k in kernels[1:]:
            if not _has(card, k):
                boot.problems.append(f"the kernel {k} named in config.txt is not on the card")
            else:
                boot.kernels[k] = _about(card, k, kernel_version)
    if not boot.kernel:
        boot.problems.append("config.txt has no kernel= line")
    elif not _has(card, boot.kernel):
        boot.problems.append(f"the kernel {boot.kernel} named in config.txt is not on the card")
    elif kernel_bytes:
        boot.version = _about(card, boot.kernel, kernel_version)
        if not boot.version:
            boot.problems.append(f"{boot.kernel} carries no Emu68 version string")
    if several and kernel_bytes and boot.kernel:
        boot.kernels = {boot.kernel: boot.version, **boot.kernels}
    boot.variant = variant(boot.kernel, boot.version) if boot.kernel else "unknown"
    rams = config_lines(boot.config, "initramfs")
    boot.roms = len(rams)
    if len({r.lower() for r in rams}) > 1:
        boot.problems.append("config.txt has several different initramfs lines; Amigent changes only "
                             "cards where they name the same files")
    if rams:
        names = initramfs_files(rams[0])
        boot.rom, boot.firmware = names[-1], names[:-1]
        for name in names:
            if not _has(card, name):
                boot.problems.append(f"{name} named by initramfs in config.txt is not on the card")
    else:
        boot.problems.append("config.txt has no initramfs line: no Kickstart file is named")
    boot.overlays = [v for v in config_lines(boot.config, "dtoverlay") if v]
    try:
        boot.cmdline = card.read("cmdline.txt").decode("latin-1")
    except CardError:
        boot.cmdline = ""
    if len(_option_lines(boot.cmdline)) > 1:
        boot.problems.append("cmdline.txt has more than one line; the Pi reads only the first")
    boot.marker = _has(card, MARKER)
    for rel, _ in files if files is not None else []:
        if "pistormboot" in rel.lower():
            boot.pistormboot.append(rel)
    return boot


# ---- cmdline.txt options


@dataclass(frozen=True)
class Option:
    name: str
    kind: str  # flag, choice, int, pattern
    text: str
    choices: tuple = ()
    low: int = 0
    high: int = 0
    pattern: str = ""
    warn: str = ""
    moved: str = ""  # where Emu68 1.1 takes it from instead


def _sd(prefix: str, driver: str, overlay: str) -> list[Option]:
    return [
        Option(f"{prefix}.verbose", "choice", f"{driver}: how much it logs (0 normal, 2 every call)",
               ("0", "1", "2"), moved=f"dtoverlay={overlay},verbose=n"),
        Option(f"{prefix}.unit0", "choice", f"{driver} unit 0, the whole card: off, ro (default) or rw",
               ("off", "ro", "rw"), moved=f"dtoverlay={overlay},unit0=..",
               warn="rw makes the whole card writable, its partition table and the boot partition "
                    "included; one wrong write there and the Amiga does not boot. The boot partition "
                    "can only be written from the Amiga with rw."),
        Option(f"{prefix}.low_speed", "flag", f"{driver}: no 50 MHz mode, no overclocking",
               moved=f"dtoverlay={overlay},low_speed"),
        Option(f"{prefix}.clock", "int", f"{driver}: high speed clock in MHz instead of 50",
               low=1, high=100, moved=f"dtoverlay={overlay},clock=n",
               warn="above 50 MHz the card is overclocked; data can get lost"),
        Option(f"{prefix}.disable", "flag", f"{driver} switched off", moved=f"dtoverlay={overlay},disable",
               warn="without the driver the Amiga partitions on the card are gone, the system "
                    "partition too if it lives there"),
    ]


_DIGITS = r"\d{1,4}([x,]\d{1,4}){0,3}"
OPTIONS: dict[str, Option] = {o.name: o for o in [
    *_sd("sd", "brcm-sdhc.device (Pi 3, Zero 2)", "sdhc"),
    *_sd("emmc", "brcm-emmc.device (Pi 4, CM4)", "emmc"),
    Option("vbr_move", "flag", "68040.library moves the VBR to fast RAM (faster, less compatible "
           "with floppy games)", moved="dtoverlay=emu68,vbr_move"),
    Option("vc4.mem", "int", "MB of VideoCore memory P96 gets (default 16)", low=0, high=1024,
           moved="dtoverlay=videocore,mem=n"),
    Option("one_slot", "flag", "PiStorm32-lite: one-slot protocol, slower chip writes"),
    Option("two_slot", "flag", "PiStorm32-lite: two-slot protocol"),
    Option("debug", "flag", "JIT debug output on the serial line", moved="dtoverlay=diagnostic,debug"),
    Option("disassemble", "flag", "m68k and AArch64 side by side in the debug output",
           moved="dtoverlay=diagnostic,disassemble"),
    Option("async_log", "flag", "debug log through a ring buffer on its own core"),
    Option("fast_serial", "flag", "synchronous serial at 10-50 MBit (needs e.g. an FT232H)"),
    Option("buptest", "int", "bus test of the PiStorm at start over n KB of chip RAM", low=1, high=2048,
           moved="dtoverlay=diagnostic,buptest", warn="a failing test stops Emu68 from starting"),
    Option("bupiter", "int", "rounds of the bus test", low=1, high=1000, moved="dtoverlay=diagnostic,bupiter=n"),
    Option("limit_2g", "flag", "map at most 2 GB of the Pi's memory"),
    Option("enable_c0_slow", "flag", "slow RAM at $C00000-$C7FFFF"),
    Option("enable_c8_slow", "flag", "slow RAM at $C80000-$CFFFFF (needs enable_c0_slow)"),
    Option("enable_d0_slow", "flag", "slow RAM at $D00000-$D7FFFF (needs enable_c0_slow and enable_c8_slow)"),
    Option("move_slow_to_chip", "flag", "the A500's 512K expansion as chip RAM"),
    Option("z2_ram_size", "choice", "Zorro II RAM in MB (default 8)", ("0", "1", "2", "4", "8"),
           moved="dtoverlay=z2ram,size=n"),
    Option("chip_slowdown", "flag", "slow the JIT down for old busy loops", moved="dtoverlay=emu68,SC"),
    Option("SC", "flag", "short for chip_slowdown", moved="dtoverlay=emu68,SC"),
    Option("cs_dist", "int", "chip_slowdown on every n-th instruction", low=1, high=8,
           moved="dtoverlay=emu68,SCS=n"),
    Option("SCS", "int", "short for cs_dist", low=1, high=8, moved="dtoverlay=emu68,SCS=n"),
    Option("dbf_slowdown", "flag", "slow down empty DBF loops", moved="dtoverlay=emu68,DBF"),
    Option("DBF", "flag", "short for dbf_slowdown", moved="dtoverlay=emu68,DBF"),
    Option("blitwait", "flag", "hold chipset accesses while the blitter runs", moved="dtoverlay=emu68,BW"),
    Option("BW", "flag", "short for blitwait", moved="dtoverlay=emu68,BW"),
    Option("fast_page_zero", "flag", "the first 4 KB in fast ARM memory", moved="dtoverlay=emu68,FP0"),
    Option("z3_disable", "flag", "no Zorro III board from Emu68",
           warn="the Emu68 ROM board brings its drivers; without it they are missing"),
    Option("ICNT", "int", "most m68k instructions in one JIT block", low=1, high=256,
           moved="dtoverlay=emu68,ICNT=n"),
    Option("CCRD", "int", "how far the CCR optimiser looks ahead", low=0, high=31,
           moved="dtoverlay=emu68,CCRD=n"),
    Option("IRNG", "int", "largest distance for inlining branches", low=0, high=65535,
           moved="dtoverlay=emu68,IRNG=n"),
    Option("checksum_rom", "flag", "fix the checksum of a changed Kickstart file"),
    Option("copy_rom", "choice", "copy the Amiga's own ROM (KB) to fast memory",
           ("256", "512", "1024", "2048")),
    Option("enable_cache", "flag", "JIT cache on at start (for bare metal software)"),
    Option("nofpu", "flag", "no FPU: every FPU instruction traps", moved="dtoverlay=emu68,no_fpu"),
    Option("swap_df0_with_df1", "flag", "DF0 and DF1 swapped"),
    Option("swap_df0_with_df2", "flag", "DF0 and DF2 swapped"),
    Option("swap_df0_with_df3", "flag", "DF0 and DF3 swapped"),
    Option("logo", "choice", "colour of the Emu68 logo while it starts", ("purple", "black")),
    Option("unicam.boot", "flag", "Framethrower on at start", moved="dtoverlay=unicam,boot"),
    Option("unicam.smooth", "flag", "Framethrower: smooth scaling", moved="dtoverlay=unicam,smooth"),
    Option("unicam.integer", "flag", "Framethrower: whole scaling factors only", moved="dtoverlay=unicam,int"),
    Option("unicam.b", "int", "Framethrower: B of the Mitchell-Netravali scaler", low=0, high=1000,
           moved="dtoverlay=unicam,b=n"),
    Option("unicam.c", "int", "Framethrower: C of the Mitchell-Netravali scaler", low=0, high=1000,
           moved="dtoverlay=unicam,c=n"),
    Option("unicam.aspect", "int", "Framethrower: aspect, 1000 is unchanged", low=333, high=3000,
           moved="dtoverlay=unicam,asp=n"),
    Option("unicam.scaler", "int", "Framethrower: scaler kind", low=0, high=3),
    Option("unicam.phase", "int", "Framethrower: scaler phase", low=0, high=255, moved="dtoverlay=unicam,ph=n"),
    Option("unicam.mode", "pattern", "Framethrower: picture mode, numbers with x or comma", pattern=_DIGITS),
    Option("unicam.size", "pattern", "Framethrower: visible size, WxH", pattern=_DIGITS,
           moved="dtoverlay=unicam,w=n,h=n"),
    Option("unicam.offset", "pattern", "Framethrower: offset, X,Y", pattern=_DIGITS,
           moved="dtoverlay=unicam,x=n,y=n"),
]}
_LOWER = {name.lower(): o for name, o in OPTIONS.items() if not name.isupper()}


def known(name: str) -> Option | None:
    return OPTIONS.get(name) or _LOWER.get(name.lower())


def _option_lines(text: str) -> list[str]:
    """The lines that carry options; a line starting with # is a comment (AmiKit's card has
    one above the options, and Emu68 boots with the line below it)."""
    return [x for x in text.splitlines() if x.strip() and not x.lstrip().startswith("#")]


def parse_cmdline(text: str) -> list[tuple[str, str | None]]:
    """The first option line's words as (name, value); value None for a flag."""
    first = next(iter(_option_lines(text)), "")
    out = []
    for word in first.split():
        name, eq, value = word.partition("=")
        out.append((name, value if eq else None))
    return out


def render_cmdline(words: list[tuple[str, str | None]], old: str) -> str:
    """The new option line in place of the old one; comment lines above it stay as they were."""
    newline = "\r\n" if "\r\n" in old else "\n"
    ending = newline if old.endswith("\n") or not old else ""
    line = " ".join(n if v is None else f"{n}={v}" for n, v in words)
    comments = []
    for x in old.splitlines():
        if x.strip() and not x.lstrip().startswith("#"):
            break
        comments.append(x)
    return "".join(c + newline for c in comments) + line + ending


def check_option(name: str, value: str | None, force: bool = False) -> tuple[str, list[str]]:
    """The option's proper name and warnings; CardError when it is unknown or the value wrong."""
    option = known(name)
    if not re.fullmatch(r"[A-Za-z0-9_.]+", name or ""):
        raise CardError(f"{name!r} is not an option name")
    if value is not None and (not value or re.search(r"\s", value)):
        raise CardError("a value without spaces is needed" + (f" for {name}" if name else ""))
    if option is None:
        if not force:
            raise CardError(f"{name} is not an Emu68 option Amigent knows; force=True writes it anyway "
                            "(Emu68 ignores words it does not know)")
        return name, [f"{name} is unknown to Amigent; written as asked"]
    warns = [option.warn] if option.warn else []
    if option.kind == "flag":
        if value not in (None, ""):
            raise CardError(f"{option.name} is a switch without a value")
    elif value is None:
        raise CardError(f"{option.name} needs a value: " + _values(option))
    elif option.kind == "choice" and value.lower() not in [c.lower() for c in option.choices]:
        raise CardError(f"{option.name}={value}: allowed are {_values(option)}")
    elif option.kind == "int":
        if not value.isdigit() or not option.low <= int(value) <= option.high:
            raise CardError(f"{option.name}={value}: a number from {option.low} to {option.high}")
    elif option.kind == "pattern" and not re.fullmatch(option.pattern, value):
        raise CardError(f"{option.name}={value}: numbers with x or comma, such as 720x576")
    if option.name == "enable_c8_slow":
        warns.append("enable_c8_slow works only with enable_c0_slow")
    if option.name == "enable_d0_slow":
        warns.append("enable_d0_slow works only with enable_c0_slow and enable_c8_slow")
    return option.name, warns


def _values(option: Option) -> str:
    if option.kind == "choice":
        return " | ".join(option.choices)
    if option.kind == "int":
        return f"{option.low}..{option.high}"
    return "numbers with x or comma"


def set_option(text: str, name: str, value: str | None, remove: bool = False,
               force: bool = False) -> tuple[str, list[str]]:
    """cmdline.txt with one option set, changed or removed; every other word stays."""
    if len(_option_lines(text)) > 1 and not force:
        raise CardError("cmdline.txt has more than one line and the Pi reads only the first; "
                        "fix it by hand, or force=True to change the first line and drop the rest")
    words = parse_cmdline(text)
    if remove:
        option = known(name)
        proper = option.name if option else name
        kept = [(n, v) for n, v in words if n.lower() != proper.lower() and n != proper]
        if len(kept) == len(words):
            raise CardError(f"{proper} is not in cmdline.txt")
        return render_cmdline(kept, text), []
    proper, warns = check_option(name, value, force)
    new = (proper, None if (known(proper) and known(proper).kind == "flag") else value)
    out, placed = [], False
    for n, v in words:
        if n == proper or (not proper.isupper() and n.lower() == proper.lower()):
            if not placed:
                out.append(new)
                placed = True
            continue
        out.append((n, v))
    if not placed:
        out.append(new)
    return render_cmdline(out, text), warns


def describe_cmdline(text: str, version: str | None) -> list[str]:
    eleven = version_tuple(version)[:2] >= (1, 1)
    lines = []
    for name, value in parse_cmdline(text):
        option = known(name)
        shown = name if value is None else f"{name}={value}"
        if option is None:
            lines.append(f"  {shown}: unknown to Amigent")
            continue
        note = f"  {shown}: {option.text}"
        if eleven and option.moved:
            note += f" (Emu68 1.1 takes this from config.txt: {option.moved})"
        lines.append(note)
    return lines or ["  (none)"]


# ---- Kickstart


ROM_SIZES = (256 * 1024, 512 * 1024, 1024 * 1024, 2048 * 1024)


def rom_checksum(data: bytes) -> int:
    """Kickstart's sum: all longwords added with end-around carry; a good ROM gives $FFFFFFFF."""
    total = sum(struct.unpack(f">{len(data) // 4}I", data[:len(data) // 4 * 4]))
    while total >> 32:
        total = (total & 0xFFFFFFFF) + (total >> 32)
    return total


def check_kickstart(data: bytes, fix_checksum: bool = False) -> tuple[str, list[str]]:
    """What the ROM is ('Kickstart 40.68, 512 KB') and notes; CardError if Emu68 cannot use it."""
    if data.startswith(b"AMIROMTYPE1"):
        raise CardError("an encrypted Cloanto ROM: it needs rom.key and cannot boot on Emu68 as it is")
    if len(data) not in ROM_SIZES:
        raise CardError(f"{len(data)} bytes: a Kickstart file has 256, 512, 1024 or 2048 KB")
    if data[:4] in (b"\x14\x11\xf9\x4e", b"\x11\x11\xf9\x4e") or data[2:4] == b"\xf9\x4e":
        raise CardError("the file is byte swapped (as for an EPROM burner); Emu68 needs the plain order")
    if data[:2] not in (b"\x11\x11", b"\x11\x14", b"\x11\x13", b"\x11\x12") or data[2:4] != b"\x4e\xf9":
        raise CardError("this does not start like a Kickstart ROM")
    notes = []
    ver, rev = struct.unpack(">HH", data[12:16])
    what = f"Kickstart {ver}.{rev}, {len(data) // 1024} KB"
    if len(data) <= 512 * 1024:
        if rom_checksum(data) != 0xFFFFFFFF:
            if not fix_checksum:
                raise CardError(f"{what}: the checksum is wrong (a changed or damaged ROM); "
                                "with checksum_rom in cmdline.txt Emu68 fixes it at start")
            notes.append("the checksum is wrong; checksum_rom in cmdline.txt fixes it at start")
    else:
        notes.append("the checksum of a ROM larger than 512 KB is not checked")
    return what, notes


# ---- backups


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry(rel: str, data: bytes) -> dict:
    return {"path": rel, "size": len(data), "crc32": f"{zlib.crc32(data):08x}", "sha256": _sha(data)}


def _stamp(kind: str) -> str:
    return time.strftime("%Y-%m-%d-%H%M%S") + "-" + re.sub(r"[^a-z0-9]+", "-", kind.lower()).strip("-")


def readme_text(backup_id: str, full: bool, what: str) -> str:
    scope = "the whole boot partition" if full else "the files a change replaced"
    return f"""Amigent backup {backup_id}
{what}

This folder holds {scope} as it was before, in files/,
with sizes and checksums in manifest.json.

If the Amiga no longer starts:
1. Switch the Amiga off and take the SD card out of the Pi.
2. Put the card into a card reader on a PC (Windows, macOS or Linux).
   The boot partition shows up as a drive or folder (FAT).
3. Copy everything inside amigent-backup/{backup_id}/files/ to the top of
   that drive, replacing the files there. Do not format anything.
   Or with Amigent installed on the PC:
     python -m amigent.emu68card restore <this folder> <the card's drive>
   (it checks the backup, shows what it will write, and writes after --yes).
   Amigent keeps the same backup on the PC as well.
4. Eject the card safely, put it back into the Pi, switch on.

Files the change added are left on the card; they do no harm.
"""


@dataclass
class Backup:
    id: str
    pc: Path
    entries: list[dict]
    absent: list[str]
    full: bool


def make_backup(card, rels: list[str], pc_root: Path, kind: str, *, full: bool = False,
                what: str = "", log=None) -> Backup:
    """The named files, on the PC and on the card, each read back and compared.

    rels that are not on the card are recorded as absent. Raises CardError if any
    copy does not match; then nothing else has been touched."""
    log = log or (lambda text: None)
    base = backup_id = _stamp(kind)
    n = 1
    while (Path(pc_root) / backup_id).exists() or _has(card, f"{BACKUPS}/{backup_id}/{MANIFEST}"):
        n += 1
        backup_id = f"{base}-{n}"
    pc = Path(pc_root) / backup_id
    entries, absent = [], []
    try:
        (pc / "files").mkdir(parents=True, exist_ok=False)
        earlier = _earlier_files(Path(pc_root), exclude=backup_id) if full else {}
        for rel in rels:
            size = card.size(rel)
            if size is None:
                absent.append(rel)
                continue
            data = None
            if rel in earlier and earlier[rel]["size"] == size:
                crc = card.crc(rel, size)
                if f"{crc:08x}" == earlier[rel]["crc32"]:
                    data = earlier[rel]["file"].read_bytes()  # unchanged since the last backup: no transfer
                    if _sha(data) != earlier[rel]["sha256"]:
                        data = None
            if data is None:
                log(f"reading {rel} ({size} bytes)")
                data = card.read(rel)
            if len(data) != size or zlib.crc32(data) != card.crc(rel, size):
                raise CardError(f"{rel}: reading it twice gave different results; the card or the "
                                "link is not reliable, nothing was changed")
            target = pc / "files" / Path(*rel.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if target.read_bytes() != data:
                raise CardError(f"{rel}: the copy on the PC does not read back the same")
            entries.append(_entry(rel, data))
        manifest = {"id": backup_id, "card": card.label, "full": full, "what": what,
                    "files": entries, "absent": absent, "made": time.strftime("%Y-%m-%d %H:%M:%S")}
        manifest_bytes = json.dumps(manifest, indent=1).encode()
        readme = readme_text(backup_id, full, what).encode()
        (pc / MANIFEST).write_bytes(manifest_bytes)
        (pc / README).write_bytes(readme)
        # the same on the card, copied there by the Amiga and checked by checksum
        there = f"{BACKUPS}/{backup_id}"
        card.makedirs(f"{there}/files")
        for e in entries:
            rel = e["path"]
            if "/" in rel:
                card.makedirs(f"{there}/files/{rel.rsplit('/', 1)[0]}")
            log(f"copying {rel} on the card")
            card.copy(rel, f"{there}/files/{rel}")
        card.write(f"{there}/{MANIFEST}", manifest_bytes)
        card.write(f"{there}/{README}", readme)
        card.flush()
        for e in entries:
            rel = f"{there}/files/{e['path']}"
            if card.size(rel) != e["size"] or f"{card.crc(rel, e['size']):08x}" != e["crc32"]:
                raise CardError(f"{e['path']}: the copy on the card does not match")
        for name, data in ((MANIFEST, manifest_bytes), (README, readme)):
            if card.read(f"{there}/{name}") != data:
                raise CardError(f"{there}/{name} does not read back the same")
    except (CardError, AmigaError, OSError) as e:
        raise CardError(f"refused: the backup failed ({e}); nothing on the card was changed"
                        + (f"; the partial backup is in {pc}" if pc.exists() else "")) from e
    return Backup(backup_id, pc, entries, absent, full)


def _earlier_files(root: Path, exclude: str) -> dict:
    """Newest verified copy of each file among earlier backups on this PC."""
    out = {}
    folders = sorted(p for p in root.iterdir() if p.is_dir() and p.name != exclude) if root.exists() else []
    for folder in folders:  # oldest first, so the newest copy wins
        try:
            manifest = json.loads((folder / MANIFEST).read_text())
        except (OSError, ValueError):
            continue
        for e in manifest.get("files", []):
            file = folder / "files" / Path(*e["path"].split("/"))
            if file.is_file():
                out[e["path"]] = {**e, "file": file}
    return out


def load_backup(folder) -> tuple[dict, dict[str, bytes]]:
    """A backup folder (from the PC or from the card), every file checked against its manifest."""
    folder = Path(folder)
    try:
        manifest = json.loads((folder / MANIFEST).read_text())
    except (OSError, ValueError) as e:
        raise CardError(f"{folder}: no readable {MANIFEST} ({e})") from e
    data = {}
    for e in manifest.get("files", []):
        rel = _clean(e["path"])
        try:
            raw = (folder / "files" / Path(*rel.split("/"))).read_bytes()
        except OSError as err:
            raise CardError(f"backup {folder.name}: {rel} is missing ({err})") from err
        if len(raw) != e["size"] or _sha(raw) != e["sha256"]:
            raise CardError(f"backup {folder.name}: {rel} does not match its checksum; do not use it")
        data[rel] = raw
    return manifest, data


def backups(root) -> list[dict]:
    root = Path(root)
    out = []
    for folder in sorted(root.iterdir()) if root.exists() else []:
        try:
            manifest = json.loads((folder / MANIFEST).read_text())
        except (OSError, ValueError):
            continue
        out.append({**manifest, "folder": folder})
    return out


# ---- writing


def _verify(card, rel: str, data: bytes) -> bool:
    if card.size(rel) != len(data):
        return False
    if len(data) <= SMALL:
        return card.read(rel) == data
    return card.crc(rel, len(data)) == zlib.crc32(data)


def install(card, writes: dict[str, bytes], log=None) -> list[str]:
    """Write each file next to its old one, verify all, then swap them in and verify again.

    On any failure the files already swapped go back to their old state. Returns lines
    for the report. Touches only the named files, and their NEW and OLD names."""
    log = log or (lambda text: None)
    lines = []
    for rel in writes:
        if "/" in rel:
            card.makedirs(rel.rsplit("/", 1)[0])  # e.g. overlays/ of a newer Emu68
    for rel, data in writes.items():
        if _has(card, rel + NEW):
            card.delete(rel + NEW)  # our own leftover from an interrupted run
        log(f"writing {rel} ({len(data)} bytes)")
        card.write(rel + NEW, data)
    card.flush()
    for rel, data in writes.items():
        if not _verify(card, rel + NEW, data):
            for r in writes:
                if _has(card, r + NEW):
                    card.delete(r + NEW)
            raise CardError(f"{rel}: the new file did not read back the same; nothing was replaced")
    swapped = []
    try:
        for rel, data in writes.items():
            existed = _has(card, rel)
            if existed:
                if _has(card, rel + OLD):
                    card.delete(rel + OLD)
                card.rename(rel, rel + OLD)
            card.rename(rel + NEW, rel)
            swapped.append((rel, existed))
        card.flush()
        for rel, data in writes.items():
            if not _verify(card, rel, data):
                raise CardError(f"{rel}: does not read back the same in place")
    except (CardError, AmigaError, OSError) as e:
        back = []
        for rel, existed in reversed(swapped):
            try:
                if existed:
                    card.delete(rel)
                    card.rename(rel + OLD, rel)
                    back.append(rel)
            except (CardError, AmigaError, OSError):
                pass
        raise CardError(f"writing failed ({e}); put back: {', '.join(back) or 'nothing'}. "
                        "Check the card before restarting; the backup has every old file") from e
    for rel, existed in swapped:
        if existed:
            card.delete(rel + OLD)
        lines.append(f"  {rel}: written and read back ({len(writes[rel])} bytes)")
    return lines


def refuse_without_marker(card) -> None:
    if not _has(card, MARKER):
        raise CardError(
            f"refused: this card has no {MARKER} in its boot partition, so Amigent only reads it. "
            f"To allow changes, the user creates that file there (any content). {UNTESTED}")


def _dry_run(card) -> str:
    if _has(card, MARKER):
        return "Dry run: nothing was written. Call again with confirm=True once the user agrees."
    return (f"Dry run: nothing was written. Writing would be refused: the card has no {MARKER}; "
            "the user creates it in the boot partition to allow changes.")


def describe_plan(card, writes: dict[str, bytes], extra: list[str] = ()) -> list[str]:
    lines = ["Plan:"]
    for rel, data in writes.items():
        size = card.size(rel)
        if size is None:
            lines.append(f"  {rel}: new file, {len(data)} bytes")
        else:
            lines.append(f"  {rel}: replaced ({size} -> {len(data)} bytes)")
    lines += [f"  {x}" for x in extra]
    lines.append(f"  first a backup of the replaced files, on the card in {BACKUPS}/ and on the PC")
    lines.append(f"  each file is written as <name>{NEW}, read back, then swapped in and read back again")
    return lines


def apply(card, writes: dict[str, bytes], *, kind: str, what: str, pc_root: Path,
          confirm: bool = False, notes: list[str] = (), extra: list[str] = (),
          restart: bool = True, log=None) -> str:
    """The safe way for a change: marker, plan, backup, install, verify."""
    for rel in writes:
        _clean(rel)
        if _ours(rel) or "pistormboot" in rel.lower():
            raise CardError(f"refused: {rel} is not a file Amigent writes")
    plan = describe_plan(card, writes, extra)
    head = [what] + [f"Note: {n}" for n in notes]
    if not confirm:
        return "\n".join(head + plan + [_dry_run(card), UNTESTED])
    refuse_without_marker(card)
    if not writes:
        return "\n".join(head + ["Nothing to write: the card has it already."])
    free = card.free()
    need = sum(len(d) for d in writes.values()) * 2 + 64 * 1024
    if free is not None and free < need:
        raise CardError(f"refused: {free} bytes free on the card, about {need} needed")
    backup = make_backup(card, list(writes), pc_root, kind, what=what, log=log)
    lines = install(card, writes, log=log)
    out = head + [f"Backup {backup.id}: on the card in {BACKUPS}/{backup.id}, on the PC in {backup.pc}"]
    out += ["Written:"] + lines
    if restart:
        out.append("Takes effect at the next start of the Amiga; restart only once the user says so.")
    out.append(f"Taking it back: amiga_emu68_undo(backup='{backup.id}', confirm=True).")
    return "\n".join(out)


def undo(card, pc_root: Path, backup_id: str = "", confirm: bool = False, log=None) -> str:
    """Put the files of one backup (the last one by default) back; itself backed up first."""
    found = [b for b in backups(pc_root) if not backup_id or b["id"] == backup_id]
    if not found:
        raise CardError(f"no backup {backup_id!r} on this PC" if backup_id else "no backup on this PC yet")
    chosen = found[-1]
    manifest, data = load_backup(chosen["folder"])
    if manifest.get("full"):
        data = {rel: raw for rel, raw in data.items() if not _ours(rel)}
    writes = {rel: raw for rel, raw in data.items() if not _same(card, rel, raw)}
    notes = []
    if manifest.get("absent"):
        notes.append("files the change added stay on the card: " + ", ".join(manifest["absent"]))
    return apply(card, writes, kind="undo", what=f"Back to the state of backup {chosen['id']} "
                 f"({manifest.get('what', '')})", pc_root=pc_root, confirm=confirm, notes=notes, log=log)


def _same(card, rel: str, data: bytes) -> bool:
    size = card.size(rel)
    return size == len(data) and card.crc(rel, size) == zlib.crc32(data)


# ---- the changes of #18


def change_option(card, pc_root: Path, name: str, value: str | None, *, remove: bool = False,
                  force: bool = False, confirm: bool = False) -> str:
    boot = read_boot(card, kernel_bytes=False)
    text = boot.cmdline
    new, warns = set_option(text, name, value, remove, force)
    if new == text:
        return f"cmdline.txt has {name} like that already; nothing to do."
    before = text.strip() or "(empty)"
    return apply(card, {"cmdline.txt": new.encode("latin-1")}, kind="option",
                 what=f"cmdline.txt: {before}\n         -> {new.strip() or '(empty)'}",
                 pc_root=pc_root, confirm=confirm, notes=warns)


def change_kickstart(card, pc_root: Path, name: str, data: bytes | None = None,
                     confirm: bool = False) -> str:
    """Boot another Kickstart: name is a file on the card, or the name data gets there."""
    boot = read_boot(card, kernel_bytes=False)
    if not boot.rom:
        raise CardError("config.txt names no Kickstart (no initramfs line); change it by hand")
    name = _clean(name)
    if "/" in name:
        raise CardError("the Kickstart file goes into the top folder of the card")
    if name.lower() == boot.rom.lower():
        return f"{boot.rom} is the Kickstart already; nothing to do."
    on_card = card.size(name)
    writes = {}
    if data is None:
        if on_card is None:
            raise CardError(f"{name} is not on the card")
        data = card.read(name)
    elif on_card is not None and not _same(card, name, data):
        raise CardError(f"a different {name} is on the card already; give the new one another name")
    elif on_card is None:
        writes[name] = data
    fixes = any(n == "checksum_rom" for n, _ in parse_cmdline(boot.cmdline))
    what, notes = check_kickstart(data, fix_checksum=fixes)
    config = replace_config(boot.config, "initramfs", name, every=True)
    writes["config.txt"] = config.encode("latin-1")
    if boot.firmware:
        notes.append(f"the FPGA file {', '.join(boot.firmware)} before the ROM stays as it is")
    notes.append(f"the old Kickstart {boot.rom} stays on the card; going back is "
                 f"amiga_emu68_kickstart(file='{boot.rom}') or amiga_emu68_undo")
    return apply(card, writes, kind="kickstart", what=f"Kickstart: {boot.rom} -> {name} ({what})",
                 pc_root=pc_root, confirm=confirm, notes=notes)


# ---- reading it all: the overview and the health check


SD_UNIT0 = ("sd.unit0 (emmc.unit0 on a Pi 4) decides about unit 0 of the card driver, which is the "
            "whole card: off hides it, ro (the default) lets the Amiga read it, rw lets it write. "
            "Only with rw can the Amiga change the boot partition, and then a wrong write can hit the "
            "partition table and the boot partition, and the Amiga does not start. Set rw only as long "
            "as it is needed, on a card with a backup.")


def overview(card, check: bool = False, write_test: bool = False, log=None) -> str:
    files = card.files()
    boot = read_boot(card, files)
    out = [f"Emu68 boot partition {card.label}"]
    if len(boot.kernels) > 1:
        out.append("  kernels, config.txt picks one by the board ([gpio...] sections):")
        for k, v in boot.kernels.items():
            out.append(f"    {k}, Emu68 {v or 'version unknown'}, for {VARIANT_TEXT[variant(k, v)]}")
    elif boot.kernel:
        out.append(f"  kernel: {boot.kernel}, Emu68 {boot.version or 'version unknown'}, for "
                   f"{VARIANT_TEXT[boot.variant]}")
    if boot.rom and _has(card, boot.rom):
        text = _about(card, boot.rom, _rom_text)
        out.append(f"  Kickstart: {boot.rom}: {text[7:]}" if text.startswith("error: ")
                   else f"  Kickstart: {boot.rom} ({text})")
    if boot.firmware:
        out.append(f"  FPGA/CPLD firmware named in config.txt: {', '.join(boot.firmware)} "
                   "(shown only; Amigent never writes firmware)")
    out.append("  cmdline.txt:")
    out += describe_cmdline(boot.cmdline, boot.version)
    if boot.overlays:
        out.append("  overlays in config.txt: " + "; ".join(boot.overlays))
    if version_tuple(boot.version)[:2] >= (1, 1):
        out.append("  Emu68 1.1 takes most options from overlays in config.txt "
                   "(see overlays/overlays.md on the card); Amigent changes only cmdline.txt")
    total = sum(s for r, s in files if not _ours(r))
    free = card.free()
    out.append(f"  {len([f for f in files if not _ours(f[0])])} files, {total // 1024} KB"
               + (f", {free // 1024} KB free" if free is not None else ""))
    kept = sorted({r.split("/")[1] for r, _ in files if _ours(r) and r.count("/") >= 2})
    if kept:
        out.append(f"  Amigent backups on the card: {', '.join(kept)}")
    if boot.pistormboot:
        out.append("  PiStormBoot is on the card: for changes by hand use its boot menu; Amigent "
                   "leaves its files and backup slots alone")
    out.append(f"  changes: {'allowed (' + MARKER + ' is there)' if boot.marker else 'not allowed, read only; the user creates ' + MARKER + ' on the card to allow them'}")
    if "unit0=rw" in boot.cmdline:
        out.append("  note: unit0=rw is set; " + SD_UNIT0)
    for p in boot.problems:
        out.append(f"  problem: {p}")
    if check:
        out += health(card, files, write_test=write_test and boot.marker, log=log)
        if write_test and not boot.marker:
            out.append("  write speed not measured: changes are not allowed on this card")
    return "\n".join(out)


def health(card, files, write_test: bool = False, log=None) -> list[str]:
    """Read every file once (by checksum on the Amiga): a sector that cannot be read shows up here."""
    out, bad, total = ["Card check:"], [], 0
    started = time.monotonic()
    for rel, size in files:
        try:
            card.crc(rel, size)
            total += size
        except (AmigaError, OSError) as e:
            bad.append(f"{rel}: {e}")
    took = max(time.monotonic() - started, 1e-6)
    out.append(f"  read every file: {len(files) - len(bad)} fine, {len(bad)} with errors; "
               f"{total / took / 1024:.0f} KB/s")
    out += [f"  read error: {b}" for b in bad]
    if write_test:
        probe = bytes(range(256)) * 1024
        rel = "amigent-speed.tmp"
        started = time.monotonic()
        try:
            card.write(rel, probe)
            card.flush()
            ok = _verify(card, rel, probe)
            took = max(time.monotonic() - started, 1e-6)
            out.append(f"  write and read back {len(probe) // 1024} KB: {'fine' if ok else 'DIFFERENT'}, "
                       f"{len(probe) / took / 1024:.0f} KB/s (includes the network)")
        except (AmigaError, OSError) as e:
            out.append(f"  write test failed: {e}")
        finally:
            try:
                card.delete(rel)
            except (AmigaError, OSError):
                pass
    out.append("  errors the card driver counted are not available from the Amiga; a full check "
               "of the FAT needs the card in a PC (chkdsk, fsck.vfat, Disk Utility)")
    return out


# ---- the update of #19


FIRMWARE = re.compile(r"(start\w*\.elf|fixup\w*\.dat|bootcode\.bin|[\w-]+\.dtb|overlays/[\w.-]+\.dtbo|"
                      r"overlays/overlays\.md|licen[cs]e\.broadcom)$", re.I)
KERNEL = re.compile(r"emu68-[\w-]+(\.gz)?$", re.I)


def read_archive(path) -> dict[str, bytes]:
    """An Emu68 release, as zip or unpacked folder, on the PC: name -> bytes."""
    path = Path(path)
    out = {}
    if path.is_dir():
        for file in sorted(path.rglob("*")):
            if file.is_file():
                out[file.relative_to(path).as_posix()] = file.read_bytes()
        return out
    try:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                try:
                    _clean(name)
                except CardError:
                    raise CardError(f"{path.name}: the entry {name!r} points outside; not used")
                out[name] = z.read(info)
    except (OSError, zipfile.BadZipFile) as e:
        raise CardError(f"{path}: not a readable Emu68 release ({e})") from e
    if out and len({n.split("/")[0] for n in out}) == 1 and all("/" in n for n in out):
        top = next(iter(out)).split("/")[0] + "/"
        out = {n[len(top):]: d for n, d in out.items()}  # a zip with one folder around it
    return out


def videocore_needed(version: str | None) -> tuple[tuple, tuple | None]:
    """(lowest, below) VideoCore.card version that fits an Emu68 version; below None = no limit."""
    if version_tuple(version)[:2] >= (1, 1):
        return (1, 5), None
    return (0, 0), (1, 5)


@dataclass
class UpdatePlan:
    writes: dict[str, bytes]
    kernel: str
    version: str
    problems: list[str]
    notes: list[str]
    lines: list[str]


def plan_update(card, archive: dict[str, bytes], boot: Boot, videocore: tuple | None,
                running: str | None = None, files: list | None = None) -> UpdatePlan:
    problems, notes, lines = [], [], []
    on_board = boot.kernels or ({boot.kernel: boot.version} if boot.kernel else {})
    if boot.problems:
        problems += boot.problems
    kernels = {n: d for n, d in archive.items() if "/" not in n and KERNEL.fullmatch(n)}
    versions = {n: kernel_version(d) for n, d in kernels.items()}
    new_version = next((v for v in versions.values() if v), None)
    if not kernels or not new_version:
        problems.append("the archive holds no Emu68 kernel with a version")
    boards = {variant(k, v): k for k, v in reversed(list(on_board.items()))}
    match = [n for n in kernels if variant(n, versions[n]) in boards]
    if kernels and not match:
        boots = " or ".join(VARIANT_TEXT[b] for b in boards) or VARIANT_TEXT[boot.variant]
        problems.append(f"the archive is for {', '.join(VARIANT_TEXT[variant(n, versions[n])] for n in kernels)}; "
                        f"this card boots {boots}")
    kernel = match[0] if match else ""
    old = boards.get(variant(kernel, versions[kernel])) if kernel else boot.kernel
    current = running or on_board.get(old, boot.version)
    for k, v in on_board.items():
        if old and k.lower() != old.lower():
            notes.append(f"{k} for {VARIANT_TEXT[variant(k, v)]} stays at Emu68 {v or '?'}; "
                         "the update is for the other board")
    if new_version and current and version_tuple(new_version) == version_tuple(current):
        problems.append(f"Emu68 {current} is on the card already")
    elif new_version and current and version_tuple(new_version) < version_tuple(current):
        notes.append(f"this goes back from {current} to {new_version}")
    low, below = videocore_needed(new_version)
    if videocore is None:
        notes.append("no VideoCore.card found in LIBS:Picasso96; if the Pi's HDMI output is used for "
                     "RTG, check its version by hand")
    elif videocore < low or (below and videocore >= below):
        need = f"{low[0]}.{low[1]} or newer" if low > (0, 0) else f"older than {below[0]}.{below[1]}"
        problems.append(f"VideoCore.card {videocore[0]}.{videocore[1]} does not fit Emu68 {new_version}, "
                        f"which needs {need}. Put the fitting VideoCore.card into LIBS:Picasso96 first "
                        "(keep a copy of the old one), then update")
    if current and version_tuple(current)[:2] < (1, 1) <= version_tuple(new_version)[:2]:
        moved = [n for n, _ in parse_cmdline(boot.cmdline) if known(n) and known(n).moved]
        if moved:
            notes.append("Emu68 1.1 takes these options from overlays in config.txt, not cmdline.txt: "
                         + ", ".join(moved) + " (see overlays/overlays.md)")
    writes, skipped = {}, []
    on_card = {r.lower(): (r, s) for r, s in (files if files is not None else card.files())}
    for name, data in sorted(archive.items()):
        if name == kernel or (FIRMWARE.fullmatch(name) and not KERNEL.fullmatch(name)):
            target = on_card.get(name.lower(), (name, None))[0]
            if on_card.get(name.lower()) and _same(card, target, data):
                continue
            writes[target] = data
        else:
            skipped.append(name)
    if kernel and old and kernel.lower() != old.lower():
        try:
            if len(on_board) > 1 and kernel.lower() in {k.lower() for k in on_board}:
                raise CardError(f"the new kernel's name {kernel} is the other board's kernel on this "
                                "card; change config.txt by hand")
            writes["config.txt"] = replace_config(boot.config, "kernel", kernel, old=old).encode("latin-1")
            lines.append(f"config.txt: kernel={old} -> kernel={kernel} (only this line)")
        except CardError as e:
            problems.append(str(e))
    if skipped:
        lines.append("left out (the card keeps its own): " + ", ".join(skipped))
    lines.append(f"never written: cmdline.txt, the Kickstart {boot.rom or '-'}, FPGA files, "
                 "the Amiga partitions")
    return UpdatePlan(writes, kernel, new_version or "", problems, notes, lines)


NO_FALLBACK = ("If the new Emu68 does not start, switching the power off and on brings back nothing: "
               "the Pi always boots what is on the card, and PiStormBoot runs only after Emu68 has "
               "started. The way back is then the card in a PC card reader: "
               "python -m amigent.emu68card restore <backup> <card drive>.")


def update(card, archive: dict[str, bytes], pc_root: Path, *, videocore: tuple | None,
           running: str | None = None, confirm: bool = False, log=None) -> str:
    files = card.files()
    boot = read_boot(card, files)
    plan = plan_update(card, archive, boot, videocore, running, files)
    head = [f"Emu68 update on {card.label}: {running or boot.version or '?'} -> {plan.version or '?'}, "
            f"{VARIANT_TEXT[boot.variant]}"]
    head += [f"Note: {n}" for n in plan.notes]
    if plan.problems:
        return "\n".join(head + [f"Stop: {p}" for p in plan.problems] + ["Nothing was written."])
    everything = [r for r, _ in files if not _ours(r)]
    used = sum(s for r, s in files if not _ours(r))
    detail = describe_plan(card, plan.writes, plan.lines)
    detail[-2] = (f"  first a backup of the whole boot partition ({len(everything)} files, {used // 1024} KB): "
                  f"on the card in {BACKUPS}/ with a {README} on how to go back, and on the PC, with checksums")
    warn = [NO_FALLBACK, "A second SD card with a copy of the system is the safer place for a first try.",
            UNTESTED]
    if not confirm:
        return "\n".join(head + detail + warn + [_dry_run(card)])
    refuse_without_marker(card)
    free = card.free()
    need = used + sum(len(d) for d in plan.writes.values()) + 1024 * 1024
    if free is not None and free < need:
        raise CardError(f"refused: {free // 1024} KB free on the card, about {need // 1024} KB needed "
                        "for the backup and the new files")
    backup = make_backup(card, everything, pc_root, "before-update", full=True,
                         what=f"before the update from Emu68 {boot.version} to {plan.version}", log=log)
    written = install(card, plan.writes, log=log)
    pending = {"backup": backup.id, "from": boot.version, "version": plan.version, "kernel": plan.kernel,
               "modules": embedded_modules(archive[plan.kernel]), "when": time.strftime("%Y-%m-%d %H:%M:%S")}
    (Path(pc_root) / "pending-update.json").write_text(json.dumps(pending, indent=1))
    return "\n".join(head + [f"Backup {backup.id} of the whole boot partition: on the card in "
                             f"{BACKUPS}/{backup.id}, on the PC in {backup.pc}", "Written:"] + written + [
        "The update counts once the Amiga has come back with the new version: restart it when the "
        "user says so (amiga_restart), then amiga_emu68_update(after_restart=True).", NO_FALLBACK])


def confirm_update(pc_root: Path, loaded_versions: dict[str, tuple[int, int]],
                   running: str | None = None) -> str:
    """After the restart: does the Amiga run the new Emu68? Checked by the drivers Emu68
    brings in its ROM, unless the running version is known directly."""
    path = Path(pc_root) / "pending-update.json"
    try:
        pending = json.loads(path.read_text())
    except (OSError, ValueError):
        return "No Emu68 update is waiting for confirmation on this PC."
    expected = {k: tuple(v) for k, v in pending.get("modules", {}).items()}
    if running:
        good = version_tuple(running) == version_tuple(pending["version"])
        seen = f"Emu68 {running} runs"
    else:
        common = [k for k in expected if k in loaded_versions]
        if not common:
            return ("The Amiga answers, but none of Emu68's own drivers is in its list, so the version "
                    "cannot be told; check it by hand (e.g. EmuControl).")
        good = all(loaded_versions[k] == expected[k] for k in common)
        seen = ", ".join(f"{k} {loaded_versions[k][0]}.{loaded_versions[k][1]}" for k in common)
    if good:
        path.rename(path.with_name(f"update-{pending['backup']}.json"))
        return (f"Confirmed: Emu68 {pending['version']} runs ({seen}). The backup {pending['backup']} "
                "stays on the card and on the PC.")
    return (f"Not confirmed: expected Emu68 {pending['version']}, but {seen}. The old Emu68 may still run "
            f"(was the Amiga restarted?). Back: amiga_emu68_undo(backup='{pending['backup']}', confirm=True), "
            "or with the card in a PC: python -m amigent.emu68card restore.")


# ---- the rescue on the PC


LOOKS_LIKE_BOOT = ("config.txt", "bootcode.bin", "start4.elf", "start.elf", "cmdline.txt")


def restore_folder(backup, target, yes: bool = False, out=print) -> int:
    """Put a backup back onto the card mounted on the PC. A dry run unless yes."""
    manifest, data = load_backup(backup)
    target = Path(target)
    card = FolderCard(target)
    if not target.is_dir():
        raise CardError(f"{target} is not a folder; give the card's drive, such as E:\\ or /media/user/boot")
    names = [p.name.lower() for p in target.iterdir()]
    if names and not any(n in names for n in LOOKS_LIKE_BOOT):
        raise CardError(f"{target} does not look like a Pi boot partition (no config.txt, bootcode.bin, "
                        "start4.elf); refusing to write there")
    writes = {rel: raw for rel, raw in data.items()
              if not _ours(rel) and not (card.size(rel) == len(raw) and card.read(rel) == raw)}
    out(f"Backup {manifest.get('id')}: {manifest.get('what', '')}; {len(data)} files, every one "
        "matches its checksum.")
    if not writes:
        out("The card holds exactly these files already; nothing to do.")
        return 0
    for rel, raw in writes.items():
        out(f"  {rel}: {'replaced' if card.size(rel) is not None else 'new'}, {len(raw)} bytes")
    extra = sorted(r for r, _ in card.files() if not _ours(r) and r not in data
                   and not r.endswith((NEW, OLD)))
    if extra:
        out("Files not in the backup stay as they are: " + ", ".join(extra))
    if not yes:
        out("Dry run: nothing was written. Run again with --yes to write.")
        return 0
    for line in install(card, writes):
        out(line)
    out("Done. Eject the card safely before taking it out.")
    return 0


def default_root() -> Path:
    from . import paths
    return paths.FOLDER / "emu68"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m amigent.emu68card",
                                     description="Emu68 boot partition backups: list, verify, restore. "
                                     + UNTESTED)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help="the backups on this PC")
    p.add_argument("--root", default=None)
    p = sub.add_parser("verify", help="check a backup against its checksums")
    p.add_argument("backup")
    p = sub.add_parser("restore", help="put a backup onto the card in a card reader")
    p.add_argument("backup", help="a backup folder, from the PC or from the card's amigent-backup")
    p.add_argument("card", help="the mounted boot partition (E:\\, /Volumes/BOOT, /media/user/boot)")
    p.add_argument("--yes", action="store_true", help="write; without it only the plan is shown")
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            root = Path(args.root) if args.root else default_root()
            found = [(machine, b) for machine in (sorted(root.iterdir()) if root.exists() else [])
                     if machine.is_dir() for b in backups(machine)]
            for machine, b in found:
                print(f"{b['folder']}  {'full' if b.get('full') else 'files'}  {b.get('what', '')}")
            if not found:
                print(f"no backups in {root}")
            return 0
        if args.command == "verify":
            manifest, data = load_backup(args.backup)
            print(f"{manifest.get('id')}: {len(data)} files, every one matches its checksum")
            return 0
        return restore_folder(args.backup, args.card, args.yes)
    except CardError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
