"""The host speaks protocol 5 to an rc3 daemon and protocol 6 to upstream.

Mocked sockets only. Nothing here contacts a machine.
"""

import struct

import pytest

from amigent.channel import (AUDIO, LOADED, PACK_PROTOCOL, AmigaChannel, AmigaError, feature_opcode)
from amigent.viewer import pip_message

RC3 = {
    "audio": "1", "pip": "1", "modules": "1", "tasklist": "1",
}
P6 = {
    "audio": "1", "pip": "0", "loaded": "1", "poke": "0", "probe": "1",
}


def test_opcode_table_follows_the_greeting():
    assert feature_opcode(5, "AUDIO", RC3) == 38
    assert feature_opcode(5, "PIP", RC3) == 39
    assert feature_opcode(5, "LOADED", RC3) == 40
    assert feature_opcode(5, "TASKS", RC3) == 41
    for name in ("PEEK", "TASKCTL", "POKE", "TRACE"):
        assert feature_opcode(5, name, RC3) is None

    assert feature_opcode(6, "AUDIO", P6) == 48
    assert feature_opcode(6, "PIP", P6) is None  # pip=0: no usable picture
    assert feature_opcode(6, "PIP", {**P6, "pip": "1"}) == 49
    assert feature_opcode(6, "LOADED", P6) == 38
    assert feature_opcode(6, "TASKS", P6) == 40
    assert feature_opcode(6, "PEEK", P6) == 39
    assert feature_opcode(6, "TASKCTL", P6) == 41
    assert feature_opcode(6, "POKE", P6) == 42
    assert feature_opcode(6, "TRACE", P6) == 43

    # Protocol 6 must not treat the rc3 flags as the rc3 opcodes.
    both = {**RC3, **P6}
    assert feature_opcode(6, "AUDIO", both) == AUDIO == 48
    assert feature_opcode(6, "LOADED", both) == LOADED == 38
    assert feature_opcode(6, "AUDIO", both) != feature_opcode(6, "LOADED", both)
    assert feature_opcode(6, "PIP", {"pip": "0", "audio": "1"}) is None


def test_a_classic_protocol_5_daemon_is_not_sent_an_extension():
    assert feature_opcode(5, "AUDIO", {}) is None
    assert feature_opcode(5, "PIP", {"pip": "0"}) is None
    assert feature_opcode(5, "LOADED", {"loaded": "1"}) is None
    assert feature_opcode(5, "TASKS", {"tasklist": "0"}) is None
    assert feature_opcode(4, "AUDIO", RC3) is None


class _Sock:
    def settimeout(self, seconds):
        pass


def _channel(protocol: int, info: dict) -> tuple[AmigaChannel, list]:
    ch = AmigaChannel("127.0.0.1")
    ch._sock = _Sock()
    ch.protocol = protocol
    ch._info = dict(info)
    sent = []

    def request(cmd, path="", arg=0, y=0, w=0, h=0, payload=b"", timeout=None):
        sent.append(cmd)

    def header(cmd, arg=0, x=0, y=0, w=0, h=0):
        sent.append(cmd)

    def text(cmd, path=""):
        sent.append(cmd)
        return ["ok"]

    ch._request = request
    ch._header = header
    ch._text = text
    ch._exact = lambda n: struct.pack(">II", 48000, 0) if n == 8 else struct.pack(">HHHHI", 0, 0, 0, 0, 0)
    return ch, sent


def test_methods_send_the_opcode_for_the_protocol():
    legacy, sent = _channel(PACK_PROTOCOL, RC3)
    assert legacy.audio(100) == (48000, b"")
    legacy.audio_start()
    legacy.audio_stop()
    assert legacy.pip()[:4] == (0, 0, 0, 0)
    assert legacy.loaded() == ["ok"]
    assert legacy.tasks() == ["ok"]
    assert sent == [38, 38, 38, 39, 40, 41]
    before = len(sent)
    with pytest.raises(AmigaError, match="1.4.0"):
        legacy.peek(0x1000, 4)
    with pytest.raises(AmigaError, match="1.4.0"):
        legacy.poke(0x1000, b"\0")
    with pytest.raises(AmigaError, match="1.4.0"):
        legacy.task_control(0x1000, 1, 0)
    with pytest.raises(AmigaError, match="1.4.0"):
        legacy.trace(2)
    assert len(sent) == before  # 39 in the list is PIP, and no memory command was added

    current, sent = _channel(6, P6)
    assert current.audio(50) == (48000, b"")
    assert current.loaded() == ["ok"]
    assert current.tasks() == ["ok"]
    with pytest.raises(AmigaError, match="Apollo"):
        current.pip()
    assert sent == [48, 38, 40]
    assert 38 in sent and 48 in sent and sent.index(48) != sent.index(38)


def test_empty_pip_surface_is_not_a_picture():
    ch, _sent = _channel(6, {**P6, "pip": "1"})
    x, y, w, h, rgb = ch.pip()
    assert (x, y, w, h, rgb) == (0, 0, 0, 0, b"")
    assert pip_message(x, y, w, h, rgb) == struct.pack(">BHHHH", 4, 0, 0, 0, 0)
    assert feature_opcode(6, "PIP", P6) is None
