"""Offline checks that D2 matrix/docs stay narrowly claimed after reconciliation."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_matrix_qualifies_live_mmio_as_bounded_d2():
    m = json.loads((ROOT / "tests/hardware/apollo_v4_matrix.json").read_text(encoding="utf-8"))
    hc = m["hardware_coverage"]
    assert "BOUNDED_D2_ONLY" in hc["live_MMIO"]
    assert "PASSED_ON_HARDWARE" in hc["d2_protected_window_peek_refuse"]
    assert "OUTSIDE" in hc["d2_system_rom_control_reads"] or "outside" in hc["d2_system_rom_control_reads"].lower()
    assert hc["d2_other_mmio_windows"] == "NOT_TESTED_ON_HARDWARE"
    assert hc["POKE_ALLOWPOKE"] == "NOT_TESTED"
    assert hc["TRACE_68080"] == "NOT_TESTED"
    assert "NOT" in hc["apollo_monitor"]
    assert "NOT" in hc["HRTmon"]


def test_reconciliation_doc_records_discrepancy():
    text = (ROOT / "docs/APOLLO_V4_STAGE4_D2_EVIDENCE_RECONCILIATION.md").read_text(encoding="utf-8")
    assert "test-owned allocated RAM" in text
    assert "$F80000" in text and "$00000004" in text
    assert "governance error" in text.lower() or "incorrectly" in text.lower()
    assert "ExecBase" in text
    assert "NOT TESTED ON HARDWARE" in text or "NOT_TESTED" in text


def test_stage4_go_gate_forbids_rom_substitution_without_auth():
    text = (ROOT / "docs/APOLLO_V4_STAGE4_SAFETY_ASSESSMENT.md").read_text(encoding="utf-8")
    assert "mandatory NO-GO" in text or "mandatory **NO-GO**" in text
    assert "test-owned allocated RAM" in text
    assert "ExecBase-at-4" in text or "ExecBase" in text
