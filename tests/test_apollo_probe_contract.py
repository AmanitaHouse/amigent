"""Apollo setup-probe contract: OS text plus AFF_FPGA core evidence."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = (ROOT / "amiga" / "apollo" / "apollo_probe.c").read_text(encoding="utf-8")
BINARY = ROOT / "src" / "amigent" / "amiga" / "bin" / "amigent-apollo-probe"


def test_probe_source_requires_apolloos_and_aff_fpga_for_exit_zero():
    assert "AFF_FPGA" in PROBE
    assert "apollo_os_here" in PROBE
    assert "RETURN_OK" in PROBE and "RETURN_WARN" in PROBE
    assert 'PutStr("ApolloOS\\n")' in PROBE or 'PutStr("ApolloOS\n")' in PROBE
    assert 'PutStr("AmigaOS\\n")' in PROBE or 'PutStr("AmigaOS\n")' in PROBE
    assert 'PutStr("68080\\n")' in PROBE or 'PutStr("68080\n")' in PROBE
    # Exit 0 only when ApolloOS and the FPGA core bit are both present.
    assert "AttnFlags & AFF_FPGA" in PROBE
    assert "m68080" not in PROBE


def test_packaged_probe_bytes_match_the_core_evidence_build():
    data = BINARY.read_bytes()
    assert len(data) == 3224
    assert hashlib.sha256(data).hexdigest() == (
        "96ca1b389980b5a94ce0fc94c67c8eeafa7dd2455df497f52532e15409ba0265"
    )
    assert data.startswith(b"\x00\x00\x03\xf3")
    assert b"ApolloOS" in data and b"AmigaOS" in data and b"68080" in data
