# Apollo V4 Stage 4 — Offline MMIO / monitor / HRTmon safety assessment

**Status:** Offline audit only — **no hardware executed**  
**Fork `main` reference:** `32ab6824d126c0018171183eb5b7a5c57b7e7445`  
**Docs branch:** `validation/apollo-v4-evidence-prep`  
**Prerequisite:** Stage 3B AUDIO closed — `docs/APOLLO_V4_STAGE3B_FINAL_SUMMARY.md`

`SYSINFO poke=0` is an ALLOWPOKE advertisement only. It is **not** live MMIO validation.

## Capability map

### 1. Read-only identification / inspection

| Item | Detail |
|------|--------|
| Source | `amigentd.c` `c_sysinfo`; Apollo detect in `apollo_detect.c` |
| Opcodes | **30** SYSINFO; also **38** LOADED, **40** TASKS |
| Entry | `AmigaChannel.sysinfo` / MCP status tools |
| Gates | Apollo fields in `AMIGENT_APOLLO` builds |
| Risk | Low |
| HW | Proto-6 SYSINFO smoke **PASSED** (Stages 2B/3B); does **not** prove MMIO/monitor/HRTmon |

### 2. Memory-reading (PEEK)

| Item | Detail |
|------|--------|
| Source | `amigentd.c` `peek_allowed` / `c_peek`; `apollo_mmio.c` `apollo_mmio_hit` |
| Opcode | **39** PEEK (protocol 6) |
| Entry | `channel.peek` / MCP `amiga_memory` |
| Address rules | 1…65536 B; no wrap; Kickstart `$F80000–$FFFFFF`; vectors `<$400`; else wholly inside one exec `MemHeader` |
| MMIO refuse | Any overlap with eight SAGA windows → fail **before** read |
| Windows | `$DFF1E6–E8`, `$DFF1EC–F0`, `$DFF1F4–F6`, `$DFF254–258`, `$DFF3B0–3C4`, `$DFF3D0–3E4`, `$DFF3EA–3FE`, `$DFF400–500` |
| Interruption | Forbid while walking MemList |
| Recovery | None if refused |
| Tests | `tests/test_protocol6_align.py` (host reimplementation + source asserts). Plan cites missing `tests/test_apollo_mmio.py` |
| HW | Live refuse (**D2**) **NOT_RUN** |

### 3. Memory-writing / execution-changing

| Op | Opcode / entry | Gates | Fail-safe | HW |
|----|----------------|-------|-----------|-----|
| **POKE** | **42** / `amiga_memory_write` | Protocol 6; **ALLOWPOKE**; no ROM; MMIO windows refused **even with ALLOWPOKE** | Yes — discard payload | **D3 NOT_RUN** (L4) |
| **TRACE** | **43** / `amiga_trace` | Protocol 6; other-process hunk | Disarm on clear/quit | **68080 not HW-claimed** |
| **TASKCTL** | **41** / `amiga_task` | Real task address | Unknown → fail | Not Stage 4 focus |

Client `feature_opcode` may expose POKE on proto 6 without checking `poke=1`; the **daemon** enforces ALLOWPOKE.

### 4. Monitor entry / exit

| Item | Detail |
|------|--------|
| Source | Daemon `MON_PORT` `"Amigent.monitor"`; tool `amigent-monitor.c` / packaged `amigent-monitor.apollo` |
| Opcodes | **37** NOTE; **47** QUIET |
| Entry | Monitor creates port under Forbid; **second instance refused** |
| Exit | Esc / close / Ctrl-C → RemPort, drain |
| Interruption | Drawing can contend for Intuition layer locks (QUIET exists for CPU/DRAG) |
| Recovery | Close monitor; QUIET 0 |
| HW | Apollo monitor (**D6**) **NOT_RUN** |

### 5. HRTmon (ApolloOS)

| Item | Detail |
|------|--------|
| Source | `src/amigent/hrtmon.py` `plan()`; MCP `amiga_hrtmon` |
| Opcode | **None** — `Which HRTmon` then optional `Run >NIL: HRTmon` |
| Gates | ApolloOS only; not already in SYSINFO tasks; on PATH |
| ROM | **Never** selected |
| Fail-safe | Plan returns `start=False` with text |
| Interruption | Program HRTmon takes console interaction |
| Recovery | Exit via HRTmon UI/keys |
| Tests | `test_hrtmon_never_selects_the_rom_monitor` |
| HW | **D7 NOT_RUN** (L4 approval) |

## Highest-priority remaining risks

1. **Live MMIO refuse unproven** — software windows ≠ V4 hardware proof.  
2. **ALLOWPOKE / POKE** — can crash or corrupt if misused; L4.  
3. **TRACE on 68080** — implemented, not hardware-claimed.  
4. **Monitor exclusivity / Intuition load** — shared `Amigent.monitor` port; drawing stalls.  
5. **HRTmon** — interactive takeover; ROM path correctly blocked in software only.  
6. **Upstream 1.5.0 still private** — no public branch/tag to re-diff against.

## Proposed next bounded hardware milestone (not authorised)

**Stage 4 Phase 1 — Live PEEK refuse into one protected SAGA window (plan D2).**

| Field | Proposal |
|-------|----------|
| Goal | Prove daemon refuses a PEEK that overlaps an Apollo MMIO window on real V4 |
| Candidate | Staged **F-FORKSAFE** `00443719…` (already HW-proven for AUDIO; contains `apollo_mmio`) — or U-DAE `456fce26…` if contribution-lineage preferred; **one** binary only |
| Provenance | Exact SHA-256 read-back before QUIT; size 129944 for F-FORKSAFE |
| Mode | Exclusive: QUIT production → launch `… TLSONLY` → test → QUIT → restore `C:amigentd TLSONLY` |
| ALLOWPOKE | **Off** |
| Max operations | ≤ **3** PEEK attempts into a single documented window (e.g. `$DFF3FC` length 2) + ≤ **2** control PEEKs of safe Kickstart/ROM or known RAM for contrast |
| Expected | Protected-window PEEK returns status fail / refuse text; **no** claimed register side effects; control PEEK may succeed |
| Stop conditions | Unexpected success reading a window; daemon hang; TLS loss; any POKE/TRACE/HRTmon/monitor launch; second daemon; ambiguity of restore |
| Console | Shell ready with restore command before QUIT |
| Evidence | SHA-256s, refuse texts, SYSINFO `poke=0`, pre/post production proto 5 SYSINFO ×2 |
| Out of scope | POKE, TRACE, monitor binary, HRTmon Run, AUDIO, PIP, install/update |

**Deferred (higher risk):** D3 POKE-with-ALLOWPOKE refuse; D6 monitor launch; D7 HRTmon program start — each needs separate approval.

## Upstream 1.5.0 public status (audit date 2026-11-21)

| Check | Result |
|-------|--------|
| Public branches | `main`, `feature/1.3.0`, `feature/screen-pause` — **no** `feature/1.5.0` |
| Tags / releases | Latest public **v1.4.0** |
| Related issue | `#40` documents multi-Amiga behaviour “before 1.5.0” (intent language, not a published tree) |
| Action | Retain existing reconciliation baseline; prepare a fresh comparison plan **only when** a public branch/tag appears — **do not** auto-rebase |

## Confirmation

This assessment does not modify fork `main`, protected contribution history, packaged binary bytes, or V4 production.
