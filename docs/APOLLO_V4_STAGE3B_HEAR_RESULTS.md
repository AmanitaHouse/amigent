# Apollo V4 Stage 3B Phase 3 — Viewer Hear hardware results

**Status:** **EXECUTED** — supervised Hear stream with nonempty PCM + PC playback attempt; production restored  
**Evidence:** `~/amigent-evidence/stage3b-hear-hw/20261121T031620Z`  
**Docs parent tip:** `bbae217`  
**Machine:** V4SA (Apollo V4-SA / ApolloOS / Kickstart 51.51)  
**Fork `main`:** `79880b8` (unchanged)

## Candidate

| Field | Value |
|-------|-------|
| Path staged | `Programs:AmiGent-Stage3B/amigentd.hear` |
| Protect | `+e` rc 0 |
| Size | 128496 |
| SHA-256 | `983fd8531ed7e8631a77daac09b9f660cd59137a106dcc8f93a58e760921dd2a` |
| Source | `contrib/apollo-audio-stream-safety` @ `1aa7265` |
| Diagnostic dumps | Absent (`audio-mem` / `audio-ptrs` not in binary) |

Historical U-DAE `456fce26…` and F-DAE `1e0e3f65…` were not overwritten.

## Safety gates (before QUIT)

| Gate | Result |
|------|--------|
| No `T:audio-mem` / `T:audio-ptrs` in source/binary | **PASS** |
| Bounded FIFO / framing / claim-release | **PASS** (source audit) |
| Enforced limits | Supervised harness: prefer **7 s**, hard **10 s**, max **2 MiB** |
| Explicit off / no auto-restart | **PASS** — `audio_stop` + close; `stream_invocations=1` |
| Stock Viewer alone | Insufficient for independent limits — harness used (same protocol path) |

## Session sequence

| Step | Result |
|------|--------|
| Production preflight proto 5 TLS | **PASS** |
| Stage + read-back hash | **PASS** |
| Production QUIT | **PASS** — TLS refused |
| Candidate launch | Operator: `Run <NIL: >NIL: Programs:AmiGent-Stage3B/amigentd.hear TLSONLY` |
| Proto-6 smoke | **PASS** — ApolloOS, 68080, `audio=1`, AFF_FPGA flags 42111 |
| First Hear (AHI inactive) | Stream started; **0 PCM** (empty keepalives); stopped at hard limit — **not** full validation |
| Operator-authorised retry | AHI confirmed (`AmigaAMP PlayTask` + `ahi.device`) |
| Second Hear (authorised) | **PASS** — see below |
| Candidate QUIT | **PASS** |
| Production restore | Operator: `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Proto 5 TLS + SYSINFO ×2 | **PASS** |
| Reboot | **None** |

## Authorised Hear stream (with AHI playing)

| Field | Value |
|-------|-------|
| Path | `audio_start` / `audio_read` / `audio_stop` (Viewer protocol path) |
| Duration | **7.078 s** (prefer stop with PCM) |
| Chunks with PCM | **246** |
| Aggregate PCM | **940704** bytes (within 2 MiB) |
| Sample rate | **47931** Hz |
| Format | s16le stereo |
| Frames | 235176 (~4.91 s of audio) |
| Peak / RMS | **7448** / **818.64** |
| Nonzero frames | 232760 / 235176 (0.9897) |
| Stop | Explicit `audio_stop`; drain OK |
| Auto-restart | **None** |
| Oneshot `audio(0)` | **Not used** |

## PC playback

| Field | Value |
|-------|-------|
| Local WAV (private evidence only) | `private/hear-capture-local-only.wav` |
| Player | Windows `Media.SoundPlayer` PlaySync (rc 0) |
| Operator quality word | Not separately recorded in chat |
| Fidelity vs source | **Not claimed** |

## Claim separation

| Claim | Result |
|-------|--------|
| Protocol-6 smoke of `983fd853…` | **PASSED ON HW** |
| Native streaming start/stop | **PASSED ON HW** |
| Nonempty PCM reception | **PASSED ON HW** |
| Nonzero signal | **PASSED ON HW** |
| Audible PC playback | **ATTEMPTED / PlaySync completed** (quality not scored) |
| Stream cleanup / no restart | **PASSED ON HW** |
| Production proto-5 restore | **PASSED ON HW** |

## Coverage

- Viewer Hear / stream (stream-safe candidate): **PASSED_ON_HARDWARE** (bounded supervised session)  
- F-DAE AUDIO: still **NOT_RUN_ON_HARDWARE**  
- Long-duration / soak / upstream 1.5.0: **NOT RUN**

## Conclusion

**APOLLO V4 VIEWER HEAR HARDWARE VALIDATED — PRODUCTION RESTORED**
