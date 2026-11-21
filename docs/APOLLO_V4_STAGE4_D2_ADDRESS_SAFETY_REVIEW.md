# Apollo V4 Stage 4 D2 — MMIO PEEK address safety review

**Decision: GO**  
**Date:** 2026-11-21  
**Fork `main` reference:** `d90d282b5276f746da96504f0e70950764caa6d6`  
**Docs branch:** `validation/apollo-v4-evidence-prep`  
**Hardware candidate:** `Programs:AmiGent-Stage3B/amigentd.forksafe`  
**Candidate size / SHA-256:** **129944** / `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c`

Offline only until this document’s frozen operation list is executed under Phase B. No POKE, TRACE, monitor, HRTmon, or AUDIO in D2.

## Source → binary provenance

| Item | Evidence |
|------|----------|
| Native MMIO | `src/native/amiga/platform/apollo/apollo_mmio.c` → `apollo_mmio_hit` |
| Native PEEK | `src/native/amiga/daemon/amigentd.c` → `c_peek` / `peek_allowed` / `CMD_PEEK` |
| Build gate | `#ifdef AMIGENT_APOLLO` wraps MMIO refuse in `c_peek` / `peek_allowed` / `c_poke` |
| Packaged Apollo (fork `main`) | 129944 / `00443719…` embeds big-endian window starts (verified offline) |
| Prior HW lineage | Same SHA passed Stage 3B AUDIO / Viewer Hear; MMIO refuse **not** previously HW-proven |

Client `AmigaChannel.peek` (`channel.py`) is protocol-6 only and size-bounded; **daemon-side refuse is mandatory** and is what D2 validates.

## Refusal path (native)

`CMD_PEEK` → `mon_say('C',"read memory",NULL)` (string only; **no** target dereference) → `c_peek`:

1. Parse hex address from request name (`c_name` / FreeVec) — no target read.  
2. **`apollo_mmio_hit(at, n)`** — if true → `c_fail(..., "that range includes Apollo registers that a read can change")` and **return**.  
3. `peek_allowed(at, n)` — also calls `apollo_mmio_hit` first; then Kickstart / low-vector / MemHeader walk under Forbid (**does not** read the requested address).  
4. Only then `t_add(&t, (const void *)at, n)` → `CopyMem` from the target.

**Conclusion:** For any range where `apollo_mmio_hit` is true, step 4 never runs. Refusal does not read the protected location. `c_fail` / `mon_say` only transmit literal strings.

### Eight deny windows `[start, end)`

| # | Start | End |
|---|-------|-----|
| 1 | `$DFF1E6` | `$DFF1E8` |
| 2 | `$DFF1EC` | `$DFF1F0` |
| 3 | `$DFF1F4` | `$DFF1F6` |
| 4 | `$DFF254` | `$DFF258` |
| 5 | `$DFF3B0` | `$DFF3C4` |
| 6 | `$DFF3D0` | `$DFF3E4` |
| 7 | `$DFF3EA` | `$DFF3FE` |
| 8 | `$DFF400` | `$DFF500` |

Wrap (`at+n < at`) or `n==0` → hit (refuse). Overlap is any shared byte.

## ALLOWPOKE

- D2 launch: `… amigentd.forksafe TLSONLY` — **no** `ALLOWPOKE`.  
- `c_poke` refuses without `allow_poke` **before** MMIO check; MMIO still refused even with ALLOWPOKE.  
- D2 sends **zero** POKE requests. No test helper writes memory or alters CPU/interrupt state.

## Frozen approved operations

| Test ID | Exact address | Width | Source window / basis | Expected | Native check | HW-read risk | Decision |
|---------|---------------|-------|----------------------|----------|--------------|--------------|----------|
| **D2-P1** | `0x00DFF3FC` | **2** | `$DFF3EA–$DFF3FE` (VREG_BOARD) | Refuse: Apollo-registers text, status 1 | `c_peek` → `apollo_mmio_hit` before `t_add` | None if refuse path holds | **APPROVED** |
| **D2-P2** | `0x00DFF1F4` | **2** | `$DFF1F4–$DFF1F6` (GFXMODE) | Same refuse | same | None if refuse path holds | **APPROVED** |
| **D2-P3** | `0x00DFF400` | **2** | `$DFF400–$DFF500` (ARNE page) | Same refuse | same | None if refuse path holds | **APPROVED** |
| **D2-C1** | `0x00F80000` | **4** | Kickstart ROM (`peek_allowed` ROM gate) | Success: 4 bytes | `peek_allowed` ROM true; no MMIO hit | ROM read only | **APPROVED** |
| **D2-C2** | `0x00000004` | **4** | Vectors (`end < 0x400`) | Success: 4 bytes | `peek_allowed` low-vector gate | Vector read only | **APPROVED** |

Maximum: **3** protected + **2** control PEEKs. Each once. No retries. No other addresses.

### Expected refuse text (protected)

`that range includes Apollo registers that a read can change`

## Offline tests

| Suite | Result |
|-------|--------|
| `tests/test_stage4_d2_mmio_safety.py` | **PASS** (D2 addresses, refuse-before-`t_add`, windows, wrap, POKE gates, binary window constants) |
| `tests/test_protocol6_align.py` (MMIO overlap) | **PASS** (prior + still applicable) |

## GO criteria checklist

1. Each protected address reviewed individually — **YES**  
2. Conclusive refuse before hardware read — **YES** (`apollo_mmio_hit` before `t_add`)  
3. No undefined/side-effect path for approved cases — **YES**  
4. Control addresses independently justified — **YES** (ROM + vector gates in `peek_allowed`)  
5. Relevant regressions pass — **YES**  
6. Exact daemon provenance — **YES** (`00443719…` / 129944; windows embedded)  
7. No write/ALLOWPOKE/config change — **YES**  
8. Physical-console recovery applicable — **YES** (Stage 3B procedure)

## Uncertainties (do not expand scope)

- Live V4 MemHeader layout not required for MMIO refuse (refuse precedes MemHeader).  
- `mon_say` “read memory” may appear even when refuse follows; it does not read the target.  
- This GO does **not** validate POKE, TRACE, monitor, or HRTmon.

## Decision

**GO — frozen list above only.**

Proceed to Phase B only with live operator console handover. If preflight or smoke fails: restore production; do not send PEEK.
