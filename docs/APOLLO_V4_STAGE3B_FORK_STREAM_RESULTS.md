# Apollo V4 Stage 3B Phase 5 — Corrected fork AUDIO streaming hardware results

**Status:** **EXECUTED** — nonempty supervised continuous PCM on corrected fork daemon; production restored  
**Evidence:** `~/amigent-evidence/stage3b-fork-stream/20261121T034526Z`  
**Docs parent tip:** `0ac49e9`  
**Machine:** V4SA (Apollo V4-SA / ApolloOS / Kickstart 51.51)  
**Fork `main`:** `79880b8` (unchanged)

## Candidate (hardware-tested)

| Field | Value |
|-------|-------|
| Staged path | `Programs:AmiGent-Stage3B/amigentd.forksafe` |
| Size | **129944** |
| SHA-256 | `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` |
| Source | `contrib/fork-audio-stream-safety` @ `496f142` |
| Diagnostic dumps | Absent (`audio-mem` / `audio-ptrs`) |

Do **not** conflate with U-DAE `456fce26…`, F-DAE `1e0e3f65…`, or U-HEAR `983fd853…`.

Prior oneshot on this binary: Phase 4 — `docs/APOLLO_V4_STAGE3B_FORK_AUDIO_RESULTS.md`.

## Mandatory streaming safety gates (before QUIT)

| Gate | Result |
|------|--------|
| Candidate hash + staged read-back | **PASS** |
| No `T:audio-mem` / `T:audio-ptrs` paths | **PASS** |
| Stream claim/release; FIFO 256 KiB; grain ≤4096 | **PASS** (source) |
| Forbid/Permit path-balanced; SetTaskPri restored | **PASS** (source) |
| Client `audio_start` / `read` / `stop`; chunk cap 256 KiB | **PASS** |
| Session-wide harness: 1× start, hard 10 s, 2 MiB, no retry, no budget reset | **PASS** |
| Production proto 5 TLS preflight SYSINFO ×2 | **PASS** |

Enforcement: monotonic `time.monotonic` deadline from first `audio_start` + cumulative PCM counter + persisted ledger (second process cannot reset).

## Session

| Step | Result |
|------|--------|
| Production QUIT | **PASS** |
| Launch | `Run <NIL: >NIL: Programs:AmiGent-Stage3B/amigentd.forksafe TLSONLY` |
| Proto-6 smoke | **PASS** — ApolloOS, 68080, `audio=1`, `pip=0` |
| AHI source | AmigaAMP 2.18 looped; PlayTask + `ahi.device` confirmed |
| Supervised stream | **PASS** — see below |
| Post-stream SYSINFO | **PASS** |
| Candidate QUIT | **PASS** |
| Production restore | **PASS** — proto 5 TLS, SYSINFO ×2 |
| Reboot | **None** |

## Stream (exactly one `audio_start`)

| Field | Value |
|-------|-------|
| Path | `AmigaChannel.audio_start` / `audio_read` / `audio_stop` |
| Total `audio_start` invocations (session) | **1** |
| Prefer / hard / max PCM | 7 s / 10 s / 2 MiB (session-wide) |
| Wall elapsed | **7.114 s** (prefer stop) |
| Chunks with PCM | **248** |
| Empty keepalives | 0 |
| Aggregate PCM | **948352** bytes |
| Rate | **47931** Hz |
| Format | s16le stereo |
| Frames | 237088 |
| Peak / RMS | **7448** / **827.58** |
| Nonzero frame ratio | **0.9877** |
| Stop | explicit `audio_stop`; drain 3; reason `prefer_time_with_pcm` |
| Automatic restart | **None** (harness; invocations remain 1) |
| Malformed chunks | none |
| Raw PCM in Git | **No** |
| Stock Viewer UI | **NOT TESTED** |
| Human-confirmed audible | **NOT CONFIRMED** (`SoundPlayer` API rc 0 only) |

**Interpretation:** Nonempty continuous PCM with signal under session-wide bounds — fork streaming **validated on hardware** via supervised harness.

## Claim separation

| Claim | Result |
|-------|--------|
| Corrected fork proto-6 smoke (`00443719…`) | **PASSED ON HARDWARE** |
| Corrected fork oneshot nonempty+signal | **PASSED ON HARDWARE** (Phase 4) |
| Corrected fork continuous streaming (supervised) | **PASSED ON HARDWARE** |
| Explicit stream stop; no restart this session | **PASSED ON HARDWARE** |
| Stock Viewer Hear UI | **NOT TESTED** |
| Human-confirmed audible playback | **NOT CONFIRMED** |
| Long-duration soak / fidelity | **NOT TESTED** |
| Production restore | **PASSED ON HARDWARE** |

## Conclusion

**APOLLO V4 CORRECTED FORK STREAMING HARDWARE VALIDATED — PRODUCTION RESTORED**

*(qualified: supervised harness path; human-audible NOT CONFIRMED; stock Viewer UI NOT TESTED)*
