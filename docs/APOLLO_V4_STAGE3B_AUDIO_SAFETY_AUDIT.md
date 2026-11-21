# Apollo V4 Stage 3B — AUDIO opcode 48 / Hear safety audit

**Status:** Offline preparation only — **no V4 AUDIO execution authorised by this document**  
**Docs parent tip:** `d28d263` (`validation/apollo-v4-evidence-prep`)  
**Fork `main`:** `79880b8` (unchanged)  
**Audit date:** 2026-11-21

## Architecture (end-to-end)

AUDIO does **not** sample Paula/SAGA custom registers. It **reads the in-RAM mix buffer** already maintained by the loaded `arne.audio` AHI driver (layout pinned to **arne.audio 4.22**), byte-swaps samples to **s16le stereo**, and returns them over the AmiGent command channel.

| Layer | Location | Role |
|-------|----------|------|
| Opcode | `CMD_AUDIO = 48` (proto 6); legacy 38 on advertised proto 5 | `amigentd.c`, `channel.py` |
| Capability | SYSINFO `audio=1` | Advertisement only — not proof of a live mix |
| Client one-shot | `AmigaChannel.audio(ms)` | Header y≤200; native **ignores ms**; returns one finished half |
| Client stream | `audio_start` / `audio_read` / `audio_stop` | arg 1 / chunks / arg 2; used by Viewer Hear |
| Dispatch | `chan_command` → `c_audio` or `c_audio_stream` | `#ifdef AMIGENT_APOLLO` |
| Native acquire | `arne_mix()` → driver private + audioctrl fields | `Forbid`/`FindName("arne.audio")` then RAM peeks |
| Convert | `copy_mix` / stream FIFO | Big-endian driver words → s16le |
| Viewer | `_media` / `_play_audio` | Separate TLS command channel; broadcasts binary msg 5 |
| MCP | `amiga_listen` | Repeated one-shots → WAV; checks `audio=1` |

```text
AHI program → arne.audio mix in chip RAM → amigentd peek/copy → opcode 48 framing → PC decode → Hear / amiga_listen
```

## Hardware resources accessed

| Resource | Access | Notes |
|----------|--------|-------|
| `arne.audio` library / private block / mix buffers | **Read** (RAM) | Version string must be `arne.audio 4.22`; `OpenCnt>0` |
| Custom registers `$DFFxxxx` (Paula / ARNE AUD / PIP) | **Not used by AUDIO** | Source forbids reading write-only ARNE/PIP regs; mix comes from driver RAM |
| DMA / interrupt vectors | **Not programmed** | Comments: hooking the driver interrupt locked the machine; polling only |
| Exec | `Forbid`/`Permit`, `FindName`, `TypeOfMem`, `CopyMem`, `SetTaskPri` (stream breathe) | Brief; no permanent hook |
| DOS | Optional **`T:audio-mem`** / **`T:audio-ptrs`** writes | Diagnostic dump after stream `audio_seq==4` / mix-ptr helper — **not** register MMIO |
| Chip / Fast RAM | Static `audio_fifo` 256 KiB + grains; one-shot `AllocVec(48000)` | Freed on one-shot path |

**Hardware writes / DMA / IRQ:** none on the AUDIO capture path. Residual **filesystem** side effects exist on the **stream** path only (`dump_mix`).

## Memory and protocol safety

| Topic | Finding |
|-------|---------|
| One-shot response | status byte + `u32 rate` + `u32 n` + `n` bytes; `n≤48000`, 4-byte aligned |
| Stream framing | After status 0: repeating `u32 rate`, `u32 len`, payload; `len=0` keepalive; `len=0xffffffff` end |
| Client chunk cap | `audio_read` rejects `size > 256*1024` |
| Stream FIFO | Power-of-two 256 KiB; drop-oldest when full |
| Bounds | Driver pointers gated by `TypeOfMem` / size windows (freq 8k–96k, frames, gap 64…256KiB) |
| Wrong driver version | `arne_mix` returns NULL → empty / quiet — no register fallback |
| Disconnect | Stream loop exits; `apollo_audio_release()` clears owner/FIFO |
| Concurrent AUDIO | `audio_owner` is **per process** — two daemons are **not** serialised |
| `ms` argument | Client clamps 0…200; native one-shot **`(void)ms`** — duration not enforced in C |

Malformed / empty / unsupported paths are covered offline by protocol + viewer tests (below). No evidence of unbounded native allocation on AUDIO (fixed caps).

## U-DAE vs F-DAE

| Item | U-DAE | F-DAE |
|------|-------|-------|
| Binary | 129844 / `456fce26…` | 131292 / `1e0e3f65…` |
| AUDIO source | `amiga/apollo/apollo_audio.c` @ `685309d` | Same AUDIO function set inside `apollo.c` on fork `main` |
| Function set | 30 AUDIO-related symbols | Superset: same AUDIO + PIP stubs (`apollo_pip` returns empty) |
| `arne.audio 4.22` / `T:audio-mem` / `T:audio-ptrs` in binary | Present | Present |
| PIP / AMMX packaging | Not the protected AUDIO unit | Extra stub / lineage — **not** AUDIO register I/O |

**AUDIO behaviour is shared lineage.** Distinct hashes still require separate rows if both are claimed HW-validated. First hardware AUDIO session should use **one** binary.

## Viewer Hear

- Enabled only when the page sends `{t:audio, on:true}` **and** SYSINFO `audio=1`.
- Requires Apollo opcode path (proto 6 → 48; advertised proto 5 → 38). Production 1.3 TLSONLY is **not** the Stage 3B candidate under test.
- Opens a **dedicated** command channel (`connect_audio`); uses TLS when `PLAIN_CLOSED`.
- Interprets chunks as s16le stereo; rejects `len % 4 != 0`; broadcasts `pcm_message(rate, pcm)` to the browser — **PC-local playback**.
- Does not persist WAV to disk in the viewer path; MCP `amiga_listen` builds in-memory WAV for the tool result only.
- Unsupported / lost connection: clears `hear`, closes link — no stream left open by design.
- `audio=1` alone does not imply non-empty PCM (quiet AHI → empty).

## Offline tests (software — not hardware)

```text
pytest tests/test_apollo_playback.py tests/test_protocol6_align.py tests/test_protocol5_compat.py
→ 26 passed
```

Covers opcode map, capability gating, TLS-only audio connect refusal, Hear start/stop, unsupported audio, odd frame length, empty mock responses. **Not** a substitute for V4 capture.

## Binary provenance (re-verified offline)

| ID | Size | SHA-256 | AUDIO content |
|----|-----:|---------|---------------|
| U-DAE | 129844 | `456fce26329612163d7012fa1526da9cb141f525ff5d8c3a5a6f817e016858b6` | `arne.audio` / `4.22` / `audio-mem` strings present |
| F-DAE | 131292 | `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` | same markers |

Do not rebuild for Stage 3B.

## Safety verdict

| Question | Answer |
|----------|--------|
| Register MMIO for AUDIO? | **No** |
| Persistent hardware state after QUIT? | **No** (driver unchanged; optional `T:` diagnostic files from stream dumps only) |
| Safe concurrent with production? | **No** — exclusive session (same as Stage 2B) |
| Safe bounded first test? | **Yes** — exclusive candidate + **one-shot** `audio(0)` |
| Stream / Hear residual? | May write `T:audio-mem` after ~4 captured halves; document; do not treat as MMIO |

**Conclusion for authorisation gate:** source supports a **bounded exclusive** Phase 1 one-shot on a verified Apollo daemon. Not safe as a concurrent add-on to production.

## Upstream 1.5.0

Private 1.5.0 AUDIO is unpublished. Do not claim Stage 3B results validate it. Re-diff `apollo_audio` / opcode 48 when public.

## Explicit non-claims

`audio=1` ≠ working Hear. Empty PCM ≠ failure if AHI is quiet. One daemon’s AUDIO pass ≠ the other binary. Stream dump files ≠ hardware validation of SAGA audio regs.
