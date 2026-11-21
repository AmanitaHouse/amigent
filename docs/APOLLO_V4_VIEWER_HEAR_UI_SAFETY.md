# Stock Viewer Hear UI — safety review (offline)

**Status:** Offline review — **stock Viewer still needs a separate safety correction before HW UI validation**  
**Scope:** `src/amigent/viewer.py`, `src/amigent/web/viewer.js` on fork `main` (`79880b8`)  
**Does not** modify the native diagnostic-dump fix PR.

## Findings (stock implementation)

| # | Question | Finding |
|---|----------|---------|
| 1 | Hear OFF always stops active stream? | **Mostly yes.** Page `stopHear(true)` sends `{t:"audio",on:false}`; `_play_audio` exits when `not _hearing()` then `_release_audio` (`audio_stop` + drain + close). |
| 2 | Can `_media` restart after Hear OFF? | **No** while `hear` is False. **Yes** if Hear stays ON and the daemon ends the stream: `_play_audio` returns early (`if self._hearing(): return`) and `_media` immediately calls `_play_audio` again → **another `audio_start`**. |
| 3 | Closing Viewer stops streaming? | **Yes.** `leave` clears `hear` when last client goes; `_watching()` false path releases audio. |
| 4 | TLS errors → reconnect / repeated starts? | Exception in `_play_audio` → `_drop_audio` sets `hear=False` and closes. **Does not** clear-text fallthrough (`connect_audio` TLS failure stays a failure). User must click Hear again. |
| 5 | Client cancellation bounded cleanup? | `_release_audio` drains `audio_read` in an **unbounded** loop (no time/byte budget on drain). |
| 6 | Independent timeout stops stream? | **No** wall-clock or prefer/hard stop in stock Viewer. |
| 7 | Aggregate PCM global bound? | **No** PC-side aggregate budget; browser worklet ring is ~8 s @ 48 kHz and drops oldest when full. |
| 8 | PC playback device released? | `stopHear` disconnects the worklet node and clears queue; **`AudioContext` is not closed**. |
| 9 | Errors surfaced clearly? | Server sets `hear=False` and emits `audio on=false`; page UI relies on button state — limited error text. |
| 10 | Explicit user action before restart after failure? | After `_drop_audio` / offline: **yes**. After daemon end-marker with Hear still pressed: **no** (automatic restart). |

## Simulated / offline tests

See `tests/test_viewer_hear_lifecycle.py` on branch `contrib/viewer-hear-ui-safety` (or validation evidence copy):

- Hear OFF triggers stop/release.
- Daemon end-marker while Hear remains ON causes a second `_play_audio` → second `audio_start` when driven like `_media`.
- TLS/`AmigaError` path clears `hear` via `_drop_audio`.
- Last client leave clears `hear`.

These are **software** proofs of lifecycle behaviour — not hardware evidence.

## Separate correction proposal (do not fold into native dump fix)

**Suggested title:** `fix(viewer): bound Hear streaming and prevent silent restart`

**Minimum changes:**

1. On daemon end-marker, clear `hear` (or require explicit re-click) — do not return to `_media` with Hear still on.
2. Session-wide prefer/hard duration and aggregate PCM budget for Hear (mirroring supervised harness: e.g. prefer ≤7–8 s optional UI, hard ≤10 s / ≤2 MiB for safety sessions; product defaults TBD).
3. Bound `_release_audio` drain (max reads / timeout).
4. On Hear OFF / leave: disconnect worklet **and** close/suspend `AudioContext` reliably.
5. Surface stream errors to the page.

Keep native daemon dump removal in its own PR.

## Minimum future stock UI hardware test

Exclusive session on corrected fork binary `00443719…` (or rebuilt main binary after merge+rebuild auth):

1. Proto-6 smoke; AmigaAMP playing; PlayTask confirmed.
2. Open stock Viewer; click Hear **once**.
3. Confirm nonempty PCM / local playback path.
4. At ≤10 s click Hear OFF; confirm **exactly one** `audio_start` for the session (instrument or daemon-side observation).
5. Confirm no automatic restart after OFF.
6. Optional: force disconnect / TLS error and confirm Hear stays off until user clicks again.
7. QUIT candidate; restore production; SYSINFO ×2.

Do **not** treat Phase 5 supervised-harness success as this UI test.

## Claim boundary

| Capability | Status |
|------------|--------|
| Supervised harness streaming (F-FORKSAFE) | PASSED ON HARDWARE |
| Stock Viewer Hear UI | **NOT TESTED ON HARDWARE** |
| Human-confirmed audible | **NOT CONFIRMED** |
