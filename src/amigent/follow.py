"""Copy a growing log from the Amiga to the PC while it grows.

What has reached the PC survives a crash or a hang of the Amiga, also the
part a filesystem such as PFS3 had not yet written to disk: amigentd reads
through the filesystem, which hands out what is still in its buffers. The
debug output (kprintf, Enforcer) is followed the same way.
"""

from __future__ import annotations

import os
import re
import struct
import threading
import time
from pathlib import Path
from typing import Callable

from .errors import AmigaError

DEBUG = "debug"


class Follower:
    """One source, polled every `every` seconds by a thread, appended to `target`.

    fetch(position) returns (new position, new bytes); it raises when the
    Amiga doesn't answer. A position that goes backwards means the file was
    started again, or the Amiga was restarted (debug output).
    """

    def __init__(self, source: str, target: Path, fetch: Callable[[int], tuple[int, bytes]],
                 every: float = 1.0, start: int = 0, on_stop: Callable[[], None] | None = None):
        self.source, self.target, self.fetch, self.every = source, target, fetch, every
        self.on_stop = on_stop
        self.position = start
        self.written = 0
        self.lost_since: float | None = None
        self.error = ""
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"follow {source}")

    def start(self) -> "Follower":
        self.target.parent.mkdir(parents=True, exist_ok=True)
        self._mark(f"following {self.source}")
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self.every + 5)
        self._mark(f"stopped following {self.source}")
        if self.on_stop:
            self.on_stop()
            self.on_stop = None

    def tick(self) -> None:
        """One look; the thread calls it, tests call it directly."""
        try:
            position, data = self.fetch(self.position)
        except Exception as e:  # noqa: BLE001 - a log copier must outlive any failure
            if self.lost_since is None:
                self.lost_since = time.time()
                self.error = str(e) or type(e).__name__
                self._mark(f"the Amiga does not answer: {self.error}")
            return
        if self.lost_since is not None:
            self._mark("the Amiga answers again")
            self.lost_since, self.error = None, ""
        if position < self.position:
            self._mark(f"{self.source} started again")
        if data:
            with open(self.target, "ab") as f:
                f.write(data)
                f.flush()
            self.written += len(data)
        self.position = position

    def _run(self) -> None:
        while not self._stop.wait(self.every):
            self.tick()

    def _mark(self, text: str) -> None:
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.target, "ab") as f:
            f.write(f"\n--- {stamp} amigent: {text} ---\n".encode("iso-8859-1", "replace"))


def file_fetch(read_from: Callable[[str, int], bytes], stat: Callable[[str], dict], path: str):
    """fetch for a file: read only what is new; a shorter file starts over."""
    def fetch(position: int) -> tuple[int, bytes]:
        size = int(stat(path).get("size", 0) or 0)
        if size < position:
            position = 0
        if size == position:
            return position, b""
        data = read_from(path, position)
        return position + len(data), data
    return fetch


def debug_fetch(debug_log: Callable[[int], tuple[int, bytes]]):
    """fetch for the debug ring: amigentd counts what went through RawPutChar."""
    def fetch(position: int) -> tuple[int, bytes]:
        total, data = debug_log(position)
        return total, data
    return fetch


def serial_fetch(read: Callable[[], bytes]):
    """fetch for a host serial port. read() returns whatever has arrived, or b''."""
    def fetch(position: int) -> tuple[int, bytes]:
        data = read() or b""
        return position + len(data), data
    return fetch


def serial_port_name(port: str) -> str:
    """COM3, the form Windows uses. The daemon does not open this port."""
    name = (port or "").strip().upper()
    if not re.fullmatch(r"COM\d+", name):
        raise AmigaError("name the serial port as COM3")
    return name


def open_serial(port: str) -> tuple[Callable[[], bytes], Callable[[], None]]:
    """The host COM port at 115200 8N1: a read of whatever is waiting, and a close.

    ApolloROM's serial debug and the ApolloCrossDev samples use this rate.
    The daemon does not also open the port; the ROM already owns the Amiga side.
    """
    if os.name != "nt":
        raise AmigaError("serial follow reads a Windows COM port such as COM3")
    name = serial_port_name(port)
    import ctypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                   ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                   ctypes.c_void_p]
    kernel.GetCommState.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.GetCommState.restype = ctypes.c_int
    kernel.SetCommState.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.SetCommState.restype = ctypes.c_int
    kernel.SetCommTimeouts.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    kernel.SetCommTimeouts.restype = ctypes.c_int
    kernel.ReadFile.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                                ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
    kernel.ReadFile.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW("\\\\.\\" + name, 0x80000000, 0, None, 3, 0x80, None)
    invalid = ctypes.c_void_p(-1).value
    if not handle or handle == invalid:
        raise AmigaError(f"could not open {name} ({ctypes.get_last_error()})")
    dcb = ctypes.create_string_buffer(64)
    if not kernel.GetCommState(handle, dcb):
        kernel.CloseHandle(handle)
        raise AmigaError(f"could not read the state of {name}")
    struct.pack_into("<I", dcb, 0, 64)
    struct.pack_into("<I", dcb, 4, 115200)
    flags = struct.unpack_from("<I", dcb, 8)[0] | 1
    flags &= ~2
    struct.pack_into("<I", dcb, 8, flags)
    dcb[18] = 8
    dcb[19] = 0
    dcb[20] = 0
    timeouts = ctypes.create_string_buffer(struct.pack("<5I", 0xFFFFFFFF, 0, 0, 0, 0))
    if not kernel.SetCommState(handle, dcb) or not kernel.SetCommTimeouts(handle, timeouts):
        kernel.CloseHandle(handle)
        raise AmigaError(f"could not set {name} to 115200 8N1")

    def read() -> bytes:
        chunk = ctypes.create_string_buffer(4096)
        got = ctypes.c_uint32()
        if not kernel.ReadFile(handle, chunk, 4096, ctypes.byref(got), None):
            return b""
        return chunk.raw[:got.value]

    def close() -> None:
        kernel.CloseHandle(handle)

    return read, close
