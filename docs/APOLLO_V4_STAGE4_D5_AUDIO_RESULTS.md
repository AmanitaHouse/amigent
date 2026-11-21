# Apollo V4 — Stage 4 D5 AUDIO regression results

**Session:** Stage 4 D5 — one-shot AUDIO on security-hardened Apollo daemon  
**Evidence (private):** `~/amigent-evidence/stage4-d5-audio-regression/20261121T080724Z`  
**Mode:** Exclusive candidate launch; production restored  
**Conclusion:** **AUDIO request handled — capture unconfirmed (valid empty); production restored**

## Candidate identity

| Field | Value |
|---|---|
| Staged path | `Programs:AmiGent-Stage4/amigentd.d4` |
| Size | 128744 |
| SHA-256 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| Launch | `… amigentd.d4 TLSONLY` (no ALLOWPOKE) |
| Prior D4 | start / proto-6 TLS / SYSINFO / `poke=0` `trace=0` PASS |

Read-back before QUIT matched the frozen SHA-256. No rebuild / restage.

## What was authorised and done

Exactly one `AmigaChannel.audio(0)` (opcode 48, arg 0). No stream, Hear, PEEK/POKE/TRACE, install, or retry.

## Session sequence

1. Offline GO (reuse D4 identity; opcode-48 oneshot retained).  
2. Production preflight: proto 5 TLS, ApolloOS/68080, SYSINFO ×2; staged hash PASS; `arne.audio 4.22`.  
3. Physical-console handover → production QUIT → operator launched `.d4`.  
4. Proto-6 TLS smoke PASS (`audio=1`, `poke=0`, `trace=0`, `pip=0`).  
5. **Single** `audio(0)` — see below.  
6. Candidate QUIT → operator restored `C:amigentd TLSONLY`.  
7. Proto 5 TLS + SYSINFO ×2 PASS. No reboot.

## AUDIO result (exactly one request)

| Field | Value |
|---|---|
| Client | `AmigaChannel.audio(0)` |
| Request count | **1** |
| Elapsed | 0.013 s |
| Rate | 0 |
| Payload bytes | **0** |
| Framing | Valid empty (within 48000 bound) |
| Peak / RMS / nonzero | n/a (empty) |
| Stream / Hear | **Not used** |
| Retry | **None** |

**Interpretation:** Request handling on the hardened daemon succeeded. Capture of nonempty PCM was **not** demonstrated.

### Procedural defect

After candidate launch, the operator was **not** explicitly asked to start active AmigaAMP loop playback before `audio(0)`. SYSINFO `AmigaAMP PlayTask` presence was incorrectly treated as proof of an active mix. That does not establish audible playback. Under D5 rules there is **no** second AUDIO attempt.

## Production

Restored and verified: protocol **5**, certificate-verified TLS, ApolloOS / 68080, SYSINFO ×2. Production binary untouched.

## Coverage after D5

| Claim | Status |
|---|---|
| `63db83ff…` start / SYSINFO (D4) | PASSED ON HARDWARE |
| `63db83ff…` one-shot AUDIO request handling | PASSED (valid empty) |
| `63db83ff…` nonempty one-shot AUDIO capture | **NOT DEMONSTRATED** |
| Continuous AUDIO / Viewer Hear on this identity | NOT TESTED |
| POKE / TRACE refuse on this identity | NOT EXECUTED ON HARDWARE |

Historical nonempty capture on other executables (e.g. U-DAE / `00443719…` stream-safe) is **not** transferred to `63db83ff…`.

## Recommended next validation step (not authorised here)

One exclusive D5-remediation session: same `63db83ff…` candidate, **operator-confirmed active AmigaAMP loop after launch**, then exactly one `audio(0)` — still no stream/Hear/POKE/TRACE.
