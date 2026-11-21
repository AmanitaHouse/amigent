# Apollo V4 — Stage 4 D5 AUDIO regression results

**Session:** Stage 4 D5 — one-shot AUDIO on security-hardened Apollo daemon  
**Remake evidence (private):** `~/amigent-evidence/stage4-d5-audio-remake/20261121T081528Z`  
**Prior valid-empty attempt:** `~/amigent-evidence/stage4-d5-audio-regression/20261121T080724Z`  
**Mode:** Exclusive candidate launch; production restored  
**Conclusion:** **APOLLO V4 STAGE 4 D5 AUDIO REGRESSION VALIDATED — PRODUCTION RESTORED**

## Candidate identity

| Field | Value |
|---|---|
| Staged path | `Programs:AmiGent-Stage4/amigentd.d4` |
| Size | 128744 |
| SHA-256 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| Launch | `… amigentd.d4 TLSONLY` (no ALLOWPOKE) |
| Prior D4 | start / proto-6 TLS / SYSINFO / `poke=0` `trace=0` PASS |

No rebuild / restage. Staged identity unchanged from D4.

## Authorised work

Exactly one `AmigaChannel.audio(0)` after **operator-confirmed** AmigaAMP loop playback.  
No stream, Hear, PEEK/POKE/TRACE, install, or AUDIO retry.

## Remake sequence (successful)

1. Operator ready → production QUIT → TLS released.  
2. Operator launched `.d4`.  
3. Proto-6 TLS smoke PASS.  
4. Operator confirmed **audio playing**.  
5. Single `audio(0)` — nonempty PCM with measurable signal.  
6. Candidate QUIT → TLS released.  
7. Operator restored classic; audio stopped.  
8. Proto 5 TLS + SYSINFO ×2 PASS. No reboot.

## AUDIO result (remake — exactly one request)

| Field | Value |
|---|---|
| Client | `AmigaChannel.audio(0)` |
| Request count | **1** |
| Elapsed | 0.018 s |
| Rate | **47931** |
| Payload bytes | **1920** |
| Frames (stereo) | **480** |
| Alignment | Multiple of 4; within 48000 |
| Peak abs (s16) | **23** |
| RMS | **9.12** |
| Nonzero frames | **466 / 480** |
| PCM SHA-256 (metadata only) | `858065561a49b7b7d3a14257f9de88acfd1cd22c0e6b3ef26b42b62b749ea2fa` |
| Raw PCM persisted | **No** |
| Stream / Hear | **Not used** |

**Interpretation:** Nonempty one-shot AHI capture with measurable signal on `63db83ff…` while AmigaAMP held the mix.

## Prior valid-empty attempt (same day)

First D5 attempt returned valid empty because `audio(0)` was issued without an explicit post-launch AmigaAMP play confirmation. That attempt remains recorded; it does **not** demonstrate nonempty capture. No retry was performed in that session.

## Production

Restored and verified: protocol **5**, certificate-verified TLS, ApolloOS / 68080, SYSINFO ×2. Production binary untouched.

## Coverage after D5 remake

| Claim | Status |
|---|---|
| `63db83ff…` start / SYSINFO (D4) | PASSED ON HARDWARE |
| `63db83ff…` nonempty one-shot AUDIO (D5 remake) | **PASSED ON HARDWARE** |
| Continuous AUDIO / Viewer Hear on this identity | NOT TESTED |
| POKE / TRACE refuse on this identity | NOT EXECUTED ON HARDWARE |

Historical stream-safe (`00443719…`) claims are **not** transferred beyond what D4/D5 explicitly show for `63db83ff…`.

## Recommended next validation step (not authorised here)

One exclusive continuous-AUDIO / stock Viewer Hear session on the same `63db83ff…` identity — still no POKE/TRACE/MMIO.
