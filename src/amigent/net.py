"""Two questions for the wire: who am I on this LAN, and does anybody answer over there."""

from __future__ import annotations

import socket

PORT = 6801  # amigentd; amigactld sits one below, TLS one above
# Our side of a gigabit LAN with a few milliseconds of delay. The Amiga still
# advertises only the window its own stack has, so a 68000 is unchanged.
PC_WINDOW = 1024 * 1024
RECV_AT_ONCE = 1024 * 1024
# One write_file on an Apollo: few round trips, and still inside the timeout a
# plipbox would be given for the same bytes (budget() at DISK_RATE).
APOLLO_SLICE = 1024 * 1024
APOLLO_BLOCK = 1024 * 1024
APOLLO_DOWNLOAD = 256 * 2**20


def widen(sock: socket.socket) -> None:
    """Ask for a large TCP window. A stack that refuses keeps its own default."""
    for opt in (socket.SO_SNDBUF, socket.SO_RCVBUF):
        try:
            sock.setsockopt(socket.SOL_SOCKET, opt, PC_WINDOW)
        except OSError:
            pass


def apollo_peer(info: dict | None) -> bool:
    """True when the far end is amigentd.apollo, the build for a V4 or an A6000.

    That binary reports cpu 68080. ApolloOS does too, including a board id this
    PC does not have a name for yet.
    """
    if not info:
        return False
    try:
        cpu = int(str(info.get("cpu", "0")).split(".", 1)[0])
    except ValueError:
        cpu = 0
    return cpu == 68080 or str(info.get("os", "")) == "ApolloOS"


def lan_address(peer: str = "", port: int = PORT, timeout: float = 5) -> str:
    """This PC's address: as peer sees it over TCP (NAT may disagree with the LAN), else the
    one the default route leaves from. Raises OSError when there is no answer to either."""
    if peer:
        with socket.create_connection((peer, port), timeout) as s:
            return s.getsockname()[0]
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("192.0.2.1", 9))  # not a single byte leaves; UDP connect just picks the interface
        return s.getsockname()[0]


def greet(host: str, port: int = PORT, timeout: float = 2.0,
          connect_timeout: float | None = None) -> bytes:
    """Knock and listen: the first bytes (up to 8) a daemon says on connect; b"" for silence."""
    try:
        with socket.create_connection((host, port), connect_timeout or timeout) as s:
            s.settimeout(timeout)
            return s.recv(8)
    except OSError:
        return b""
