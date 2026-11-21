# Apollo V4 Stage 4 D3 — Offline POKE safety and fail-closed audit

**Mode:** OFFLINE ONLY — **no V4 contact, no live POKE, no ALLOWPOKE on hardware**  
**Fork `main`:** `d90d282b5276f746da96504f0e70950764caa6d6`  
**Apollo candidate identity (unchanged):** `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` (129944 B)  
**D2 reconciliation baseline:** `f28e695e5373363a21133f77f0f62990d2978a8f`  
**D2 HW claim (do not expand):** three protected-window **PEEK** refuses only

## 1. Exact POKE source locations and protocol behaviour

| Layer | Location | Role |
|-------|----------|------|
| Opcode | Protocol 6 **CMD_POKE = 42** (`amigentd.c` command map; `channel.POKE`) | Wire command |
| Dispatch | `case CMD_POKE:` → `c_poke(l, x, (ULONG)w << 16 \| h)` | Length = `w:h` |
| Native write | `c_poke` → `CopyMem(data, (APTR)at, n)` under `Disable`/`Enable` + `CacheClearU` | **Only** physical write |
| Client | `AmigaChannel.poke` — `_need6`, size `1…PEEK_MAX`, hex address in name, payload after header | No SYSINFO `poke` check |
| Feature map | `feature_opcode(6, "POKE", …)` returns **42 even when `poke=0`** | Client may *send*; daemon must refuse |
| MCP | `amiga_memory_write` — resolves address, **peeks**, then `ctl.poke`; docs require ALLOWPOKE | Not a gate bypass |
| Advertise | SYSINFO `t_pair(&t, "poke", allow_poke)` | Mirror of startup flag |
| Enable | CLI `ALLOWPOKE/S` or WB tooltype `ALLOWPOKE` → `allow_poke = TRUE` | Startup only |

### Native order inside `c_poke` (Apollo build; post D3 resource harden)

1. Parse hex address (`c_address`) — no target write.  
2. **`!n || n > PEEK_MAX`** → `l_skip` + refuse (no AllocVec).  
3. **`if (!allow_poke)`** → `l_skip` + `c_fail("writing memory is off; … ALLOWPOKE …")` — **return** (no AllocVec).  
4. `AllocVec` + `l_recv` payload into a **temporary** buffer (not the target).  
5. **`apollo_mmio_hit(at, n)`** → `FreeVec` + same Apollo-registers refuse text as PEEK — **return**.  
6. **`!peek_allowed(at, n) || at >= 0xF80000`** → refuse (“only RAM exec manages…”); ROM never written.  
7. `mon_say("write memory")` (string only).  
8. **`CopyMem(data, (APTR)at, n)`** — first and only write to the requested address.

**Conclusion:** Prohibited/malformed paths that hit steps 2–3 never allocate; steps 5–6 never reach step 8. Packaged Apollo binary may still be pre-harden until a separately authorised rebuild. See D6/D7 review for resource closure detail.

## 2. ALLOWPOKE enforcement

| Check | Finding |
|-------|---------|
| Default | `allow_poke` false unless CLI/tooltype |
| Refuse without flag | Step 3 before MMIO and before `CopyMem` |
| TLS / auth | No assignment of `allow_poke` from TLS or session errors (startup only) |
| Client | May still emit opcode 42 on proto 6; **daemon** enforces |
| Protocol 5 | Client `_need6` blocks; no POKE on legacy map |

## 3. Protected MMIO write refusal

| Check | Finding |
|-------|---------|
| Same eight windows as PEEK | `apollo_mmio.c` shared `apollo_mmio_hit` |
| Even with ALLOWPOKE | Step 4 still refuses overlapping ranges |
| D2 addresses as writes | `$DFF3FC`/`$DFF1F4`/`$DFF400` (and overlaps) are hits |
| Wrap / `n==0` | `apollo_mmio_hit` returns TRUE → refuse before `CopyMem` |
| ROM | Explicit `at >= 0xF80000` refuse after gates |

## 4. Bypass / alignment / overflow risks

| Topic | Assessment |
|-------|------------|
| Client-only prevention | **Insufficient alone** — daemon gates are authoritative; client does not check `poke=1` |
| Overflow / wrap into allow | `apollo_mmio_hit` treats wrap as hit; `peek_allowed` rejects `end < at` |
| Alignment | No special align requirement; byte lengths 1…65536 |
| Partial target write on refuse | No — full `CopyMem` only after all gates; refuse frees temp buffer |
| Fallback after refuse | None in `c_poke` |
| MCP peek-then-poke | Peek can fail separately; does not enable writes if ALLOWPOKE off |
| Residual risk if ALLOWPOKE **on** | Any `peek_allowed` RAM can be corrupted — **high** operational risk |

No source bypass found that lets a prohibited Apollo POKE reach `CopyMem` when gates are compiled in (`AMIGENT_APOLLO`).

## 5. Offline tests

| Suite | Result |
|-------|--------|
| `tests/test_stage4_d3_poke_safety.py` | Focused fail-closed / order / MMIO / ROM / client / opcode / matrix |
| `tests/test_stage4_d2_mmio_safety.py` | D2 MMIO window consistency |
| `tests/test_stage4_d2_reconciliation.py` | Address-class claims; `POKE_ALLOWPOKE` remains `NOT_TESTED` |
| `tests/test_protocol6_align.py` + `test_protocol5_compat.py` | Protocol POKE/MMIO alignment |
| `tests/test_daemon_identity.py` | Packaged Apollo identity unchanged |

**Local run:** `51 passed` (focused D3 + D2 safety/reconciliation + protocol5/6 + daemon identity).

## 6. Future no-write hardware refusal test — meaningful?

**Yes, technically meaningful** (separate authorisation required):

- Candidate with **TLSONLY only** (no ALLOWPOKE): one POKE to a non-MMIO RAM-looking address → expect ALLOWPOKE-off refuse; prove **zero** lasting corruption via prior/after PEEK of a **test-owned** buffer *or* simply that refuse text returns and SYSINFO stays healthy.  
- Optionally (higher caution): session that starts with ALLOWPOKE **only if newly authorised**, then POKE into a **known MMIO window** → expect MMIO refuse without write — still a **negative** path.

This does **not** expand D2’s three-address PEEK claim.

## 7. Positive-path RAM write — safe enough to propose?

**Not currently safe enough to propose** under Stage 4 D2 address-class rules without a **new, dedicated design + explicit user authorisation**.

A future proposal would need, at minimum:

- Explicit `AllocMem`/`FreeMem` (or equivalent) **test-owned** buffer whose exact address/size/lifetime are verified in-session.  
- No ROM, vectors/`$4`, OS structures, registers, or foreign application memory (D2 lesson).  
- Pre-image capture, single write, verify, restore, free.  
- ALLOWPOKE only for that exclusive session; production never left with ALLOWPOKE.  
- Hard stop on any mismatch.

Until that design exists and is authorised: **do not propose a positive-path D3 hardware write.**

## 8. Recommended D3 status

| Gate | Status |
|------|--------|
| Offline fail-closed audit | **PASS** |
| Hardware D3 (any POKE / ALLOWPOKE on V4) | **NO-GO** — not authorised by this review; requires separate explicit user authorisation |
| Propose negative-path HW refuse later | Allowed as a *future* draft only after new auth |
| Propose positive-path HW write | **Not ready** |

**STAGE 4 D3 OFFLINE POKE SAFETY REVIEW COMPLETE**

## 9. Documentation commit SHA

`e6820074b01d85f943ba9de7e955dc386c17a31d` on `validation/apollo-v4-evidence-prep`

## 10. Production / main / binaries

| Artefact | Status |
|----------|--------|
| Fork `main` | Remains `d90d282b5276f746da96504f0e70950764caa6d6` — not advanced by D3 |
| Packaged Apollo daemon | Identity `00443719…` / 129944 B — **unchanged** |
| V4 production session | **Not contacted** |
| ALLOWPOKE on hardware | **Not enabled** |
| Live POKE | **Not executed** |
