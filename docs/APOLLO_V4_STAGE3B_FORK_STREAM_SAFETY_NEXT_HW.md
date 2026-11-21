# Next hardware milestone — fork stream-safe Apollo daemon

**Status:** Prepared only — **not authorised**  
**Purpose:** Smoke + one nonempty `audio(0)` on a **new** fork-built candidate after diagnostic-dump removal.  
**Do not** treat as Hear UI validation unless separately named.

## Candidate (offline build — **not** hardware-validated)

| Field | Value |
|-------|-------|
| Branch | `contrib/fork-audio-stream-safety` |
| Source commit | `496f142` |
| Size | **129944** bytes |
| SHA-256 | `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` |
| Staging path (suggested) | `Programs:AmiGent-Stage3B/amigentd.ffork` |
| Evidence copy | `~/amigent-evidence/fork-audio-stream-safety/20261121T033004Z` |

Must **not** overwrite U-DAE `456fce26…`, F-DAE `1e0e3f65…`, or U-HEAR `983fd853…`.

## Prioritised tests (single exclusive session)

1. Source/binary hash verify on PC and staged read-back.  
2. Physical Shell handover; restore command ready.  
3. QUIT production → launch candidate `TLSONLY`.  
4. Proto-6 TLS + SYSINFO (ApolloOS / 68080 / `audio=1`).  
5. Confirm AmigaAMP AHI playing **before** AUDIO.  
6. Exactly one `audio(0)` nonempty capture (metadata only; no raw PCM in Git).  
7. QUIT candidate → restore `C:amigentd TLSONLY` → proto 5 SYSINFO ×2.

## Optional separate authorisation

Stock Viewer Hear UI session (button on/off) — only after the above pass, and only if explicitly authorised. Prefer supervised limits if used.

## Stop conditions

Hash mismatch; smoke fail; empty oneshot with AHI confirmed active (record once, no retry unless authorised); restore uncertain. No auto reboot.
