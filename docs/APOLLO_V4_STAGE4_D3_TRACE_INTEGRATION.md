# Stage 4 — D3 POKE + Apollo TRACE combined integration

**Branch:** `review/stage4-d3-trace-integration`  
**Base:** fork `main` `d90d282…`  
**Mode:** Offline fork-local review — **NOT HARDWARE VALIDATED**

## Reviewable commits

1. D3 POKE resource harden (source + fixture + tests).  
2. Apollo TRACE fail-closed (source + client capability + tests).  
3. Combined native build / package.  
4. POKE payload wall-clock deadline + package refresh.

Standalone review branches remain: `review/stage4-d3-poke-resource` (`edb200b`),  
`review/stage4-trace-failclosed` (`24084e3`).

## Combined Apollo executable

| Field | Value |
|-------|-------|
| Path | `src/amigent/amiga/bin/amigentd.apollo` |
| Size | 128744 |
| SHA-256 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| Toolchain | ApolloCrossDev GCC-6.50-Stable, `-m68080 -DAMIGENT_APOLLO` |
| Status | **NOT HARDWARE VALIDATED** |
| Offline regression | **413 passed**, 5 skipped (`tests/` excluding `tests/native`) |

Includes D3 POKE resource gates, Apollo TRACE set refusal, and POKE payload wall-clock deadline.

Preserved HW identity: `tests/fixtures/amigentd.apollo.fforksafe-00443719` (`00443719…` / 129944 B).

Prior review-only binaries (`077d997…`, `918ffd07…`, `6765f090…`) are **not** packaged and are **not** hardware-validated.

## SUPERSEDED_APOLLO_SHA256

- `1e0e3f65…` (F-DAE)  
- `00443719…` (F-FORKSAFE)  

Unknown Apollo digests remain protected. Standalone experimental / intermediate review builds are not listed.

## POKE payload wall-clock deadline

Confirmed: `l_wait` / `l_recv` / `l_skip` restarted a full `IO_SECONDS` per fragment, so a
slow drip could extend a refused POKE indefinitely.

Fix: `POKE_DEADLINE_MS = IO_SECONDS * 1000` (**30 s** total wall-clock) from `now_ms()` at the
start of the bounded payload phase; `l_skip_until` / `l_recv_until` use remaining time and do
**not** reset on each fragment. Oversized declares still close without drain. Deadline
expiry or incomplete recv closes the channel (`FALSE`) so bytes are not read as the next command.

Maximum enforceable POKE payload duration: **30 seconds** wall-clock.

## Recommended PR order (draft only — not published)

**Option A (preferred):** one security-hardening PR with separately reviewable commits
(D3 → TRACE → package → deadline).  
**Option B:** PR1 D3 source → PR2 TRACE → PR3 package/deadline (depends on 1+2).

Do not merge without explicit authorisation. Hardware validation of `63db83ff…` requires a separate GO.
