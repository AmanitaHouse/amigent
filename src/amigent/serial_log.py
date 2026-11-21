"""The Pi's serial debug output, recorded on the PC (#21).

When an Amiga with Emu68 freezes hard, nothing on the Amiga can tell what
happened, but Emu68 keeps writing to the Pi's serial line. A USB serial
adapter (3.3 V TTL) on the PC reads it; this module records what comes, each
line with the PC's time, into the config folder: serial/<machine-id>.log. It
only reads: nothing is ever sent down the line.

The recorder runs as a thread of the MCP server (amiga_serial_log) or on its
own as `amigent-serial`; both write the same file, and amiga_debug_log and
amiga_status read it whoever wrote it. pyserial is needed only here:
`pip install "amigent[serial]"` (pipx: `pipx inject amigent pyserial`).
Without it, and without an adapter, nothing changes.

Emu68 can narrow its JIT debug output to a range of 68k addresses at run time
through its control registers DBGCTRL ($ed), DBGADDRLO ($ee) and DBGADDRHI
($ef), read and written with MOVEC in supervisor mode. range_program() builds
a tiny AmigaOS program for that; it runs only on Emu68, where those registers
exist.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from . import paths, roster

BAUD = 921600  # Emu68's regular serial output: 921.6 kBit, 8N1
STAMP = "%Y-%m-%d %H:%M:%S"
FLUSH_AFTER = 1.0  # a line without its end is written after this much quiet
READ_SIZE = 4096
NO_PYSERIAL = ('the serial recorder needs pyserial: pip install "amigent[serial]" '
               "(with pipx: pipx inject amigent pyserial)")

DBGCTRL, DBGADDRLO, DBGADDRHI = 0xED, 0xEE, 0xEF
_recorders: dict[str, "Recorder"] = {}
_lock = threading.Lock()


def folder() -> Path:
    return paths.FOLDER / "serial"


def log_file(machine: str) -> Path:
    return folder() / f"{paths.safe(roster.identity(machine) or machine or 'Amiga')}.log"


def state_file(machine: str) -> Path:
    return log_file(machine).with_suffix(".json")


def open_port(port: str, baud: int = BAUD):
    """A pyserial port for reading only, or a clear message without pyserial."""
    try:
        import serial  # noqa: PLC0415 - optional
    except ImportError:
        raise RuntimeError(NO_PYSERIAL) from None
    return serial.Serial(port, baud, timeout=0.2)


def ports() -> list[tuple[str, str]]:
    """(device, description) of the serial ports pyserial sees; [] without pyserial."""
    try:
        from serial.tools import list_ports  # noqa: PLC0415
    except ImportError:
        return []
    return [(p.device, p.description or "") for p in list_ports.comports()]


def pick_port(port: str = "") -> str:
    """The port asked for, else the only USB adapter there is."""
    if port:
        return port
    found = ports()
    usb = [d for d, desc in found if "usb" in (d + desc).lower() or "uart" in desc.lower()]
    if len(usb) == 1:
        return usb[0]
    if not found:
        raise RuntimeError("no serial port found: plug in the USB serial adapter, or name its port "
                           "(COM5, /dev/ttyUSB0)")
    raise RuntimeError("several serial ports, name one: " +
                       ", ".join(f"{d} ({desc})" for d, desc in found))


class Recorder:
    """Reads a serial port in a thread and appends stamped lines to a file.

    port is anything with read(n) and close(); pyserial's Serial or a fake.
    """

    def __init__(self, port, target: Path, name: str = "", baud: int = BAUD,
                 clock: Callable[[], float] = time.time):
        self.port, self.target, self.name, self.baud, self.clock = port, target, name, baud, clock
        self.partial = b""
        self.partial_since = 0.0
        self.lines = 0
        self.last_data = 0.0
        self.error = ""
        self.started = clock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"serial {name}")

    def start(self) -> "Recorder":
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self._mark(f"recording {self.name} at {self.baud} baud")
        self._write_state()
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3)
        self.flush(force=True)
        try:
            self.port.close()
        except Exception:  # noqa: BLE001
            pass
        self._mark(f"stopped recording {self.name}")
        try:
            state_file_for(self.target).unlink()
        except OSError:
            pass

    @property
    def running(self) -> bool:
        return self._thread.is_alive() and not self._stop.is_set()

    def tick(self) -> None:
        """One read; the thread calls it, tests call it directly."""
        try:
            data = self.port.read(READ_SIZE)
        except Exception as e:  # noqa: BLE001 - the adapter was pulled, say so and stop
            self.error = str(e) or type(e).__name__
            self._mark(f"the serial port failed: {self.error}")
            self._stop.set()
            return
        now = self.clock()
        if data:
            self.last_data = now
            if not self.partial:
                self.partial_since = now
            self.partial += data
            *done, self.partial = self.partial.replace(b"\r\n", b"\n").replace(b"\r", b"\n").split(b"\n")
            if done:
                self._lines(done, now)
                self.partial_since = now
        self.flush()

    def flush(self, force: bool = False) -> None:
        if self.partial and (force or self.clock() - self.partial_since >= FLUSH_AFTER):
            self._lines([self.partial], self.clock())
            self.partial = b""

    def _lines(self, lines: list[bytes], when: float) -> None:
        stamp = time.strftime(STAMP, time.localtime(when)) + f".{int(when * 1000) % 1000:03d}"
        with open(self.target, "ab") as f:
            for line in lines:
                f.write(stamp.encode() + b" " + line + b"\n")
        self.lines += len(lines)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.tick()

    def _mark(self, text: str) -> None:
        stamp = time.strftime(STAMP, time.localtime(self.clock()))
        with open(self.target, "ab") as f:
            f.write(f"--- {stamp} amigent: {text} ---\n".encode("utf-8", "replace"))

    def _write_state(self) -> None:
        state_file_for(self.target).write_text(json.dumps(
            {"pid": os.getpid(), "port": getattr(self.port, "port", "") or "", "baud": self.baud,
             "started": time.strftime(STAMP, time.localtime(self.started))}), encoding="utf-8")


def state_file_for(target: Path) -> Path:
    return target.with_suffix(".json")


# ---------------------------------------------------------------- inside the MCP server

def start(machine: str, port: str = "", baud: int = BAUD, opener=open_port) -> Recorder:
    key = roster.identity(machine) or machine
    with _lock:
        running = _recorders.get(key)
        if running and running.running:
            return running
        if opener is open_port and not _has_pyserial():
            raise RuntimeError(NO_PYSERIAL)
        device = pick_port(port) if opener is open_port else port
        recorder = Recorder(opener(device, baud), log_file(machine), name=device, baud=baud).start()
        _recorders[key] = recorder
        return recorder


def stop(machine: str) -> bool:
    with _lock:
        recorder = _recorders.pop(roster.identity(machine) or machine, None)
    if recorder:
        recorder.stop()
    return recorder is not None


def recorder(machine: str) -> Recorder | None:
    return _recorders.get(roster.identity(machine) or machine)


def status(machine: str) -> dict:
    """Who records, where, how much; also a recorder of another process (amigent-serial)."""
    target = log_file(machine)
    out: dict = {"file": str(target)}
    own = recorder(machine)
    if own and own.running:
        out.update(recording=True, port=own.name, baud=own.baud, lines=own.lines)
        if own.last_data:
            out["last_data"] = time.strftime(STAMP, time.localtime(own.last_data))
    else:
        state = state_file_for(target)
        try:
            other = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            other = None
        if other and _alive(other.get("pid", 0)):
            out.update(recording=True, by="amigent-serial", **other)
        else:
            out["recording"] = False
            if own and own.error:
                out["error"] = own.error
    if target.exists():
        out["size"] = target.stat().st_size
    return out


def _alive(pid: int) -> bool:
    if not pid:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except (OSError, ValueError, SystemError):
        return False
    return True


# ---------------------------------------------------------------- reading the record

def read_since(machine: str, position: int) -> tuple[int, str]:
    """What came after position (a byte offset); a shorter file starts from 0."""
    target = log_file(machine)
    try:
        size = target.stat().st_size
    except OSError:
        return 0, ""
    if position > size:
        position = 0
    with open(target, "rb") as f:
        f.seek(position)
        data = f.read()
    return size, data.decode("utf-8", "replace")


def tail(machine: str, lines: int = 20, before: float | None = None) -> list[str]:
    """The last lines of the record; with before (a time stamp), the last ones
    written before it, the moment the Amiga went away or started again."""
    target = log_file(machine)
    try:
        with open(target, "rb") as f:
            f.seek(max(0, target.stat().st_size - 256 * 1024))
            text = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    rows = [r for r in text.splitlines() if r and not r.startswith("--- ")]
    if before is not None:
        limit = time.strftime(STAMP, time.localtime(before))
        rows = [r for r in rows if r[:19] < limit]
    return rows[-lines:]


def exists(machine: str) -> bool:
    return log_file(machine).exists()


# ---------------------------------------------------------------- narrowing Emu68's debug output

def _movec_to(register: int) -> bytes:
    """MOVEC D0,Rc: 4E7B, then D0 (bit 15 clear, register 0) and the control register."""
    return struct.pack(">HH", 0x4E7B, register & 0xFFF)


def range_code(low: int, high: int, control: int) -> bytes:
    """68k code: Supervisor() sets DBGADDRLO, DBGADDRHI and DBGCTRL, then CacheClearU()
    so that units translated before are translated again under the new rules."""
    user = b"".join([
        struct.pack(">HH", 0x2C78, 0x0004),   # move.l 4.w,a6
        struct.pack(">HH", 0x4BFA, 0x000E),   # lea super(pc),a5  (super at 20, extension at 6)
        struct.pack(">HH", 0x4EAE, 0xFFE2),   # jsr -30(a6)   Supervisor
        struct.pack(">HH", 0x4EAE, 0xFD84),   # jsr -636(a6)  CacheClearU
        struct.pack(">H", 0x7000),            # moveq #0,d0
        struct.pack(">H", 0x4E75),            # rts
    ])
    assert len(user) == 20
    supervisor = b"".join([
        struct.pack(">HI", 0x203C, low & 0xFFFFFFFF), _movec_to(DBGADDRLO),
        struct.pack(">HI", 0x203C, high & 0xFFFFFFFF), _movec_to(DBGADDRHI),
        struct.pack(">HI", 0x203C, control & 0xFFFFFFFF), _movec_to(DBGCTRL),
        struct.pack(">H", 0x4E73),            # rte
    ])
    return user + supervisor


def hunk_file(code: bytes) -> bytes:
    """An AmigaOS executable of one code hunk, no relocations."""
    code += b"\0" * (-len(code) % 4)
    longs = len(code) // 4
    return (struct.pack(">IIIII", 0x3F3, 0, 1, 0, 0) + struct.pack(">I", longs)
            + struct.pack(">II", 0x3E9, longs) + code + struct.pack(">I", 0x3F2))


def control(verbose: int, disassemble: bool) -> int:
    """DBGCTRL: DC_VERBOSE in bits 0-1, DC_DISASM in bit 2."""
    if not 0 <= verbose <= 3:
        raise ValueError("verbose is 0 to 3")
    return (verbose & 3) | (4 if disassemble else 0)


def range_program(low: int, high: int, verbose: int = 1, disassemble: bool = False) -> bytes:
    if not 0 <= low <= high <= 0xFFFFFFFF:
        raise ValueError("the range needs 0 <= low <= high <= $FFFFFFFF")
    return hunk_file(range_code(low, high, control(verbose, disassemble)))


# ---------------------------------------------------------------- amigent-serial

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="amigent-serial",
        description="Record the Pi's serial debug output (Emu68) with time stamps until Ctrl+C. "
                    "Reads only; amiga_debug_log and amiga_status show what came.")
    parser.add_argument("port", nargs="?", default="", help="COM5, /dev/ttyUSB0; default: the only USB adapter")
    parser.add_argument("--machine", default="", help="the Amiga it belongs to (default: the default Amiga)")
    parser.add_argument("--baud", type=int, default=BAUD, help=f"default {BAUD}, Emu68's speed")
    parser.add_argument("--list", action="store_true", help="list the serial ports and stop")
    args = parser.parse_args(argv)
    if args.list:
        found = ports()
        print("\n".join(f"{d}  {desc}" for d, desc in found) if found else
              ("no serial ports" if _has_pyserial() else NO_PYSERIAL))
        return 0
    machine = roster.pick(args.machine) or "Amiga"
    if not _has_pyserial():
        print(f"amigent-serial: {NO_PYSERIAL}", file=sys.stderr)
        return 1
    try:
        device = pick_port(args.port)
        rec = Recorder(open_port(device, args.baud), log_file(machine), name=device, baud=args.baud)
    except (RuntimeError, OSError) as e:
        print(f"amigent-serial: {e}", file=sys.stderr)
        return 1
    rec.start()
    print(f"recording {device} at {args.baud} baud into {rec.target}; Ctrl+C stops")
    try:
        while rec.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    rec.stop()
    print(f"{rec.lines} lines recorded" + (f"; {rec.error}" if rec.error else ""))
    return 0 if not rec.error else 1


def _has_pyserial() -> bool:
    try:
        import serial  # noqa: F401, PLC0415
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
