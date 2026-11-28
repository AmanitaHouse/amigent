"""Canonical upstream AUDIO is opcode 49 (EMU68 is 48); legacy fork AUDIO is 48/38.

PIP is retired and has no active opcode or command in this tree.
These tests check numbering, capability flags and the bytes on the wire.
They do not play audio and they do not run on Apollo hardware.
"""

import struct
from pathlib import Path

import pytest

from amigent.channel import (
    AUDIO, CPU, DRAG, EMU68, LEGACY_AUDIO_5, LEGACY_AUDIO_6, LOADED, LOCKS, NOTE, PEEK, POKE,
    QUIET, TASKCTL, TASKS, TRACE, AmigaChannel, AmigaError, apollo_commands, audio_request,
    feature_opcode,
)

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = (NOTE, LOADED, PEEK, TASKS, TASKCTL, POKE, TRACE, LOCKS, CPU, DRAG, QUIET)


def test_upstream_opcodes_37_through_49_stay_authoritative():
    assert UPSTREAM == tuple(range(37, 48))
    assert EMU68 == 48
    assert AUDIO == 49
    assert EMU68 != AUDIO
    assert LEGACY_AUDIO_6 == 48
    assert LEGACY_AUDIO_5 == 38


def test_protocol_6_audio_negotiates_canonical_49_and_legacy_48():
    assert feature_opcode(6, "AUDIO", {"audio": "49"}) == 49
    assert feature_opcode(6, "AUDIO", {"audio": "49", "emu68": "0"}) == 49
    assert feature_opcode(6, "AUDIO", {"audio": "1"}) == 48
    assert feature_opcode(6, "AUDIO", {"audio": "1", "emu68": "0"}) == 48
    assert feature_opcode(6, "AUDIO", {}) is None
    assert feature_opcode(6, "AUDIO", {"audio": "0"}) is None
    assert feature_opcode(6, "LOADED", {"loaded": "1", "audio": "49"}) == LOADED == 38
    assert feature_opcode(6, "LOADED", {"loaded": "1", "audio": "1"}) == LOADED == 38
    assert feature_opcode(6, "AUDIO", {"loaded": "1", "audio": "49"}) == 49
    assert feature_opcode(6, "AUDIO", {"loaded": "1", "audio": "1"}) == 48


def test_protocol_5_keeps_published_audio_loaded_tasks_and_retires_pip():
    advertised = {"audio": "1", "pip": "1", "modules": "1", "tasklist": "1"}
    assert feature_opcode(5, "AUDIO", advertised) == 38
    assert feature_opcode(5, "PIP", advertised) is None
    assert feature_opcode(5, "LOADED", advertised) == 40
    assert feature_opcode(5, "TASKS", advertised) == 41
    assert feature_opcode(5, "AUDIO", {}) is None
    assert feature_opcode(5, "AUDIO", {"audio": "49"}) is None
    assert feature_opcode(5, "PIP", {"pip": "0"}) is None
    assert feature_opcode(4, "AUDIO", advertised) is None


def test_pip_is_retired_and_never_exposed():
    assert feature_opcode(6, "PIP", {}) is None
    assert feature_opcode(6, "PIP", {"pip": "0", "audio": "1"}) is None
    assert feature_opcode(6, "PIP", {"pip": "1"}) is None
    assert feature_opcode(6, "PIP", {"pip": "49"}) is None
    assert feature_opcode(5, "PIP", {"pip": "1"}) is None
    assert "PIP" not in apollo_commands({"pip": "1"})
    assert "PIP" not in apollo_commands({"pip": "1", "audio": "49"})
    assert not hasattr(AmigaChannel, "pip")


def test_audio_headers_are_ten_bytes():
    assert audio_request() == struct.pack(">BBHHHH", 49, 0, 0, 0, 0, 0)
    assert audio_request(1, 200) == struct.pack(">BBHHHH", 49, 1, 0, 200, 0, 0)
    assert audio_request(1, 200, info={"audio": "1"}) == struct.pack(">BBHHHH", 48, 1, 0, 200, 0, 0)
    assert audio_request(2, 0, protocol=5) == struct.pack(">BBHHHH", 38, 2, 0, 0, 0, 0)
    with pytest.raises(AmigaError):
        audio_request(protocol=4)


@pytest.mark.parametrize("sysinfo,expected_opcode", [
    ({"audio": "49", "emu68": "0"}, 49),
    ({"audio": "1", "emu68": "0", "pip": "0"}, 48),
])
def test_one_shot_and_stream_use_negotiated_opcode_and_framing(sysinfo, expected_opcode):
    channel = AmigaChannel.__new__(AmigaChannel)
    channel.protocol = 6
    channel._sock = type("Sock", (), {"settimeout": lambda self, t: None})()
    channel.timeout = 30
    channel._audio_opcode = 0
    channel.sysinfo = lambda: dict(sysinfo)
    sent = []
    channel._request = lambda cmd, **kw: sent.append((cmd, kw))
    blobs = iter([struct.pack(">II", 48000, 4), b"\x01\x00\x02\x00"])
    channel._exact = lambda n: next(blobs)

    rate, pcm = channel.audio(200)
    assert sent == [(expected_opcode, {"y": 200})]
    assert rate == 48000 and pcm == b"\x01\x00\x02\x00"

    channel.audio_start()
    assert sent[-1] == (expected_opcode, {"arg": 1})
    channel._exact = lambda n: struct.pack(">II", 48000, 0xFFFFFFFF)
    assert channel.audio_read() is None
    headers = []
    channel._header = lambda cmd, arg=0, **kw: headers.append((cmd, arg))
    channel.audio_stop()
    assert headers == [(expected_opcode, 2)]


def test_a_classic_daemon_is_not_offered_audio():
    channel = AmigaChannel.__new__(AmigaChannel)
    channel.protocol = 6
    channel._sock = object()
    channel.sysinfo = lambda: {"cpu": "68020", "loaded": "1"}
    with pytest.raises(AmigaError, match="Apollo"):
        channel.audio()


def test_the_daemon_implements_legacy_audio_48_and_not_pip():
    daemon = (ROOT / "src/native/amiga/daemon" / "amigentd.c").read_text(encoding="utf-8")
    audio = (ROOT / "src/native/amiga/apollo" / "apollo_audio.c").read_text(encoding="utf-8")
    assert "case CMD_AUDIO:" in daemon
    assert "apollo_audio(" in audio and "arne.audio" in audio
    assert "apollo_pip" not in daemon and "apollo_pip" not in audio
    assert "c_pip" not in daemon
    assert "CMD_PIP" not in daemon and "CMD_PIP" not in audio
    assert "reserved for PIP" not in daemon
    assert 't_pair(&t, "audio", 1)' in daemon
    assert 't_pair(&t, "pip"' not in daemon
    makefile = (ROOT / "src/native/amiga" / "Makefile.apollo").read_text(encoding="utf-8")
    assert "apollo_audio.o" in makefile
    assert "apollo.o" not in makefile and "ammx" not in makefile
