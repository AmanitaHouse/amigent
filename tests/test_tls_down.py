"""A pinned Amiga whose TLS port is shut: the plain hello says why, and nothing is sent."""

import socket
import time

import pytest

from amigent import tls
from amigent.amigactl import AmigaError
from amigent.amigentd import Amigentd, AmigentdError
from amigent.channel import AmigaChannel
from amigent.viewer import connection_reason
from fakeamiga import FakeAmiga


def heard(amiga):
    """What the fake got on its one plain connection, once it has closed it."""
    deadline = time.monotonic() + 3
    while not amiga.received and time.monotonic() < deadline:
        time.sleep(0.01)
    return amiga.received


@pytest.fixture
def amiga(private_config):
    """A fake amigentd with a pinned certificate on the PC and nothing on its TLS port."""
    for _ in range(20):  # one whose next port is free, so a connect there is refused
        fake = FakeAmiga()
        probe = socket.socket()
        try:
            probe.bind(("127.0.0.1", fake.port + 1))
            break
        except OSError:
            fake.close()
        finally:
            probe.close()
    else:
        pytest.skip("no fake Amiga with a free port after its own")
    private_config.mkdir(parents=True, exist_ok=True)
    (private_config / "tls-127.0.0.1.pem").write_text("pinned")
    assert tls.wanted("127.0.0.1")
    yield fake
    fake.close()


def test_without_amissl_the_reason_comes_from_the_hello(amiga):
    amiga.hello_flags = 1 | 4
    with pytest.raises(AmigaError) as caught:
        AmigaChannel("127.0.0.1", amiga.port, timeout=5, key="secret").connect()
    assert tls.NO_TLS_TEXT in str(caught.value)
    assert connection_reason(str(caught.value)) == "reason_no_tls"
    assert heard(amiga) == [b""]  # no key, no command: nothing went out in plain


def test_a_certificate_that_does_not_load_has_its_own_reason(amiga):
    amiga.hello_flags = 1 | 2 | 4
    with pytest.raises(AmigentdError) as caught:
        Amigentd("127.0.0.1", amiga.port, timeout=5, key="secret").connect()
    assert tls.NO_CERT_TEXT in str(caught.value)
    assert connection_reason(str(caught.value)) == "reason_no_certificate"
    assert heard(amiga) == [b""]


def test_an_open_plain_port_changes_nothing(amiga):
    with pytest.raises(AmigaError, match="cannot reach") as caught:
        AmigaChannel("127.0.0.1", amiga.port, timeout=5, key="secret").connect()
    assert "AmiSSL" not in str(caught.value) and "amigent-tls.pem" not in str(caught.value)
    assert amiga.counts == {}  # the hello was read, no command followed


def test_no_plain_answer_either_stays_not_answering(amiga):
    amiga.close()
    with pytest.raises(AmigentdError, match="not answering") as caught:
        Amigentd("127.0.0.1", amiga.port, timeout=5, key="secret").connect()
    assert connection_reason(str(caught.value)) == "reason_refused"


def test_an_amiga_that_is_off_is_not_asked_twice(private_config, monkeypatch):
    private_config.mkdir(parents=True, exist_ok=True)
    (private_config / "tls-192.0.2.7.pem").write_text("pinned")
    dialled = []

    def silent(address, timeout=None, *args, **kwargs):
        dialled.append(address)
        raise TimeoutError("timed out")

    monkeypatch.setattr(tls.socket, "create_connection", silent)
    with pytest.raises(TimeoutError):
        tls.connect("192.0.2.7", 6801, 1)
    assert dialled == [("192.0.2.7", 6802)]
