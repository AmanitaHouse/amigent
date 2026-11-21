# Apollo V4 Stage 2B results — F-DAE exclusive protocol-6 validation

**Session UTC start:** 2026-11-21T01:45:48Z  
**Authorisation:** Stage 2B exclusive — physical Shell confirmed; F-DAE staging + temporary production interruption  
**Runbook:** `docs/APOLLO_V4_STAGE2B_FDAE_RUNBOOK.md`  
**Docs parent tip:** `e9860b0`  
**Fork `main` (unchanged):** `79880b8f018ae735715de4f1d0e943acf4462dcd`  
**Client:** Amigent `1.4.0` from docs checkout `e9860b0`  
**Machine:** `V4SA`  
**PC evidence (private):** `~/amigent-evidence/stage2b-fdae-exclusive/20261121T014548Z/`

U-DAE was **not** re-run as fallback. Stage 3 was **not** started. `C:amigentd` and `…/amigentd.udae` were **not** overwritten. No automatic reboot.

## Session metadata

| Field | Value |
|-------|-------|
| Test date (UTC) | 2026-11-21 |
| Session stage | **2B exclusive candidate (F-DAE)** |
| Independent console | **yes** |
| Candidate staged before QUIT | **yes** |
| Concurrent second PORT | **no** |
| TLS on PORT+1 (6802) | **yes** |

## Binary under test

| Role | Path | Size | SHA-256 | ID |
|------|------|-----:|---------|-----|
| Candidate | `Programs:AmiGent-Stage2B/amigentd.fdae` | 131292 | `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` | **F-DAE** |
| Production (untouched) | `C:amigentd` | 113324 | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` | prod 1.3 |
| Prior U-DAE staging (untouched) | `Programs:AmiGent-Stage2B/amigentd.udae` | 129844 | _(left in place; not launched)_ | U-DAE |

## Results summary

| Step | Result | Notes |
|------|--------|-------|
| Staging + read-back hash | **PASS** | Match F-DAE; `Protect "…/amigentd.fdae" +e` rc=0 |
| Console handover | **PASS** | Operator confirmed |
| Production `QUIT` | **PASS** | TLS 6802 refused afterward |
| F-DAE launch (console) | **PASS** | `Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.fdae TLSONLY` |
| Protocol-6 + TLS | **PASS** | Banner `amigentd protocol 6` |
| SYSINFO / volumes / Version | **PASS** | See below |
| Candidate `QUIT` | **PASS** | TLS 6802 refused |
| Production restore | **PASS** | `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Final protocol-5 + TLS | **PASS** | Second `sysinfo()` OK |
| Reboot / recovery intervention | **none** | |

## Hardware observations (F-DAE / protocol 6)

| Field | Observed |
|-------|----------|
| Negotiated protocol | **6** |
| TLS | yes |
| `os` | ApolloOS |
| `board_name` | V4-SA |
| `cpu` | 68080 |
| `kickstart` | 51.51 |
| `exec_version` | 51.3 |
| `attn_flags` | 42111 (AFF_FPGA present) |
| Shell `Version` | Kickstart 51.51, Workbench 40.0 |
| `self` | `Programs:AmiGent-Stage2B/amigentd` (staged leaf was `amigentd.fdae`; same naming caveat as U-DAE) |
| `poke` | 0 |
| `probe` | 1 |
| `loaded` | 1 |
| `audio` | 1 — **not exercised** |
| `pip` | 0 — **not a picture claim; PIP not tested** |

## Differences from U-DAE session

| Topic | U-DAE | F-DAE |
|-------|-------|-------|
| Size / SHA-256 | 129844 / `456fce26…` | 131292 / `1e0e3f65…` |
| Staging leaf | `amigentd.udae` | `amigentd.fdae` |
| Protocol / TLS / OS / CPU | 6 / yes / ApolloOS / 68080 | **Same outcome class** |
| `pip` in SYSINFO | not highlighted in U-DAE observed set | explicitly **`pip=0`** |
| `self` extension | omitted (`.udae`) | omitted (`.fdae`) — same `GetProgramName` mechanism |
| Production restore | protocol 5, no reboot | **same** |

## Explicitly not validated

AUDIO/Hear, monitor, HRTmon, live MMIO/ALLOWPOKE, probe execution, PIP picture, installer/update/fallback.

## Confirmations

- No Update swap; no V4 writes beyond approved staging directory.  
- PC client closed without remote shutdown of restored production.  
- Private evidence outside Git.
