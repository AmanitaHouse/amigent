# Apollo V4 Stage 3A — Probe hardware results

**Status:** **EXECUTED** — both probes matched contract; production protocol-5 TLS unaffected  
**Session UTC:** `20261121T021031Z`  
**Docs branch tip (pre-results):** `951519d`  
**Machine:** `V4SA` (Apollo V4-SA)  
**Evidence (private, outside Git):** `~/amigent-evidence/stage3a-probe/20261121T021031Z`

## MMIO safety gate (mandatory, before transfer)

| Check | Result |
|-------|--------|
| Shared `apollo_detect.c` control flow (U-PRB@685309d and F-PRB) | IdString `"ApolloOS"` → TRUE; else exec&lt;51 → FALSE; else `AFF_FPGA` → TRUE; else `$DFF3FC` |
| U-PRB / F-PRB `main` | No direct register access; F-PRB only reads `AttnFlags` for stdout/exit |
| Live SYSINFO before staging | `os=ApolloOS`, `cpu=68080`, `attn_flags=42111`, AFF_FPGA set |
| Gate verdict | **PASS** — `$DFF3FC` not reached on this path |
| Production shutdown required | **No** |

## Production preflight

| Item | Observed |
|------|----------|
| Banner / protocol | `amigentd protocol 5`, TLS |
| SYSINFO ×2 | ApolloOS / 68080 / `attn_flags=42111` / Kickstart 51.51 |
| PC U-PRB | 3112 / `ab454b39988bd7b88c24058d0398507456ff12ff180b638d626beac821e1aff4` |
| PC F-PRB | 3224 / `96ca1b389980b5a94ce0fc94c67c8eeafa7dd2455df497f52532e15409ba0265` |

## Staging

| Probe | Path | Read-back SHA-256 | Protect |
|-------|------|-------------------|---------|
| U-PRB | `Programs:AmiGent-Stage3A/amigent-apollo-probe.uprb` | `ab454b39…` (match) | `Protect "…" +e` rc 0 |
| F-PRB | `Programs:AmiGent-Stage3A/amigent-apollo-probe.fprb` | `96ca1b38…` (match) | `Protect "…" +e` rc 0 |

`C:amigentd`, `S:User-Startup`, keys, Stage 2B daemons: **not modified**.

## Hardware observations (actual)

### U-PRB

| Field | Actual | Expected | Match |
|-------|--------|----------|-------|
| Command | `Programs:AmiGent-Stage3A/amigent-apollo-probe.uprb` | — | — |
| stdout | `ApolloOS\n` | `ApolloOS\n` | **Yes** |
| rc | `0` | `0` | **Yes** |
| Production after | SYSINFO OK | — | **Yes** |

### F-PRB

| Field | Actual | Expected | Match |
|-------|--------|----------|-------|
| Command | `Programs:AmiGent-Stage3A/amigent-apollo-probe.fprb` | — | — |
| stdout | `ApolloOS\n68080\n` | `ApolloOS\n68080\n` | **Yes** |
| rc | `0` | `0` | **Yes** |
| Production after | SYSINFO OK | — | **Yes** |

F-PRB exit 0 on this board is hardware evidence for the **ApolloOS ∧ AFF_FPGA** positive path. It does **not** prove negative cases, `$DFF3FC` fallback, install/update selection, or unpublished 1.5.0 detect.

## Differences observed

| Topic | U-PRB | F-PRB |
|-------|-------|-------|
| stdout | `ApolloOS` only | `ApolloOS` then `68080` |
| exit 0 meaning | ApolloOS alone | ApolloOS **and** AFF_FPGA |

## Final production state

| Check | Result |
|-------|--------|
| Protocol | **5** |
| TLS | **Yes** |
| SYSINFO ×2 after both probes | ApolloOS / 68080 / AFF_FPGA present |
| QUIT issued | **No** |
| Daemon restart | **Not required** |

## Out of scope (still NOT RUN)

AUDIO, monitor, HRTmon, live MMIO/`$DFF3FC`, installer/update/fallback, unpublished 1.5.0 probe gating.

## Conclusion

**APOLLO V4 STAGE 3A PROBES HARDWARE VALIDATED — PRODUCTION UNAFFECTED**
