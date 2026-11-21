# Next hardware milestone — fork stream-safe Apollo daemon

**Status:** Prepared only — **not authorised**  
**Purpose:** Smoke + one nonempty `audio(0)` on a **new** fork-built candidate after diagnostic-dump removal.  
**Do not** treat as Hear UI validation unless separately named.

## Candidate (to be filled after offline build)

| Field | Placeholder |
|-------|-------------|
| Branch | `contrib/fork-audio-stream-safety` |
| Source commit | *(build provenance)* |
| Size / SHA-256 | *(build provenance)* |
| Staging path | e.g. `Programs:AmiGent-Stage3B/amigentd.ffork` |

Must **not** overwrite U-DAE, F-DAE, or U-HEAR `983fd853…`.

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
