"""ApolloOS build choice, AUDIO/PIP framing, serial log merge, and HRTmon."""

import os
import socket
import struct
from pathlib import Path

import pytest

from amigent import net, pack
from amigent.channel import (AmigaChannel, apollo_commands, audio_request, parse_audio_body,
                             parse_pip_body, pcm_wav, pip_request)
from amigent.follow import Follower, debug_fetch, serial_fetch, serial_port_name
from amigent.hrtmon import plan
from amigent.setup import apollo_os, select_build
from amigent.viewer import pcm_message, pip_message
from amigent.errors import AmigaError
from fakeamiga import FakeAmiga


def test_apollo_peer_is_the_daemon_for_a_v4_or_a6000():
    assert net.apollo_peer({"cpu": "68080"})
    assert net.apollo_peer({"os": "ApolloOS", "cpu": "68020"})
    assert not net.apollo_peer({"cpu": "68030", "os": "AmigaOS"})
    assert not net.apollo_peer({})
    assert not net.apollo_peer(None)


def test_widen_asks_for_a_large_window():
    sock = socket.socket()
    try:
        net.widen(sock)
        # What the stack kept. Windows may report more than was asked.
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF) >= net.PC_WINDOW // 2
        assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF) >= net.PC_WINDOW // 2
    finally:
        sock.close()


def test_an_apollo_channel_sends_in_large_slices(tmp_path):
    fake = FakeAmiga()
    fake.protocol = 5
    fake.cpu = "68080"
    try:
        ch = AmigaChannel("127.0.0.1", fake.port, timeout=5, key="")
        ch.policy = pack.Policy("apollo-slice", "10.1.1.1", path=tmp_path / "slice.json")
        ch.connect()
        assert ch.policy.apollo and ch._slice == net.APOLLO_SLICE
        ch.close()
    finally:
        fake.close()


def test_build_choice():
    assert select_build(5) == "amigentd.000"
    assert select_build(0) == "amigentd"
    assert select_build(0, {"os": "ApolloOS"}) == "amigentd.apollo"
    assert select_build(0, {"exec_version": "47.96", "attn_flags": "1024"}) == "amigentd"
    assert select_build(0, {"exec_version": "51.3", "attn_flags": str(1 << 10)}) == "amigentd.apollo"
    assert select_build(0, {"exec_version": "51.3", "attn_flags": "0"}) == "amigentd"
    assert select_build(0, {}, "exec.library 51.3\nApolloOS\n") == "amigentd.apollo"
    assert not apollo_os({"os": "AmigaOS"})


def test_an_empty_pip_surface_is_not_a_supported_command():
    root = Path(__file__).resolve().parents[1]
    daemon = (root / "src/native/amiga/daemon/amigentd.c").read_text(encoding="latin-1")
    apollo = (root / "src/native/amiga/platform/apollo/apollo.c").read_text(encoding="latin-1")
    assert 't_pair(&t, "audio", 1);' in daemon
    assert 't_pair(&t, "pip", 0);' in daemon
    assert 't_pair(&t, "pip", 1);' not in daemon
    reader = apollo.split("LONG apollo_pip(", 1)[1].split("static ULONG peek", 1)[0]
    assert "*x = *y = *w = *h = 0;" in reader and "return 0;" in reader
    assert "DFF3" not in reader  # the write-only PIP registers stay unread
    assert apollo_commands({"audio": "1", "pip": "0"}) == frozenset({"AUDIO"})
    assert apollo_commands({"audio": "1", "pip": "1"}) == frozenset({"AUDIO", "PIP"})
    assert apollo_commands({"audio": "0", "pip": "0"}) == frozenset()
    assert apollo_commands(None) == frozenset()


def test_audio_and_pip_framing():
    assert audio_request() == bytes([38, 0, 0, 0, 0, 0, 0, 0, 0, 0])
    assert struct.pack(">BBHHHH", 38, 1, 0, 0, 0, 0) == bytes([38, 1, 0, 0, 0, 0, 0, 0, 0, 0])
    assert struct.pack(">BBHHHH", 38, 2, 0, 0, 0, 0)[1] == 2
    rate, size = struct.unpack(">II", (47931).to_bytes(4, "big") + (0xFFFFFFFF).to_bytes(4, "big"))
    assert rate == 47931 and size == 0xFFFFFFFF
    assert pip_request()[0] == 39 and len(pip_request()) == 10
    rate, pcm = parse_audio_body((48000).to_bytes(4, "big") + (4).to_bytes(4, "big") + b"\x01\x00\x02\x00")
    assert rate == 48000 and pcm == b"\x01\x00\x02\x00"
    x, y, w, h, rgb = parse_pip_body(
        b"\x00\x0a\x00\x14\x00\x02\x00\x01\x00\x00\x00\x06" + b"\x01\x02\x03\x04\x05\x06")
    assert (x, y, w, h, rgb) == (10, 20, 2, 1, b"\x01\x02\x03\x04\x05\x06")
    assert pcm_message(48000, pcm) == b"\x05" + (48000).to_bytes(4, "big") + pcm
    wav = pcm_wav(pcm, 48000)
    assert wav.startswith(b"RIFF") and wav.endswith(pcm)
    assert int.from_bytes(wav[24:28], "little") == 48000
    assert int.from_bytes(wav[22:24], "little") == 2
    assert pip_message(10, 20, 2, 1, rgb) == b"\x04" + b"\x00\x0a\x00\x14\x00\x02\x00\x01" + rgb


def test_serial_bytes_join_the_debug_log(tmp_path):
    target = tmp_path / "debug.log"
    ring = {"n": 0, "data": b""}

    def debug_log(since):
        if since > ring["n"]:
            return ring["n"], b""
        return ring["n"], ring["data"][since:ring["n"]]

    pending = {"b": b"ROM: hello\n"}

    def read():
        got = pending["b"]
        pending["b"] = b""
        return got

    debug = Follower("debug", target, debug_fetch(debug_log), start=0)
    serial = Follower("serial", target, serial_fetch(read), start=0)
    serial.tick()
    ring["data"] = b"kprintf\n"
    ring["n"] = len(ring["data"])
    pending["b"] = b"more\n"
    debug.tick()
    serial.tick()
    raw = target.read_bytes()
    assert b"ROM: hello\n" in raw and b"kprintf\n" in raw and b"more\n" in raw
    assert serial.position == len(b"ROM: hello\nmore\n")


def test_a_serial_port_is_named_as_com():
    assert serial_port_name(" com3 ") == "COM3"
    with pytest.raises(AmigaError):
        serial_port_name("ttyS0")
    with pytest.raises(AmigaError):
        serial_port_name("")


@pytest.mark.skipif(os.name != "nt", reason="the serial follow opens a Windows COM port")
def test_a_missing_com_port_fails_at_once():
    from amigent.follow import open_serial
    with pytest.raises(AmigaError):
        open_serial("COM99")


def test_hrtmon_stays_on_the_os_program():
    text, start = plan("AmigaOS", "", "", True)
    assert not start and "ROM monitor stays unused" in text
    text, start = plan("ApolloOS", "", "Workbench|hrtmon", True)
    assert not start and "already running" in text and "keyboard" in text
    text, start = plan("ApolloOS", "", "Workbench", False)
    assert not start and "command path" in text
    text, start = plan("", "ApolloOS", "Workbench", True)
    assert start and "started" in text
    assert "HRT!" not in text
