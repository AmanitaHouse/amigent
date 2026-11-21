# Apollo V4 Stage 4 — D3 resource follow-up and D6/D7 monitor safety review

**Mode:** OFFLINE ONLY — **no V4 contact, no monitor launch, no HRTmon, no TRACE, no POKE**  
**Fork `main`:** `d90d282b5276f746da96504f0e70950764caa6d6`  
**Apollo candidate identity (unchanged):** `004437199347eb4479399002dbb6d45ae9cb0fda8d56b257bfe24b54d3b9676c` (129944 B)  
**D3 safety baseline:** `docs/APOLLO_V4_STAGE4_D3_POKE_SAFETY_REVIEW.md` (`e682007` / tip `314bf94`)  
**D3 hardware:** remains **NO-GO**

## A. Baseline ancestry

| Commit | Role |
|--------|------|
| `e6820074b01d85f943ba9de7e955dc386c17a31d` | D3 POKE fail-closed review + tests |
| `314bf9415fd73fd4363419d037c92ac2edb60b3b` | SHA note in D3 review |
| `d90d282…` | Fork `main` (unchanged) |

Evidence preserved; packaged Apollo bytes unchanged by this assessment.

---

## B. D3 resource-handling closure (`CMD_POKE` / `c_poke`)

### Pre-hardening findings (as of D3 review)

Prior order: parse address → **`AllocVec(n)`** → **`l_recv`** → ALLOWPOKE → MMIO → RAM → `CopyMem`.

| Question | Finding |
|----------|---------|
| 1. Payload length bound | **Gap:** client bounds 1…`PEEK_MAX` (65536); daemon accepted any `w:h` ULONG (`0…0xFFFFFFFF`) before AllocVec |
| 2. Overflow / signedness | `n` is `ULONG`; wrap into MMIO handled by `apollo_mmio_hit`; no signed length |
| 3. `AllocVec` failure | Handled: `l_skip` + `ERROR_NO_FREE_STORE` |
| 4. `l_recv` timeout | `IO_SECONDS` (30) per `WaitSelect` progress wait; failure → `FreeVec` + channel ends (`FALSE`) |
| 5. Unauthorised allocation / blocking | **Yes, residual:** ALLOWPOKE-off still allocated and received full `n` (DoS / memory pressure). Slow peer can block channel on `l_recv`/`l_skip` |
| 6. Rejected requests free temps | Yes when AllocVec succeeded; incomplete recv frees |
| 7. Earlier ALLOWPOKE gate | **Safe** if payload drained with `l_skip` (preserves framing); desync only if skip fails (channel closes) |

**Physical write:** still unreachable when ALLOWPOKE off / MMIO / non-RAM. Resource issue was allocation-before-refuse, not a write bypass.

### Hardening correction (source only)

`src/native/amiga/daemon/amigentd.c` `c_poke` now:

1. Parse address.  
2. Refuse `!n || n > PEEK_MAX` via **`l_skip` + fail** (no AllocVec).  
3. Refuse `!allow_poke` via **`l_skip` + fail** (no AllocVec).  
4. `AllocVec` / `l_recv` only when writes are authorised and sized.  
5. MMIO / RAM / ROM gates unchanged; `CopyMem` last.

| Artefact | Status |
|----------|--------|
| Source tree | Hardened as above |
| Packaged / candidate Apollo binary | **Unchanged** — does **not** include this fix until a separately authorised rebuild |
| Hardware validation inheritance | **None** — a rebuilt binary must not claim prior D2/D3 HW evidence |

### Moving the gate earlier — protocol note

Framing requires consuming the declared payload length. Early refuse + `l_skip` keeps the next 10-byte command header aligned. Incomplete skip returns `FALSE` and ends the channel process — fail-closed for sync errors.

---

## C. D6 — Standard monitor (`amigent-monitor` / `Amigent.monitor`)

| Topic | Evidence |
|-------|----------|
| Activation | Operator runs `amigent-monitor` (or packaged `amigent-monitor.apollo` on ApolloOS). **Not** entered by a daemon “enter monitor” opcode |
| Protocol | Daemon `mon_say` → `FindPort("Amigent.monitor")` → `PutMsg` (no reply). Opcodes **NOTE=37**, **QUIET=47** feed the port; absence of port = no-op |
| CPU / OS | Intuition 37+ Workbench tool; Apollo package may install 68080-built monitor binary; same port protocol |
| Exclusive | Second instance: `FindPort` under Forbid → refuse (“runs already”), rc 5 |
| Intuition / desktop | Opens pubscreen window; layer lock while drawing; QUIET pauses drawing so measurements are not stalled |
| Privilege / interrupts | User-mode Intuition app; no supervisor entry; no vector rewrite |
| Daemon responsive | Yes — monitor is a separate process; daemon only does FindPort/PutMsg |
| Shutdown block | Monitor exit does not require daemon; daemon quit does not require monitor. Drawing lock can delay Intuition until QUIET/close |
| Exit | Close gadget, Esc, Ctrl-C → RemPort, drain messages, CloseWindow |
| TLS disconnect | Monitor is local Amiga UI; TLS drop does not enter/exit monitor. Orphan messages freed on RemPort |
| Recovery | Close window / kill task; if unresponsive, physical console Close/Ctrl-C; RemPort clears port for a new instance |
| vs HRTmon | Log/UI observer only — **not** HRTmon / ROM debugger |

**Offline simulation:** port messaging and NOTE paths covered in host tests (`test_v13` notes); full Intuition window not simulated. No live D6 session in this review.

**HW recommendation:** **NO-GO** — launching the monitor is a live Intuition session with layer-lock side effects; no smaller “enter without entering” probe demonstrates D6 meaningfully beyond already-passed SYSINFO/NOTE-no-listener.

---

## D. D7 — HRTmon (ApolloOS program path)

| Check | Finding |
|-------|---------|
| 1. ApolloOS identify | `sysinfo` `os`; else `Version FULL exec.library` text contains `ApolloOS` |
| 2. Unsupported fail-closed | Non-ApolloOS → `plan(..., start=False)`; no `Run` |
| 3. Program vs ROM | `Run >NIL: HRTmon` only; docs/code state ROM unused |
| 4. ROM entry reachable? | **No** path in `hrtmon.plan` / `amiga_hrtmon` to ROM addresses or supervisor trampolines |
| 5. CPU / IRQ / memory | Depends on external **HRTmon program** behaviour — **not** controlled by Amigent source; treated as unknown / high uncertainty |
| 6. Operator exit | Screen/keyboard of that program (not remote-desktop friendly if it leaves Intuition) |
| 7. Failed / incomplete entry | Missing PATH / already running → no start; `Run` failures not deeply diagnosed |
| 8. Physical-console recovery | Likely required if HRTmon takes over input/display |
| 9. Daemon stop afterward | Daemon not the HRTmon process; stop via normal Amigent quit **if** OS still runnable |

ApolloOS presence ≠ proven safe HRTmon operation.

**HW recommendation:** **NO-GO**.

---

## E. TRACE / 68080

| Topic | Finding |
|-------|---------|
| Path | `CMD_TRACE=43` → `c_trace`: list/clear, or set TRAP `#15` (`0x4E4F`) in **other process** hunk; installs `trapstub` as `tc_TrapCode` |
| 68080 restriction | Source comment: stub is upstream 1.4.0; **behaviour on 68080 not validated on hardware** |
| Vectors | Per-task `tc_TrapCode`, not rewriting exception vector table directly |
| CPU state | Patches code word; Disable around arm; cache flush via `CacheClearU` / 030/040 supervisor helpers (`cpu_cache` from AFF_68020–060 — **no 68080-specific flush path**) |
| ApolloOS | No dedicated refuse; command remains available on Apollo builds |
| Tests | `test_trace_is_present_and_not_claimed_for_the_68080`; host describe_traces |
| Recommendation | **Fail-closed restriction recommended** for Apollo/68080 builds (refuse TRACE **set**; list/clear may remain) until a dedicated design + HW auth exists. **Not applied in packaged binary** in this change set — document-only recommendation unless a separate native patch is authorised |

**HW recommendation:** **NO-GO** (set or fire). List-only on a stock daemon still implies TRACE subsystem present; do not propose list-as-HW-proof without auth.

---

## F. Offline validation

See commit message / pytest run: D3 resource tests, D6/D7 monitor tests, protocol/daemon identity regressions. Packaged Apollo hash verified unchanged.

---

## G. Hardware risk classification

| Feature | Entry | Prerequisites | Destructive ops | Exit | Console recovery | HW evidence | Offline evidence | Uncertainty | HW GO/NO-GO |
|---------|-------|---------------|-----------------|------|------------------|-------------|------------------|-------------|-------------|
| **D6 monitor** | Run `amigent-monitor` | Intuition, free port | Layer locks; drawing load | Esc/close/Ctrl-C | Yes if hung | None | Source + packaging tests | Intuition stalls under load | **NO-GO** |
| **D7 HRTmon** | MCP `amiga_hrtmon` → `Run HRTmon` | ApolloOS, HRTmon on PATH | Unknown (external prog) | Program UI | Likely | None | `hrtmon.plan` fail-closed / ROM unused | Program behaviour on V4 | **NO-GO** |
| **TRACE** | Opcode 43 set | Proto 6, running target hunk | Code patch, trap handler, caches | Clear / `traces_off` on quit | If trap mishandled | None (explicitly unvalidated) | Source comments + tests | 68080 stub/cache | **NO-GO** |
| **D3 POKE refuse** | Opcode 42 | Proto 6 | None if refused | N/A | N/A | None | Fail-closed + resource harden (source) | Packaged bin pre-harden | **NO-GO** (HW still) |
| **D3 POKE write** | 42 + ALLOWPOKE | Explicit auth | RAM corrupt | N/A | Restore/reboot | None | Gates only | High if ALLOWPOKE on | **NO-GO** |

**Smallest safely observable related ops (already or offline-only):** SYSINFO; NOTE with no listener; packaged monitor **hash** check. None of these enter D6/D7 or arm TRACE. **No new hardware test proposed.**

---

## H. Status matrix (do not change past HW observations)

| Item | Status |
|------|--------|
| D2 bounded MMIO PEEK refuse (3 addresses) | **PASSED ON HARDWARE** |
| D3 POKE refusal | **PASSED OFFLINE ONLY** |
| D3 positive write | **NOT TESTED / NO-GO** |
| D6 monitor | **NOT TESTED ON HARDWARE** |
| D7 HRTmon | **NOT TESTED ON HARDWARE** |
| TRACE on 68080 | **NOT TESTED ON HARDWARE** |

---

## I. Recommended Stage 4 stance

| Gate | Status |
|------|--------|
| D3 resource follow-up | **PASS** (source hardened; packaged binary still pre-fix) |
| D6 / D7 / TRACE hardware | **NO-GO** |
| Propose bounded monitor HW test | **Not safe enough** — no non-entry probe proves D6; entry has Intuition risk |
| Prerequisites if ever proposed | Exclusive session; written GO gate; restore plan; physical console staffed; no concurrent AUDIO/PEEK stress; separate auth |

**STAGE 4 D3 RESOURCE REVIEW AND D6/D7 OFFLINE SAFETY ASSESSMENT COMPLETE**
