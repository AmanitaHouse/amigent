# Apollo V4 Stage 3B — Viewer Hear hardware runbook

**Status:** **Executed** — see `docs/APOLLO_V4_STAGE3B_HEAR_RESULTS.md`  
**Candidate:** stream-safe U-DAE lineage build  
**SHA-256:** `983fd8531ed7e8631a77daac09b9f660cd59137a106dcc8f93a58e760921dd2a` (128496 B)  
**Source:** `contrib/apollo-audio-stream-safety` @ `1aa7265`  
**Safety:** `docs/APOLLO_V4_STAGE3B_HEAR_STREAM_SAFETY.md`  
**Do not** use historical U-DAE `456fce26…` for Hear (still contains `T:audio-mem` dump)

## Bounds (from protocol / client)

| Limit | Value | Source |
|-------|-------|--------|
| Max Hear wall time | **10 seconds** (operator stops earlier if OK) | Session policy |
| Client chunk size reject | `> 256 KiB` | `AmigaChannel.audio_read` |
| Daemon PCM per push | ≤ 4096 bytes (+ 8-byte header) | `apollo_audio_take` / `audio_push` |
| Approx max PCM @ 10 s | order **~1–2 MB** raw at ~48 kHz stereo (not a hard daemon cap; stop by wall clock) | Rate × 4 × t |
| Streams | Exactly **one** Hear on/off cycle | No retries |
| AUDIO oneshot during Hear session | **Forbidden** | Separate from Phase 2A |

## Preconditions

1. Physical AmigaOS Shell open and responsive (independent of AmiGent).  
2. Production proto **5** TLS health (SYSINFO ×2).  
3. PC production backup hash `b00fef0e…` verified.  
4. Candidate staged under a **new** path, e.g. `Programs:AmiGent-Stage3B/amigentd.hear` — read-back SHA-256 = `983fd853…`.  
5. Operator AHI source ready: AmigaAMP 2.18, AHI unit 0 ARNE HiFi; looped media that AmigaAMP can open (not the rejected MPEGA-incompatible WAV).  
6. Viewer on PC pointed at V4 TLS; Hear button appears only with `audio=1`.  
7. Restoration command rehearsed without depending on AmiGent:

```text
Run <NIL: >NIL: C:amigentd TLSONLY
```

## Sequence

### 1 — Stop production

`ADDRESS AMIGENT 'QUIT'` — confirm TLS 6802 refused.

### 2 — Launch candidate

```text
Run <NIL: >NIL: Programs:AmiGent-Stage3B/amigentd.hear TLSONLY
```

PC: certificate-validated TLS, **protocol 6**, ApolloOS, 68080, `audio=1`, SYSINFO responsive.  
**If smoke fails → restore production; do not Hear.**

### 3 — Start AHI source

Start AmigaAMP loop; confirm PlayTask / audible output as applicable.

### 4 — One bounded Hear

1. Open Viewer; click **Hear**.  
2. Confirm PC receives nonempty PCM chunks and local playback starts.  
3. At **≤ 10 s**, click Hear **off** (do not leave pressed — client may restart stream).  
4. Record: chunk count / approx bytes / whether audio was audible on PC.  
5. Do **not** retry on failure.

### 5 — Stop source; quit candidate

Stop AmigaAMP. ARexx QUIT candidate; TLS refused.

### 6 — Restore production

```text
Run <NIL: >NIL: C:amigentd TLSONLY
```

Verify proto 5 TLS, SYSINFO ×2. No reboot. Do not overwrite `C:amigentd`.

## Operator checklist

| Action | Owner |
|--------|-------|
| Shell ready; restore command available | Operator |
| Confirm QUIT / launch / restore observations while AmiGent offline | Operator ↔ Cursor chat |
| AmigaAMP start/stop | Operator |
| Hear on/off within 10 s | Operator |
| Capture PC metadata (no raw PCM in Git) | Cursor |

## Stop conditions

Candidate hash mismatch; console unavailable; ambiguous production stop; proto-6 smoke fail; unexpected audio/DOS behaviour; Hear timeout without stop; V4 unstable; restore uncertain.

No F-DAE Hear, no streaming beyond the single window, no automatic reboot.

## Pass criteria

- Proto-6 smoke of **this** binary PASS  
- Hear receives nonempty framed chunks with local PC playback  
- Hear stopped cleanly; candidate quit; production proto 5 restored  
- No `T:` diagnostic overwrite expected (binary lacks `audio-mem`)

## Explicitly not claimed by a pass

Waveform fidelity vs source; long-duration soak; F-DAE Hear; concurrent AUDIO; upstream 1.5.0.
