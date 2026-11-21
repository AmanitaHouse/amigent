# Apollo V4 Stage 3B — Viewer Hear / streaming safety

**Status:** Offline hardening complete — **no V4 Hear session authorised**  
**Preserves Phase 2A:** nonempty one-shot capture on U-DAE `456fce26…`  
**Correction branch:** `contrib/apollo-audio-stream-safety` @ `1aa7265` (parent `685309d`)  
**Fork `main`:** `79880b8` (unchanged)  
**Evidence (private):** `~/amigent-evidence/stage3b-hear-stream-safety/20261121T031024Z`

## 1. `T:audio-mem` cause and effect

| Item | Finding |
|------|---------|
| Location | `amiga/apollo/apollo_audio.c` — `dump_mix()` via `remember_half` / `watch_wide` |
| Trigger | After successful stream half capture increments `audio_seq` to **4** |
| API | `Open("T:audio-mem", MODE_NEWFILE)` — creates/replaces file |
| Content | Raw 504-byte driver private + 256-byte audioctrl + pointer peeks (`dump_follow`) |
| Consumers | **None** in daemon, client, Viewer, or tests — write-only diagnostic |
| Runtime dependency | None — FIFO/PCM path does not read the file |
| Also present | `apollo_mix_ptrs()` wrote `T:audio-ptrs` (`MODE_NEWFILE`); **never called** from `amigentd.c` |
| One-shot | `apollo_audio()` does **not** call `dump_mix` (Phase 1/2A unaffected) |

## 2. Correction applied

Removed `dump_follow`, `dump_mix`, and both `audio_seq == 4` call sites.  
`apollo_mix_ptrs()` retained as a public stub that only clears `mix_ptr_n` (no DOS write).  
Removed unused `proto/dos.h` / `dos/dos.h` includes from `apollo_audio.c`.

**Not changed:** opcode 48, framing, PCM s16le, AHI/`arne.audio` mixer logic, claim/release, FIFO sizing.

Historical packaged U-DAE `456fce26…` and F-DAE `1e0e3f65…` were **not** overwritten.

## 3. New candidate (distinct binary)

| Field | Value |
|-------|-------|
| Source commit | `1aa726578f3c762ec41a06299f82b21873e2113a` |
| Toolchain | ApolloCrossDev **GCC-6.50-Stable** `m68k-amigaos-gcc` |
| Flags | `-m68080 -DAMIGENT_APOLLO -O2 -nostartfiles -nostdlib` (`Makefile.apollo`) |
| Size | **128496** bytes |
| SHA-256 | `983fd8531ed7e8631a77daac09b9f660cd59137a106dcc8f93a58e760921dd2a` |
| Strings | `arne.audio` present; `audio-mem` / `audio-ptrs` **absent** |
| Build path | `build/apollo/amigentd.apollo` (not packaged into `src/amigent/amiga/bin/`) |

This build requires its **own** protocol-6 smoke on hardware before Hear is claimed validated.

## 4. Stream lifecycle (source audit)

| Check | Result |
|-------|--------|
| Claim failure | `c_audio_stream` fails closed if owner busy; no partial task |
| FIFO | Fixed `AUDIO_FIFO` 256 KiB; drops oldest on overflow |
| Chunk send | Daemon max take 4096 PCM + 8 header; client rejects `size > 256 KiB` |
| Forbid/Permit | Balanced in `apollo_audio_claim` / `release` |
| Task priority | `audio_follow` saves `pri`, restores on exit; `apollo_audio_breathe` −1→0 |
| Stop (arg 2) | Sends end marker `0xffffffff`, then `apollo_audio_release` |
| Disconnect / error | Loop exits → `release`; CTRL-C watched |
| Idle end | ~600 ms without new halves ends follow loop |
| QUIT | Tears down links; no persistent capture task beyond channel process |
| File side effects after fix | **None** on normal Hear stream |
| `arne.audio` ownership | OpenCnt still held by AHI clients (e.g. AmigaAMP); daemon only reads mix RAM |

One-shot success does **not** prove stream cleanup; cleanup is established from this source review + offline tests.

## 5. Viewer Hear behaviour

| Step | Behaviour |
|------|-----------|
| Offer | Hear button only if SYSINFO `audio=1` |
| Start | Page `audio on` → `_play_audio` → TLS `connect_audio` → `audio_start` (arg 1) |
| Chunks | `audio_read`; empty keepalives skipped; odd length raises |
| Playback | Browser AudioWorklet; local only |
| Stop | Page `audio off` → `audio_stop` + drain + close |
| Offline / capability loss | `stopHear`; `_audio_ready` clears `hear` |
| Error / TLS fail | `_drop_audio` sets `hear=False` — **no** cleartext retry |
| Auto-restart | If Hear stays **on** after daemon ends stream, `_media` may call `_play_audio` again |

**Hardware bound implication:** operator must turn Hear **off** within the authorised window; do not leave Hear pressed after stop.

## 6. Offline tests

| Suite | Result |
|-------|--------|
| `tests/test_apollo_audio.py` (+ diagnostic-file / chunk / oneshot tests) on correction branch | **PASS** |
| `tests/test_apollo_packaging.py`, foundation, mmio on correction branch | **PASS** (packaged U-DAE hash unchanged) |
| `tests/test_apollo_playback.py`, `tests/test_protocol6_align.py` on docs branch / current client | **23 passed** |

Software only — not hardware validation.

## 7. Remaining blockers before Hear HW

None for diagnostic overwrite. Still required at authorisation time:

- Exclusive QUIT → stage **new** candidate → smoke → short Hear → restore  
- Operator AHI source (AmigaAMP / ARNE unit 0 proven in Phase 2A)  
- Explicit max Hear duration and PC playback check  
- Renewed proto-6 smoke of `983fd853…` (not inherited from `456fce26…`)

Fork `main` `src/native/.../apollo.c` still contains the old dumps if that tree is rebuilt — out of scope for this U-DAE-lineage candidate; do not conflate with F-DAE.
