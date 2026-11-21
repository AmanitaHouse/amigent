# Apollo V4 Stage 3B Phase 2A — Controlled nonempty AUDIO capture

**Status:** **EXECUTED** — nonempty one-shot PCM with measurable signal; production restored  
**Session UTC evidence root:** `20261121T024102Z`  
**Docs parent tip:** `c0fd6a3`  
**Machine:** V4SA (Apollo V4-SA / ApolloOS / Kickstart 51.51)  
**Evidence (private):** `~/amigent-evidence/stage3b-audio-phase2a/20261121T024102Z`  
**Fork `main`:** `79880b8` (unchanged)

## Scope

Exactly one exclusive U-DAE `audio(0)` while an operator-controlled AHI source was active.  
**Not** exercised: Viewer Hear, streaming (`audio(1)`/`audio(2)`/`audio_start`/`audio_stop`), F-DAE AUDIO, AHI prefs changes, new player install, MMIO/HRTmon/monitor/PIP, reboot.

Phase 1 valid-empty result is **not** reinterpreted as nonempty capture.

## AHI source (before production interrupt)

| Item | Finding |
|------|---------|
| Driver | `DEVS:AHI/arne.audio` **4.22** |
| Prefs | `ENV:sys/ahi.prefs` unit **0** mode id **`0x01010002`** (ARNE HiFi) |
| Player | `SYS:Utilities/AmigaAMP3/Music` (AmigaAMP **2.18**), prefs `AHIUnit=0`, Engine=MPEGA |
| Staged tone | `Programs:AmiGent-Stage3B/amigent-ahi-tone440.wav` (original 440 Hz WAV, SHA `a5fcb97a…`) |
| Staged tone result | AmigaAMP reported **Can't open file!** (MPEGA engine unsuitable for that WAV) |
| Active source | Operator-selected **alternate** media file, **loop** enabled |
| Mix evidence | Preflight SYSINFO tasks included `AmigaAMP PlayTask`, `ahi.device Unit Process`; port `AMIGAAMP` |

No AHI reconfiguration; no new executable software installed.

## Safety reconfirm (U-DAE one-shot)

| Gate | Result |
|------|--------|
| `audio(0)` one-shot only | **PASS** — single invocation |
| No stream / no `T:audio-mem` | **PASS** (arg 0 path) |
| No resident capture task left by request | **PASS** — post SYSINFO responsive; no further AUDIO |
| Payload bound ≤48000 | **PASS** — 1920 bytes |
| Format | s16le stereo (4-byte frames); client framing OK |
| Scheduling / priority restore | Source-audited; no abnormal behaviour observed |

## Binaries

| Role | Path | SHA-256 |
|------|------|---------|
| Production backup (PC) | Stage 2A `…/v4-production-C-amigentd.bin` | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| U-DAE staged (read-back) | `Programs:AmiGent-Stage2B/amigentd.udae` | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` (129844 B) |

## Session steps

| Step | Result |
|------|--------|
| Preflight (proto 5 TLS, SYSINFO ×2, hashes, Avail) | **PASS** |
| Production QUIT | **PASS** — TLS refused |
| U-DAE launch | Operator: `Run <NIL: >NIL: Programs:AmiGent-Stage2B/amigentd.udae TLSONLY` |
| Proto 6 + TLS + `audio=1` | **PASS** — ApolloOS, 68080 |
| Controlled AHI source | AmigaAMP loop kept active across launch |
| **Single** `audio(0)` | **PASS** — see below |
| Post-request SYSINFO | **PASS** |
| Source stop | Operator (AmigaAMP) |
| U-DAE QUIT | **PASS** — TLS refused |
| Production restore | Operator: `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Proto 5 + TLS + SYSINFO ×2 | **PASS** |
| Reboot / recovery intervention | **None** |

## AUDIO request (exactly one)

| Field | Value |
|-------|-------|
| Client | `AmigaChannel.audio(0)` |
| Opcode / arg | 48 / 0 |
| Timeout | 30 s channel bound |
| Completed | Yes (0.020 s) |
| Rate | **47931** |
| Payload bytes | **1920** |
| Frames (stereo) | **480** (~0.01 s @ reported rate) |
| Alignment | Multiple of 4; within max 48000 |
| Peak abs (s16) | **151** |
| RMS | **89.05** |
| Nonzero frames | **480 / 480** |
| PCM SHA-256 (metadata only) | `e5110d919cf5aa14936533512726799d4ddc12aca21aafb75dcb31cd7d0de713` |
| Raw PCM persisted | **No** |
| Stream / Hear | **Not used** |

**Interpretation:** Successful **real hardware nonempty PCM capture** with a measurable nonzero signal while AmigaAMP held the AHI/`arne.audio` mix. Fidelity, full-band accuracy, and PC playback are **untested**. Operator alternate looped file identity was not recorded as a filesystem path in private evidence (loop confirmed by operator + AmigaAMP task presence).

## Abnormal behaviour

None observed. No second AUDIO call. No reboot.

## Coverage update

- AUDIO opcode 48 one-shot (quiet AHI): **PASSED_ON_HARDWARE (valid empty)** — Phase 1  
- AUDIO opcode 48 one-shot (AHI source active): **PASSED_ON_HARDWARE (nonempty + signal)** — Phase 2A  
- Viewer Hear / stream / F-DAE AUDIO: still **NOT_RUN_ON_HARDWARE**

## Remaining for Viewer Hear

Separate authorisation required for: Viewer Hear UI / `amiga_listen`, streaming opcodes, sustained capture, fidelity checks, and any F-DAE AUDIO session.

## Conclusion

**APOLLO V4 NONEMPTY AUDIO CAPTURE VALIDATED — PRODUCTION RESTORED**
