# Apollo V4 Stage 3B — Evidence closure

**Docs branch tip (pending this commit):** follows `a8eacf8`  
**Private assessment:** `~/amigent-evidence/stage3b-hear-hw/20261121T031620Z/private/evidence-assessment.json`  
**Hardware-tested stream binary:** `983fd853…` @ `1aa7265`  
**Fork `main`:** `79880b8` — not modified by Stage 3B HW sessions

## Final Hear assessment

Bounded supervised streaming on the stream-safe U-HEAR candidate is **hardware-validated** for: proto-6 smoke, nonempty PCM to PC, explicit stop, and production restore. Human-audible confirmation and stock Viewer UI remain **not** established.

## Empty attempt / retry / stream count

| Item | Value |
|------|-------|
| Same exclusive window | Yes |
| Stream starts | **2** (empty then successful) |
| `stream_invocations=1` | Per harness run only |
| Retry | Operator-authorised after empty; AHI then confirmed |
| Limits | Per-run 7 s / 10 s / 2 MiB |

## Playback and UI

| Item | Classification |
|------|----------------|
| SoundPlayer PlaySync | **PASSED** (API) |
| Operator heard PC output | **NOT CONFIRMED** |
| Stock Viewer Hear button path | **NOT TESTED** |
| Harness = Viewer protocol opcodes | Yes (`audio_start`/`read`/`stop`) |

## PCM timing

940704 bytes ÷ 4 ÷ 47931 Hz ≈ **4.91 s** of PCM inside **7.078 s** wall time — overhead unexplained as loss; expected for pump/start/stop.

## Follow-on work (offline / later HW)

- Fork `main` diagnostic-dump removal (separate branch; not HW-validated until tested).  
- Optional future: stock Viewer UI Hear; F-DAE AUDIO; longer soak — each needs explicit authorisation.
