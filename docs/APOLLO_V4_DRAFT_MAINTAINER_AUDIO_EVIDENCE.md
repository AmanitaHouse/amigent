# Draft — Maintainer-facing Apollo AUDIO hardware evidence

**Status:** Draft only — **not posted**. Do not open an upstream PR from this note.  
**Upstream `feature/1.5.0`:** unpublished at last audit; do not assume identity with these builds.

## What was shown on physical Apollo V4-SA

1. **Nonempty one-shot AUDIO** on the protected packaging-lineage daemon  
   SHA-256 `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6`  
   (1920 bytes s16le stereo @ ~47931 Hz with nonzero samples; production restored).

2. **Bounded PCM streaming** on a stream-safety candidate derived from that lineage after removing diagnostic `T:` dumps  
   SHA-256 `983fd8531ed7e8631a77daac09b9f660cd59137a106dcc8f93a58e760921dd2a`  
   (~7 s wall / ~941 KiB PCM / 246 chunks; explicit stop; production restored).

Streaming used the protocol-6 `audio_start` / chunk / `audio_stop` path under a supervised PC harness with hard duration and byte limits. AmigaAMP held `arne.audio` 4.22 on AHI unit 0.

## Why the diagnostic dump was removed

The stream path wrote `T:audio-mem` via `MODE_NEWFILE` once `audio_seq` reached 4 (`dump_mix`). A related `T:audio-ptrs` helper existed. Nothing in the daemon or client consumed those files. Removing the writes eliminates an unconditional overwrite of `T:` during Hear without changing opcode 48, framing, or mixer logic.

## Exact binary for streaming claims

Only `983fd853…` carries the Hear/stream hardware claim. Do not attribute streaming results to `456fce26…` (oneshot only) or the fork’s packaged `1e0e3f65…` (not stream-tested).

## Limitations

- Human-confirmed PC loudspeaker hearing: not confirmed in evidence.  
- Stock Viewer Hear UI button path: not tested (harness used the same opcodes).  
- Reference fidelity / long soak / F-DAE streaming: not tested.  
- Unpublished 1.5.0 tree: not compared live.
