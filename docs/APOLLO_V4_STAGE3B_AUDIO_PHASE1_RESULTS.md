# Apollo V4 Stage 3B Phase 1 — AUDIO one-shot results

**Status:** **EXECUTED** — one-shot `audio(0)` completed; **valid empty** PCM; production restored  
**Session UTC:** `20261121T022512Z` (evidence root)  
**Docs parent tip:** `ba44492`  
**Machine:** V4SA (Apollo V4-SA)  
**Evidence (private):** `~/amigent-evidence/stage3b-audio-phase1/20261121T022512Z`

## Safety gates (before QUIT)

| Gate | Result |
|------|--------|
| B1 Forbid/Permit | **PASS** |
| B2 SetTaskPri (oneshot) | **PASS** — not used on one-shot path |
| B3 One-shot isolation | **PASS** — no stream / no `T:audio-mem` / no DFF |
| B4 Protocol contract | **PASS** — opcode 48, ≤48000 B, s16le |

## Binaries

| Role | Path | SHA-256 |
|------|------|---------|
| Production backup (PC) | Stage 2A backup | `b00fef0e…` |
| U-DAE staged | `Programs:AmiGent-Stage2B/amigentd.udae` | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` (read-back match) |

## Session steps

| Step | Result |
|------|--------|
| Operator Shell handover | Confirmed |
| Production QUIT | PASS — TLS 6802 refused |
| U-DAE launch | Operator: `Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.udae TLSONLY` |
| Proto 6 + TLS | PASS — `audio=1`, ApolloOS, 68080 |
| **Single** `audio(0)` | PASS — see below |
| Post-request SYSINFO | PASS — responsive |
| U-DAE QUIT | PASS — TLS refused |
| Production restore | Operator: `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Proto 5 + TLS + SYSINFO ×2 | PASS |
| Reboot | **Not required** |

## AUDIO request (exactly one)

| Field | Value |
|-------|-------|
| Client | `AmigaChannel.audio(0)` |
| Opcode / arg / y | 48 / 0 / 0 |
| Timeout | 30 s channel bound |
| Completed | Yes (0.012 s) |
| Rate | `0` |
| Payload bytes | `0` |
| Framing | Valid empty (status OK; n=0) |
| Within max 48000 | Yes |
| PCM persisted | **No** (metadata only) |
| Stream / Hear | **Not used** |

**Interpretation:** Successful one-shot **request handling** on V4. Empty payload is an expected quiet-AHI / no-new-half outcome. **Does not** demonstrate audible capture, fidelity, streaming, or Viewer Hear.

## Abnormal behaviour

None observed (operator and PC). No second AUDIO call. No speculative retry.

## Coverage update

- AUDIO opcode 48 one-shot: **PASSED_ON_HARDWARE (valid empty)**  
- Viewer Hear / stream / F-DAE AUDIO: still **NOT_RUN_ON_HARDWARE**

## Conclusion

**APOLLO V4 STAGE 3B PHASE 1 AUDIO REQUEST VALIDATED — PRODUCTION RESTORED**  
*(qualified: successful empty one-shot; no audible capture demonstrated)*
