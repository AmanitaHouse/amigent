# Apollo V4 Stage 3B Phase 2 — Nonempty capture & Hear preparation

**Status:** Offline preparation only — **no V4 contact authorised**  
**Preserves Phase 1:** valid-empty `audio(0)` on U-DAE (`docs/APOLLO_V4_STAGE3B_AUDIO_PHASE1_RESULTS.md`) — do **not** rewrite that as nonempty capture  
**Parent tip:** `62fa1a5` · Fork `main`: `79880b8`

## 1. Why Phase 1 returned `rate=0`, `n=0`

### Facts (source @ `685309d` / U-DAE)

One-shot path: `CMD_AUDIO` arg 0 → `c_audio` → `apollo_audio(buf, 48000, &rate, ms)`.

`apollo_audio` always starts with `*rate = 0`, then:

| Condition | Result |
|-----------|--------|
| `cap < 4` | return 0 |
| `arne_mix(...)` returns NULL **or** `n < 4` | return 0 |
| Same half as previous oneshot (`hold == seen_hold && index == seen_index`) | `*rate = 0`; return 0 |
| Else | `copy_mix` → nonempty s16le; `*rate` = driver mix frequency |

`arne_mix` returns NULL when any of:

- `arne.audio` not in `LibList`, or `lib_OpenCnt == 0` (driver not open / no AHI client holding it)
- IdString not exactly **`arne.audio 4.22`**
- Resident / seglist / private / audioctrl pointer checks fail (`audio_why` 3…11)
- Frequency / frames / half-buffer span out of allowed windows

`ms` is **ignored** (`(void)ms`). Empty is a **successful** framed answer (status 0, length 0), not a protocol error.

### Interpretation of Phase 1 HW observation

**Most likely (hypothesis, fits facts):** no usable open `arne.audio` 4.22 mix was present — quiet Workbench / no AHI program holding the driver, **or** mix half not yet / no longer readable under the layout checks.

**Also possible:** wrong/newer `arne.audio` version than 4.22 → hard fail to NULL.

**Unlikely for first oneshot after fresh U-DAE start:** `seen_hold` dedup (statics start zero; first distinct half should pass).

**Not established:** that Paula-only or non-AHI playback can fill this buffer. Source only reads **arne.audio** driver RAM.

## 2. AHI mixer requirements

| Requirement | Detail |
|-------------|--------|
| Driver | Loaded library name `arne.audio`, id **`arne.audio 4.22`** |
| Open | `lib_OpenCnt > 0` — an AHI client must have the unit open |
| Path | AHI mix → chip double-buffer halves; daemon copies the **finished** half |
| Not used | Paula/$DFF audio regs, non-AHI players that never open arne |
| After stop | If OpenCnt drops to 0 or halves go invalid → oneshot returns empty again |

## 3. Controlled Amiga-side source (recommendation)

**Preferred (no install):** operator starts an **already installed** AHI-capable player (mod/tracker/sample player configured for **AHI / arne**), playing a **short, original / operator-owned** loop or tone. Confirm audibly on V4 speakers/headphones before the AmiGent request.

**Not preferred without inventory proof:** “any Amiga sound” (Paula copper lists, games that bypass AHI).

**If no AHI tool exists on the machine:** prepare offline a tiny AHI tone tool (source only; **do not install in this prep**). Execution would need separate auth + transfer. Out of scope until nonempty capture with an existing tool is attempted or inventory shows none.

**Operator control:** start playback at Shell/Workbench; stop after the AmiGent oneshot; no User-Startup change; no mic/private audio.

## 4. Test 1 — Nonempty one-shot (recommended next live)

**Feasible:** Yes — same U-DAE + `audio(0)` while AHI mix is live; no streaming.

**Scope (exclusive, Stage 2B-style):**

1. Preflight proto 5 / hashes / Shell.  
2. Operator starts approved AHI source; confirms audible output.  
3. QUIT production → launch staged U-DAE `TLSONLY`.  
4. Proto 6 + `audio=1`.  
5. **Exactly one** `audio(0)`.  
6. Expect: `rate` in 8000…96000, `n ≥ 4`, `n % 4 == 0`, `n ≤ 48000`; record rate, n, PCM SHA-256 only (no raw commit).  
7. Optional: stop AHI source; **no** second AUDIO unless separately authorised.  
8. QUIT U-DAE → restore `C:amigentd TLSONLY` → proto 5 ×2 SYSINFO.

**Pass criteria:** nonempty structurally valid PCM + restore. Consistency with a synthetic tone is **best-effort** (spectrum/amplitude notes); do not require bit-exact match without a calibrated generator.

**Does not validate:** Hear, stream, F-DAE, fidelity listening on PC.

## 5. Test 2 — Viewer Hear (separate authorisation)

### Behaviour (facts)

| Item | Behaviour |
|------|-----------|
| Enable | Page `{t:audio,on:true}` + SYSINFO `audio=1` |
| Wire | **Stream:** `audio_start` (arg 1) → `audio_read` loop → `audio_stop` (arg 2) |
| One-shot | **Not** used by Hear |
| Channel | Dedicated TLS command channel (`connect_audio`) |
| PC | Broadcasts binary msg 5 (`pcm_message`); browser plays locally |
| Cancel | `hear=false` → stop + drain + close |

### Streaming residual — `T:audio-mem`

| Question | Finding |
|----------|---------|
| Trigger | After `audio_seq` reaches **4** in `remember_half` / `watch_wide` (successful stream captures) |
| In U-DAE binary | **Yes** (`audio-mem` string present) |
| Avoid by short Hear? | **No** for any useful Hear window — ~4 halves ≈ tens of ms; Hear of 1–2 s will hit it |
| Overwrite | `Open(..., MODE_NEWFILE)` — replaces `T:audio-mem` once (`static done`) |
| Size | Order of ~1–few×10 KiB (504+256 private/ctrl + pointer peeks) |
| Priority | `apollo_audio_breathe` toggles task pri −1→0 during stream |
| Cancel / disconnect | `apollo_audio_release` on stream exit; QUIT tears down channels |
| After QUIT | No persistent capture task; `T:audio-mem` may remain on RAM:T until reboot/delete |

**Hear HW verdict:** Not MMIO-blocked. Safe enough for a **short, exclusive** session **only if** the operator accepts the one-time `T:audio-mem` diagnostic write and exclusive QUIT/restore rules. Still **separate** from Test 1 — do not auto-chain.

## 6. Offline tests

```text
pytest tests/test_apollo_playback.py tests/test_protocol6_align.py
→ 22 passed (+ focused nonempty PCM contract test if added)
```

Software only — not hardware evidence.

## 7. Recommended next live authorisation

**Minimum next session:** Test 1 only (nonempty oneshot + controlled AHI source).

Hear: prepared; authorise later after nonempty capture exists (or explicitly instead, accepting stream residual).

## 8. Upstream 1.5.0

Unpublished. Results apply only to U-DAE `456fce26…` / current fork sources. No PR changes.

## 9. Authorisation needed for next V4 session

- Exclusive production interruption + U-DAE launch/restore (as Stage 2B/3B.1).  
- Operator-approved **AHI** playback source running during the single `audio(0)`.  
- Exactly one AUDIO request; metadata-only PCM evidence.  
- **Not** included unless separately named: Hear/stream, F-DAE AUDIO, install of new tone tool, reboot.
