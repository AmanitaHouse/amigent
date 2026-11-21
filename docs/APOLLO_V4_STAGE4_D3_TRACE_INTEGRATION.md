# Stage 4 — D3 POKE + Apollo TRACE combined integration

**Branch:** `review/stage4-d3-trace-integration`  
**Base:** fork `main` `d90d282…`  
**Mode:** Offline fork-local review — **NOT HARDWARE VALIDATED**

## Reviewable commits

1. D3 POKE resource harden (source + fixture + tests).  
2. Apollo TRACE fail-closed (source + client capability + tests).  
3. Combined native build, package pins, and this document.

Standalone review branches remain: `review/stage4-d3-poke-resource` (`edb200b`),  
`review/stage4-trace-failclosed` (`24084e3`).

## Combined Apollo executable

| Field | Value |
|-------|-------|
| Path | `src/amigent/amiga/bin/amigentd.apollo` |
| Size | 128308 |
| SHA-256 | `6765f090c4e92898c479cac36bb0021872f6c046238a3d7a670b906ae82c9f85` |
| Toolchain | ApolloCrossDev GCC-6.50-Stable, `-m68080 -DAMIGENT_APOLLO` |
| Status | **NOT HARDWARE VALIDATED** |

Includes both D3 POKE resource gates and Apollo TRACE set refusal strings.

Preserved HW identity: `tests/fixtures/amigentd.apollo.fforksafe-00443719` (`00443719…` / 129944 B).

Standalone D3-only (`077d997…`) and TRACE-only (`918ffd07…`) binaries are **not** packaged here.

## SUPERSEDED_APOLLO_SHA256

- `1e0e3f65…` (F-DAE)  
- `00443719…` (F-FORKSAFE)  

Unknown Apollo digests remain protected. Standalone experimental builds are not listed.

## IO_SECONDS note

`IO_SECONDS` (30) is a **per-WaitSelect progress timeout**, not a total-request deadline.  
Bounded refuses may still hold a channel while draining ≤64 KiB. Oversized declares close without drain.

## Recommended PR order (draft only — not published)

**Option A (preferred):** one security-hardening PR with the three commits above.  
**Option B:** PR1 D3 source → PR2 TRACE source → PR3 package update (depends on 1+2).

Do not merge without explicit authorisation. Hardware validation of `6765f090…` requires a separate GO.
