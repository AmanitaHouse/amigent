"""An emulated Amiga seen from outside: WinUAE's GDB server (WinUAE 6.1 and later).

For an Amiga that runs in WinUAE on this PC, amigas.json can name the GDB port
("gdb": "127.0.0.1:2345"); WinUAE starts its server with
`-s debugging_features=gdbserver -s gdb_port=2345 -s cpu_threaded=false`.
Then Amigent can pause the emulated CPU, read its registers and memory without
asking the Amiga, and save or restore the whole machine as a state file: before
an installation that is an undo of everything, disk changes aside.

Only the GDB Remote Serial Protocol's basics are used: ?, g, m, c, Ctrl-C and
qRcmd for WinUAE's monitor commands (checkpoint, capabilities, execution-status).
"""

from __future__ import annotations

import socket

REGS = [f"d{i}" for i in range(8)] + [f"a{i}" for i in range(8)] + ["sr", "pc"]


class GdbError(Exception):
    pass


def checksum(data: bytes) -> bytes:
    return b"%02x" % (sum(data) & 0xFF)


def frame(data: str | bytes) -> bytes:
    raw = data.encode("latin-1") if isinstance(data, str) else data
    return b"$" + raw + b"#" + checksum(raw)


def unescape(data: bytes) -> bytes:
    """Binary escapes (}) and run lengths (*) of RSP replies."""
    out = bytearray()
    i = 0
    while i < len(data):
        c = data[i]
        if c == 0x7D and i + 1 < len(data):
            out.append(data[i + 1] ^ 0x20)
            i += 2
        elif c == 0x2A and out and i + 1 < len(data):
            out += bytes([out[-1]]) * (data[i + 1] - 29)
            i += 2
        else:
            out.append(c)
            i += 1
    return bytes(out)


def parse_address(text: str) -> tuple[str, int]:
    host, _, port = text.rpartition(":")
    if not host or not port.isdigit():
        raise GdbError(f"gdb wants host:port, got {text!r}")
    return host, int(port)


class Gdb:
    def __init__(self, address: str, timeout: float = 10.0):
        self.host, self.port = parse_address(address)
        self.timeout = timeout
        self.sock: socket.socket | None = None
        self.buf = b""
        self.running = True  # WinUAE runs until someone stops it

    def connect(self) -> None:
        if self.sock:
            return
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as e:
            raise GdbError(f"no GDB server at {self.host}:{self.port} ({e}); WinUAE 6.1 starts it with "
                           "-s debugging_features=gdbserver -s gdb_port=PORT -s cpu_threaded=false") from None
        self.sock.settimeout(self.timeout)

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def _byte(self) -> int:
        while not self.buf:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise GdbError("the GDB server closed the connection")
            self.buf += chunk
        b, self.buf = self.buf[0], self.buf[1:]
        return b

    def _packet(self) -> bytes:
        while True:
            c = self._byte()
            if c == ord("$"):
                break
        data = bytearray()
        while True:
            c = self._byte()
            if c == ord("#"):
                break
            data.append(c)
        given = bytes([self._byte(), self._byte()])
        if given.lower() != checksum(bytes(data)):
            self.sock.sendall(b"-")
            return self._packet()
        self.sock.sendall(b"+")
        return unescape(bytes(data))

    def _send(self, data: str) -> None:
        self.connect()
        for _ in range(3):
            self.sock.sendall(frame(data))
            c = self._byte()
            if c == ord("+"):
                return
        raise GdbError("the GDB server did not take the packet")

    def command(self, data: str) -> str:
        self._send(data)
        return self._packet().decode("latin-1")

    def pause(self) -> str:
        """Stop the emulated CPU; the stop reply (S05, T05...)."""
        self.connect()
        if not self.running:
            return "stopped already"
        self.sock.sendall(b"\x03")
        reply = self._packet().decode("latin-1")
        self.running = False
        return reply

    def resume(self) -> None:
        self._send("c")  # no answer until the next stop
        self.running = True

    def why(self) -> str:
        return self.command("?")

    def registers(self) -> dict[str, int]:
        was = self.running
        if was:
            self.pause()
        try:
            hexes = self.command("g")
        finally:
            if was:
                self.resume()
        if hexes.startswith("E"):
            raise GdbError(f"registers: {hexes}")
        return {name: int(hexes[i * 8:i * 8 + 8], 16) for i, name in enumerate(REGS)
                if len(hexes) >= i * 8 + 8}

    def read(self, address: int, size: int) -> bytes:
        was = self.running
        if was:
            self.pause()
        out = bytearray()
        try:
            while len(out) < size:
                n = min(size - len(out), 2048)
                reply = self.command(f"m{address + len(out):x},{n:x}")
                if reply.startswith("E") or not reply:
                    raise GdbError(f"memory at ${address + len(out):08X}: {reply or 'no answer'}")
                out += bytes.fromhex(reply)
        finally:
            if was:
                self.resume()
        return bytes(out)

    def monitor(self, text: str) -> str:
        """A WinUAE monitor command (qRcmd); console output packets come first."""
        self._send("qRcmd," + text.encode().hex())
        said = []
        while True:
            reply = self._packet().decode("latin-1")
            if reply.startswith("O") and reply != "OK":
                said.append(bytes.fromhex(reply[1:]).decode("utf-8", "replace"))
                continue
            break
        if reply.startswith("E"):
            raise GdbError(f"monitor {text.split()[0]}: {reply}")
        if reply == "" and not said:
            raise GdbError(f"this WinUAE does not know the monitor command {text.split()[0]!r}")
        if reply not in ("OK", ""):
            try:
                said.append(bytes.fromhex(reply).decode("utf-8", "replace"))
            except ValueError:
                said.append(reply)
        return "".join(said) or "OK"

    def checkpoint(self, action: str, path: str) -> str:
        """Save or restore the whole emulated Amiga as a WinUAE state file (host path)."""
        if action not in ("save", "restore"):
            raise GdbError("checkpoint: save or restore")
        was = self.running
        if was:
            self.pause()
        try:
            return self.monitor(f"checkpoint {action} {path}")
        finally:
            if was:
                self.resume()


def describe_registers(regs: dict[str, int], namer=None) -> str:
    lines = []
    for row in (REGS[:8], REGS[8:16]):
        lines.append("  ".join(f"{r.upper()}={regs[r]:08X}" for r in row if r in regs))
    if "pc" in regs:
        pc = f"PC={regs['pc']:08X}"
        if namer:
            where = namer.name(regs["pc"])
            if where:
                pc += f" ({where})"
        lines.append(f"{pc}  SR={regs.get('sr', 0):04X}")
    return "\n".join(lines)
