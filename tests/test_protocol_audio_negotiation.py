"""Table-driven protocol AUDIO/EMU68/PIP capability negotiation and collision tests.

Verifies canonical upstream opcode 49 (AUDIO) and 48 (EMU68), transitional legacy
Apollo compatibility (protocol 6 opcode 48, protocol 5 opcode 38), retirement of
dead PIP mappings, and fail-closed wire behaviour on contradictory or malformed
SYSINFO advertisements. Offline only; nothing contacts hardware.
"""
from __future__ import annotations

import json
import shutil
import struct
import subprocess

import pytest

import amigent.server as server
from amigent.channel import (
    AUDIO, EMU68, LEGACY_AUDIO_5, LEGACY_AUDIO_6, LOADED, READ_ONLY_COMMANDS_5, TASKS,
    AmigaChannel, AmigaError, Commands, apollo_commands, audio_capability_error, audio_request,
    emu68_capability_error, feature_opcode, read_only_allows,
)
from amigent.daemons import describe_connected
from amigent.paths import AMIGA
from amigent.viewer import hear_eligible
from amigent.webserver import WEB


def _mock_channel(protocol, info: dict) -> tuple[AmigaChannel, list[tuple[int, dict]], list[tuple[int, int]]]:
    """Offline AmigaChannel that records every wire request/header sent."""
    ch = AmigaChannel.__new__(AmigaChannel)
    ch.protocol = protocol
    ch._sock = type("Sock", (), {"settimeout": lambda self, t: None})()
    ch.timeout = 30
    ch._audio_opcode = 0
    ch.read_only = False
    ch.sysinfo = lambda: dict(info)
    sent_requests: list[tuple[int, dict]] = []
    sent_headers: list[tuple[int, int]] = []
    ch._request = lambda cmd, **kw: sent_requests.append((cmd, kw))
    ch._header = lambda cmd, arg=0, **kw: sent_headers.append((cmd, arg))
    ch._one = lambda req: sent_requests.append((req.cmd, {"arg": req.arg})) or ["emu68=1"]
    return ch, sent_requests, sent_headers


# Full capability matrix from the protocol-alignment specification.
MATRIX = [
    # (id, protocol, info, expected_audio, expected_emu68, expected_pip, expected_hear_apollo)
    ("p6_canonical_49", 6, {"audio": "49", "emu68": "0"}, 49, 48, None, True),
    ("p6_legacy_1", 6, {"audio": "1", "emu68": "0"}, 48, None, None, True),
    ("p5_legacy_1", 5, {"audio": "1", "modules": "1", "tasklist": "1"}, 38, None, None, False),
    ("p6_conflict_audio49_pip1", 6, {"audio": "49", "pip": "1"}, None, None, None, False),
    ("p6_conflict_audio1_emu68_1", 6, {"audio": "1", "emu68": "1"}, None, None, None, False),
    ("p6_conflict_audio49_emu68_1", 6, {"audio": "49", "emu68": "1"}, None, None, None, False),
    ("p6_emu68_only", 6, {"emu68": "1"}, None, 48, None, False),
    ("p6_emu68_zero_no_audio", 6, {"emu68": "0"}, None, 48, None, False),
    ("p6_malformed_audio_yes", 6, {"audio": "yes"}, None, None, None, False),
    ("p6_malformed_audio_48", 6, {"audio": "48"}, None, None, None, False),
    ("p6_malformed_audio_2", 6, {"audio": "2"}, None, None, None, False),
    ("p6_pip_only_1", 6, {"pip": "1"}, None, None, None, False),
    ("p6_pip_only_49", 6, {"pip": "49"}, None, None, None, False),
    ("p5_pip_only_1", 5, {"pip": "1"}, None, None, None, False),
    ("p5_audio_49_refused", 5, {"audio": "49"}, None, None, None, False),
    ("p7_canonical_49", 7, {"audio": "49", "emu68": "0"}, 49, 48, None, True),
    ("p7_legacy_1_refused", 7, {"audio": "1", "emu68": "0"}, None, None, None, False),
    ("malformed_proto_none", None, {"audio": "49"}, None, None, None, False),
    ("malformed_proto_bool", True, {"audio": "49"}, None, None, None, False),
    ("malformed_proto_str", "six", {"audio": "49"}, None, None, None, False),
]


@pytest.mark.parametrize("case_id,proto,info,exp_audio,exp_emu68,exp_pip,exp_hear", MATRIX,
                         ids=[row[0] for row in MATRIX])
def test_capability_matrix(case_id, proto, info, exp_audio, exp_emu68, exp_pip, exp_hear):
    assert feature_opcode(proto, "AUDIO", info) == exp_audio
    assert feature_opcode(proto, "EMU68", info) == exp_emu68
    assert feature_opcode(proto, "PIP", info) is exp_pip is None

    cmds = apollo_commands(info, protocol=proto) if isinstance(proto, int) and not isinstance(proto, bool) else frozenset()
    assert "PIP" not in cmds
    if isinstance(proto, int) and not isinstance(proto, bool):
        assert ("AUDIO" in cmds) == (exp_audio is not None)

    apollo_info = {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": proto, **info}
    assert hear_eligible(apollo_info, connected=True) is exp_hear


@pytest.mark.parametrize("proto,info,expected_opcode", [
    (6, {"audio": "49", "emu68": "0"}, 49),
    (6, {"audio": "1", "emu68": "0"}, 48),
    (5, {"audio": "1", "modules": "1", "tasklist": "1"}, 38),
])
def test_wire_audio_dispatch_uses_negotiated_opcode(proto, info, expected_opcode):
    ch, sent, headers = _mock_channel(proto, info)
    blobs = iter([struct.pack(">II", 48000, 4), b"\x01\x00\x02\x00"])
    ch._exact = lambda n: next(blobs)

    rate, pcm = ch.audio(100)
    assert rate == 48000 and pcm == b"\x01\x00\x02\x00"
    assert sent == [(expected_opcode, {"y": 100})]

    ch.audio_start()
    assert sent[-1] == (expected_opcode, {"arg": 1})

    ch._exact = lambda n: struct.pack(">II", 48000, 0xFFFFFFFF)
    assert ch.audio_read() is None

    ch.audio_stop()
    assert headers == [(expected_opcode, 2)]


@pytest.mark.parametrize("proto,info,match", [
    (6, {"audio": "49", "pip": "1"}, "contradictory"),
    (6, {"audio": "1", "emu68": "1"}, "ambiguous opcode 48"),
    (6, {"audio": "49", "emu68": "1"}, "contradictory"),
    (6, {"audio": "yes"}, "malformed"),
    (6, {"audio": "48"}, "malformed"),
    (6, {"audio": "2"}, "malformed"),
    (6, {"pip": "1"}, "Apollo"),
    (6, {"pip": "49"}, "Apollo"),
    (5, {"audio": "49"}, "protocol 5"),
    (5, {"pip": "1"}, "protocol 5"),
    (7, {"audio": "1"}, "protocol 6"),
])
def test_wire_audio_refuses_contradictory_and_malformed_with_zero_dispatch(proto, info, match):
    ch, sent, headers = _mock_channel(proto, info)
    with pytest.raises(AmigaError, match=match):
        ch.audio(50)
    with pytest.raises(AmigaError, match=match):
        ch.audio_start()
    assert sent == [] and headers == []


@pytest.mark.parametrize("info,match", [
    ({"audio": "1", "emu68": "0"}, "legacy AUDIO"),
    ({"audio": "1", "emu68": "1"}, "ambiguous opcode 48"),
    ({"audio": "49", "emu68": "1"}, "contradictory"),
    ({"audio": "48", "emu68": "1"}, "malformed"),
    ({"audio": "yes", "emu68": "1"}, "malformed"),
])
def test_wire_emu68_refuses_legacy_audio_and_contradictions_with_zero_dispatch(info, match):
    ch, sent, headers = _mock_channel(6, info)
    with pytest.raises(AmigaError, match=match):
        ch.emu68_info()
    with pytest.raises(AmigaError, match=match):
        ch.emu68_set([(0x1E0, 1, 1)])
    assert sent == [] and headers == []


def test_wire_emu68_dispatches_48_when_uncontested():
    ch, sent, _ = _mock_channel(6, {"emu68": "1"})
    ch.emu68_info()
    assert sent == [(48, {"arg": 0})]

    # Canonical upstream Apollo AUDIO-49 with emu68=0 keeps opcode 48 as EMU68.
    ch2, sent2, _ = _mock_channel(6, {"audio": "49", "emu68": "0"})
    ch2.emu68_info()
    assert sent2 == [(48, {"arg": 0})]


def test_protocol_5_loaded_tasks_and_readonly_guards_preserved():
    info = {"audio": "1", "modules": "1", "tasklist": "1", "pip": "1"}
    assert feature_opcode(5, "LOADED", info) == 40
    assert feature_opcode(5, "TASKS", info) == 41
    assert feature_opcode(5, "AUDIO", info) == 38
    assert feature_opcode(5, "PIP", info) is None
    assert READ_ONLY_COMMANDS_5 == frozenset({40, 41})
    assert read_only_allows(5, 40) and read_only_allows(5, 41)
    assert not read_only_allows(5, 38)
    assert not read_only_allows(5, 39)
    assert not read_only_allows(5, 48)
    assert not read_only_allows(5, 49)
    assert read_only_allows(6, LOADED) and read_only_allows(6, TASKS)
    assert not read_only_allows(6, EMU68) and not read_only_allows(6, AUDIO)


def test_audio_request_canonical_and_legacy_and_refusals():
    assert audio_request() == struct.pack(">BBHHHH", 49, 0, 0, 0, 0, 0)
    assert audio_request(1, 200, info={"audio": "49"}) == struct.pack(">BBHHHH", 49, 1, 0, 200, 0, 0)
    assert audio_request(1, 200, info={"audio": "1"}) == struct.pack(">BBHHHH", 48, 1, 0, 200, 0, 0)
    assert audio_request(2, 0, protocol=5, info={"audio": "1"}) == struct.pack(">BBHHHH", 38, 2, 0, 0, 0, 0)
    for bad in ({"audio": "49", "pip": "1"}, {"audio": "1", "emu68": "1"},
                {"audio": "49", "emu68": "1"}, {"audio": "yes"}, {"audio": "48"}):
        with pytest.raises(AmigaError):
            audio_request(info=bad)


def test_amiga_listen_negotiation_and_apollo_eligibility(monkeypatch):
    monkeypatch.setattr(server, "_with_ctl", lambda fn: fn())
    pcm = b"\x01\x00\x02\x00" * 9600

    for proto, info, expected_op in (
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "49", "emu68": "0"}, 49),
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "1", "emu68": "0"}, 48),
        (5, {"os": "ApolloOS", "cpu": "68080", "audio": "1"}, 38),
    ):
        ch, sent, _ = _mock_channel(proto, info)
        ch._exact = lambda n, _pcm=pcm: (struct.pack(">II", 48000, len(_pcm)) if n == 8 else _pcm)
        cmd = Commands("192.0.2.1")
        cmd.backend = ch
        monkeypatch.setattr(server._session(), "ctl", cmd)
        text, block = server.amiga_listen(0.2)
        assert text == f"heard {len(pcm)} bytes at 48000 Hz"
        assert block.data.startswith(b"RIFF")
        assert sent and all(op == expected_op for op, _ in sent)

    # Non-Apollo -m68020 build advertising audio=49 and contradictory/malformed sets must not dispatch.
    for proto, info in (
        (6, {"os": "AmigaOS", "cpu": "68020", "audio": "49", "emu68": "0"}),
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "49", "pip": "1"}),
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "1", "emu68": "1"}),
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "49", "emu68": "1"}),
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "yes"}),
        (6, {"os": "ApolloOS", "cpu": "68080", "audio": "48"}),
    ):
        ch, sent, headers = _mock_channel(proto, info)
        cmd = Commands("192.0.2.1")
        cmd.backend = ch
        monkeypatch.setattr(server._session(), "ctl", cmd)
        reply = server.amiga_listen(0.2)
        assert len(reply) == 1 and isinstance(reply[0], str)
        assert sent == [] and headers == []


def test_describe_connected_reflects_negotiated_audio_and_rejects_conflicts():
    bin_dir = AMIGA / "bin"
    c49 = describe_connected(6, "1.6.0", None, {"audio": "49", "loaded": "1"}, bin_dir)
    assert "AUDIO" in c49["daemon_capabilities"]
    c48 = describe_connected(6, "1.5.0", None, {"audio": "1", "loaded": "1"}, bin_dir)
    assert "AUDIO" in c48["daemon_capabilities"]
    conflict = describe_connected(6, "1.6.0", None, {"audio": "49", "pip": "1"}, bin_dir)
    assert "AUDIO" not in conflict["daemon_capabilities"]
    ambig = describe_connected(6, "1.5.0", None, {"audio": "1", "emu68": "1"}, bin_dir)
    assert "AUDIO" not in ambig["daemon_capabilities"]


def test_viewer_js_hear_eligibility_matches_python_across_matrix():
    """Execute viewer.js infoHearEligible in Node (when available) for exact JS/Python parity."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not available for JS execution parity check")
    js = (WEB / "viewer.js").read_text(encoding="utf-8")
    start = js.index("function apolloMachine(info)")
    end = js.index("function hearEligible(info)")
    snippet = js[start:end]

    cases = [
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "49", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "1", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 5, "audio": "1", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "49", "emu68": "0", "pip": "1"},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "1", "emu68": "1", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "49", "emu68": "1", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "yes", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "48", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 6, "audio": "", "emu68": "0", "pip": "1"},
        {"os": "AmigaOS", "cpu": "68020", "daemon_protocol": 6, "audio": "49", "emu68": "0", "pip": ""},
        {"os": "AmigaOS", "cpu": "68080", "daemon_protocol": 6, "audio": "49", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 7, "audio": "49", "emu68": "0", "pip": ""},
        {"os": "ApolloOS", "cpu": "68080", "daemon_protocol": 7, "audio": "1", "emu68": "0", "pip": ""},
    ]
    script = (
        f"{snippet}\n"
        f"const cases = {json.dumps(cases)};\n"
        "console.log(JSON.stringify(cases.map(c => infoHearEligible(c))));\n"
    )
    proc = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True)
    js_results = json.loads(proc.stdout)
    py_results = [hear_eligible(c, connected=True) for c in cases]
    assert js_results == py_results


def test_capability_error_helpers_are_consistent():
    assert audio_capability_error(6, {"audio": "49", "emu68": "0"}) == ""
    assert audio_capability_error(6, {"audio": "1", "emu68": "0"}) == ""
    assert audio_capability_error(5, {"audio": "1"}) == ""
    assert "contradictory" in audio_capability_error(6, {"audio": "49", "pip": "1"})
    assert "ambiguous" in audio_capability_error(6, {"audio": "1", "emu68": "1"})
    assert "contradictory" in audio_capability_error(6, {"audio": "49", "emu68": "1"})
    assert emu68_capability_error(6, {"emu68": "1"}) == ""
    assert emu68_capability_error(6, {"emu68": "0", "audio": "49"}) == ""
    assert "legacy AUDIO" in emu68_capability_error(6, {"emu68": "0", "audio": "1"})
    assert "ambiguous" in emu68_capability_error(6, {"emu68": "1", "audio": "1"})
    assert "contradictory" in emu68_capability_error(6, {"emu68": "1", "audio": "49"})
    assert not hasattr(AmigaChannel, "pip")
    assert AUDIO == 49 and EMU68 == 48 and LEGACY_AUDIO_6 == 48 and LEGACY_AUDIO_5 == 38
