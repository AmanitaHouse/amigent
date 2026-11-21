# Maintainer three Apollo V4 requests — evidence status

**Date:** 2026-11-21  
**Scope:** Offline source review + existing HW evidence. **No** new V4 session, production change, PR, merge, or upstream comment.  
**1.5.0 public tip:** `upstream/feature/1.5.0` @ `651a357b6aae8800c314799347b257e9884e2773`  
**Fork main:** `fad6693…` · **Public main:** `f6aab1d…`  
**HW candidate (prior):** `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` (128744 B)  
**Production (unchanged):** `b00fef0e5279dec6c8496371a62eabe51c3297f1e280e6b3d1dd07eb525cb2d3`

---

## Summary table

| Maintainer request | Status | Actual evidence | Remaining requirement |
|---|---|---|---|
| Native build + `regress.py` | **BLOCKED** (HW) / offline READY for safe subset | Script inspected on 1.5.0; safe `--only` subset prepared; full script has UI/RISK/INST checks; `63db83ff…` is prior D4/D5/D5B identity, **not** a regress run | Authorised exclusive candidate session; run safe subset; do **not** claim D4–D5B as full regress |
| `amiga_status` / `amiga_cpu` / FPU | **PARTIAL** | CPU 68080 confirmed on HW via SYSINFO/probes; `attn_flags=42111` archived; 1.5.0 FPU logic inspected offline (bit 10 ≠ FPU); **no** live `amiga_status`/`amiga_cpu` verbatim outputs under 1.5.0 host tools | Authorised read-only session with **1.5.0 PC tools** + candidate/production SYSINFO; capture verbatim JSON/text |
| `amigent-setup --update` | **OFFLINE ONLY** / live **NO-GO** until separate auth | 1.5.0 updater path reviewed; offline selection/replacement tests **40 passed / 4 skipped**; **no** live V4 `--update` ever run; 1.5.0 package has **no** `amigentd.apollo` | Separate live-update authorisation; full backup inventory; policy for replacing installed Apollo 1.4.0 with packaged classic 1.5.0 |

---

## A. PR #10 relevance verdict

**NO NEW UPSTREAM PR for #10.**

| Contract | Fork #10 (`4924da4`) | Public 1.5.0 detect |
|---|---|---|
| ApolloOS | IdString **or** (exec≥51 ∧ bit10) **or** `$DFF3FC` board id | exec≥51 ∧ `AFF_68080` (bit 10) only |
| Bit name | `AFF_FPGA` | `AFF_68080` (same bit) |
| Probe prints `68080` | yes | no (prints OS only) |
| Exit 0 | ApolloOS ∧ bit | ApolloOS (= exec≥51 ∧ bit) |
| `$DFF3FC` as OS fallback | yes (undesired) | **removed** (reporting-only `apollo_board`) |

Useful leftover from #10: optional informational `68080` probe line — unused by 1.5.0 `setup.py`. Negative-path / `$DFF3FC` behaviour in #10 **conflicts** with maintainer 1.5.0 contract.

**HW already answered (Stage 3A):** F-PRB printed `ApolloOS` + `68080`, rc 0; U-PRB printed `ApolloOS`, rc 0; production left up. Does **not** prove negative cases or private-adapted binaries (those binaries are now public on 1.5.0, still untested on V4).

**AttnFlags bit 10 is CPU-class evidence, not FPU.**

---

## B. Accessible source versions

| Item | Location / SHA |
|---|---|
| Maintainer `feature/1.5.0` | **PUBLIC** `651a357…` |
| `amiga/amigentd.c` | on 1.5.0 (classic AttnFlags CPU ladder + raw `attn_flags`) |
| `scripts/regress.py` | on 1.5.0 blob `dbb93257…` (697 lines) |
| `amiga_status` / FPU | `src/amigent/server.py` + `system.py` on 1.5.0 (`tests/test_fpu.py` present) |
| `amiga_cpu` | **load sampler**, not CPU-id (`server.py` ~1147) |
| `amigent-setup --update` | `src/amigent/setup.py` on 1.5.0 (includes #38 catalogue) |
| Issue #42 FPU | Implemented on 1.5.0; issue **CLOSED** |
| Packaged Apollo daemon/probe on 1.5.0 | **ABSENT** (`amigentd.apollo` / `amigent-apollo-probe` not in package) |

### What each tree can test

| Test | Fork `main` | Public `main` | Public `feature/1.5.0` |
|---|---|---|---|
| Packaged Apollo AUDIO daemon HW | yes (`63db83ff…`) | via draft #47 only | **no** packaged Apollo binary |
| 1.5.0 FPU host reporting | no | no | yes (source+offline tests) |
| 1.5.0 updater / #38 selection | partial fork `daemons.py` | no | yes |
| Full `regress.py` vs 1.5.0 tools | different host surface | older script | matching script |

---

## C. Request 1 — `regress.py`

### Safety classification (39 checks in `ORDER`)

- **Read-only-ish:** `status`, `version`, `exec`, `missing_volume`, `loaded`, `journal`, `gurus`, `screen`, `wait`, `debug` (without `--kprintf`), `aminet` (search only), `emulator` (skip without gdb)
- **Temp write (RAM:):** `job`, `live_output`, `files`, `tree`, `packing`, `notes`, `close_shell`, optional UI writers
- **Persistent PC state:** `state`, `screen_diff` (config/screens under `~/.config/amigent`)
- **RISKY:** `memory` (PEEK `$DFF000`), `probes` (PEEK `$4`, high-pri sampler), `tasks` (priority change), `trace` (`--trace` only), `hold`, `monitor_text` (launches monitor + TASKCTL)
- **INSTALLER:** `install_undo` (confined under test DIR)
- **UI injection:** `open_shell`, `drag_measure`, `typing`, `ui`, `arexx`, `screen_text`, `steps`
- **Stress:** `takeover` (21 connections)
- **Clipboard:** `clipboard` (may leave test text if clipboard was empty)

**Selective runs:** `--only NAMES` only (no `--skip`). Include `close_shell` when using RAM: scratch DIR.  
**TLS:** automatic if pin present (`port+1`); no CLI key/TLS flags. Plaintext against TLSONLY fails closed.  
**Does not** restart/quit amigentd (except monitor TASKCTL Ctrl-C). Failed connect may trigger `machines.relocate` (LAN sweep).  
**Protocol:** many checks need ≥5; `loaded`/`memory`/`tasks`/`probes`/`trace` need 6 + capabilities.

### Offline

- Script existence and structure verified on 1.5.0.  
- No hardware `regress.py` run has been performed. D4/D5/D5B are **not** substitutes.

### Safe HW subset (proposed)

```text
python scripts/regress.py <address> --only status,version,exec,missing_volume,job,live_output,loaded,journal,gurus,screen,state,files,tree,packing,notes,screen_diff,close_shell
```

**Exclude:** `--trace`, `--pointer`, `--kprintf`, `--aminet`; and checks `memory`, `probes`, `tasks`, `trace`, `monitor_text`, UI injection group, `clipboard`, `install_undo`, `takeover` (optional), `pause` (optional).

**NO-GO for unrestricted full script** on exclusive candidate without per-check review of UI/RISK/INST items.

### Candidate provenance

| Field | Value |
|---|---|
| SHA-256 | `63db83ff021c47f7146e0872cd36bf90eb201f36a0cf455a58f3c518a84e8ef1` |
| Size | 128744 |
| Prior HW | D4 smoke + D5 AUDIO + D5B Viewer Hear |
| Rebuild for regress? | **Not required** for that identity |
| 1.5.0 packaged substitute | Classic `amigentd` `def99527…` (113068 B) — **different identity**, unvalidated on V4 |

---

## D. Request 2 — CPU / FPU

### Naming trap

| Tool | What it actually is |
|---|---|
| `amiga_status` | JSON report: system facts, SYSINFO, volumes, FPU line via AttnFlags |
| `amiga_cpu` | **Per-task CPU load sampler** (protocol 6 `probe`), **not** CPU model identification |

### Existing HW (pre-1.5.0 tools / Apollo daemon SYSINFO)

- Board V4-SA, ApolloOS, Kickstart 51.51, CPU **68080**  
- `attn_flags=42111` (`0xa47f`) — bit 10 set  
- Stage 3A probes / D4 SYSINFO: ApolloOS / 68080  

**CPU identification verified on hardware** (daemon SYSINFO + probes).

### FPU (1.5.0 source, offline)

- FPU from AttnFlags bits `AFF_FPU40|AFF_68881|AFF_68882` — **not** from bit 10 alone.  
- Offline: `describe_fpu(42111)` → `68080 with FPU`; `describe_fpu(1<<10)` → `68080, no FPU`.  
- 68080 path does **not** require `68040.library` / `68060.library`.  
- Offline tests: `tests/test_fpu.py` + related → **42 passed** on 1.5.0 worktree.

### Gaps / pitfalls

1. **No verbatim live `amiga_status` / `amiga_cpu` output** captured with 1.5.0 host against V4.  
2. Classic **1.5.0 daemon** SYSINFO `cpu` field uses old AttnFlags ladder → for flags `0xa47f` computes **68040**, not 68080; 68080 appears via raw `attn_flags` + host `describe_fpu` / `C:CPU` text. Apollo-packaged daemons (fork) force `cpu=68080` in SYSINFO — **not shipped in 1.5.0 package**.  
3. Do **not** execute FPU instructions to “prove” FPU.  
4. Issue #42’s PiStorm note is not a V4 result.

**Verdict:** CPU **verified on HW**. FPU reporting **logic verified offline**; **live FPU line untested**. 1.5.0 implementation **source available**, HW against it **pending**.

---

## E. Request 3 — `amigent-setup --update`

### Never done on physical V4 production

Prior work = exclusive staged launches + restore. **Not** a live `--update` transaction.

### 1.5.0 updater inventory (can modify)

`C:amigentd`, `C:amigentd.new`, `C:amigentd.old`, `T:amigent-update.rexx`, `T:amigent-update.done`, optional `ENVARC:amigent-home` / `amigent-spare`, home scripts (`amigent-repair`, `amigent-scan`, `menu-add.rexx`, status/monitor), spare copies (including key/TLS files).  
**Reads** `S:User-Startup` for args; does **not** rewrite it on update.  
Scripts/home renewed even when daemon replacement is skipped.

### Critical packaging fact

1.5.0 wheel/bin has **no** `amigentd.apollo`. On ApolloOS, selection falls back to **classic** `amigentd`.  
Offline: unknown installed **1.4.0** bytes → **replace=True** with packaged 1.5.0 classic (no `--force` needed). Same-version unknown → keep unless `--force`.

→ A naïve live `--update` on current production Apollo `b00fef0e…` / protocol-5 Apollo install risks **replacing Apollo daemon with classic 1.5.0** unless packaging/policy is fixed first.

### Offline tests (1.5.0 worktree)

`pytest -k 'update or setup or replacement or consider'` → **40 passed, 4 skipped**.

### Live update GO/NO-GO

**NO-GO** until:

1. Separate explicit authorisation for persistent production change.  
2. Backups of **every** path above (not only `C:amigentd`); existing `~/amigent-evidence/.../v4-production-C-amigentd.bin` is necessary but **not sufficient**.  
3. Written expected selection (classic vs Apollo) and acceptance of downgrade-from-Apollo if that is the outcome.  
4. No casual `--force`.  
5. Physical console recovery + restore drill.  
6. Post-update TLS/SYSINFO ×2 + restore to `b00fef0e…` plan.

---

## F. One consolidated HW plan (when authorised)

**Session A — exclusive candidate (preferred first)**  
1. Production TLS/SYSINFO preflight (hash `b00fef0e…`).  
2. Stage `63db83ff…` off `C:`; launch exclusive; TLS.  
3. Safe `regress.py --only …` subset.  
4. Read-only: capture `amiga_status` JSON + note `amiga_cpu` is load sampler; record SYSINFO `cpu`/`attn_flags`.  
5. QUIT candidate; restore production; SYSINFO ×2.  

**Session B — live `--update` (separate authorisation)**  
Only after packaging/policy decision on Apollo binary. Not combined with unrestricted regress.

---

## G. Draft maintainer response (**NOT POSTED**)

> Thanks for publishing `feature/1.5.0` — we can now work against that tree (`651a357…`).
>
> **1. Native daemon + `regress.py`**  
> We have not yet run `scripts/regress.py` on the V4. Earlier D4/D5/D5B sessions validated startup/TLS/SYSINFO and AUDIO/Hear for `63db83ff…` only; they are not a full regress. We inspected the 1.5.0 script and prepared a read-mostly `--only` subset that avoids TRACE, UI injection, clipboard, monitor launch, and installer checks. We can run that on an exclusive staged candidate (not live `C:amigentd`) once a hardware session is authorised.
>
> **2. `amiga_status` / `amiga_cpu` / FPU**  
> On hardware we already see ApolloOS, Kickstart 51.51, CPU 68080, and `attn_flags=42111` (bit 10 set). We have **not** yet captured live `amiga_status` output with the 1.5.0 host tools. Offline, 1.5.0’s FPU logic correctly treats bit 10 as 68080-class, not as FPU; FPU comes from separate AttnFlags FPU bits. Note: `amiga_cpu` in Amigent is the per-task load sampler, not the CPU-model report — model/FPU appear under `amiga_status` / inventory. We will capture verbatim outputs in the next authorised read-only pass.
>
> **3. `amigent-setup --update`**  
> Not yet run against the production V4 install. Offline review of 1.5.0 shows scripts/home can renew even when the daemon is unchanged, and that the public 1.5.0 package currently ships no `amigentd.apollo`, so an ApolloOS update would select the classic daemon. We will not perform a live `--update` on production until that packaging/policy point is agreed and we have separate authorisation plus backups of every path the updater can touch.
>
> **Probe / #10**  
> Stage 3A already confirmed our probe positive case (`ApolloOS`/`68080`). We do not plan another upstream PR for fork #10; 1.5.0’s exec-51 + bit-10 detect matches the maintainer direction, and the old `$DFF3FC` OS fallback should stay out.

---

## Confirmations

- Fork `main`, protected contribution tips, draft PRs #46/#47/#48, and V4 production **not modified** by this investigation.  
- No upstream comment posted.  
- No native rebuild performed for this brief.
