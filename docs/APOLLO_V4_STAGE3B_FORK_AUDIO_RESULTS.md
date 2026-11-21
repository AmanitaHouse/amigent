# Apollo V4 Stage 3B Phase 4 — Corrected fork AUDIO oneshot hardware results

**Status:** **EXECUTED** — nonempty one-shot PCM with signal on corrected fork daemon; production restored  
**Evidence:** `~/amigent-evidence/stage3b-fork-audio/20261121T033439Z`  
**Docs parent tip:** `b31f5e0`  
**Machine:** V4SA (Apollo V4-SA / ApolloOS / Kickstart 51.51)  
**Fork `main`:** `79880b8` (unchanged)

## Candidate (hardware-tested)

| Field | Value |
|-------|-------|
| Staged path | `Programs:AmiGent-Stage3B/amigentd.forksafe` |
| Protect | `+e` rc 0 |
| Size | **129944** |
| SHA-256 | `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` |
| Source | `contrib/fork-audio-stream-safety` @ `496f142` |
| Diagnostic dumps | Absent (`audio-mem` / `audio-ptrs`) |

Do **not** conflate with U-DAE `456fce26…`, F-DAE `1e0e3f65…`, or U-HEAR `983fd853…`.

**Streaming on this fork binary:** later Phase 5 — `docs/APOLLO_V4_STAGE3B_FORK_STREAM_RESULTS.md`. This Phase 4 session was oneshot only.

## Safety gates (before QUIT)

| Gate | Result |
|------|--------|
| Source/binary hash identity | **PASS** |
| No `T:` diagnostic Open paths | **PASS** |
| One-shot `apollo_audio` / separate stream path | **PASS** (source) |
| Production proto 5 TLS preflight | **PASS** |

## Session

| Step | Result |
|------|--------|
| Production QUIT | **PASS** |
| Launch | `Run <NIL: >NIL: Programs:AmiGent-Stage3B/amigentd.forksafe TLSONLY` |
| Proto-6 smoke | **PASS** — ApolloOS, 68080, `audio=1`, `pip=0`, Version/volumes OK |
| AHI source | AmigaAMP looped; PlayTask + `ahi.device` confirmed |
| Exactly one `audio(0)` | **PASS** — see below |
| Post SYSINFO | **PASS** |
| Candidate QUIT | **PASS** |
| Production restore | **PASS** — proto 5 TLS, SYSINFO ×2 |
| Reboot | **None** |

## AUDIO request (exactly one)

| Field | Value |
|-------|-------|
| Client | `AmigaChannel.audio(0)` |
| Opcode / arg | 48 / 0 |
| Completed | Yes (0.021 s) |
| Rate | **47931** |
| Payload bytes | **1920** |
| Frames | **480** |
| Peak / RMS | **1063** / **415.14** |
| Nonzero frames | **480 / 480** |
| Within max 48000 | Yes |
| Raw PCM persisted | **No** |
| Stream / Hear | **Not used** |

**Interpretation:** Nonempty valid PCM with measurable nonzero signal — fork daemon one-shot capture **validated on hardware**.

Comparison note (not a requirement): matches prior U-DAE Phase 2A shape (47931 Hz / 1920 B); amplitudes differ (source content).

## Claim separation

| Claim | Result |
|-------|--------|
| Corrected fork proto-6 smoke (`00443719…`) | **PASSED ON HARDWARE** |
| Corrected fork oneshot nonempty+signal | **PASSED ON HARDWARE** |
| Corrected fork streaming / Hear | See Phase 5 (`FORK_STREAM_RESULTS.md`); stock Viewer UI still NOT TESTED |
| Production restore | **PASSED ON HARDWARE** |

## Conclusion

**APOLLO V4 CORRECTED FORK AUDIO HARDWARE VALIDATED — PRODUCTION RESTORED**

Supervised streaming was later validated in Phase 5; do not infer stock Viewer UI from either session.
