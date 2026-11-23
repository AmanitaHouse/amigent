"""What the PC says when amigentd turns a plain connection away (hello flag 4)."""

import socket
import struct
import threading

import pytest

from amigent import tls
from amigent.amigactl import AmigaError
from amigent.amigentd import Amigentd, AmigentdError
from amigent.channel import AmigaChannel


def refusing(flags):
    """A TLSONLY amigentd: the hello with these flags, then the line is closed."""
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)

    def run():
        while True:
            try:
                conn, _ = listener.accept()
            except OSError:
                return
            conn.sendall(b"AMGT" + struct.pack(">HH", 6, flags))
            conn.close()

    threading.Thread(target=run, daemon=True).start()
    return listener


@pytest.fixture
def plain(monkeypatch):
    monkeypatch.setenv("AMIGENT_TLS", "off")


def test_plain_closed_with_amissl_asks_for_the_certificate(plain):
    listener = refusing(1 | 2 | 4)
    try:
        with pytest.raises(AmigaError, match="Copy its certificate"):
            AmigaChannel("127.0.0.1", listener.getsockname()[1], timeout=5, key="k").connect()
    finally:
        listener.close()


def test_plain_closed_without_amissl_says_repair_at_the_amiga(plain):
    listener = refusing(1 | 4)
    try:
        with pytest.raises(AmigaError, match="AmiSSL does not open") as caught:
            AmigaChannel("127.0.0.1", listener.getsockname()[1], timeout=5, key="k").connect()
        assert "amigentd SETUP" in str(caught.value)
    finally:
        listener.close()


def test_screen_connection_says_the_same(plain):
    listener = refusing(1 | 4)
    try:
        with pytest.raises(AmigentdError, match="AmiSSL does not open"):
            Amigentd("127.0.0.1", listener.getsockname()[1], key="k").connect()
    finally:
        listener.close()


def test_flags_without_the_lock_or_over_tls_say_nothing():
    assert tls.plain_closed(1 | 2, encrypted=False) == ""
    assert tls.plain_closed(1 | 4, encrypted=True) == ""
    assert tls.plain_closed(1 | 2 | 4, encrypted=True) == ""
    assert tls.plain_closed(4, encrypted=False) == tls.NO_TLS_TEXT
    assert tls.plain_closed(2 | 4, encrypted=False) == tls.PLAIN_CLOSED_TEXT
