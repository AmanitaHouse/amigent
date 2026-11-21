# Apollo V4 Stage 3B — Final AUDIO hardware-validation summary

**Campaign status:** **CLOSED**  
**Board:** Apollo V4-SA · ApolloOS · Kickstart 51.51 · CPU 68080 · AFF_FPGA present  
**Fork `main` tip at close:** `32ab6824d126c0018171183eb5b7a5c57b7e7445`  
**Docs branch:** `validation/apollo-v4-evidence-prep`  
**Primary tested Apollo daemon (stream-safe fork):** SHA-256 `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` (129944 B)

Public-safe. No hosts, credentials, or raw PCM.

## Hardware and production baseline

| Item | Value |
|------|-------|
| Production executable | `C:amigentd` · amigentd **1.3** · protocol **5** · `TLSONLY` |
| Production SHA-256 | `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3` |
| TLS | Certificate-verified; listener on PORT+1 for this install |
| Exclusive sessions | ARexx `QUIT` → staged candidate → restore `C:amigentd TLSONLY` |
| Reboots required in Stage 3B | **None** |

Every exclusive AUDIO session restored production protocol 5 with SYSINFO ×2 before close.

## One-shot AUDIO milestones

| Phase | Binary | Result | Doc |
|-------|--------|--------|-----|
| 1 | U-DAE `456fce26…` | Valid empty capture | `APOLLO_V4_STAGE3B_AUDIO_PHASE1_RESULTS.md` |
| 2A | U-DAE `456fce26…` | Nonempty PCM + nonzero signal @ ~47931 Hz | `APOLLO_V4_STAGE3B_AUDIO_PHASE2A_RESULTS.md` |
| 4 | F-FORKSAFE `00443719…` | Nonempty oneshot on corrected fork | `APOLLO_V4_STAGE3B_FORK_AUDIO_RESULTS.md` |

## Upstream-derived streaming validation

| Phase | Binary | Result | Doc |
|-------|--------|--------|-----|
| 3 | U-HEAR `983fd853…` | Bounded supervised continuous PCM; explicit stop | `APOLLO_V4_STAGE3B_HEAR_RESULTS.md` |

U-HEAR removed unused `T:audio-mem` / `T:audio-ptrs` diagnostic dumps from the stream path. Streaming claims attach only to `983fd853…`, not to oneshot-only `456fce26…`.

## Fork stream-safety correction and packaging

| Step | Identity | Notes |
|------|----------|-------|
| Source | `contrib/fork-audio-stream-safety` @ `496f142` | Stream claim/release, FIFO/grain bounds, no diagnostic dumps |
| Packaged binary | `src/amigent/amiga/bin/amigentd.apollo` | SHA-256 `00443719…` (129944 B) |
| Fork PR **#11** | Packaging + F-DAE supersession | Merged into `main` |
| Prior F-DAE | `1e0e3f65…` (131292 B) | Preserved offline; not stream-HW-validated |

## Viewer Hear lifecycle (offline → merge)

| Step | Identity | Notes |
|------|----------|-------|
| Offline review | `APOLLO_V4_VIEWER_HEAR_UI_SAFETY.md` | End-marker clears Hear; drain bound; 8 MiB PCM budget; `AudioContext.close()` |
| Fork PR **#12** | Viewer Hear lifecycle | Merged into `main` @ `32ab682` |

## Supervised fork streaming + stock Viewer Hear

| Phase | Path | Key metrics | Doc |
|-------|------|-------------|-----|
| 5 | Supervised harness vs `00443719…` | 1× `audio_start`; ~7.1 s; 948352 B; 248 chunks | `APOLLO_V4_STAGE3B_FORK_STREAM_RESULTS.md` |
| 6 | **Stock Viewer ♪** vs `00443719…` | 1× `audio_start`; ~7.6 s; **611840** B; **160** chunks | `APOLLO_V4_STAGE3B_STOCK_VIEWER_HEAR_RESULTS.md` |

Phase 6 evidence: `~/amigent-evidence/stage3b-stock-viewer-hear/20261121T051205Z`.  
Hear OFF used the session watchdog through the **normal UI path** (`submit(audio,on=false)`). End-marker observed; no automatic restart. `AudioContext.close()` is **source-verified** (no separate runtime closure probe was recorded).

### Human-audible playback

**Final result: YES — brief operator-confirmed PC playback** (recorded after Phase 6 restore).

An earlier “inconclusive / not reported” state existed only until that confirmation; it is historical context, not the campaign close result. Docs tip that records YES: `78a68c54ab1905caf6dc166b1c97ac990cfcf4d0`.

## Known limitations (do not over-claim)

- Not a reference fidelity measurement; not a long-duration soak.
- Not universal AHI device-matrix coverage.
- Does **not** validate unpublished upstream `feature/1.5.0`.
- F-DAE (`1e0e3f65…`) AUDIO streaming still **NOT RUN ON HARDWARE**.
- Live MMIO refuse, Apollo monitor, and HRTmon remain **NOT RUN** (Stage 4).
- Peak/RMS were not recomputed for the Phase 6 stock-Viewer capture (PCM not retained).

## Exact provenance (traceability)

| Role | SHA-256 / commit |
|------|------------------|
| Production backup | `b00fef0e…` |
| U-DAE oneshot lineage | `456fce26…` |
| U-HEAR stream-safe | `983fd853…` |
| F-FORKSAFE (packaged + Phase 4–6) | `00443719…` |
| Viewer / packaging `main` | `32ab682…` |
| Phase 6 docs (audible YES) | `78a68c5…` on `validation/apollo-v4-evidence-prep` |

## Production restoration history

All Stage 3B exclusive sessions ended with production `C:amigentd TLSONLY`, protocol **5**, certificate-validated TLS, and two successful read-only SYSINFO responses. No overwrite of `C:amigentd` or `S:User-Startup`. No automatic reboot.

## Closure statement

Stage 3B AUDIO hardware validation on Apollo V4-SA is **complete** for the authorised scope: oneshot, supervised streaming, fork stream-safe packaging, and stock Viewer Hear with brief human-audible confirmation — **production restored**.
