# Stage 4 D2 — Evidence reconciliation (offline)

**Status:** RECONCILED  
**V4 contact during this note:** **None**  
**Evidence preserved:** `~/amigent-evidence/stage4-d2-mmio/20261121T060119Z`  
**Offline GO commit:** `1110a0d`  
**Results commit:** `6d077be2537a7561d3522ffebee9360a499a0d91`  
**Candidate:** `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` (129944 B)

Original evidence files, request logs and results are **not** rewritten. This document qualifies interpretation.

## A — What actually happened (preserved)

| Fact | Record |
|------|--------|
| Protected PEEKs | **3** — `$DFF3FC`/2, `$DFF1F4`/2, `$DFF400`/2 — all refused with native text |
| Control PEEKs | **2** — `$F80000`/4 and `$00000004`/4 — both returned 4 bytes |
| ALLOWPOKE | Off (`poke=0` on smoke) |
| POKE / TRACE / monitor / HRTmon / AUDIO | **0** |
| Production restore | Protocol **5** TLS; SYSINFO ×2 ApolloOS / 68080 |
| Abnormalities / reboot | **None** reported |

## B — Safety-gate discrepancy (controls)

### 1. What the original plan authorised

Optional controls: at most two PEEKs of **known-safe, demonstrably allocated RAM owned by the test** (or another **explicitly justified benign** target meeting that class).  
**Not** guessed RAM, hardware registers, or arbitrary “appears readable” addresses.  
If a control could not be proven as that class → omit it, or **NO-GO** if controls were required for interpretation.

### 2. What the offline review approved (incorrectly)

GO (`1110a0d`) listed:

- **D2-C1** `$F80000` width 4 — Kickstart **ROM** (`peek_allowed` ROM window)  
- **D2-C2** `$00000004` width 4 — **low-memory / vector** area (`end < 0x400`)

Neither is **test-owned allocated RAM**. Approving them as if they satisfied the original control class was an **offline GO error**.

### 3. What the hardware session executed

Exactly those five frozen operations (3 refuse + 2 controls). No extra PEEK/POKE.

### 4. What was directly observed

- Three refuse responses matching daemon string `that range includes Apollo registers that a read can change`.  
- Two successful 4-byte reads; daemon remained responsive; production restored.

### 5. What remains uncertain

- That `$F80000` / `$4` are “universally safe” on every ApolloOS configuration — **not** proven by one successful read.  
- Broader MMIO window coverage beyond the three addresses — **not** HW-tested.  
- POKE / TRACE / monitor / HRTmon — **not** tested.

### Address 4 (conventional AmigaOS use — source-backed)

Daemon comment in `peek_allowed` (`amigentd.c`):

```c
if (end < 0x400)  /* vectors and ExecBase at 4: chip RAM below exec's list */
    return TRUE;
```

On classic AmigaOS, absolute address **4** holds the **ExecBase** pointer (CPU exception/vector page in the low `$000`–`$3FF` region). The daemon explicitly allows PEEK wholly inside that region. That explains **why the daemon permitted** D2-C2 — it does **not** reclassify D2-C2 as “test-owned allocated RAM” under the original D2 authorisation.

Kickstart `$F80000+` is likewise an explicit **ROM** allow in the same function — again daemon-permitted, **not** test-owned RAM.

**Do not** describe D2-C1/C2 as compliant with the original control-address criteria.

## C — Protection coverage (bounded)

| Statement | Basis | Strength |
|-----------|--------|----------|
| Three protected addresses refused | Hardware-observed response text + widths match frozen list | **HW observed** |
| Refuse occurs before target `CopyMem` | Source order: `apollo_mmio_hit` → `c_fail` before `t_add` | **Source-verified** (not re-proven by a HW probe into the refuse path) |
| Responses from native daemon | Exact refuse string from `c_peek`; TLS proto-6 session | **HW + source** |
| Controls did not write | Session sent only PEEK; `poke=0`; no POKE opcode | **HW session log** |
| No extra PEEK/POKE | `peek-d2.json` five rows only | **HW session log** |
| Other five MMIO windows | — | **NOT TESTED ON HARDWARE** |

## D — Matrix interpretation

Use narrow fields (see updated `apollo_v4_matrix.json`).  
`live_MMIO` remains only as a **compatibility alias** meaning: **bounded D2 protected-window PEEK refusal on three addresses** — not full MMIO/POKE/monitor validation.

## E — Future GO gate (governance)

See updated Stage 4 assessment / runbook section: GO requires explicit match to the **user-authorised address class**; ROM/system-vector substitution for test-owned RAM without **new** authorisation → **mandatory NO-GO**.

## Conclusion of reconciliation

Protected-window PEEK refusal on the three named addresses remains **hardware-validated**.  
Control reads remain **executed but out-of-class** relative to the original authorisation.  
Production was restored and is not contacted by this offline note.
