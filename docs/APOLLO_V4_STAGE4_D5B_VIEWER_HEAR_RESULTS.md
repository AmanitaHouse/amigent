# Apollo V4 — Stage 4 D5B hardened stock Viewer Hear results

**Session:** Stage 4 D5B — continuous AUDIO via stock Viewer on hardened Apollo daemon  
**Evidence (private):** `~/amigent-evidence/stage4-d5b-hardened-viewer-hear/20261121T082420Z`  
**Mode:** Exclusive candidate launch; production restored  
**Conclusion:** **APOLLO V4 STAGE 4 D5B HARDENED VIEWER HEAR VALIDATED — PRODUCTION RESTORED**  
**Human-audible:** **YES — audible PC audio (choppy)**; Viewer connection-loss reported after Hear

## Identities

| Role | Value |
|---|---|
| Fork `main` | `fad6693a1678c5ae65c60d29a9a6a6b74feb42f3` |
| Candidate path | `Programs:AmiGent-Stage4/amigentd.d4` |
| Candidate size / SHA-256 | 128744 / `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| Viewer source commit | `fad6693…` (PRs #12/#13 Hear visibility + lifecycle) |
| Viewer.js SHA-256 | `151fd6ea88f7b952e374565a9343fb9aa7bdf0e7344f3e1f8139292b2da15715` |
| Viewer.py SHA-256 | `b054766387252fb1136fe107582c20ae30ef19562b10a139308aa482c3685f35` |
| Launch | stock `amigent.viewer.Viewer` + channel observation hooks / Hear-OFF watchdog |

Prior D5 sessions preserved separately (not consolidated):

- Valid empty: `…/stage4-d5-audio-regression/20261121T080724Z`
- Nonempty oneshot remake: `…/stage4-d5-audio-remake/20261121T081528Z`

## Limits enforced (session-wide, no reset)

| Limit | Value |
|---|---|
| Hear activations / `audio_start` | 1 |
| Prefer stop | ~7 s with PCM |
| Hard deadline | 10 s from first Hear |
| Aggregate PCM | 2 MiB (stricter than Viewer 8 MiB) |
| Retries | 0 |

Instrumentation observed `audio_start`/`read`/`stop` and forced OFF only via `submit(audio,on=false)` — same path as the UI button. Stream path remained stock Viewer `_play_audio`.

## Sequence

1. D5B OFFLINE GO + production preflight (staged hash match).  
2. Operator handover → production QUIT → `.d4` launch.  
3. Proto-6 TLS smoke PASS (`audio=1`, `poke=0`, `trace=0`, `pip=0`).  
4. Operator **audio playing** (explicit; not PlayTask-only).  
5. Stock Viewer launched (Hear OFF) → one ♪ Hear ON.  
6. Watchdog prefer-stop → Hear OFF / `audio_stop` / end-marker.  
7. Operator audible **YES (choppy)**; Viewer connection-loss noted after Hear.  
8. AmigaAMP stopped; candidate QUIT; classic restored; proto 5 SYSINFO ×2 PASS. No reboot.

## Stream metrics

| Field | Value |
|---|---|
| `audio_start` count | **1** |
| `audio_stop` count | **1** |
| Wall elapsed | **8.371 s** |
| Stop reason | `prefer_time_with_pcm` |
| PCM bytes | **531536** |
| Chunks / empty keepalives | **139** / 0 |
| Nonzero chunks | **138** |
| Rate | **47931** Hz |
| Peak abs observed | **7448** |
| Within hard / bytes | True / True |
| Second start refused | False |
| Hear final | False |
| End-marker | yes |
| Raw PCM in Git | **No** |

## Cleanup

| Check | Result |
|---|---|
| Hear OFF via normal path | PASS (watchdog `submit on=false`) |
| `audio_stop` + end-marker | PASS |
| No automatic restart | PASS (`audio_starts` remained 1) |
| `AudioContext.close()` | Source-verified in Viewer `stopHear`; no separate runtime probe |
| AmigaAMP stopped | Operator confirmed |

## Coverage after D5B

| Claim on `63db83ff…` | Status |
|---|---|
| D4 startup / TLS / SYSINFO | PASSED ON HARDWARE |
| D5 nonempty one-shot AUDIO | PASSED ON HARDWARE |
| D5B continuous stock Viewer Hear | **PASSED ON HARDWARE** |
| D5B Hear OFF + no restart | **PASSED ON HARDWARE** |
| D5B PC-audible | **YES (choppy)** |
| Stream / long soak / fidelity | NOT TESTED beyond this bounded session |
| POKE / TRACE / MMIO / monitor / HRTmon | NOT EXECUTED ON HARDWARE |

## Basic AUDIO regression closure note

For the hardened `63db83ff…` identity, basic AUDIO regression coverage can be considered **closed** for: oneshot nonempty capture + bounded stock Viewer continuous Hear with audible (choppy) PC playback. Remaining AUDIO work is soak/fidelity/device matrix and unrelated Stage 4 features (POKE/TRACE/etc.).

## Basic AUDIO regression closure (post-D5B)

**CLOSED** for hardened executable `63db83ff…` (D4 + D5 oneshot + D5B Viewer Hear).

Choppy PC playback and the operator-reported Viewer connection loss after Hear remain
**documented findings** from this session. They are **not** treated as release blockers
or as grounds for another AUDIO quality campaign unless a future authorised session
establishes a reproducible regression.

See `docs/APOLLO_V4_RELEASE_READINESS_AND_UPSTREAM_150.md`.
