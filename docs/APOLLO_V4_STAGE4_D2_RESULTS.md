# Apollo V4 Stage 4 D2 — Live MMIO PEEK refuse hardware results

**Status:** **EXECUTED — PASS**  
**Offline GO:** `docs/APOLLO_V4_STAGE4_D2_ADDRESS_SAFETY_REVIEW.md` (`1110a0d`)  
**Evidence:** `~/amigent-evidence/stage4-d2-mmio/20261121T060119Z`  
**Machine:** V4SA · ApolloOS · Kickstart 51.51 · 68080  
**Candidate:** `Programs:AmiGent-Stage3B/amigentd.forksafe`  
**SHA-256 / size:** `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` / **129944**  
**Fork `main` (unchanged by this docs commit):** `d90d282b5276f746da96504f0e70950764caa6d6`

## Session

| Step | Result |
|------|--------|
| Offline GO + frozen list | **PASS** |
| Production preflight proto 5 TLS + SYSINFO ×2 | **PASS** |
| Staged candidate read-back hash | **PASS** |
| Physical-console handover | **PASS** |
| Production QUIT | **PASS** — TLS released |
| Launch `…forksafe TLSONLY` | **PASS** |
| Proto-6 smoke | **PASS** — ApolloOS / 68080 / `poke=0` / `loaded=1` |
| Frozen PEEK sequence | **PASS** — see below |
| Candidate QUIT | **PASS** |
| Production restore `C:amigentd TLSONLY` | **PASS** — proto 5 TLS, SYSINFO ×2 |
| Reboot | **None** |

## PEEK results (each once; no retries)

| ID | Address | Width | Expected | Actual | Match |
|----|---------|-------|----------|--------|-------|
| D2-P1 | `$DFF3FC` | 2 | Refuse Apollo-registers text | `that range includes Apollo registers that a read can change` | **YES** |
| D2-P2 | `$DFF1F4` | 2 | Refuse | same refuse text | **YES** |
| D2-P3 | `$DFF400` | 2 | Refuse | same refuse text | **YES** |
| D2-C1 | `$F80000` | 4 | 4-byte Kickstart ROM | 4 bytes (`11144ef9…`) | **YES** (executed; **out of original control class** — see reconciliation) |
| D2-C2 | `$00000004` | 4 | 4-byte vector / ExecBase slot | 4 bytes (`01800584…`) | **YES** (executed; **out of original control class** — see reconciliation) |

Protected PEEKs: **3**. Control PEEKs: **2**. POKE/TRACE/monitor/HRTmon/AUDIO: **0**.  
Wall time for PEEK sequence: **~0.55 s**. SYSINFO after peeks: ApolloOS / 68080. Operator reported no abnormal behaviour.

**Reconciliation:** `docs/APOLLO_V4_STAGE4_D2_EVIDENCE_RECONCILIATION.md` — original plan required test-owned allocated RAM for optional controls; offline GO incorrectly approved ROM (`$F80000`) and low-memory vector (`$4`). Those reads are preserved as executed observations, **not** as compliant controls.

## Claims

| Claim | Result |
|-------|--------|
| Daemon refuses the three named protected-window PEEKs (HW-observed refuse text; source order refuse-before-`t_add`) | **PASSED ON HARDWARE** (bounded) |
| Other protected MMIO windows | **NOT TESTED ON HARDWARE** |
| D2-C1/C2 system/ROM control reads | **EXECUTED** — successful; **outside** authorised control-address class |
| ALLOWPOKE remained off (`poke=0`) | **PASSED ON HARDWARE** |
| Production restored protocol 5 | **PASSED ON HARDWARE** |
| POKE / TRACE / monitor / HRTmon | **NOT TESTED** |

## Conclusion

**APOLLO V4 STAGE 4 D2 MMIO PROTECTION VALIDATED — PRODUCTION RESTORED**

*(qualified: protected-window refusal on three addresses; control peeks executed but out-of-class vs original authorisation — see reconciliation)*
