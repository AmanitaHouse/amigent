# Apollo V4 Stage 3B — AUDIO / Hear hardware runbook

**Status:** Prepared offline — **Stage 3B hardware execution not authorised**  
**Safety audit:** `docs/APOLLO_V4_STAGE3B_AUDIO_SAFETY_AUDIT.md`  
**Prerequisite HW:** Stage 2B U-DAE + F-DAE proto-6 smoke PASSED; Stage 3A probes PASSED; production restored/continuous.

## Authorisation model

| Phase | What | Separate approval? |
|-------|------|--------------------|
| **1** | Exclusive candidate + **one-shot** opcode 48 | **Yes** — first AUDIO contact |
| **2** | Viewer Hear stream + PC playback | **Yes** — only after Phase 1 pass |
| **3** | Other daemon binary AUDIO | **Yes** — do not infer from Phase 1 |

No Phase runs in this preparation task.

## Recommended first candidate

**U-DAE** — protected contribution daemon (AUDIO unit under review).

| Field | Value |
|-------|-------|
| Size | 129844 |
| SHA-256 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` |
| Staging (reuse Stage 2B path if still present and hash-matches) | `Programs:AmiGent-Stage2B/amigentd.udae` |
| Or Stage 3B path | `Programs:AmiGent-Stage3B/amigentd.udae` |

F-DAE (`1e0e3f65…`) is Phase 3 only unless authorisation names it first.

## Why exclusive

Concurrent AUDIO with production is **not** established safe (`audio_owner` is per-process; hooks/monitor already exclusive). Reuse Stage 2B physical-Shell recovery.

## Phase 1 — Minimal AUDIO opcode validation

### Preconditions

1. Physical keyboard + display Shell ready.  
2. Production protocol **5** + TLS responsive.  
3. PC backup `~/amigent-evidence/stage2a-production-backup/20261121T010816Z/v4-production-C-amigentd.bin` SHA-256 `b00fef0e…`.  
4. Candidate hash re-verified on PC.  
5. Staging read-back hash OK; `Protect "…" +e`.  
6. Restoration command ready: `Run <NIL: >NIL: C:amigentd TLSONLY`.

### Sequence (mirrors Stage 2B order)

1. Stage candidate **while production is up**; read-back hash.  
2. `ADDRESS AMIGENT 'QUIT'`; wait until `AMIGENT` gone; confirm TLS 6802 dead.  
3. Launch: `Run <NIL: >NIL: <staged-udae> TLSONLY` (cwd preferably `SYS:`).  
4. PC connect pinned TLS → protocol **6**; `sysinfo()` — require `audio=1`.  
5. **Single** one-shot: `Commands.audio(0)` (or `ms=0`).  
6. Record: rate, byte length, first/last 16 bytes hex (or SHA-256 of PCM), elapsed time.  
7. Optional second one-shot **only if** first returned empty **and** operator confirms an AHI source is playing — still one additional call max; no loops.  
8. Candidate `QUIT`.  
9. Restore `C:amigentd TLSONLY`; verify protocol **5** + TLS + `sysinfo()`.

### Minimal request / limits

| Item | Value |
|------|-------|
| Request | Opcode 48, arg 0, y 0 (one-shot) |
| Max native buffer | 48000 bytes |
| Client timeout | ≤ 30 s (existing channel default) |
| Retries | **None** automatic |
| Stream / Hear | **Out of scope** for Phase 1 |
| Expected empty | Valid if no AHI mix / wrong `arne.audio` version — record as empty success of transport + quiet mix, not as Hear pass |

### Distinguishing transport success from audio content

| Outcome | Meaning |
|---------|---------|
| Status OK, rate>0, n≥4, n%4==0 | Framed PCM present — Phase 1 content PASS |
| Status OK, n=0 | Opcode path OK; mix absent/quiet — Phase 1 **transport** PASS; content deferred |
| Error / hang / wrong size | **STOP** |

### Operator audio source (if non-empty required)

Use an operator-approved AHI playback already running on the V4 (game/mod player). Do **not** capture private mic/conversations. Do not start AUDIO/monitor/HRTmon extras beyond the daemon under test.

## Phase 2 — Viewer Hear (separate authorisation)

Only after Phase 1 recorded a clean one-shot path (empty or PCM).

1. Same exclusive U-DAE (or re-authorised session).  
2. Start `amigent-viewer` against candidate TLS.  
3. Confirm UI shows audio capability from SYSINFO.  
4. Operator enables Hear once; capture ~1–2 s PC-side; then disable.  
5. Verify: stream starts/stops; sample rate matches Phase 1; duration plausible; no TLS fallthrough to plaintext.  
6. Note: stream path may create **`T:audio-mem`** after ~4 halves — expect/document; do not treat as SAGA MMIO.  
7. Stop Hear → candidate QUIT → restore production.

Do **not** auto-enter Phase 2 when Phase 1 passes.

## Phase 3 — F-DAE (or second binary)

Separate exclusive session. Same Phase 1 one-shot contract. Shared source lineage does **not** waive a second binary’s evidence row.

## Stop conditions

Stop immediately on: unexpected audio glitches / silence of whole machine, display freeze, RAM exhaustion, daemon hang/crash, TLS failure, chunk >256 KiB, odd frame size, suspected unreleased resources, any scope creep (PIP, MMIO, monitor, HRTmon, setup/update).

No speculative retries. No automatic reboot. Operator-controlled reboot only if Stage 2B recovery rules require it.

## Evidence (private, outside Git)

`~/amigent-evidence/stage3b-audio/<UTC>/`

Record: binary SHA, staging path, commands, one-shot rate/len/hash, Hear notes (Phase 2), production restore proof. Do **not** commit PCM/WAV or credentials.

## Out of scope

Production in-place AUDIO, concurrent second PORT AUDIO, PIP, live `$DFF` audio regs, unpublished 1.5.0, install/update selection.
