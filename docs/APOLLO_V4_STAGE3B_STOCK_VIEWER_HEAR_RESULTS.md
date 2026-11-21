# Apollo V4 Stage 3B Phase 6 — Stock Viewer Hear hardware results

**Status:** **EXECUTED** — stock Viewer Hear against corrected fork daemon; production restored  
**Evidence:** `~/amigent-evidence/stage3b-stock-viewer-hear/20261121T051205Z`  
**Machine:** V4SA (Apollo V4-SA / ApolloOS / Kickstart 51.51)  
**Fork `main` (Viewer source):** `32ab6824d126c0018171183eb5b7a5c57b7e7445` (PR #11 packaging + PR #12 Hear lifecycle)  
**Docs branch:** `validation/apollo-v4-evidence-prep` (`main` unchanged by this documentation)

## Candidate (hardware-tested)

| Field | Value |
|-------|-------|
| Staged path | `Programs:AmiGent-Stage3B/amigentd.forksafe` |
| Size | **129944** |
| SHA-256 | `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` |
| Prior HW | Phase 4 oneshot + Phase 5 supervised stream PASS |

Do **not** conflate with U-DAE `456fce26…`, F-DAE `1e0e3f65…`, or U-HEAR `983fd853…`.

## Stock Viewer identity

| Field | Value |
|-------|-------|
| Commit | `32ab6824d126c0018171183eb5b7a5c57b7e7445` |
| Assets | `src/amigent/web/index.html`, `viewer.js` from that commit (launched via `amigent.viewer.Viewer`) |
| Hear control | Toolbar **♪** (`#hear`); shown when SYSINFO `audio=1` |
| Offline safety | Drain ≤64, end-marker clears Hear, 8 MiB app PCM budget, `AudioContext.close()`, no silent restart |

## Mandatory stock Viewer safety gate (before QUIT)

| Gate | Result |
|------|--------|
| Merged Viewer code/assets (not cached older build) | **PASS** — repo at `32ab682` |
| Hear OFF prevents extra `audio_start` | **PASS** (source + session) |
| Stream end-marker clears Hear | **PASS** (source + end-marker observed) |
| TLS failure does not plaintext-fallback | **PASS** (source) |
| Viewer close cancels pending audio | **PASS** (source) |
| Stop/drain bounded | **PASS** (source; drain ≤64) |
| PCM buffering bounded | **PASS** (app 8 MiB; HW test 2 MiB enforced) |
| `AudioContext.close()` on stop/error | **PASS** (source) |
| Future stream needs new user action | **PASS** (source + session) |
| Stream-start counting for this session | **PASS** — channel hooks |
| Independent duration/byte limits | **PASS** — prefer 7 s / hard 10 s / 2 MiB via normal Hear OFF |

Instrumentation observed and forced OFF only through `submit(audio,on=false)` — **not** a supervised harness substitute for the stream path.

## Session

| Step | Result |
|------|--------|
| Production preflight proto 5 TLS + SYSINFO ×2 | **PASS** |
| Physical-console handover | **PASS** (operator ready) |
| Production QUIT | **PASS** — TLS released |
| Launch | `Run <NIL: >NIL: Programs:AmiGent-Stage3B/amigentd.forksafe TLSONLY` |
| Proto-6 smoke | **PASS** — ApolloOS, 68080, `audio=1`, `pip=0` |
| AHI source | AmigaAMP 2.18 looped; PlayTask + `ahi.device` confirmed |
| Stock Viewer Hear ON (once, ♪ UI) | **PASS** |
| Hear OFF / cleanup | **PASS** — prefer stop ~7 s |
| AmigaAMP stopped | **PASS** (operator) |
| Candidate QUIT | **PASS** — TLS released |
| Production restore | **PASS** — `Run <NIL: >NIL: C:amigentd TLSONLY` |
| Final proto 5 TLS + SYSINFO ×2 | **PASS** |
| Reboot | **None** |

## Hear stream (exactly one `audio_start`)

| Field | Value |
|-------|-------|
| Path | Stock Viewer UI → `Viewer._play_audio` → `AmigaChannel.audio_start` / `read` / `stop` |
| Total `audio_start` (entire session) | **1** |
| Prefer / hard / max PCM | 7 s / 10 s / 2 MiB (session-wide) |
| Wall elapsed (prefer stop) | **~7.6 s** (`prefer_time_with_pcm`) |
| Chunks with PCM | **160** |
| Empty keepalives | **0** |
| Aggregate PCM | **611840** bytes |
| Rate | **47931** Hz |
| Format | s16le stereo |
| Nonzero PCM | **Yes** — 160 nonempty chunks, 0 empty keepalives (peak/RMS not computed; PCM not retained) |
| PC playback path | Stock Viewer Web Audio (`AudioContext`) path active during Hear |
| Human-confirmed audible | **YES** — operator reported brief audible PC playback |
| Hear OFF | Watchdog via normal UI path (`audio on=false`); `hear_final=false` |
| `audio_stop` + end-marker | **Yes** |
| Automatic restart | **None** (starts remain 1) |
| Second `audio_start` attempt | **None** |
| Raw PCM in Git | **No** |

## Claim separation

| Claim | Result |
|-------|--------|
| Stock Viewer Hear vs corrected fork (`00443719…`) | **PASSED ON HARDWARE** |
| Real AHI PCM through merged Viewer | **PASSED ON HARDWARE** |
| Bounded supervised stock Viewer session | **PASSED ON HARDWARE** |
| Explicit Hear OFF + stream cleanup | **PASSED ON HARDWARE** |
| No unintended restart this session | **PASSED ON HARDWARE** |
| PC audio playback path operated | **PASSED** (Web Audio path) |
| Human-audible confirmation | **YES** (brief) |
| Reference fidelity / long soak / device matrix | **NOT TESTED** |
| Upstream unpublished 1.5.0 | **NOT CLAIMED** |
| Production restore | **PASSED ON HARDWARE** |

## Conclusion

**APOLLO V4 STOCK VIEWER HEAR HARDWARE VALIDATED — PRODUCTION RESTORED**

*(human-audible YES — brief PC-side playback confirmed by operator)*
