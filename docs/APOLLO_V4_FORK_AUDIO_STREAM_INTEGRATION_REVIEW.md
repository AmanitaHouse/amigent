# Fork integration review — Apollo AUDIO streaming diagnostic dump removal

**Status:** Offline review complete — **ready to merge into fork `main` (not merged yet)**  
**Native review branch:** `review/fork-audio-stream-safety-main` @ `065c112`  
**Source lineage:** `contrib/fork-audio-stream-safety` @ `496f142` (same patch; cherry-picked onto `79880b8`)  
**Docs tip:** `validation/apollo-v4-evidence-prep` @ `f0b8953`  
**Fork `main`:** `79880b8` (unchanged)

## Suggested PR title

`fix(apollo): remove unsafe audio streaming diagnostic dumps`

## Suggested PR description

```text
## Summary
- Remove hardcoded `T:audio-mem` / `T:audio-ptrs` diagnostic overwrite paths from
  the fork Apollo AUDIO implementation (`dump_mix` / `apollo_mix_ptrs` writes).
- Keep opcode 48 framing, oneshot, stream claim/release, FIFO bounds, mixer,
  MMIO posture, AMMX, and PIP-disabled behaviour unchanged.
- Add software tests that assert the dump paths are absent and that client
  oneshot/stream framing bounds remain intact.

## Hardware evidence (already executed; not re-run here)
- Candidate binary SHA-256 `00443719…` (129944 B) built from this source.
- Oneshot nonempty PCM PASS (Phase 4).
- Supervised continuous stream PASS (Phase 5): 1× audio_start, 7.114 s,
  948352 B @ 47931 Hz; production proto 5 restored.
- Evidence: `~/amigent-evidence/stage3b-fork-stream/20261121T034526Z`

## Test plan
- [x] Full `pytest tests/` on review branch (352 passed, 4 skipped)
- [x] Packaging wheel retains protected F-DAE `1e0e3f65…` (131292 B)
- [ ] Maintainer review of exact diff (2 files only)
- [ ] Merge when authorised (do not force-push protected history)
```

## Exact source diff assessment

| Check | Result |
|-------|--------|
| Files changed vs `main` | **2 only:** `src/native/amiga/platform/apollo/apollo.c`, `tests/test_apollo_playback.py` |
| Diff nature | Delete `dump_follow` / `dump_mix`; stub `apollo_mix_ptrs` to clear counters only; drop unused DOS includes; add software tests |
| Protocol framing | **Unchanged** (no `amigentd.c` edits) |
| AUDIO opcode behaviour | **Unintentionally unchanged** (oneshot/stream paths untouched aside from removing dump call sites at `audio_seq == 4`) |
| AHI mixer / PCM conversion | **Preserved** |
| Buffer limits (`AUDIO_FIFO` 256 KiB, `GRAIN_MAX` 4096) | **Preserved** |
| Stream cancel / `claim`/`release` | **Preserved** (source) |
| Forbid/Permit + SetTaskPri restore | **Preserved** (path-balanced; not altered by this diff) |
| New file-write paths | **None** |
| MMIO protections | **Intact** (untouched) |
| AMMX / fork-specific code | **Intact** (untouched) |
| PIP | Remains advertised/`pip=0` posture; `apollo_pip` untouched |
| `src/native/` layout | **Intact** |
| Unrelated diff | **None** — focused cherry-pick onto `main` |

### Directly verified (source) vs hardware-demonstrated

| Property | Source-verified | Bounded HW demonstrated |
|----------|-----------------|-------------------------|
| No `T:audio-mem` / `T:audio-ptrs` Open | Yes | No writes observed in Phase 5 (not by creating those files) |
| Dump functions removed | Yes | N/A |
| Oneshot nonempty PCM | Software framing tests | Phase 4 PASS |
| Continuous stream + stop | Client framing tests | Phase 5 PASS (supervised harness) |
| No auto-restart | N/A (daemon) | Phase 5 harness: 1 start |
| Stock Viewer Hear UI | Separate review | **NOT TESTED ON HARDWARE** |
| Long soak / audible | No | No |

## Regression results

| Suite | Result |
|-------|--------|
| Full `pytest tests/` (review @ `065c112`) | **352 passed, 4 skipped, 0 failed** |
| `tests/test_apollo_playback.py` | 10 passed |
| Protocol 5/6 + align | 18 passed |
| Distribution / daemon selection / identity | 21 passed |
| Viewer | 20 passed |
| First full-run hygiene flake | `test_pycache_prefix…` failed once under `PYTHONDONTWRITEBYTECODE`; **passes** cleanly on main and review when re-run — **unrelated** to this change |

## Packaging verification

| Check | Result |
|-------|--------|
| `python -m build` (setuptools 84.2.1 venv) | wheel + sdist OK |
| Wheel Apollo daemon | `amigent/amiga/bin/amigentd.apollo` **131292** B / SHA-256 `1e0e3f65d46b62c93f7986d8137120ef5e2dec2515a9b63f6aa5909d2e75e9ca` |
| Matches matrix F-DAE | **Yes** |
| Diff replaces packaged binary | **No** |
| Unexpected package file changes | **None** attributable to this PR (source-only; packaged F-DAE bytes unchanged) |

## Binary identity / provenance

| Artifact | Role |
|----------|------|
| F-DAE packaged `1e0e3f65…` | Unchanged protected distribution binary (still contains dumps until a **separately authorised** rebuild) |
| HW candidate `00443719…` | Built from this corrected source; Stage 3B Phase 4/5 validated — **not** substituted into `amiga/bin/` by this PR |

Merging this PR updates **source** on `main`. Rebuilding/replacing the packaged Apollo daemon remains a separate authorised step.

## Known limitations

- Stock Viewer Hear UI still lacks session-wide duration/byte budgets and can auto-restart after a daemon end marker while Hear remains on — see `docs/APOLLO_V4_VIEWER_HEAR_UI_SAFETY.md`.
- Human-audible confirmation and long-duration soak remain open.
- Upstream 1.5.0 source not public; do not assume equivalence.

## Merge readiness

**Native fix is ready to merge** into fork `main` via PR from `review/fork-audio-stream-safety-main` (or `contrib/fork-audio-stream-safety`).

Do **not** combine Viewer lifecycle changes into this PR.

`.githooks/**` and `.gitattributes` are preserved (untouched). Protected historical contribution branches are not rewritten.
