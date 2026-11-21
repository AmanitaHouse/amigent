# Apollo AUDIO — distribution closure and Viewer hardening (offline)

**Status:** Ready for fork-local integration review (not merged)  
**Docs tip:** `validation/apollo-v4-evidence-prep` (this commit)  
**Fork `main`:** `79880b8` (unchanged)  
**No V4 contact / release / upstream PR**

## Why the wheel still shipped F-DAE after the source fix

setuptools packages **prebuilt** executables from `src/amigent/amiga/bin/*` (`[tool.setuptools.package-data]`).  
`amigent-setup` / `daemons.choose` select among those files by name and machine fit.  

Changing `src/native/amiga/platform/apollo/apollo.c` does **not** rebuild or replace `src/amigent/amiga/bin/amigentd.apollo`.  
Therefore `review/fork-audio-stream-safety-main` @ `065c112` (source-only) still produced wheels containing F-DAE `1e0e3f65…` (131292 B).

## Native packaging branch

| Field | Value |
|-------|-------|
| Branch | `review/fork-audio-stream-packaging` |
| Tip | `9502243` |
| Based on | `065c112` (source dump removal) |
| Packaged Apollo | **129944** B / `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` |
| Matches HW candidate | **Yes** (Phase 4/5) |
| Wheel + sdist Apollo hash | **Same** `00443719…` |
| Classic daemons | Unchanged |
| Preserved F-DAE archive | `~/amigent-evidence/fdae-preserved-before-stream-safe-packaging/` |
| Update path | `SUPERSEDED_APOLLO_SHA256` allows replacing known F-DAE at same `$VER: 1.4.0` |
| Fresh install | Selects corrected `amigentd.apollo` on ApolloOS+68080 |
| Regression | **354 passed, 4 skipped** |

Suggested PR title: `fix(apollo): ship daemon without unsafe audio diagnostic dumps`

Dependency: packaging branch **includes** the source fix (`065c112` ancestry). Prefer merging this packaging branch (or PR that stacks source+bytes). A source-only merge is **not** a completed distribution fix.

## Viewer lifecycle branch

| Field | Value |
|-------|-------|
| Branch | `contrib/viewer-hear-ui-safety` |
| Tip | `e187e6e` |
| Auto-restart after daemon end | **Prevented** (`hear` cleared; release always) |
| Drain | Bounded (`AUDIO_DRAIN_MAX = 64`) |
| Aggregate PCM | `AUDIO_PCM_BUDGET = 8 MiB` per Hear (not the 10 s HW cap) |
| `AudioContext` | Closed in `stopHear` |
| TLS plaintext fallback | Unchanged (still refused) |
| User re-Hear after cleanup | Allowed |
| Regression | **363 passed, 4 skipped** |
| Hardware UI validation | **NOT DONE** |

Suggested PR title: `fix(viewer): prevent unintended Hear restart and release audio resources`

## Suggested merge order

1. Native packaging PR (`9502243`) — source + packaged binary + identity/update tests.  
2. Viewer PR (`e187e6e`) — independent; can land before or after packaging.  
3. Separately authorised stock Viewer Hear **hardware** session (runbook below).  
4. Do **not** publish a release until packaging PR is merged and release process is authorised.

## Future stock Viewer Hear HW session (not executed)

1. Hash-verify packaged/staged Apollo = `00443719…`.  
2. Physical Shell recovery ready; QUIT production → launch candidate `TLSONLY`.  
3. Proto-6 TLS smoke; AmigaAMP PlayTask.  
4. One stock Viewer Hear on/off; confirm **one** `audio_start`; OFF + cleanup.  
5. Record whether a human hears PC playback.  
6. Restore `C:amigentd TLSONLY`; proto 5 SYSINFO ×2.

## Claim matrix (unchanged boundaries)

| Capability | Status | Hash |
|------------|--------|------|
| U-DAE proto-6 | PASSED ON HW | `456fce26…` |
| F-DAE proto-6 | PASSED ON HW | `1e0e3f65…` |
| U-HEAR supervised stream | PASSED ON HW | `983fd853…` |
| F-FORKSAFE oneshot+stream | PASSED ON HW | `00443719…` |
| Packaged Apollo (proposed) | Bytes match HW; install offline-tested | `00443719…` |
| Stock Viewer Hear UI | Offline hardened; **NOT TESTED ON HW** | — |
| Human audible | NOT CONFIRMED | — |
| Upstream 1.5.0 | NOT VERIFIED | — |
