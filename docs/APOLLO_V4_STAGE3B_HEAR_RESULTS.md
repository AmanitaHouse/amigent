# Apollo V4 Stage 3B Phase 3 — Viewer Hear hardware results

**Status:** **EXECUTED** — supervised Hear streaming on stream-safe U-HEAR; production restored  
**Evidence:** `~/amigent-evidence/stage3b-hear-hw/20261121T031620Z`  
**Evidence assessment:** `private/evidence-assessment.json`  
**Docs tip at session end:** `a8eacf8` (this file supersedes claim wording)  
**Machine:** V4SA (Apollo V4-SA / ApolloOS / Kickstart 51.51)  
**Fork `main`:** `79880b8` (unchanged by this session)

## Candidate (hardware-tested binary)

| Field | Value |
|-------|-------|
| Staged path | `Programs:AmiGent-Stage3B/amigentd.hear` |
| Protect | `+e` rc 0 |
| Size | **128496** |
| SHA-256 | `983fd8531ed7e8631a77daac09b9f660cd59137a106dcc8f93a58e760921dd2a` |
| Source | `contrib/apollo-audio-stream-safety` @ `1aa7265` |
| Diagnostic dumps | Absent in this binary |

Do **not** attach these Hear claims to U-DAE `456fce26…` or F-DAE `1e0e3f65…`.

## Evidence ambiguities resolved

| Question | Finding |
|----------|---------|
| Empty Hear in same session? | **Yes** — first supervised stream returned empty keepalives (AHI not playing). Operator then authorised a second Hear. |
| Preserved empty `hear.json`? | **No** — second run overwrote `private/hear.json`. Empty outcome retained in `retry-authorisation.json` + chat. |
| Total `audio_start` requests | **2** across the exclusive session (1 empty + 1 successful). |
| Scope of `stream_invocations=1` | **Per harness `hear()` call**, not the whole session. Successful run’s JSON shows `1`. |
| Retry authorisation | Operator chat: repeat test with audio playing; recorded in `retry-authorisation.json`. |
| Limit scope | Prefer **7 s** / hard **10 s** / **2 MiB** applied **independently per** `hear()` run (not cumulative). |
| Initiation path | **Supervised harness** (`AmigaChannel.audio_start` / `audio_read` / `audio_stop`). |
| Stock Viewer UI | **NOT TESTED** |
| `SoundPlayer.PlaySync` | API completed (rc 0) after Windows-path copy — **playback API execution PASSED**; human hearing **NOT CONFIRMED** |
| PCM vs wall clock | 940704 B @ 47931 Hz ≈ **4.91 s** of audio content inside **7.078 s** wall clock (~2.17 s startup/pump/stop overhead). Expected. |

## Prior related HW (separate binary)

| Claim | Binary | Result |
|-------|--------|--------|
| One-shot nonempty PCM | U-DAE `456fce26…` | **PASSED ON HARDWARE** — Phase 2A |

## This session — claim table

| Claim | Result |
|-------|--------|
| Stream-safe candidate proto-6 TLS/SYSINFO smoke | **PASSED ON HARDWARE** (`983fd853…`) |
| Nonempty PCM streaming to PC | **PASSED ON HARDWARE** |
| Explicit stream termination / drain | **PASSED ON HARDWARE** |
| No automatic restart after stop (this session’s successful run) | **PASSED FOR THIS SESSION** |
| PC playback API execution (`SoundPlayer.PlaySync`) | **PASSED** |
| Human-confirmed audible output | **NOT CONFIRMED** |
| Reference-based audio fidelity | **NOT TESTED** |
| Long-duration streaming stability | **NOT TESTED** |
| Original F-DAE streaming | **NOT TESTED** |
| Stock Viewer Hear UI | **NOT TESTED** |
| Production proto-5 restore + SYSINFO ×2 | **PASSED ON HARDWARE** |

## Successful stream metrics

| Field | Value |
|-------|-------|
| Wall duration | 7.078 s (prefer stop) |
| Chunks with PCM | 246 |
| Aggregate PCM | 940704 bytes |
| Rate | 47931 Hz |
| Format | s16le stereo |
| Peak / RMS | 7448 / 818.64 |
| Nonzero frame ratio | 0.9897 |
| AHI source | AmigaAMP 2.18; `arne.audio` 4.22; unit 0 ARNE (PlayTask confirmed) |

## Session sequence (summary)

1. Gates + stage `amigentd.hear` while production up.  
2. QUIT production → launch U-HEAR → proto-6 smoke **PASS**.  
3. First Hear without AHI → empty keepalives → candidate quit.  
4. Operator-authorised relaunch with AmigaAMP playing.  
5. AHI check **PASS** → second Hear **PASS** → stop → candidate quit.  
6. Restore `C:amigentd TLSONLY` → proto 5 TLS + SYSINFO ×2 **PASS**. No reboot.

## Conclusion

Hardware streaming validation for U-HEAR `983fd853…` stands, with the empty first attempt and harness-vs-UI limitations recorded above.

**APOLLO V4 VIEWER HEAR HARDWARE VALIDATED — PRODUCTION RESTORED**  
*(qualified: supervised harness path; human-audible confirmation NOT CONFIRMED; stock Viewer UI NOT TESTED)*
