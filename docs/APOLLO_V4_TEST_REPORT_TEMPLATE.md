# Apollo V4 hardware test report (template)

Fill one report per test session. Mark every hardware row **NOT RUN** until executed.

**Audit / plan commit:** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Plan document:** `docs/APOLLO_V4_HARDWARE_TEST_PLAN.md`  
**Coverage document:** `docs/UPSTREAM_CONTRIBUTION_COVERAGE.md`

---

## Session metadata

| Field | Value |
|-------|-------|
| Test date (UTC) | |
| Operator | |
| Authorisation reference | _(inventory / stage2-port / L3–L4)_ |
| Session stage | 1 inventory / 2A backup / 2B exclusive candidate / 3A probe / 3 Apollo features |
| Independent console confirmed? | yes / no — physical Shell required for 2B |
| Candidate staged before production QUIT? | yes / no (2B runbook) |
| Concurrent second PORT used? | yes / no — if yes, note hooks owner |
| TLS connected on PORT+1? | yes / no (expect 6802 when PORT=6801) |
| AmiGent client version (`amigent.__version__`) | |
| Client git commit SHA | |
| Client tree dirty? | yes / no |
| Upstream PR(s) this evidence supports | |
| Fork review PR(s) cross-ref | |
| Full `amigent-doctor` used? | **must be no** for Stage 1 (writes RAM:) |

## Hardware and OS

| Field | Value |
|-------|-------|
| Board / model | |
| ApolloOS / Kickstart strings | |
| Exec version / attn flags (if known) | |
| Network path (LAN / VPN) | _(redact addresses if needed)_ |
| Production daemon port (pre-test) | |
| Production daemon hash (pre-test) | |
| Production User-Startup amigent line (redacted) | |

## Binaries under test this session

| Role | Path on Amiga or PC | Size | SHA-256 | Matrix ID (F-DAE / U-DAE / …) |
|------|---------------------|------|---------|-------------------------------|
| Daemon | | | | |
| Probe | | | | |
| Monitor | | | | |
| Other | | | | |

## Evidence class key

| Tag | Meaning |
|-----|---------|
| SW | Software / CI / host harness only |
| HW | Physical Apollo V4 observation |
| UNV | Unverified claim — must not be reported as pass |

---

## Results

Copy rows from the plan as needed.

| Test ID | Class (SW/HW/UNV) | Binary IDs | Expected | Actual | Pass? | Evidence files | Notes |
|---------|-------------------|------------|----------|--------|-------|----------------|-------|
| D1 MMIO harness | SW | — | refuse windows | | | | |
| A2 probe F-PRB | HW | F-PRB | 3224 / 96ca1b38… | ApolloOS+68080 / rc 0 | Stage 3A | 20261121T021031Z | PASSED ON HW |
| A2 probe U-PRB | HW | U-PRB | 3112 / ab454b39… | ApolloOS / rc 0 | Stage 3A | 20261121T021031Z | PASSED ON HW |
| A3 SYSINFO | HW | | | | | | NOT RUN |
| B1 handshake | HW | | | | | | NOT RUN |
| B4 TLSONLY | HW | | | | | | NOT RUN |
| C1 launch/quit | HW | | | | | | NOT RUN |
| C5 identity About | HW | | | | | | NOT RUN |
| D2 MMIO peek refuse | HW | | | | | | NOT RUN |
| D4 AUDIO Hear | HW | | | | | | NOT RUN |
| D5 PIP advertising | HW | | | | | | NOT RUN |
| D7 HRTmon | HW | | | | | | NOT RUN — approval |
| E4 rollback | HW | | | | | | NOT RUN — approval |

### AUDIO observations

| Field | Value |
|-------|-------|
| Start method (Hear / `amiga_listen`) | |
| Stop method | |
| Rate / bytes logged | |
| Subjective playback note | |
| Daemon ID used | F-DAE / U-DAE |

### Failures and reproduction

| Test ID | Symptom | Reproduction steps | Logs |
|---------|---------|----------------------|------|
| | | | |

### Recovery / rollback

| Check | Pre-test | Post-test | Match? |
|-------|----------|-----------|--------|
| Production daemon hash | | | |
| Production port answers | | | |
| User-Startup unchanged | | | |
| Candidate stopped | | | |

### Untested this session

List plan IDs not attempted.

---

## Maintainer attachment blurb (optional)

Paste only after real HW rows are filled:

> Hardware evidence for \<PR\> — client \<sha\>, daemon \<sha256\>, probe \<sha256\>, plan IDs \<…\>, date \<…\>. Software-only rows are tagged SW; physical rows are tagged HW.

## Sign-off

| Role | Name | Date |
|------|------|------|
| Operator | | |
| Approver (L3–L4) | | |
